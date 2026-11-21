"""Clock feasibility at the precision of a complete observed record."""

import math
import unittest
from fractions import Fraction

import numpy as np

from homological_observability import infer_target_posterior
from homological_observability._record_inputs import _regular_step
from homological_observability.record_io import recording_example


class SnapshotClockTests(unittest.TestCase):
    def test_all_timestamps_must_share_one_origin_and_step(self):
        epoch = 1_700_000_000
        tick = math.ulp(float(epoch))
        request = recording_example("posterior", "triangle")
        record = request["record"]
        record["states"] = ["a"] * 5
        for first in (epoch, float(epoch)):
            with self.subTest(first=type(first).__name__):
                record["times"] = [first] + [epoch + k * tick for k in (4, 6, 8, 12)]
                with self.assertRaisesRegex(ValueError, "regular grid"):
                    infer_target_posterior(request)

    def test_feasible_step_can_differ_from_endpoint_mean(self):
        epoch = 1_700_000_000.0
        tick = math.ulp(epoch)
        offsets = [0, 1, 3, 5, 7, 8]
        times = [epoch + k * tick for k in offsets]
        step = _regular_step(times) / tick
        # All rounding intervals share an origin at this slope. The observed
        # endpoint mean 8/5 lies outside the feasible interval [5/3, 9/5].
        self.assertGreaterEqual(step, 5 / 3)
        self.assertLessEqual(step, 9 / 5)
        origins = [k - i * step for i, k in enumerate(offsets)]
        self.assertLessEqual(max(origins) - min(origins), 1 + math.ulp(8.0))

    def test_regular_grids_from_decimal_times_and_float_arithmetic(self):
        for times in (
            [float(Fraction(1_700_000_000) + Fraction(i, 10)) for i in range(53)],
            np.linspace(-1, 1, 11).tolist(),
            np.linspace(0, 1, 99).tolist(),
            np.linspace(0.1, 0.9, 50).tolist(),
        ):
            with self.subTest(start=times[0], count=len(times)):
                self.assertEqual(
                    _regular_step(times), (times[-1] - times[0]) / (len(times) - 1)
                )
