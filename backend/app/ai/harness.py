"""四角色辅导编排入口。"""

from typing import Any

from app.ai.tutor import (
    AssistantAgent,
    DiagnosticianAgent,
    EncouragerAgent,
    SharedState,
    TeacherAgent,
    TutorResponse,
)


class TutorHarness:
    """编排确定性辅导角色，不参与两层出题流程。"""

    def __init__(self) -> None:
        self._core_agents = (
            TeacherAgent(),
            AssistantAgent(),
            DiagnosticianAgent(),
        )
        self._encourager = EncouragerAgent()

    async def reply(self, context: dict[str, Any]) -> TutorResponse:
        """根据题目与学生上下文生成苏格拉底式角色消息。"""

        if not isinstance(context, dict):
            raise ValueError("辅导上下文格式不正确")

        raw_question = context.get("question")
        question = raw_question if isinstance(raw_question, dict) else None
        raw_answer = context.get("student_answer")
        student_answer = str(raw_answer).strip() if raw_answer is not None else None
        state = SharedState(
            question=question,
            student_answer=student_answer,
            context=dict(context),
            diagnosis=self._diagnose(context),
        )

        for agent in self._core_agents:
            agent.respond(state)
        if state.is_incorrect or state.is_frustrated:
            self._encourager.respond(state)

        next_step = (
            "请先回答老师提出的第一个问题，再尝试修正你的思路。"
            if state.is_incorrect
            else "请根据助教的小提示说出你的下一步思路。"
        )
        return TutorResponse(messages=state.messages, suggested_next_step=next_step)

    @staticmethod
    def _diagnose(context: dict[str, Any]) -> str:
        if context.get("is_correct") is False:
            return "当前思路需要重新检查题意与运算含义。"
        return "当前思路方向基本合理，需要继续说明推理过程。"
