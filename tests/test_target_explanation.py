"""Target-image ranks cross-checked with independent existing hidden analyses."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator, ValidationError

import homological_observability as ho
from homological_observability import cli
from homological_observability.applications._dfr_data import dfr_model
from homological_observability.filtration import exposure_filtration
from homological_observability.homology import build_homology_basis


class TargetExplanationTests(unittest.TestCase):
    def test_target_image_entropy_matches_hidden_difference_across_models(self):
        models = [dfr_model(s)[0] for s in ("snapshots", "w", "w-on")]
        models += [ho.load_example("wedge-c3-c5")]
        for model in models:
            basis = build_homology_basis(model)
            targets = (
                ho.IntegerReadout.from_mapping(
                    "F", {edge: i + 1 for i, edge in enumerate(basis.chord_edges)}
                ),
            )
            for alpha in (
                Fraction(0),
                Fraction(1, 4),
                Fraction(1, 2),
                Fraction(1),
                Fraction(2),
            ):
                model = replace(
                    model,
                    alpha=alpha,
                    observation_time=None,
                    sampling_interval=None,
                    max_layer=None,
                )
                document = ho.analyze_target(model, targets, explain=True)
                explanation = document["explanation"]
                self.assertEqual(document["explanation_status"], "COMPLETE")
                before = ho.analyze_model(model).phase.entropy_log_t_coefficient
                after = ho.analyze_model(
                    replace(model, readouts=(*model.readouts, *targets))
                ).phase.entropy_log_t_coefficient
                self.assertAlmostEqual(
                    float(Fraction(explanation["target_entropy_log_t_coefficient"])),
                    before - after,
                )
                self.assertTrue(
                    all(
                        layer["graded_target_rank"] >= 0
                        for layer in explanation["layers"]
                    )
                )
                reversed_document = ho.analyze_target(
                    model, targets, explain=True, reverse_tree_order=True
                )
                self.assertEqual(explanation, reversed_document["explanation"])

    def test_pure_endpoint_target_has_zero_image_at_every_layer(self):
        model, _ = dfr_model("snapshots")
        target = ho.IntegerReadout.from_mapping(
            "gradient", {(u, v): int(v) - int(u) for u, v in model.edges}
        )
        result = ho.analyze_target(
            replace(model, alpha=Fraction(1, 4)), [target], explain=True
        )
        self.assertTrue(result["result"]["sufficient"])
        self.assertEqual(result["explanation"]["target_entropy_log_t_coefficient"], "0")

    def test_partial_horizon_does_not_claim_global_entropy(self):
        model = ho.load_example("wedge-c3-c5")
        targets = (
            ho.IntegerReadout.from_mapping(
                "F", {e: 1 for e in build_homology_basis(model).chord_edges}
            ),
        )
        result = ho.analyze_target(
            replace(model, max_layer=2, alpha=Fraction(1, 4)), targets, explain=True
        )
        self.assertEqual(result["explanation_status"], "PARTIAL_HORIZON")
        self.assertIsNone(result["explanation"]["target_entropy_log_t_coefficient"])
        self.assertIsNotNone(result["explanation"]["prefix_entropy_log_t_coefficient"])
        self.assertTrue(result["result"]["certificate_complete"])
        report = ho.render_target_text(result)
        self.assertIn("Computed-prefix entropy", report)
        self.assertIn("later layers remain open", report)
        self.assertNotIn("Target entropy log(T) coefficient", report)

    def test_explanation_limits_preserve_core_certificates(self):
        model, targets = dfr_model("w-on")
        core = ho.analyze_target(model, targets)
        for limited, limits in (
            (replace(model, max_cycles=1), None),
            (model, ho.TargetLimits(max_explanation_cycles=1)),
            (replace(model, max_layer=1000000), None),
        ):
            result = ho.analyze_target(limited, targets, limits=limits, explain=True)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["result"], core["result"])
            self.assertEqual(result["explanation_status"], "LIMIT_REACHED")
        unavailable = ho.analyze_target(
            model, targets, limits=ho.TargetLimits(max_matrix_entries=1), explain=True
        )
        self.assertEqual(unavailable["explanation_status"], "UNAVAILABLE")

    def test_finite_scales_are_distinct_from_asymptotic_coefficients(self):
        model, targets = dfr_model("w")
        result = ho.analyze_target(
            replace(model, observation_time=2.5, sampling_interval=0.125),
            targets,
            explain=True,
        )
        layers = result["explanation"]["layers"]
        self.assertEqual(layers[2]["finite_exposure_scale"], "5/16")
        self.assertIsNone(result["explanation"]["target_entropy_log_t_coefficient"])

    def test_generator_matrix_budget_precedes_allocation(self):
        vertices = tuple(str(i) for i in range(6))
        model = ho.GraphModel("K6", vertices, tuple(combinations(vertices, 2)))
        targets = (ho.IntegerReadout.from_mapping("F", {("0", "1"): 1}),)
        core = ho.analyze_target(model, targets)
        validator = Draft202012Validator(ho.load_target_task_schema())
        for maximum in (400, 1969):
            with self.subTest(max_matrix_entries=maximum):
                with mock.patch(
                    "homological_observability.filtration.cycle_coordinates",
                    side_effect=AssertionError(
                        "cycle coordinates allocated over budget"
                    ),
                ):
                    result = ho.analyze_target(
                        model,
                        targets,
                        limits=ho.TargetLimits(max_matrix_entries=maximum),
                        explain=True,
                    )
                self.assertEqual(result["status"], "COMPLETE")
                self.assertEqual(result["result"], core["result"])
                self.assertEqual(result["explanation_status"], "LIMIT_REACHED")
                self.assertEqual(
                    result["explanation"]["limit"], {"resource": "matrix_entries"}
                )
                validator.validate(result)

        baseline = ho.analyze_target(model, targets, explain=True)
        for maximum in (1970, 2000):
            result = ho.analyze_target(
                model,
                targets,
                limits=ho.TargetLimits(max_matrix_entries=maximum),
                explain=True,
            )
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["explanation_status"], "COMPLETE")
            self.assertEqual(result["result"], core["result"])
            self.assertEqual(result["explanation"], baseline["explanation"])

        cycles, lattices = exposure_filtration(build_homology_basis(model))
        self.assertEqual(len(cycles), 197)
        self.assertEqual(lattices[-1].shape, (10, 10))

    def test_matrix_limited_explanation_replays_with_incomplete_cli_exit(self):
        vertices = tuple(str(i) for i in range(6))
        model = ho.GraphModel("K6", vertices, tuple(combinations(vertices, 2)))
        targets = (ho.IntegerReadout.from_mapping("F", {("0", "1"): 1}),)
        limits = ho.TargetLimits(max_matrix_entries=400)
        core = ho.design_readouts(model, targets, targets, limits=limits)
        result = ho.design_readouts(
            model, targets, targets, limits=limits, explain=True
        )
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["result"], core["result"])
        self.assertEqual(result["explanation_status"], "LIMIT_REACHED")
        self.assertEqual(ho.run_target_request(result["request"]), result)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "request.json"
            path.write_text(json.dumps(result["request"]), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(["design", str(path), "--format", "json"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout.getvalue()), result)

    def test_schema_replay_and_cli_partial_exit(self):
        model, targets = dfr_model("w")
        documents = [
            ho.analyze_target(model, targets),
            ho.analyze_target(model, targets, explain=True),
            ho.analyze_target(replace(model, max_layer=1), targets, explain=True),
            ho.analyze_target(
                model,
                targets,
                explain=True,
                limits=ho.TargetLimits(max_explanation_cycles=1),
            ),
            ho.analyze_target(
                model,
                targets,
                explain=True,
                limits=ho.TargetLimits(max_matrix_entries=1),
            ),
        ]
        validator = Draft202012Validator(ho.load_target_task_schema())
        for document in documents:
            validator.validate(document)
            Draft202012Validator(ho.load_target_request_schema()).validate(
                document["request"]
            )
            self.assertEqual(ho.run_target_request(document["request"]), document)
        forged = copy.deepcopy(documents[2])
        forged["explanation"]["target_entropy_log_t_coefficient"] = "1"
        with self.assertRaises(ValidationError):
            validator.validate(forged)
        with (
            tempfile.TemporaryDirectory() as temporary,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            path = Path(temporary) / "request.json"
            path.write_text(json.dumps(documents[3]["request"]))
            self.assertEqual(cli.main(["target", str(path)]), 1)
        with self.assertRaises(TypeError):
            ho.analyze_target(model, targets, explain=1)


if __name__ == "__main__":
    unittest.main()
