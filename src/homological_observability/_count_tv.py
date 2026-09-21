"""Outward-rounded finite-count TV intervals, including the omitted tails."""

from __future__ import annotations

import math
from decimal import ROUND_CEILING, ROUND_FLOOR, Context, Decimal

_Interval = tuple[Decimal, Decimal]


def binomial_poisson_tv(
    n: int, probability: float, mean: float, cutoff: int, *, mean_multiplier: int = 1
) -> tuple[float, float]:
    """Enclose TV(Bin(n,p), Pois(mean_multiplier*mean)).

    Inputs are the exact values of the supplied binary floats. Positive PMFs
    are propagated by interval recurrence at 60 decimal digits. Integer powers
    use multiplication; no difference of large log-factorials is formed.
    The remaining probability mass supplies a tail bound even for short cutoffs.
    """
    down = Context(prec=60, rounding=ROUND_FLOOR)
    up = Context(prec=60, rounding=ROUND_CEILING)
    n = int(n)
    zero, one = Decimal(0), Decimal(1)
    p = Decimal.from_float(float(probability))
    raw_mean = Decimal.from_float(float(mean))
    mu = (
        down.multiply(raw_mean, mean_multiplier),
        up.multiply(raw_mean, mean_multiplier),
    )
    complement = (down.subtract(one, p), up.subtract(one, p))

    def multiply(left: _Interval, right: _Interval) -> _Interval:
        return down.multiply(left[0], right[0]), up.multiply(left[1], right[1])

    def divide(left: _Interval, right: _Interval) -> _Interval:
        return down.divide(left[0], right[1]), up.divide(left[1], right[0])

    finite = (one, one)
    power = complement
    exponent = n
    while exponent:
        if exponent & 1:
            finite = multiply(finite, power)
        exponent >>= 1
        if exponent:
            power = multiply(power, power)

    # Decimal.exp is correctly rounded (ROUND_HALF_EVEN). Adjacent decimal
    # values enclose it regardless of the arithmetic contexts' rounding modes.
    exp_lower = down.exp(mu[1].copy_negate())
    exp_upper = up.exp(mu[0].copy_negate())
    limiting = (
        max(zero, down.next_minus(exp_lower)),
        up.next_plus(exp_upper),
    )
    if raw_mean == 0:
        limiting = (one, one)
    partial_lower = partial_upper = finite_mass_lower = limit_mass_lower = zero
    for k in range(cutoff + 1):
        if k:
            if p == one:
                finite = (one, one) if k == n else (zero, zero)
            elif k <= n:
                numerator = multiply((Decimal(n - k + 1),) * 2, (p, p))
                denominator = multiply((Decimal(k),) * 2, complement)
                finite = multiply(finite, divide(numerator, denominator))
            else:
                finite = (zero, zero)
            limiting = multiply(limiting, divide(mu, (Decimal(k),) * 2))

        difference_lower = max(
            zero,
            down.subtract(finite[0], limiting[1]),
            down.subtract(limiting[0], finite[1]),
        )
        difference_upper = max(
            up.subtract(finite[1], limiting[0]),
            up.subtract(limiting[1], finite[0]),
        )
        partial_lower = down.add(partial_lower, difference_lower)
        partial_upper = up.add(partial_upper, difference_upper)
        finite_mass_lower = down.add(finite_mass_lower, finite[0])
        limit_mass_lower = down.add(limit_mass_lower, limiting[0])

    tail_upper = up.add(
        max(zero, up.subtract(one, finite_mass_lower)),
        max(zero, up.subtract(one, limit_mass_lower)),
    )
    lower = max(zero, down.divide(partial_lower, 2))
    upper = min(one, up.divide(up.add(partial_upper, tail_upper), 2))
    lower_float, upper_float = float(lower), float(upper)
    if Decimal.from_float(lower_float) > lower:
        lower_float = math.nextafter(lower_float, -math.inf)
    if Decimal.from_float(upper_float) < upper:
        upper_float = math.nextafter(upper_float, math.inf)
    return lower_float, upper_float
