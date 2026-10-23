"""Question generation (SPEC 7 + 10.1)."""
import asyncio
import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..logging_utils import logger
from ..models import Chunk
from ..schemas import GeneratedQuestions
from . import qdrant_store
from .embeddings import embed_queries
from .groq_client import LLMError, chat_json
from .modes import get_mode, norm_mode
from .prompts import esc, fill, load

SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "minItems": 2, "maxItems": 4, "items": {
        "type": "object",
        "properties": {
            "question": {"type": "string"}, "topic": {"type": "string"},
            "difficulty": {"type": "string", "enum": ["basic", "medium", "hard"]},
            "key_points": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
            "source_chunk_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 2}},
        "required": ["question", "topic", "difficulty", "key_points", "source_chunk_ids"],
        "additionalProperties": False}}},
    "required": ["questions"], "additionalProperties": False,
}


_PROBE_VECS: dict[str, list[list[float]]] = {}  # probes are constants per mode: embed once per process


async def _probe_vectors(mode: str) -> list[list[float]]:
    if mode not in _PROBE_VECS:
        _PROBE_VECS[mode] = await embed_queries(list(get_mode(mode)["probes"]))
    return _PROBE_VECS[mode]


async def gather_passages(db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID, mode: str = "viva") -> list[Chunk]:
    vecs = await _probe_vectors(mode)
    await qdrant_store.ensure_collection()  # once, before the parallel searches
    results = await asyncio.gather(*(qdrant_store.search(str(user_id), str(document_id), v, limit=1) for v in vecs))
    ids: list[str] = []
    for found in results:  # keep probe order
        for cid in found:
            if cid not in ids:
                ids.append(cid)
    chunks: list[Chunk] = []
    if ids:
        rows = (await db.execute(select(Chunk).where(Chunk.document_id == document_id, Chunk.id.in_([uuid.UUID(i) for i in ids])))).scalars().all()
        by_id = {str(c.id): c for c in rows}
        chunks = [by_id[i] for i in ids if i in by_id]
    if len(chunks) < 2:  # vector store empty or tiny doc: fall back to the first chunks in order
        rows = (await db.execute(select(Chunk).where(Chunk.document_id == document_id)
                                 .order_by(Chunk.position).limit(5))).scalars().all()
        seen = {str(c.id) for c in chunks}
        chunks += [c for c in rows if str(c.id) not in seen]
    return chunks[:5]


async def generate(db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID, n: int, mode: str = "viva") -> list[dict]:
    mode = norm_mode(mode)
    n = max(settings.QUESTIONS_MIN, min(settings.QUESTIONS_MAX, n))
    chunks = await gather_passages(db, user_id, document_id, mode)
    if not chunks:
        raise LLMError("No passages available.")
    valid_ids = {str(c.id) for c in chunks}
    passages = "\n".join(f'<passage id="{c.id}">\n{esc(c.text[:1200])}\n</passage>' for c in chunks)
    prompt = fill(load(f"question_gen_{mode}"), n=str(n), passages=passages, examiner=get_mode(mode)["examiner"])

    last: Exception | None = None
    for _ in range(2):  # one retry (SPEC)
        try:
            raw = await chat_json(
                model=settings.MODEL_QUESTIONS, user=prompt, schema=SCHEMA, schema_name="viva_questions", strict=True,
                temperature=0.4, max_tokens=1200, reasoning_effort="low", stage="question_gen", timeout=max(settings.LLM_TIMEOUT_S, 30))
            parsed = GeneratedQuestions.model_validate(raw)
            items = parsed.questions[:n]
            if len(items) < settings.QUESTIONS_MIN:
                raise ValueError("too few questions")
            out = []
            for q in items:
                src = [s for s in q.source_chunk_ids if s in valid_ids] or [str(chunks[0].id)]
                out.append({"text": q.question, "topic": q.topic, "difficulty": q.difficulty,
                            "key_points": [k.strip() for k in q.key_points if k.strip()][:4], "source_chunk_ids": src[:2]})
            return out
        except (LLMError, ValidationError, ValueError) as e:
            last = e
            logger.warning('{"stage":"question_gen_attempt_failed","error":"%s","detail":"%s"}', type(e).__name__,
                           str(e)[:200].replace('"', "'").replace("\n", " "))
    raise LLMError(f"Question generation failed: {type(last).__name__}")
