"""四角色辅导 Provider 接入与降级测试。"""

import asyncio

import pytest

from app.ai.harness import TutorHarness
from app.ai.provider import get_ai_provider, reset_ai_provider
from app.ai.provider import AIProvider
from app.core.config import settings


class _RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    async def generate(self, messages, **_kwargs):
        self.calls.append(messages)
        system = messages[0]["content"]
        role_name = next(
            name for name in ("诊断师", "老师", "苏格拉底助教", "鼓励师") if name in system
        )
        return {"content": f"{role_name}的模型辅导内容：请先说说你观察到的条件。"}


class _FailingProvider:
    async def generate(self, _messages, **_kwargs):
        raise RuntimeError("upstream-secret-stack")


class _SlowProvider:
    async def generate(self, _messages, **_kwargs):
        await asyncio.sleep(0.05)
        return {"content": "不应返回的迟到内容"}


def _wrong_answer_context() -> dict:
    return {
        "question": {
            "question_body": "把十二个苹果平均分给三个人，第一步应该想什么？",
            "knowledge_points": ["平均分"],
            "correct_answer": "机密标准答案：四个",
            "explanation": "机密解析：用十二除以三",
        },
        "student_answer": "我想用加法。",
        "is_correct": False,
        "frustrated": True,
    }


@pytest.mark.asyncio
async def test_configured_provider_generates_all_four_tutor_roles_without_answer_fields():
    provider = _RecordingProvider()

    response = await TutorHarness(provider=provider).reply(_wrong_answer_context())

    assert len(provider.calls) == 4
    assert {message.role for message in response.messages} == {
        "teacher",
        "assistant",
        "diagnostician",
        "encourager",
    }
    assert all("模型辅导内容" in message.content for message in response.messages)
    serialized_prompts = str(provider.calls)
    assert "机密标准答案：四个" not in serialized_prompts
    assert "机密解析：用十二除以三" not in serialized_prompts


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [_FailingProvider(), _SlowProvider()])
async def test_provider_failure_or_timeout_falls_back_to_safe_role_templates(provider):
    response = await TutorHarness(
        provider=provider,
        provider_timeout_seconds=0.01,
    ).reply(_wrong_answer_context())

    assert {message.role for message in response.messages} == {
        "teacher",
        "assistant",
        "diagnostician",
        "encourager",
    }
    contents = "\n".join(message.content for message in response.messages)
    assert "upstream-secret-stack" not in contents
    assert "机密标准答案：四个" not in contents
    assert "机密解析：用十二除以三" not in contents
    assert "不应返回的迟到内容" not in contents
    assert "先" in contents


def test_global_provider_reads_application_ai_settings(monkeypatch):
    reset_ai_provider()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "settings-provider-key")
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "https://provider.example/v1")
    monkeypatch.setattr(settings, "AI_MODEL_NAME", "provider-model")

    try:
        provider = get_ai_provider()
        assert provider.api_key == "settings-provider-key"
        assert provider.base_url == "https://provider.example/v1"
        assert provider.model == "provider-model"
    finally:
        reset_ai_provider()


@pytest.mark.asyncio
async def test_provider_rejects_oversized_input_and_output_budget_before_network_call():
    provider = AIProvider(api_key="test", max_input_chars=10, default_max_tokens=8)
    with pytest.raises(ValueError, match="输入内容过长"):
        await provider.generate([{"role": "user", "content": "01234567890"}])
    with pytest.raises(ValueError, match="输出预算"):
        await provider.generate([{"role": "user", "content": "ok"}], max_tokens=9)
