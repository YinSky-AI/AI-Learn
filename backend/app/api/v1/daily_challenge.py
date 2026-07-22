import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_id
from app.models.user import User
from app.schemas.common import success_response
from app.services.daily_challenge_service import DailyChallengeService

router = APIRouter()


class ChallengeAnswer(BaseModel):
    question_id: uuid.UUID
    # 倒计时归零时前端也必须提交，由服务端将未作答项按空答案处理并完成本次挑战。
    selected_answer: str = Field(max_length=500)


class ChallengeSubmitRequest(BaseModel):
    event_id: uuid.UUID
    answers: list[ChallengeAnswer] = Field(min_length=1, max_length=20)


@router.post("/daily/start")
async def start_challenge(user_id: uuid.UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    return success_response(await DailyChallengeService(db).start(user_id), "今日挑战已开始")


@router.post("/daily/submit")
async def submit_challenge(request: ChallengeSubmitRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return success_response(await DailyChallengeService(db).submit(user, request.event_id, [answer.model_dump() for answer in request.answers]), "挑战结果已提交")


@router.get("/leaderboard/{kind}")
async def leaderboard(kind: str, limit: int = Query(50, ge=1, le=50), user_id: uuid.UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    if kind not in {"daily", "total", "streak"}:
        raise HTTPException(status_code=404, detail={"code": "CHALLENGE_005", "message": "不存在的排行榜类型"})
    return success_response(await DailyChallengeService(db).leaderboard(kind, user_id, limit), "排行榜获取成功")
