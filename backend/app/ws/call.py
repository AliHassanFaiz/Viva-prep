"""WebSocket endpoint and call orchestrator (SPEC sections 8 and 9): a plain asyncio state machine."""
import asyncio
import base64
import binascii
import json
import time
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, update

from ..config import settings
from ..db import SessionLocal
from ..logging_utils import log_stage, logger
from ..models import Chunk, Document, Session, SessionQuestion, Turn, now
from ..services import decision as decision_svc
from ..services import stt, tts
from ..services.finish import finish_session
from ..static_clips import STATIC_CLIPS

router = APIRouter()
ACTIVE: dict[str, "Call"] = {}
IDLE, SPEAKING, LISTENING, THINKING, ENDED = "IDLE", "SPEAKING", "LISTENING", "THINKING", "ENDED"
MAX_AUDIO_B64 = 14_000_000  # ~10 MB of audio


class Call:
    def __init__(self, ws: WebSocket, session_id: uuid.UUID):
        self.ws, self.session_id = ws, session_id
        self.questions: list[SessionQuestion] = []
        self.vocab_hint: str | None = None
        self.idx = 0
        self.followup_used = False
        self.state = IDLE
        self.ending = False  # closing line is being played; call ends when playback finishes
        self.current_turn_id: uuid.UUID | None = None
        self.tts_task: asyncio.Task | None = None
        self.nudge_task: asyncio.Task | None = None
        self.end_timer: asyncio.Task | None = None
        self.nudge_used = False
        self.seq = 0
        self.lock = asyncio.Lock()
        self.closed = False

    # ---------- helpers ----------
    async def send(self, **msg) -> None:
        if self.closed:
            return
        try:
            await self.ws.send_text(json.dumps(msg))
        except Exception:
            self.closed = True

    async def set_state(self, s: str) -> None:
        self.state = s
        await self.send(type="state", state=s.lower())

    async def save_turn(self, role: str, kind: str, text: str, sq_id: uuid.UUID | None, turn_id: uuid.UUID | None = None,
                        duration_ms: int | None = None, timings: dict | None = None) -> uuid.UUID:
        tid = turn_id or uuid.uuid4()
        self.seq += 1
        async with SessionLocal() as db:
            exists = turn_id is not None and await db.get(Turn, tid) is not None
            if exists:
                tid = uuid.uuid4()
            db.add(Turn(id=tid, session_id=self.session_id, session_question_id=sq_id, seq=self.seq, role=role,
                        kind=kind, text=text, duration_ms=duration_ms, timings=timings))
            await db.commit()
        return tid

    async def merge_timings(self, turn_id: uuid.UUID, **kw) -> None:
        try:
            async with SessionLocal() as db:
                t = await db.get(Turn, turn_id)
                if t is not None:
                    t.timings = {**(t.timings or {}), **kw}
                    await db.commit()
        except Exception:
            pass

    @property
    def q(self) -> SessionQuestion:
        return self.questions[self.idx]

    def cancel(self, task: asyncio.Task | None) -> None:
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()

    # ---------- loading / resume ----------
    async def load(self) -> bool:
        async with SessionLocal() as db:
            sess = await db.get(Session, self.session_id)
            if sess is None:
                return False
            self.questions = list((await db.execute(select(SessionQuestion).where(SessionQuestion.session_id == self.session_id)
                                                    .order_by(SessionQuestion.position))).scalars().all())
            doc = await db.get(Document, sess.document_id)
            self.vocab_hint = doc.vocab_hint if doc else None
            turns = (await db.execute(select(Turn).where(Turn.session_id == self.session_id).order_by(Turn.seq))).scalars().all()
            self.status = sess.status
        self.seq = max([t.seq for t in turns], default=0)
        self.fresh = not turns
        # rebuild idx / followup_used from the saved turns
        pos = {q.id: i for i, q in enumerate(self.questions)}
        for t in turns:
            if t.role == "examiner" and t.kind == "question" and t.session_question_id in pos:
                self.idx, self.followup_used = pos[t.session_question_id], False
                self.nudge_used = False
            elif t.role == "examiner" and t.kind == "followup":
                self.followup_used = True
            elif t.role == "examiner" and t.kind == "nudge":
                self.nudge_used = True
            elif t.kind == "closing":
                self.ending = True
        return bool(self.questions)

    # ---------- speaking ----------
    async def speak_cached(self, audio_ids: list[str], kind: str, text: str, sq: SessionQuestion | None = None,
                           save_text: str | None = None) -> None:
        self.cancel(self.tts_task)
        turn_id = await self.save_turn("examiner", kind, save_text or text, sq.id if sq else None)
        self.current_turn_id = turn_id
        await self.set_state(SPEAKING)
        await self.send(type="play_cached", turn_id=str(turn_id), audio_ids=audio_ids, text=text)
        if kind == "closing":
            self.ending = True
            # safety net: if the browser never reports playback_finished, still end the call
            self.cancel(self.end_timer)
            self.end_timer = asyncio.create_task(self._end_after(25))

    async def _end_after(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
        await self.finish_call()

    async def ask_current(self, with_greeting: bool = False) -> None:
        q = self.q
        ids = (["greeting"] if with_greeting else []) + [f"q:{q.id}"]
        if with_greeting:
            await self.save_turn("examiner", "greeting", STATIC_CLIPS["greeting"], None)
        text = (STATIC_CLIPS["greeting"] + " " if with_greeting else "") + q.text
        await self.speak_cached(ids, "question", text, q, save_text=q.text)

    async def advance(self) -> None:
        self.idx += 1
        self.followup_used = False
        self.nudge_used = False
        if self.idx >= len(self.questions):
            self.idx = len(self.questions) - 1
            await self.speak_cached(["closing"], "closing", STATIC_CLIPS["closing"])
        else:
            await self.ask_current()

    async def stream_followup(self, turn_id: uuid.UUID, text: str, student_turn_id: uuid.UUID | None) -> None:
        t0 = time.perf_counter()
        first = True
        try:
            await self.set_state(SPEAKING)
            seq = 0
            async for item in tts.stream_audio(text):
                if isinstance(item, tuple):
                    _, fmt, rate = item
                    await self.send(type="tts_start", turn_id=str(turn_id), sample_rate=rate, format=fmt)
                    continue
                if first:
                    first = False
                    ms = (time.perf_counter() - t0) * 1000
                    log_stage(self.session_id, turn_id, "tts_first_chunk", ms)
                    if student_turn_id:
                        asyncio.create_task(self.merge_timings(student_turn_id, tts_first_chunk_ms=round(ms)))
                await self.send(type="tts_chunk", turn_id=str(turn_id), seq=seq, data=base64.b64encode(item).decode())
                seq += 1
            await self.send(type="tts_end", turn_id=str(turn_id))
        except asyncio.CancelledError:
            raise  # barge-in or new answer: the HTTP stream is closed by the cancellation
        except Exception as e:
            logger.error('{"stage":"followup_tts_failed","error":"%s"}', type(e).__name__)
            await self.send(type="error", code="tts_failed", message="Voice is unavailable; using your browser voice.",
                            fallback="browser_voice", turn_id=str(turn_id), text=text)

    # ---------- timers ----------
    def start_nudge_timer(self) -> None:
        self.cancel(self.nudge_task)
        if self.nudge_used or self.ending:
            return
        self.nudge_task = asyncio.create_task(self._nudge())

    async def _nudge(self) -> None:
        try:
            await asyncio.sleep(settings.NUDGE_AFTER_MS / 1000)
            if self.state == LISTENING and not self.nudge_used and not self.ending and not self.lock.locked():
                self.nudge_used = True
                await self.speak_cached(["nudge"], "nudge", STATIC_CLIPS["nudge"], self.q)
        except asyncio.CancelledError:
            pass

    # ---------- message handlers ----------
    async def on_start(self) -> None:
        await self.send(type="ready", question_count=len(self.questions), current_index=self.idx)
        if self.status in ("ended", "report_running", "report_ready", "report_failed"):
            await self.set_state(ENDED)
            return
        if self.fresh:
            async with SessionLocal() as db:
                await db.execute(update(Session).where(Session.id == self.session_id)
                                 .values(status="in_progress", started_at=now()))
                await db.commit()
            await self.ask_current(with_greeting=True)
        elif self.ending:
            await self.finish_call()  # reconnected after the closing line
        else:
            await self.ask_current()  # resume: replay the current question

    async def on_playback_finished(self, turn_id: str) -> None:
        if not self.current_turn_id or turn_id != str(self.current_turn_id):
            return  # stale
        if self.ending:
            await self.finish_call()
            return
        if self.state in (SPEAKING, LISTENING):
            await self.set_state(LISTENING)
            self.start_nudge_timer()

    async def on_barge_in(self, turn_id: str) -> None:
        if not self.current_turn_id or turn_id != str(self.current_turn_id):
            return
        self.cancel(self.tts_task)
        self.cancel(self.nudge_task)
        try:
            async with SessionLocal() as db:
                await db.execute(update(Turn).where(Turn.id == self.current_turn_id).values(interrupted=True))
                await db.commit()
        except Exception:
            pass
        if not self.ending:
            await self.set_state(LISTENING)

    async def on_answer(self, msg: dict) -> None:
        async with self.lock:
            if self.ending or self.state == ENDED:
                return
            self.cancel(self.nudge_task)
            self.cancel(self.tts_task)
            await self.set_state(THINKING)
            raw_id = msg.get("turn_id")
            try:
                client_turn_id = uuid.UUID(str(raw_id))
            except ValueError:
                client_turn_id = uuid.uuid4()
            timings: dict = {}
            duration_ms: int | None = None
            probs: list[float] = []
            if msg.get("type") == "answer_audio":
                try:
                    b64 = msg.get("data") or ""
                    if len(b64) > MAX_AUDIO_B64:
                        raise ValueError("too large")
                    wav = base64.b64decode(b64, validate=False)
                    duration_ms = int(msg.get("duration_ms") or 0)
                    if msg.get("client_silence_to_send_ms") is not None:
                        timings["client_silence_to_send_ms"] = int(msg["client_silence_to_send_ms"])
                    tr = await stt.transcribe(wav, self.vocab_hint, str(self.session_id), str(client_turn_id))
                    text, probs = tr.text, tr.no_speech_probs
                    timings["stt_ms"] = round(tr.ms)
                except (stt.STTError, ValueError, binascii.Error):
                    await self.send(type="error", code="stt_failed", message="We couldn't transcribe that. Please type your answer.",
                                    fallback="text_input")
                    await self.set_state(LISTENING)
                    return
            else:
                text = str(msg.get("text") or "").strip()[:4000]

            if stt.is_silence(text, probs, duration_ms):
                await self.speak_cached(["repeat_prompt"], "nudge", STATIC_CLIPS["repeat_prompt"], self.q)
                return  # does not count as a follow-up

            kind = "followup_answer" if self.followup_used else "answer"
            student_turn = await self.save_turn("student", kind, text, self.q.id, client_turn_id, duration_ms, timings or None)
            await self.send(type="transcript", turn_id=str(student_turn), text=text)

            if self.followup_used:  # server-side guard: never judge a follow-up answer
                await self.advance()
                return

            passages = await self._passages(self.q)
            t0 = time.perf_counter()
            verdict = await decision_svc.decide(self.q.text, list(self.q.key_points or []), passages, text,
                                                str(self.session_id), str(student_turn))
            asyncio.create_task(self.merge_timings(student_turn, decision_ms=round((time.perf_counter() - t0) * 1000)))

            if verdict.verdict == "clear":
                await self.advance()
            elif verdict.verdict == "repeat_request":
                await self.speak_cached([f"q:{self.q.id}"], "question", self.q.text, self.q)
            else:  # vague -> exactly one follow-up
                self.followup_used = True
                follow = verdict.followup or decision_svc.DEFAULT_FOLLOWUP
                turn_id = await self.save_turn("examiner", "followup", follow, self.q.id)
                self.current_turn_id = turn_id
                await self.send(type="examiner_text", turn_id=str(turn_id), kind="followup", text=follow)
                self.tts_task = asyncio.create_task(self.stream_followup(turn_id, follow, student_turn))

    async def _passages(self, q: SessionQuestion) -> list[str]:
        try:
            ids = [uuid.UUID(x) for x in (q.source_chunk_ids or [])][:2]
            if not ids:
                return []
            async with SessionLocal() as db:
                rows = (await db.execute(select(Chunk.text).where(Chunk.id.in_(ids)))).scalars().all()
            return list(rows)
        except Exception:
            return []

    async def finish_call(self) -> None:
        if self.state == ENDED:
            return
        self.cancel(self.tts_task)
        self.cancel(self.nudge_task)
        if self.end_timer is not asyncio.current_task():
            self.cancel(self.end_timer)
        await finish_session(self.session_id)
        await self.set_state(ENDED)

    def shutdown(self) -> None:
        self.closed = True
        for t in (self.tts_task, self.nudge_task, self.end_timer):
            self.cancel(t)


@router.websocket("/ws/call/{session_id}")
async def call_ws(ws: WebSocket, session_id: str, user_id: str = Query(default="")):
    origin = (ws.headers.get("origin") or "").rstrip("/")
    if origin and settings.origins and origin not in settings.origins and "*" not in settings.origins:
        await ws.close(code=4403)
        return
    try:
        sid, uid = uuid.UUID(session_id), uuid.UUID(user_id)
    except ValueError:
        await ws.close(code=4404)
        return
    async with SessionLocal() as db:
        sess = await db.get(Session, sid)
        if sess is None or sess.user_id != uid:  # same answer for "missing" and "not yours"
            await ws.close(code=4404)
            return
    await ws.accept()

    old = ACTIVE.get(session_id)
    if old:
        old.shutdown()
    call = Call(ws, sid)
    ACTIVE[session_id] = call
    tasks: set[asyncio.Task] = set()

    def spawn(coro) -> None:
        t = asyncio.create_task(coro)
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    async def guarded(coro) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error('{"stage":"ws_handler_error","error":"%s"}', type(e).__name__)
            await call.send(type="error", code="internal", message="Something went wrong. Please try again.", fallback="text_input")
            if call.state == THINKING:
                await call.set_state(LISTENING)

    try:
        if not await call.load():
            await call.send(type="error", code="no_questions", message="This session has no questions.", fallback="none")
            await ws.close()
            return
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                mtype = msg.get("type")
            except (json.JSONDecodeError, AttributeError):
                continue
            if mtype == "ping":
                await call.send(type="pong")
            elif mtype == "start":
                spawn(guarded(call.on_start()))
            elif mtype == "playback_finished":
                spawn(guarded(call.on_playback_finished(str(msg.get("turn_id")))))
            elif mtype == "barge_in":
                spawn(guarded(call.on_barge_in(str(msg.get("turn_id")))))
            elif mtype == "speech_start":  # optional extra: the student is talking, so don't nudge
                call.cancel(call.nudge_task)
            elif mtype in ("answer_audio", "answer_text"):
                spawn(guarded(call.on_answer(msg)))
            elif mtype == "end_call":
                spawn(guarded(call.finish_call()))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error('{"stage":"ws_error","error":"%s"}', type(e).__name__)
    finally:
        was_ending = call.ending and call.state != ENDED
        call.shutdown()
        if ACTIVE.get(session_id) is call:
            ACTIVE.pop(session_id, None)
        if was_ending:  # closing line was spoken; don't leave the session without a report
            await finish_session(sid)
        # in-flight answer handlers are left to finish on their own so no saved turn is lost
