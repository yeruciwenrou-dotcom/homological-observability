#!/usr/bin/env python3
"""Regenerate or verify reader-visible example result artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import homological_observability as ho

ROOT = Path(__file__).resolve().parents[1]
FROZEN_MARKDOWN_SHA256 = (
    "4633502da1a52be11a890474cdc15430950c3e3311c15277f915ceb4cefd8804"
)


def expected_artifacts() -> dict[Path, str]:
    topology_result = ho.analyze_model(ho.load_example("wedge-c3-c5"))
    critical_result = ho.analyze_critical_model(
        ho.load_critical_model(ROOT / "examples/biased_c4_critical.json")
    )
    role = ho.ArtifactRole.BUILTIN_EXAMPLE
    return {
        ROOT / "examples/wedge_c3_c5_result.json": ho.render_json(
            topology_result,
            artifact_role=role,
        ),
        ROOT / "examples/wedge_c3_c5_result.md": ho.render_markdown(
            topology_result,
            artifact_role=role,
        ),
        ROOT / "examples/biased_c4_critical_result.json": (
            ho.render_critical_json(critical_result)
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if committed artifacts differ instead of rewriting them",
    )
    arguments = parser.parse_args(argv)
    if not arguments.check and ho.__version__ != "1.1.0":
        parser.error(
            "these archived examples belong to software 1.1.0; use that version "
            "to regenerate them, or --check to compare a later implementation"
        )

    artifacts = expected_artifacts()
    mismatches: list[Path] = []
    for path, expected in artifacts.items():
        if arguments.check:
            if not path.is_file():
                mismatches.append(path)
                continue
            frozen = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                original = json.loads(frozen)
                current = json.loads(expected)
                if original["software"].pop("version") != "1.1.0":
                    mismatches.append(path)
                    continue
                if current["software"].pop("version") != ho.__version__:
                    mismatches.append(path)
                    continue
                if path.name == "wedge_c3_c5_result.json":
                    # Check each record's own identity before comparing the
                    # scientific content across the explicit format transition.
                    for record in (original, current):
                        canonical = json.dumps(
                            record["model"],
                            ensure_ascii=False,
                            allow_nan=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        if (
                            record.pop("normalized_model_sha256")
                            != hashlib.sha256(canonical).hexdigest()
                        ):
                            raise AssertionError("example model digest is inconsistent")
                    if (
                        original["schema_version"] != 2
                        or original["model"]["schema_version"] != 1
                    ):
                        raise AssertionError("unexpected archived example format")
                    if (
                        current["schema_version"] != 3
                        or current["model"]["schema_version"] != 2
                    ):
                        raise AssertionError("unexpected current example format")
                    original["schema_version"] = 3
                    original["model"]["schema_version"] = 2
                if original != current:
                    mismatches.append(path)
            elif (
                hashlib.sha256(path.read_bytes()).hexdigest() != FROZEN_MARKDOWN_SHA256
            ):
                # The archived 1.1.0 reading surface stays byte-identical. New
                # report behavior is exercised separately with current results.
                mismatches.append(path)
        else:
            path.write_text(expected, encoding="utf-8")

    if mismatches:
        formatted = ", ".join(str(path.relative_to(ROOT)) for path in mismatches)
        parser.error(f"frozen example artifacts are stale: {formatted}")
    action = "verified" if arguments.check else "regenerated"
    print(f"PASS: {action} {len(artifacts)} example result artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
