"""Independent finite-state checks for the Bessel cycle formulas."""

from __future__ import annotations

import math
import unittest

import numpy as np
from scipy.linalg import expm

from homological_observability import (
    c4_diametric_endpoint_probability,
    reciprocal_lattice_peak_error,
    residue_probability,
    ring_bridge_probability,
    tv_c3_count_vector,
    tv_c4_visible_count,
)


def cycle_transition_probability(n: int, residue: int, delta: float) -> float:
    generator = np.zeros((n, n))
    for state in range(n):
        generator[state, state] = -2.0
        generator[state, (state + 1) % n] += 1.0
        generator[state, (state - 1) % n] += 1.0
    return float(expm(delta * generator)[0, residue % n])


def lifted_probability(displacement: int, delta: float, radius: int = 14) -> float:
    states = np.arange(-radius, radius + 1)
    generator = np.zeros((len(states), len(states)))
    for index in range(len(states)):
        generator[index, index] = -2.0
        if index > 0:
            generator[index, index - 1] = 1.0
        if index + 1 < len(states):
            generator[index, index + 1] = 1.0
    origin = radius
    target = displacement + radius
    return float(expm(delta * generator)[origin, target])


class CycleFormulaTests(unittest.TestCase):
    def test_residue_formula_matches_matrix_exponential(self) -> None:
        for n in range(3, 7):
            for residue in range(n):
                with self.subTest(n=n, residue=residue):
                    expected = cycle_transition_probability(n, residue, 0.2)
                    computed = residue_probability(n, residue, 0.2)
                    self.assertAlmostEqual(computed, expected, places=14)

    def test_bridge_formula_matches_lifted_chain(self) -> None:
        for n, residue, winding in ((3, 1, -1), (4, 2, 0), (5, 2, -1)):
            with self.subTest(n=n):
                displacement = residue + n * winding
                expected = lifted_probability(displacement, 0.2) / (
                    cycle_transition_probability(n, residue, 0.2)
                )
                computed = ring_bridge_probability(n, residue, winding, 0.2)
                self.assertAlmostEqual(computed, expected, places=14)

    def test_c4_closed_form_matches_cycle_chain(self) -> None:
        for delta in (0.2, 0.1, 0.05):
            with self.subTest(delta=delta):
                self.assertAlmostEqual(
                    c4_diametric_endpoint_probability(delta),
                    cycle_transition_probability(4, 2, delta),
                    places=14,
                )

    def test_cycle_formulas_remain_finite_for_long_windows(self) -> None:
        endpoint = residue_probability(4, 2, 10000.0)
        posterior = ring_bridge_probability(4, 2, 0, 10000.0)
        self.assertTrue(np.isfinite(endpoint))
        self.assertTrue(np.isfinite(posterior))
        self.assertAlmostEqual(endpoint, 0.25, places=13)
        self.assertGreaterEqual(posterior, 0.0)
        self.assertLessEqual(posterior, 1.0)

    def test_c4_closed_form_retains_small_window_precision(self) -> None:
        delta = 1.0e-12
        self.assertAlmostEqual(
            c4_diametric_endpoint_probability(delta) / delta**2,
            1.0,
            places=11,
        )

    def test_public_inputs_are_checked(self) -> None:
        with self.assertRaises(ValueError):
            ring_bridge_probability(2, 0, 0, 0.1)
        with self.assertRaises(ValueError):
            ring_bridge_probability(3, 0, 0, 0.0)
        with self.assertRaises(ValueError):
            residue_probability(3, 0.5, 0.1)
        with self.assertRaises(ValueError):
            ring_bridge_probability(3, 0, 0.5, 0.1)
        with self.assertRaises(ValueError):
            ring_bridge_probability(3, 0.5, 0, 0.1)
        with self.assertRaises(ValueError):
            tv_c3_count_vector(10.5, 0.01)
        with self.assertRaises(ValueError):
            tv_c4_visible_count(10, 0.01, limiting_mean=math.nan)
        with self.assertRaises(ValueError):
            reciprocal_lattice_peak_error(10.5, 0)


if __name__ == "__main__":
    unittest.main()
