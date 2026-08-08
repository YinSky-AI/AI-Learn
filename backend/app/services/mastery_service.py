"""Transactional persistence helpers for versioned knowledge mastery."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.bkt import BKT_EQUATION_V1, BKTParameters, update_bkt
from app.models.adaptive_learning import KnowledgeMasteryState
from app.models.content import KnowledgeNode


@dataclass(frozen=True, slots=True)
class MasteryChange:
    state: KnowledgeMasteryState
    knowledge_node: KnowledgeNode
    before: Decimal
    after: Decimal


async def update_mastery(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    knowledge_point_code: str,
    correct: bool,
    answer_reference: str,
    parameters: BKTParameters = BKT_EQUATION_V1,
) -> MasteryChange:
    """Lock and update one versioned BKT state inside the caller's transaction."""

    node = (
        await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.code == knowledge_point_code)
        )
    ).scalar_one_or_none()
    if node is None:
        raise ValueError("knowledge_node_missing")

    state = (
        await db.execute(
            select(KnowledgeMasteryState)
            .where(
                KnowledgeMasteryState.user_id == user_id,
                KnowledgeMasteryState.knowledge_node_id == node.id,
                KnowledgeMasteryState.model_version == parameters.model_version,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if state is None:
        state = KnowledgeMasteryState(
            user_id=user_id,
            knowledge_node_id=node.id,
            p_known=parameters.p_initial,
            model_version=parameters.model_version,
            observation_count=0,
        )
        db.add(state)
        await db.flush()

    before = Decimal(str(state.p_known))
    after = update_bkt(before, correct, parameters)
    state.p_known = after
    state.observation_count += 1
    state.last_answer_ref = answer_reference
    await db.flush()
    return MasteryChange(state=state, knowledge_node=node, before=before, after=after)


async def update_mastery_once(
    db: AsyncSession,
    diagnosis,
    correct: bool,
    parameters: BKTParameters = BKT_EQUATION_V1,
) -> MasteryChange:
    """Public persistence interface keyed by the unique answer diagnosis."""

    if diagnosis.standard_answer_id is not None:
        answer_reference = f"answer:{diagnosis.standard_answer_id}"
    else:
        answer_reference = f"generated_answer:{diagnosis.generated_answer_id}"
    return await update_mastery(
        db,
        user_id=diagnosis.user_id,
        knowledge_point_code=diagnosis.knowledge_point_code,
        correct=correct,
        answer_reference=answer_reference,
        parameters=parameters,
    )
