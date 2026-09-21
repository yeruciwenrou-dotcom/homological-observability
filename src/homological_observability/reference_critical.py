#!/usr/bin/env python3
"""Reproduce the three-cycle and four-cycle critical-kernel checks."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .critical import (
    tv_c3_count_vector,
    tv_c4_visible_count,
)
from .cycles import (
    c3_conditional_hidden_winding_probability,
    c4_diametric_endpoint_probability,
    c4_each_leading_route_probability,
)

DEFAULT_WINDOWS = (25, 100, 400, 1600, 6400)


def build_results(
    theta: float = 1.0, n_windows_values: tuple[int, ...] = DEFAULT_WINDOWS
) -> pd.DataFrame:
    """Compute the finite-resolution critical-kernel checks."""
    if theta <= 0.0:
        raise ValueError("theta must be positive")

    rows: list[dict[str, float | int]] = []
    for n_windows in n_windows_values:
        delta = math.sqrt(theta / n_windows)

        # N delta^2 = theta, equivalent to T delta = theta when T=N delta.
        # Exact probability of one minimal two-jump winding path with no
        # counter-jumps. Higher-jump winding paths are not included in this
        # finite-N count diagnostic; they vanish at the displayed limit.
        c3_mark_probability = math.exp(-2.0 * delta) * delta**2 / 2.0
        c3_tv_lower, c3_tv_upper = tv_c3_count_vector(
            n_windows,
            c3_mark_probability,
            limiting_mean=theta / 2.0,
        )

        c4_endpoint_probability = c4_diametric_endpoint_probability(delta)
        c4_tv_lower, c4_tv_upper = tv_c4_visible_count(
            n_windows,
            c4_endpoint_probability,
            limiting_mean=theta,
        )

        rows.append(
            {
                "n_windows": n_windows,
                "delta": delta,
                "c3_leading_two_jump_mean_each_direction": (
                    n_windows * c3_mark_probability
                ),
                "c3_limiting_poisson_mean_each_direction": theta / 2.0,
                "c3_leading_count_tv_lower": c3_tv_lower,
                "c3_leading_count_tv_upper": c3_tv_upper,
                "c4_mean_visible_count": n_windows * c4_endpoint_probability,
                "c4_limiting_mean_visible_count": theta,
                "c4_visible_count_tv_lower": c4_tv_lower,
                "c4_visible_count_tv_upper": c4_tv_upper,
                "c3_local_bessel_value": (
                    c3_conditional_hidden_winding_probability(delta)
                ),
                "c3_local_two_term": delta / 2.0 - delta**2 / 4.0,
                "c4_each_route_given_diametric": (
                    c4_each_leading_route_probability(delta)
                ),
            }
        )

    return pd.DataFrame(rows)


def _strictly_decreasing(values: np.ndarray, tolerance: float = 0.0) -> bool:
    return bool(np.all(np.diff(values) < tolerance))


def validate_results(results: pd.DataFrame, theta: float = 1.0) -> None:
    """Raise AssertionError if a stated finite-cycle check fails."""
    if results.empty:
        raise AssertionError("critical-kernel result table is empty")

    if not _strictly_decreasing(results["delta"].to_numpy()):
        raise AssertionError("delta must decrease along the refinement sequence")

    for label, lower_column, upper_column in (
        (
            "C3 leading-count",
            "c3_leading_count_tv_lower",
            "c3_leading_count_tv_upper",
        ),
        (
            "C4 visible-count",
            "c4_visible_count_tv_lower",
            "c4_visible_count_tv_upper",
        ),
    ):
        lower = results[lower_column].to_numpy()
        upper = results[upper_column].to_numpy()
        if np.any(lower < 0.0) or np.any(upper > 1.0):
            raise AssertionError(f"{label} TV bounds leave [0,1]")
        if np.any(lower > upper + 1.0e-13):
            raise AssertionError(f"{label} TV lower bound exceeds upper")
        if not _strictly_decreasing(upper, tolerance=1.0e-13):
            raise AssertionError(f"{label} TV upper bounds do not decrease")

    c3_mean_error = np.abs(
        results["c3_leading_two_jump_mean_each_direction"].to_numpy() - theta / 2.0
    )
    c4_mean_error = np.abs(results["c4_mean_visible_count"].to_numpy() - theta)
    c3_local_error = np.abs(
        results["c3_local_bessel_value"].to_numpy()
        - results["c3_local_two_term"].to_numpy()
    )
    c4_route_error = np.abs(results["c4_each_route_given_diametric"].to_numpy() - 0.5)

    for label, error in (
        ("C3 mean", c3_mean_error),
        ("C4 mean", c4_mean_error),
        ("C3 local expansion", c3_local_error),
        ("C4 route weight", c4_route_error),
    ):
        if not _strictly_decreasing(error, tolerance=1.0e-15):
            raise AssertionError(f"{label} error does not decrease")

    for delta in results["delta"].to_numpy():
        if (
            abs(
                c3_conditional_hidden_winding_probability(delta, cutoff=30)
                - c3_conditional_hidden_winding_probability(delta, cutoff=45)
            )
            > 1.0e-14
        ):
            raise AssertionError("C3 Bessel-sum cutoff is not numerically stable")
        if (
            abs(
                c4_each_leading_route_probability(delta, cutoff=30)
                - c4_each_leading_route_probability(delta, cutoff=45)
            )
            > 1.0e-14
        ):
            raise AssertionError("C4 Bessel-sum cutoff is not numerically stable")


def write_results(results: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False, float_format="%.17g")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theta", type=float, default=1.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / "generated_results/critical_kernel_results.csv",
    )
    args = parser.parse_args()

    results = build_results(theta=args.theta)
    validate_results(results, theta=args.theta)
    write_results(results, args.output)
    print(results.to_string(index=False))
    print(f"\nPASS: critical-kernel checks; saved {args.output}")


if __name__ == "__main__":
    main()
