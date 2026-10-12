"""Execution and consistency tests for the complete public documentation."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def public_markdown() -> tuple[Path, ...]:
    paths = [
        ROOT / "README.md",
        ROOT / "PAPER_MAP.md",
        ROOT / "CHANGELOG.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "examples/wedge_c3_c5_result.md",
        ROOT / "results/REPORT.md",
    ]
    paths.extend(sorted((ROOT / "docs").glob("*.md")))
    return tuple(paths)


def fenced_blocks(text: str, language: str) -> list[str]:
    pattern = rf"```{re.escape(language)}\n(.*?)\n```"
    return re.findall(pattern, text, flags=re.DOTALL)


class DocumentationTests(unittest.TestCase):
    def test_all_local_links_resolve(self) -> None:
        for path in public_markdown():
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"!?\[[^]]*\]\(([^)]+)\)", text):
                if "://" in target or target.startswith(("#", "mailto:")):
                    continue
                file_target = target.partition("#")[0]
                self.assertTrue(
                    (path.parent / file_target).exists(),
                    f"broken link in {path.relative_to(ROOT)}: {target}",
                )

    def test_python_and_json_blocks_execute_or_parse(self) -> None:
        namespace = {"__name__": "__documentation_test__"}
        for path in public_markdown():
            text = path.read_text(encoding="utf-8")
            for index, block in enumerate(fenced_blocks(text, "python")):
                with self.subTest(path=path.name, language="python", index=index):
                    exec(compile(block, str(path), "exec"), namespace.copy())
            for index, block in enumerate(fenced_blocks(text, "json")):
                with self.subTest(path=path.name, language="json", index=index):
                    json.loads(block)

    def test_reader_commands_run(self) -> None:
        commands = (
            ["examples", "--format", "json"],
            ["example", "wedge-c3-c5"],
            ["example", "wedge-c3-c5", "--format", "json"],
            ["analyze", "examples/wedge_c3_c5.json"],
            ["analyze", "examples/wedge_c3_c5.json", "--format", "json"],
            ["critical", "examples/biased_c4_critical.json"],
            [
                "critical",
                "examples/biased_c4_critical.json",
                "--format",
                "json",
            ],
        )
        for arguments in commands:
            with self.subTest(arguments=arguments):
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "homological_observability.cli",
                        *arguments,
                    ],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )

        subprocess.run(
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

        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homological_observability.cli",
                    "reproduce",
                    "--check",
                    "--output-dir",
                    directory,
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

    def test_documented_setup_and_long_gates_are_in_ci(self) -> None:
        workflow = (ROOT / ".github/workflows/reproduce.yml").read_text(
            encoding="utf-8"
        )
        for command in (
            "python quickstart.py",
            "python tests/validate_schema.py",
            "python tests/validate_distribution.py",
            "python tests/validate_graph_atlas.py",
            "ruff check .",
            "ruff format --check .",
        ):
            self.assertIn(command, workflow)

        action_uses = re.findall(r"uses:\s+([^@\s]+)@([^\s]+)", workflow)
        self.assertTrue(action_uses)
        for action, revision in action_uses:
            self.assertIn(
                action,
                {"actions/checkout", "actions/setup-python", "actions/upload-artifact"},
            )
            self.assertRegex(revision, r"^[0-9a-f]{40}$")

    def test_reader_verification_and_reproduction_hash_roles_are_explicit(
        self,
    ) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        contract = (ROOT / "docs/OUTPUT_CONTRACT.md").read_text(encoding="utf-8")

        normalized_readme = " ".join(readme.split())
        self.assertIn("runs the reader-side test suite", normalized_readme)
        self.assertNotIn("runs the complete test suite", normalized_readme)
        self.assertIn(
            "reader-side tests and frozen-paper reproduction",
            " ".join(changelog.split()),
        )
        self.assertIn("rtol=1e-12", contract)
        self.assertIn("atol=1e-14", contract)
        self.assertIn(
            "provenance identifiers, not cross-platform acceptance criteria",
            " ".join(contract.split()),
        )

    def test_frozen_example_artifacts_are_current(self) -> None:
        subprocess.run(
            [sys.executable, "tools/freeze_examples.py", "--check"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_public_documents_do_not_expose_process_language(self) -> None:
        forbidden = (
            "cross-window",
            "private pr",
            "review window",
            "internal audit round",
            "first milestone",
            "first-milestone",
            "vertical slice through the product",
            "product contract tests",
            "human-readable text does not change the schema",
            "without a schema-version change",
            "requires a new schema version",
            "migration guidance",
            "internal development version",
            "contract tests compare",
            "automated documentation tests",
            "## compatibility policy",
            "阶段 3",
            "跨窗口",
            "封板",
            "does not implement the general rate-dependent critical",
        )
        for path in public_markdown():
            lowered = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden:
                self.assertNotIn(
                    phrase,
                    lowered,
                    f"internal process language in {path.relative_to(ROOT)}",
                )

    def test_paper_support_and_visible_image_notation_are_explicit(self) -> None:
        scope = (ROOT / "docs/SCIENTIFIC_SCOPE.md").read_text(encoding="utf-8")
        conventions = (ROOT / "docs/CONVENTIONS.md").read_text(encoding="utf-8")
        self.assertIn("bidirectional positive-rate support", scope)
        self.assertRegex(
            conventions,
            r"positive\s+transition-rate support in both directions",
        )

        collision = re.compile(r"\bJ_(?:m|[0-9]+)")
        for path in public_markdown():
            document = path.read_text(encoding="utf-8")
            self.assertIsNone(
                collision.search(document),
                f"visible-image notation collides with the paper in {path.relative_to(ROOT)}",
            )
            self.assertNotIn("rank J", document)
            self.assertNotIn("gr J", document)

        self.assertIn(r"\pi:\Lambda\longrightarrow\mathbb Z^q", conventions)
        self.assertIn(r"P=[\pi]_{\mathcal B}", conventions)
        self.assertNotRegex(
            conventions,
            r"(?m)^\s*=\s*$",
            "a standalone equals sign can turn a display formula into a heading",
        )

    def test_critical_reader_surface_matches_the_generated_result(self) -> None:
        guide = (ROOT / "docs/CRITICAL_EXPERIMENT.md").read_text(encoding="utf-8")
        scope = (ROOT / "docs/SCIENTIFIC_SCOPE.md").read_text(encoding="utf-8")
        paper_map = (ROOT / "PAPER_MAP.md").read_text(encoding="utf-8")
        result = json.loads(
            (ROOT / "examples/biased_c4_critical_result.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["summary"]["critical_total_intensity"], "5/2")
        self.assertEqual(result["stationary_law"]["probabilities"], ["1/4"] * 4)
        first_marks = result["limit_experiment"]["critical_endpoint_components"][0][
            "conditional_mark_law"
        ]
        self.assertEqual(
            sorted(mark["probability"] for mark in first_marks),
            ["1/5", "4/5"],
        )
        for document in (guide, scope, paper_map):
            self.assertIn("posterior at finite $(T,\\delta)$", document)
        self.assertIn(
            "critical-limit generative specification",
            " ".join(guide.split()),
        )

    def test_mathematics_uses_github_math_markup(self) -> None:
        mathematical_documents = (
            ROOT / "README.md",
            ROOT / "PAPER_MAP.md",
            ROOT / "docs/CONVENTIONS.md",
            ROOT / "docs/CRITICAL_EXPERIMENT.md",
            ROOT / "docs/SCIENTIFIC_SCOPE.md",
            ROOT / "docs/END_TO_END_EXAMPLE.md",
            ROOT / "docs/MODEL_GUIDE.md",
            ROOT / "docs/OUTPUT_CONTRACT.md",
        )
        code_styled_mathematics = (
            "`H_1(G; Z)`",
            "`L_m`",
            "`pi(L_m)`",
            "`P(L_m)`",
            "`K_m =",
            "`Z/2`",
            "`alpha_m",
            "`lambda_m",
        )
        for path in mathematical_documents:
            document = path.read_text(encoding="utf-8")
            for expression in code_styled_mathematics:
                self.assertNotIn(
                    expression,
                    document,
                    f"code-styled mathematics in {path.relative_to(ROOT)}",
                )
            self.assertNotRegex(
                document,
                r"\$(?:pi|alpha)(?:[^A-Za-z]|$)",
                f"unescaped Greek command in {path.relative_to(ROOT)}",
            )
            self.assertNotIn(
                r"\operatorname",
                document,
                f"unsupported GitHub math macro in {path.relative_to(ROOT)}",
            )
            self.assertNotIn(
                r"\,",
                document,
                f"GitHub renders the thin-space macro incorrectly in {path.relative_to(ROOT)}",
            )
            self.assertNotRegex(
                document,
                r"[A-Za-z]-\$",
                f"hyphen-adjacent inline math is not rendered in {path.relative_to(ROOT)}",
            )
            for line in document.splitlines():
                if not line.lstrip().startswith("|"):
                    continue
                for expression in re.findall(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$", line):
                    self.assertNotIn(
                        "|",
                        expression,
                        f"unescaped table-cell pipe in {path.relative_to(ROOT)}",
                    )

        generated = (ROOT / "examples/wedge_c3_c5_result.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(r"$\pi(L_m)$", generated)
        self.assertIn(r"$\mathbb Z/2\mathbb Z$", generated)

    def test_network_diagram_is_valid_svg(self) -> None:
        root = ET.parse(ROOT / "docs/wedge_c3_c5.svg").getroot()
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("recursive-include docs *.md *.svg", manifest)
        self.assertIn("include CONTRIBUTING.md", manifest)
        self.assertIn("include SECURITY.md", manifest)


if __name__ == "__main__":
    unittest.main()
