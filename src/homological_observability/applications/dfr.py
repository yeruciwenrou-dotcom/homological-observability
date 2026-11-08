"""CPU application: paired DFR data, structural audit and user prediction replay.

Run ``python -m homological_observability.applications.dfr --help``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from ..design import design_readouts
from ..target import analyze_target, evaluate_target
from ._dfr_data import (
    SCHEMES,
    dfr_model,
    feature_view,
    generate_dataset,
    json_bytes,
    load_dataset,
)
from ._dfr_predictions import (
    constant_predictions,
    evaluate_predictions,
    make_predictions,
)

__all__ = [
    "generate_dataset",
    "load_dataset",
    "feature_view",
    "make_predictions",
    "evaluate_predictions",
    "constant_predictions",
    "run_case",
]


def run_case(dataset):
    """Use visible inputs for reconstruction, and join separate truth only to score."""
    audits = {}
    reconstructions = {}
    for scheme in SCHEMES:
        model, targets = dfr_model(scheme)
        model = replace(
            model,
            observation_time=dataset["manifest"]["grid"][-1],
            sampling_interval=dataset["manifest"]["grid"][1],
        )
        audits[scheme] = analyze_target(model, targets, explain=True)
        by_id = {
            row["trajectory_id"]: row["DeltaW"]
            for row in dataset["files"]["natural-labels.json"]["rows"]
        }
        exact = []
        if audits[scheme]["result"]["sufficient"]:
            for row in dataset["files"][f"natural-inputs-{scheme}.json"]["rows"]:
                result = evaluate_target(
                    model,
                    targets,
                    row["readouts"],
                    start=row["snapshots"][0],
                    end=row["snapshots"][-1],
                )
                if (
                    result["status"] != "COMPLETE"
                    or result["result"]["target_values"] is None
                ):
                    raise AssertionError(
                        "sufficient DFR scheme did not reconstruct a legal record"
                    )
                value = result["result"]["target_values"]["DeltaW"]
                exact.append(
                    {
                        "trajectory_id": row["trajectory_id"],
                        "target": value,
                        "truth": by_id[row["trajectory_id"]],
                    }
                )
        reconstructions[scheme] = {
            "count": len(exact),
            "mismatches": sum(r["target"] != r["truth"] for r in exact),
            "records": exact,
        }
    model, targets = dfr_model("w")
    model = replace(
        model,
        observation_time=dataset["manifest"]["grid"][-1],
        sampling_interval=dataset["manifest"]["grid"][1],
    )
    all_model, _ = dfr_model("all")
    design = design_readouts(model, targets, all_model.readouts[1:], explain=True)
    predictions = constant_predictions(dataset)
    pressure_predictions = constant_predictions(
        dataset, split="pressure", cohort="pressure"
    )
    return {
        "schema_name": "homological-observability.dfr-case",
        "protocol_version": 1,
        "dataset_id": dataset["manifest"]["dataset_id"],
        "audits": audits,
        "design": design,
        "paired_reconstruction": reconstructions,
        "natural_prediction_evaluation": evaluate_predictions(dataset, predictions),
        "pressure_prediction_evaluation": evaluate_predictions(
            dataset, pressure_predictions
        ),
        "prediction_template": predictions,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser(
        "generate", help="generate a source-bound known-Q dataset"
    )
    generate.add_argument("--output-dir", type=Path, required=True)
    generate.add_argument("--trajectories", type=int, default=64)
    generate.add_argument("--seed", type=int, default=20261108)
    generate.add_argument("--split-seed", type=int, default=731)
    run = sub.add_parser("run", help="audit, design, reconstruct and evaluate the case")
    run.add_argument(
        "--dataset", type=Path, help="omit to use the bundled fixed dataset"
    )
    run.add_argument("--output-dir", type=Path, required=True)
    evaluate = sub.add_parser("evaluate", help="evaluate your versioned predictions")
    evaluate.add_argument("predictions", type=Path)
    evaluate.add_argument("--dataset", type=Path)
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            result = generate_dataset(
                args.output_dir,
                trajectories=args.trajectories,
                seed=args.seed,
                split_seed=args.split_seed,
            )
            print(
                f"Generated {result['config']['trajectories']} paired trajectories: {result['dataset_id']}"
            )
        elif args.command == "run":
            if args.output_dir.exists():
                raise FileExistsError("case output directory already exists")
            dataset = load_dataset(args.dataset)
            result = run_case(dataset)
            args.output_dir.mkdir(parents=True)
            (args.output_dir / "case.json").write_bytes(json_bytes(result))
            (args.output_dir / "predictions.json").write_bytes(
                json_bytes(result["prediction_template"])
            )
            report = [
                "DFR research case",
                f"Dataset: {result['dataset_id']}",
                f"Minimum added channels for DeltaW: {result['design']['result']['minimum_added']}",
            ]
            for scheme, record in result["paired_reconstruction"].items():
                report.append(
                    f"{scheme}: reconstructed {record['count']}; mismatches {record['mismatches']}"
                )
            for cohort in ("natural", "pressure"):
                evaluation = result[f"{cohort}_prediction_evaluation"]
                report.append(
                    f"{cohort}: training-median MAE {evaluation['raw']['mae']}; exact match {evaluation['raw']['exact_match_accuracy']}"
                )
            report.append(
                "Natural sampling and the constructed equal-weight pressure set are separate populations."
            )
            (args.output_dir / "report.txt").write_text(
                "\n".join(report) + "\n", encoding="utf-8"
            )
            print("\n".join(report))
        else:
            if args.output.exists():
                raise FileExistsError("evaluation output already exists")
            result = evaluate_predictions(
                load_dataset(args.dataset),
                json.loads(args.predictions.read_text(encoding="utf-8")),
            )
            with args.output.open("xb") as stream:
                stream.write(json_bytes(result))
            print(
                f"Evaluated {result['raw']['count']} predictions; MAE={result['raw']['mae']}"
            )
    except (OSError, TypeError, ValueError, ArithmeticError) as error:
        parser.exit(2, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
