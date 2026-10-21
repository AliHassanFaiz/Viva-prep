import asyncio
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_db
from ..deps import get_user_id, parse_uuid
from ..errors import APIError
from ..logging_utils import logger
from ..models import Document, Evaluation, Question, ReadinessReport, Session, SessionQuestion, Turn
from ..schemas import SessionCreate
from ..services import audio_store, tts
from ..services.finish import finish_session
from ..static_clips import STATIC_AUDIO_NAMES

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def get_owned_session(db: AsyncSession, sid: str, user_id: uuid.UUID) -> Session:
    s = await db.get(Session, parse_uuid(sid, "Session"))
    if s is None or s.user_id != user_id:
        raise APIError(404, "not_found", "Session not found.")
    return s


async def _gen_audio(sq: SessionQuestion) -> bool:
    try:
        audio_store.save(str(sq.id), await tts.synth_mp3(sq.text))
        return True
    except Exception as e:
        logger.error('{"stage":"question_tts_failed","error":"%s"}', type(e).__name__)
        return False


def _q_payload(session_id, sq: SessionQuestion, has_audio: bool) -> dict:
    return {"session_question_id": str(sq.id), "position": sq.position, "text": sq.text,
            "audio_url": f"/api/sessions/{session_id}/audio/{sq.id}" if has_audio else None}


@router.post("", status_code=201)
async def create_session(body: SessionCreate, user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, parse_uuid(body.document_id, "Document"))
    if doc is None or doc.user_id != user_id:
        raise APIError(404, "not_found", "Document not found.")
    if doc.status != "ready":
        raise APIError(409, "not_ready", "The document is not ready.")
    qids = [parse_uuid(q, "Question") for q in body.question_ids]
    rows = (await db.execute(select(Question).where(Question.id.in_(qids), Question.document_id == doc.id))).scalars().all()
    by_id = {q.id: q for q in rows}
    chosen = [by_id[i] for i in qids if i in by_id]
    if not (settings.QUESTIONS_MIN <= len(chosen) <= settings.QUESTIONS_MAX) or len(chosen) != len(set(qids)):
        raise APIError(400, "bad_questions", f"Choose {settings.QUESTIONS_MIN} to {settings.QUESTIONS_MAX} of this document's questions.")
    chosen.sort(key=lambda q: q.position)

    sess = Session(user_id=user_id, document_id=doc.id, status="ready", audio_ready=False)
    db.add(sess)
    await db.flush()
    sqs = [SessionQuestion(session_id=sess.id, position=i, text=q.text, topic=q.topic,
                           key_points=list(q.key_points or []), source_chunk_ids=list(q.source_chunk_ids or []))
           for i, q in enumerate(chosen)]
    db.add_all(sqs)
    await db.flush()
    results = await asyncio.gather(*[_gen_audio(sq) for sq in sqs])
    sess.audio_ready = all(results)
    await db.commit()
    return {"session_id": str(sess.id), "audio_ready": sess.audio_ready, "mode": doc.mode,
            "questions": [_q_payload(sess.id, sq, ok) for sq, ok in zip(sqs, results)],
            "static_audio": STATIC_AUDIO_NAMES}


@router.get("/{sid}/audio/{sqid}")
async def question_audio(sid: str, sqid: str, user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    s = await get_owned_session(db, sid, user_id)
    sq_id = parse_uuid(sqid, "Audio")
    sq = await db.get(SessionQuestion, sq_id)
    if sq is None or sq.session_id != s.id:
        raise APIError(404, "not_found", "Audio not found.")
    data = audio_store.get(str(sq_id))
    if data is None:
        raise APIError(404, "not_found", "Audio not available.")
    return Response(content=data, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/{sid}/end", status_code=202)
async def end_session(sid: str, user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    s = await get_owned_session(db, sid, user_id)
    await finish_session(s.id)
    await db.refresh(s)
    return {"status": s.status if s.status != "ended" else "report_running"}


@router.get("/{sid}/report")
async def get_report(sid: str, user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    s = await get_owned_session(db, sid, user_id)
    rep = await db.get(ReadinessReport, s.id)
    sqs = (await db.execute(select(SessionQuestion).where(SessionQuestion.session_id == s.id)
                            .order_by(SessionQuestion.position))).scalars().all()
    evs = {e.session_question_id: e for e in (await db.execute(
        select(Evaluation).where(Evaluation.session_id == s.id))).scalars().all()}
    turns = (await db.execute(select(Turn).where(Turn.session_id == s.id).order_by(Turn.seq))).scalars().all()
    tx: dict[uuid.UUID, dict] = {}
    for t in turns:
        if t.session_question_id and t.kind in ("answer", "followup", "followup_answer"):
            d = tx.setdefault(t.session_question_id, {"answer": "", "followup": None, "followup_answer": None})
            d[t.kind] = ((d[t.kind] + " ") if d[t.kind] else "") + t.text
    status = rep.status if rep else "pending"
    out_q = []
    for sq in sqs:
        e = evs.get(sq.id)
        t = tx.get(sq.id, {"answer": "", "followup": None, "followup_answer": None})
        item = {"session_question_id": str(sq.id), "position": sq.position, "question": sq.text, "topic": sq.topic,
                "status": e.status if e else None, "question_score": e.question_score if e else None,
                "scores": e.scores if e else None, "covered_points": (e.covered_points if e else []) or [],
                "missed_points": (e.missed_points if e else []) or [], "incorrect_claims": (e.incorrect_claims if e else []) or [],
                "feedback": ("Could not score this question." if e and e.status == "failed" else (e.feedback if e else None)),
                "model_answer": e.model_answer if e else None, "transcript": t}
        out_q.append(item)
    return {"status": status, "progress": {"done": len(evs), "total": len(sqs)},
            "overall_score": rep.overall_score if rep else None, "band": rep.band if rep else None,
            "avg_wpm": rep.avg_wpm if rep else None, "summary": rep.summary if rep else None,
            "error": rep.error if rep else None, "questions": out_q}


@router.get("")
async def list_sessions(user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Session, Document.filename, ReadinessReport.overall_score, ReadinessReport.band)
        .join(Document, Document.id == Session.document_id)
        .outerjoin(ReadinessReport, ReadinessReport.session_id == Session.id)
        .where(Session.user_id == user_id).order_by(Session.created_at.desc()))).all()
    return [{"id": str(s.id), "created_at": s.created_at.isoformat(), "document_name": fn, "status": s.status,
             "overall_score": sc, "band": b} for s, fn, sc, b in rows]


@router.get("/{sid}")
async def get_session(sid: str, user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    s = await get_owned_session(db, sid, user_id)
    doc = await db.get(Document, s.document_id)
    sqs = (await db.execute(select(SessionQuestion).where(SessionQuestion.session_id == s.id)
                            .order_by(SessionQuestion.position))).scalars().all()
    turns = (await db.execute(select(Turn).where(Turn.session_id == s.id).order_by(Turn.seq))).scalars().all()
    evs = (await db.execute(select(Evaluation).where(Evaluation.session_id == s.id))).scalars().all()
    return {
        "id": str(s.id), "status": s.status, "document_name": doc.filename if doc else "", "mode": doc.mode if doc else "viva",
        "created_at": s.created_at.isoformat(), "audio_ready": s.audio_ready, "static_audio": STATIC_AUDIO_NAMES,
        "questions": [_q_payload(s.id, sq, audio_store.get(str(sq.id)) is not None) for sq in sqs],
        "turns": [{"id": str(t.id), "seq": t.seq, "role": t.role, "kind": t.kind, "text": t.text,
                   "duration_ms": t.duration_ms, "interrupted": t.interrupted, "timings": t.timings,
                   "session_question_id": str(t.session_question_id) if t.session_question_id else None} for t in turns],
        "evaluations": [{"session_question_id": str(e.session_question_id), "status": e.status, "scores": e.scores,
                         "question_score": e.question_score, "feedback": e.feedback} for e in evs],
    }


@router.delete("/{sid}", status_code=204)
async def delete_session(sid: str, user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    s = await get_owned_session(db, sid, user_id)
    for i in (await db.execute(select(SessionQuestion.id).where(SessionQuestion.session_id == s.id))).scalars().all():
        audio_store.delete(str(i))
    await db.delete(s)
    await db.commit()
    return Response(status_code=204)
