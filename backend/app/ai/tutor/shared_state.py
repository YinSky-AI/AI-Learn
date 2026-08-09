"""四角色辅导共享状态与响应模型。"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field


TutorRole = Literal["teacher", "assistant", "diagnostician", "encourager"]
DiagnosisStatus = Literal["diagnosed", "insufficient_evidence", "not_required"]


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
    diagnosis_status: DiagnosisStatus | None = None
    diagnosis_evidence: str = ""
    misconception_display_name: str = ""
    mastery_band: str = "unknown"
    next_action: str = "ask_diagnostic_question"
    student_message: str = ""

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

    def to_provider_context(self, target: TutorRole) -> str:
        """构造仅含辅导所需白名单字段的模型上下文。

        题目标准答案与解析可能仍存在于 ``question`` 原始字典中，但这里绝不读取，
        避免将未授权答案发送给外部 Provider。
        """

        history_lines = []
        for turn in self.conversation_history[-10:]:
            role = str(turn.get("role", ""))
            content = str(turn.get("content", "")).strip()
            if role in {"user", "student", "assistant"} and content:
                speaker = "学生" if role in {"user", "student"} else "辅导老师"
                history_lines.append(f"{speaker}：{content[:500]}")

        result_status = "尚未判定"
        if isinstance(self.context.get("is_correct"), bool):
            result_status = "回答正确" if not self.is_incorrect else "回答有误"
        sections = [
            f"学生年龄段：{self.student_profile.age_group}",
            f"学科：{self.student_profile.subject or '未提供'}",
            f"题目：{self.question_text}",
            f"学生当前问题：{self.student_message or '未提供'}",
            f"知识点：{self.knowledge_point}",
            f"学生作答：{self.student_attempt or '尚未作答'}",
            f"服务端判定：{result_status}",
            f"掌握度区间：{self.mastery_band}",
            f"已验证证据：{self.diagnosis_evidence or '尚无可用于定位错因的已验证步骤证据'}",
            f"错因：{self.misconception_display_name or '尚未确定'}",
            f"下一动作：{self.next_action}",
            (
                "教学策略："
                f"{self.teaching_strategy.approach} / {self.teaching_strategy.pace} / "
                f"{self.teaching_strategy.focus_area}"
            ),
            f"辅导依据：{self.diagnosis or '证据不足，需要继续了解当前思路。'}",
        ]
        note = self.latest_note(target)
        if note:
            sections.append(f"团队留言：{note}")
        if history_lines:
            sections.append("最近对话：\n" + "\n".join(history_lines))
        return "\n".join(sections)

    def contains_forbidden_answer(self, content: str) -> bool:
        """检查 Provider 输出是否复述了原始标准答案或解析。"""

        if not self.question:
            return False
        for field in ("correct_answer", "explanation", "answer", "analysis"):
            value = self.question.get(field)
            if isinstance(value, str) and value.strip() and value.strip() in content:
                return True
        return False

    @property
    def question_text(self) -> str:
        """从前端题目上下文提取题干，绝不读取标准答案。"""

        if not self.question:
            return "这道题"
        for field in ("question_text", "question_body", "text"):
            value = self.question.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "这道题"

    @property
    def knowledge_point(self) -> str:
        """提取可用于追问的知识点，不从答案或解析中推断。"""

        if self.question:
            points = self.question.get("knowledge_points")
            if isinstance(points, list):
                values = [str(point).strip() for point in points if str(point).strip()]
                if values:
                    return "、".join(values[:2])
            for field in ("knowledge_point", "topic"):
                value = self.question.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return self.student_profile.topic or "题意与条件"

    @property
    def student_attempt(self) -> str:
        """返回学生已提交的作答；未作答时保持为空，避免泄露答案。"""

        return self.student_answer or ""
