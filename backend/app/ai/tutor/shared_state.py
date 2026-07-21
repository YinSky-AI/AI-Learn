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


@dataclass
class SharedState:
    """四个辅导 Agent 共享的纯 Python 黑板。"""

    question: dict[str, Any] | None = None
    student_answer: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    diagnosis: str | None = None
    messages: list[TutorMessage] = field(default_factory=list)

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
