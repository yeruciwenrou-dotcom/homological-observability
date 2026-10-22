"""Human reports retain the scope and concrete evidence of computed comparisons."""

from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

import homological_observability as ho


def readable(markdown):
    """Remove Markdown punctuation escapes for assertions on visible wording."""
    return re.sub(r"\\([^\s])", r"\1", markdown)


class ComparisonReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = ho.load_study_example("bridge")
        cls.document = ho.compare_configurations(cls.study)

    def test_metric_summary_names_scoped_candidates_without_interpreting_question(self):
        result = copy.deepcopy(self.document)
        result["study"]["question"] = "Choose the cheapest physical instrument."
        report = readable(ho.render_comparison_markdown(result))
        findings = report.split("## Main findings\n", 1)[1].split(
            "## Shared conditions", 1
        )[0]
        self.assertIn(
            "1-channel configurations on the full integer cycle group", findings
        )
        self.assertIn(
            "latest reported first hidden layer is 4: Counter x (C4) [x]; Counter 2x+y [mixed]",
            findings,
        )
        self.assertIn("carry incomparable information", findings)
        self.assertNotIn("cheapest", findings)
        self.assertLess(findings.index("latest reported"), findings.index("6 of 6"))
        self.assertIn("11 vertices, 12 edges", report)
        self.assertIn("delta = T^(-0.375)", report)
        self.assertIn("cycle enumeration budget: 1000", report)

    def test_representative_edge_witness_and_readouts_are_visible_and_locatable(self):
        report = readable(ho.render_comparison_markdown(self.document))
        index, pair = next(
            (index, pair)
            for index, pair in enumerate(self.document["relations"])
            if pair["left"] == "x" and pair["right"] == "mixed"
        )
        for key in ("left_not_right_witness", "right_not_left_witness"):
            witness = pair[key]
            changes = []
            chain = {
                tuple(term["edge"]): term["coefficient"]
                for term in witness["edge_chain"]
            }
            for identifier in ("x", "mixed"):
                readouts = self.document["results"][identifier]["model"]["readouts"]
                changes.append(
                    [
                        sum(
                            term["coefficient"] * chain.get(tuple(term["edge"]), 0)
                            for term in readout["coefficients"]
                        )
                        for readout in readouts
                    ]
                )
            self.assertIn(
                f"Readout changes: Counter x (C4) [x]: {changes[0]}; "
                f"Counter 2x+y [mixed]: {changes[1]}.",
                report,
            )
            self.assertIn(f"relations[{index}].{key}", report)
            for edge, coefficient in chain.items():
                self.assertIn(f"| {edge[0]} → {edge[1]} | {coefficient} |", report)
        self.assertIn("Same information", report)
        self.assertNotIn("RIGHT_REFINES_LEFT", report)
        self.assertIn("[All exact evidence](comparison.json)", report)

    def test_partial_and_unavailable_results_do_not_gain_full_scope_claims(self):
        partial_study = copy.deepcopy(self.study)
        partial_study["analysis"]["max_layer"] = 2
        partial = ho.compare_configurations(partial_study)
        report = readable(ho.render_comparison_markdown(partial))
        self.assertIn("computed exposure through layer 2 only", report)
        self.assertIn("uncomputed layers open", report)
        self.assertNotIn("on the full integer cycle group", report)
        limited_study = copy.deepcopy(self.study)
        limited_study["analysis"]["max_cycles"] = 1
        limited_study["configurations"][0]["readouts"] = "invalid readouts"
        limited = ho.compare_configurations(limited_study)
        for render in (ho.render_comparison_text, ho.render_comparison_markdown):
            text = readable(render(limited))
            self.assertIn("INCOMPLETE", text)
            self.assertIn("LIMIT_REACHED", text)
            self.assertIn("ERROR", text)
            self.assertIn("No information conclusion is available", text)
            self.assertNotIn("no hidden integer direction remains for", text)
            self.assertNotIn("Readout changes:", text)
            self.assertIn("Increase analysis.max_cycles", text)

    def test_user_text_cannot_create_markdown_structure_or_terminal_controls(self):
        result = copy.deepcopy(self.document)
        label = "# <img src=x> | `x`\n[link](https://example.org)\x1b"
        result["study"]["name"] = label
        result["study"]["question"] = "- pretend heading\n```sh\ndanger"
        result["rows"][1]["label"] = label
        report = ho.render_comparison_markdown(result)
        self.assertNotRegex(report, r"(?<!\\)<img")
        self.assertNotIn("[link](https://example.org)", report)
        self.assertNotIn("```sh", report)
        self.assertIn(r"\|", report)
        self.assertIn(r"\`x\`", report)
        self.assertNotIn("\x1b", report)
        self.assertNotIn("\x1b", ho.render_comparison_text(result))

    def test_linked_bundle_preserves_original_records_and_reverse_replay(self):
        result = ho.compare_configurations(self.study, reverse_tree_order=True)
        before = copy.deepcopy(result)
        with tempfile.TemporaryDirectory() as temporary:
            destination = ho.write_comparison_bundle(result, Path(temporary) / "bundle")
            readme = (destination / "README.md").read_text()
            self.assertIn("[comparison report](comparison.md)", readme)
            self.assertIn(
                "compare study.json --output-dir replay --reverse-tree-order", readme
            )
            self.assertIn("analyze models/config-ID.json --reverse-tree-order", readme)
            self.assertLess(
                readme.index("## Run the study again"), readme.index("Code SHA-256")
            )
            self.assertEqual(
                json.loads((destination / "comparison.json").read_text()), before
            )
            self.assertEqual(
                json.loads((destination / "environment.json").read_text()),
                before["producer"]["environment"],
            )
        self.assertEqual(result, before)


if __name__ == "__main__":
    unittest.main()
