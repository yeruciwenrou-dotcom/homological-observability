"""Reference comparison and report status across successful and failed runs."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from homological_observability import reproduction


class ReproductionStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.critical = reproduction.reference_critical.build_results(theta=1.0)
        cls.selected = reproduction.reference_appendix.build_results()

    def setUp(self) -> None:
        for module, frame in (
            (reproduction.reference_critical, self.critical),
            (reproduction.reference_appendix, self.selected),
        ):
            patcher = mock.patch.object(module, "build_results", return_value=frame)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_checked_and_unchecked_reports_match_the_returned_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for checked in (True, False):
                result = reproduction.run_reproduction(output, check=checked)
                report = (output / "REPORT.md").read_text(encoding="utf-8")
                expected = "PASS" if checked else "NOT REQUESTED"
                self.assertIn(f"Frozen-reference comparison: {expected}", report)
                self.assertEqual(result.to_dict()["status"], "PASS")
                self.assertIs(
                    result.to_dict()["checked_against_frozen_reference"], checked
                )

    def test_mismatch_replaces_a_success_report_in_fresh_and_reused_directories(self):
        for reused in (False, True):
            with (
                self.subTest(reused=reused),
                tempfile.TemporaryDirectory() as directory,
            ):
                output = Path(directory)
                if reused:
                    reproduction.run_reproduction(output, check=True)
                compare = reproduction.compare_with_reference

                def tamper_then_compare(path):
                    path.write_text("value\n-1\n", encoding="utf-8")
                    compare(path)

                with mock.patch.object(
                    reproduction,
                    "compare_with_reference",
                    side_effect=tamper_then_compare,
                ):
                    with self.assertRaises(reproduction.ReproductionMismatch):
                        reproduction.run_reproduction(output, check=True)
                report = (output / "REPORT.md").read_text(encoding="utf-8")
                self.assertIn("Run status: FAIL", report)
                self.assertNotIn("PASS", report)

    def test_interrupted_calculation_invalidates_the_previous_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            reproduction.run_reproduction(output, check=True)
            with mock.patch.object(
                reproduction.reference_critical,
                "build_results",
                side_effect=RuntimeError("interrupted calculation"),
            ):
                with self.assertRaisesRegex(RuntimeError, "interrupted calculation"):
                    reproduction.run_reproduction(output, check=True)
            report = (output / "REPORT.md").read_text(encoding="utf-8")
            self.assertIn("Run status: INCOMPLETE", report)
            self.assertNotIn("PASS", report)


if __name__ == "__main__":
    unittest.main()
