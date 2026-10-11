"""ViVa Prep diagnostic: runs each stage separately and tells you which one is stuck.
Put this file inside the `backend` folder and run:  python debug_check.py
"""
import asyncio
import time
import uuid


def line(title):
    print("\n" + "=" * 8, title)


async def stage(name, coro, timeout):
    t = time.time()
    try:
        res = await asyncio.wait_for(coro, timeout)
        print(f"[OK]   {name}  ({time.time() - t:.1f}s)")
        return res
    except asyncio.TimeoutError:
        print(f"[STUCK] {name}  - no result after {timeout}s")
    except Exception as e:
        print(f"[FAIL] {name}  - {type(e).__name__}: {str(e)[:300]}")
    return None


async def main():
    line("1. Settings / keys")
    from app.config import settings
    print("GROQ_API_KEY set       :", bool(settings.GROQ_API_KEY))
    print("ELEVENLABS_API_KEY set :", bool(settings.ELEVENLABS_API_KEY))
    print("ELEVENLABS_VOICE_ID set:", bool(settings.ELEVENLABS_VOICE_ID))

    line("2. Embedding model (fastembed)")
    from app.services.embeddings import embed_passages
    vecs = await stage("embed a sentence", embed_passages(["hello world, this is a test"]), 120)

    line("3. Vector store (Qdrant in-memory)")
    from app.services import qdrant_store
    if vecs:
        cid = str(uuid.uuid4())
        doc = str(uuid.uuid4())
        await stage("qdrant upsert",
                    qdrant_store.upsert_chunks(doc, [{"chunk_id": cid, "position": 0, "section": None, "page": 1}], vecs), 30)
        await stage("qdrant search", qdrant_store.search(doc, vecs[0], 1), 30)
    else:
        print("(skipped: embedding did not work)")

    line("4. Database (SQLite)")
    from sqlalchemy import text
    from app.db import SessionLocal, init_db

    async def db_test():
        await init_db()
        async with SessionLocal() as s:
            await s.execute(text("select 1"))

    await stage("database", db_test(), 30)

    line("5. Groq (internet + API key)")
    import httpx

    async def groq_test():
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.groq.com/openai/v1/models",
                            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"})
        print("       HTTP status:", r.status_code, "(200 = key OK, 401 = wrong key)")

    await stage("groq reachable", groq_test(), 30)

    line("6. ElevenLabs (internet + API key)")

    async def eleven_test():
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.elevenlabs.io/v1/voices/" + settings.ELEVENLABS_VOICE_ID,
                            headers={"xi-api-key": settings.ELEVENLABS_API_KEY})
        print("       HTTP status:", r.status_code, "(200 = OK, 401 = wrong key, 404 = wrong voice id)")

    await stage("elevenlabs reachable", eleven_test(), 30)

    print("\nDONE. Send a screenshot / copy of everything above to Claude.")


if __name__ == "__main__":
    asyncio.run(main())
