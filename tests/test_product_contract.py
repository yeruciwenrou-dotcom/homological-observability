"""Contract tests for the public API, renderers, CLI, and package data."""

from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from importlib import resources
from pathlib import Path
from unittest import mock

import homological_observability as ho
from homological_observability import cli
from homological_observability.examples import examples_to_dict, load_example
from homological_observability.reproduction import ReproductionMismatch

ROOT = Path(__file__).resolve().parents[1]


class ProductContractTests(unittest.TestCase):
    def test_runtime_package_and_citation_versions_match(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        citation_version = re.search(r"^version: (.+)$", citation, flags=re.MULTILINE)
        self.assertIsNotNone(citation_version)
        self.assertEqual(project["project"]["version"], ho.__version__)
        self.assertEqual(citation_version.group(1), ho.__version__)

    def test_public_api_serializes_the_builtin_example_deterministically(self) -> None:
        model = load_example("wedge-c3-c5")
        result = ho.analyze_model(model)
        first = ho.analysis_to_dict(
            result,
            artifact_role=ho.ArtifactRole.BUILTIN_EXAMPLE,
        )
        second = json.loads(
            ho.render_json(
                result,
                artifact_role=ho.ArtifactRole.BUILTIN_EXAMPLE,
            )
        )
        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], 2)
        self.assertEqual(first["status"], "COMPLETE")
        self.assertEqual(first["artifact_role"], "builtin-example")
        self.assertEqual(len(first["normalized_model_sha256"]), 64)
        self.assertEqual(first["summary"]["requested_max_layer"], 3)
        self.assertEqual(first["summary"]["natural_max_layer"], 4)
        self.assertTrue(first["summary"]["requested_horizon_complete"])
        self.assertTrue(first["summary"]["natural_filtration_complete"])
        self.assertEqual(first["summary"]["first_nonzero_exposure_layer"], 2)
        self.assertEqual(first["summary"]["first_nonzero_hidden_layer"], 3)
        layer_three = first["filtration"]["layers"][3]
        self.assertEqual(
            layer_three["visible"]["graded_quotient"]["torsion_factors"],
            [2],
        )

    def test_zero_matrices_retain_their_exact_shapes(self) -> None:
        document = ho.analysis_to_dict(ho.analyze_model(load_example("wedge-c3-c5")))
        layer_zero = document["filtration"]["layers"][0]
        self.assertEqual(
            layer_zero["exposure"]["basis_columns"],
            {"rows": 2, "columns": 0, "data": [[], []]},
        )
        self.assertEqual(
            layer_zero["visible"]["basis_columns"],
            {"rows": 1, "columns": 0, "data": [[]]},
        )

    def test_limit_status_never_serializes_a_partial_filtration(self) -> None:
        model = ho.GraphModel.create(
            name="limited-wedge",
            vertices=("a1", "a2", "b1", "b2", "b3", "b4", "o"),
            edges=(
                ("a1", "a2"),
                ("a1", "o"),
                ("a2", "o"),
                ("b1", "b2"),
                ("b1", "o"),
                ("b2", "b3"),
                ("b3", "b4"),
                ("b4", "o"),
            ),
            max_layer=3,
            max_cycles=1,
        )
        document = ho.analysis_to_dict(ho.analyze_model(model))
        self.assertEqual(document["status"], "LIMIT_REACHED")
        self.assertIsNone(document["filtration"])
        self.assertIsNone(document["phase"])
        self.assertEqual(document["limit"]["resource"], "simple_cycles")
        self.assertFalse(document["summary"]["requested_horizon_complete"])
        self.assertFalse(document["summary"]["natural_filtration_complete"])
        self.assertIsNone(document["summary"]["computed_max_layer"])

    def test_low_layer_horizon_is_not_reported_as_naturally_complete(self) -> None:
        model = ho.GraphModel.create(
            name="c5-partial-horizon",
            vertices=("v0", "v1", "v2", "v3", "v4"),
            edges=(
                ("v0", "v1"),
                ("v1", "v2"),
                ("v2", "v3"),
                ("v3", "v4"),
                ("v4", "v0"),
            ),
            max_layer=2,
        )
        result = ho.analyze_model(model)
        document = ho.analysis_to_dict(result)

        self.assertEqual(result.status, ho.AnalysisStatus.PARTIAL_HORIZON)
        self.assertFalse(result.is_complete)
        self.assertEqual(document["status"], "PARTIAL_HORIZON")
        self.assertEqual(document["summary"]["requested_max_layer"], 2)
        self.assertEqual(document["summary"]["computed_max_layer"], 2)
        self.assertEqual(document["summary"]["natural_max_layer"], 3)
        self.assertTrue(document["summary"]["requested_horizon_complete"])
        self.assertFalse(document["summary"]["natural_filtration_complete"])
        self.assertEqual(document["filtration"]["layers"][2]["exposure"]["rank"], 0)
        self.assertIsNotNone(document["phase"])
        self.assertIn("Partial horizon", ho.render_text(result))
        self.assertIn("## Partial horizon", ho.render_markdown(result))

    def test_text_and_markdown_share_the_evidence_boundary(self) -> None:
        result = ho.analyze_model(load_example("wedge-c3-c5"))
        text = ho.render_text(result)
        markdown = ho.render_markdown(result)
        self.assertIn("exact integer", text.lower())
        self.assertIn("asymptotic predictions", text.lower())
        self.assertIn("## Evidence boundary", markdown)
        self.assertIn("finite-sample error bars", markdown)

    def test_analysis_schema_is_bundled_and_tracks_the_document(self) -> None:
        schema = ho.load_analysis_schema()
        document = ho.analysis_to_dict(ho.analyze_model(load_example("wedge-c3-c5")))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 2)
        self.assertEqual(set(schema["required"]), set(document))
        self.assertEqual(
            schema["properties"]["artifact_role"]["enum"],
            ["fresh-analysis", "builtin-example"],
        )
        self.assertEqual(
            schema["properties"]["status"]["enum"],
            ["COMPLETE", "PARTIAL_HORIZON", "LIMIT_REACHED"],
        )

    def test_package_mirrors_match_reader_visible_examples_and_references(self) -> None:
        package = resources.files("homological_observability")
        packaged_example = package.joinpath(
            "data", "examples", "wedge_c3_c5.json"
        ).read_bytes()
        self.assertEqual(
            packaged_example, (ROOT / "examples/wedge_c3_c5.json").read_bytes()
        )
        for name in (
            "critical_kernel_results.csv",
            "selected_appendix_checks.csv",
        ):
            with package.joinpath("data", "reference", name).open("rb") as handle:
                self.assertEqual(handle.read(), (ROOT / "results" / name).read_bytes())

    def test_cli_json_is_the_public_api_document(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "homological_observability.cli",
                "example",
                "wedge-c3-c5",
                "--format",
                "json",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cli_document = json.loads(completed.stdout)
        api_document = ho.analysis_to_dict(
            ho.analyze_model(load_example("wedge-c3-c5")),
            artifact_role=ho.ArtifactRole.BUILTIN_EXAMPLE,
        )
        self.assertEqual(cli_document, api_document)

    def test_cli_lists_examples_and_reports_input_errors_without_tracebacks(
        self,
    ) -> None:
        listed = subprocess.run(
            [
                sys.executable,
                "-m",
                "homological_observability.cli",
                "examples",
                "--format",
                "json",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(listed.stdout), examples_to_dict())

        failed = subprocess.run(
            [
                sys.executable,
                "-m",
                "homological_observability.cli",
                "analyze",
                "missing-model.json",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(failed.returncode, 2)
        self.assertIn("error:", failed.stderr)
        self.assertNotIn("Traceback", failed.stderr)

    def test_cli_uses_exit_one_for_resource_limited_results(self) -> None:
        payload = json.loads((ROOT / "examples/wedge_c3_c5.json").read_text())
        payload["analysis"]["max_cycles"] = 1
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "limited.json"
            model_path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homological_observability.cli",
                    "analyze",
                    str(model_path),
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

    def test_cli_uses_exit_zero_for_a_completed_partial_horizon(self) -> None:
        payload = {
            "schema_version": 1,
            "name": "c5-partial-horizon",
            "vertices": ["v0", "v1", "v2", "v3", "v4"],
            "edges": [
                ["v0", "v1"],
                ["v1", "v2"],
                ["v2", "v3"],
                ["v3", "v4"],
                ["v4", "v0"],
            ],
            "analysis": {"max_layer": 2},
        }
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "partial.json"
            model_path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homological_observability.cli",
                    "analyze",
                    str(model_path),
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0)
        document = json.loads(completed.stdout)
        self.assertEqual(document["status"], "PARTIAL_HORIZON")
        self.assertTrue(document["summary"]["requested_horizon_complete"])
        self.assertFalse(document["summary"]["natural_filtration_complete"])

    def test_cli_reproduction_mismatch_uses_exit_one(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(
                cli,
                "run_reproduction",
                side_effect=ReproductionMismatch("reference mismatch"),
            ),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = cli.main(["reproduce", "--check"])
        self.assertEqual(exit_code, 1)
        self.assertIn("FAIL: reference mismatch", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
