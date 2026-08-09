import json

import pytest

from app.ai.question_pipeline import (
    AdaptiveGenerationContext,
    QuestionGenerationError,
    QuestionPipeline,
)
from app.schemas.question import QuestionGenerateRequest


class FakeProvider:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []

    async def generate(self, messages):
        self.calls.append(messages)
        return {"content": next(self._responses)}


@pytest.mark.asyncio
async def test_pipeline_returns_revised_questions_after_review_rejection():
    original_questions = [{"question_body": "原题", "correct_answer": "A"}]
    revised_questions = [{"question_body": "修订题", "correct_answer": "B"}]
    provider = FakeProvider(
        [
            json.dumps(original_questions, ensure_ascii=False),
            json.dumps({"passed": False, "revision_notes": "请修正答案"}, ensure_ascii=False),
            json.dumps(revised_questions, ensure_ascii=False),
            json.dumps({"passed": True, "revision_notes": ""}, ensure_ascii=False),
        ]
    )
    request = QuestionGenerateRequest(
        age_group_code="10-12",
        subject_code="数学",
        course_topic="分数加法",
        difficulty_level="medium",
        question_types=["choice"],
        question_count=1,
    )

    result = await QuestionPipeline(provider).generate(request, user_id="user-1", db=None)

    assert result.questions == revised_questions
    assert result.review.passed is True
    assert len(provider.calls) == 4
    assert "请修正答案" in provider.calls[2][0]["content"]


@pytest.mark.asyncio
async def test_pipeline_raises_user_error_after_three_review_rejections():
    questions = [{"question_body": "仍未通过的题目", "correct_answer": "A"}]
    rejection = {"passed": False, "revision_notes": "答案仍有歧义"}
    provider = FakeProvider(
        [
            response
            for _ in range(3)
            for response in (
                json.dumps(questions, ensure_ascii=False),
                json.dumps(rejection, ensure_ascii=False),
            )
        ]
    )
    request = QuestionGenerateRequest(
        age_group_code="10-12",
        subject_code="数学",
        course_topic="分数加法",
        difficulty_level="medium",
        question_types=["choice"],
        question_count=1,
    )

    with pytest.raises(
        QuestionGenerationError,
        match="^题目未能通过审核，请调整条件后重试$",
    ):
        await QuestionPipeline(provider).generate(request, user_id="user-1", db=None)

    assert len(provider.calls) == 6


@pytest.mark.asyncio
async def test_adaptive_constraints_reach_generator_and_reviewer_then_feedback_reaches_retry():
    off_target = [{"question_type": "fill_blank", "question_body": "计算 2 + 3。", "correct_answer": "5", "explanation": "直接相加。", "knowledge_tags": ["arithmetic"]}]
    targeted = [{"question_type": "fill_blank", "question_body": "解方程 2x=8。", "correct_answer": "x=4", "explanation": "等式两边同时除以 2。", "knowledge_tags": ["normalize_coefficient", "coefficient_normalization_error"]}]
    provider = FakeProvider([
        json.dumps(off_target, ensure_ascii=False),
        json.dumps({"passed": False, "revision_notes": "题目未覆盖系数化为一错误，请围绕目标错因修订。"}, ensure_ascii=False),
        json.dumps(targeted, ensure_ascii=False),
        json.dumps({"passed": True, "revision_notes": ""}, ensure_ascii=False),
    ])
    request = QuestionGenerateRequest(age_group_code="13-15", subject_code="math", course_topic="一元一次方程", difficulty_level="medium", question_types=["fill_blank"], question_count=1)
    adaptive = AdaptiveGenerationContext(
        target_knowledge_point_code="normalize_coefficient",
        target_misconception_code="coefficient_normalization_error",
        parent_question_id="11111111-1111-1111-1111-111111111111",
        policy_version="adaptive-policy-v1",
    )

    result = await QuestionPipeline(provider).generate(request, user_id="user-1", db=None, adaptive_context=adaptive)

    assert result.questions == targeted
    generator_prompt = provider.calls[0][0]["content"]
    reviewer_prompt = provider.calls[1][0]["content"]
    retry_prompt = provider.calls[2][0]["content"]
    for prompt in (generator_prompt, reviewer_prompt):
        assert "normalize_coefficient" in prompt
        assert "coefficient_normalization_error" in prompt
        assert "11111111-1111-1111-1111-111111111111" in prompt
    assert "题目未覆盖系数化为一错误" in retry_prompt
    assert len(provider.calls) == 4
