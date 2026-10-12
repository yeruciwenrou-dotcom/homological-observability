"""Exact bridge and endpoint probabilities on symmetric cycle graphs."""

from __future__ import annotations

import math
from numbers import Integral

from scipy.special import ive

_MAX_CYCLE_SIZE = 1_000_000
_MAX_WINDING_CUTOFF = 50_000


def _check_cycle_inputs(n: int, delta: float, cutoff: int) -> None:
    if isinstance(n, bool) or not isinstance(n, Integral) or n < 3:
        raise ValueError("n must be an integer of at least 3")
    if n > _MAX_CYCLE_SIZE:
        raise ValueError("floating cycle probabilities require n <= 1000000")
    if not math.isfinite(delta) or delta <= 0.0:
        raise ValueError("delta must be positive and finite")
    if isinstance(cutoff, bool) or not isinstance(cutoff, Integral) or cutoff < 1:
        raise ValueError("cutoff must be a positive integer")
    if cutoff > _MAX_WINDING_CUTOFF:
        raise ValueError("cycle probability exceeds the 100001-term winding budget")


def _congruence_bessel_sum(n: int, residue: int, delta: float, cutoff: int) -> float:
    _check_cycle_inputs(n, delta, cutoff)
    if isinstance(residue, bool) or not isinstance(residue, Integral):
        raise ValueError("residue must be an integer")
    argument = 2.0 * delta
    if not math.isfinite(argument):
        raise ValueError("Bessel argument is outside the finite float range")
    residue = int(residue) % int(n)
    tail_cutoff = math.ceil((residue + 12.0 * math.sqrt(argument)) / n)
    effective_cutoff = max(cutoff, tail_cutoff)
    if effective_cutoff > _MAX_WINDING_CUTOFF:
        raise ValueError("cycle probability exceeds the 100001-term winding budget")
    return math.fsum(
        ive(abs(residue + n * winding), argument)
        for winding in range(-effective_cutoff, effective_cutoff + 1)
    )


def _small_window_bessel_series(order: int, delta: float) -> float:
    """Return I_order(2*delta) / (delta**order / order!) for delta <= 1."""
    term = total = 1.0
    for j in range(1, 32):
        term *= (delta / j) * (delta / (order + j))
        updated = total + term
        if updated == total:
            return total
        total = updated
    raise ArithmeticError("small-window Bessel series did not converge")


def _small_window_bridge(
    n: int, residue: int, winding: int, delta: float, cutoff: int
) -> float:
    """Cancel the common rare-endpoint scale before evaluating the ratio."""
    canonical = residue % n
    base = min(canonical, n - canonical)
    base_series = _small_window_bessel_series(base, delta)

    def relative_weight(order: int) -> float:
        weight = 1.0
        for index in range(base + 1, order + 1):
            weight *= delta / index
            if weight == 0.0:
                return 0.0
        return weight * _small_window_bessel_series(order, delta) / base_series

    effective_cutoff = max(cutoff, (abs(residue) + n - 1) // n + 1)
    denominator = math.fsum(
        relative_weight(abs(residue + n * shift))
        for shift in range(-effective_cutoff, effective_cutoff + 1)
    )
    return relative_weight(abs(residue + n * winding)) / denominator


def _small_window_endpoint(n: int, residue: int, delta: float, cutoff: int) -> float:
    """Accumulate the rare scale in binary exponents and round only at the end."""
    canonical = residue % n
    base = min(canonical, n - canonical)
    leading_winding = 0 if canonical <= n - canonical else -1
    leading_probability = _small_window_bridge(
        n, canonical, leading_winding, delta, cutoff
    )
    mantissa, exponent = math.frexp(
        math.exp(-2 * delta)
        * _small_window_bessel_series(base, delta)
        / leading_probability
    )
    delta_mantissa, delta_exponent = math.frexp(delta)
    for index in range(1, base + 1):
        mantissa, shift = math.frexp(mantissa * delta_mantissa / index)
        exponent += delta_exponent + shift
    return math.ldexp(mantissa, exponent)


def _nonzero_probability(probability: float, *, label: str) -> float:
    if not math.isfinite(probability) or not 0.0 < probability <= 1.0:
        raise ValueError(f"{label} is outside the nonzero finite float range")
    return probability


def ring_bridge_probability(
    n: int,
    residue: int,
    winding: int,
    delta: float,
    cutoff: int = 60,
) -> float:
    """Return P(W=winding | D mod n=residue) on the symmetric C_n.

    Here D is the clockwise jump count minus the counter-clockwise count and
    D = residue + n*winding fixes the lifted displacement.
    """
    if isinstance(winding, bool) or not isinstance(winding, Integral):
        raise ValueError("winding must be an integer")
    _check_cycle_inputs(n, delta, cutoff)
    if isinstance(residue, bool) or not isinstance(residue, Integral):
        raise ValueError("residue must be an integer")
    n, cutoff = int(n), int(cutoff)
    quotient, residue = divmod(int(residue), n)
    winding = int(winding) + quotient
    if delta <= 1.0:
        probability = _small_window_bridge(n, residue, winding, delta, cutoff)
    else:
        denominator = _congruence_bessel_sum(n, residue, delta, cutoff)
        try:
            order = float(abs(residue + n * winding))
        except OverflowError as error:
            raise ValueError(
                "Bessel order is outside the finite float range"
            ) from error
        numerator = float(ive(order, 2.0 * delta))
        if not math.isfinite(denominator) or denominator <= 0.0:
            raise ValueError("bridge endpoint probability could not be resolved")
        probability = numerator / denominator
    return _nonzero_probability(probability, label="bridge probability")


def residue_probability(n: int, residue: int, delta: float, cutoff: int = 60) -> float:
    """Return P(D mod n=residue) for two independent Pois(delta) counts."""
    _check_cycle_inputs(n, delta, cutoff)
    if isinstance(residue, bool) or not isinstance(residue, Integral):
        raise ValueError("residue must be an integer")
    n, cutoff = int(n), int(cutoff)
    residue = int(residue) % n
    if delta <= 1.0:
        probability = _small_window_endpoint(n, residue, delta, cutoff)
    else:
        probability = _congruence_bessel_sum(n, residue, delta, cutoff)
    return _nonzero_probability(probability, label="endpoint probability")


def c3_conditional_hidden_winding_probability(delta: float, cutoff: int = 30) -> float:
    """Return P(W=-1 | D mod 3=1) for the three-cycle example."""
    return ring_bridge_probability(3, 1, -1, delta, cutoff)


def c4_diametric_endpoint_probability(delta: float) -> float:
    """Return the exact probability P(D mod 4=2)."""
    if not math.isfinite(delta) or delta <= 0.0:
        raise ValueError("delta must be positive and finite")
    half_difference = -math.expm1(-2.0 * delta) / 2.0
    return _nonzero_probability(half_difference**2, label="endpoint probability")


def c4_each_leading_route_probability(delta: float, cutoff: int = 30) -> float:
    """Return P(D=+2 | D mod 4=2) for either diametric route."""
    return ring_bridge_probability(4, 2, 0, delta, cutoff)
