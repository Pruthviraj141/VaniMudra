# 🤟 SignVision — System Architecture & Hackathon Build Plan

> **Hackathon**: Built in 6 hours | **Team**: SignVision | **Date**: October 9, 2026  
> **Mission**: Bridge the communication gap between 2.7 million Deaf/Hard-of-Hearing Indians and the hearing world using AI-powered Indian Sign Language translation.

---

## 🎯 The Problem

India has ~**2.7 million Deaf/Hard-of-Hearing individuals** (Census 2011). Indian Sign Language (ISL) is their primary language. Yet:

- Most hearing people don't know a single sign
- Existing ISL tools are desktop-only, fragmented, or incomplete dictionaries
- No mobile-first, AI-powered, real-time ISL translator exists for India
- Communication in hospitals, schools, and public services remains a daily barrier

**SignVision solves this** — give anyone a phone and they can communicate through Indian Sign Language instantly.

---

## 🏗️ High-Level System Architecture

![Image Description](diagrams/architecture.png)

---

## 🧱 Component Breakdown

### 1. Mobile App — `Application/` (Expo / React Native)

The user-facing layer. Single-screen app with two modes: offline word lookup and online AI sentence translation.

| Component | File | Responsibility |
|---|---|---|
| **HomeScreen** | `src/screens/HomeScreen.tsx` | Central state machine — manages sign queue, playback status, gloss tokens, search history |
| **SearchBar** | `src/components/SearchBar.tsx` | Text input + `expo-speech-recognition` voice input with interim transcripts |
| **AvatarWebView** | `src/components/AvatarWebView.tsx` | Embeds CWASA WebGL 3D avatar via WebView; bidirectional `postMessage` bridge |
| **s3Service** | `src/services/s3Service.ts` | Offline word dictionary (Dice coefficient similarity, 1,500+ signs, zero network) |
| **apiService** | `src/services/apiService.ts` | Typed REST client for backend; retries with exponential backoff; `AbortController` timeouts |
| **Types** | `src/types/index.ts` | Single source of truth for all TypeScript types; mirrors Pydantic models exactly |

**Key Design: Refs + State Double-Buffer**  
`HomeScreen` mirrors `signQueue` and `currentQueueIndex` into refs (`signQueueRef`, `currentQueueIndexRef`) to solve React's stale closure problem inside the `handleFinished` WebView callback. Effect-driven queue playback ensures race-free sequential sign animation.

---

### 2. Core Backend — `backend/` (Python / FastAPI @ port 8000)

The AI brain. Converts English text to ISL GLOSS tokens via a 6-stage NLP pipeline.

#### NLP Pipeline (`app/core/nlp_engine.py`)

```
English Sentence
      │
      ▼
① Preprocessing         — lowercase, expand contractions, split sentences
      │
      ▼
② Fixed Expression       — shortcircuit for "how are you", "thank you", etc. (no AI needed)
      │
      ▼
③ spaCy POS Analysis     — en_core_web_trf transformer model for accurate tagging
      │
      ▼
④ NVIDIA LLM Extraction  — GPT-oss-120b extracts {subject, object, verb, tense, negation, ...}
      │
      ▼
⑤ ISL Rule Transform     — apply ISL grammar: strip articles, prepend time markers,
      │                     WH-words to end, sentence-final Q markers (ISL topic-prominent)
      ▼
⑥ GLOSS Assembly         — [TIME] [SUBJECT] [OBJECT] [VERB] [ADJ] [NOT?] [WH?]
      │
      ▼
Word Lookup → S3 URLs → Response JSON
```

**ISL Grammar Rules Applied:**
- ❌ No articles (`a`, `an`, `the` are dropped)
- ❌ No auxiliary verbs (`is`, `was`, `are`, `am`)
- ⏰ Time markers prepended (`YESTERDAY`, `NOW`, `FUTURE`)
- ❓ WH-questions: WH-word moves to sentence end
- ✅/❌ Yes/No questions: `Q` marker appended

#### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/process` | Full text → NLP → GLOSS → S3 sign URLs |
| `POST` | `/transcribe` | `.wav` audio → text → `/process` |
| `GET` | `/lookup/{word}` | Single word with semantic fallback |
| `GET` | `/search?query=` | Vector similarity search (ChromaDB) |
| `GET` | `/health` | Health + word dictionary count |

#### Services

| Service | Technology | Role |
|---|---|---|
| **WordLookupService** | JSON dict in-memory | 4-tier lookup: exact → anchor → partial → semantic |
| **SemanticSearchService** | `all-MiniLM-L6-v2` + ChromaDB (HNSW) | "Did you mean?" — 384-dim cosine similarity |

---

### 3. Video Microservice — `video-service/` (Python / FastAPI @ port 8001)

Dedicated inference endpoint for ISL-to-English recognition.

```
.mp4 / .webm chunk
      │
      ▼
POST /api/translate-video
      │
      ▼
Google Gemini Vision API  (multimodal: video frames + prompt)
      │
      ▼
English text transcript
```

The Gemini prompt is heavily engineered to understand ISL handshapes, movements, and body positioning, translating them directly to English words/phrases.

---

### 4. Data Layer

| Store | Technology | Size | Use |
|---|---|---|---|
| **Sign Dictionary** | `sign_language_data.json` | ~200KB, 1,500+ entries | Word → S3 URL mapping; bundled in app AND used by backend |
| **Vector Store** | ChromaDB (SQLite + HNSW) | ~20,000 word embeddings | Semantic nearest-neighbor lookups |
| **SiGML Files** | AWS S3 (`ap-south-1`) | Per-sign XMLs | 3D avatar animation source; streamed at playback time |
| **Local History** | AsyncStorage | Last 20 searches | Offline-persistent search history on device |

**Sign Dictionary Schema:**
```json
"SCHOOL": {
  "anchors": ["COLLEGE", "UNIVERSITY"],
  "category": "noun",
  "s3_url": "https://signvision-085587597556.s3.ap-south-1.amazonaws.com/sigml-files/school.sigml",
  "hamnosys": "..."
}
```

---

### 5. The CWASA Avatar

The 3D signing avatar is powered by the **University of East Anglia's CWASA** (Connected World Avatar System for Accessibility).

- **Rendering**: WebGL 3D — runs inside WebView at 30 FPS
- **Format**: SiGML (Signing Gesture Markup Language) — XML encoding of 3D hand/body motion
- **Bridge**: `postMessage(JSON)` — bidirectional React Native ↔ WebView event protocol
- **Avatars**: `anna` (default), `marc`, `francoise`, `luna`

**Why WebView and not native 3D?**  
CWASA is a mature, proven ISL animation research system. Native reimplementation in Unity or SceneKit would take months. WebView embedding makes the full ISL signing library available immediately, with hardware-accelerated WebGL in a separate process that doesn't block the RN UI thread.

---

## 🔄 End-to-End Data Flows

### Flow A: Word Mode (Offline, ~instant)

```
User types "APPLE"
    → s3Service.lookupWord("apple")
    → normalize → "APPLE"
    → exact match in bundled JSON → s3_url
    → avatarRef.play(s3_url, "APPLE")
    → WebView: CWASA fetches apple.sigml from S3
    → 3D avatar signs "APPLE"
    → finished event → history saved to AsyncStorage
```
**No backend. No network except S3 fetch. Works offline if S3 not needed.**

---

### Flow B: Sentence Mode (Online, AI-powered, ~3-8s)

```
User speaks "I am not going to school"
    → expo-speech-recognition → transcript
    → POST :8000/process { text: "..." }
    → NLP Pipeline (6 stages)
        → spaCy POS → LLM extract → ISL rules → GLOSS
        → GLOSS: [FUTURE, I, SCHOOL, GO, NOT]
        → word lookup → 5 S3 URLs
    → Response JSON
    → signQueue = [{word, url}, {word, url}, ...]
    → useEffect: play sign 0 (FUTURE)
    → avatar finishes → advance index → play sign 1 (I)
    → ... sequential until all 5 signs played
```

---

### Flow C: Video Recognition (ISL → English)

```
User records ISL sign video
    → .mp4 chunk → POST :8001/api/translate-video
    → Gemini Vision API (multimodal inference)
    → English text → displayed to user
```

---

## ⚙️ Technology Stack

| Layer | Technology | Why |
|---|---|---|
| **Mobile** | Expo / React Native (TypeScript) | Cross-platform, native speech permissions, EAS cloud builds |
| **Voice Input** | `expo-speech-recognition` | Native `SpeechRecognizer` / `SFSpeechRecognizer` bindings; interim results |
| **Avatar** | CWASA WebView (WebGL/SiGML) | Pre-proven ISL signing library; avoids months of native 3D work |
| **AI Backend** | Python + FastAPI + Uvicorn | Best ML ecosystem, async, auto-OpenAPI, Pydantic type safety |
| **NLP** | spaCy `en_core_web_trf` | Transformer-based POS — most accurate for ambiguous English words |
| **LLM** | NVIDIA API `gpt-oss-120b` | 120B parameter reasoning model; OpenAI-compatible; no OpenAI credits |
| **Semantic Search** | `all-MiniLM-L6-v2` + ChromaDB | 384-dim embeddings; HNSW O(log n) ANN; "Did you mean?" fallback |
| **Video AI** | Google Gemini Vision API | Best multimodal model for video understanding |
| **Storage** | AWS S3 (`ap-south-1`) | Global CDN-class delivery of SiGML animation files |
| **Offline Dict** | Bundled JSON (200KB) | Zero-network word mode; works in any connectivity condition |

---

## 🗂️ Repository Structure

```
Signvision/
├── Application/                 # Expo React Native Mobile App
│   ├── App.tsx                  # Root component
│   ├── app.json                 # Expo config (permissions, build metadata)
│   ├── eas.json                 # EAS Build profiles (dev/preview/production)
│   └── src/
│       ├── components/
│       │   ├── AvatarWebView.tsx    # CWASA 3D avatar WebView bridge
│       │   └── SearchBar.tsx        # Search + voice recognition UI
│       ├── screens/
│       │   └── HomeScreen.tsx       # Main screen + full state machine
│       ├── services/
│       │   ├── apiService.ts        # Typed REST client for backend
│       │   └── s3Service.ts         # Offline word lookup + S3 URL utils
│       ├── types/
│       │   └── index.ts             # Canonical TypeScript types
│       └── data/
│           └── sign_language_data.json  # Bundled 1,500+ word ISL dictionary
│
├── backend/                     # Python FastAPI AI Engine
│   └── app/
│       ├── main.py              # FastAPI app + all endpoints
│       ├── core/
│       │   ├── config.py        # Pydantic Settings (env vars)
│       │   └── nlp_engine.py    # 6-stage NLP pipeline (817 lines)
│       └── services/
│           ├── word_lookup.py   # 4-tier sign dictionary lookup
│           └── semantic_search.py  # ChromaDB vector similarity
│
├── video-service/               # ISL Video → English Microservice
│   └── main.py                  # Gemini Vision API inference endpoint
│
├── data/
│   ├── sign_language_data.json  # Master ISL dictionary (source of truth)
│   └── Initial-sigml-files/     # Raw .sigml animation sources
│
├── dataset/                     # Raw ISL data (a-z letters, numbers)
├── feats/                       # Semantic search spike / prototypes
├── docs/                        # Architecture diagrams, research drafts
│
├── arch.md                      # ← This file: system architecture
├── PROJECT_INFO.md              # Project overview
├── AGENTS.md                    # AI agent contribution guide
└── info.md                      # Full technical documentation
```

---

## ⏱️ 6-Hour Hackathon Build Timeline

> This is exactly how we built SignVision from concept to demo in 6 hours.

| Hour | Phase | What We Built |
|------|-------|---------------|
| **0:00 – 0:30** | 🧠 **Architecture** | System design, data flow, API contracts. This `arch.md`. |
| **0:30 – 1:30** | 🗄️ **Data Layer** | `sign_language_data.json` dictionary (1,500+ words → S3 URLs). Ran `build_embeddings()` to generate ChromaDB vector store. |
| **1:30 – 2:30** | ⚙️ **Core Backend** | FastAPI skeleton → health endpoint → `word_lookup.py` → `semantic_search.py` → `/lookup/{word}` working end-to-end. |
| **2:30 – 3:30** | 🧠 **NLP Engine** | 6-stage pipeline: preprocessing → spaCy POS → NVIDIA LLM extraction → ISL rule transform → GLOSS assembly → `/process` endpoint live. |
| **3:30 – 4:15** | 📱 **Mobile App** | Expo scaffold → `HomeScreen` state machine → `s3Service` offline lookup → Word Mode working on device. |
| **4:15 – 5:00** | 🤟 **Avatar Integration** | `AvatarWebView` with CWASA WebGL. `postMessage` bridge. Sign queue playback loop. Sentence Mode end-to-end. |
| **5:00 – 5:30** | 🎙️ **Voice Recognition** | `expo-speech-recognition` integrated into `SearchBar`. Permissions, interim results, language fallback. |
| **5:30 – 6:00** | 🎥 **Video Service + Polish** | `video-service` Gemini endpoint. UI polish, error states, search history, GLOSS breadcrumb UI. Demo prep. |

---

## 🔐 Security & Configuration

All secrets and keys are loaded from environment variables — **never hardcoded**.

| Variable | Service |
|---|---|
| `GPT_API_KEY` | NVIDIA LLM API (sentence translation) |
| `GEMINI_API_KEY` | Google Gemini (video recognition) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 bucket access |

Config is managed via `pydantic-settings` (`app/core/config.py`) with `.env` file fallback. `@lru_cache()` ensures single-load at startup.

---

## 📡 API Contract (TypeScript ↔ Pydantic)

The frontend TypeScript types in `src/types/index.ts` are **exact mirrors** of the backend Pydantic models. This ensures compile-time type safety across the stack.

```typescript
// Frontend — TypeScript
interface SignQueueItem {
  word: string;
  url: string;
  matchType: 'exact' | 'anchor' | 'partial' | 'semantic' | 'none';
}

interface ProcessResponse {
  gloss: { tokens: string[]; sentence: string };
  signs: SignQueueItem[];
  processing_time_ms: number;
}
```

```python
# Backend — Pydantic
class SignResult(BaseModel):
    word: str
    url: str
    match_type: Literal['exact', 'anchor', 'partial', 'semantic', 'none']

class ProcessResponse(BaseModel):
    gloss: GlossOutput
    signs: List[SignResult]
    processing_time_ms: float
```

---

## 🚀 Running the Project

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_trf
uvicorn app.main:app --reload --port 8000
```

### 2. Video Microservice

```bash
cd video-service
uvicorn main:app --reload --port 8001
```

### 3. Mobile App

```bash
cd Application
npm install
npx expo start
```

### 4. Health Check

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
```

---

## 🔮 What Makes This World-Class

| Feature | Impact |
|---|---|
| **Offline-first word mode** | Works in zero-connectivity environments (hospitals, rural areas) |
| **True ISL grammar** | Not just word-by-word substitution — applies real ISL topic-prominent grammar rules |
| **Voice → ISL in one tap** | Hearing person speaks → Deaf person sees sign animation. Zero friction. |
| **Semantic fallback** | Typing `"furious"` finds `"ANGRY"` via vector similarity — handles vocabulary gaps gracefully |
| **Bidirectional** | English → ISL (text/voice) AND ISL video → English — full two-way communication |
| **Real 3D avatar** | CWASA is a research-grade, UEA-developed ISL avatar — not animated GIFs or drawings |
| **1,500+ signs** | Covers nouns, verbs, adjectives, pronouns, time markers, WH-words, numbers, alphabets |
| **Production architecture** | FastAPI + Pydantic + TypeScript types + ChromaDB — not a toy demo |

---

## 📐 Design Principles

1. **Offline-first**: Word mode requires zero network. Add network capability for AI, not replace it.
2. **Type-safe full stack**: TypeScript frontend types mirror Pydantic backend models exactly.
3. **Staged AI**: Fixed expressions first (fast) → spaCy (structured) → LLM (semantic) → fallback. Every stage has a fallback.
4. **Imperative avatar, declarative UI**: The React state machine drives the queue declaratively; the avatar is called imperatively via refs. Clean separation.
5. **Single source of truth for data**: `sign_language_data.json` is maintained once; synced to both backend and bundled in application.

---

*Built with ❤️ for accessibility. Indian Sign Language is a full, rich language. SignVision treats it as one.*
