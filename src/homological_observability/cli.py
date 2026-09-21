"""Command-line interface for topology, critical experiments, and evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .analysis import AnalysisStatus, analyze_model
from .critical_experiment import (
    CriticalStatus,
    analyze_critical_model,
    load_critical_model,
    render_critical_json,
    render_critical_text,
)
from .examples import examples_to_dict, load_example
from .model import load_model
from .reproduction import ReproductionMismatch, run_reproduction
from .serialization import ArtifactRole, render_json, render_text
from .version import __version__

EXIT_SUCCESS = 0
EXIT_INCOMPLETE = 1
EXIT_ERROR = 2


def _add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homological-observability",
        description=(
            "Exact integer homology filtrations, critical-limit experiments, "
            "and frozen paper-evidence checks."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    examples_parser = commands.add_parser(
        "examples", help="list built-in analysis examples"
    )
    _add_format(examples_parser)

    example_parser = commands.add_parser(
        "example", help="run one built-in analysis example"
    )
    example_parser.add_argument("name", help="example registry name")
    _add_format(example_parser)

    analyze_parser = commands.add_parser(
        "analyze", help="analyze a user-supplied JSON model"
    )
    analyze_parser.add_argument("model", type=Path, help="path to a model JSON file")
    _add_format(analyze_parser)

    critical_parser = commands.add_parser(
        "critical", help="construct a critical-limit experiment from a rate model"
    )
    critical_parser.add_argument(
        "model", type=Path, help="path to a critical-model JSON file"
    )
    _add_format(critical_parser)

    reproduce_parser = commands.add_parser(
        "reproduce", help="regenerate the finite-cycle paper evidence"
    )
    reproduce_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "generated_results",
        help="destination for generated tables, report, and figures",
    )
    reproduce_parser.add_argument(
        "--check",
        action="store_true",
        help="compare generated tables with the packaged frozen references",
    )
    _add_format(reproduce_parser)
    return parser


def _emit_error(message: str, *, output_format: str) -> int:
    if output_format == "json":
        payload: dict[str, Any] = {
            "schema_name": "homological-observability.error",
            "schema_version": 1,
            "status": "ERROR",
            "message": message,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(f"error: {message}", file=sys.stderr)
    return EXIT_ERROR


def _run_examples(output_format: str) -> int:
    document = examples_to_dict()
    if output_format == "json":
        print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for example in document["examples"]:
            print(f"{example['name']} [{example['category']}]: {example['title']}")
            print(f"  {example['description']}")
    return EXIT_SUCCESS


def _run_analysis(model, *, role: ArtifactRole, output_format: str) -> int:
    result = analyze_model(model)
    if output_format == "json":
        sys.stdout.write(render_json(result, artifact_role=role))
    else:
        sys.stdout.write(render_text(result, artifact_role=role))
    return (
        EXIT_INCOMPLETE
        if result.status is AnalysisStatus.LIMIT_REACHED
        else EXIT_SUCCESS
    )


def _run_reproduction(arguments: argparse.Namespace) -> int:
    try:
        result = run_reproduction(arguments.output_dir, check=arguments.check)
    except ReproductionMismatch as error:
        if arguments.format == "json":
            print(
                json.dumps(
                    {
                        "schema_name": "homological-observability.reproduction",
                        "schema_version": 1,
                        "artifact_role": "canonical-paper-evidence",
                        "status": "FAIL",
                        "message": str(error),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            print(f"FAIL: {error}", file=sys.stderr)
        return EXIT_INCOMPLETE
    if arguments.format == "json":
        print(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("PASS: all calculation checks completed")
        if result.checked:
            print("PASS: generated tables agree with frozen reference results")
        print(f"output directory: {result.output_dir}")
    return EXIT_SUCCESS


def _run_critical(model, *, output_format: str) -> int:
    result = analyze_critical_model(model)
    if output_format == "json":
        sys.stdout.write(render_critical_json(result))
    else:
        sys.stdout.write(render_critical_text(result))
    return (
        EXIT_INCOMPLETE
        if result.status is CriticalStatus.LIMIT_REACHED
        else EXIT_SUCCESS
    )


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return its documented process exit code."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "examples":
            return _run_examples(arguments.format)
        if arguments.command == "example":
            return _run_analysis(
                load_example(arguments.name),
                role=ArtifactRole.BUILTIN_EXAMPLE,
                output_format=arguments.format,
            )
        if arguments.command == "analyze":
            return _run_analysis(
                load_model(arguments.model),
                role=ArtifactRole.FRESH_ANALYSIS,
                output_format=arguments.format,
            )
        if arguments.command == "critical":
            return _run_critical(
                load_critical_model(arguments.model),
                output_format=arguments.format,
            )
        if arguments.command == "reproduce":
            return _run_reproduction(arguments)
    except (OSError, TypeError, ValueError) as error:
        return _emit_error(str(error), output_format=arguments.format)
    except (ArithmeticError, AssertionError) as error:
        if arguments.command != "critical":
            raise
        return _emit_error(
            f"critical experiment exactness check failed: {error}",
            output_format=arguments.format,
        )
    raise AssertionError(f"unhandled command: {arguments.command}")


if __name__ == "__main__":
    raise SystemExit(main())
