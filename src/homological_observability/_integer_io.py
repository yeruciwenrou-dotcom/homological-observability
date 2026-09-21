"""Bound exact integer text without changing interpreter-wide safety limits."""

from __future__ import annotations

import sys


def integer_text_limit() -> int:
    """Keep public decimal records bounded, even if the process disables its cap."""
    return min(sys.get_int_max_str_digits() or 4300, 4300)


def check_integer_text(value: int, *, label: str) -> None:
    limit = integer_text_limit()
    if abs(value) >= 10**limit:
        raise ValueError(
            f"{label} exceeds the {limit}-digit decimal input/output limit"
        )


def parse_json_integer(text: str) -> int:
    if len(text.lstrip("-")) > integer_text_limit():
        raise ValueError("JSON integer exceeds the decimal input/output limit")
    return int(text)


def decimal_digits(value: int) -> int:
    """Count digits exactly without converting the integer to decimal text."""
    value = abs(value)
    if value == 0:
        return 1
    # A bit-length estimate only selects the starting power; integer comparisons
    # decide the exact answer, including either side of a power of ten.
    exponent = (value.bit_length() - 1) * 30103 // 100000
    power = 10**exponent
    while value < power:
        power //= 10
        exponent -= 1
    while value >= power * 10:
        power *= 10
        exponent += 1
    return exponent + 1
