"""Closed taxonomy and versions for the equation-learning vertical slice."""

from enum import StrEnum


MISCONCEPTION_VERSION = "equation-misconception-v1"
RULE_VERSION = "equation-diagnosis-rules-v1"
RULE_CONFIDENCE_THRESHOLD = 0.85


class KnowledgePointCode(StrEnum):
    EQUATION_EQUIVALENCE = "equation_equivalence"
    DISTRIBUTIVE_EXPANSION = "distributive_expansion"
    COMBINE_LIKE_TERMS = "combine_like_terms"
    MOVE_TERMS_SIGN = "move_terms_sign"
    NORMALIZE_COEFFICIENT = "normalize_coefficient"
    EQUATION_WORD_MODELING = "equation_word_modeling"


class MisconceptionCode(StrEnum):
    BALANCE_VIOLATION = "balance_violation"
    SIGN_TRANSFER_ERROR = "sign_transfer_error"
    DISTRIBUTION_ERROR = "distribution_error"
    COMBINE_LIKE_TERMS_ERROR = "combine_like_terms_error"
    COEFFICIENT_NORMALIZATION_ERROR = "coefficient_normalization_error"
    ARITHMETIC_SLIP = "arithmetic_slip"
    MULTIPLE_POSSIBLE_CAUSES = "multiple_possible_causes"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
