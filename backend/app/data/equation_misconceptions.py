"""Versioned, reviewable misconception definitions for equation diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.domain.equation_taxonomy import (
    KnowledgePointCode,
    MISCONCEPTION_VERSION,
    MisconceptionCode,
)


@dataclass(frozen=True)
class MisconceptionDefinition:
    display_name: str
    knowledge_point_code: KnowledgePointCode
    minimum_evidence: str


_DEFINITIONS = {
    MisconceptionCode.BALANCE_VIOLATION: MisconceptionDefinition(
        "等式两边不平衡",
        KnowledgePointCode.EQUATION_EQUIVALENCE,
        "相邻方程不等价，且只改变等式一侧",
    ),
    MisconceptionCode.SIGN_TRANSFER_ERROR: MisconceptionDefinition(
        "移项符号错误",
        KnowledgePointCode.MOVE_TERMS_SIGN,
        "相邻方程不等价，并出现跨等号移动项的结构",
    ),
    MisconceptionCode.DISTRIBUTION_ERROR: MisconceptionDefinition(
        "去括号或分配律错误",
        KnowledgePointCode.DISTRIBUTIVE_EXPANSION,
        "含括号的方程展开后与前一步不等价",
    ),
    MisconceptionCode.COMBINE_LIKE_TERMS_ERROR: MisconceptionDefinition(
        "合并同类项错误",
        KnowledgePointCode.COMBINE_LIKE_TERMS,
        "合并多个同类项后方程不再等价",
    ),
    MisconceptionCode.COEFFICIENT_NORMALIZATION_ERROR: MisconceptionDefinition(
        "系数化为一错误",
        KnowledgePointCode.NORMALIZE_COEFFICIENT,
        "从 ax=b 求解 x 时相邻方程不等价",
    ),
    MisconceptionCode.ARITHMETIC_SLIP: MisconceptionDefinition(
        "基础计算失误",
        KnowledgePointCode.EQUATION_EQUIVALENCE,
        "变形意图可定位，但数值计算使相邻方程不等价",
    ),
    MisconceptionCode.MULTIPLE_POSSIBLE_CAUSES: MisconceptionDefinition(
        "存在多种可能原因",
        KnowledgePointCode.EQUATION_EQUIVALENCE,
        "至少两个具体错因都与当前结构证据相符",
    ),
    MisconceptionCode.INSUFFICIENT_EVIDENCE: MisconceptionDefinition(
        "证据不足",
        KnowledgePointCode.EQUATION_EQUIVALENCE,
        "没有可验证的相邻步骤或表达式无法安全解析",
    ),
}

MISCONCEPTION_DEFINITIONS = MappingProxyType(_DEFINITIONS)

__all__ = [
    "MISCONCEPTION_DEFINITIONS",
    "MISCONCEPTION_VERSION",
    "MisconceptionDefinition",
]
