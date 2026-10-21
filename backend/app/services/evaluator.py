"""Post-call evaluation (SPEC 10.3). Sequential, one call per question, then one summary call. Scores computed in code."""
import asyncio
import re
import uuid
from statistics import mean

from pydantic import ValidationError
from sqlalchemy import delete, select

from ..config import settings
from ..db import SessionLocal
from ..logging_utils import log_stage, logger
from ..models import Chunk, Document, Evaluation, ReadinessReport, Session, SessionQuestion, Turn, now
from ..schemas import QuestionEval, SummaryOut
from .groq_client import LLMError, chat_json
from .modes import get_mode
from .prompts import esc, fill, load

_tasks: set[asyncio.Task] = set()

EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {"type": "object", "properties": {k: {"type": "integer", "minimum": 0, "maximum": 5}
                   for k in ("accuracy", "completeness", "clarity", "justification")},
                   "required": ["accuracy", "completeness", "clarity", "justification"]},
        "covered_points": {"type": "array", "items": {"type": "string"}},
        "missed_points": {"type": "array", "items": {"type": "string"}},
        "incorrect_claims": {"type": "array", "items": {"type": "string"}},
        "feedback": {"type": "string"}, "model_answer": {"type": "string"}},
    "required": ["scores", "covered_points", "missed_points", "incorrect_claims", "feedback", "model_answer"],
}
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"strengths": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                   "gaps": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                   "practice_next": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                   "overall_comment": {"type": "string"}},
    "required": ["strengths", "gaps", "practice_next", "overall_comment"],
}


def question_score(s: dict) -> int:
    return round(mean([s["accuracy"], s["completeness"], s["clarity"], s["justification"]]) * 20)


def band_for(score: int) -> str:
    return "needs_work" if score < 50 else "developing" if score < 75 else "ready"


def start_evaluation(session_id: uuid.UUID) -> None:
    t = asyncio.create_task(run_evaluation(session_id))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def _truncate_words(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


async def _llm_report(prompt: str, schema: dict, name: str, stage: str, sid) -> dict:
    last: Exception | None = None
    for _ in range(2):  # one retry
        try:
            return await chat_json(
                model=settings.MODEL_REPORT, user=prompt, schema=schema, schema_name=name, strict=False,
                temperature=0.2, max_tokens=700, reasoning_effort="none", stage=stage, session_id=sid,
                timeout=max(settings.LLM_TIMEOUT_S, 40), use_budget=True)
        except LLMError as e:
            last = e
    raise LLMError(str(last))


async def run_evaluation(session_id: uuid.UUID) -> None:
    try:
        async with SessionLocal() as db:
            sess = await db.get(Session, session_id)
            if sess is None:
                return
            doc = await db.get(Document, sess.document_id)
            m = get_mode(doc.mode if doc else None)
            report = await db.get(ReadinessReport, session_id)
            if report is None:
                report = ReadinessReport(session_id=session_id)
                db.add(report)
            report.status, report.error = "running", None
            sess.status = "report_running"
            await db.execute(delete(Evaluation).where(Evaluation.session_id == session_id))
            await db.commit()
            questions = (await db.execute(select(SessionQuestion).where(SessionQuestion.session_id == session_id)
                                          .order_by(SessionQuestion.position))).scalars().all()
            turns = (await db.execute(select(Turn).where(Turn.session_id == session_id).order_by(Turn.seq))).scalars().all()

        by_q: dict[uuid.UUID, dict[str, str]] = {}
        for t in turns:
            if t.session_question_id and t.kind in ("answer", "followup", "followup_answer"):
                by_q.setdefault(t.session_question_id, {})
                d = by_q[t.session_question_id]
                d[t.kind] = (d[t.kind] + " " + t.text) if t.kind in d else t.text

        answered_scores: list[int] = []
        summary_rows: list[str] = []
        for q in questions:
            d = by_q.get(q.id, {})
            answer = d.get("answer", "").strip()
            ev = Evaluation(session_id=session_id, session_question_id=q.id)
            if not answer:
                ev.status, ev.scores, ev.question_score = "ok", dict(accuracy=0, completeness=0, clarity=0, justification=0), 0
                ev.covered_points, ev.missed_points, ev.incorrect_claims = [], list(q.key_points or []), []
                ev.feedback, ev.model_answer = "No answer recorded.", ""
            else:
                try:
                    async with SessionLocal() as db:
                        ids = [uuid.UUID(x) for x in (q.source_chunk_ids or [])][:2]
                        chunks = (await db.execute(select(Chunk).where(Chunk.id.in_(ids)))).scalars().all() if ids else []
                    passages = "\n".join(f"<passage>{esc(c.text[:1000])}</passage>" for c in chunks) or "<passage></passage>"
                    prompt = fill(load("evaluate_question"), question=q.text, key_points="; ".join(q.key_points or []),
                                  passages=passages, answer=esc(d["answer"][:1500]),
                                  followup=esc(d.get("followup", "none")),
                                  followup_answer=esc(d.get("followup_answer", "none")[:1500]),
                                  person=m["person"], session=m["session"], source=m["source"], **m["rubric"])
                    parsed = None
                    for _ in range(2):  # validate, retry once on bad output
                        raw = await _llm_report(prompt, EVAL_SCHEMA, "viva_eval", "evaluate", session_id)
                        try:
                            parsed = QuestionEval.model_validate(raw)
                            break
                        except ValidationError:
                            continue
                    if parsed is None:
                        raise LLMError("invalid evaluation output")
                    s = parsed.scores.model_dump()
                    ev.status, ev.scores, ev.question_score = "ok", s, question_score(s)
                    ev.covered_points, ev.missed_points = parsed.covered_points, parsed.missed_points
                    ev.incorrect_claims = parsed.incorrect_claims
                    ev.feedback, ev.model_answer = _truncate_words(parsed.feedback, 500), _truncate_words(parsed.model_answer, 700)
                    answered_scores.append(ev.question_score)
                    summary_rows.append(f"Q: {q.text}\nScores: {s}\nFeedback: {ev.feedback}")
                except Exception as e:
                    logger.error('{"stage":"evaluate_failed","session_id":"%s","error":"%s"}', session_id, type(e).__name__)
                    ev.status = "failed"
            async with SessionLocal() as db:
                db.add(ev)
                await db.commit()  # committed per question so the report page can show progress

        # ---- summary + overall ----
        if answered_scores:
            overall = round(mean(answered_scores))
            summary = SummaryOut()
            try:
                prompt = fill(load("summarize"), results=esc("\n\n".join(summary_rows)), person=m["person"], session=m["session"])
                summary = SummaryOut.model_validate(await _llm_report(prompt, SUMMARY_SCHEMA, "viva_summary", "summarize", session_id))
            except Exception as e:
                logger.error('{"stage":"summary_failed","error":"%s"}', type(e).__name__)
                summary = SummaryOut(overall_comment="Your answers were scored individually below. A written summary could not be generated.")
        else:
            overall = 0
            summary = SummaryOut(gaps=["No answers were recorded in this session."],
                                 practice_next=["Run another session and answer each question out loud."],
                                 overall_comment="We did not hear any answers, so there is nothing to score yet.")

        words = sum(len(t.text.split()) for t in turns if t.role == "student" and t.kind in ("answer", "followup_answer") and t.duration_ms)
        ms = sum(t.duration_ms or 0 for t in turns if t.role == "student" and t.kind in ("answer", "followup_answer"))
        wpm = round(words / (ms / 60000)) if ms >= 3000 else None

        async with SessionLocal() as db:
            report = await db.get(ReadinessReport, session_id)
            sess = await db.get(Session, session_id)
            if report is None or sess is None:
                return
            report.status, report.overall_score, report.band = "ready", overall, band_for(overall)
            report.summary, report.avg_wpm, report.updated_at = summary.model_dump(), wpm, now()
            sess.status = "report_ready"
            await db.commit()
    except Exception as e:
        logger.error('{"stage":"evaluation_crashed","session_id":"%s","error":"%s"}', session_id, type(e).__name__)
        try:
            async with SessionLocal() as db:
                report = await db.get(ReadinessReport, session_id)
                sess = await db.get(Session, session_id)
                if report:
                    report.status, report.error = "failed", "Could not generate the report."
                if sess:
                    sess.status = "report_failed"
                await db.commit()
        except Exception:
            pass
