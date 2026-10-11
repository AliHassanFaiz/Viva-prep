<<<<<<< HEAD
# ViVa Prep

A live AI examiner that prepares students to defend their own work. Upload a report, review 2-4 questions, hold a spoken mock viva, get a readiness report. Built to `SPEC.md`.

## Run locally

**Backend** (Python 3.11+)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill GROQ_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
uvicorn app.main:app --reload --port 8000
```
Leave `DATABASE_URL` and `QDRANT_URL` empty for a zero-setup dev run (SQLite + in-memory Qdrant). For production paste your Neon string (`postgresql://...?sslmode=require` works as-is) and Qdrant Cloud URL/key. Tables are created on startup.

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_URL / VITE_WS_URL
npm run dev                 # http://localhost:5173
```

**One-time: static audio clips** (SPEC section 13)
```bash
cd backend && python -m scripts.make_static_audio   # writes frontend/public/audio/*.mp3
```
Without them the app still works: the browser's built-in voice is used for greeting/closing.

## Day-one smoke tests (SPEC section 16)
```bash
python -m scripts.smoke_stt answer.wav   # WAV -> Whisper
python -m scripts.smoke_stt --tts        # ElevenLabs mp3 + streamed PCM
python -m scripts.smoke_stt --qdrant     # insert + filtered search
```

## Tests
`cd backend && pytest` - unit tests plus an end-to-end test (upload -> questions -> session -> WebSocket call with follow-up, repeat, resume -> report -> delete) using mocked Groq/ElevenLabs.

## Deploy
- Backend: any WebSocket-capable host that doesn't sleep (Railway/Render). Use the `Dockerfile`. Set all variables from `.env.example`; `ALLOWED_ORIGINS` must include the frontend URL.
- Frontend: Vercel (`vercel.json` handles SPA routing). Set `VITE_API_URL` (https) and `VITE_WS_URL` (wss). Microphone needs HTTPS.

## Things to verify on your accounts (SPEC says "verify")
- `MODEL_REPORT=qwen/qwen3.8-27b` is the spec's name; change it in `.env` if Groq lists a different id. The client automatically falls back to plain JSON mode if a model rejects strict schemas or `reasoning_effort`.
- ElevenLabs `pcm_24000` output may not be allowed on your plan; the server falls back to pcm_22050, pcm_16000, then mp3.
- Tune thresholds in `backend/app/config.py` and `frontend/src/lib/settings.ts`.

## Small deviations from the spec
- Proposed questions are stored `accepted=true` (the UI treats them as accepted by default, and this survives reloads).
- Extra endpoints: `GET /api/documents/{id}/questions`, `GET /api/metrics` (average stage timings for the pitch).
- Extra optional WebSocket message `speech_start` so the "repeat?" nudge never fires while the student is talking.
=======
# Viva-Preprartion
>>>>>>> 1a4760516ff546ec6aff90c7da673f3babe23611
