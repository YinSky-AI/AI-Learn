from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.domain.bkt import BKTParameters, BKT_EQUATION_V1, update_bkt


def test_correct_observation_increases_mastery_with_documented_rounding():
    """Changing the BKT formula or rounding rule must make this test fail."""

    result = update_bkt(Decimal("0.35"), True, BKT_EQUATION_V1)

    assert result == Decimal("0.7517")


def test_incorrect_observation_reduces_posterior_before_learning():
    """Skipping the incorrect posterior or learning transition must fail."""

    result = update_bkt(Decimal("0.35"), False, BKT_EQUATION_V1)

    assert result == Decimal("0.2036")


@pytest.mark.parametrize("prior", [Decimal("-0.0001"), Decimal("1.0001")])
def test_update_rejects_prior_outside_probability_range(prior: Decimal):
    """Allowing an invalid mastery probability must make this test fail."""

    with pytest.raises(ValueError, match="掌握概率"):
        update_bkt(prior, True, BKT_EQUATION_V1)


def test_parameters_are_versioned_immutable_probabilities():
    """Making BKT parameters mutable or unversioned must make this test fail."""

    assert BKT_EQUATION_V1.model_version == "bkt-equation-v1"
    with pytest.raises(FrozenInstanceError):
        BKT_EQUATION_V1.p_learn = Decimal("0.9")  # type: ignore[misc]
    with pytest.raises(ValueError, match="概率参数"):
        BKTParameters(
            model_version="invalid",
            p_initial=Decimal("0.35"),
            p_learn=Decimal("1.1"),
            p_slip=Decimal("0.1"),
            p_guess=Decimal("0.2"),
        )


@pytest.mark.parametrize(
    ("prior", "correct", "parameters"),
    [
        (
            Decimal("0"),
            True,
            BKTParameters(
                model_version="zero-correct-denominator",
                p_initial=Decimal("0"),
                p_learn=Decimal("0"),
                p_slip=Decimal("0"),
                p_guess=Decimal("0"),
            ),
        ),
        (
            Decimal("1"),
            False,
            BKTParameters(
                model_version="zero-incorrect-denominator",
                p_initial=Decimal("1"),
                p_learn=Decimal("0"),
                p_slip=Decimal("0"),
                p_guess=Decimal("0"),
            ),
        ),
    ],
)
def test_update_rejects_impossible_zero_denominator_observation(
    prior: Decimal, correct: bool, parameters: BKTParameters
):
    """Silently dividing by zero or inventing a posterior must make this fail."""

    with pytest.raises(ValueError, match="观测概率为零"):
        update_bkt(prior, correct, parameters)
