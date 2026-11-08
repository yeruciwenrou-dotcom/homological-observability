#!/usr/bin/env python3
"""Reproducible target-task correctness, baseline and resource assessment."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import random
import re
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, replace
from fractions import Fraction
from importlib import metadata
from pathlib import Path
from unittest.mock import patch

import homological_observability as ho
from homological_observability import design
from homological_observability.applications import dfr
from homological_observability.applications._dfr_data import dfr_model

ROOT = Path(__file__).resolve().parents[1]
SEED = 621108


def rank(rows, width):
    """Fraction elimination on edge cochains, independent of cycle/Smith code."""
    rows = [[Fraction(x) for x in row] for row in rows]
    pivot = 0
    for column in range(width):
        found = next((i for i in range(pivot, len(rows)) if rows[i][column]), None)
        if found is None:
            continue
        rows[pivot], rows[found] = rows[found], rows[pivot]
        divisor = rows[pivot][column]
        rows[pivot] = [x / divisor for x in rows[pivot]]
        for i in range(pivot + 1, len(rows)):
            factor = rows[i][column]
            if factor:
                rows[i] = [x - factor * y for x, y in zip(rows[i], rows[pivot])]
        pivot += 1
        if pivot == len(rows):
            break
    return pivot


def edge_rows(model, readouts):
    return [[r.as_mapping().get(e, 0) for e in model.edges] for r in readouts]


def incidence(model):
    return [
        [int(v == node) - int(u == node) for u, v in model.edges]
        for node in model.vertices
    ]


def enough(model, targets, selected):
    # Cochains modulo gradients give a basis-free criterion on ker(incidence).
    rows = incidence(model) + edge_rows(model, (*model.readouts, *selected))
    return rank(rows, len(model.edges)) == rank(
        rows + edge_rows(model, targets), len(model.edges)
    )


def exhaustive(model, targets, pool):
    for size in range(len(pool) + 1):
        choices = [
            subset
            for subset in itertools.combinations(pool, size)
            if enough(model, targets, subset)
        ]
        if choices:
            return choices
    return []


def check_certificate(model, targets, document):
    certificate = document["result"]["certificate"]
    if certificate["kind"] == "ambiguity":
        chain = [row[0] for row in certificate["edge_chain"]["data"]]
        assert all(
            sum(x * y for x, y in zip(row, chain)) == 0 for row in incidence(model)
        )
        assert all(
            sum(x * y for x, y in zip(row, chain)) == 0
            for row in edge_rows(model, model.readouts)
        )
        change = [
            sum(x * y for x, y in zip(row, chain)) for row in edge_rows(model, targets)
        ]
        assert any(change)
        assert change == [row[0] for row in certificate["target_change"]["data"]]
    else:
        p = edge_rows(model, model.readouts)
        for row, target in zip(
            certificate["decoder"]["data"], edge_rows(model, targets)
        ):
            residual = [
                sum(Fraction(c) * p[i][j] for i, c in enumerate(row)) - target[j]
                for j in range(len(model.edges))
            ]
            assert (
                rank(incidence(model) + [residual], len(model.edges))
                == len(model.vertices) - 1
            )


def synthetic(beta, candidate_count, target_count=1, *, bits=1):
    """Labeled constructed triangles; these are not physical sensor models."""
    vertices = ["o"] + [f"v{i}-{j}" for i in range(beta) for j in (0, 1)]
    edges = [
        e
        for i in range(beta)
        for e in (("o", f"v{i}-0"), (f"v{i}-0", f"v{i}-1"), (f"v{i}-1", "o"))
    ]
    model = ho.GraphModel.create(
        name="constructed triangle family", vertices=vertices, edges=edges
    )
    scale = 1 << (bits - 1)
    pool = tuple(
        ho.IntegerReadout.from_mapping(
            f"channel-{i}", {(f"v{i % beta}-0", f"v{i % beta}-1"): scale}
        )
        for i in range(candidate_count)
    )
    targets = tuple(replace(pool[i], name=f"target-{i}") for i in range(target_count))
    return model, targets, pool


def correctness():
    rng = random.Random(SEED)
    cases = []
    model, targets = dfr_model("w")
    all_model, _ = dfr_model("all")
    cases += [("dfr-fixed", model, targets, all_model.readouts[1:])]
    cases += [("dfr-zero", replace(model, readouts=()), targets, all_model.readouts)]
    for name in ("bridge", "theta", "minimal"):
        model = ho.parse_model(ho.load_study_example(name)["model"])
        pool = tuple(
            ho.IntegerReadout.from_mapping(f"edge-{i}", {edge: 1})
            for i, edge in enumerate(model.edges[:6])
        )
        target = replace(
            next((row for row in pool if not enough(model, (row,), ())), pool[0]),
            name="cycle-target",
        )
        cases.append((name, model, (target,), pool))
    for i in range(24):
        beta = 1 + i % 4
        model, _, _ = synthetic(beta, beta)

        def cochain(name):
            return ho.IntegerReadout.from_mapping(
                name, {edge: rng.randrange(-2, 3) for edge in model.edges}
            )

        model = replace(
            model, readouts=tuple(cochain(f"fixed-{j}") for j in range(i % 3))
        )
        pool = tuple(cochain(f"candidate-{j}") for j in range(1 + i % 5))
        targets = tuple(cochain(f"target-{j}") for j in range(1 + i % 2))
        cases.append((f"generated-{i}", model, targets, pool))
    results = []
    for name, model, targets, pool in cases:
        expected = {
            tuple(r.name for r in group) for group in exhaustive(model, targets, pool)
        }
        for reverse in (False, True):
            document = ho.design_readouts(
                model, targets, pool, reverse_tree_order=reverse
            )
            assert document["status"] == "COMPLETE", name
            result = document["result"]
            actual = {tuple(s["added_ids"]) for s in result["solutions"]}
            assert actual == expected, (name, actual, expected)
            assert result["feasible"] == bool(expected)
            assert result["minimum_added"] == (
                len(next(iter(expected))) if expected else None
            )
            diagnosis = ho.analyze_target(model, targets, reverse_tree_order=reverse)
            assert diagnosis["result"]["sufficient"] == enough(model, targets, ())
            check_certificate(model, targets, diagnosis)
            for solution in result["solutions"]:
                selected = tuple(r for r in pool if r.name in solution["added_ids"])
                augmented = replace(model, readouts=(*model.readouts, *selected))
                check_certificate(augmented, targets, {"result": solution})
        results.append(
            {"case": name, "minimum": result["minimum_added"], "ties": len(expected)}
        )
    return {
        "seed": SEED,
        "oracle": "Fraction rank on incidence and edge cochains; no product cycle basis",
        "cases": results,
        "tree_orders": 2,
    }


def ordered_baseline(model, targets, pool, order, method):
    if method == "deletion":
        selected = list(pool)
        for item in order:
            trial = [r for r in selected if r.name != item.name]
            if enough(model, targets, trial):
                selected = trial
    else:
        selected = []
        remaining = list(order)
        while not enough(model, targets, selected) and remaining:

            def deficit(item):
                rows = incidence(model) + edge_rows(
                    model, (*model.readouts, *selected, item)
                )
                return rank(rows + edge_rows(model, targets), len(model.edges)) - rank(
                    rows, len(model.edges)
                )

            item = min(remaining, key=deficit)  # Ties follow the declared order.
            selected.append(item)
            remaining.remove(item)
    return {
        "ids": [r.name for r in selected],
        "count": len(selected),
        "sufficient": enough(model, targets, selected),
    }


def timed(call, repeats=3):
    durations = []
    value = None
    for _ in range(repeats):
        start = time.perf_counter()
        value = call()
        durations.append(time.perf_counter() - start)
    return value, {"seconds": durations, "median_seconds": statistics.median(durations)}


def baselines():
    fixed, targets = dfr_model("w")
    all_model, _ = dfr_model("all")
    model, trap_target, _ = synthetic(2, 2)
    x, y = [(f"v{i}-0", f"v{i}-1") for i in range(2)]
    trap_pool = tuple(
        ho.IntegerReadout.from_mapping(name, values)
        for name, values in (("x+y", {x: 1, y: 1}), ("y", {y: 1}), ("x", {x: 1}))
    )
    cases = [
        ("dfr-fixed", fixed, targets, all_model.readouts[1:]),
        ("dfr-zero", replace(fixed, readouts=()), targets, all_model.readouts),
        (
            "direct-target-available",
            fixed,
            targets,
            (*all_model.readouts[1:], replace(targets[0], name="direct-DeltaW")),
        ),
        ("deletion-order-example", model, trap_target, trap_pool),
    ]
    output = []
    for name, model, targets, pool in cases:
        reference, reference_time = timed(lambda: exhaustive(model, targets, pool))
        product, product_time = timed(lambda: ho.design_readouts(model, targets, pool))
        assert {tuple(r.name for r in s) for s in reference} == {
            tuple(s["added_ids"]) for s in product["result"]["solutions"]
        }
        orders = [("forward", pool), ("reverse", tuple(reversed(pool)))]
        shuffled = list(pool)
        random.Random(SEED).shuffle(shuffled)
        orders.append(("seeded", tuple(shuffled)))
        ordered = []
        for method in ("deletion", "greedy"):
            for order_name, order in orders:
                result, duration = timed(
                    lambda: ordered_baseline(model, targets, pool, order, method)
                )
                ordered.append(
                    {"method": method, "order": order_name, **result, **duration}
                )
        output.append(
            {
                "case": name,
                "minimum": product["result"]["minimum_added"],
                "ties": product["result"]["ties_found"],
                "fraction_enumeration": reference_time,
                "product_with_certificates": product_time,
                "ordered_methods": ordered,
            }
        )
    # Existing compare path: same fixed task, before/after target; certificate-
    # rich full-history analysis has more output responsibility than pure ranks.
    fixed, targets = dfr_model("w")
    study = {
        "schema_version": 2,
        "name": "DFR target audit",
        "question": "Does W determine DeltaW?",
        "model": {
            key: value
            for key, value in ho.model_to_dict(fixed).items()
            if key in ("schema_version", "name", "vertices", "edges")
        },
        "analysis": {"max_cycles": 10000},
        "configurations": [
            {"id": "p", "label": "W", "readouts": ho.model_to_dict(fixed)["readouts"]},
            {
                "id": "pf",
                "label": "W and target",
                "readouts": ho.model_to_dict(
                    replace(fixed, readouts=(*fixed.readouts, *targets))
                )["readouts"],
            },
        ],
    }
    comparison, timing = timed(lambda: ho.compare_configurations(study))
    diagnosis, target_timing = timed(lambda: ho.analyze_target(fixed, targets))
    assert comparison["status"] == "COMPLETE"
    assert comparison["relations"][0]["relation"] == "RIGHT_REFINES_LEFT"
    assert comparison["relations"][0]["scope"] == "FULL_HOMOLOGY"
    assert diagnosis["result"]["sufficient"] is False
    return {
        "cases": output,
        "existing_compare": {
            "timing": timing,
            "status": comparison["status"],
            "result": comparison,
        },
        "target_diagnosis": {
            "timing": target_timing,
            "sufficient": diagnosis["result"]["sufficient"],
        },
        "timing_scope": "Fraction scripts return ranks/IDs; product design also builds coordinates, certificates, replay metadata and statuses. Timings do not imply equal output responsibilities.",
    }


def records():
    dataset = dfr.load_dataset()
    paths = dataset["files"]["natural-events.json"]["rows"]
    # Fixed paired data: canonical compact JSON and signed int64 readout arrays.
    cohorts = {}
    for scheme in ("w", "w-on", "all"):
        rows = dataset["files"][f"natural-inputs-{scheme}.json"]["rows"]
        encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
        counters = sum(len(row["readouts"]) for row in rows)
        _, encoding = timed(
            lambda: json.dumps(rows, sort_keys=True, separators=(",", ":"))
        )
        cohorts[scheme] = {
            "trajectory_count": len(rows),
            "scalar_count": counters,
            "int64_readout_bytes": 8 * counters,
            "json_bytes_with_snapshots_and_ids": len(encoded),
            "encoding": encoding,
        }
    case, duration = timed(lambda: dfr.run_case(dataset), repeats=1)
    assert all(
        case["paired_reconstruction"][s]["mismatches"] == 0 for s in ("w-on", "all")
    )
    all_model, targets = dfr_model("all")
    alternative = replace(
        all_model, readouts=(all_model.readouts[0], all_model.readouts[3])
    )
    alternative_audit = ho.analyze_target(alternative, targets)
    pressure = dataset["files"]["pressure-inputs-all.json"]["rows"]
    visible = [
        (row["snapshots"], {name: row["readouts"][name] for name in ("W", "S0")})
        for row in pressure
    ]
    assert not alternative_audit["result"]["sufficient"] and visible[0] == visible[1]
    truth = {
        row["trajectory_id"]: row["DeltaW"]
        for row in dataset["files"]["natural-labels.json"]["rows"]
    }

    def accumulate(readouts):
        mappings = [r.as_mapping() for r in readouts]
        values = []
        for path in paths:
            states = path["states"]
            values.append(
                [
                    sum(
                        m.get((u, v), 0) - m.get((v, u), 0)
                        for u, v in zip(states, states[1:])
                    )
                    for m in mappings
                ]
            )
        return values

    accumulation = {}
    for name, readouts in (
        ("direct-target", targets),
        ("w-on", dfr_model("w-on")[0].readouts),
        ("all", all_model.readouts),
    ):
        values, measurement = timed(lambda: accumulate(readouts))
        if name == "direct-target":
            assert [x[0] for x in values] == [
                truth[row["trajectory_id"]] for row in paths
            ]
        accumulation[name] = {"channels": len(readouts), **measurement}
    return {
        "dataset_id": dataset["manifest"]["dataset_id"],
        "observations": cohorts,
        "event_accumulation": accumulation,
        "same_count_alternative": {
            "channels": ["W", "S0"],
            "sufficient": alternative_audit["result"]["sufficient"],
            "pressure_inputs_equal": visible[0] == visible[1],
            "pressure_targets": [
                row["DeltaW"]
                for row in dataset["files"]["pressure-labels.json"]["rows"]
            ],
        },
        "application_seconds": duration,
        "application": case,
        "scope": "Fixed 64 natural trajectories; identical snapshots and IDs. int64 is a declared representation, JSON sizes are measured. Event accumulation excludes simulation and snapshots. No physical acquisition cost or training improvement is inferred.",
    }


PROFILES = {
    "small-2-4-1": (2, 4, 1, {}),
    "small-4-8-2": (4, 8, 2, {}),
    "medium-8-12-2": (8, 12, 2, {}),
    "search-8-12-4": (8, 12, 4, {}),
    "large-16-16-4": (16, 16, 4, {}),
    "bounded-16-16-4": (16, 16, 4, {"max_seconds": 2.0}),
    "subset-cap": (4, 8, 2, {"max_subsets": 2}),
    "output-cap": (2, 8, 1, {"max_solutions": 1}),
    "matrix-cap": (192, 192, 1, {}),
    "integer-1024": (2, 4, 1, {"bits": 1024}),
    "explanation": (4, 8, 2, {"explain": True}),
    "explanation-cap": (4, 8, 2, {"explain": True, "max_explanation_cycles": 1}),
}


def profile(name):
    beta, count, q, options = PROFILES[name]
    options = dict(options)
    bits = options.pop("bits", 1)
    explain = options.pop("explain", False)
    model, targets, pool = synthetic(beta, count, q, bits=bits)
    limits = ho.TargetLimits(**options)
    stages = {}

    def measured(name, function):
        def wrapped(*args, **kwargs):
            stage = kwargs.get("stage", "precheck") if name == "rank" else name
            start = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                stages[stage] = stages.get(stage, 0.0) + time.perf_counter() - start

        return wrapped

    start = time.perf_counter()
    with (
        patch.object(design, "prepare", measured("coordinates", design.prepare)),
        patch.object(design, "sufficiency", measured("rank", design.sufficiency)),
        patch.object(
            design, "_certificate", measured("certificates", design._certificate)
        ),
        patch.object(
            design,
            "attach_explanation",
            measured("explanation", design.attach_explanation),
        ),
    ):
        result = ho.design_readouts(
            model, targets, pool, limits=limits, explain=explain
        )
    elapsed = time.perf_counter() - start
    start = time.perf_counter()
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    stages["json_encoding"] = time.perf_counter() - start
    if sys.platform.startswith("linux"):
        status = Path("/proc/self/status").read_text()
        rss_bytes = 1024 * int(re.search(r"VmHWM:\s+(\d+)", status)[1])
    else:
        rss_bytes = None
    try:
        import resource

        if rss_bytes is None:
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss_bytes = int(rss if sys.platform == "darwin" else 1024 * rss)
    except ImportError:
        rss_bytes = None
    summary = result["result"]
    assert summary["minimum_added"] in (None, q)
    if summary["minimum_proven"]:
        assert summary["minimum_added"] == q
    if name == "subset-cap":
        assert (
            result["limit"]["resource"] == "subsets" and not summary["minimum_proven"]
        )
    if name == "output-cap":
        assert (
            summary["minimum_proven"]
            and summary["enumeration_complete"]
            and not summary["ties_complete"]
        )
    if name == "matrix-cap":
        assert (
            result["limit"]["resource"] == "matrix_entries" and result["basis"] is None
        )
    if name == "explanation-cap":
        assert (
            summary["certificates_complete"]
            and result["explanation_status"] == "LIMIT_REACHED"
        )
    # Replay deterministic core records; deadline stops may depend on hardware.
    replay = None
    if result["limit"] is None or result["limit"]["resource"] != "cooperative_seconds":
        replay = ho.run_target_request(result["request"]) == result
        assert replay
    return {
        "case": name,
        "constructed": True,
        "cycle_rank": beta,
        "candidate_count": count,
        "target_count": q,
        "integer_bits": bits,
        "limits": asdict(limits),
        "seconds": elapsed,
        "stages_seconds": stages,
        "peak_process_rss_bytes": rss_bytes,
        "json_bytes": len(encoded),
        "status": result["status"],
        "limit": result["limit"],
        "explanation_status": result["explanation_status"],
        "minimum": summary["minimum_added"],
        "minimum_proven": summary["minimum_proven"],
        "subsets": summary["subsets_examined"],
        "ties": summary["ties_found"],
        "returned": len(summary["solutions"]),
        "ties_complete": summary["ties_complete"],
        "certificates_complete": summary["certificates_complete"],
        "replay_equal": replay,
    }


def source_identity():
    files = [
        p
        for base in ("src", "tools", "tests")
        for p in sorted((ROOT / base).rglob("*.py"))
    ]
    digest = hashlib.sha256()
    for path in files:
        digest.update(
            path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes()
        )
    return {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_sha256": digest.hexdigest(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "packages": {
            name: metadata.version(name)
            for name in (
                "sympy",
                "networkx",
                "numpy",
                "scipy",
                "homological-observability",
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--profile", choices=PROFILES)
    args = parser.parse_args()
    if args.profile:
        print(json.dumps(profile(args.profile)))
        return
    if args.output_dir is None:
        parser.error("--output-dir is required")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    results = {
        "protocol": 1,
        "environment": source_identity(),
        "measurement": "Individual resource profiles run in fresh subprocesses. Peak RSS uses Linux VmHWM or resource.ru_maxrss elsewhere, measured before replay and including interpreter/imports. Stages partition coordinate, rank, certificate and optional explanation work; JSON encoding is additional. Each scale point is one run, not a latency guarantee.",
    }
    for name, function in (
        ("correctness", correctness),
        ("baselines", baselines),
        ("records", records),
    ):
        print(name, flush=True)
        results[name] = function()
        (args.output_dir / f"{name}.json").write_text(
            json.dumps(results[name], indent=2) + "\n"
        )
    results["scale"] = []
    for name in PROFILES:
        print(name, flush=True)
        run = subprocess.run(
            [sys.executable, __file__, "--profile", name],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        results["scale"].append(json.loads(run.stdout))
    (args.output_dir / "assessment.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    print("PASS: target task assessment")


if __name__ == "__main__":
    main()
