import uuid

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .errors import APIError
from .models import User


async def ensure_user(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    if await db.get(User, user_id) is None:
        db.add(User(id=user_id))
        try:
            await db.commit()
        except Exception:  # concurrent upsert from a parallel request
            await db.rollback()
            if (await db.execute(select(User.id).where(User.id == user_id))).first() is None:
                raise
    return user_id


async def get_user_id(x_user_id: str | None = Header(default=None), db: AsyncSession = Depends(get_db)) -> uuid.UUID:
    try:
        uid = uuid.UUID(x_user_id or "")
    except ValueError:
        raise APIError(400, "bad_user_id", "Missing or invalid X-User-Id header.")
    return await ensure_user(db, uid)


def parse_uuid(value: str, what: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise APIError(404, "not_found", f"{what} not found.")
