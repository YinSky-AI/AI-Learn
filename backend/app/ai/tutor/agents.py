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
        return "先不急着看答案。你能用自己的话说说题目在问什么，并找出最关键的条件吗？"


class AssistantAgent(TutorAgent):
    role = "assistant"
    name = "助教"

    def _build_content(self, state: SharedState) -> str:
        return "试着画一幅简单的图，或者换成更小的数。这样看时，你认为第一步应该处理哪个数量？"


class DiagnosticianAgent(TutorAgent):
    role = "diagnostician"
    name = "诊断师"

    def _build_content(self, state: SharedState) -> str:
        if state.is_incorrect:
            return "你的思路已经有了起点，但运算含义可能和题意没有完全对应。请比较“合在一起”和“平均分”有什么不同。"
        return "你的表达抓住了主要方向。再检查一次：每个条件都用上了吗，结论能由这些条件一步步推出吗？"


class EncouragerAgent(TutorAgent):
    role = "encourager"
    name = "鼓励师"

    def _build_content(self, state: SharedState) -> str:
        return "暂时答错并不代表不会，你已经找到了可以继续检查的地方。先完成一个小步骤，我们再一起往下想。"
