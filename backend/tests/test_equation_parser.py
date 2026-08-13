from fractions import Fraction

import pytest

from app.domain.equation_parser import (
    EquationSyntaxError,
    LinearEquationKind,
    equations_are_equivalent,
    parse_linear_equation,
)


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os').system('whoami')",
        "x.__class__",
        "[x for x in (1, 2)]",
        "sin(x)=0",
        "x^2=4",
        "x+y=2",
        "x*x=4",
        "1/x=2",
    ],
)
def test_parser_rejects_non_whitelisted_or_nonlinear_syntax(text: str):
    """Removing the whitelist or linearity guard must make this test fail."""

    with pytest.raises(EquationSyntaxError):
        parse_linear_equation(text)


@pytest.mark.parametrize("text", ["", "x=1=2", "x/0=1", "x=", "x=1#ignore"])
def test_parser_rejects_malformed_equations(text: str):
    """Accepting incomplete or partially parsed input must make this test fail."""

    with pytest.raises(EquationSyntaxError):
        parse_linear_equation(text)


def test_parser_rejects_overlong_input():
    """Dropping the input-size boundary must make this test fail."""

    with pytest.raises(EquationSyntaxError):
        parse_linear_equation("x=" + "1" * 199)


@pytest.mark.parametrize(
    ("text", "coefficient", "constant"),
    [
        ("2x+2=10", Fraction(2), Fraction(-8)),
        ("-x=-3", Fraction(-1), Fraction(3)),
        ("0.5x=1.25", Fraction(1, 2), Fraction(-5, 4)),
        ("x/3=2", Fraction(1, 3), Fraction(-2)),
        ("2（x＋1）＝10", Fraction(2), Fraction(-8)),
        ("6÷3x＝4", Fraction(2), Fraction(-4)),
    ],
)
def test_parser_constructs_exact_linear_coefficients(
    text: str, coefficient: Fraction, constant: Fraction
):
    """Using floating-point parsing or omitting normalization must make this fail."""

    equation = parse_linear_equation(text)

    assert Fraction(equation.coefficient) == coefficient
    assert Fraction(equation.constant) == constant
    assert equation.kind is LinearEquationKind.LINEAR


def test_equivalence_is_scale_invariant_but_rejects_a_different_solution():
    """Comparing equation text or coefficients directly must make this test fail."""

    expanded = parse_linear_equation("2(x+1)=10")
    collected = parse_linear_equation("2x+2=10")
    wrong = parse_linear_equation("2x=12")

    assert equations_are_equivalent(expanded, collected)
    assert not equations_are_equivalent(collected, wrong)


def test_identity_and_contradiction_are_not_treated_as_linear_equations():
    """Collapsing all zero-coefficient equations into one kind must make this fail."""

    identity = parse_linear_equation("x=x")
    contradiction = parse_linear_equation("x=x+1")

    assert identity.kind is LinearEquationKind.IDENTITY
    assert contradiction.kind is LinearEquationKind.CONTRADICTION
    assert not equations_are_equivalent(identity, contradiction)
