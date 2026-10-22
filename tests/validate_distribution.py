#!/usr/bin/env python3
"""Build and smoke-test wheel and sdist outside the repository tree."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def environment_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def smoke_artifact(artifact: Path, workspace: Path) -> None:
    label = "wheel" if artifact.suffix == ".whl" else "sdist"
    environment = workspace / f"{label}-environment"
    run_directory = workspace / f"{label}-run"
    output_directory = run_directory / "evidence"
    run_directory.mkdir()
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment_python(environment)
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--constraint",
            str(ROOT / "requirements.txt"),
            str(artifact),
        ],
        check=True,
        cwd=run_directory,
    )

    location = subprocess.run(
        [
            str(python),
            "-c",
            "import homological_observability as h; print(h.__file__)",
        ],
        check=True,
        cwd=run_directory,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if str(ROOT) in location:
        raise AssertionError(f"{label} imported from the repository: {location}")

    # Exercise protection in the installed package, where no checkout results/
    # directory exists. A failed guard must be caught before reference writes.
    subprocess.run(
        [
            str(python),
            "-c",
            "from pathlib import Path\n"
            "import homological_observability as h\n"
            "from homological_observability.reproduction import run_reproduction\n"
            "root = Path(h.__file__).parent / 'data' / 'reference'\n"
            "before = {p.name: p.read_bytes() for p in root.iterdir()}\n"
            "try:\n"
            "    run_reproduction(root, check=True)\n"
            "except ValueError:\n"
            "    pass\n"
            "else:\n"
            "    raise AssertionError('installed references were writable outputs')\n"
            "import tempfile, os\n"
            "with tempfile.TemporaryDirectory() as directory:\n"
            "    target = Path(directory)\n"
            "    reference = root / 'critical_kernel_results.csv'\n"
            "    for link in (os.symlink, os.link):\n"
            "        alias = target / 'selected_appendix_checks.csv'\n"
            "        link(reference, alias)\n"
            "        try:\n"
            "            run_reproduction(target, check=True)\n"
            "        except ValueError:\n"
            "            pass\n"
            "        else:\n"
            "            raise AssertionError('installed reference alias was writable')\n"
            "        alias.unlink()\n"
            "assert before == {p.name: p.read_bytes() for p in root.iterdir()}\n"
            "assert 0 < h.poisson_averaged_binomial_map_bessel(1e10) < 1\n"
            "assert h.residue_probability(4, 2, 1e-160) == 1e-320\n"
            "assert h.ring_bridge_probability(1000, 500, 0, 0.3) == 0.5\n"
            "try:\n"
            "    h.IntegerReadout('h', ((('a', 'b'), 0.5),))\n"
            "except TypeError:\n"
            "    pass\n"
            "else:\n"
            "    raise AssertionError('installed constructor accepted a fraction')\n",
        ],
        check=True,
        cwd=run_directory,
    )

    example = subprocess.run(
        [
            str(python),
            "-m",
            "homological_observability.cli",
            "example",
            "wedge-c3-c5",
            "--format",
            "json",
        ],
        check=True,
        cwd=run_directory,
        capture_output=True,
        text=True,
    )
    document = json.loads(example.stdout)
    if document["status"] != "COMPLETE":
        raise AssertionError(f"{label} example did not complete")

    # Exercise the independent comparison product from each installed artifact.
    # This also catches missing study templates or schemas in wheel/sdist data.
    installed_contract = subprocess.run(
        [
            str(python),
            "-c",
            "import json; import homological_observability as h; "
            "study = h.load_study_example('bridge'); "
            "print(json.dumps({'study': study, 'result': h.compare_configurations(study), "
            "'study_schema': h.load_study_schema(), "
            "'comparison_schema': h.load_comparison_schema()}))",
        ],
        check=True,
        cwd=run_directory,
        capture_output=True,
        text=True,
    )
    contract = json.loads(installed_contract.stdout)
    Draft202012Validator(contract["study_schema"]).validate(contract["study"])
    Draft202012Validator(contract["comparison_schema"]).validate(contract["result"])
    study_path = run_directory / "study.json"
    subprocess.run(
        [
            str(python),
            "-m",
            "homological_observability.cli",
            "study-example",
            "bridge",
            "--output",
            str(study_path),
        ],
        check=True,
        cwd=run_directory,
        capture_output=True,
        text=True,
    )
    bundle = run_directory / "comparison"
    comparison = subprocess.run(
        [
            str(python),
            "-m",
            "homological_observability.cli",
            "compare",
            str(study_path),
            "--format",
            "json",
            "--output-dir",
            str(bundle),
        ],
        check=True,
        cwd=run_directory,
        capture_output=True,
        text=True,
    )
    if json.loads(comparison.stdout) != contract["result"]:
        raise AssertionError(f"{label} comparison CLI differs from the installed API")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest["bundle_status"] != "COMPLETE":
        raise AssertionError(f"{label} comparison export did not finish")
    subprocess.run(
        [
            str(python),
            "-m",
            "homological_observability.cli",
            "compare",
            "study.json",
            "--output-dir",
            "replay",
            "--format",
            "json",
        ],
        check=True,
        cwd=bundle,
        capture_output=True,
        text=True,
    )
    if (bundle / "comparison.json").read_bytes() != (
        bundle / "replay/comparison.json"
    ).read_bytes():
        raise AssertionError(f"{label} installed group replay changed its result")
    individual = subprocess.run(
        [
            str(python),
            "-m",
            "homological_observability.cli",
            "analyze",
            "models/config-mixed.json",
            "--format",
            "json",
        ],
        check=True,
        cwd=bundle,
        capture_output=True,
        text=True,
    )
    if json.loads(individual.stdout) != contract["result"]["results"]["mixed"]:
        raise AssertionError(f"{label} installed individual replay changed its result")

    critical_model = {
        "schema_version": 1,
        "name": "c3-installed-smoke",
        "vertices": ["v0", "v1", "v2"],
        "edges": [["v0", "v1"], ["v1", "v2"], ["v2", "v0"]],
        "readouts": [],
        "rates": [
            {"edge": [start, end], "rate": "1"}
            for start, end in (
                ("v0", "v1"),
                ("v1", "v0"),
                ("v1", "v2"),
                ("v2", "v1"),
                ("v2", "v0"),
                ("v0", "v2"),
            )
        ],
        "critical": {
            "layer": 2,
            "theta": "1",
            "limits": {
                "max_paths": 1000,
                "max_estimated_integer_digits": 1000,
                "max_integer_digits": 1000,
                "max_output_records": 1000,
                "max_cycles": 1000,
            },
            "audit_paths": False,
        },
    }
    critical_model_path = run_directory / "critical.json"
    critical_model_path.write_text(json.dumps(critical_model), encoding="utf-8")
    critical = subprocess.run(
        [
            str(python),
            "-m",
            "homological_observability.cli",
            "critical",
            str(critical_model_path),
            "--format",
            "json",
        ],
        check=True,
        cwd=run_directory,
        capture_output=True,
        text=True,
    )
    critical_document = json.loads(critical.stdout)
    if critical_document["status"] != "COMPLETE":
        raise AssertionError(f"{label} critical experiment did not complete")
    if critical_document["summary"]["common_total_intensity"] != "1":
        raise AssertionError(f"{label} critical experiment changed its exact weight")

    reproduction = subprocess.run(
        [
            str(python),
            "-m",
            "homological_observability.cli",
            "reproduce",
            "--check",
            "--output-dir",
            str(output_directory),
            "--format",
            "json",
        ],
        check=True,
        cwd=run_directory,
        capture_output=True,
        text=True,
    )
    reproduction_document = json.loads(reproduction.stdout)
    if reproduction_document["status"] != "PASS":
        raise AssertionError(f"{label} reference check did not pass")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir",
        type=Path,
        help="test existing wheel and sdist files without rebuilding",
    )
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        distribution = (
            arguments.dist_dir.resolve() if arguments.dist_dir else workspace / "dist"
        )
        if arguments.dist_dir is None:
            subprocess.run(
                [sys.executable, "-m", "build", "--outdir", str(distribution)],
                check=True,
                cwd=ROOT,
            )
        artifacts = sorted(distribution.iterdir())
        wheels = [path for path in artifacts if path.suffix == ".whl"]
        sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
        if len(artifacts) != 2 or len(wheels) != 1 or len(sdists) != 1:
            raise AssertionError(f"unexpected distribution artifacts: {artifacts!r}")
        smoke_artifact(wheels[0], workspace)
        smoke_artifact(sdists[0], workspace)
    print("PASS: wheel and sdist work outside the repository")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
