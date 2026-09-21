#!/usr/bin/env python3
"""Reproduce selected finite-cycle formulas and the lattice-peak example."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .critical import (
    poisson_averaged_binomial_map_bessel,
    poisson_averaged_binomial_map_direct,
)
from .cycles import residue_probability, ring_bridge_probability
from .lattice import (
    reciprocal_lattice_peak_error,
)

DELTAS = (0.2, 0.1, 0.05, 0.025)
MAP_MEANS = (0.2, 1.0, 3.0, 8.0)
BASE_COUNTS = (100, 400, 1600, 6400)


def _row(
    category: str,
    check_type: str,
    check: str,
    parameter: float,
    computed: float,
    comparison: float,
) -> dict[str, float | str]:
    return {
        "category": category,
        "check_type": check_type,
        "check": check,
        "parameter": parameter,
        "computed": computed,
        "comparison_value": comparison,
        "absolute_error": abs(computed - comparison),
    }


def build_results() -> pd.DataFrame:
    """Build the labeled table of selected appendix checks."""
    rows: list[dict[str, float | str]] = []

    for delta in DELTAS:
        rows.extend(
            [
                _row(
                    "finite-cycle bridge",
                    "asymptotic comparison",
                    "C3 hidden winding",
                    delta,
                    ring_bridge_probability(3, 1, -1, delta),
                    delta / 2.0 - delta**2 / 4.0,
                ),
                _row(
                    "finite-cycle bridge",
                    "asymptotic comparison",
                    "C4 each geodesic route",
                    delta,
                    ring_bridge_probability(4, 2, 0, delta),
                    0.5,
                ),
                _row(
                    "finite-cycle bridge",
                    "asymptotic comparison",
                    "C5 long complementary route",
                    delta,
                    ring_bridge_probability(5, 2, -1, delta),
                    delta / 3.0 - delta**2 / 9.0,
                ),
                _row(
                    "finite-cycle bridge",
                    "asymptotic comparison",
                    "C6 diametric endpoint",
                    delta,
                    residue_probability(6, 3, delta),
                    delta**3 / 3.0,
                ),
            ]
        )

    for lam in MAP_MEANS:
        rows.append(
            _row(
                "critical MAP",
                "exact formula comparison",
                "Poisson-averaged binomial MAP identity",
                lam,
                poisson_averaged_binomial_map_direct(lam),
                poisson_averaged_binomial_map_bessel(lam),
            )
        )

    for n_base in BASE_COUNTS:
        rows.extend(
            [
                _row(
                    "reciprocal-lattice peak",
                    "mechanism illustration",
                    "parity peak without auxiliary increments",
                    float(n_base),
                    reciprocal_lattice_peak_error(n_base, 0),
                    math.sqrt(2.0 / math.pi),
                ),
                _row(
                    "reciprocal-lattice peak",
                    "mechanism illustration",
                    "parity peak with subleading auxiliary increments",
                    float(n_base),
                    reciprocal_lattice_peak_error(n_base, int(math.sqrt(n_base))),
                    0.0,
                ),
            ]
        )

    return pd.DataFrame(rows)


def _errors_for(results: pd.DataFrame, check: str) -> np.ndarray:
    return results.loc[results["check"] == check, "absolute_error"].to_numpy()


def _strictly_decreasing(values: np.ndarray, tolerance: float = 0.0) -> bool:
    return bool(np.all(np.diff(values) < tolerance))


def validate_results(results: pd.DataFrame) -> None:
    """Raise AssertionError if an advertised appendix check fails."""
    if results.empty:
        raise AssertionError("selected-check result table is empty")

    for check in (
        "C3 hidden winding",
        "C4 each geodesic route",
        "C5 long complementary route",
        "C6 diametric endpoint",
        "parity peak without auxiliary increments",
        "parity peak with subleading auxiliary increments",
    ):
        errors = _errors_for(results, check)
        if len(errors) < 2 or not _strictly_decreasing(errors, tolerance=1.0e-15):
            raise AssertionError(f"error sequence does not decrease for {check}")

    map_errors = _errors_for(results, "Poisson-averaged binomial MAP identity")
    if len(map_errors) != len(MAP_MEANS) or np.max(map_errors) > 1.0e-12:
        raise AssertionError("Poisson-averaged binomial MAP identity failed")

    expected_types = {
        "asymptotic comparison",
        "exact formula comparison",
        "mechanism illustration",
    }
    if set(results["check_type"]) != expected_types:
        raise AssertionError("unexpected or missing public check type")

    for n, residue, winding in ((3, 1, -1), (4, 2, 0), (5, 2, -1)):
        for delta in DELTAS:
            if (
                abs(
                    ring_bridge_probability(n, residue, winding, delta, cutoff=60)
                    - ring_bridge_probability(n, residue, winding, delta, cutoff=80)
                )
                > 1.0e-14
            ):
                raise AssertionError("bridge Bessel-sum cutoff is unstable")

    for delta in DELTAS:
        if (
            abs(
                residue_probability(6, 3, delta, cutoff=60)
                - residue_probability(6, 3, delta, cutoff=80)
            )
            > 1.0e-14
        ):
            raise AssertionError("residue Bessel-sum cutoff is unstable")


def write_results(results: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False, float_format="%.17g")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / "generated_results/selected_appendix_checks.csv",
    )
    args = parser.parse_args()

    results = build_results()
    validate_results(results)
    write_results(results, args.output)
    print(results.to_string(index=False))
    print(f"\nPASS: selected appendix checks; saved {args.output}")


if __name__ == "__main__":
    main()
