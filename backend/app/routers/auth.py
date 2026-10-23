import re
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_db
from ..deps import get_user_id
from ..errors import APIError
from ..models import User
from ..services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class Credentials(BaseModel):
    email: str
    password: str


def _email(raw: str) -> str:
    e = (raw or "").strip().lower()
    if len(e) > 320 or not EMAIL_RE.match(e):
        raise APIError(422, "bad_email", "Enter a valid email address.")
    return e


def _out(user: User) -> dict:
    return {"access_token": auth.create_access_token(user.id), "token_type": "bearer",
            "user": {"id": str(user.id), "email": user.email}}


@router.post("/signup", status_code=201)
async def signup(body: Credentials, db: AsyncSession = Depends(get_db)):
    email = _email(body.email)
    if not (settings.PASSWORD_MIN_LEN <= len(body.password) <= 128):
        raise APIError(422, "weak_password", f"Password must be {settings.PASSWORD_MIN_LEN} to 128 characters.")
    if (await db.execute(select(User.id).where(User.email == email))).first() is not None:
        raise APIError(409, "email_taken", "An account with this email already exists. Log in instead.")
    user = User(id=uuid.uuid4(), email=email, password_hash=await auth.hash_password(body.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:  # two signups with the same email at once
        await db.rollback()
        raise APIError(409, "email_taken", "An account with this email already exists. Log in instead.")
    return _out(user)


@router.post("/login")
async def login(body: Credentials, request: Request, db: AsyncSession = Depends(get_db)):
    email = (body.email or "").strip().lower()
    key = f"{email}|{request.client.host if request.client else ''}"
    if auth.throttled(key):
        raise APIError(429, "too_many_attempts", "Too many failed attempts. Try again in a few minutes.")
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    ok = await auth.verify_password(body.password or "", user.password_hash if user else None)
    if user is None or not ok:  # same message for unknown email and wrong password
        auth.record_fail(key)
        raise APIError(401, "bad_credentials", "Incorrect email or password.")
    auth.clear_fails(key)
    return _out(user)


@router.get("/me")
async def me(user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    return {"id": str(user.id), "email": user.email}
