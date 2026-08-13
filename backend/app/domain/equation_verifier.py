"""Deterministic verification of adjacent equation-solving steps."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.domain.equation_parser import (
    EquationSyntaxError,
    LinearEquation,
    equations_are_equivalent,
    normalize_equation_text,
    parse_linear_equation,
)


class TransitionFeature(StrEnum):
    DISTRIBUTION_ATTEMPT = "distribution_attempt"
    MOVE_TERMS_ATTEMPT = "move_terms_attempt"
    COMBINE_LIKE_TERMS_ATTEMPT = "combine_like_terms_attempt"
    COEFFICIENT_NORMALIZATION_ATTEMPT = "coefficient_normalization_attempt"
    ONE_SIDE_CHANGED = "one_side_changed"


@dataclass(frozen=True)
class StepVerification:
    parsed_steps: tuple[LinearEquation, ...]
    first_invalid_transition: int | None
    features: frozenset[TransitionFeature]
    parse_error_step: int | None


def _transition_features(
    previous: str,
    current: str,
    previous_equation: LinearEquation,
    current_equation: LinearEquation,
) -> frozenset[TransitionFeature]:
    previous_normalized = normalize_equation_text(previous)
    current_normalized = normalize_equation_text(current)
    previous_left, previous_right = previous_normalized.split("=", maxsplit=1)
    current_left, current_right = current_normalized.split("=", maxsplit=1)
    left_changed = previous_left != current_left
    right_changed = previous_right != current_right
    previous_left_value = parse_linear_equation(f"{previous_left}=0")
    previous_right_value = parse_linear_equation(f"{previous_right}=0")
    current_left_value = parse_linear_equation(f"{current_left}=0")
    current_right_value = parse_linear_equation(f"{current_right}=0")
    left_delta = (
        current_left_value.coefficient - previous_left_value.coefficient,
        current_left_value.constant - previous_left_value.constant,
    )
    right_delta = (
        current_right_value.coefficient - previous_right_value.coefficient,
        current_right_value.constant - previous_right_value.constant,
    )
    opposite_variable_change = (
        left_delta[0] != 0
        and left_delta[1] == 0
        and right_delta == (-left_delta[0], 0)
    )
    opposite_constant_change = (
        left_delta[1] != 0
        and left_delta[0] == 0
        and right_delta == (0, -left_delta[1])
    )
    features: set[TransitionFeature] = set()
    if "(" in previous_normalized and "(" not in current_normalized:
        features.add(TransitionFeature.DISTRIBUTION_ATTEMPT)
    if left_changed != right_changed:
        features.add(TransitionFeature.ONE_SIDE_CHANGED)
    if (
        "(" not in previous_normalized
        and (opposite_variable_change or opposite_constant_change)
    ):
        features.add(TransitionFeature.MOVE_TERMS_ATTEMPT)
    if previous_normalized.count("x") > current_normalized.count("x"):
        features.add(TransitionFeature.COMBINE_LIKE_TERMS_ATTEMPT)
    if (
        abs(previous_equation.coefficient) != 1
        and abs(current_equation.coefficient) == 1
    ):
        features.add(TransitionFeature.COEFFICIENT_NORMALIZATION_ATTEMPT)
    return frozenset(features)


def verify_solution_steps(steps: Sequence[str]) -> StepVerification:
    """Locate the first non-equivalent transition using zero-based indices."""

    parsed: list[LinearEquation] = []
    for step_index, step in enumerate(steps):
        try:
            parsed.append(parse_linear_equation(step))
        except EquationSyntaxError:
            return StepVerification(
                parsed_steps=tuple(parsed),
                first_invalid_transition=None,
                features=frozenset(),
                parse_error_step=step_index,
            )

    for transition_index, (previous, current) in enumerate(
        zip(parsed, parsed[1:], strict=False)
    ):
        if not equations_are_equivalent(previous, current):
            return StepVerification(
                parsed_steps=tuple(parsed),
                first_invalid_transition=transition_index,
                features=_transition_features(
                    steps[transition_index],
                    steps[transition_index + 1],
                    previous,
                    current,
                ),
                parse_error_step=None,
            )
    return StepVerification(
        parsed_steps=tuple(parsed),
        first_invalid_transition=None,
        features=frozenset(),
        parse_error_step=None,
    )
