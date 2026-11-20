"""Editable examples, readable results and replay bundles for finite records."""

import json
from importlib import resources
from pathlib import Path

from ._integer_io import parse_json_integer
from .applications._dfr_data import dfr_model, load_dataset, rate_matrix
from .serialization import cochains_to_dict, model_to_dict
from .target_io import target_json


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
            lines.append(f"Most probable target: {candidates} {unit}")
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
        if "reason" in r["diagnostics"]:
            lines.append(f"Reason: {r['diagnostics']['reason']}")
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
        for p in r["protocols"]:
            risk = p["mean_risk"]
            diff = p["mean_risk_difference"]
            mean = (
                f"{risk:.4%}" if risk is not None else f"bounds {p['mean_risk_bounds']}"
            )
            delta = (
                f"{100 * diff:+.3f} percentage points"
                if diff is not None
                else f"bounds {p['paired_difference_bounds']}"
            )
            lines.append(
                f"{p['name']}: risk {mean}, difference {delta}, {p['snapshots_per_record']} snapshots, "
                f"{p['counters_per_record']} counters, {p['mean_encoded_bytes']:.1f} mean bytes, "
                f"{p['resolved']}/{p['trajectories']} resolved"
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
        + f"\nReplay: homological-observability {command} request.json\n",
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
