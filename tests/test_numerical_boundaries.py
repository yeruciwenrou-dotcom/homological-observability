"""Independent high-precision checks of count intervals and rare bridges."""

from __future__ import annotations

import math
import unittest
from fractions import Fraction

import mpmath as mp

from homological_observability import (
    c4_each_leading_route_probability,
    ring_bridge_probability,
    tv_c3_count_vector,
    tv_c4_visible_count,
)


def exact_float(value: float):
    numerator, denominator = value.as_integer_ratio()
    return mp.mpf(numerator) / denominator


def independent_count_tv(n: int, p: float, mean: float):
    """Use the closed-form binomial PMF, separately from the implementation."""
    p_exact, mu = exact_float(p), exact_float(mean)
    poisson_values = [mp.exp(-mu) * mu**k / mp.factorial(k) for k in range(160)]
    binomial_values = [
        mp.mpf(math.comb(n, k)) * p_exact**k * (1 - p_exact) ** (n - k)
        if k <= n
        else mp.mpf(0)
        for k in range(160)
    ]
    return mp.fsum(abs(b - z) for b, z in zip(binomial_values, poisson_values)) / 2


class NumericalBoundaryTests(unittest.TestCase):
    def assert_encloses(self, interval, expected) -> None:
        lower, upper = interval
        self.assertGreaterEqual(lower, 0.0)
        self.assertLessEqual(upper, 1.0)
        self.assertLessEqual(exact_float(lower), expected)
        self.assertGreaterEqual(exact_float(upper), expected)

    def test_large_n_intervals_enclose_independent_probabilities(self) -> None:
        with mp.workdps(100):
            for n in (10**6, 10**9, 10**12):
                with self.subTest(n=n):
                    p = 1.0 / n
                    expected = independent_count_tv(n, p, 1.0)
                    interval = tv_c3_count_vector(n, p / 2, 0.5)
                    self.assert_encloses(interval, expected)
                    self.assertLessEqual(
                        interval[1] - interval[0], 2 * math.ulp(interval[1])
                    )
                    self.assert_encloses(tv_c4_visible_count(n, p, 1.0), expected)

    def test_frozen_window_sequence_has_reliable_c3_and_c4_intervals(self) -> None:
        with mp.workdps(100):
            for n in (25, 100, 400, 1600, 6400):
                delta = math.sqrt(1 / n)
                q = math.exp(-2 * delta) * delta**2 / 2
                p = math.expm1(-2 * delta) ** 2 / 4
                with self.subTest(n=n, cycle=3):
                    self.assert_encloses(
                        tv_c3_count_vector(n, q), independent_count_tv(n, 2 * q, 1.0)
                    )
                with self.subTest(n=n, cycle=4):
                    self.assert_encloses(
                        tv_c4_visible_count(n, p), independent_count_tv(n, p, 1.0)
                    )

    def test_total_count_reduction_matches_the_full_two_count_law(self) -> None:
        n, q, mean = 8, 0.125, 0.4
        with mp.workdps(100):
            exact_q = Fraction.from_float(q)
            mu = exact_float(mean)
            differences = []
            poisson_mass = []
            for a in range(n + 1):
                for b in range(n - a + 1):
                    finite = (
                        math.comb(n, a)
                        * math.comb(n - a, b)
                        * exact_q ** (a + b)
                        * (1 - 2 * exact_q) ** (n - a - b)
                    )
                    limiting = (
                        mp.exp(-2 * mu)
                        * mu ** (a + b)
                        / (mp.factorial(a) * mp.factorial(b))
                    )
                    differences.append(
                        abs(mp.mpf(finite.numerator) / finite.denominator - limiting)
                    )
                    poisson_mass.append(limiting)
            expected = (mp.fsum(differences) + 1 - mp.fsum(poisson_mass)) / 2
            self.assert_encloses(tv_c3_count_vector(n, q, mean), expected)

    def test_short_cutoffs_retain_tail_bounds_and_degenerate_inputs(self) -> None:
        with mp.workdps(100):
            for p, mean in ((0.0, 1.0), (1.0, 1.0), (0.2, 0.0), (0.3, 4.0)):
                expected = independent_count_tv(10, p, mean)
                for cutoff in (0, 2, 24):
                    with self.subTest(p=p, mean=mean, cutoff=cutoff):
                        self.assert_encloses(
                            tv_c4_visible_count(10, p, mean, cutoff), expected
                        )
            self.assertEqual(tv_c4_visible_count(10, 0.0, 0.0), (0.0, 0.0))

    def test_rare_endpoint_scale_cancels_before_bridge_evaluation(self) -> None:
        with mp.workdps(100):
            for delta in (1e-150, 1e-160, 1e-200):
                self.assertEqual(c4_each_leading_route_probability(delta), 0.5)
                for n, residue, winding in ((3, 1, -1), (5, 2, -1), (6, 3, 0)):
                    with self.subTest(n=n, delta=delta):
                        d = exact_float(delta)
                        numerator = mp.besseli(abs(residue + n * winding), 2 * d)
                        denominator = mp.fsum(
                            mp.besseli(abs(residue + n * shift), 2 * d)
                            for shift in range(-4, 5)
                        )
                        expected = numerator / denominator
                        actual = ring_bridge_probability(n, residue, winding, delta)
                        self.assertLess(
                            abs(exact_float(actual) / expected - 1), mp.mpf("1e-14")
                        )
                        self.assertEqual(
                            actual,
                            ring_bridge_probability(n, residue + n, winding - 1, delta),
                        )

    def test_unrepresentable_bridge_probability_has_a_range_diagnostic(self) -> None:
        with self.assertRaisesRegex(ValueError, "float range"):
            ring_bridge_probability(3, 1, -1, math.ulp(0.0))


if __name__ == "__main__":
    unittest.main()
