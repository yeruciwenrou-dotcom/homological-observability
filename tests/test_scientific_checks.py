"""Regression and identity tests for the advertised scientific checks."""

from __future__ import annotations

import math
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import critical_kernel_checks
import quickstart
import reproduce_all
import selected_appendix_checks
from homological_observability import (
    poisson_averaged_binomial_map_bessel,
    poisson_averaged_binomial_map_direct,
    reproduction,
)

ROOT = Path(__file__).resolve().parents[1]


class ScientificCheckTests(unittest.TestCase):
    def test_poisson_averaged_map_identity(self) -> None:
        for mean in (0.0, 0.2, 1.0, 3.0, 8.0):
            with self.subTest(mean=mean):
                self.assertAlmostEqual(
                    poisson_averaged_binomial_map_direct(mean),
                    poisson_averaged_binomial_map_bessel(mean),
                    places=13,
                )

    def test_bessel_map_formula_remains_finite_for_large_mean(self) -> None:
        mean = 10000.0
        computed = poisson_averaged_binomial_map_bessel(mean)
        leading_asymptotic = math.sqrt(2.0 / (math.pi * mean))
        self.assertTrue(math.isfinite(computed))
        self.assertAlmostEqual(
            computed / leading_asymptotic,
            1.0,
            places=4,
        )

    def test_reference_tables_are_reproduced(self) -> None:
        critical = critical_kernel_checks.build_results()
        critical_kernel_checks.validate_results(critical)
        selected = selected_appendix_checks.build_results()
        selected_appendix_checks.validate_results(selected)

        pd.testing.assert_frame_equal(
            critical,
            pd.read_csv(ROOT / "results/critical_kernel_results.csv"),
            check_dtype=False,
            check_exact=False,
            rtol=1.0e-12,
            atol=1.0e-14,
        )
        pd.testing.assert_frame_equal(
            selected,
            pd.read_csv(ROOT / "results/selected_appendix_checks.csv"),
            check_dtype=False,
            check_exact=False,
            rtol=1.0e-12,
            atol=1.0e-14,
        )

    def test_reference_comparison_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "generated.csv"
            reference = Path(directory) / "reference.csv"
            pd.DataFrame({"value": [1.0]}).to_csv(generated, index=False)
            pd.DataFrame({"value": [2.0]}).to_csv(reference, index=False)
            with self.assertRaises(AssertionError):
                reproduce_all.compare_with_reference(generated, reference)

    def test_reproduction_cannot_overwrite_reference_results(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not overwrite"):
            reproduce_all.validate_output_directory(ROOT / "results")
        with self.assertRaisesRegex(ValueError, "must not overwrite"):
            reproduce_all.validate_output_directory(ROOT / "results/generated")

    def test_reproduction_rejects_reference_file_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            output = output_dir / "critical_kernel_results.csv"
            try:
                output.hardlink_to(ROOT / "results/critical_kernel_results.csv")
            except OSError as error:
                self.skipTest(f"hard links unavailable: {error}")
            with self.assertRaisesRegex(ValueError, "must not alias"):
                reproduce_all.validated_output_path(output_dir, output.name)

    def test_packaged_reference_directory_is_protected_before_any_write(self) -> None:
        reference = reproduction._reference_resource("critical_kernel_results.csv")
        before = reference.read_bytes()
        for output in (reference.parent, reference.parent / "nested"):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ValueError, "must not overwrite"):
                    reproduction.run_reproduction(output, check=True)
        self.assertEqual(reference.read_bytes(), before)
        self.assertFalse((reference.parent / "nested").exists())

    def test_cross_named_reference_aliases_are_rejected_before_any_write(self) -> None:
        for source in (
            ROOT / "results/critical_kernel_results.csv",
            reproduction._reference_resource("selected_appendix_checks.csv"),
        ):
            for link_type in ("hard", "symbolic"):
                with self.subTest(source=source, link_type=link_type):
                    with tempfile.TemporaryDirectory() as directory:
                        output_dir = Path(directory)
                        output = output_dir / "REPORT.md"
                        try:
                            if link_type == "hard":
                                output.hardlink_to(source)
                            else:
                                output.symlink_to(source)
                        except OSError:
                            continue  # Some supported Windows setups disallow links.
                        before = source.read_bytes()
                        with self.assertRaisesRegex(ValueError, "must not alias"):
                            reproduction.run_reproduction(output_dir, check=False)
                        self.assertEqual(source.read_bytes(), before)
                        self.assertEqual(set(output_dir.iterdir()), {output})

    def test_invalid_refinement_is_rejected(self) -> None:
        results = critical_kernel_checks.build_results()
        results.loc[1, "delta"] = results.loc[0, "delta"]
        with self.assertRaises(AssertionError):
            critical_kernel_checks.validate_results(results)

    def test_cycle_explorer_runs(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "explore_cycles.py",
                "--cycle",
                "4",
                "--residue",
                "2",
                "--delta",
                "0.1",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("posterior mass shown: 1", completed.stdout)

    def test_cycle_explorer_reports_invalid_inputs_cleanly(self) -> None:
        completed = subprocess.run(
            [sys.executable, "explore_cycles.py", "--cycle", "2"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--cycle must be at least 3", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

        completed = subprocess.run(
            [
                sys.executable,
                "explore_cycles.py",
                "--cycle",
                "4",
                "--residue",
                "4",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("0 <= residue < --cycle", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_one_command_quickstart_runs_complete_gate(self) -> None:
        commands = []

        def record(command, **kwargs):
            commands.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)

        with (
            mock.patch.object(
                quickstart, "ensure_environment", return_value=Path(sys.executable)
            ),
            mock.patch.object(quickstart, "ensure_dependencies"),
            mock.patch.object(quickstart.subprocess, "run", side_effect=record),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(quickstart.main([]), 0)

        self.assertEqual(commands[0][0][-4:], ["discover", "-s", "tests", "-v"])
        self.assertEqual(commands[0][0][1:3], ["-W", "error"])
        self.assertEqual(commands[1][0][-1], "reproduce_all.py")
        self.assertEqual(commands[1][0][1:3], ["-W", "error"])
        self.assertTrue(all(kwargs["check"] for _, kwargs in commands))

    def test_quickstart_rebuilds_environment_for_active_python(self) -> None:
        builder = mock.Mock()
        with (
            mock.patch.object(
                quickstart, "environment_python", return_value=Path(sys.executable)
            ),
            mock.patch.object(
                quickstart,
                "_environment_version",
                return_value=(sys.version_info.major, sys.version_info.minor - 1),
            ),
            mock.patch.object(
                quickstart.venv, "EnvBuilder", return_value=builder
            ) as cls,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(quickstart.ensure_environment(), Path(sys.executable))

        cls.assert_called_once_with(with_pip=True, clear=True)
        builder.create.assert_called_once_with(quickstart.ENVIRONMENT)

    def test_quickstart_repairs_an_unusable_environment(self) -> None:
        builder = mock.Mock()
        with (
            mock.patch.object(
                quickstart, "environment_python", return_value=Path(sys.executable)
            ),
            mock.patch.object(quickstart, "_environment_version", side_effect=OSError),
            mock.patch.object(
                quickstart.venv, "EnvBuilder", return_value=builder
            ) as cls,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(quickstart.ensure_environment(), Path(sys.executable))

        cls.assert_called_once_with(with_pip=True, clear=True)
        builder.create.assert_called_once_with(quickstart.ENVIRONMENT)

    def test_reader_facing_local_links_resolve(self) -> None:
        for relative in ("README.md", "PAPER_MAP.md"):
            path = ROOT / relative
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                file_target = target.partition("#")[0]
                self.assertTrue(
                    (path.parent / file_target).exists(),
                    f"broken link in {relative}: {target}",
                )


if __name__ == "__main__":
    unittest.main()
