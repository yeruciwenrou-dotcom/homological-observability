"""Scientific contracts: generator law, paired views, prediction replay and leakage."""

import contextlib
import copy
import hashlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.linalg import expm

from homological_observability.applications import dfr
from homological_observability.applications._dfr_data import (
    SCHEMES,
    dfr_model,
    digest,
    json_bytes,
    observe_path,
    rate_matrix,
    simulate_path,
    stationary_distribution,
)


class DFRDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = dfr.load_dataset()

    def test_rate_source_support_and_stationary_initial_law(self):
        q = rate_matrix()
        self.assertEqual(q[0, 2], math.exp(-1))
        self.assertEqual(q[2, 0], math.exp(1))
        self.assertEqual(q[1, 4], 1)
        self.assertEqual(q[1, 5], 0)
        np.testing.assert_allclose(q.sum(axis=1), 0, atol=1e-15)
        model, _ = dfr_model()
        support = {(str(i), str(j)) for i in range(6) for j in range(6) if q[i, j] > 0}
        self.assertEqual(support, set(model.edges) | {e[::-1] for e in model.edges})
        probability = stationary_distribution(q)
        np.testing.assert_allclose(probability @ q, 0, atol=1e-15)
        self.assertTrue(np.all(probability > 0))

    def test_direct_sampler_against_independent_two_state_transition_law(self):
        q = np.array([[-2.0, 2.0], [3.0, -3.0]])
        rng = np.random.Generator(np.random.PCG64(551))
        paths = [simulate_path(q, [1.0, 0.0], 0.4, rng) for _ in range(5000)]
        final_one = sum(p["states"][-1] == "1" for p in paths) / len(paths)
        no_jump = sum(len(p["states"]) == 1 for p in paths) / len(paths)
        self.assertAlmostEqual(final_one, expm(0.4 * q)[0, 1], delta=0.03)
        self.assertAlmostEqual(no_jump, math.exp(-0.8), delta=0.03)

    def test_seed_reproducibility_and_whole_trajectory_pairing(self):
        with tempfile.TemporaryDirectory() as temporary:
            a, b = (Path(temporary) / name for name in ("a", "b"))
            dfr.generate_dataset(a, trajectories=12, seed=9)
            dfr.generate_dataset(b, trajectories=12, seed=9)
            self.assertEqual(
                {p.name: p.read_bytes() for p in a.iterdir()},
                {p.name: p.read_bytes() for p in b.iterdir()},
            )
            dataset = dfr.load_dataset(a)
        ids = dataset["manifest"]["split_ids"]
        self.assertFalse(set(ids["train"]) & set(ids["test"]))
        self.assertFalse(set(ids["validation"]) & set(ids["test"]))
        base = dataset["files"]["natural-inputs-snapshots.json"]["rows"]
        for scheme in SCHEMES:
            rows = dataset["files"][f"natural-inputs-{scheme}.json"]["rows"]
            self.assertEqual(
                [(r["trajectory_id"], r["split"], r["snapshots"]) for r in rows],
                [(r["trajectory_id"], r["split"], r["snapshots"]) for r in base],
            )

    def test_full_grid_pressure_and_separate_truth_features(self):
        data = self.dataset
        for scheme in ("snapshots", "w"):
            view = dfr.feature_view(data, scheme, cohort="pressure", split="pressure")
            np.testing.assert_array_equal(view["X"][0], view["X"][1])
            self.assertEqual(view["X"].shape, (2, 50 + len(SCHEMES[scheme])))
            self.assertFalse(
                {"times", "DeltaW", "trajectory_id", "event_count"}
                & set(view["columns"])
            )
        richer = dfr.feature_view(data, "w-on", cohort="pressure", split="pressure")[
            "X"
        ]
        self.assertFalse(np.array_equal(richer[0], richer[1]))
        self.assertEqual(
            [r["DeltaW"] for r in data["files"]["pressure-labels.json"]["rows"]], [0, 2]
        )

    def test_zero_jump_paths_and_right_continuous_snapshots(self):
        model, _ = dfr_model("w")
        self.assertEqual(
            observe_path({"times": [0.0], "states": ["0"]}, [0.0, 0.5, 1.0], model),
            {"snapshots": ["0"] * 3, "readouts": {"W": 0}},
        )
        self.assertEqual(
            observe_path(
                {"times": [0.0, 0.5], "states": ["0", "1"]}, [0.0, 0.5, 1.0], model
            )["snapshots"],
            ["0", "1", "1"],
        )
        for path in (
            {"times": [], "states": []},
            {"times": [0.0], "states": ["9"]},
            {"times": [0.0, 0.1], "states": ["0", "4"]},
            {"times": [0.0, 0.1], "states": ["0", "0"]},
            {"times": [0.0, True], "states": ["0", "1"]},
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                observe_path(path, [0.0, 1.0], model)

    def test_dataset_rejects_hash_and_type_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "data"
            dfr.generate_dataset(path, trajectories=10)
            label_path = path / "pressure-labels.json"
            labels = json.loads(label_path.read_bytes())
            labels["rows"][0]["DeltaW"] = False
            label_path.write_bytes(json_bytes(labels))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                dfr.load_dataset(path)
            manifest_path = path / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["files"][label_path.name] = hashlib.sha256(
                label_path.read_bytes()
            ).hexdigest()
            manifest.pop("dataset_id")
            manifest["dataset_id"] = digest(manifest)
            manifest_path.write_bytes(json_bytes(manifest))
            with self.assertRaisesRegex(ValueError, "alignment mismatch"):
                dfr.load_dataset(path)
            manifest_path.write_bytes(b"{}")
            with self.assertRaises(ValueError):
                dfr.load_dataset(path)

    def test_case_reconstruction_and_minimal_additions(self):
        result = dfr.run_case(self.dataset)
        self.assertEqual(result["design"]["result"]["minimum_added"], 1)
        self.assertEqual(
            {tuple(s["added_ids"]) for s in result["design"]["result"]["solutions"]},
            {("W_ON",), ("W_OFF",)},
        )
        for scheme in ("w-on", "all"):
            self.assertEqual(result["paired_reconstruction"][scheme]["count"], 64)
            self.assertEqual(result["paired_reconstruction"][scheme]["mismatches"], 0)
            self.assertEqual(result["audits"][scheme]["explanation_status"], "COMPLETE")
        self.assertFalse(result["audits"]["w"]["result"]["sufficient"])


class DFRPredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = dfr.load_dataset()

    def pressure(self, values, **kwargs):
        return dfr.make_predictions(
            self.dataset, values, split="pressure", cohort="pressure", **kwargs
        )

    def test_identity_and_complete_alignment_validation(self):
        base = self.pressure([0, 0])
        for field, value in {
            "protocol_version": True,
            "dataset_id": "other",
            "task_id": "other",
            "target_name": "W",
            "scheme_id": "w-on",
            "cohort": "natural",
            "split": "train",
            "semantics": "unknown",
            "rounding": "floor",
        }.items():
            document = {**base, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                dfr.evaluate_predictions(self.dataset, document)
        for rows in (
            base["predictions"][:1],
            base["predictions"] + [base["predictions"][0]],
            [base["predictions"][0], {"trajectory_id": "other", "value": 0}],
        ):
            with self.assertRaises(ValueError):
                dfr.evaluate_predictions(self.dataset, {**base, "predictions": rows})
        reverse = {**base, "predictions": base["predictions"][::-1]}
        self.assertEqual(
            dfr.evaluate_predictions(self.dataset, base),
            dfr.evaluate_predictions(self.dataset, reverse),
        )

    def test_finite_numeric_values_and_integer_semantics(self):
        for value in (True, None, float("nan"), float("inf"), "0", 10**400):
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                self.pressure([value, 0])
        with self.assertRaises(ValueError):
            self.pressure([0.5, 0.5], semantics="integer_realized")
        self.pressure([1.0, 1.0], semantics="integer_realized")
        self.pressure(np.array([1.0, 1.0]))

    def test_no_silent_rounding_and_conditional_mean_off_lattice(self):
        raw = dfr.evaluate_predictions(self.dataset, self.pressure([0.6, 0.6]))
        self.assertIsNone(raw["postprocessed"])
        self.assertEqual([r["prediction"] for r in raw["records"]], [0.6, 0.6])
        rounded = dfr.evaluate_predictions(
            self.dataset, self.pressure([0.6, 0.6], rounding="nearest_even")
        )
        self.assertEqual(
            [r["postprocessed_prediction"] for r in rounded["records"]], [1, 1]
        )
        self.assertEqual(rounded["raw"], raw["raw"])
        mean = dfr.evaluate_predictions(
            self.dataset, self.pressure([1, 1], semantics="conditional_mean")
        )
        self.assertIsNone(mean["raw"]["exact_match_accuracy"])
        self.assertEqual(mean["raw"]["mae"], 1)
        self.assertTrue(mean["pressure_bound"]["applicable_to_submitted_point_values"])

    def test_pressure_bound_applies_to_same_visible_input_function(self):
        constant = dfr.evaluate_predictions(self.dataset, self.pressure([0, 0]))
        self.assertEqual(constant["raw"]["mae"], 1)
        self.assertEqual(constant["raw"]["exact_match_accuracy"], 0.5)
        leaked = dfr.evaluate_predictions(self.dataset, self.pressure([0, 2]))
        self.assertEqual(leaked["raw"]["mae"], 0)
        self.assertFalse(leaked["identical_visible_input_consistency"])
        self.assertFalse(
            leaked["pressure_bound"]["applicable_to_submitted_point_values"]
        )
        rich = dfr.evaluate_predictions(
            self.dataset, self.pressure([0, 2], scheme="w-on")
        )
        self.assertEqual(rich["exact_reconstruction"]["mae"], 0)
        self.assertIsNone(rich["pressure_bound"])

    def test_constant_fit_uses_only_training_labels(self):
        data = copy.deepcopy(self.dataset)
        before = dfr.constant_predictions(data)
        for row in data["files"]["natural-labels.json"]["rows"]:
            if row["split"] != "train":
                row["DeltaW"] = 999
        self.assertEqual(before, dfr.constant_predictions(data))
        evaluation = dfr.evaluate_predictions(self.dataset, before)
        self.assertIsNone(evaluation["pressure_bound"])
        self.assertEqual(evaluation["raw"]["count"], 13)
        self.assertEqual(sum(evaluation["label_distribution"].values()), 13)
        self.assertEqual(
            evaluation["training_median_baseline"]["fit_split"], "natural/train"
        )

    def test_application_cli_prediction_replay(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            directory = Path(temporary)
            self.assertEqual(
                dfr.main(
                    [
                        "generate",
                        "--output-dir",
                        str(directory / "data"),
                        "--trajectories",
                        "10",
                    ]
                ),
                0,
            )
            self.assertEqual(
                dfr.main(
                    [
                        "run",
                        "--dataset",
                        str(directory / "data"),
                        "--output-dir",
                        str(directory / "case"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                dfr.main(
                    [
                        "evaluate",
                        str(directory / "case/predictions.json"),
                        "--dataset",
                        str(directory / "data"),
                        "--output",
                        str(directory / "evaluation.json"),
                    ]
                ),
                0,
            )
            case = json.loads((directory / "case/case.json").read_bytes())
            evaluation = json.loads((directory / "evaluation.json").read_bytes())
            self.assertEqual(evaluation, case["natural_prediction_evaluation"])
            with (
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                dfr.main(
                    [
                        "run",
                        "--dataset",
                        str(directory / "data"),
                        "--output-dir",
                        str(directory / "case"),
                    ]
                )
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
