# Data

## Overview
The `data` folder primarily stores large JSON files or foundational data required by the `backend` for serving Indian Sign Language representations.

## Structure
*   `sign_language_data.json`: A large JSON dictionary mapping English words/gloss to their respective assets (likely paths, URLs, or metadata indicating how to render the sign).
*   `Initial-sigml-files/`: May contain SiGML (Signing Gesture Markup Language) used to animate a virtual avatar if video fallbacks aren't present.

## Features
*   Acts as the central local database mapping words -> signs for the ISL engine.
*   The `backend` reads this mapping into memory during lookups.
