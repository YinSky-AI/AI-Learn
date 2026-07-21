import uuid
from types import SimpleNamespace

import pytest


def _question(index: int) -> dict:
    return {
        "id": uuid.uuid4(),
        "difficulty_level": "DIFF_EASY",
        "question_type": "CHOICE",
        "question_body": f"题目 {index}",
        "options": [{"key": "A", "value": "选项"}],
        "standard_time_seconds": 30,
    }


@pytest.mark.asyncio
async def test_lesson_quiz_is_answer_safe_and_limited_to_ten(monkeypatch):
    from app.api.v1 import courses as course_api

    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    node_id = uuid.uuid4()
    monkeypatch.setattr(
        course_api.course_service,
        "get_course_by_id",
        lambda *_args, **_kwargs: _async_value(SimpleNamespace(id=course_id)),
    )
    monkeypatch.setattr(
        course_api.course_service,
        "get_lesson_by_id",
        lambda *_args, **_kwargs: _async_value(
            SimpleNamespace(
                id=lesson_id,
                course_id=course_id,
                type="quiz",
                knowledge_node_id=node_id,
            )
        ),
    )
    query_options = {}

    async def fake_list_questions(*_args, **kwargs):
        query_options.update(kwargs)
        return [_question(i) for i in range(12)]

    monkeypatch.setattr(
        course_api.content_service,
        "list_questions_by_node",
        fake_list_questions,
    )

    response = await course_api.get_lesson_quiz(str(course_id), str(lesson_id), db=object())

    assert len(response["data"]) == 10
    assert query_options["local_only"] is True
    assert all("correct_answer" not in question for question in response["data"])
    assert all("explanation" not in question for question in response["data"])


@pytest.mark.asyncio
async def test_non_quiz_lesson_does_not_expose_questions(monkeypatch):
    from app.api.v1 import courses as course_api

    course_id = uuid.uuid4()
    monkeypatch.setattr(
        course_api.course_service,
        "get_course_by_id",
        lambda *_args, **_kwargs: _async_value(SimpleNamespace(id=course_id)),
    )
    monkeypatch.setattr(
        course_api.course_service,
        "get_lesson_by_id",
        lambda *_args, **_kwargs: _async_value(
            SimpleNamespace(
                course_id=course_id,
                type="video",
                knowledge_node_id=uuid.uuid4(),
            )
        ),
    )

    response = await course_api.get_lesson_quiz(str(course_id), str(uuid.uuid4()), db=object())

    payload = response if isinstance(response, dict) else response.model_dump()
    assert payload["data"] is None
    assert payload["message"] == "该课时不是测验课时"


async def _async_value(value):
    return value
