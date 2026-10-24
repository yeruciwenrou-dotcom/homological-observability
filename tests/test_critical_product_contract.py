"""Public API, CLI, Schema, and resource tests for critical experiments."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest import mock

import homological_observability as ho
from homological_observability import cli

ROOT = Path(__file__).resolve().parents[1]


def cycle_payload(
    size: int,
    *,
    layer: int,
    theta: int | float | str = "1",
    audit_paths: bool = False,
    max_paths: int = 100_000,
) -> dict[str, object]:
    vertices = [f"v{index}" for index in range(size)]
    edges = [[vertices[index], vertices[(index + 1) % size]] for index in range(size)]
    directed = sorted(
        (start, end)
        for left, right in edges
        for start, end in ((left, right), (right, left))
    )
    return {
        "schema_version": 1,
        "name": f"c{size}-critical",
        "vertices": vertices,
        "edges": edges,
        "readouts": [],
        "rates": [{"edge": [start, end], "rate": "1"} for start, end in directed],
        "critical": {
            "layer": layer,
            "theta": theta,
            "limits": {
                "max_paths": max_paths,
                "max_estimated_integer_digits": 4096,
                "max_integer_digits": 4096,
                "max_output_records": 100_000,
                "max_cycles": 100_000,
            },
            "audit_paths": audit_paths,
        },
    }


class CriticalModelContractTests(unittest.TestCase):
    def test_json_decimals_are_parsed_as_exact_rationals(self) -> None:
        payload = cycle_payload(3, layer=2, theta=0.1)
        payload["rates"][0]["rate"] = 0.2
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "critical.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            model = ho.load_critical_model(path)

        self.assertEqual(model.theta, Fraction(1, 10))
        self.assertEqual(model.rates[0][1], Fraction(1, 5))
        normalized = ho.critical_model_to_dict(model)
        self.assertEqual(normalized["critical"]["theta"], "1/10")
        self.assertEqual(normalized["rates"][0]["rate"], "1/5")

    def test_python_api_rejects_binary_floats_and_incomplete_rates(self) -> None:
        payload = cycle_payload(3, layer=2)
        model = ho.parse_critical_model(payload)
        rates = dict(model.rates)
        rates[("v0", "v1")] = 0.5
        with self.assertRaisesRegex(TypeError, "exact string"):
            ho.CriticalModel.create(
                name="float-rate",
                vertices=model.graph.vertices,
                edges=model.graph.edges,
                rates=rates,
                layer=2,
                theta=1,
            )
        del rates[("v0", "v1")]
        with self.assertRaisesRegex(ValueError, "do not match the support"):
            ho.CriticalModel.create(
                name="missing-rate",
                vertices=model.graph.vertices,
                edges=model.graph.edges,
                rates=rates,
                layer=2,
                theta=Decimal("1"),
            )

    def test_model_schema_is_independent_of_the_topology_model_schema(self) -> None:
        model_schema = ho.load_model_schema()
        critical_schema = ho.load_critical_model_schema()
        self.assertEqual(
            model_schema["$id"], "urn:homological-observability:schema:model:2"
        )
        self.assertEqual(
            critical_schema["$id"],
            "urn:homological-observability:schema:critical-model:1",
        )
        self.assertNotIn("rates", model_schema["properties"])
        model = ho.parse_critical_model(cycle_payload(3, layer=2))
        document = ho.critical_model_to_dict(model)
        self.assertEqual(set(critical_schema["required"]), set(document))


class CriticalExperimentContractTests(unittest.TestCase):
    def test_c3_public_result_preserves_exact_mechanism_and_boundary(self) -> None:
        model = ho.parse_critical_model(cycle_payload(3, layer=2))
        result = ho.analyze_critical_model(model)
        document = ho.critical_experiment_to_dict(result)

        self.assertEqual(result.status, ho.CriticalStatus.COMPLETE)
        self.assertEqual(document["status"], "COMPLETE")
        self.assertEqual(document["summary"]["path_count"], 12)
        self.assertEqual(document["summary"]["common_total_intensity"], "1")
        self.assertEqual(document["summary"]["critical_total_intensity"], "0")
        self.assertEqual(
            sorted(
                atom["intensity"]
                for atom in document["limit_experiment"]["common_endpoint_component"][
                    "levy_measure"
                ]
            ),
            ["1/2", "1/2"],
        )
        self.assertTrue(document["limit_experiment"]["components_mutually_independent"])
        self.assertIn(
            "not an exact finite-(T, delta) posterior",
            document["limit_experiment"]["boundary_note"],
        )
        self.assertIsNone(document["catalogue"]["audit_paths"])
        self.assertIsNone(document["limit"])
        schema = ho.load_critical_experiment_schema()
        self.assertEqual(set(schema["required"]), set(document))

    def test_audit_mode_lists_every_length_m_walk(self) -> None:
        model = ho.parse_critical_model(cycle_payload(3, layer=2, audit_paths=True))
        document = ho.critical_experiment_to_dict(ho.analyze_critical_model(model))
        self.assertTrue(document["summary"]["audit_paths_included"])
        self.assertEqual(len(document["catalogue"]["audit_paths"]), 12)
        for path in document["catalogue"]["audit_paths"]:
            self.assertEqual(len(path["walk"]), 3)
            self.assertEqual(path["rate_product"], "1")
            self.assertEqual(path["leading_weight"], "1/2")

    def test_c4_retains_zero_marks_in_critical_endpoint_laws(self) -> None:
        model = ho.parse_critical_model(cycle_payload(4, layer=2))
        document = ho.critical_experiment_to_dict(ho.analyze_critical_model(model))
        endpoints = document["limit_experiment"]["critical_endpoint_components"]
        self.assertEqual(len(endpoints), 4)
        self.assertEqual(document["summary"]["common_total_intensity"], "0")
        self.assertEqual(document["summary"]["critical_total_intensity"], "1")
        for endpoint in endpoints:
            self.assertTrue(endpoint["zero_marks_retained"])
            self.assertEqual(
                sorted(
                    mark["probability"] for mark in endpoint["conditional_mark_law"]
                ),
                ["1/2", "1/2"],
            )

    def test_single_layer_completion_is_distinct_from_natural_filtration(self) -> None:
        model = ho.parse_critical_model(cycle_payload(5, layer=2))
        document = ho.critical_experiment_to_dict(ho.analyze_critical_model(model))
        self.assertEqual(document["status"], "COMPLETE")
        self.assertTrue(document["topology"]["requested_layer_complete"])
        self.assertFalse(document["topology"]["natural_filtration_complete"])
        self.assertFalse(document["summary"]["natural_filtration_complete"])
        self.assertTrue(document["summary"]["critical_catalogue_empty"])
        self.assertEqual(document["groups"]["graded"]["free_rank"], 0)
        self.assertEqual(document["groups"]["graded"]["finite_order"], 1)

    def test_resource_limit_is_atomic_and_machine_readable(self) -> None:
        model = ho.parse_critical_model(
            cycle_payload(3, layer=2, audit_paths=True, max_paths=6)
        )
        result = ho.analyze_critical_model(model)
        document = ho.critical_experiment_to_dict(result)

        self.assertEqual(result.status, ho.CriticalStatus.LIMIT_REACHED)
        self.assertFalse(result.is_complete)
        self.assertEqual(document["limit"]["resource"], "directed_paths")
        self.assertEqual(document["limit"]["observed_or_estimated"], 12)
        self.assertEqual(document["limit"]["measurement"], "exact")
        self.assertIsNone(document["groups"])
        self.assertIsNone(document["stationary_law"])
        self.assertIsNone(document["catalogue"])
        self.assertIsNone(document["limit_experiment"])

    def test_digit_output_and_cycle_limits_share_the_atomic_contract(self) -> None:
        base = ho.parse_critical_model(cycle_payload(3, layer=2))
        cases = (
            (
                "estimated_integer_digits",
                ho.CriticalLimits.create(max_estimated_integer_digits=1),
                Fraction(1),
                "preflight-estimate",
            ),
            (
                "integer_digits",
                ho.CriticalLimits.create(max_integer_digits=1),
                Fraction(1, 10),
                "exact",
            ),
            (
                "output_records",
                ho.CriticalLimits.create(max_output_records=1),
                Fraction(1),
                "exact",
            ),
        )
        for expected_resource, limits, theta, measurement in cases:
            with self.subTest(resource=expected_resource):
                model = ho.CriticalModel.create(
                    name=f"c3-{expected_resource}-limit",
                    vertices=base.graph.vertices,
                    edges=base.graph.edges,
                    rates=base.rate_mapping(),
                    layer=2,
                    theta=theta,
                    limits=limits,
                )
                document = ho.critical_experiment_to_dict(
                    ho.analyze_critical_model(model)
                )
                self.assertEqual(document["status"], "LIMIT_REACHED")
                self.assertEqual(document["limit"]["resource"], expected_resource)
                self.assertEqual(document["limit"]["measurement"], measurement)
                self.assertIsNone(document["catalogue"])
                self.assertIsNone(document["limit_experiment"])

        vertices = ("o", "a", "b", "c", "d", "e")
        edges = (
            ("o", "a"),
            ("a", "b"),
            ("b", "o"),
            ("o", "c"),
            ("c", "d"),
            ("d", "e"),
            ("e", "o"),
        )
        rates = {(start, end): 1 for edge in edges for start, end in (edge, edge[::-1])}
        cycle_limited = ho.CriticalModel.create(
            name="wedge-cycle-limit",
            vertices=vertices,
            edges=edges,
            rates=rates,
            layer=2,
            theta=1,
            limits=ho.CriticalLimits.create(max_cycles=1),
        )
        document = ho.critical_experiment_to_dict(
            ho.analyze_critical_model(cycle_limited)
        )
        self.assertEqual(document["status"], "LIMIT_REACHED")
        self.assertEqual(document["limit"]["resource"], "simple_cycles")
        self.assertIsNone(document["catalogue"])

    def test_exact_limits_do_not_inherit_preflight_rejections(
        self,
    ) -> None:
        base = ho.parse_critical_model(cycle_payload(5, layer=3))
        model = ho.CriticalModel.create(
            name="c5-exact-resource-limits",
            vertices=base.graph.vertices,
            edges=base.graph.edges,
            rates=base.rate_mapping(),
            layer=3,
            theta=1,
            limits=ho.CriticalLimits.create(
                max_integer_digits=5,
                max_output_records=50,
            ),
        )
        document = ho.critical_experiment_to_dict(ho.analyze_critical_model(model))

        self.assertEqual(document["status"], "COMPLETE")
        self.assertEqual(document["resources"]["usage"]["output_records"], 42)
        self.assertEqual(
            document["resources"]["usage"]["maximum_integer_digits"],
            2,
        )
        self.assertIsNone(document["limit"])

    def test_digit_budget_includes_readouts_marks_and_summary_intensities(self) -> None:
        vertices = ("o", "a", "b", "c", "d")
        edges = (("o", "a"), ("a", "b"), ("b", "o"), ("o", "c"), ("c", "d"), ("d", "o"))
        rates = {edge: 1 for pair in edges for edge in (pair, pair[::-1])}

        def build(digits, *, readouts=(), theta=1):
            return ho.analyze_critical_model(
                ho.CriticalModel.create(
                    name="wedge-c3-c3-digits",
                    vertices=vertices,
                    edges=edges,
                    rates=rates,
                    layer=2,
                    theta=theta,
                    readouts=readouts,
                    limits=ho.CriticalLimits.create(max_integer_digits=digits),
                    audit_paths=True,
                )
            )

        readouts = (("large-readout", {("o", "a"): 10**30, ("o", "c"): 1}),)
        complete = build(31, readouts=readouts)
        self.assertEqual(complete.status, ho.CriticalStatus.COMPLETE)
        self.assertEqual(complete.resource_usage.maximum_integer_digits, 31)
        self.assertTrue(
            any(
                abs(value) == 10**30
                for mark in complete.induced_readout.free_generator_images
                for value in mark.free
            )
        )
        for ceiling in (5, 30):
            limited = build(ceiling, readouts=readouts)
            self.assertEqual(limited.status, ho.CriticalStatus.LIMIT_REACHED)
            self.assertEqual(limited.limit.observed_or_estimated, 31)
            self.assertEqual(limited.limit.measurement, "exact")
            self.assertIsNone(limited.catalogue)
            self.assertIsNone(limited.induced_readout)

        complete = build(4, theta=999)
        self.assertEqual(complete.status, ho.CriticalStatus.COMPLETE)
        self.assertEqual(
            sum(atom.intensity for atom in complete.common_levy_measure),
            Fraction(5994, 5),
        )
        self.assertEqual(complete.resource_usage.maximum_integer_digits, 4)
        limited = build(3, theta=999)
        self.assertEqual(limited.status, ho.CriticalStatus.LIMIT_REACHED)
        self.assertEqual(limited.limit.observed_or_estimated, 4)
        self.assertIsNone(limited.common_levy_measure)

    def test_public_critical_experiment_preserves_a_finite_visible_quotient(
        self,
    ) -> None:
        base = ho.load_example("wedge-c3-c5")
        rates = {
            (start, end): 1 for edge in base.edges for start, end in (edge, edge[::-1])
        }
        readouts = tuple(
            (readout.name, dict(readout.coefficients)) for readout in base.readouts
        )
        model = ho.CriticalModel.create(
            name="wedge-c3-c5-critical",
            vertices=base.vertices,
            edges=base.edges,
            rates=rates,
            readouts=readouts,
            layer=3,
            theta=1,
        )
        document = ho.critical_experiment_to_dict(ho.analyze_critical_model(model))

        self.assertEqual(document["status"], "COMPLETE")
        self.assertEqual(document["groups"]["graded"]["free_rank"], 1)
        self.assertEqual(document["groups"]["visible"]["torsion_factors"], [2])
        self.assertEqual(document["groups"]["hidden_kernel"]["free_rank"], 1)
        self.assertEqual(
            document["groups"]["induced_readout"]["source_free_generator_images"],
            [{"torsion": [1], "free": []}],
        )
        self.assertEqual(
            {
                tuple(weight["visible_label"]["torsion"])
                for weight in document["catalogue"]["weights"]
            },
            {(0,), (1,)},
        )

    def test_cli_json_equals_the_public_api_and_uses_documented_exit_codes(
        self,
    ) -> None:
        payload = cycle_payload(3, layer=2, theta=0.5)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "critical.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homological_observability.cli",
                    "critical",
                    str(path),
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            api_document = ho.critical_experiment_to_dict(
                ho.analyze_critical_model(ho.load_critical_model(path))
            )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout), api_document)
        self.assertEqual(completed.stderr, "")

        limited = cycle_payload(3, layer=2, max_paths=1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "limited.json"
            path.write_text(json.dumps(limited), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homological_observability.cli",
                    "critical",
                    str(path),
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(json.loads(completed.stdout)["status"], "LIMIT_REACHED")
        self.assertNotIn("Traceback", completed.stderr)

    def test_cli_input_error_uses_the_existing_error_contract(self) -> None:
        payload = cycle_payload(3, layer=2)
        payload["rates"].pop()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homological_observability.cli",
                    "critical",
                    str(path),
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 2)
        document = json.loads(completed.stdout)
        self.assertEqual(document["status"], "ERROR")
        self.assertEqual(document["schema_name"], "homological-observability.error")
        self.assertEqual(document["schema_version"], 1)
        self.assertNotIn("Traceback", completed.stderr)

    def test_cli_internal_exactness_failure_is_controlled(self) -> None:
        model = ho.parse_critical_model(cycle_payload(3, layer=2))
        with (
            mock.patch.object(cli, "load_critical_model", return_value=model),
            mock.patch.object(
                cli,
                "analyze_critical_model",
                side_effect=AssertionError("normalization mismatch"),
            ),
        ):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli.main(["critical", "model.json", "--format", "json"])
        self.assertEqual(exit_code, 2)
        document = json.loads(stdout.getvalue())
        self.assertEqual(document["status"], "ERROR")
        self.assertIn("exactness check failed", document["message"])


if __name__ == "__main__":
    unittest.main()
