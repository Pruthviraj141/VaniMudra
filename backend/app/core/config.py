import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    CHROMA_DB_PATH: str = "./data/chroma_db"
    CHROMA_COLLECTION: str = "words"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    SEMANTIC_SEARCH_TOP_K: int = 5
    SEMANTIC_SEARCH_MIN_SIMILARITY: float = 0.5

    DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"
    SIGN_LANGUAGE_DATA_FILE: str = "sign_language_data.json"
    WORDS_FILE: str = "words.txt"

    RECORDINGS_DIR: str = "./recordings"

    class Config:
        env_file = str(Path(__file__).resolve().parent.parent.parent.parent / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
