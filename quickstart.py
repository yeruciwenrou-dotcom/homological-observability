#!/usr/bin/env python3
"""Create a local environment and reproduce the companion results."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENVIRONMENT = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
PROJECT = ROOT / "pyproject.toml"
STAMP_FILE = ENVIRONMENT / ".homological-observability-quickstart"


def environment_python() -> Path:
    if os.name == "nt":
        return ENVIRONMENT / "Scripts" / "python.exe"
    return ENVIRONMENT / "bin" / "python"


def _environment_version(python: Path) -> tuple[int, int]:
    completed = subprocess.run(
        [
            str(python),
            "-c",
            "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    major, minor = completed.stdout.strip().split(".")
    return int(major), int(minor)


def ensure_environment() -> Path:
    python = environment_python()
    if not python.is_file():
        print("Creating .venv ...", flush=True)
        venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)
        python = environment_python()
    else:
        try:
            version = _environment_version(python)
        except (OSError, subprocess.CalledProcessError, ValueError):
            version = None
        if version != sys.version_info[:2]:
            print(
                "Recreating .venv for the active Python version ...",
                flush=True,
            )
            venv.EnvBuilder(with_pip=True, clear=True).create(ENVIRONMENT)
            python = environment_python()
    return python


def _dependency_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (REQUIREMENTS, PROJECT):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_dependencies(python: Path) -> None:
    fingerprint = _dependency_fingerprint()
    current = (
        STAMP_FILE.read_text(encoding="utf-8").strip() if STAMP_FILE.is_file() else ""
    )
    if current == fingerprint:
        print("Reusing the pinned quickstart environment.", flush=True)
        return

    print("Installing pinned dependencies ...", flush=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", REQUIREMENTS.name],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", "-e", "."],
        cwd=ROOT,
        check=True,
    )
    STAMP_FILE.write_text(f"{fingerprint}\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Set up and verify the homological-observability companion."
    )
    parser.add_argument(
        "--reproduce-only",
        action="store_true",
        help="skip the independent tests and only regenerate the scientific results",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if sys.version_info[:2] not in {(3, 11), (3, 12), (3, 13)}:
        raise SystemExit("Python 3.11, 3.12, or 3.13 is required.")

    python = ensure_environment()
    ensure_dependencies(python)

    if not arguments.reproduce_only:
        print("Running the independent test suite ...", flush=True)
        subprocess.run(
            [
                str(python),
                "-W",
                "error",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-v",
            ],
            cwd=ROOT,
            check=True,
        )

    subprocess.run(
        [str(python), "-W", "error", "reproduce_all.py"],
        cwd=ROOT,
        check=True,
    )
    print(
        "\nOpen generated_results/REPORT.md for the scientific summary.",
        flush=True,
    )
    print(
        "Open generated_results/companion_summary.png for the summary figure.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        command = " ".join(str(part) for part in error.cmd)
        print(
            f"Verification stopped: command exited with {error.returncode}: {command}",
            file=sys.stderr,
        )
        raise SystemExit(error.returncode) from None
