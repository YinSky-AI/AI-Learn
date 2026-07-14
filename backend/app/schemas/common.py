# -*- coding: utf-8 -*-
"""
统一响应格式 Pydantic Schema 模块

定义平台所有 API 的统一响应格式，确保前后端数据交互的一致性。

标准响应结构：
{
    "code": "SUCCESS",
    "message": "操作成功",
    "data": <业务数据>,
    "meta": <元信息（如分页）>
}

包含的模型和工具函数：
- MetaInfo: 分页元信息
- ApiResponse: 通用 API 响应（支持泛型）
- PagedResponse: 带分页的 API 响应
- success_response: 构造成功响应的字典
- error_response: 构造错误响应的字典
- paged_response: 构造分页响应的字典
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MetaInfo(BaseModel):
    """
    分页元信息模型

    用于列表查询接口的分页信息展示，包含当前页、每页数量、总记录数和总页数。
    """
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")
    total: int = Field(default=0, description="总记录数")
    total_pages: int = Field(default=0, description="总页数")


class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应格式模型（支持泛型）

    所有 API 接口的标准响应结构，支持通过泛型参数 T 指定 data 字段的数据类型，
    便于 IDE 类型推断和 API 文档生成。

    Attributes:
        code: 业务响应码，SUCCESS 表示成功，其他表示各类错误
        message: 面向用户的响应消息
        data: 业务数据，类型由泛型参数决定
        meta: 元信息字典，可用于扩展分页、追踪 ID 等
    """
    code: str = Field(default="SUCCESS", description="响应码")
    message: str = Field(default="操作成功", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="元信息（分页等）")


class PagedResponse(BaseModel, Generic[T]):
    """
    带分页的 API 响应格式模型（支持泛型）

    列表查询接口的标准响应结构，data 为列表类型，meta 为 MetaInfo 分页信息。

    Attributes:
        code: 业务响应码
        message: 响应消息
        data: 业务数据列表
        meta: 分页元信息
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
    """
    构造成功响应字典

    快速创建符合 ApiResponse 结构的成功响应，code 固定为 "SUCCESS"。

    Args:
        data: 业务数据，任意类型
        message: 响应消息，默认 "操作成功"
        meta: 元信息字典，如分页信息、追踪 ID 等

    Returns:
        dict: 标准成功响应字典
    """
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
    """
    构造错误响应字典

    快速创建符合 ApiResponse 结构的错误响应，meta 固定为 None。

    Args:
        code: 业务错误码（如 AUTH_001、VAL_001）
        message: 错误消息，默认 "操作失败"
        data: 错误详情数据，可选

    Returns:
        dict: 标准错误响应字典
    """
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
    """
    构造分页响应字典（兼容前端数据格式）

    将列表数据和分页信息封装为前端期望的格式，data 字段内包含 items 和分页字段。
    前端可直接通过 response.data.items 获取列表，response.data.total 获取总数。

    Args:
        data: 当前页的数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页数量
        message: 响应消息，默认 "查询成功"

    Returns:
        dict: 标准分页响应字典，data 内包含 items、total、page、pageSize、totalPages
    """
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
