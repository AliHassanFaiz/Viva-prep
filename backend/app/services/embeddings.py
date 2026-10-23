"""fastembed wrapper (bge-small-en-v1.5, 384 dims). The model is loaded lazily and runs in a worker thread."""
import asyncio
import threading

from ..config import settings

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name=settings.EMBED_MODEL)
        return _model


def _embed_sync(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return [v.tolist() for v in model.embed(texts, batch_size=32)]


async def embed_passages(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), 32):
        out.extend(await asyncio.to_thread(_embed_sync, texts[i:i + 32]))
    return out


async def embed_queries(texts: list[str]) -> list[list[float]]:
    """Embed several search queries in ONE worker-thread call."""
    prefix = QUERY_PREFIX if "bge" in settings.EMBED_MODEL.lower() else ""
    return await asyncio.to_thread(_embed_sync, [prefix + t for t in texts])


async def warmup() -> None:
    """Load the model at startup so the first upload does not pay the load time. Never raises."""
    try:
        await asyncio.to_thread(_embed_sync, ["warm up"])
    except Exception:  # noqa: BLE001 - warm-up is best effort
        pass


async def embed_query(text: str) -> list[float]:
    prefix = QUERY_PREFIX if "bge" in settings.EMBED_MODEL.lower() else ""
    return (await asyncio.to_thread(_embed_sync, [prefix + text]))[0]
