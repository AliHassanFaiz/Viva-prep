"""Qdrant: one collection, cosine, 384 dims. Every search and delete is filtered by BOTH user_id and document_id,
so one user can never retrieve another user's points even if a document id leaks."""
import asyncio

from qdrant_client import AsyncQdrantClient, models

from ..config import settings

_client: AsyncQdrantClient | None = None
_ready = False
_init_lock = asyncio.Lock()


def client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        if settings.QDRANT_URL:
            _client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None, timeout=30)
        else:
            _client = AsyncQdrantClient(location=":memory:")  # dev only
    return _client


async def ensure_collection() -> None:
    global _ready
    if _ready:
        return
    async with _init_lock:
        if _ready:
            return
        c = client()
        name = settings.QDRANT_COLLECTION
        if not await c.collection_exists(name):
            await c.create_collection(
                name, vectors_config=models.VectorParams(size=settings.EMBED_DIM, distance=models.Distance.COSINE))
        for field, schema in (
            ("user_id", models.KeywordIndexParams(type=models.KeywordIndexType.KEYWORD, is_tenant=True)),  # tenant key
            ("document_id", models.PayloadSchemaType.KEYWORD),
        ):
            try:
                await c.create_payload_index(name, field_name=field, field_schema=schema)
            except Exception:
                pass  # already exists (or in-memory mode where indexes are no-ops)
        _ready = True


async def upsert_chunks(user_id: str, document_id: str, items: list[dict], vectors: list[list[float]]) -> None:
    """items: [{chunk_id, position, section, page}]"""
    await ensure_collection()
    points = [
        models.PointStruct(
            id=it["chunk_id"], vector=vec,
            payload={"user_id": user_id, "document_id": document_id, "chunk_id": it["chunk_id"], "position": it["position"],
                     "section": it.get("section"), "page": it.get("page")})
        for it, vec in zip(items, vectors)
    ]
    for i in range(0, len(points), 64):
        await client().upsert(settings.QDRANT_COLLECTION, points=points[i:i + 64], wait=True)


def _scope(user_id: str, document_id: str) -> models.Filter:
    if not user_id or not document_id:  # never fall back to an unscoped query
        raise ValueError("user_id and document_id are required")
    return models.Filter(must=[
        models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
        models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)),
    ])


async def search(user_id: str, document_id: str, vector: list[float], limit: int = 1) -> list[str]:
    """Returns chunk ids, best first."""
    await ensure_collection()
    res = await client().query_points(
        settings.QDRANT_COLLECTION, query=vector, query_filter=_scope(user_id, document_id), limit=limit, with_payload=True)
    return [p.payload["chunk_id"] for p in res.points if p.payload and "chunk_id" in p.payload]


async def delete_document(user_id: str, document_id: str) -> None:
    try:
        await ensure_collection()
        await client().delete(
            settings.QDRANT_COLLECTION, points_selector=models.FilterSelector(filter=_scope(user_id, document_id)), wait=True)
    except Exception as e:  # never block a user's delete request on the vector store
        from ..logging_utils import logger
        logger.error('{"stage":"qdrant_delete_failed","error":"%s"}', type(e).__name__)
