"""Shared by the WebSocket (end_call / last question) and REST (/end)."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SessionLocal
from ..models import ReadinessReport, Session, now
from .evaluator import start_evaluation


async def finish_session(session_id: uuid.UUID) -> bool:
    """Idempotent. Returns True if this call started the evaluation."""
    async with SessionLocal() as db:
        sess = await db.get(Session, session_id)
        if sess is None:
            return False
        if sess.status in ("ended", "report_running", "report_ready"):
            return False
        sess.status, sess.ended_at = "ended", now()
        if sess.started_at is None:
            sess.started_at = sess.ended_at
        if await db.get(ReadinessReport, session_id) is None:
            db.add(ReadinessReport(session_id=session_id, status="pending"))
        await db.commit()
    start_evaluation(session_id)
    return True
