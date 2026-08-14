# CheckMate

AI-powered answer-sheet grading — a native Android app backed by a FastAPI service
that runs OCR and LLM-based grading (Gemini, with OpenAI/Anthropic/Ollama fallbacks).

## Project structure
- `android/` — native Android app (Kotlin)
- `backend/` — FastAPI backend (OCR + grading pipeline)

## Backend setup
1. `cd backend`
2. Create a virtual env and install deps: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your API keys
4. Run: `uvicorn app.main:app --reload`

## Notes
- Never commit your `.env` — it holds secret API keys (already gitignored).