"""Independent regressions for extreme probabilities and public model inputs."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import mpmath as mp

import homological_observability as ho
from homological_observability._integer_io import decimal_digits
from homological_observability.cycles import c4_diametric_endpoint_probability
from tests.test_critical_product_contract import cycle_payload


def mp_float(value):
    a, b = value.as_integer_ratio()
    return mp.mpf(a) / b


class ExtremeProbabilityTests(unittest.TestCase):
    def test_bessel_map_across_finite_float_scales(self):
        with mp.workdps(380):
            for lam in (
                0.0,
                1e-12,
                0.3,
                1.0,
                8.0,
                100.0,
                1e6,
                1e10,
                1e50,
                1e100,
                sys.float_info.max,
            ):
                with self.subTest(lam=lam):
                    x = mp_float(lam)
                    expected = mp.exp(-x) * (mp.besseli(0, x) + mp.besseli(1, x))
                    actual = ho.poisson_averaged_binomial_map_bessel(lam)
                    self.assertGreater(actual, 0)
                    self.assertLessEqual(actual, 1)
                    self.assertLess(
                        abs(mp_float(actual) / expected - 1), mp.mpf("2e-14")
                    )

    def test_residue_probabilities_preserve_subnormal_mass(self):
        with mp.workdps(100):
            for n, r, d in (
                (4, 2, 1e-160),
                (4, 2, 2e-162),
                (3, 1, 1e-320),
                (6, 3, 1e-107),
                (5, 2, 0.1),
                (4, 2, 1.0),
            ):
                with self.subTest(n=n, residue=r, delta=d):
                    x = mp_float(d)
                    expected = mp.exp(-2 * x) * mp.fsum(
                        mp.besseli(abs(r + n * k), 2 * x) for k in range(-20, 21)
                    )
                    actual = ho.residue_probability(n, r, d)
                    self.assertGreater(actual, 0)
                    self.assertLessEqual(
                        abs(actual - float(expected)),
                        max(2 * math.ulp(float(expected)), 2e-14 * float(expected)),
                    )
                    self.assertEqual(actual, ho.residue_probability(n, r + n, d))
                    if n == 4:
                        self.assertLessEqual(
                            abs(actual - c4_diametric_endpoint_probability(d)),
                            2 * math.ulp(actual),
                        )
            p = ho.residue_probability(4, 2, 1e-160)
            self.assertGreater(p * 1e308, 9.9e-13)
            self.assertLess(p * 1e308, 1.01e-12)

    def test_unrepresentable_endpoint_mass_is_rejected_in_both_apis(self):
        for function in (
            lambda: ho.residue_probability(4, 2, 1e-200),
            lambda: c4_diametric_endpoint_probability(1e-200),
        ):
            with self.assertRaisesRegex(ValueError, "float range"):
                function()
        self.assertEqual(ho.ring_bridge_probability(4, 2, 0, 1e-200), 0.5)

    def test_bridge_support_and_switch_are_explicit(self):
        with mp.workdps(100):
            for n, r in ((4, 2), (5, 2), (1000, 500)):
                for d in (0.24999999, 0.25, 0.25000001, 0.3, 0.99999999, 1.0):
                    with self.subTest(n=n, delta=d):
                        x = mp_float(d)
                        expected = mp.besseli(r, 2 * x) / mp.fsum(
                            mp.besseli(abs(r + n * k), 2 * x) for k in range(-20, 21)
                        )
                        self.assertLess(
                            abs(
                                mp_float(ho.ring_bridge_probability(n, r, 0, d))
                                / expected
                                - 1
                            ),
                            mp.mpf("2e-14"),
                        )
            for d in (math.nextafter(1.0, math.inf), 1.01):
                self.assertAlmostEqual(
                    ho.ring_bridge_probability(4, 2, 0, d),
                    float(
                        mp.besseli(2, 2 * mp_float(d))
                        / mp.fsum(
                            mp.besseli(abs(2 + 4 * k), 2 * mp_float(d))
                            for k in range(-20, 21)
                        )
                    ),
                    places=14,
                )
                with self.assertRaisesRegex(ValueError, "could not be resolved"):
                    ho.ring_bridge_probability(1000, 500, 0, d)


class PublicInputBoundaryTests(unittest.TestCase):
    def model(self, **kwargs):
        base = ho.parse_critical_model(cycle_payload(3, layer=2))
        values = dict(
            name="input-boundary",
            vertices=base.graph.vertices,
            edges=base.graph.edges,
            rates=base.rate_mapping(),
            layer=2,
            theta=1,
        )
        values.update(kwargs)
        return ho.CriticalModel.create(**values)

    def test_digit_count_is_exact_beyond_the_interpreter_text_limit(self):
        for k in (1, 4095, 4096, 4299, 4300, 5000):
            self.assertEqual(decimal_digits(10**k - 1), k)
            self.assertEqual(decimal_digits(10**k), k + 1)
            self.assertEqual(decimal_digits(-(10**k + 1)), k + 1)
        self.assertEqual(decimal_digits(0), 1)

    def test_representable_over_budget_inputs_keep_complete_identity(self):
        original_limit = sys.get_int_max_str_digits()
        base = self.model()
        for digits in (4097, 4101, 4300):
            big = 10 ** (digits - 1)
            cases = (
                dict(theta=big),
                dict(theta=Fraction(1, big)),
                dict(rates={e: big for e, _ in base.rates}),
                dict(readouts=(("h", {base.graph.edges[0]: big}),)),
            )
            for kwargs in cases:
                with self.subTest(digits=digits, field=next(iter(kwargs))):
                    model = self.model(**kwargs)
                    result = ho.analyze_critical_model(model)
                    self.assertEqual(result.status, ho.CriticalStatus.LIMIT_REACHED)
                    self.assertEqual(result.limit.resource, "integer_digits")
                    self.assertEqual(result.limit.observed_or_estimated, digits)
                    payload = json.loads(ho.render_critical_json(result))
                    self.assertIsNone(payload["catalogue"])
                    self.assertEqual(
                        payload["normalized_model_sha256"],
                        ho.normalized_critical_model_sha256(model),
                    )
                    self.assertEqual(ho.parse_critical_model(payload["model"]), model)
                    self.assertIn("LIMIT_REACHED", ho.render_critical_text(result))
        self.assertEqual(sys.get_int_max_str_digits(), original_limit)

    def test_oversized_python_inputs_are_rejected_before_reports(self):
        old_limit = sys.get_int_max_str_digits()
        base = self.model()
        for value in (
            "1e5000",
            "1e-5000",
            "1e1000000000",
            10**5000,
            Decimal("1e5000"),
            Fraction(1, 10**5000),
        ):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "input/output limit"):
                    self.model(theta=value)
        for kwargs in (
            dict(rates={e: 10**5000 for e, _ in base.rates}),
            dict(readouts=(("h", {base.graph.edges[0]: 10**5000}),)),
        ):
            with self.assertRaisesRegex(ValueError, "input/output limit"):
                self.model(**kwargs)
        with self.assertRaisesRegex(ValueError, "input/output limit"):
            replace(base, theta=Fraction(10**5000))
        with self.assertRaisesRegex(ValueError, "input/output limit"):
            ho.CriticalLimits.create(max_integer_digits=5000)
        with self.assertRaisesRegex(ValueError, "valid exact number"):
            self.model(theta="1e999999999999999999999999")
        self.assertEqual(sys.get_int_max_str_digits(), old_limit)

    def test_cli_rejection_and_resource_results_are_machine_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for theta, code, status in (
                ("1e4100", 1, "LIMIT_REACHED"),
                ("1e5000", 2, "ERROR"),
                ("1e-5000", 2, "ERROR"),
            ):
                payload = cycle_payload(3, layer=2)
                payload["critical"]["theta"] = theta
                path.write_text(json.dumps(payload), encoding="utf-8")
                process = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "homological_observability.cli",
                        "critical",
                        str(path),
                        "--format",
                        "json",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    process.returncode, code, process.stdout + process.stderr
                )
                self.assertEqual(json.loads(process.stdout)["status"], status)
                self.assertNotIn("Traceback", process.stderr)
            for field in ("rate", "readout"):
                payload = cycle_payload(3, layer=2)
                if field == "rate":
                    payload["rates"][0]["rate"] = "1e5000"
                    raw = json.dumps(payload)
                else:
                    payload["readouts"] = [
                        {
                            "name": "large",
                            "coefficients": [
                                {"edge": ["v0", "v1"], "coefficient": "BIG_INTEGER"}
                            ],
                        }
                    ]
                    raw = json.dumps(payload).replace('"BIG_INTEGER"', "1" + "0" * 5000)
                path.write_text(raw, encoding="utf-8")
                process = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "homological_observability.cli",
                        "critical",
                        str(path),
                        "--format",
                        "json",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(process.returncode, 2)
                self.assertEqual(json.loads(process.stdout)["status"], "ERROR")
                self.assertNotIn("Traceback", process.stderr)
            environment = dict(os.environ, PYTHONINTMAXSTRDIGITS="640")
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homological_observability.cli",
                    "critical",
                    str(path),
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("input/output limit", json.loads(process.stdout)["message"])

    def test_direct_constructors_enforce_the_same_graph_contract(self):
        for coefficient in (0.5, True, Fraction(1, 2), "1"):
            with self.subTest(coefficient=coefficient):
                with self.assertRaisesRegex(TypeError, "integers"):
                    ho.IntegerReadout("h", ((("a", "b"), coefficient),))
        graph = ho.GraphModel.create(
            name="c3",
            vertices=("a", "b", "c"),
            edges=(("a", "b"), ("a", "c"), ("b", "c")),
        )
        direct = ho.GraphModel(
            name=graph.name, vertices=graph.vertices, edges=graph.edges
        )
        self.assertEqual(ho.analyze_model(direct), ho.analyze_model(graph))
        for changes in (
            dict(max_layer=0),
            dict(max_cycles=0.5),
            dict(readouts=(ho.IntegerReadout("h", ((("a", "x"), 1),)),)),
            dict(vertices=("a", "a", "b")),
            dict(edges=(("a", "b"),)),
        ):
            with self.subTest(changes=changes):
                with self.assertRaises((ValueError, TypeError)):
                    replace(graph, **changes)


if __name__ == "__main__":
    unittest.main()
