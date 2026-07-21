"""确定性的四角色苏格拉底式辅导 Agent。"""

from abc import ABC, abstractmethod

from app.ai.tutor.shared_state import SharedState, TutorRole


class TutorAgent(ABC):
    """只向共享状态追加一条消息的 Agent 基类。"""

    role: TutorRole
    name: str

    def respond(self, state: SharedState) -> None:
        state.append_message(self.role, self.name, self._build_content(state))

    @abstractmethod
    def _build_content(self, state: SharedState) -> str:
        """生成不直接给出完整答案的中文提示。"""


class TeacherAgent(TutorAgent):
    role = "teacher"
    name = "老师"

    def _build_content(self, state: SharedState) -> str:
        note = state.latest_note("teacher")
        question = state.question_text
        knowledge_point = state.knowledge_point
        attempt = (
            f"你刚才写的是“{state.student_attempt}”。"
            if state.student_attempt
            else "你还没有提交具体作答。"
        )
        if state.teaching_strategy.approach == "simplified":
            return (
                f"针对“{question}”，我们先放慢节奏，聚焦{knowledge_point}中的"
                f"{state.teaching_strategy.focus_area}。{attempt}{note}请先用自己的话说出题目要找什么，好吗？"
            )
        if state.teaching_strategy.approach == "deep":
            return (
                f"针对“{question}”，你目前掌握得不错。我们围绕{knowledge_point}的"
                f"{state.teaching_strategy.focus_area}再深入一步：你能说明每一步为什么成立吗？"
            )
        return (
            f"关于“{question}”，先不急着看答案。我们先看{knowledge_point}。"
            f"{attempt}{note}你能说说题目在问什么，并找出最关键的条件吗？"
        )


class SocratesAgent(TutorAgent):
    role = "assistant"
    name = "苏格拉底助教"

    def _build_content(self, state: SharedState) -> str:
        note = state.latest_note("assistant")
        question = state.question_text
        knowledge_point = state.knowledge_point
        if state.history_mentions("画图"):
            return (
                f"沿用你上一轮提出的画图方法来处理“{question}”：先在图中标出和“{knowledge_point}”"
                "有关的条件。接着你认为应该比较哪两个量？"
            )
        if state.conversation_history:
            return (
                f"结合上一轮关于“{question}”的思路，{note}我们把“{knowledge_point}”拆成"
                "“已知什么、要求什么”两个小问题。"
                "你想先回答哪一个？"
            )
        return (
            f"围绕“{question}”里的{knowledge_point}，{note}我们把问题拆成两个小步骤："
            "先找已知条件，再判断它们之间的关系。你想先做哪一步？"
        )


# 保留已发布的导入名，角色语义由 SocratesAgent 实现。
AssistantAgent = SocratesAgent


class DiagnosticianAgent(TutorAgent):
    role = "diagnostician"
    name = "诊断师"

    def diagnose(self, state: SharedState) -> None:
        """根据回答更新共享诊断、掌握度、策略和角色留言。"""

        has_result = isinstance(state.context.get("is_correct"), bool)
        if has_result:
            state.mastery.record(state.is_incorrect is False)

        if state.is_incorrect:
            if state.student_attempt:
                state.diagnosis = (
                    f"针对“{state.question_text}”，你写的“{state.student_attempt}”可能混淆了"
                    f"{state.knowledge_point}中的题目关系，需要回到条件和运算含义。"
                )
            else:
                state.diagnosis = (
                    f"针对“{state.question_text}”，还需要先确认{state.knowledge_point}中的"
                    "已知条件和所求内容。"
                )
            state.teaching_strategy.approach = "simplified"
            state.teaching_strategy.pace = "slow"
            state.teaching_strategy.focus_area = f"{state.knowledge_point}的题意和运算含义"
            state.add_note("teacher", "先确认所求量，不要展开完整计算。")
            state.add_note("assistant", "用小步骤或图示帮助学生检查原思路。")
            state.add_note("encourager", "肯定学生已做出的尝试，再邀请完成一个小步骤。")
        elif has_result:
            state.diagnosis = (
                f"针对“{state.question_text}”，当前回答方向正确，可以继续说明"
                f"{state.knowledge_point}的推理依据。"
            )
            state.teaching_strategy.approach = "deep"
            state.teaching_strategy.pace = "normal"
            state.teaching_strategy.focus_area = "推理依据"
            state.add_note("teacher", "用追问帮助学生解释理由。")
            state.add_note("assistant", "引导学生检查能否迁移到相似情境。")
        else:
            state.diagnosis = (
                f"针对“{state.question_text}”，信息不足，需要围绕{state.knowledge_point}"
                "追问学生当前思路。"
            )
            state.add_note("teacher", "先询问学生已经想到哪一步。")
            state.add_note("assistant", "提供一个可选择的小步骤。")

        if state.is_frustrated:
            state.student_profile.frustration_level = max(
                state.student_profile.frustration_level, 0.7
            )

    def _build_content(self, state: SharedState) -> str:
        return f"诊断结果：{state.diagnosis}你愿意根据这个线索检查刚才的思路吗？"


class EncouragerAgent(TutorAgent):
    role = "encourager"
    name = "鼓励师"

    def _build_content(self, state: SharedState) -> str:
        note = state.latest_note("encourager")
        return (
            f"{note}暂时答错并不代表不会。我们会按“{state.teaching_strategy.focus_area}”"
            "这个重点慢慢来，你先完成一个小步骤就很好。"
        )
