import json

import pytest

from app.ai.question_pipeline import QuestionPipeline
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
