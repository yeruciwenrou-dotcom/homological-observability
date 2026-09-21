"""Critical count diagnostics and Poisson-averaged MAP formulas."""

from __future__ import annotations

import math
from numbers import Integral

from scipy.special import i0e, i1e
from scipy.stats import binom, poisson

from ._count_tv import binomial_poisson_tv


def tv_c3_count_vector(
    n_windows: int,
    per_direction_mark_probability: float,
    limiting_mean: float = 0.5,
    cutoff: int = 18,
) -> tuple[float, float]:
    """Enclose TV for two winding counts, summing total counts through 2*cutoff.

    Given their total, both vectors have the same Bin(total, 1/2) split.
    Their TV therefore equals TV(Bin(N, 2q), Pois(2*limiting_mean)). The
    returned interval includes both arithmetic rounding and omitted tails.
    """
    if (
        isinstance(n_windows, bool)
        or not isinstance(n_windows, Integral)
        or n_windows < 1
    ):
        raise ValueError("n_windows must be a positive integer")
    if isinstance(cutoff, bool) or not isinstance(cutoff, Integral) or cutoff < 0:
        raise ValueError("cutoff must be a nonnegative integer")
    q = per_direction_mark_probability
    if not math.isfinite(q) or not 0.0 < q < 0.5:
        raise ValueError(
            "per-direction mark probability must be finite and lie in (0, 1/2)"
        )
    if not math.isfinite(limiting_mean) or limiting_mean < 0.0:
        raise ValueError("limiting_mean must be nonnegative and finite")

    return binomial_poisson_tv(
        n_windows, 2.0 * q, limiting_mean, 2 * cutoff, mean_multiplier=2
    )


def tv_c4_visible_count(
    n_windows: int,
    endpoint_probability: float,
    limiting_mean: float = 1.0,
    cutoff: int = 24,
) -> tuple[float, float]:
    """Enclose count TV, including rounding and tails beyond ``cutoff``."""
    if (
        isinstance(n_windows, bool)
        or not isinstance(n_windows, Integral)
        or n_windows < 1
    ):
        raise ValueError("n_windows must be a positive integer")
    if isinstance(cutoff, bool) or not isinstance(cutoff, Integral) or cutoff < 0:
        raise ValueError("cutoff must be a nonnegative integer")
    if not math.isfinite(endpoint_probability) or not (
        0.0 <= endpoint_probability <= 1.0
    ):
        raise ValueError("endpoint_probability must be finite and lie in [0, 1]")
    if not math.isfinite(limiting_mean) or limiting_mean < 0.0:
        raise ValueError("limiting_mean must be nonnegative and finite")

    return binomial_poisson_tv(n_windows, endpoint_probability, limiting_mean, cutoff)


def poisson_averaged_binomial_map_direct(lam: float, cutoff: int = 100) -> float:
    """Evaluate E[max atom of Bin(M,1/2)] for M~Pois(lam)."""
    if not math.isfinite(lam) or lam < 0.0:
        raise ValueError("lam must be nonnegative and finite")
    if isinstance(cutoff, bool) or not isinstance(cutoff, Integral) or cutoff < 0:
        raise ValueError("cutoff must be a nonnegative integer")
    if poisson.sf(cutoff, lam) > 1.0e-14:
        raise ValueError("cutoff is too small for the requested Poisson mean")
    return float(
        sum(poisson.pmf(m, lam) * binom.pmf(m // 2, m, 0.5) for m in range(cutoff + 1))
    )


def poisson_averaged_binomial_map_bessel(lam: float) -> float:
    """Evaluate exp(-lam)[I_0(lam)+I_1(lam)]."""
    if not math.isfinite(lam) or lam < 0.0:
        raise ValueError("lam must be nonnegative and finite")
    probability = float(i0e(lam) + i1e(lam))
    if not math.isfinite(probability) or not 0.0 < probability <= 1.0:
        raise ValueError("MAP probability is outside the nonzero finite float range")
    return probability
