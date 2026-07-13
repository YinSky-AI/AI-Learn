# -*- coding: utf-8 -*-
"""
统一响应格式模块
所有 API 返回统一格式: { code, message, data, meta }
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MetaInfo(BaseModel):
    """分页元信息"""
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")
    total: int = Field(default=0, description="总记录数")
    total_pages: int = Field(default=0, description="总页数")


class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应格式
    """
    code: str = Field(default="SUCCESS", description="响应码")
    message: str = Field(default="操作成功", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="元信息（分页等）")


class PagedResponse(BaseModel, Generic[T]):
    """
    带分页的 API 响应格式
    """
    code: str = Field(default="SUCCESS", description="响应码")
    message: str = Field(default="操作成功", description="响应消息")
    data: Optional[List[T]] = Field(default=None, description="响应数据列表")
    meta: Optional[MetaInfo] = Field(default=None, description="分页信息")


def success_response(
    data: Any = None,
    message: str = "操作成功",
    meta: Optional[Dict[str, Any]] = None,
) -> dict:
    """构造成功响应"""
    return {
        "code": "SUCCESS",
        "message": message,
        "data": data,
        "meta": meta,
    }


def error_response(
    code: str,
    message: str = "操作失败",
    data: Any = None,
) -> dict:
    """构造错误响应"""
    return {
        "code": code,
        "message": message,
        "data": data,
        "meta": None,
    }


def paged_response(
    data: List[Any],
    total: int,
    page: int,
    page_size: int,
    message: str = "查询成功",
) -> dict:
    """构造分页响应，data 中包含 items 和分页信息（兼容前端期望格式）"""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "code": "SUCCESS",
        "message": message,
        "data": {
            "items": data,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": total_pages,
        },
        "meta": None,
    }
