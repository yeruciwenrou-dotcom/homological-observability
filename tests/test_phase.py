"""Tests for theorem-derived sampling-phase predictions."""

from __future__ import annotations

import contextlib
import io
import json
import math
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from homological_observability import cli
from homological_observability.analysis import analyze_model
from homological_observability.model import GraphModel
from homological_observability.phase import SamplingRegime
from homological_observability.serialization import model_to_dict


def wedge_model() -> GraphModel:
    triangle = ("o", "a1", "a2")
    pentagon = ("o", "b1", "b2", "b3", "b4")
    vertices = tuple(sorted(set(triangle + pentagon)))
    edges = tuple(
        (u, v)
        for cycle in (triangle, pentagon)
        for u, v in zip(cycle, cycle[1:] + cycle[:1])
    )
    return GraphModel.create(
        name="wedge-phase",
        vertices=vertices,
        edges=edges,
        max_layer=3,
    )


class PhasePredictionTests(unittest.TestCase):
    def test_wedge_phase_has_two_hidden_free_layers(self) -> None:
        result = analyze_model(wedge_model(), alpha=0.4)
        layer_two, layer_three = result.phase.layers
        self.assertEqual(layer_two.hidden_free_rank, 1)
        self.assertEqual(layer_three.hidden_free_rank, 1)
        self.assertEqual(layer_two.critical_alpha, Fraction(1, 1))
        self.assertEqual(layer_three.critical_alpha, Fraction(1, 2))
        self.assertEqual(layer_two.snapshot_budget_exponent, Fraction(2, 1))
        self.assertEqual(layer_three.snapshot_budget_exponent, Fraction(3, 2))
        self.assertEqual(layer_two.regime, SamplingRegime.DENSE)
        self.assertEqual(layer_three.regime, SamplingRegime.DENSE)
        self.assertAlmostEqual(result.phase.entropy_log_t_coefficient, 0.4)

    def test_critical_and_sparse_regimes_are_classified(self) -> None:
        critical = analyze_model(wedge_model(), alpha=0.5).phase.layers
        self.assertEqual(critical[1].regime, SamplingRegime.CRITICAL)
        sparse = analyze_model(wedge_model(), alpha=1.1).phase.layers
        self.assertEqual(sparse[0].regime, SamplingRegime.SPARSE)
        self.assertEqual(sparse[1].regime, SamplingRegime.SPARSE)
        self.assertEqual(
            analyze_model(
                wedge_model(),
                alpha=1.1,
            ).phase.entropy_log_t_coefficient,
            0.0,
        )

    def test_lambda_values_use_observation_time_and_interval(self) -> None:
        layers = analyze_model(
            wedge_model(),
            observation_time=100.0,
            sampling_interval=0.1,
        ).phase.layers
        self.assertAlmostEqual(layers[0].lambda_value, 10.0)
        self.assertAlmostEqual(layers[1].lambda_value, 1.0)
        self.assertIsNone(layers[0].regime)
        self.assertIsNone(layers[0].entropy_log_t_coefficient)

    def test_invalid_phase_parameters_are_rejected(self) -> None:
        for alpha in (-0.1, math.inf, math.nan):
            with self.subTest(alpha=alpha):
                with self.assertRaises(ValueError):
                    analyze_model(wedge_model(), alpha=alpha)
        for alpha in (True, "0.5"):
            with self.subTest(alpha=alpha):
                with self.assertRaises(TypeError):
                    analyze_model(wedge_model(), alpha=alpha)
        with self.assertRaises(ValueError):
            analyze_model(wedge_model(), observation_time=100.0)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            analyze_model(
                wedge_model(),
                alpha=0.5,
                observation_time=100.0,
                sampling_interval=0.1,
            )
        with self.assertRaises(ValueError):
            analyze_model(
                wedge_model(),
                observation_time=100.0,
                sampling_interval=0.0,
            )

    def test_strict_thresholds_follow_the_exact_binary_input(self) -> None:
        for alpha in (0.9999999999995, 1.0000000000005):
            layer = analyze_model(wedge_model(), alpha=alpha).phase.layers[0]
            expected = 1 - Fraction.from_float(alpha)
            self.assertEqual(layer.scaling_exponent, float(expected))
            self.assertEqual(
                layer.regime,
                SamplingRegime.DENSE if expected > 0 else SamplingRegime.SPARSE,
            )
        vertices = tuple(map(str, range(7)))
        model = GraphModel.create(
            name="c7-phase",
            vertices=vertices,
            edges=tuple((vertices[i], vertices[(i + 1) % 7]) for i in range(7)),
        )
        for alpha in (math.nextafter(1 / 3, 0), 1 / 3, math.nextafter(1 / 3, 1)):
            with self.subTest(alpha=alpha):
                layer = analyze_model(model, alpha=alpha).phase.layers[-1]
                expected = 1 - 3 * Fraction.from_float(alpha)
                self.assertNotEqual(expected, 0)
                self.assertEqual(layer.scaling_exponent, float(expected))
                self.assertEqual(
                    layer.regime,
                    SamplingRegime.DENSE if expected > 0 else SamplingRegime.SPARSE,
                )
                self.assertEqual(
                    layer.entropy_log_t_coefficient,
                    float(max(expected, Fraction(0)) / 2),
                )

    def test_cumulative_exposure_survives_intermediate_range_loss(self) -> None:
        for time, delta in ((1e300, 1e-200), (1e-300, 1e200)):
            with self.subTest(time=time):
                phase = analyze_model(
                    wedge_model(), observation_time=time, sampling_interval=delta
                ).phase
                for layer in phase.layers:
                    expected = Fraction.from_float(time) * Fraction.from_float(
                        delta
                    ) ** (layer.layer - 1)
                    self.assertEqual(layer.lambda_value, float(expected))

    def test_final_range_errors_are_consistent_in_api_and_cli(self) -> None:
        for parameters in (
            {"observation_time": 1e300, "sampling_interval": 1e100},
            {"observation_time": 1e-300, "sampling_interval": 1e-100},
            {"alpha": 1e308},
        ):
            with self.subTest(parameters=parameters):
                with self.assertRaisesRegex(ValueError, "float range"):
                    analyze_model(wedge_model(), **parameters)
                payload = model_to_dict(wedge_model())
                payload["analysis"].update(parameters)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "model.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    for format_name in ("text", "json"):
                        stdout, stderr = io.StringIO(), io.StringIO()
                        with (
                            contextlib.redirect_stdout(stdout),
                            contextlib.redirect_stderr(stderr),
                        ):
                            code = cli.main(
                                ["analyze", str(path), "--format", format_name]
                            )
                        self.assertEqual(code, 2)
                        output = stdout.getvalue() + stderr.getvalue()
                        self.assertIn("float range", output)
                        self.assertNotIn("Traceback", output)
                        if format_name == "json":
                            json.loads(stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
