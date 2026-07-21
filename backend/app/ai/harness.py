"""四角色辅导编排入口。"""

import logging
from typing import Any

from app.ai.provider import get_ai_provider
from app.ai.tutor import (
    DiagnosticianAgent,
    EncouragerAgent,
    MasteryState,
    SharedState,
    SocratesAgent,
    StudentProfile,
    TeacherAgent,
    TutorResponse,
)
from app.ai.tutor.agents import TutorProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

_AUTO_PROVIDER = object()


class TutorHarness:
    """编排四角色辅导；Provider 不可用时逐角色安全降级。"""

    def __init__(
        self,
        provider: TutorProvider | None | object = _AUTO_PROVIDER,
        provider_timeout_seconds: float = 20.0,
    ) -> None:
        self._diagnostician = DiagnosticianAgent()
        self._teacher = TeacherAgent()
        self._assistant = SocratesAgent()
        self._encourager = EncouragerAgent()
        self._provider = (
            self._resolve_configured_provider()
            if provider is _AUTO_PROVIDER
            else provider
        )
        self._provider_timeout_seconds = max(0.001, provider_timeout_seconds)
        self._last_state: SharedState | None = None

    @staticmethod
    def _resolve_configured_provider() -> TutorProvider | None:
        """仅在应用已配置密钥时启用真实 Provider。"""

        if not settings.DEEPSEEK_API_KEY.strip():
            return None
        try:
            return get_ai_provider()
        except Exception as exc:
            logger.warning(
                "辅导 Provider 初始化失败，将使用模板降级: error_type=%s",
                type(exc).__name__,
            )
            return None

    async def reply(self, context: dict[str, Any]) -> TutorResponse:
        """根据题目与学生上下文生成苏格拉底式角色消息。"""

        if not isinstance(context, dict):
            raise ValueError("辅导上下文格式不正确")

        raw_question = context.get("question")
        question = raw_question if isinstance(raw_question, dict) else None
        raw_answer = context.get("student_answer")
        student_answer = str(raw_answer).strip() if raw_answer is not None else None
        profile_data = context.get("student_profile")
        profile_data = profile_data if isinstance(profile_data, dict) else {}
        raw_mastery = context.get("mastery", 0.5)
        if isinstance(raw_mastery, dict):
            raw_mastery = raw_mastery.get("level", 0.5)
        try:
            mastery_level = max(0.0, min(1.0, float(raw_mastery)))
        except (TypeError, ValueError):
            mastery_level = 0.5
        raw_history = context.get("conversation_history")
        history = raw_history[-10:] if isinstance(raw_history, list) else []

        state = SharedState(
            question=question,
            student_answer=student_answer,
            context=dict(context),
            student_profile=StudentProfile(
                age_group=str(profile_data.get("age_group") or context.get("age_group") or "9-12"),
                subject=str(profile_data.get("subject") or context.get("subject") or ""),
                topic=str(profile_data.get("topic") or context.get("topic") or ""),
                frustration_level=float(profile_data.get("frustration_level") or 0.0),
            ),
            mastery=MasteryState(level=mastery_level),
            conversation_history=[turn for turn in history if isinstance(turn, dict)],
        )

        self._diagnostician.diagnose(state)
        await self._teacher.respond(
            state, self._provider, self._provider_timeout_seconds
        )
        await self._assistant.respond(
            state, self._provider, self._provider_timeout_seconds
        )
        await self._diagnostician.respond(
            state, self._provider, self._provider_timeout_seconds
        )
        if state.is_incorrect or state.is_frustrated:
            await self._encourager.respond(
                state, self._provider, self._provider_timeout_seconds
            )
        self._last_state = state

        next_step = (
            "请先回答老师提出的第一个问题，再尝试修正你的思路。"
            if state.is_incorrect
            else "请根据助教的小提示说出你的下一步思路。"
        )
        return TutorResponse(
            messages=state.messages,
            suggested_next_step=next_step,
            diagnosis=state.diagnosis or "需要继续了解当前思路。",
            teaching_strategy=state.teaching_strategy.as_dict(),
            mastery=state.mastery.level,
        )
