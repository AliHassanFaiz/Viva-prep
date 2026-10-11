import json
import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("viva")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)


def log_stage(session_id, turn_id, stage: str, ms: float | None = None, **extra) -> None:
    """One JSON line per call stage. Never pass transcripts or report text here."""
    rec = {"session_id": str(session_id) if session_id else None, "turn_id": str(turn_id) if turn_id else None,
           "stage": stage, "ms": None if ms is None else round(ms)}
    rec.update(extra)
    logger.info(json.dumps(rec))


@contextmanager
def timed():
    box = {"ms": 0.0}
    t0 = time.perf_counter()
    try:
        yield box
    finally:
        box["ms"] = (time.perf_counter() - t0) * 1000
