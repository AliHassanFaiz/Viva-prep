import uuid

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .errors import APIError
from .models import User
from .services.auth import decode_token

_KNOWN: set[uuid.UUID] = set()  # users already confirmed to exist: avoids a DB hit on every request


def _unauthorized() -> APIError:
    return APIError(401, "unauthorized", "Please log in to continue.")


async def get_user_id(authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)) -> uuid.UUID:
    scheme, _, token = (authorization or "").partition(" ")
    claims = decode_token(token.strip(), "access") if scheme.lower() == "bearer" and token else None
    if claims is None:
        raise _unauthorized()
    try:
        uid = uuid.UUID(claims["sub"])
    except (ValueError, KeyError):
        raise _unauthorized()
    if uid not in _KNOWN:
        user = await db.get(User, uid)
        if user is None:  # valid signature but the account is gone (e.g. database was reset)
            raise _unauthorized()
        _KNOWN.add(uid)
    return uid


def parse_uuid(value: str, what: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise APIError(404, "not_found", f"{what} not found.")
