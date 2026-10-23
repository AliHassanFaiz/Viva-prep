"""Runs once in the background at startup, so the first upload does not pay one-time costs:
loading the embedding model, creating the Qdrant collection and indexes (several round trips to Qdrant Cloud),
and embedding the fixed search phrases used to pick passages for questions. Every step is best effort."""
import asyncio

from ..logging_utils import log_stage
from . import embeddings, qdrant_store, question_gen
from .modes import MODES


async def run() -> None:
    t0 = asyncio.get_running_loop().time()
    await embeddings.warmup()
    for name, step in (("qdrant", qdrant_store.ensure_collection), *[(f"probes_{m}", _probes(m)) for m in MODES]):
        try:
            await step()
        except Exception:  # noqa: BLE001 - a failed warm-up must never stop the app
            log_stage(None, None, "warmup_step_failed", None, step=name)
    log_stage(None, None, "warmup_done", (asyncio.get_running_loop().time() - t0) * 1000)


def _probes(mode: str):
    async def go():
        await question_gen._probe_vectors(mode)
    return go
