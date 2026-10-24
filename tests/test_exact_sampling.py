"""Sampling identity, critical boundaries, and exported-request replay."""

from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

import homological_observability as ho
from homological_observability.phase import predict_phase


def cycle(n, **settings):
    vertices = [str(i) for i in range(n)]
    return ho.GraphModel.create(
        name=f"C{n}",
        vertices=vertices,
        edges=[(vertices[i], vertices[(i + 1) % n]) for i in range(n)],
        **settings,
    )


class ExactSamplingTests(unittest.TestCase):
    def test_rational_critical_layers_and_both_sides(self):
        for n in (3, 5, 7, 9, 11):
            m = (n + 1) // 2
            critical = Fraction(1, m - 1)
            for reverse in (False, True):
                for alpha, expected in (
                    (critical, "CRITICAL"),
                    (critical - Fraction(1, 10**20), "DENSE"),
                    (critical + Fraction(1, 10**20), "SPARSE"),
                ):
                    with self.subTest(n=n, reverse=reverse, alpha=alpha):
                        result = ho.analyze_model(
                            cycle(n, alpha=alpha), reverse_tree_order=reverse
                        )
                        layer = result.phase.layers[-1]
                        self.assertIsInstance(result.model.alpha, Fraction)
                        self.assertEqual(layer.regime.value, expected)
                        self.assertEqual(layer.hidden_free_rank, 1)
                        exponent = 1 - alpha * (m - 1)
                        self.assertEqual(layer.scaling_exponent, float(exponent))
                        self.assertEqual(
                            layer.entropy_log_t_coefficient, float(max(exponent, 0) / 2)
                        )
                        direct = predict_phase(result.filtration, alpha=alpha)
                        self.assertEqual(direct, result.phase)

    def test_binary_floats_keep_their_actual_value(self):
        for n in (5, 7, 9, 11):
            m = (n + 1) // 2
            center = 1 / (m - 1)
            for alpha in (
                center,
                math.nextafter(center, 0),
                math.nextafter(center, math.inf),
            ):
                with self.subTest(n=n, alpha=alpha):
                    result = ho.analyze_model(cycle(n, alpha=alpha))
                    exponent = 1 - Fraction.from_float(alpha) * (m - 1)
                    expected = (
                        "CRITICAL"
                        if exponent == 0
                        else "DENSE"
                        if exponent > 0
                        else "SPARSE"
                    )
                    self.assertEqual(result.phase.layers[-1].regime.value, expected)
                    self.assertIsInstance(result.model.alpha, float)

    def test_normalization_and_distinct_numeric_identity(self):
        document = ho.model_to_dict(cycle(7))
        document["analysis"]["alpha"] = "2/6"
        model = ho.parse_model(document)
        normalized = ho.model_to_dict(model)
        self.assertEqual(normalized["analysis"]["alpha"], "1/3")
        self.assertEqual(ho.model_to_dict(ho.parse_model(normalized)), normalized)
        self.assertNotEqual(
            ho.normalized_model_sha256(model),
            ho.normalized_model_sha256(cycle(7, alpha=1 / 3)),
        )
        for text in ("0/9", "000/0009"):
            document["analysis"]["alpha"] = text
            self.assertEqual(
                ho.model_to_dict(ho.parse_model(document))["analysis"]["alpha"], "0/1"
            )
        direct = ho.GraphModel(
            name=model.name,
            vertices=model.vertices,
            edges=model.edges,
            alpha=Fraction(1, 3),
        )
        self.assertEqual(direct.alpha, Fraction(1, 3))

    def test_effective_request_replay_including_explicit_none_and_limits(self):
        source = ho.load_example("wedge-c3-c5")
        original = ho.model_to_dict(source)
        for overrides in (
            {"alpha": Fraction(1, 3)},
            {"alpha": None},
            {"observation_time": 100, "sampling_interval": 0.1},
        ):
            for limited in (False, True):
                document = copy.deepcopy(original)
                if limited:
                    document["analysis"]["max_cycles"] = 1
                model = ho.parse_model(document)
                for reverse in (False, True):
                    result = ho.analyze_model(
                        model, reverse_tree_order=reverse, **overrides
                    )
                    saved = ho.analysis_to_dict(result)
                    replay = ho.analysis_to_dict(
                        ho.analyze_model(
                            ho.parse_model(saved["model"]), reverse_tree_order=reverse
                        )
                    )
                    self.assertEqual(saved, replay)
                    self.assertEqual(ho.model_to_dict(model), document)
                    if limited:
                        self.assertEqual(saved["status"], "LIMIT_REACHED")
        finite = cycle(7, observation_time=100, sampling_interval=0.1)
        self.assertEqual(
            ho.analyze_model(finite, alpha=Fraction(1, 3)).phase.alpha, Fraction(1, 3)
        )
        self.assertEqual(ho.model_to_dict(source), original)

    def test_invalid_and_bounded_values(self):
        document = ho.model_to_dict(cycle(7))
        for value in (
            "-1/3",
            "1/-3",
            "1/0",
            "1.0/3",
            "0.3",
            "1 /3",
            "1/3\n",
            "1e2/3",
            "1/" + "9" * 4301,
            True,
            float("nan"),
            float("inf"),
            -1,
        ):
            with (
                self.subTest(value=str(value)[:30]),
                self.assertRaises((TypeError, ValueError)),
            ):
                document["analysis"]["alpha"] = value
                ho.parse_model(document)
        for value in (Fraction(-1, 3), Fraction(10**4300, 1), Fraction(1, 10**4300)):
            with self.assertRaises(ValueError):
                cycle(7, alpha=value)
        with self.assertRaises(ValueError):
            ho.analyze_model(cycle(7, alpha=Fraction(1, 3) + Fraction(1, 10**400)))
        with self.assertRaises(ValueError):
            cycle(7, alpha=Fraction(1, 3), observation_time=1, sampling_interval=0.1)

    def test_versioned_schemas_and_legacy_inputs(self):
        old = ho.model_to_dict(cycle(7, alpha=1 / 3))
        old["schema_version"] = 1
        Draft202012Validator(ho.load_model_schema(version=1)).validate(old)
        normalized = ho.model_to_dict(ho.parse_model(old))
        self.assertEqual(normalized["schema_version"], 2)
        old["analysis"]["alpha"] = "1/3"
        with self.assertRaises(ValueError):
            ho.parse_model(old)
        with self.assertRaises(ValidationError):
            Draft202012Validator(ho.load_model_schema(version=1)).validate(old)
        for loader, previous, latest in (
            (ho.load_model_schema, 1, 2),
            (ho.load_study_schema, 1, 2),
            (ho.load_analysis_schema, 2, 3),
            (ho.load_comparison_schema, 1, 2),
        ):
            for version in (previous, latest):
                schema = loader(version=version)
                Draft202012Validator.check_schema(schema)
                self.assertEqual(
                    schema["properties"]["schema_version"]["const"], version
                )
            for version in (True, 99, "1"):
                with self.assertRaises(ValueError):
                    loader(version=version)

    def test_cli_bundle_and_individual_replay(self):
        study = ho.load_study_example("bridge")
        study["analysis"]["alpha"] = "2/6"
        for reverse in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "study.json"
                source.write_text(json.dumps(study), encoding="utf-8")
                prefix = [sys.executable, "-m", "homological_observability.cli"]
                flag = ["--reverse-tree-order"] if reverse else []
                command = subprocess.run(
                    prefix
                    + [
                        "compare",
                        str(source),
                        "--output-dir",
                        str(root / "first"),
                        "--format",
                        "json",
                    ]
                    + flag,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                result = json.loads(command.stdout)
                Draft202012Validator(ho.load_comparison_schema()).validate(result)
                self.assertEqual(result["study"]["analysis"]["alpha"], "1/3")
                subprocess.run(
                    prefix
                    + [
                        "compare",
                        str(root / "first/study.json"),
                        "--output-dir",
                        str(root / "second"),
                        "--format",
                        "json",
                    ]
                    + flag,
                    check=True,
                    capture_output=True,
                )
                self.assertEqual(
                    (root / "first/comparison.json").read_bytes(),
                    (root / "second/comparison.json").read_bytes(),
                )
                command = subprocess.run(
                    prefix
                    + [
                        "analyze",
                        str(root / "first/models/config-mixed.json"),
                        "--format",
                        "json",
                    ]
                    + flag,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(json.loads(command.stdout), result["results"]["mixed"])
