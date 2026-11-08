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


def _render_case_text(result):
    lines = ["DFR: recover DeltaW and evaluate predictions"]
    design = result["design"]["result"]
    if design["minimum_proven"]:
        count = design["minimum_added"]
        noun = "channel" if count == 1 else "channels"
        lines.append(
            f"With W already recorded, the minimum is {count} additional {noun}."
        )
    elif design["feasible"] is False:
        lines.append(
            "The candidate pool cannot determine DeltaW with W already recorded."
        )
    else:
        lines.append(
            "The minimum number of additional channels has not been established."
        )
    for solution in design["solutions"]:
        lines.append(
            "Add: " + (", ".join(solution["added_ids"]) or "no additional channel")
        )
    if not design["ties_complete"]:
        lines.append("Further choices may remain unsearched or unreturned.")
    lines.append(
        f"Design calculation: {result['design']['status']}; exposure explanation: {result['design']['explanation_status']}."
    )
    lines.extend(["", "Exact reconstruction from each observation scheme:"])
    for scheme, record in result["paired_reconstruction"].items():
        sufficient = result["audits"][scheme]["result"]["sufficient"]
        if sufficient is True:
            detail = f"reconstructed {record['count']} paths; mismatches {record['mismatches']}"
        elif sufficient is False:
            detail = "DeltaW is not determined; exact reconstruction is unavailable"
        else:
            detail = "target sufficiency is unresolved; exact reconstruction was not attempted"
        lines.append(f"  {scheme}: {detail}")
    lines.extend(["", "Training-median prediction baseline (W-only inputs):"])
    for cohort in ("natural", "pressure"):
        evaluation = result[f"{cohort}_prediction_evaluation"]["raw"]
        label = (
            "Natural test split" if cohort == "natural" else "Constructed pressure pair"
        )
        lines.append(
            f"  {label}: {evaluation['count']} paths; MAE {evaluation['mae']:.6g}; "
            f"exact-match accuracy {evaluation['exact_match_accuracy']:.6g}"
        )
    lines.extend(
        [
            "The pressure pair has identical visible inputs and distinct targets; its scores describe this constructed pair.",
            "",
            "case.json: full results, certificates and evaluation details.",
            "predictions.json: natural-test prediction template for evaluation replay.",
            f"Dataset: {result['dataset_id']}",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare DFR observation schemes, recover DeltaW and evaluate model predictions.",
        epilog="Tutorial and model sources: docs/SCIENTIFIC_ML.md.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser(
        "generate", help="simulate paired trajectories using the documented DFR rates"
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
            report = _render_case_text(result)
            (args.output_dir / "report.txt").write_text(report, encoding="utf-8")
            print(report, end="")
            print(f"Report: {args.output_dir / 'report.txt'}")
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
