"""Password hashing (stdlib scrypt) and signed tokens (PyJWT, HS256).

Two token types, so one can never be used as the other:
  access: sent as `Authorization: Bearer ...` on every API call
  ws:     short-lived, bound to ONE session; used in the WebSocket URL (URLs end up in logs)
"""
import asyncio
import base64
import hashlib
import hmac
import os
import secrets
import time
import uuid

import jwt

from ..config import settings
from ..logging_utils import logger

ALGO = "HS256"
_N, _R, _P = 2 ** 14, 8, 1

_secret: str | None = None


def _get_secret() -> str:
    global _secret
    if _secret is None:
        if settings.JWT_SECRET:
            _secret = settings.JWT_SECRET
        else:
            _secret = secrets.token_urlsafe(48)
            logger.warning('{"stage":"auth","warning":"JWT_SECRET is empty: using a random secret, logins reset on restart"}')
    return _secret


# ---- passwords ----
def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password_sync(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(h)}"


def verify_password_sync(password: str, stored: str | None) -> bool:
    try:
        scheme, n, r, p, salt, digest = (stored or "").split("$")
        if scheme != "scrypt":
            return False
        h = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(h, base64.b64decode(digest))
    except Exception:  # malformed hash, bad params
        return False


_DUMMY_HASH = hash_password_sync("not-a-real-password")  # so unknown emails cost the same time as wrong passwords


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(hash_password_sync, password)


async def verify_password(password: str, stored: str | None) -> bool:
    return await asyncio.to_thread(verify_password_sync, password, stored or _DUMMY_HASH) and bool(stored)


# ---- tokens ----
def _encode(claims: dict, ttl_s: int) -> str:
    now = int(time.time())
    return jwt.encode({**claims, "iat": now, "exp": now + ttl_s}, _get_secret(), algorithm=ALGO)


def create_access_token(user_id: uuid.UUID) -> str:
    return _encode({"sub": str(user_id), "typ": "access"}, settings.JWT_EXPIRE_MINUTES * 60)


def create_ws_token(user_id: uuid.UUID, session_id: uuid.UUID) -> str:
    return _encode({"sub": str(user_id), "typ": "ws", "sid": str(session_id)}, settings.WS_TOKEN_TTL_S)


def decode_token(token: str, typ: str) -> dict | None:
    """Returns the claims, or None for anything invalid, expired or of the wrong type."""
    try:
        claims = jwt.decode(token, _get_secret(), algorithms=[ALGO], options={"require": ["exp", "sub", "typ"]})
    except jwt.PyJWTError:
        return None
    return claims if claims.get("typ") == typ else None


# ---- login throttle (in memory: per process) ----
_fails: dict[str, list[float]] = {}


def throttled(key: str) -> bool:
    now = time.time()
    recent = [t for t in _fails.get(key, []) if now - t < settings.LOGIN_WINDOW_S]
    _fails[key] = recent
    return len(recent) >= settings.LOGIN_MAX_FAILS


def record_fail(key: str) -> None:
    _fails.setdefault(key, []).append(time.time())


def clear_fails(key: str) -> None:
    _fails.pop(key, None)
