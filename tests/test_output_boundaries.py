"""Generated integers and resource refusals at the public output boundary."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import jsonschema

import homological_observability as ho
from homological_observability._integer_io import integer_text_limit
from homological_observability.integer_lattice import QuotientInvariants
from tests.test_critical_product_contract import cycle_payload


def triangle_readout(coefficient: int) -> ho.GraphModel:
    return ho.GraphModel.create(
        name="triangle-output-boundary",
        vertices=("a", "b", "c"),
        edges=(("a", "b"), ("a", "c"), ("b", "c")),
        readouts=(
            (
                "h",
                {
                    ("a", "b"): coefficient,
                    ("a", "c"): -coefficient,
                    ("b", "c"): coefficient,
                },
            ),
        ),
    )


def run_cli(command: str, payload: dict, output_format: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "model.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "homological_observability.cli",
                command,
                str(path),
                "--format",
                output_format,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )


class PathPreflightBoundaryTests(unittest.TestCase):
    def test_early_refusals_remain_serializable(self):
        original_limit = sys.get_int_max_str_digits()
        for layer, budget in (
            (2, 1),
            (1000, 100_000),
            (15000, 100_000),
            (10**1000, 100_000),
        ):
            with self.subTest(layer_digits=len(str(layer)), budget=budget):
                model = ho.parse_critical_model(
                    cycle_payload(3, layer=layer, max_paths=budget)
                )
                result = ho.analyze_critical_model(model)
                document = json.loads(ho.render_critical_json(result))
                jsonschema.validate(document, ho.load_critical_experiment_schema())
                self.assertEqual(document["status"], "LIMIT_REACHED")
                self.assertEqual(document["limit"]["resource"], "directed_paths")
                self.assertEqual(document["limit"]["measurement"], "unavailable")
                self.assertIsNone(document["limit"]["observed_or_estimated"])
                self.assertIsNone(document["summary"]["path_count"])
                self.assertIsNone(document["resources"]["usage"]["path_count"])
                self.assertIsNone(document["catalogue"])
                self.assertIn("LIMIT_REACHED", ho.render_critical_text(result))
                self.assertEqual(
                    document["normalized_model_sha256"],
                    ho.normalized_critical_model_sha256(model),
                )
        self.assertEqual(sys.get_int_max_str_digits(), original_limit)

    def test_cli_early_refusals_use_incomplete_exit_code(self):
        for layer in (15000, 10**1000):
            for output_format in ("json", "text"):
                process = run_cli(
                    "critical", cycle_payload(3, layer=layer), output_format
                )
                self.assertEqual(process.returncode, 1, process.stderr)
                self.assertIn("LIMIT_REACHED", process.stdout)
                self.assertEqual(process.stderr, "")
                if output_format == "json":
                    jsonschema.validate(
                        json.loads(process.stdout), ho.load_critical_experiment_schema()
                    )

    def test_small_counts_stay_exact(self):
        for budget, status in ((12, "COMPLETE"), (6, "LIMIT_REACHED")):
            result = ho.analyze_critical_model(
                ho.parse_critical_model(cycle_payload(3, layer=2, max_paths=budget))
            )
            document = json.loads(ho.render_critical_json(result))
            self.assertEqual(document["status"], status)
            self.assertEqual(document["summary"]["path_count"], 12)
            if result.limit is not None:
                self.assertEqual(result.limit.measurement, "exact")

    def test_constant_walk_counts_skip_large_layer_iteration(self):
        for vertices, edges, rates, count in (
            (("a",), (), {}, 0),
            (("a", "b"), (("a", "b"),), {("a", "b"): 1, ("b", "a"): 1}, 2),
        ):
            model = ho.CriticalModel.create(
                name="constant-count",
                vertices=vertices,
                edges=edges,
                rates=rates,
                layer=10**1000,
                theta=1,
            )
            result = ho.analyze_critical_model(model)
            document = json.loads(ho.render_critical_json(result))
            jsonschema.validate(document, ho.load_critical_experiment_schema())
            self.assertEqual(document["limit"]["resource"], "estimated_integer_digits")
            self.assertEqual(document["summary"]["path_count"], count)

    def test_unrepresentable_preflight_estimate_is_omitted(self):
        model = ho.CriticalModel.create(
            name="estimate-boundary",
            vertices=("a",),
            edges=(),
            rates={},
            layer=10 ** integer_text_limit() - 1,
            theta=1,
            limits=ho.CriticalLimits.create(max_integer_digits=integer_text_limit()),
        )
        result = ho.analyze_critical_model(model)
        document = json.loads(ho.render_critical_json(result))
        jsonschema.validate(document, ho.load_critical_experiment_schema())
        self.assertEqual(document["limit"]["resource"], "estimated_integer_digits")
        self.assertEqual(document["limit"]["measurement"], "unavailable")
        self.assertIsNone(document["limit"]["observed_or_estimated"])
        self.assertIn("LIMIT_REACHED", ho.render_critical_text(result))


class GeneratedIntegerBoundaryTests(unittest.TestCase):
    def test_readout_sums_accept_and_reject_adjacent_digit_counts(self):
        original_limit = sys.get_int_max_str_digits()
        for digits in (200, integer_text_limit() - 1):
            result = ho.analyze_model(triangle_readout(9 * 10 ** (digits - 1)))
            document = json.loads(ho.render_json(result))
            self.assertEqual(
                abs(document["homology"]["readout_matrix"]["data"][0][0]),
                27 * 10 ** (digits - 1),
            )
            jsonschema.validate(document, ho.load_analysis_schema())
            self.assertIn("COMPLETE", ho.render_text(result))
            self.assertIn("COMPLETE", ho.render_markdown(result))
        model = triangle_readout(9 * 10 ** (integer_text_limit() - 1))
        self.assertEqual(len(ho.normalized_model_sha256(model)), 64)
        with self.assertRaisesRegex(ValueError, "generated output integer.*limit"):
            ho.analyze_model(model)

        self.assertEqual(sys.get_int_max_str_digits(), original_limit)

    def test_lattice_basis_can_exceed_representable_readout_entries(self):
        q = 10 ** (integer_text_limit() // 2 + 1)
        model = ho.GraphModel.create(
            name="lattice-output-boundary",
            vertices=("o", "a", "b", "c", "d"),
            edges=(
                ("o", "a"),
                ("a", "b"),
                ("b", "o"),
                ("o", "c"),
                ("c", "d"),
                ("d", "o"),
            ),
            readouts=(
                ("x", {("a", "b"): q, ("c", "d"): 1}),
                ("y", {("a", "b"): 1, ("c", "d"): q}),
            ),
        )
        with self.assertRaisesRegex(ValueError, "generated output integer.*limit"):
            ho.analyze_model(model)

        critical_model = ho.CriticalModel.create(
            name=model.name,
            vertices=model.vertices,
            edges=model.edges,
            readouts=tuple((item.name, item.as_mapping()) for item in model.readouts),
            rates={edge: 1 for pair in model.edges for edge in (pair, pair[::-1])},
            layer=2,
            theta=1,
        )
        critical = ho.analyze_critical_model(critical_model)
        # This task exports quotient coordinates, not the large internal basis.
        self.assertEqual(critical.status, ho.CriticalStatus.COMPLETE)
        jsonschema.validate(
            json.loads(ho.render_critical_json(critical)),
            ho.load_critical_experiment_schema(),
        )

    def test_renderers_check_derived_finite_orders(self):
        result = ho.analyze_model(triangle_readout(1))
        q = 10 ** (integer_text_limit() // 2 + 1)
        layer = replace(
            result.filtration.layers[-1], exposure_graded=QuotientInvariants(0, (q, q))
        )
        result = replace(
            result,
            filtration=replace(
                result.filtration, layers=(*result.filtration.layers[:-1], layer)
            ),
        )
        for renderer in (
            ho.analysis_to_dict,
            ho.render_json,
            ho.render_text,
            ho.render_markdown,
        ):
            with self.assertRaisesRegex(ValueError, "generated output integer.*limit"):
                renderer(result)

    def test_supplied_documents_have_the_same_boundary(self):
        document = ho.analysis_to_dict(ho.analyze_model(triangle_readout(1)))
        document["homology"]["readout_matrix"]["data"][0][0] = (
            10 ** integer_text_limit()
        )
        for renderer in (ho.render_json, ho.render_text, ho.render_markdown):
            with self.assertRaisesRegex(ValueError, "generated output integer.*limit"):
                renderer(document)

    def test_cli_generated_overflow_is_a_controlled_error_in_both_formats(self):
        payload = ho.model_to_dict(
            triangle_readout(9 * 10 ** (integer_text_limit() - 1))
        )
        for output_format in ("json", "text"):
            process = run_cli("analyze", payload, output_format)
            self.assertEqual(process.returncode, 2)
            self.assertNotIn("Traceback", process.stderr)
            self.assertNotIn("COMPLETE", process.stdout)
            if output_format == "json":
                document = json.loads(process.stdout)
                jsonschema.validate(document, ho.load_error_schema())
                self.assertIn("generated output integer", document["message"])
            else:
                self.assertIn("generated output integer", process.stderr)


if __name__ == "__main__":
    unittest.main()
