"""Canonical learning-dimension values and catalog boundary mappings."""

from __future__ import annotations

CANONICAL_AGE_GROUPS = ("AGE_06_09", "AGE_10_12", "AGE_13_15", "AGE_16_18")
CANONICAL_DIFFICULTIES = ("DIFF_EASY", "DIFF_MEDIUM", "DIFF_HARD")

SUBJECT_TO_CATALOG = {
    "SUBJ_MATH": "math",
    "SUBJ_CHINESE": "chinese",
    "SUBJ_ENGLISH": "english",
    "SUBJ_PHYSICS": "physics",
    "SUBJ_CHEMISTRY": "chemistry",
    "SUBJ_BIOLOGY": "biology",
    "SUBJ_HISTORY": "history",
    "SUBJ_GEOGRAPHY": "geography",
    "SUBJ_POLITICS": "politics",
    "SUBJ_SCIENCE": "science",
    "SUBJ_ART": "art",
    "SUBJ_PROGRAMMING": "programming",
}

AGE_GROUP_TO_CATALOG = {
    "AGE_06_09": "6-8",
    "AGE_10_12": "9-12",
    "AGE_13_15": "13-15",
    "AGE_16_18": "16-18",
}

# Historical spellings are accepted at the boundary and immediately normalized.
AGE_GROUP_ALIASES = {
    "AGE_06_08": "AGE_06_09",
    "AGE_09_11": "AGE_10_12",
    "AGE_12_14": "AGE_13_15",
    "AGE_15_18": "AGE_16_18",
}

DIFFICULTY_TO_CATALOG = {
    "DIFF_EASY": "beginner",
    "DIFF_MEDIUM": "intermediate",
    "DIFF_HARD": "advanced",
}
DIFFICULTY_FROM_CATALOG = {value: key for key, value in DIFFICULTY_TO_CATALOG.items()}


def normalize_age_group(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = AGE_GROUP_ALIASES.get(value.strip().upper(), value.strip().upper())
    return normalized if normalized in CANONICAL_AGE_GROUPS else None


def normalize_subject(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip().upper()
    if candidate in SUBJECT_TO_CATALOG:
        return candidate
    for code, catalog_value in SUBJECT_TO_CATALOG.items():
        if value.strip().lower() == catalog_value:
            return code
    return None


def normalize_difficulty(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip().upper()
    if candidate in CANONICAL_DIFFICULTIES:
        return candidate
    return {"BEGINNER": "DIFF_EASY", "INTERMEDIATE": "DIFF_MEDIUM", "ADVANCED": "DIFF_HARD"}.get(candidate)
