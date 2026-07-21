"""当前用户的知识图谱接口。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import ApiResponse, success_response
from app.services.knowledge_graph_service import KnowledgeGraphService, UnknownSubjectError

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def get_knowledge_graph(
    subject: str = Query(default="math", min_length=1, max_length=30, description="学科编码或中文名称"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """返回三学科 MVP 图谱，并使用当前用户的行为报告补充掌握度。"""
    try:
        graph = await KnowledgeGraphService(db).get_for_user(user_id, subject)
    except UnknownSubjectError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GRAPH_001", "message": str(error)},
        ) from error
    return success_response(data=graph, message="获取知识图谱成功")
