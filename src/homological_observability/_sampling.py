"""Exact alpha values and their bounded, portable JSON representation."""

from __future__ import annotations

import re
from fractions import Fraction

from ._integer_io import check_integer_text, integer_text_limit

Alpha = float | Fraction
_RATIO = re.compile(r"([0-9]+)/([0-9]+)\Z")


def validate_exact_alpha(value: Fraction) -> Fraction:
    if value < 0:
        raise ValueError("alpha must be nonnegative")
    check_integer_text(value.numerator, label="alpha numerator")
    check_integer_text(value.denominator, label="alpha denominator")
    return value


def parse_alpha(value: object, *, schema_version: int) -> object:
    """Only version 2 JSON admits unsigned integer fractions p/q."""
    if not isinstance(value, str):
        return value
    if schema_version != 2:
        raise ValueError("fraction alpha requires model schema_version 2")
    limit = integer_text_limit()
    if len(value) > 2 * limit + 1:
        raise ValueError("alpha exceeds the decimal input/output limit")
    match = _RATIO.fullmatch(value)
    if match is None:
        raise ValueError("alpha must use nonnegative integer fraction p/q")
    numerator, denominator = match.groups()
    if len(numerator) > limit or len(denominator) > limit:
        raise ValueError("alpha exceeds the decimal input/output limit")
    denominator_value = int(denominator)
    if denominator_value == 0:
        raise ValueError("alpha denominator must be positive")
    return validate_exact_alpha(Fraction(int(numerator), denominator_value))


def alpha_to_json(value: Alpha | None) -> float | str | None:
    if isinstance(value, Fraction):
        validate_exact_alpha(value)
        return f"{value.numerator}/{value.denominator}"
    return value


def exact_alpha(value: Alpha) -> Fraction:
    """Preserve explicit fractions and the exact value of binary float inputs."""
    return value if isinstance(value, Fraction) else Fraction.from_float(value)
