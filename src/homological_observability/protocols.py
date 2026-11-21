"""Paired comparison of declared recording protocols for a scalar path target."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from fractions import Fraction

import numpy as np

from ._observed_paths import observe_path, simulate_path
from ._record_inputs import (
    common_request,
    fields,
    number,
    result_document,
    text,
    time_coordinate,
)
from .comparison import _sha256
from .model import _array, _object
from .posterior import PosteriorSolver


def _protocols(raw, model):
    protocols = []
    names = set()
    available = {r.name for r in model.readouts}
    for item in _array(raw, label="protocols"):
        keys = ("name", "snapshots", "channels")
        fields(item, keys, keys, "protocol")
        name = text(item["name"], "protocol name")
        channels = _array(item["channels"], label="channels")
        snapshots = item["snapshots"]
        if name in names or type(snapshots) is not int or snapshots < 2:
            raise ValueError("protocols need unique names and at least two snapshots")
        if any(not isinstance(c, str) or c not in available for c in channels) or len(
            set(channels)
        ) != len(channels):
            raise ValueError("protocol channels must be distinct names from the model")
        protocols.append(dict(name=name, channels=list(channels), snapshots=snapshots))
        names.add(name)
    if not 2 <= len(protocols) <= 64:
        raise ValueError(
            "declare between 2 and 64 protocols; the first is the comparison baseline"
        )
    return protocols


def _snapshot_grid(horizon, count):
    """Round each exact sample once, so shared times agree across protocols."""
    step = Fraction(horizon) / (count - 1)
    if step.denominator == 1:
        return range(0, step.numerator * count, step.numerator)
    if horizon < (count - 1) * math.ulp(0.0):
        raise ValueError("the declared grid is unresolvable in the specified time unit")
    grid = []
    for i in range(count):
        numerator = i * step.numerator
        tick, remainder = divmod(numerator, step.denominator)
        if remainder == 0:
            grid.append(tick)
        else:
            point = numerator / step.denominator
            # Retain which side of an integer event this sample lies on.
            if point.is_integer():
                point = Fraction(numerator, step.denominator)
            grid.append(point)
    return grid


def _paths(raw, model, q, horizon, grid_total, limits):
    if not isinstance(raw, dict):
        raise TypeError("source must be an object")
    if raw.get("kind") == "events":
        keys = ("kind", "name", "trajectories")
        fields(raw, keys, keys, "event source")
        name = text(raw["name"], "source name")
        paths = _array(raw["trajectories"], label="trajectories")
        if not paths or len(paths) * grid_total > 2_000_000:
            raise ValueError(
                "the study needs at least one path and at most 2000000 projected snapshot states"
            )
        seen = set()
        validated = []
        for path in paths:
            keys = ("trajectory_id", "times", "states")
            fields(path, keys, keys, "event path")
            identity = text(path["trajectory_id"], "trajectory ID")
            if identity in seen:
                raise ValueError("duplicate trajectory ID")
            seen.add(identity)
            # Validate all events before any inference, including intermediate
            # jumps that will disappear from a coarser snapshot schedule.
            times = [
                time_coordinate(t, "event time")
                for t in _array(path["times"], label="times")
            ]
            states = _array(path["states"], label="states")
            if any(not isinstance(s, str) for s in states):
                raise TypeError("event states must be vertex names")
            row = {"trajectory_id": identity, "times": times, "states": list(states)}
            observe_path(row, [0.0, horizon], model)
            validated.append(row)
        return {"kind": "events", "name": name, "trajectories": validated}, validated
    if raw.get("kind") != "simulate":
        raise ValueError("source kind must be events or simulate")
    keys = ("kind", "trajectories", "initial_distribution", "seed")
    fields(raw, (*keys, "max_events_per_path"), keys, "simulation source")
    if q is None:
        raise ValueError("simulation requires directed rates")
    matrix = q.dense(limits.max_matrix_entries)
    if matrix is None:
        raise ValueError("simulation rate matrix exceeds max_matrix_entries")
    size, seed = raw["trajectories"], raw["seed"]
    cap = raw.get("max_events_per_path", 100000)
    if type(size) is not int or size < 1 or size * grid_total > 2_000_000:
        raise ValueError(
            "simulation needs at least one path and at most 2000000 projected snapshot states"
        )
    if (
        type(seed) is not int
        or not 0 <= seed < 2**63
        or type(cap) is not int
        or cap < 1
    ):
        raise ValueError(
            "simulation needs a 63-bit nonnegative seed and a positive event budget"
        )
    dist = _object(raw["initial_distribution"], label="initial distribution")
    if dist.keys() != set(model.vertices):
        raise ValueError("initial distribution must name every model state")
    probs = np.array([number(dist[v], "initial probability") for v in model.vertices])
    if (
        np.any(probs < 0)
        or np.any(probs > 1)
        or not math.isclose(float(probs.sum()), 1.0, abs_tol=1e-12, rel_tol=0)
    ):
        raise ValueError("initial probabilities must be nonnegative and sum to one")
    rng = np.random.Generator(np.random.PCG64(seed))
    law = probs / probs.sum()
    # Preserve the ensemble IDs of previously representable horizons.
    float_horizon = float(horizon)
    ensemble = _sha256(
        [
            "PCG64",
            model.vertices,
            float_horizon if horizon == float_horizon else horizon,
            [(u, v, rate) for (u, v), rate in q.rates.items()],
            law.tolist(),
            seed,
        ]
    )[:20]
    paths = [
        {
            "trajectory_id": f"{ensemble}-{i}",
            **simulate_path(
                matrix, law, horizon, rng, labels=model.vertices, max_events=cap
            ),
        }
        for i in range(size)
    ]
    return {
        "kind": "simulate",
        "trajectories": size,
        "initial_distribution": dict(zip(model.vertices, probs.tolist())),
        "seed": seed,
        "max_events_per_path": cap,
    }, paths


def _risk_interval(row):
    risk = row["map_risk"]
    if risk is None:
        return 0.0, 1.0
    err = row["conditional_error_indicator"]
    return max(0.0, risk - err), min(1.0, risk + err)


def compare_recording_protocols(request: dict) -> dict:
    """Compare matched 0–1 risks on event paths or an explicitly seeded ensemble.

    The baseline is the first declared protocol. Fixed event sets give descriptive
    differences. Independent simulations additionally give a conservative 95%
    Hoeffding interval for the expected paired difference.
    """
    normalized, model, target, q, limits = common_request(
        request,
        extra=("protocols", "source", "horizon", "risk_threshold"),
        required=("protocols", "source", "horizon"),
    )
    horizon = request["horizon"]
    if number(horizon, "horizon") <= 0:
        raise ValueError("horizon must be positive")
    protocols = _protocols(request["protocols"], model)
    normalized.update(horizon=horizon, protocols=protocols)
    threshold = request.get("risk_threshold")
    if "risk_threshold" in request:
        threshold = number(threshold, "risk threshold")
        if not 0 <= threshold <= 1:
            raise ValueError("risk threshold must lie in [0,1]")
        normalized["risk_threshold"] = threshold
    source, paths = _paths(
        request["source"],
        model,
        q,
        horizon,
        sum(p["snapshots"] for p in protocols),
        limits,
    )
    normalized["source"] = source
    simulated = source["kind"] == "simulate"
    rows = []
    summaries = []
    baseline = {}
    size = len(paths)
    complete = True
    by_name = {r.name: r for r in model.readouts}
    for idx, protocol in enumerate(protocols):
        selected = replace(
            model, readouts=tuple(by_name[name] for name in protocol["channels"])
        )
        grid = _snapshot_grid(horizon, protocol["snapshots"])
        dt = horizon / (len(grid) - 1)
        solver = PosteriorSolver(
            selected, target, q, limits, normalized["reverse_tree_order"]
        )
        risks = []
        deltas = []
        byte_counts = []
        paired_points = []
        resolved_risks = []
        for path in paths:
            view = observe_path(path, grid, selected)
            record = {
                "times": grid,
                "states": view["snapshots"],
                "counts": view["readouts"],
            }
            status, result = solver.solve(record, dt)
            if result["outcome"] == "IMPOSSIBLE_RECORD":
                raise AssertionError(
                    "a projected event path must be compatible with its exact counters"
                )
            identity = path["trajectory_id"]
            # The schedule and channel definitions are shared metadata. Charge
            # the canonical UTF-8 JSON payload of states and signed counts.
            payload = {"states": record["states"], "counts": record["counts"]}
            encoded = json.dumps(
                payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            risk = result["map_risk"]
            row = {
                "trajectory_id": identity,
                "protocol": protocol["name"],
                "status": status,
                "observation": payload,
                "encoded_bytes": len(encoded),
                "map_risk": risk,
                "map_candidates": result["map_candidates"],
                "diagnostics": result["diagnostics"],
                "conditional_error_indicator": result["diagnostics"].get(
                    "conditional_error_indicator", 0.0 if risk is not None else None
                ),
            }
            rows.append(row)
            bounds = _risk_interval(row)
            risks.append(bounds)
            if idx == 0:
                baseline[identity] = (bounds, risk)
            base, base_point = baseline[identity]
            # Identical baseline paired with itself has exactly zero difference.
            deltas.append(
                (bounds[0] - base[1], bounds[1] - base[0]) if idx else (0.0, 0.0)
            )
            if risk is None:
                complete = False
            else:
                resolved_risks.append(risk)
            if idx == 0 or (risk is not None and base_point is not None):
                paired_points.append(0.0 if idx == 0 else risk - base_point)
            byte_counts.append(len(encoded))
        bounds = [sum(x) / size for x in zip(*risks)]
        paired = [sum(x) / size for x in zip(*deltas)]
        summary = {
            "name": protocol["name"],
            "trajectories": size,
            "resolved": len(resolved_risks),
            "coverage": len(resolved_risks) / size,
            "mean_risk": sum(resolved_risks) / size
            if len(resolved_risks) == size
            else None,
            "mean_risk_bounds": bounds,
            "mean_risk_difference": sum(paired_points) / size
            if len(paired_points) == size
            else None,
            "paired_difference_bounds": paired,
            "expected_difference_interval_95": None,
            "snapshots_per_record": len(grid),
            "counters_per_record": len(selected.readouts),
            "mean_encoded_bytes": sum(byte_counts) / size,
        }
        if simulated:
            margin = math.sqrt(2 * math.log(40) / size)
            summary["expected_difference_interval_95"] = (
                [max(-1.0, paired[0] - margin), min(1.0, paired[1] + margin)]
                if idx
                else [0.0, 0.0]
            )
        if threshold is not None:
            summary["sample_risk_threshold_status"] = (
                "MET"
                if bounds[1] <= threshold
                else "EXCEEDED"
                if bounds[0] > threshold
                else "UNRESOLVED"
            )
        summaries.append(summary)
    return result_document(
        "recording-protocol-comparison",
        normalized,
        "COMPLETE" if complete else "PARTIAL",
        {
            "target": target.name,
            "baseline": protocols[0]["name"],
            "loss": "zero_one",
            "difference": "protocol_minus_baseline",
            "sample_kind": "independent_simulation"
            if simulated
            else "fixed_event_paths",
            "encoded_bytes": "compact UTF-8 JSON of states and counts; shared schedule excluded",
            "trajectory_ids": [p["trajectory_id"] for p in paths],
            "event_paths_sha256": _sha256(paths),
            "protocols": summaries,
            "rows": rows,
        },
    )
