"""Safe parsing and canonicalization for one-variable linear equations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from lark import Lark, Transformer, v_args
from lark.exceptions import LarkError, VisitError
from sympy import Add, Integer, Mul, Poly, Pow, Rational, Symbol, cancel, expand
from sympy.core.expr import Expr
from sympy.polys.polyerrors import PolynomialError


MAX_EQUATION_LENGTH = 200
_X = Symbol("x")
_GRAMMAR = r"""
    ?start: equation
    equation: sum "=" sum
    ?sum: product (ADD_OP product)*
    ?product: unary (MUL_OP unary)*
    ?unary: "-" unary -> negate
          | atom
    ?atom: NUMBER       -> number
         | "x"          -> variable
         | "(" sum ")"

    ADD_OP: "+" | "-"
    MUL_OP: "*" | "/"
    NUMBER: /(?:\d+(?:\.\d*)?|\.\d+)/
"""
_PARSER = Lark(_GRAMMAR, parser="lalr", start="equation")
_CHARACTER_TRANSLATION = str.maketrans(
    {
        "＋": "+",
        "－": "-",
        "−": "-",
        "＊": "*",
        "×": "*",
        "／": "/",
        "÷": "/",
        "＝": "=",
        "（": "(",
        "）": ")",
    }
)


class EquationSyntaxError(ValueError):
    """The submitted equation is outside the supported safe grammar."""


class LinearEquationKind(StrEnum):
    LINEAR = "linear"
    IDENTITY = "identity"
    CONTRADICTION = "contradiction"


@dataclass(frozen=True)
class LinearEquation:
    """Canonical representation of ``coefficient * x + constant = 0``."""

    coefficient: Rational
    constant: Rational
    kind: LinearEquationKind


@v_args(inline=True)
class _SympyTransformer(Transformer):
    """Build SymPy nodes directly; raw user text never reaches SymPy parsing."""

    def number(self, token: object) -> Expr:
        return Rational(str(token))

    def variable(self) -> Expr:
        return _X

    def negate(self, value: Expr) -> Expr:
        return Mul(Integer(-1), value, evaluate=True)

    def sum(self, first: Expr, *operations: object) -> Expr:
        result = first
        for index in range(0, len(operations), 2):
            operator = str(operations[index])
            operand = operations[index + 1]
            assert isinstance(operand, Expr)
            result = Add(
                result,
                operand if operator == "+" else Mul(Integer(-1), operand),
                evaluate=True,
            )
        return result

    def product(self, first: Expr, *operations: object) -> Expr:
        result = first
        for index in range(0, len(operations), 2):
            operator = str(operations[index])
            operand = operations[index + 1]
            assert isinstance(operand, Expr)
            if operator == "/":
                if operand == 0:
                    raise EquationSyntaxError("方程包含除以零")
                result = Mul(result, Pow(operand, Integer(-1)), evaluate=True)
            else:
                result = Mul(result, operand, evaluate=True)
        return result

    def equation(self, left: Expr, right: Expr) -> tuple[Expr, Expr]:
        return left, right


def normalize_equation_text(text: str) -> str:
    """Normalize only documented characters and unambiguous multiplication."""

    if not isinstance(text, str) or not text or len(text) > MAX_EQUATION_LENGTH:
        raise EquationSyntaxError("方程长度无效")
    normalized = "".join(text.translate(_CHARACTER_TRANSLATION).split())
    if not normalized:
        raise EquationSyntaxError("方程不能为空")
    normalized = re.sub(r"(?<=[0-9x)])(?=\()", "*", normalized)
    normalized = re.sub(r"(?<=[0-9)])(?=x)", "*", normalized)
    normalized = re.sub(r"(?<=x)(?=[0-9])", "*", normalized)
    normalized = re.sub(r"(?<=\))(?=[0-9])", "*", normalized)
    return normalized


def _canonicalize(left: Expr, right: Expr) -> LinearEquation:
    difference = cancel(left - right)
    numerator, denominator = difference.as_numer_denom()
    if denominator == 0 or denominator.has(_X):
        raise EquationSyntaxError("只支持一元一次方程")
    expression = expand(numerator / denominator)
    if expression == 0:
        return LinearEquation(
            coefficient=Rational(0),
            constant=Rational(0),
            kind=LinearEquationKind.IDENTITY,
        )
    try:
        polynomial = Poly(expression, _X, domain="QQ")
    except (PolynomialError, TypeError, ValueError) as exc:
        raise EquationSyntaxError("只支持一元一次方程") from exc
    if polynomial.degree() > 1:
        raise EquationSyntaxError("只支持一元一次方程")
    coefficient = Rational(polynomial.coeff_monomial(_X))
    constant = Rational(polynomial.coeff_monomial(Integer(1)))
    kind = (
        LinearEquationKind.LINEAR
        if coefficient != 0
        else LinearEquationKind.CONTRADICTION
    )
    return LinearEquation(coefficient=coefficient, constant=constant, kind=kind)


def parse_linear_equation(text: str) -> LinearEquation:
    """Parse a supported equation without evaluating user-controlled code."""

    try:
        tree = _PARSER.parse(normalize_equation_text(text))
        transformed = _SympyTransformer().transform(tree)
        if not isinstance(transformed, tuple) or len(transformed) != 2:
            raise EquationSyntaxError("方程格式无效")
        left, right = transformed
        return _canonicalize(left, right)
    except EquationSyntaxError:
        raise
    except (LarkError, VisitError, PolynomialError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise EquationSyntaxError("无法识别该方程写法") from exc


def equations_are_equivalent(first: LinearEquation, second: LinearEquation) -> bool:
    """Return whether two canonical equations have the same solution set."""

    if first.kind is not second.kind:
        return False
    if first.kind is not LinearEquationKind.LINEAR:
        return True
    return first.coefficient * second.constant == second.coefficient * first.constant
