# ViVa Prep: A Live AI Examiner That Prepares Students to Defend Their Own Work

**Event:** 4th International AI Championship (AIEF) | **Category:** Intelligent App Creation (AI-native apps with adaptive, intelligent UX)
**Team:** VivaForge | **Members:** Sameer (UMT Lahore, BS IT, 7th semester) · Ali Hassan (UMT Lahore, BS IT, 7th semester) · Umair (UMT Lahore, BS IT, 7th semester) · Hammad (UMT Lahore, BS IT, 7th semester)
**Repository / Demo:** https://github.com/AliHassanFaiz/Viva-prep.git 

---

## 1. Project Overview & Problem Statement

Students spend months on a thesis, final-year project, or research paper, then face a viva or defense that lasts less than an hour. Many freeze, ramble, or cannot justify decisions they made themselves. The reasons are simple:

* **No realistic practice.** Friends are too kind, and supervisors have limited time.
* **No feedback on weak spots.** Students do not know which parts of their own project they cannot defend.
* **No pressure training.** Speaking clearly while being questioned is a skill that needs repetition, and typing answers into a chatbot does not build it.

This affects every final-year student, and it is hardest for those without access to experienced mentors.

## 2. Proposed Solution

ViVa Prep is an AI examiner built around the student's own document. The student uploads a report, and the app runs a short, live, spoken mock viva in English.

**The user journey**

1. **Upload.** The student uploads a report (PDF or Word). The system reads it, splits it into sections, and stores it for retrieval.
2. **Question proposal.** A language model proposes 2 to 4 questions drawn from the report. The student reviews them and accepts, edits, or removes any before the session starts.
3. **Live voice call.** The student starts a real-time voice session over a WebSocket connection. The examiner asks each question out loud and listens. The app detects pauses so the student is not cut off, and the student can interrupt the examiner at any time.
4. **One smart follow-up.** If an answer is vague, too short, or gives no reason, the examiner asks **one** follow-up on the same question and then moves on. If the answer is clear, it moves straight to the next question. Nothing is scored during the call, so it feels like a real viva.
5. **Evaluation after the call.** When the call ends, the full transcript is evaluated against a rubric and the matching passages from the report. The student receives a readiness report with a score per question, strengths, gaps, and model answers.
6. **History.** Every session is saved, so the student can reopen past sessions and compare practice rounds.

### 2.1 System architecture

```
                 ┌──────────────────────────────────────────────┐
                 │        Browser (React + Vite, HTTPS)         │
                 │  Upload · Question review · Call · Report ·  │
                 │  History                                     │
                 │  Mic → voice activity detection → WAV chunk  │
                 │  Audio player: cached questions, filler      │
                 │  clips, streamed follow-ups                  │
                 └───────┬───────────────────────────┬──────────┘
                    REST │                           │ WebSocket (wss)
                 ┌───────▼───────────────────────────▼──────────┐
                 │          FastAPI backend (cloud host)        │
                 │  Document service    Question service        │
                 │  Call orchestrator   Evaluation worker       │
                 └───┬─────────┬──────────────┬──────────┬──────┘
                     │         │              │          │
              Qdrant Cloud  Neon Postgres   Groq API   ElevenLabs
              (chunk        (sessions,      (see 2.2)  (examiner
               vectors)      turns, reports,            voice)
                             history)
```

### 2.2 Components and models

| Component | Technology | Job |
|-----------|------------|-----|
| Question generation | Groq `openai/gpt-oss-20b` | Reads a few retrieved report passages and proposes 2 to 4 questions with the key points a good answer should contain |
| Live decision | Groq `openai/gpt-oss-120b` (low reasoning effort, JSON output) | After each answer, decides: clear, vague, or "student asked to repeat the question" |
| Speech to text | Groq `whisper-large-v3-turbo` | Transcribes each finished spoken answer (English, with a vocabulary hint from the report) |
| Text to speech | ElevenLabs Flash v2.5 (or Turbo v2.5) | The examiner's voice |
| Final report | Groq `qwen/qwen3.8-27b` (JSON output) | Scores each answer and writes the readiness report |
| Embeddings | Open-source model (bge-small-en-v1.5, 384 dimensions) | Turns report chunks into vectors |
| Vector database | Qdrant Cloud | Stores and searches report chunks |
| Storage | Neon PostgreSQL | Sessions, questions, transcript turns, reports, history |
| Backend | FastAPI (REST and WebSocket), LangGraph optional | Orchestrates everything |
| Frontend | React with Vite, browser voice activity detection | Call screen, report, history |

## 3. Objectives & Expected Outcomes

| # | Objective | Expected outcome |
|---|-----------|------------------|
| 1 | Make practice realistic | A live spoken viva with questions drawn from the student's own report |
| 2 | Keep the student in control | The student accepts or edits the proposed questions before the call starts |
| 3 | Make the call feel natural | Pauses are detected without cutting the student off, the examiner stops speaking when interrupted, and the voice is clear and low-delay |
| 4 | Probe weak answers | One follow-up is asked only when an answer is vague, then the call moves on |
| 5 | Give fair, grounded feedback | End-of-call evaluation of the whole transcript, checked against the report text |
| 6 | Pinpoint weak areas and track progress | A readiness report per session and a history of past sessions |
| 7 | Show it works | A small pilot with students, reporting self-rated confidence before and after, response delay measurements, and agreement between AI scores and human ratings |

Pilot results will be reported with their limits (small sample, self-reported confidence).

## 4. Target Users

* **Primary:** Final-year undergraduate and master's students preparing for project defenses and thesis vivas.
* **Secondary:** Students preparing for research presentations or interviews about a past project.
* **Tertiary:** Supervisors who want to give students extra practice without extra time.

## 5. Key Features / Deliverables

* **Report upload** (PDF or Word) with section-aware reading and retrieval
* **Question proposal screen** where the student sees 2 to 4 generated questions and accepts, edits, or removes them
* **Live voice call** over WebSocket with Whisper transcription and a natural ElevenLabs voice
* **Pause detection** that decides when the student has finished speaking, with a manual "I'm done" fallback
* **Interruption handling (barge-in)** so the examiner stops speaking as soon as the student starts talking
* **Pre-generated question audio** so the next question starts instantly after a clear answer
* **Vagueness check** that triggers a single follow-up per question when needed, and replays the question if the student asks for it
* **Saved transcript** written turn by turn, so a dropped connection does not lose the session
* **Post-call evaluation** with a rubric covering accuracy against the report, completeness, clarity, and justification
* **Readiness report** with per-question scores, strengths, gaps, and model answers
* **Session history** stored in the database, so the student can reopen past sessions and compare practice rounds
* **Delete my data** option for uploaded reports and sessions

## 6. Implementation Plan & Timeline

| Dates (2026) | Milestone | Details |
|--------------|-----------|---------|
| **Oct 10 (today)** | Foundations | Set up accounts and keys; test one recorded WAV answer through Whisper; database tables; report upload, chunking, embedding, and Qdrant storage; question generation and the accept/edit screen; pre-generate question audio and static filler clips |
| **Oct 11** | Live voice call | WebSocket call loop: voice activity detection, pause handling, Whisper transcription, vagueness decision, cached question playback, streamed follow-up voice, transcript saving; then interruption handling (build last) |
| **Oct 12** | Report, history, and submission | Post-call evaluation and readiness report; history page; deploy over HTTPS; quick test with 3 to 5 students; README and demo video; submit before the deadline |
| **Oct 16** | Shortlist announced | Review screening feedback |
| **Oct 17–23** | Mentorship and upgrade | Tune pause and interruption settings with real testers, add examiner styles, compare AI scores with human ratings, run a larger pilot, rehearse the pitch with a recorded backup |
| **Oct 24** | Final pitch | Live demo at FAST-NUCES, Lahore (or virtual) |

If time runs short, cut in this order: interruption handling (replace with a "stop" button), history comparison, examiner styles. Keep the call, the follow-up, and the post-call report.

## 7. Resources or Requirements

**Team:** 4 members covering backend and AI, frontend and voice, evaluation and pilot, and documentation/pitch.

**Technology stack:**
* Backend: FastAPI with WebSocket support, LangGraph for the examiner workflow (optional)
* Language models (Groq): gpt-oss-20b (questions), gpt-oss-120b (live decision), qwen3.8-27b (final report)
* Speech to text: Whisper large-v3-turbo (Groq)
* Text to speech: ElevenLabs Flash v2.5 (or Turbo v2.5)
* Retrieval: Qdrant Cloud with an open-source embedding model (bge-small-en-v1.5, run in the backend)
* Storage: PostgreSQL (Neon)
* Frontend: React with Vite, browser voice activity detection
* Deployment: backend on a host that supports WebSockets (for example Railway or Render), frontend on Vercel, all over HTTPS (browsers require a secure connection for microphone access)

## 8. Potential Challenges or Risks

| Risk | Mitigation |
|------|------------|
| Questions or scores not supported by the report | Ground every question and score in retrieved passages, and store the source passage with each question |
| Student is cut off, or the call waits too long after silence | Use a silence threshold of about 1.2 to 1.5 seconds, ignore very short sounds, and offer an "I'm done" button |
| Whisper writes text for silence or noise | Send only audio where speech was detected, and discard transcripts flagged as no-speech |
| Student speaks while the examiner is talking, or the examiner's voice is picked up by the microphone | Stop playback the moment speech is detected, require a minimum speech length, use echo cancellation, and use headphones for the demo |
| Delay after the student stops speaking feels awkward | Pre-generate question audio, keep follow-ups to one short sentence, stream the follow-up voice, play a short filler clip, and show Listening, Thinking, and Speaking states |
| Free-tier rate limits (several judges testing at once) | Send only relevant passages, keep prompts short, retry with backoff, fall back to the smaller model for the follow-up decision, and process the report one question at a time |
| ElevenLabs free allowance runs out | Pre-generate and reuse static clips, keep examiner sentences short, and fall back to the browser's built-in voice if the allowance is used up |
| Technical terms mis-heard by speech recognition | Pass key terms from the report as a vocabulary hint, show the transcript, and allow typing as a fallback |
| AI scoring is inconsistent or too lenient | Use a fixed rubric, test against human ratings, and show the reasoning behind each score |
| Unpublished student work is private | Process files only for the session, allow deletion of reports and sessions, and treat report text and spoken answers as data, never as instructions |
| Backend sleeps or drops the connection | Use a host without cold starts for the demo, reconnect automatically, and resume from the saved transcript |
| Short build window | Build in order: basic call, pauses, voice quality, history, then interruption; keep a "stop" button as a fallback |

## 9. Additional Details

### 9.1 Why this fits the category
The experience is adaptive and AI-native. The questions come from the student's own work, the examiner adapts with a follow-up when an answer is weak, and the feedback is generated from what was actually said.

### 9.2 Design choice: evaluate after the call
Scoring happens after the call, not during it. This matches a real viva, keeps the live conversation fast, and lets the model judge the whole transcript at once. During the call the only live judgment is a quick check on whether an answer is vague.

### 9.3 How each request works, in sequence

**A. Upload and ingest** (REST: upload a document)
1. The browser uploads the PDF or Word file.
2. The backend checks the file type and size, extracts the text, and splits it into sections and chunks of a few hundred tokens with a small overlap.
3. Each chunk is embedded with the local embedding model.
4. Vectors are stored in Qdrant (tagged with the document ID), and chunk text is stored in PostgreSQL.
5. The document status becomes "ready" (the browser checks status while this runs in the background).

**B. Generate questions** (REST: create questions for a document)
1. The backend runs a handful of retrieval searches (objective, method, results, limitations, design choices) and takes the top chunk from each, giving a small set of representative passages.
2. gpt-oss-20b receives those passages and returns 2 to 4 questions as structured JSON: question text, topic, the key points a good answer should contain, and the source chunk IDs.
3. The questions are saved as "proposed" and returned to the browser.

**C. Review and create the session** (REST: update questions, create session)
1. The student accepts, edits, or removes questions.
2. The backend creates the session and generates the audio for each accepted question once with ElevenLabs.
3. The browser downloads and caches that audio, along with a few static clips (greeting, short fillers, repeat request, closing) that were generated ahead of time and cost no quota during a session.

**D. Start the call** (WebSocket opens)
1. The browser opens the WebSocket over wss and sends the session ID.
2. The server loads the questions, key points, and source passages into memory and sets the state to SPEAKING.
3. It tells the browser to play the greeting and question 1 from the cache.
4. When playback finishes, the browser reports it, and the state becomes LISTENING.

**E. One answer turn** (WebSocket)
1. The browser's voice activity detection hears speech start. After about 1.2 to 1.5 seconds of silence, it ends the segment.
2. The browser encodes the segment as WAV (Groq recommends WAV for lower latency) and sends it. At the same moment it plays a short filler clip, and the screen shows "Thinking".
3. The server sends the audio to Whisper (model whisper-large-v3-turbo, language set to English, a short vocabulary hint taken from the report, limited to 224 tokens). If the result looks like silence or noise, the server asks the student to repeat, without counting it as a follow-up.
4. The transcript is saved as a turn and sent to the browser for captions.
5. **If this answer was already a follow-up answer,** the server skips the decision step and goes straight to the next question.
6. Otherwise the server calls gpt-oss-120b with the question, the key points, the one or two source passages, and the answer, and receives JSON with a verdict:
   - **clear:** the server tells the browser to play the next question from the cache (or the closing clip after the last question).
   - **vague:** the model supplies one short follow-up sentence. The server sends it to ElevenLabs, relays the audio to the browser in chunks as it is generated, and marks the follow-up as used for this question.
   - **repeat request:** the server tells the browser to replay the cached question.
7. When playback finishes, the state returns to LISTENING.

**F. Interruption** (WebSocket)
1. While the examiner is speaking, the browser hears the student start talking (for longer than a few hundred milliseconds).
2. The browser stops playback immediately and sends a barge-in message.
3. The server cancels any follow-up audio still being generated, records the examiner turn as "interrupted", and switches to LISTENING.
4. The student's speech is then processed as in step E.

**G. End the call** (WebSocket and REST)
1. After the last question, or when the student ends the call, the server marks the session as ended. Every turn was already saved.
2. The server starts the evaluation as a background job, and the browser opens the report page, which shows progress.

**H. Evaluation** (background job)
1. For each question, qwen3.8-27b receives the question, the key points, the source passages, and the student's answer and follow-up answer, and returns JSON scores and feedback for each rubric item plus a model answer.
2. Requests are sent one question at a time, with a short wait if a rate limit is hit, because of the per-minute token limit.
3. A final call combines the per-question results into an overall summary: strengths, main gaps, and what to practice next.
4. Everything is saved, the session status becomes "report ready", and the browser shows the report.

**I. History** (REST)
1. The browser lists past sessions (date, document name, overall score).
2. Opening one loads the transcript, scores, and report from the database.
3. The student can delete a session or a document, which also removes its vectors from Qdrant.

### 9.4 Call state machine and messages

States: `IDLE → SPEAKING → LISTENING → THINKING → (SPEAKING or ENDED)`. A barge-in moves `SPEAKING → LISTENING`.

| Direction | Message | Purpose |
|-----------|---------|---------|
| Browser → server | `start` | Open the call for a session |
| Browser → server | `answer_audio` | A finished spoken answer (WAV) |
| Browser → server | `barge_in` | Student interrupted the examiner |
| Browser → server | `playback_finished` | Examiner audio finished playing |
| Browser → server | `end_call` | Student ended the call |
| Server → browser | `state` | Listening, thinking, speaking, ended |
| Server → browser | `play_cached` | Play a pre-generated question or clip |
| Server → browser | `tts_chunk` / `tts_end` | Streamed follow-up audio |
| Server → browser | `transcript` | Student's transcribed answer (for captions) |
| Server → browser | `error` | Failure, with a text-input fallback |

### 9.5 Data model (PostgreSQL)

* `documents`: id, user, filename, status, created time
* `chunks`: id, document, text, section, page (vectors live in Qdrant)
* `questions`: id, document, text, topic, key points, source chunks, accepted, order
* `sessions`: id, document, user, status, started and ended times
* `turns`: id, session, question, role, kind (question, answer, follow-up, follow-up answer), text, duration, interrupted
* `evaluations`: id, session, question, scores, feedback, model answer
* `readiness_reports`: session, overall score, summary

For the prototype, users are identified by a simple anonymous ID (no login).

### 9.6 Expected delay and quotas (estimates, to be measured)

* **Clear answer:** silence wait (about 1.2 to 1.5 s) + upload and transcription + one short model call; the next question plays from the cache. The filler clip covers the gap.
* **Vague answer:** the same, plus the time for the first chunk of follow-up audio. ElevenLabs lists about 75 ms model latency for Flash v2.5 and about 250 to 300 ms for Turbo v2.5, before network and application delays.
* We will log the time of each stage (speech end, transcript, decision, first audio) during testing and report the measured numbers, not these estimates.
* A 4-question session needs roughly 4 to 8 transcription requests, up to 4 decision calls, 1 question-generation call, and about 5 evaluation calls, which fits the listed free limits for a single user but not for many simultaneous testers.