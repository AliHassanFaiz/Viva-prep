import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_user_id, parse_uuid
from ..errors import APIError
from ..models import Document, Question
from ..schemas import QuestionOut, QuestionPatch

router = APIRouter(prefix="/api/questions", tags=["questions"])


def question_out(q: Question) -> dict:
    return QuestionOut(id=str(q.id), position=q.position, text=q.text, topic=q.topic, difficulty=q.difficulty,
                       key_points=list(q.key_points or []), accepted=q.accepted).model_dump()


async def get_owned_question(db: AsyncSession, qid: str, user_id: uuid.UUID) -> Question:
    q = await db.get(Question, parse_uuid(qid, "Question"))
    if q is not None:
        doc = await db.get(Document, q.document_id)
        if doc is not None and doc.user_id == user_id:
            return q
    raise APIError(404, "not_found", "Question not found.")


@router.patch("/{qid}")
async def patch_question(qid: str, body: QuestionPatch, user_id: uuid.UUID = Depends(get_user_id),
                         db: AsyncSession = Depends(get_db)):
    q = await get_owned_question(db, qid, user_id)
    if body.text is not None:
        q.text = body.text.strip()
    if body.accepted is not None:
        q.accepted = body.accepted
    if body.position is not None:
        q.position = body.position
    await db.commit()
    return question_out(q)


@router.delete("/{qid}", status_code=204)
async def delete_question(qid: str, user_id: uuid.UUID = Depends(get_user_id), db: AsyncSession = Depends(get_db)):
    q = await get_owned_question(db, qid, user_id)
    await db.delete(q)
    await db.commit()
    return Response(status_code=204)
