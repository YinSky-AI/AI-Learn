import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.encoders import jsonable_encoder
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app


SENSITIVE_KEYS = {
    "correct_answer",
    "correct_option",
    "answer",
    "answer_key",
    "is_correct",
    "model_answer",
    "analysis",
    "explanation",
    "expected_answer",
    "standard_answer",
    "reference_answer",
    "reference_solution",
    "solution",
    "rationale",
}


def _assert_recursively_answer_safe(value):
    if isinstance(value, dict):
        assert SENSITIVE_KEYS.isdisjoint(value)
        for nested in value.values():
            _assert_recursively_answer_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_recursively_answer_safe(nested)


def _assert_normalized_sensitive_keys_absent(value):
    forbidden = {key.replace("_", "") for key in SENSITIVE_KEYS}
    if isinstance(value, dict):
        assert forbidden.isdisjoint(
            str(key).casefold().replace("_", "").replace("-", "") for key in value
        )
        for nested in value.values():
            _assert_normalized_sensitive_keys_absent(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_normalized_sensitive_keys_absent(nested)


def _question():
    return SimpleNamespace(
        id=uuid.uuid4(),
        knowledge_node_id=uuid.uuid4(),
        difficulty_level="DIFF_EASY",
        question_type="CHOICE",
        question_body="1 + 1 等于几？",
        options=[
            {
                "key": "A",
                "value": "2",
                "is_correct": True,
                "metadata": {
                    "correct_answer": "A",
                    "analysis": "直接相加",
                    "safe_hint": "先数一数",
                },
            },
            {"key": "B", "value": "3", "answer": False},
        ],
        correct_answer="A",
        explanation="直接相加",
        standard_time_seconds=30,
        sort_order=1,
        knowledge_node_rel=None,
    )


def _response_payload(response):
    return jsonable_encoder(response)


@pytest.mark.asyncio
async def test_public_content_question_endpoints_use_recursive_brief(monkeypatch):
    from app.api.v1 import content as content_api

    question = _question()

    async def fake_list_by_node(*_args, **_kwargs):
        return [question]

    async def fake_list_all(*_args, **_kwargs):
        return [question]

    async def fake_count(*_args, **_kwargs):
        return 1

    monkeypatch.setattr(content_api.content_service, "list_questions_by_node", fake_list_by_node)
    monkeypatch.setattr(content_api.content_service, "list_all_questions", fake_list_all)
    monkeypatch.setattr(content_api.content_service, "count_all_questions", fake_count)

    node_response = await content_api.list_questions(question.knowledge_node_id, db=object())
    paged_response = await content_api.list_all_questions(
        pagination={"page": 1, "page_size": 20},
        db=object(),
    )

    node_payload = _response_payload(node_response)["data"][0]
    page_payload = _response_payload(paged_response)["data"]["items"][0]
    _assert_recursively_answer_safe(node_payload)
    _assert_recursively_answer_safe(page_payload)
    assert node_payload["options"][0]["metadata"]["safe_hint"] == "先数一数"
    assert page_payload["question_body"] == question.question_body


@pytest.mark.asyncio
async def test_public_content_http_responses_never_expose_answer_equivalents(monkeypatch):
    from app.api.v1 import content as content_api

    question = _question()
    question.options[0].update(
        {
            "correctAnswer": "A",
            "answer_key": "A",
            "correct_option": "A",
            "expectedAnswer": "A",
            "isCorrect": True,
            "metadata": {
                "modelAnswer": "A",
                "referenceSolution": "直接相加",
                "safe_hint": "先数一数",
            },
        }
    )

    async def fake_list(*_args, **_kwargs):
        return [question]

    async def fake_count(*_args, **_kwargs):
        return 1

    async def override_db():
        yield object()

    monkeypatch.setattr(content_api.content_service, "list_questions_by_node", fake_list)
    monkeypatch.setattr(content_api.content_service, "list_all_questions", fake_list)
    monkeypatch.setattr(content_api.content_service, "count_all_questions", fake_count)
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            node_response = await client.get(
                f"/api/v1/content/knowledge-nodes/{question.knowledge_node_id}/questions"
            )
            page_response = await client.get("/api/v1/content/questions")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert node_response.status_code == 200
    assert page_response.status_code == 200
    node_payload = node_response.json()["data"][0]
    page_payload = page_response.json()["data"]["items"][0]
    _assert_normalized_sensitive_keys_absent(node_payload)
    _assert_normalized_sensitive_keys_absent(page_payload)
    assert node_payload["options"][0]["metadata"]["safe_hint"] == "先数一数"


def test_public_generated_question_schema_recursively_sanitizes_options():
    from app.schemas.question import GeneratedQuestionPublicResponse

    payload = GeneratedQuestionPublicResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "batch_id": uuid.uuid4(),
            "subject_code": "SUBJ_MATH",
            "course_topic": "加法",
            "difficulty_level": "DIFF_EASY",
            "question_type": "CHOICE",
            "question_body": "1 + 1 等于几？",
            "options": _question().options,
            "correct_answer": "A",
            "explanation": "直接相加",
            "knowledge_tags": [
                "加法",
                {"modelAnswer": "A", "safe_hint": "观察运算符"},
            ],
            "quality_status": "passed",
            "created_at": datetime.now(timezone.utc),
        }
    ).model_dump(mode="json")

    _assert_recursively_answer_safe(payload)
    _assert_normalized_sensitive_keys_absent(payload)
    assert payload["options"][0]["metadata"]["safe_hint"] == "先数一数"
    assert payload["knowledge_tags"][1]["safe_hint"] == "观察运算符"


@pytest.mark.asyncio
async def test_wrong_book_list_and_practice_use_recursive_brief(monkeypatch):
    from app.api.v1 import wrong_book as wrong_book_api

    question = _question()
    record = SimpleNamespace(
        id=uuid.uuid4(),
        question=question,
        subject="数学",
        wrong_count=2,
        review_count=1,
        last_wrong_at=datetime.now(timezone.utc),
        is_mastered=False,
        user_note=None,
    )

    async def fake_list(*_args, **_kwargs):
        return [record], 1

    async def fake_practice(*_args, **_kwargs):
        return [question]

    monkeypatch.setattr(wrong_book_api.WrongBookService, "list_questions", fake_list)
    monkeypatch.setattr(wrong_book_api.WrongBookService, "get_practice_questions", fake_practice)

    listing = await wrong_book_api.get_questions(
        page=1,
        page_size=20,
        user_id=uuid.uuid4(),
        db=object(),
    )
    practice = await wrong_book_api.get_practice(
        count=5,
        user_id=uuid.uuid4(),
        db=object(),
    )

    listing_payload = _response_payload(listing)["data"]["items"][0]
    practice_payload = _response_payload(practice)["data"]["questions"][0]
    _assert_recursively_answer_safe(listing_payload)
    _assert_recursively_answer_safe(practice_payload)
    assert listing_payload["options"][0]["metadata"]["safe_hint"] == "先数一数"


def test_verified_and_admin_full_adapters_require_explicit_access_boundary():
    from app.services.question_access import (
        QuestionAccessDenied,
        admin_question_full,
        verified_answer_feedback,
    )

    question = _question()
    with pytest.raises(QuestionAccessDenied):
        verified_answer_feedback(
            question,
            verified_question_id=uuid.uuid4(),
            is_correct=False,
        )
    with pytest.raises(QuestionAccessDenied):
        admin_question_full(
            question,
            is_authorized=False,
            actor_id=uuid.uuid4(),
            reason="question-bank-review",
        )

    verified = verified_answer_feedback(
        question,
        verified_question_id=question.id,
        is_correct=False,
    )
    admin = admin_question_full(
        question,
        is_authorized=True,
        actor_id=uuid.uuid4(),
        reason="question-bank-review",
    )
    assert verified["correct_answer"] == "A"
    assert verified["explanation"] == "直接相加"
    assert admin["correct_answer"] == "A"
