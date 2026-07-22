"""错题本 API。"""

import uuid
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import paged_response, success_response
from app.services.wrong_book_service import WrongBookService
from app.services.question_access import sanitize_public_value

router = APIRouter()


class PracticeAnswerSubmit(BaseModel):
    question_id: uuid.UUID
    user_answer: str = Field(min_length=1, max_length=500)


def _serialize(record):
    question = record.question
    return {"id": str(record.id), "question_id": str(question.id), "question_text": question.question_body, "options": sanitize_public_value(question.options), "subject": record.subject, "knowledge_point": question.knowledge_node_rel.title if question.knowledge_node_rel else None, "difficulty": question.difficulty_level, "wrong_count": record.wrong_count, "review_count": record.review_count, "last_wrong_at": record.last_wrong_at.isoformat(), "is_mastered": record.is_mastered, "user_note": record.user_note}


@router.get("/stats")
async def get_stats(user_id: uuid.UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    return success_response(await WrongBookService(db).get_stats(user_id))


@router.get("/practice")
async def get_practice(subject: str | None = None, count: int = Query(5, ge=1, le=20), user_id: uuid.UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    questions = await WrongBookService(db).get_practice_questions(user_id, subject, count)
    return success_response({"questions": [{"id": str(q.id), "question_text": q.question_body, "options": sanitize_public_value(q.options), "subject": subject, "difficulty": q.difficulty_level} for q in questions], "count": len(questions)})


@router.post("/practice/answer")
async def submit_practice_answer(request: PracticeAnswerSubmit, user_id: uuid.UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    result = await WrongBookService(db).submit_practice_answer(user_id, request.question_id, request.user_answer)
    if not result.pop("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "BIZ_001", "message": "错题不存在或无权练习"})
    return success_response(result, "答案提交成功")


@router.get("")
async def get_questions(subject: str | None = None, knowledge_point: str | None = None, is_mastered: bool | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user_id: uuid.UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    records, total = await WrongBookService(db).list_questions(user_id, subject, knowledge_point, is_mastered, page, page_size)
    return paged_response([_serialize(record) for record in records], total, page, page_size)


@router.post("/{question_id}/master")
async def mark_mastered(question_id: uuid.UUID, user_id: uuid.UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    if not await WrongBookService(db).mark_mastered(user_id, question_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "BIZ_001", "message": "错题记录不存在"})
    return success_response({"success": True}, "已标记为掌握")
