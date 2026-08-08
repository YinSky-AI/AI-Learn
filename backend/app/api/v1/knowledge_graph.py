"""当前用户的知识图谱接口。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import ApiResponse, success_response
from app.schemas.content import KnowledgePracticeResponse, QuestionBrief
from app.services.knowledge_graph_service import KnowledgeGraphService, UnknownSubjectError

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def get_knowledge_graph(
    subject: str = Query(default="math", min_length=1, max_length=30, description="学科编码或中文名称"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """返回展示图谱，并使用数据库知识节点与 BKT 状态补充运行时事实。"""
    try:
        graph = await KnowledgeGraphService(db).get_for_user(user_id, subject)
    except UnknownSubjectError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GRAPH_001", "message": str(error)},
        ) from error
    return success_response(data=graph, message="获取知识图谱成功")


@router.get("/{graph_node_id}/practice", response_model=ApiResponse)
async def get_knowledge_graph_practice(
    graph_node_id: str = Path(..., min_length=1, max_length=100, description="图谱叶节点 ID"),
    subject: str = Query(..., min_length=1, max_length=30, description="学科编码"),
    name: str = Query(..., min_length=1, max_length=100, description="知识点名称"),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """返回专项练习的安全题面；答案仅在学习会话提交后由服务端返回。"""
    try:
        node, questions = await KnowledgeGraphService(db).get_practice_set(
            subject,
            graph_node_id,
            name,
        )
    except (UnknownSubjectError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    data = KnowledgePracticeResponse(
        graph_node_id=graph_node_id,
        knowledge_node_id=node.id,
        name=name,
        subject=subject,
        difficulty_level=node.difficulty_level,
        questions=[QuestionBrief.model_validate(question) for question in questions[:10]],
    )
    return ApiResponse(data=data, message="获取专项练习成功")
