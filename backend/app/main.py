import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .services import embeddings, qdrant_store, question_gen
from .config import settings
from .db import init_db
from .errors import register_error_handlers
from .routers import auth, documents, history, questions, sessions
from .services import warmup
from .ws import call


async def _warm_all():
    await embeddings.warmup()  # load the embedding model first

    async def probes():
        for m in ("viva", "interview"):  # must match your real mode keys in modes.py
            await question_gen._probe_vectors(m)

    await asyncio.gather(qdrant_store.ensure_collection(), probes(), return_exceptions=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    warm = asyncio.create_task(_warm_all())  # background: first request no longer pays cold-start cost
    yield
    warm.cancel()


app = FastAPI(title="ViVa Prep API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["*"], allow_headers=["*"])
register_error_handlers(app)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(questions.router)
app.include_router(sessions.router)
app.include_router(history.router)
app.include_router(call.router)


@app.get("/api/health")
async def health():
    return {"ok": True}
