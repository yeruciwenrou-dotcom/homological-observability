"""Regression checks for shared cochain serialization and embedded model versions."""

import copy
import unittest
from dataclasses import replace

from jsonschema import Draft202012Validator

import homological_observability as ho


class TargetReplayTests(unittest.TestCase):
    def setUp(self):
        self.model = ho.GraphModel.create(
            name="triangle", vertices="abc", edges=[("a", "b"), ("b", "c"), ("c", "a")]
        )
        self.zero = ho.IntegerReadout("zero", ((("a", "b"), 0),))
        self.turn = ho.IntegerReadout("turn", ((("a", "b"), 0), (("a", "c"), -1)))

    def test_direct_model_target_and_candidate_replay(self):
        model = replace(self.model, readouts=(self.zero,))
        operations = [
            ho.analyze_target(model, [self.turn]),
            ho.evaluate_target(model, [self.zero], {"zero": 0}, start="a", end="a"),
            ho.design_readouts(model, [self.turn], [self.turn]),
        ]
        for doc in operations:
            with self.subTest(operation=doc["operation"]):
                replay = ho.run_target_request(doc["request"])
                self.assertEqual(doc["result"], replay["result"])
                self.assertEqual(doc["request_sha256"], replay["request_sha256"])
        self.assertEqual(ho.model_to_dict(model)["readouts"][0]["coefficients"], [])
        canonical = replace(
            model, readouts=(ho.IntegerReadout.from_mapping("zero", {}),)
        )
        self.assertEqual(
            ho.normalized_model_sha256(model), ho.normalized_model_sha256(canonical)
        )

    def test_alpha_schema_agrees_with_runtime_for_both_model_versions(self):
        doc = ho.analyze_target(self.model, [self.turn])
        request_validator = Draft202012Validator(ho.load_target_request_schema())
        result_validator = Draft202012Validator(ho.load_target_task_schema())
        for version in (1, 2):
            for alpha in (0.5, "1/3"):
                sample = copy.deepcopy(doc)
                model = sample["request"]["model"]
                model.update(schema_version=version, analysis={"alpha": alpha})
                expected = version == 2 or isinstance(alpha, float)
                with self.subTest(version=version, alpha=alpha):
                    self.assertEqual(
                        request_validator.is_valid(sample["request"]), expected
                    )
                    self.assertEqual(result_validator.is_valid(sample), expected)
                    if expected:
                        ho.run_target_request(sample["request"])
                    else:
                        with self.assertRaises((ValueError, TypeError)):
                            ho.run_target_request(sample["request"])
