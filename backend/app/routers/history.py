"""Averages of the measured stage timings (SPEC section 15) for the pitch."""
import uuid
from statistics import mean

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_user_id
from ..models import Turn, Session

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/metrics")
async def metrics(user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Turn.timings).join(Session, Session.id == Turn.session_id)
                             .where(Session.user_id == user_id, Turn.role == "student"))).scalars().all()
    out: dict[str, dict] = {}
    for key in ("stt_ms", "decision_ms", "tts_first_chunk_ms", "client_silence_to_send_ms"):
        vals = [t[key] for t in rows if t and isinstance(t.get(key), (int, float))]
        out[key] = {"avg": round(mean(vals)) if vals else None, "n": len(vals)}
    return out
