"""Async engine/session. Accepts a Neon URL as-is (postgresql://...?sslmode=require) or falls back to SQLite for local dev."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


def _build_url(raw: str) -> tuple[str, dict]:
    if not raw:
        return "sqlite+aiosqlite:///./viva_dev.db", {}
    url = raw.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    connect_args: dict = {}
    if url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(url)
        q = dict(parse_qsl(parts.query))
        sslmode = q.pop("sslmode", None)
        q.pop("channel_binding", None)  # not understood by asyncpg
        ssl_flag = q.pop("ssl", None)
        if sslmode in ("require", "verify-ca", "verify-full") or ssl_flag in ("true", "require", "1") or "neon.tech" in parts.netloc:
            connect_args["ssl"] = True
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))
    return url, connect_args


DB_URL, _connect_args = _build_url(settings.DATABASE_URL)
IS_SQLITE = DB_URL.startswith("sqlite")

_kwargs: dict = {"connect_args": _connect_args}
if not IS_SQLITE:
    # Neon scales to zero and closes idle connections: verify before use, recycle often.
    _kwargs.update(pool_pre_ping=True, pool_recycle=300, pool_size=5, max_overflow=5)

engine = create_async_engine(DB_URL, **_kwargs)

if IS_SQLITE:
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_fk(dbapi_conn, _):  # enforce ON DELETE CASCADE like Postgres does
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from .models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
