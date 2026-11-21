"""Editable examples, readable results and replay bundles for finite records."""

import json
from importlib import resources
from pathlib import Path

from ._integer_io import parse_json_integer
from .applications._dfr_data import dfr_model, load_dataset, rate_matrix
from .serialization import cochains_to_dict, model_to_dict
from .target_io import target_json

FINITE_RECORD_GUIDE = (
    "https://github.com/yeruciwenrou-dotcom/homological-observability/blob/"
    "v2.2.0/docs/FINITE_RECORDS.md"
)


def recording_example(command, example):
    """Return an ordinary request suitable for editing and re-running."""
    if example == "kinesin" and command == "posterior":
        return json.loads(
            resources.files("homological_observability")
            .joinpath("data", "examples", "kinesin_record.json")
            .read_text(encoding="utf-8")
        )
    if example == "triangle":
        base = json.loads(
            resources.files("homological_observability")
            .joinpath("data", "examples", "triangle_record.json")
            .read_text(encoding="utf-8")
        )
        if command == "posterior":
            return base
        base.pop("record")
        base["model"]["readouts"] = [dict(base["target"], name="turn_counter")]
        base.update(
            horizon=1.0,
            protocols=[
                {"name": "endpoints", "snapshots": 2, "channels": []},
                {"name": "counted", "snapshots": 2, "channels": ["turn_counter"]},
            ],
            source={
                "kind": "simulate",
                "initial_distribution": {"a": 1, "b": 0, "c": 0},
                "trajectories": 32,
                "seed": 27,
            },
        )
        return base
    if example != "dfr":
        raise ValueError("example must be triangle or dfr")
    model, targets = dfr_model("w" if command == "posterior" else "w-on")
    q = rate_matrix()
    dataset = load_dataset()
    base = {
        "schema_version": 1,
        "model": model_to_dict(model),
        "target": cochains_to_dict(targets)[0],
        "time_unit": "model time",
        "target_unit": "turn",
        "rates": [
            {"from": u, "to": v, "rate": float(q[i, j])}
            for i, u in enumerate(model.vertices)
            for j, v in enumerate(model.vertices)
            if i != j and q[i, j] > 0
        ],
    }
    data = dataset["files"]
    if command == "posterior":
        row = data["natural-inputs-w.json"]["rows"][0]
        base["record"] = {
            "times": dataset["manifest"]["grid"],
            "states": row["snapshots"],
            "counts": row["readouts"],
        }
    else:
        base.update(
            horizon=dataset["manifest"]["grid"][-1],
            protocols=[
                {"name": name, "snapshots": 8, "channels": channels}
                for name, channels in [
                    ("snapshots", []),
                    ("with-W", ["W"]),
                    ("with-W-and-W_ON", ["W", "W_ON"]),
                ]
            ],
            source={
                "kind": "events",
                "name": "DFR natural " + dataset["manifest"]["dataset_id"],
                "trajectories": [
                    {k: p[k] for k in ("trajectory_id", "states", "times")}
                    for p in data["natural-events.json"]["rows"]
                ],
            },
        )
    return base


def load_record_request(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8"), parse_int=parse_json_integer
    )


def render_record_result(doc):
    r = doc["result"]
    unit = doc["request"]["target_unit"]
    lines = [f"Target: {r['target']} ({unit})", f"Status: {doc['status']}"]
    if "outcome" in r:
        lines.append(f"Record: {r['outcome']}")
        support = r["target_support"]
        if support and support["step"] != 0:
            lines.append(f"Integer support: {support['offset']} + {support['step']} Z")
        if r["map_risk"] is not None:
            candidates = ", ".join(str(v) for v in r["map_candidates"])
            if r["outcome"] == "EXACT":
                label = "Exact target"
            elif len(r["map_candidates"]) > 1:
                label = "Possible most-probable targets at this precision"
            else:
                label = "Most probable target"
            lines.append(f"{label}: {candidates} {unit}")
            lines.append(f"Conditional 0-1 error risk: {r['map_risk']:.8g}")
            if r["outcome"] == "NUMERICAL_POSTERIOR":
                top = sorted(r["pmf"], key=lambda item: -item["probability"])[:5]
                lines.append(
                    "Leading probabilities: "
                    + ", ".join(
                        f"P({item['value']})={item['probability']:.8g}" for item in top
                    )
                )
            for name, value in r["set_probabilities"].items():
                lines.append(f"P({name}) = {value:.8g}")
        reason = r["diagnostics"].get("reason")
        # Rates and rank have their own instructions below.
        if reason and doc["status"] not in ("RATES_REQUIRED", "UNSUPPORTED_RANK"):
            reason_text = {
                "fourier_grid_budget": "The Fourier grid exceeds a size limit. Check limits.max_grid_points and limits.max_matrix_entries in the request.",
                "rate_matrix_budget": "The rate matrix exceeds limits.max_matrix_entries.",
                "nonzero_count_at_zero_duration": "A record with zero duration has a nonzero count. Check the observation times and the recorded counts.",
                "record_outside_integer_image": "The recorded counts fall outside the integer image of the model's readouts.",
                "matrix_exponential_failed": "The matrix exponential calculation failed for this sampling interval.",
                "nonfinite_matrix_exponential": "The matrix exponential produced nonfinite entries.",
                "stiff_window_exceeds_numerical_range": "The rates and sampling interval place this window outside the solver's numerical range.",
                "snapshot_endpoint_mass_unresolved": "The probability of the observed endpoint pair is unresolved at this precision.",
                "tilted_endpoint_mass_unresolved": "The tilted transition calculation could not resolve the endpoint weight.",
                "snapshot_conditioning_below_precision": "The probability of the observed snapshots falls below the working precision.",
                "bridge_characteristic_precision": "The conditional Fourier calculation reached its precision limit.",
                "nonfinite_probability_mass": "The computed probability mass has a nonfinite value.",
                "cumulative_count_below_precision": "The probability of the recorded counts falls below the working precision.",
                "cooperative_seconds": "The exact integer calculation reached its time limit.",
                "integer_bits": "The exact integer calculation reached its bit-length limit.",
                "matrix_entries": "The exact integer calculation reached its matrix-size limit.",
            }
            lines.append(reason_text.get(reason, "Reason: " + reason.replace("_", " ")))
        if doc["status"] in ("RATES_REQUIRED", "UNSUPPORTED_RANK"):
            lines.append(
                "This record satisfies the integer constraints. "
                "Use the integer support above to identify its possible target values."
            )
            if doc["status"] == "RATES_REQUIRED":
                lines.extend(
                    [
                        "To estimate probabilities, supply a finite positive rate for "
                        "each direction of every support edge.",
                        "In 'rates', use the model's state labels for 'from' and 'to'. "
                        f"Give each 'rate' in inverse units of {doc['request']['time_unit']!r}.",
                    ]
                )
                section = "use-your-own-model"
            else:
                lines.append(
                    "The target and all observed counters have effective joint rank "
                    f"{r['joint_rank']}. The numerical solver supports rank up to 2."
                )
                section = "interpreting-a-posterior"
            lines.append(f"Finite-record guide: {FINITE_RECORD_GUIDE}#{section}")
        if "failed_count_constraint" in r:
            failed = r["failed_count_constraint"]
            rule = f"a multiple of {failed['modulus']}" if failed["modulus"] else "zero"
            lines.append(
                f"Integer constraint on corrected counts: weights {failed['weights']} give {failed['observed']}; expected {rule}."
            )

    else:
        lines.extend(
            [
                f"Paired trajectories: {len(r['trajectory_ids'])} ({r['sample_kind']})",
                f"Risk differences use protocol minus baseline ({r['baseline']}).",
            ]
        )
        if r["sample_kind"] == "independent_simulation":
            lines.append(
                "Sampling coverage is per comparison, conditional on the numerical risk estimates."
            )
        else:
            lines.append("Risk differences describe this fixed set of event paths.")
        threshold = doc["request"].get("risk_threshold")
        if threshold is not None:
            lines.append(f"Threshold for the sample mean risk: {threshold}")
        if doc["status"] == "PARTIAL":
            lines.append(
                "The sample mean risk bounds include all trajectories, with [0, 1] "
                "for each unresolved risk."
            )
        for p in r["protocols"]:
            risk = p["mean_risk"]
            diff = p["mean_risk_difference"]
            mean = (
                f"{risk:.4%}"
                if risk is not None
                else f"bounds {json.dumps(p['mean_risk_bounds'])}"
            )
            delta = (
                f"{100 * diff:+.3f} percentage points"
                if diff is not None
                else f"bounds {json.dumps(p['paired_difference_bounds'])}"
            )
            lines.append(
                f"{p['name']}: risk {mean}, difference {delta}, {p['snapshots_per_record']} snapshots, "
                f"{p['counters_per_record']} counters, {p['mean_encoded_bytes']:.1f} mean bytes, "
                f"{p['resolved']}/{p['trajectories']} resolved"
            )
            interval = p.get("expected_difference_interval_95")
            if interval is not None:
                lines.append(
                    "  95% Hoeffding sampling interval for the expected risk difference "
                    f"(risk units): {json.dumps(interval)}"
                )
            threshold_status = p.get("sample_risk_threshold_status")
            if threshold_status is not None:
                lines.append(
                    f"  Sample mean risk bounds {json.dumps(p['mean_risk_bounds'])}: {threshold_status}"
                )
    lines.append(f"Replay request SHA-256: {doc['request_sha256']}")
    return "\n".join(lines) + "\n"


def write_record_bundle(doc, output, command):
    # Finish serialization before creating the directory. A failed writer removes
    # only files it successfully created; a competing writer cannot own this dir.
    directory = Path(output)
    files = {
        "request.json": target_json(doc["request"]),
        "result.json": target_json(doc),
        "report.txt": render_record_result(doc)
        + f"\nReplay from this results directory:\nhomological-observability {command} request.json\n",
    }
    directory.mkdir(parents=True, exist_ok=False)
    created = []
    try:
        for name, contents in files.items():
            path = directory / name
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(contents)
    except OSError:
        for path in created:
            path.unlink(missing_ok=True)
        directory.rmdir()
        raise
