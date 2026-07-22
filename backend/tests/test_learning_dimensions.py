from app.domain.learning_dimensions import (
    AGE_GROUP_TO_CATALOG,
    DIFFICULTY_TO_CATALOG,
    normalize_age_group,
    normalize_difficulty,
    normalize_subject,
)


def test_canonical_dimensions_and_legacy_age_aliases_are_stable():
    assert normalize_age_group("AGE_06_08") == "AGE_06_09"
    assert normalize_age_group("AGE_10_12") == "AGE_10_12"
    assert AGE_GROUP_TO_CATALOG["AGE_06_09"] == "6-8"
    assert normalize_subject("math") == "SUBJ_MATH"
    assert normalize_difficulty("advanced") == "DIFF_HARD"
    assert DIFFICULTY_TO_CATALOG["DIFF_MEDIUM"] == "intermediate"


def test_unknown_dimension_is_rejected_at_boundary():
    assert normalize_age_group("AGE_UNKNOWN") is None
    assert normalize_subject("unknown") is None
    assert normalize_difficulty("expert") is None
