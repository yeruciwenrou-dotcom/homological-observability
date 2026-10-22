"""Reader-facing contracts for shared configuration studies and replay bundles."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

import homological_observability as ho

ROOT = Path(__file__).resolve().parents[1]


def study_document() -> dict:
    """Two rings share a vertex; their first exposure layers are 2 and 3."""
    return {
        "schema_version": 1,
        "name": "Pump and return paths",
        "question": "What is retained by one exact cumulative counter?",
        "model": {
            "schema_version": 1,
            "name": "two-path-circuits",
            "vertices": ["o", "a1", "a2", "b1", "b2", "b3", "b4"],
            "edges": [
                ["o", "a1"],
                ["a1", "a2"],
                ["a2", "o"],
                ["o", "b1"],
                ["b1", "b2"],
                ["b2", "b3"],
                ["b3", "b4"],
                ["b4", "o"],
            ],
        },
        "analysis": {"alpha": 0.375, "max_cycles": 100},
        "configurations": [
            {"id": "none", "label": "Snapshots only", "readouts": []},
            {
                "id": "pump",
                "label": "Pump counter",
                "readouts": [
                    {
                        "name": "pump",
                        "coefficients": [{"edge": ["o", "a1"], "coefficient": 1}],
                    }
                ],
            },
            {
                "id": "return",
                "label": "Return counter",
                "readouts": [
                    {
                        "name": "return",
                        "coefficients": [{"edge": ["o", "b1"], "coefficient": 1}],
                    }
                ],
            },
        ],
    }


class ComparisonContractTests(unittest.TestCase):
    def run_cli(self, *arguments: str, cwd: Path | None = None):
        environment = dict(os.environ)
        # Keep the same package under test while changing the reader's directory.
        environment["PYTHONPATH"] = str(Path(ho.__file__).resolve().parent.parent)
        return subprocess.run(
            [sys.executable, "-m", "homological_observability.cli", *arguments],
            cwd=cwd or ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def validate_comparison(self, result: dict) -> None:
        schema = ho.load_comparison_schema()
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(result)
        validator = Draft202012Validator(ho.load_analysis_schema())
        for raw_result in result["results"].values():
            validator.validate(raw_result)

    def test_public_schemas_validate_authored_studies_and_fresh_results(self):
        study_schema = ho.load_study_schema()
        Draft202012Validator.check_schema(study_schema)
        Draft202012Validator(study_schema).validate(study_document())
        result = ho.compare_configurations(study_document())
        self.validate_comparison(result)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(
            [row["id"] for row in result["rows"]], ["none", "pump", "return"]
        )
        self.assertEqual(result["rows"][0]["first_hidden_layer"], 2)
        self.assertEqual(result["rows"][1]["first_hidden_layer"], 3)
        self.assertEqual(result["producer"]["version"], ho.__version__)
        self.assertRegex(result["producer"]["code_sha256"], r"^[0-9a-f]{64}$")

    def test_normalization_is_deterministic_and_does_not_mutate_input(self):
        study = study_document()
        original = copy.deepcopy(study)
        first = ho.compare_configurations(study)
        second = ho.compare_configurations(ho.parse_study(study))
        self.assertEqual(study, original)
        self.assertEqual(first, second)
        self.assertEqual(len(first["study_sha256"]), 64)
        changed = copy.deepcopy(study)
        changed["analysis"]["alpha"] = 0.5
        self.assertNotEqual(
            first["study_sha256"], ho.compare_configurations(changed)["study_sha256"]
        )

    def test_shared_conditions_cannot_be_overridden_per_candidate(self):
        for location, field, value in (
            ("model", "readouts", []),
            ("model", "analysis", {}),
            ("configuration", "analysis", {"alpha": 0.5}),
            ("configuration", "model", {}),
        ):
            with self.subTest(location=location, field=field):
                invalid = study_document()
                target = (
                    invalid["model"]
                    if location == "model"
                    else invalid["configurations"][0]
                )
                target[field] = value
                with self.assertRaises((TypeError, ValueError)):
                    ho.parse_study(invalid)

    def test_unsafe_or_duplicate_identifiers_and_excess_candidates_are_rejected(self):
        for identifier in ("../escape", "UPPER", "x/y", "x" * 65):
            invalid = study_document()
            invalid["configurations"][0]["id"] = identifier
            with self.subTest(identifier=identifier):
                with self.assertRaises((TypeError, ValueError)):
                    ho.parse_study(invalid)
        invalid = study_document()
        invalid["configurations"][1]["id"] = "none"
        with self.assertRaises(ValueError):
            ho.parse_study(invalid)
        invalid["configurations"] = [
            {"id": f"candidate-{index}", "readouts": []} for index in range(65)
        ]
        with self.assertRaises(ValueError):
            ho.parse_study(invalid)

    def test_invalid_candidate_is_retained_and_later_candidates_still_run(self):
        for bad_readouts in (
            "wrong container",
            [
                {
                    "name": "invalid",
                    "coefficients": [{"edge": ["o", "a1"], "coefficient": 1.25}],
                }
            ],
        ):
            with self.subTest(readouts=bad_readouts):
                study = study_document()
                study["configurations"][0]["readouts"] = bad_readouts
                result = ho.compare_configurations(study)
                self.validate_comparison(result)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(result["rows"][0]["status"], "ERROR")
                self.assertEqual(result["rows"][1]["status"], "COMPLETE")
                self.assertEqual(
                    result["study"]["configurations"][0]["readouts"], bad_readouts
                )
                self.assertTrue(result["rows"][0]["error"])
                self.assertTrue(result["rows"][0]["recovery"])
                self.assertTrue(
                    all(
                        relation["relation"] == "UNAVAILABLE"
                        for relation in result["relations"]
                        if relation["left"] == "none" or relation["right"] == "none"
                    )
                )

    def test_partial_and_resource_limits_have_distinct_machine_contracts(self):
        study = study_document()
        study["analysis"]["max_layer"] = 2
        partial = ho.compare_configurations(study)
        self.validate_comparison(partial)
        self.assertEqual(partial["status"], "INCOMPLETE")
        self.assertTrue(
            all(row["status"] == "PARTIAL_HORIZON" for row in partial["rows"])
        )
        self.assertTrue(
            all(
                relation["scope"] == "COMPUTED_EXPOSURE"
                for relation in partial["relations"]
            )
        )
        self.assertEqual(partial["rows"][1]["computed_hidden_rank"], 0)
        self.assertFalse(partial["rows"][1]["natural_complete"])
        study["analysis"].pop("max_layer")
        study["analysis"]["max_cycles"] = 1
        limited = ho.compare_configurations(study)
        self.validate_comparison(limited)
        self.assertEqual(limited["status"], "INCOMPLETE")
        self.assertTrue(
            all(row["status"] == "LIMIT_REACHED" for row in limited["rows"])
        )
        self.assertTrue(
            all(row["computed_hidden_rank"] is None for row in limited["rows"])
        )
        self.assertTrue(
            all(
                relation["relation"] == "UNAVAILABLE"
                for relation in limited["relations"]
            )
        )
        false_complete = copy.deepcopy(limited)
        false_complete["status"] = "COMPLETE"
        self.assertFalse(
            Draft202012Validator(ho.load_comparison_schema()).is_valid(false_complete)
        )

    def test_schema_rejects_false_completion_and_information_claims(self):
        result = ho.compare_configurations(study_document())
        validator = Draft202012Validator(ho.load_comparison_schema())
        false_incomplete = copy.deepcopy(result)
        false_incomplete["status"] = "INCOMPLETE"
        self.assertFalse(validator.is_valid(false_incomplete))
        false_scope = copy.deepcopy(result)
        false_scope["rows"][0]["natural_complete"] = False
        self.assertFalse(validator.is_valid(false_scope))
        false_relation = copy.deepcopy(result)
        relation = false_relation["relations"][0]
        relation["relation"] = "EQUIVALENT"
        self.assertFalse(validator.is_valid(false_relation))

    def test_cli_json_matches_api_and_bundle_replays_outside_source_directory(self):
        result = ho.compare_configurations(study_document())
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            path = workspace / "study.json"
            path.write_text(json.dumps(study_document()), encoding="utf-8")
            bundle = workspace / "results"
            completed = self.run_cli(
                "compare",
                str(path),
                "--format",
                "json",
                "--output-dir",
                str(bundle),
                cwd=workspace,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), result)
            self.assertEqual(
                json.loads((bundle / "comparison.json").read_text()), result
            )
            replay = self.run_cli(
                "compare",
                "study.json",
                "--format",
                "json",
                "--output-dir",
                "replayed",
                cwd=bundle,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(json.loads(replay.stdout), result)
            manifest = json.loads((bundle / "manifest.json").read_text())
            self.assertEqual(manifest["bundle_status"], "COMPLETE")
            names = {item["path"] for item in manifest["files"]}
            self.assertTrue(
                {
                    "study.json",
                    "comparison.json",
                    "comparison.md",
                    "environment.json",
                    "README.md",
                }
                <= names
            )
            self.assertEqual(
                json.loads((bundle / "environment.json").read_text()),
                result["producer"]["environment"],
            )
            for item in manifest["files"]:
                contents = (bundle / item["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(contents).hexdigest(), item["sha256"])
                self.assertEqual(len(contents), item["size_bytes"])
            for identifier, raw_result in result["results"].items():
                self.assertEqual(
                    json.loads(
                        (bundle / "raw" / f"config-{identifier}.json").read_text()
                    ),
                    raw_result,
                )
                single = self.run_cli(
                    "analyze",
                    f"models/config-{identifier}.json",
                    "--format",
                    "json",
                    cwd=bundle,
                )
                self.assertEqual(single.returncode, 0, single.stderr)
                self.assertEqual(json.loads(single.stdout), raw_result)

    def test_cli_incomplete_exit_and_invalid_global_failure_do_not_look_successful(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            path = workspace / "study.json"
            study = study_document()
            study["analysis"]["max_layer"] = 2
            path.write_text(json.dumps(study), encoding="utf-8")
            partial = self.run_cli("compare", str(path), "--format", "json")
            self.assertEqual(partial.returncode, 1, partial.stderr)
            self.assertEqual(json.loads(partial.stdout)["status"], "INCOMPLETE")
            study["model"]["edges"].append(["o", "o"])
            path.write_text(json.dumps(study), encoding="utf-8")
            output = workspace / "invalid-results"
            failed = self.run_cli(
                "compare", str(path), "--output-dir", str(output), "--format", "json"
            )
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(json.loads(failed.stdout)["status"], "ERROR")
            self.assertFalse(output.exists())
            self.assertNotIn("Traceback", failed.stdout + failed.stderr)

    def test_export_and_template_commands_never_overwrite_existing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output = workspace / "results"
            output.mkdir()
            sentinel = output / "comparison.json"
            sentinel.write_text("original evidence", encoding="utf-8")
            with self.assertRaises((ValueError, OSError)):
                ho.write_comparison_bundle(
                    ho.compare_configurations(study_document()), output
                )
            self.assertEqual(sentinel.read_text(), "original evidence")
            template = workspace / "study.json"
            first = self.run_cli("study-example", "minimal", "--output", str(template))
            self.assertEqual(first.returncode, 0, first.stderr)
            original = template.read_bytes()
            second = self.run_cli("study-example", "bridge", "--output", str(template))
            self.assertEqual(second.returncode, 2)
            self.assertEqual(template.read_bytes(), original)

    def test_alternative_tree_bundle_replays_its_declared_coordinates(self):
        study = study_document()
        result = ho.compare_configurations(study, reverse_tree_order=True)
        self.validate_comparison(result)
        self.assertTrue(result["shared_conditions"]["reverse_tree_order"])
        with tempfile.TemporaryDirectory() as directory:
            bundle = ho.write_comparison_bundle(result, Path(directory) / "bundle")
            replay = self.run_cli(
                "compare",
                "study.json",
                "--reverse-tree-order",
                "--format",
                "json",
                cwd=bundle,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(json.loads(replay.stdout), result)
            self.assertIn("--reverse-tree-order", (bundle / "README.md").read_text())
            single = self.run_cli(
                "analyze",
                "models/config-pump.json",
                "--reverse-tree-order",
                "--format",
                "json",
                cwd=bundle,
            )
            self.assertEqual(single.returncode, 0, single.stderr)
            self.assertEqual(json.loads(single.stdout), result["results"]["pump"])

    def test_complete_bundle_preserves_an_incomplete_scientific_study(self):
        study = study_document()
        study["configurations"][0]["readouts"] = "invalid counters"
        result = ho.compare_configurations(study)
        with tempfile.TemporaryDirectory() as directory:
            bundle = ho.write_comparison_bundle(result, Path(directory) / "bundle")
            self.assertEqual(
                json.loads((bundle / "manifest.json").read_text())["bundle_status"],
                "COMPLETE",
            )
            self.assertEqual(
                json.loads((bundle / "comparison.json").read_text())["status"],
                "INCOMPLETE",
            )
            self.assertEqual(
                json.loads((bundle / "models/config-none.json").read_text())[
                    "readouts"
                ],
                "invalid counters",
            )
            self.assertFalse((bundle / "raw/config-none.json").exists())
            replay = self.run_cli(
                "compare", "study.json", "--format", "json", cwd=bundle
            )
            self.assertEqual(replay.returncode, 1, replay.stderr)
            self.assertEqual(json.loads(replay.stdout), result)

    def test_interrupted_export_never_publishes_a_completion_manifest(self):
        result = ho.compare_configurations(study_document())
        original_open = Path.open

        def fail_report(path, *arguments, **keywords):
            if path.name == "comparison.md" and arguments and arguments[0] == "xb":
                raise OSError("simulated full disk")
            return original_open(path, *arguments, **keywords)

        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            with mock.patch.object(Path, "open", fail_report):
                with self.assertRaisesRegex(OSError, "simulated full disk"):
                    ho.write_comparison_bundle(result, bundle)
            self.assertFalse((bundle / "manifest.json").exists())
            with self.assertRaises((ValueError, OSError)):
                ho.write_comparison_bundle(result, bundle)

    def test_human_reports_preserve_small_positive_entropy_coefficients(self):
        study = ho.load_study_example("bridge")
        study["analysis"]["alpha"] = 1 / 3
        result = ho.compare_configurations(study)
        row = next(row for row in result["rows"] if row["id"] == "x")
        value = row["entropy_log_t_coefficient"]
        self.assertGreater(value, 0)
        self.assertLess(value, 1e-16)
        self.assertIn(repr(value), ho.render_comparison_text(result))
        self.assertIn(repr(value), ho.render_comparison_markdown(result))

    def test_portable_filenames_preserve_reserved_device_identifiers(self):
        study = study_document()
        study["configurations"] = [{"id": "con", "readouts": []}]
        result = ho.compare_configurations(study)
        self.assertEqual(result["rows"][0]["id"], "con")
        with tempfile.TemporaryDirectory() as directory:
            bundle = ho.write_comparison_bundle(result, Path(directory) / "bundle")
            self.assertTrue((bundle / "models/config-con.json").is_file())
            self.assertTrue((bundle / "raw/config-con.json").is_file())
            self.assertFalse((bundle / "models/con.json").exists())

    def test_export_retains_the_original_producer_environment(self):
        result = ho.compare_configurations(study_document())
        saved_environment = copy.deepcopy(result["producer"]["environment"])
        saved_environment["platform"] = "Earlier evaluation host"
        result["producer"]["environment"] = saved_environment
        with tempfile.TemporaryDirectory() as directory:
            bundle = ho.write_comparison_bundle(result, Path(directory) / "bundle")
            self.assertEqual(
                json.loads((bundle / "environment.json").read_text()), saved_environment
            )
            self.assertEqual(
                json.loads((bundle / "comparison.json").read_text())["producer"][
                    "environment"
                ],
                saved_environment,
            )

    def test_analysis_entry_import_does_not_initialize_plotting(self):
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(Path(ho.__file__).resolve().parent.parent)
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import homological_observability.cli; "
                "assert 'matplotlib' not in sys.modules, 'analysis loaded plotting'",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_packaged_templates_are_valid_editable_studies(self):
        validator = Draft202012Validator(ho.load_study_schema())
        for name in ("minimal", "bridge", "theta"):
            with self.subTest(name=name):
                completed = self.run_cli("study-example", name)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                study = json.loads(completed.stdout)
                validator.validate(study)
                result = ho.compare_configurations(study)
                self.validate_comparison(result)
                self.assertEqual(result["status"], "COMPLETE")


if __name__ == "__main__":
    unittest.main()
