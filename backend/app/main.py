from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .errors import register_error_handlers
from .routers import documents, history, questions, sessions
from .ws import call


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="ViVa Prep API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["*"], allow_headers=["*"])
register_error_handlers(app)
app.include_router(documents.router)
app.include_router(questions.router)
app.include_router(sessions.router)
app.include_router(history.router)
app.include_router(call.router)


@app.get("/api/health")
async def health():
    return {"ok": True}
