"""Generate and optionally check the frozen finite-cycle paper evidence."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import pandas as pd

from . import reference_appendix, reference_critical
from .reporting import write_report, write_summary_figure

REFERENCE_NAMES = (
    "critical_kernel_results.csv",
    "selected_appendix_checks.csv",
)


class ReproductionMismatch(AssertionError):
    """Raised when generated evidence differs from a frozen reference table."""


@dataclass(frozen=True)
class ReproductionResult:
    """Machine-readable outcome of one full reference-suite run."""

    output_dir: Path
    checked: bool
    files: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_name": "homological-observability.reproduction",
            "schema_version": 1,
            "artifact_role": "canonical-paper-evidence",
            "status": "PASS",
            "checked_against_frozen_reference": self.checked,
            "output_directory": str(self.output_dir),
            "files": [{"name": name, "sha256": digest} for name, digest in self.files],
        }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reference_resource(name: str):
    if name not in REFERENCE_NAMES:
        raise ValueError(f"unknown reference table: {name}")
    return resources.files("homological_observability").joinpath(
        "data", "reference", name
    )


def compare_with_reference(generated: Path, reference=None) -> None:
    """Compare one generated CSV with a path or packaged reference table."""

    if reference is None:
        reference = _reference_resource(generated.name)
    if not reference.is_file():
        raise FileNotFoundError(f"missing reference result: {reference}")
    generated_frame = pd.read_csv(generated)
    with reference.open("rb") as handle:
        reference_frame = pd.read_csv(handle)
    try:
        pd.testing.assert_frame_equal(
            generated_frame,
            reference_frame,
            check_dtype=False,
            check_exact=False,
            rtol=1.0e-12,
            atol=1.0e-14,
        )
    except AssertionError as error:
        raise ReproductionMismatch(str(error)) from error


def _repository_reference_dir() -> Path | None:
    """Locate the reader-visible reference tree in an editable checkout."""

    candidate = Path(__file__).resolve().parents[2] / "results"
    return candidate if candidate.is_dir() else None


def _reference_directories() -> tuple[Path, ...]:
    """Find writable filesystem locations of both copies of the evidence."""

    directories = []
    repository = _repository_reference_dir()
    if repository is not None:
        directories.append(repository.resolve())
    resource = _reference_resource(REFERENCE_NAMES[0])
    # A zip-backed Traversable has no filesystem output alias. Normal wheels
    # and editable installations expose Path resources and need protection.
    if isinstance(resource, Path):
        directories.append(resource.parent.resolve())
    return tuple(dict.fromkeys(directories))


def validate_output_directory(output_dir: Path) -> Path:
    """Resolve output while protecting checkout and installed references."""

    resolved = output_dir.resolve()
    for reference_dir in _reference_directories():
        if resolved == reference_dir or reference_dir in resolved.parents:
            raise ValueError(
                "output directory must not overwrite the committed reference results"
            )
    return resolved


def validated_output_path(output_dir: Path, name: str) -> Path:
    """Return an output path that cannot alias committed reference evidence."""

    output = output_dir / name
    resolved = output.resolve()
    for reference_dir in _reference_directories():
        if resolved == reference_dir or reference_dir in resolved.parents:
            raise ValueError(
                "generated output must not alias the committed reference results"
            )
        if output.exists():
            for reference in reference_dir.rglob("*"):
                if reference.is_file() and output.samefile(reference):
                    raise ValueError(
                        "generated output must not alias the committed reference results"
                    )
    return output


def run_reproduction(
    output_dir: str | Path,
    *,
    check: bool,
) -> ReproductionResult:
    """Reproduce the finite-cycle tables, report, and figures."""

    resolved_output = validate_output_directory(Path(output_dir))
    critical_path = validated_output_path(
        resolved_output, "critical_kernel_results.csv"
    )
    selected_path = validated_output_path(
        resolved_output, "selected_appendix_checks.csv"
    )
    report_path = validated_output_path(resolved_output, "REPORT.md")
    figure_png = validated_output_path(resolved_output, "companion_summary.png")
    figure_svg = validated_output_path(resolved_output, "companion_summary.svg")
    resolved_output.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# Computational companion report\n\n"
        "**Run status: INCOMPLETE**\n\n"
        "The current run has not completed.\n",
        encoding="utf-8",
    )

    critical = reference_critical.build_results(theta=1.0)
    reference_critical.validate_results(critical, theta=1.0)
    reference_critical.write_results(critical, critical_path)

    selected = reference_appendix.build_results()
    reference_appendix.validate_results(selected)
    reference_appendix.write_results(selected, selected_path)

    generated_paths = (critical_path, selected_path)
    if check:
        try:
            for generated_path in generated_paths:
                compare_with_reference(generated_path)
        except ReproductionMismatch:
            report_path.write_text(
                "# Computational companion report\n\n"
                "**Run status: FAIL**\n\n"
                "Generated tables differ from the frozen references.\n",
                encoding="utf-8",
            )
            raise

    write_summary_figure(critical, selected, figure_png, figure_svg)
    write_report(critical, selected, report_path, checked=check)

    all_paths = (
        critical_path,
        selected_path,
        report_path,
        figure_png,
        figure_svg,
    )
    return ReproductionResult(
        output_dir=resolved_output,
        checked=check,
        files=tuple((path.name, sha256(path)) for path in all_paths),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "generated_results",
        help="directory for newly generated tables, report, and figures",
    )
    parser.add_argument(
        "--skip-reference-check",
        action="store_true",
        help="generate and validate results without comparing committed tables",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the source-checkout reproduction script."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_reproduction(
            args.output_dir,
            check=not args.skip_reference_check,
        )
    except ValueError as error:
        parser.error(str(error))
    except ReproductionMismatch as error:
        parser.exit(1, f"FAIL: {error}\n")
    print("PASS: all calculation checks completed")
    if result.checked:
        print("PASS: generated tables agree with committed reference results")
    for name, digest in result.files[:2]:
        print(f"{name}: sha256={digest}")
    print(f"report: {result.output_dir / 'REPORT.md'}")
    print(f"figure: {result.output_dir / 'companion_summary.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
