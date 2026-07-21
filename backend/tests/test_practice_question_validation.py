from types import SimpleNamespace

import pytest

from app.services.content_service import is_question_practice_ready


def _question(question_type="CHOICE", options=None, correct_answer="A"):
    return SimpleNamespace(
        question_type=question_type,
        question_body="一道可练习的题目",
        options=options,
        correct_answer=correct_answer,
    )


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (_question("FILL_BLANK", None, "4"), True),
        (_question("CHOICE", None), False),
        (_question("CHOICE", [{"key": "A", "value": "只有一个选项"}]), False),
        (
            _question(
                "CHOICE",
                [{"key": "A", "value": "选项 A"}, {"key": "B", "value": "选项 B"}],
                "B",
            ),
            True,
        ),
        (
            _question(
                "MULTIPLE_CHOICE",
                [{"key": "A", "value": "选项 A"}, {"key": "B", "value": "选项 B"}],
                "A,C",
            ),
            False,
        ),
    ],
)
def test_practice_question_requires_a_submittable_shape(question, expected):
    assert is_question_practice_ready(question) is expected
