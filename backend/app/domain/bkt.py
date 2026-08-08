"""Pure, versioned Bayesian Knowledge Tracing calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


_ZERO = Decimal("0")
_ONE = Decimal("1")
_FOUR_PLACES = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class BKTParameters:
    model_version: str
    p_initial: Decimal
    p_learn: Decimal
    p_slip: Decimal
    p_guess: Decimal

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise ValueError("BKT 模型版本不能为空")
        if any(
            probability < _ZERO or probability > _ONE
            for probability in (
                self.p_initial,
                self.p_learn,
                self.p_slip,
                self.p_guess,
            )
        ):
            raise ValueError("BKT 概率参数必须位于 0 到 1")


BKT_EQUATION_V1 = BKTParameters(
    model_version="bkt-equation-v1",
    p_initial=Decimal("0.35"),
    p_learn=Decimal("0.15"),
    p_slip=Decimal("0.10"),
    p_guess=Decimal("0.20"),
)


def update_bkt(
    prior: Decimal,
    correct: bool,
    parameters: BKTParameters,
) -> Decimal:
    """Apply one observation and learning transition, rounded half-up to 4 places."""

    if prior < _ZERO or prior > _ONE:
        raise ValueError("掌握概率必须位于 0 到 1")
    if correct:
        known_likelihood = prior * (_ONE - parameters.p_slip)
        unknown_likelihood = (_ONE - prior) * parameters.p_guess
    else:
        known_likelihood = prior * parameters.p_slip
        unknown_likelihood = (_ONE - prior) * (_ONE - parameters.p_guess)
    denominator = known_likelihood + unknown_likelihood
    if denominator == _ZERO:
        raise ValueError("当前 BKT 参数下该观测概率为零")
    posterior = known_likelihood / denominator
    after_learning = posterior + (_ONE - posterior) * parameters.p_learn
    return after_learning.quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)
