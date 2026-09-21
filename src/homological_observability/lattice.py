"""A finite lattice model that isolates reciprocal-peak suppression."""

from __future__ import annotations

import math
from numbers import Integral

import numpy as np
from scipy.stats import binom


def reciprocal_lattice_peak_error(n_base: int, n_auxiliary: int) -> float:
    """Return the local Gaussian error for 2*Bin(n,1/2)+Bin(m,1/2)."""
    if isinstance(n_base, bool) or not isinstance(n_base, Integral) or n_base < 1:
        raise ValueError("n_base must be a positive integer")
    if (
        isinstance(n_auxiliary, bool)
        or not isinstance(n_auxiliary, Integral)
        or n_auxiliary < 0
    ):
        raise ValueError("n_auxiliary must be a nonnegative integer")

    p_base = binom.pmf(np.arange(n_base + 1), n_base, 0.5)
    p_auxiliary = binom.pmf(np.arange(n_auxiliary + 1), n_auxiliary, 0.5)
    distribution = np.zeros(2 * n_base + n_auxiliary + 1)
    for base_count, probability in enumerate(p_base):
        start = 2 * base_count
        distribution[start : start + n_auxiliary + 1] += probability * p_auxiliary

    mean = n_base + n_auxiliary / 2.0
    scale = 2.0 * math.sqrt(n_base)
    limiting_variance = 0.25
    normalized = (np.arange(distribution.size) - mean) / scale
    gaussian = (2.0 * math.pi * limiting_variance) ** -0.5 * np.exp(
        -(normalized**2) / (2.0 * limiting_variance)
    )
    return float(np.max(np.abs(scale * distribution - gaussian)))
