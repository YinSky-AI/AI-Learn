"""四角色辅导共享状态与响应模型。"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field


TutorRole = Literal["teacher", "assistant", "diagnostician", "encourager"]


class TutorMessage(BaseModel):
    """单个辅导角色面向学生的消息。"""

    role: TutorRole = Field(..., description="辅导角色")
    name: str = Field(..., description="角色中文名称")
    content: str = Field(..., description="苏格拉底式中文提示")


class TutorResponse(BaseModel):
    """一次多角色辅导回复。"""

    messages: list[TutorMessage]
    suggested_next_step: str
    diagnosis: str
    teaching_strategy: dict[str, Any]
    mastery: float


@dataclass
class StudentProfile:
    """本轮辅导所需的最小学生画像。"""

    age_group: str = "9-12"
    subject: str = ""
    topic: str = ""
    frustration_level: float = 0.0


@dataclass
class MasteryState:
    """当前知识点的轻量掌握状态。"""

    level: float = 0.5
    attempt_count: int = 0
    correct_count: int = 0

    def record(self, is_correct: bool) -> None:
        self.attempt_count += 1
        if is_correct:
            self.correct_count += 1
        outcome = 1.0 if is_correct else 0.0
        self.level = round(max(0.0, min(1.0, self.level * 0.7 + outcome * 0.3)), 3)


@dataclass
class TeachingStrategy:
    """由诊断师更新、供后续角色消费的教学策略。"""

    approach: str = "standard"
    pace: str = "normal"
    focus_area: str = "题意与条件"

    def as_dict(self) -> dict[str, str]:
        return {
            "approach": self.approach,
            "pace": self.pace,
            "focus_area": self.focus_area,
        }


@dataclass
class SharedState:
    """四个辅导 Agent 共享的纯 Python 黑板。"""

    question: dict[str, Any] | None = None
    student_answer: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    diagnosis: str | None = None
    messages: list[TutorMessage] = field(default_factory=list)
    student_profile: StudentProfile = field(default_factory=StudentProfile)
    mastery: MasteryState = field(default_factory=MasteryState)
    teaching_strategy: TeachingStrategy = field(default_factory=TeachingStrategy)
    agent_notes: dict[str, list[str]] = field(default_factory=dict)
    conversation_history: list[dict[str, str]] = field(default_factory=list)

    @property
    def is_incorrect(self) -> bool:
        return self.context.get("is_correct") is False

    @property
    def is_frustrated(self) -> bool:
        if bool(self.context.get("frustrated")):
            return True
        text = " ".join(
            str(value)
            for value in (
                self.student_answer,
                self.context.get("student_message"),
                self.context.get("frustration"),
            )
            if value
        )
        return any(keyword in text for keyword in ("不会", "不知道", "太难", "做不到", "放弃", "沮丧"))

    def append_message(self, role: TutorRole, name: str, content: str) -> None:
        """追加一条角色消息，不改变其他共享状态。"""

        self.messages.append(TutorMessage(role=role, name=name, content=content))

    def add_note(self, target: TutorRole, content: str) -> None:
        self.agent_notes.setdefault(target, []).append(content)

    def latest_note(self, target: TutorRole) -> str:
        notes = self.agent_notes.get(target, [])
        return notes[-1] if notes else ""

    def history_mentions(self, keyword: str) -> bool:
        return any(
            keyword in str(turn.get("content", ""))
            for turn in self.conversation_history
            if turn.get("role") in {"user", "student"}
        )
