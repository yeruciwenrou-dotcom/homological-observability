"""Known-Q DFR trajectories with paired observations and separate truth files."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from dataclasses import replace
from importlib import resources
from pathlib import Path

import numpy as np

from .._target_common import cochains_to_dict
from ..model import GraphModel, IntegerReadout
from ..serialization import model_to_dict
from ..version import __version__

PROTOCOL_VERSION = 1
SOURCE_COMMIT = "88893cd76822cd4040699f1ccbf5879b7688ce5b"
SOURCE_URL = f"https://github.com/pseifner/NeuralMJP/blob/{SOURCE_COMMIT}/scripts/data_generation/generate_data.py"
SCHEMES = {
    "snapshots": (),
    "w": ("W",),
    "w-on": ("W", "W_ON"),
    "all": ("W", "W_ON", "W_OFF", "S0", "S1", "S2"),
}


def json_bytes(value):
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def dfr_model(scheme="snapshots"):
    if scheme not in SCHEMES:
        raise ValueError("unknown DFR observation scheme")
    rules = {
        "W": {("2", "0"): 1, ("5", "3"): 1},
        "W_ON": {("2", "0"): 1},
        "W_OFF": {("5", "3"): 1},
        **{f"S{i}": {(str(i), str(i + 3)): 1} for i in range(3)},
    }
    model = GraphModel.create(
        name="DFR known-Q research application",
        vertices=map(str, range(6)),
        edges=[
            ("0", "1"),
            ("1", "2"),
            ("2", "0"),
            ("3", "4"),
            ("4", "5"),
            ("5", "3"),
            ("0", "3"),
            ("1", "4"),
            ("2", "5"),
        ],
        readouts=[(name, rules[name]) for name in SCHEMES[scheme]],
    )
    target = (
        IntegerReadout.from_mapping(
            "DeltaW", {("2", "0"): 1, ("5", "3"): -1}, allowed_edges=model.edges
        ),
    )
    return model, target


def rate_matrix():
    """Row-generator for beta=V=b=r=1, in states ON0..2, OFF0..2."""
    q = np.zeros((6, 6), dtype=float)
    for i in range(3):
        for j in range(3):
            if i != j:
                q[i, j] = math.exp(-(j - i) / 2)
                q[i + 3, j + 3] = 1.0
        q[i, i + 3] = q[i + 3, i] = 1.0
    np.fill_diagonal(q, -q.sum(axis=1))
    return q


def stationary_distribution(q):
    equations = q.T.copy()
    equations[-1] = 1.0
    rhs = np.zeros(len(q))
    rhs[-1] = 1.0
    probability = np.linalg.solve(equations, rhs)
    probability /= probability.sum()
    if np.any(probability <= 0) or np.max(np.abs(probability @ q)) > 1e-12:
        raise ArithmeticError("DFR stationary-law numerical check failed")
    return probability


def simulate_path(q, probability, horizon, rng, *, max_events=100000):
    """Direct CTMC simulation; event zero records the initial state."""
    state = int(rng.choice(len(q), p=probability))
    times, states = [0.0], [str(state)]
    time = 0.0
    while True:
        rate = -q[state, state]
        next_time = time + float(rng.exponential(1.0 / rate))
        if next_time >= horizon:
            break
        if next_time <= time:
            raise ArithmeticError("event time failed to advance")
        if len(times) - 1 >= max_events:
            raise ValueError("trajectory exceeds the event budget")
        choices = q[state].copy()
        choices[state] = 0
        state = int(rng.choice(len(q), p=choices / rate))
        times.append(next_time)
        states.append(str(state))
        time = next_time
    return {"times": times, "states": states}


def observe_path(path, grid, model):
    """Validate the whole path, including zero-jump paths, then expose its view."""
    times, states = path["times"], path["states"]
    if (
        not isinstance(times, list)
        or not isinstance(states, list)
        or not times
        or len(times) != len(states)
    ):
        raise ValueError("a trajectory needs aligned nonempty times and states")
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times):
        raise ValueError("event times must be finite numbers")
    if (
        times[0] != 0
        or any(b <= a for a, b in zip(times, times[1:]))
        or times[-1] >= grid[-1]
    ):
        raise ValueError(
            "event times must start at zero and increase strictly before T"
        )
    if any(state not in model.vertices for state in states):
        raise ValueError(
            "path state is outside the support, including its initial state"
        )
    allowed = set(model.edges) | {edge[::-1] for edge in model.edges}
    if any((u, v) not in allowed for u, v in zip(states, states[1:])):
        raise ValueError("path contains a transition outside the support")
    snapshots = [
        states[int(index)] for index in np.searchsorted(times, grid, side="right") - 1
    ]
    counts = {}
    for readout in model.readouts:
        coefficients = readout.as_mapping()
        counts[readout.name] = sum(
            coefficients.get((u, v), 0) - coefficients.get((v, u), 0)
            for u, v in zip(states, states[1:])
        )
    return {"snapshots": snapshots, "readouts": counts}


def _target_value(path, grid):
    model, targets = dfr_model()
    return observe_path(path, grid, replace(model, readouts=targets))["readouts"][
        "DeltaW"
    ]


def _pressure_paths(grid):
    # Both paths finish their changes before the FIRST positive snapshot time.
    # They agree at every grid point, not just at the two outer endpoints.
    walks = [["0", "3"], ["0", "1", "2", "0", "3", "5", "4", "3", "0", "3"]]
    result = []
    for i, walk in enumerate(walks):
        times = [0.0] + [
            float(grid[1] * (j + 1) / (len(walk) + 1)) for j in range(len(walk) - 1)
        ]
        result.append(
            {
                "trajectory_id": digest(["pressure", i])[:24],
                "split": "pressure",
                "times": times,
                "states": walk,
            }
        )
    return result


def _files_for_paths(paths, grid, prefix):
    files = {}
    for scheme in SCHEMES:
        model, _ = dfr_model(scheme)
        rows = [
            {
                "trajectory_id": p["trajectory_id"],
                "split": p["split"],
                **observe_path(p, grid, model),
            }
            for p in paths
        ]
        files[f"{prefix}-inputs-{scheme}.json"] = {
            "protocol_version": 1,
            "scheme_id": scheme,
            "rows": rows,
        }
    files[f"{prefix}-labels.json"] = {
        "protocol_version": 1,
        "rows": [
            {
                "trajectory_id": p["trajectory_id"],
                "split": p["split"],
                "DeltaW": _target_value(p, grid),
            }
            for p in paths
        ],
    }
    files[f"{prefix}-events.json"] = {"protocol_version": 1, "rows": paths}
    return files


def generate_dataset(
    output_dir,
    *,
    trajectories=64,
    seed=20261108,
    split_seed=731,
    observation_time=2.5,
    grid_points=50,
):
    """Generate the four paired schemes and an explicitly separate pressure set."""
    if type(trajectories) is not int or not 10 <= trajectories <= 10000:
        raise ValueError("trajectories must be an integer between 10 and 10000")
    if any(type(s) is not int or not 0 <= s < 2**63 for s in (seed, split_seed)):
        raise ValueError("seeds must be nonnegative integers below 2**63")
    if type(grid_points) is not int or not 2 <= grid_points <= 10000:
        raise ValueError("grid_points must be between 2 and 10000")
    if (
        type(observation_time) not in (int, float)
        or not math.isfinite(observation_time)
        or observation_time <= 0
    ):
        raise ValueError("observation_time must be positive and finite")
    if trajectories * grid_points > 1000000:
        raise ValueError("dataset exceeds the one-million snapshot budget")
    directory = Path(output_dir)
    if directory.exists():
        raise FileExistsError("dataset directory already exists")
    q = rate_matrix()
    probability = stationary_distribution(q)
    rng = np.random.Generator(np.random.PCG64(seed))
    grid = np.linspace(0, observation_time, grid_points).tolist()
    if not grid[1] > 0 or any(b <= a for a, b in zip(grid, grid[1:])):
        raise ValueError("observation grid cannot be represented with distinct times")
    split_rng = np.random.Generator(np.random.PCG64(split_seed))
    permutation = split_rng.permutation(trajectories).tolist()
    split_at = (int(0.6 * trajectories), int(0.8 * trajectories))
    split_by_index = {
        i: "train" if k < split_at[0] else "validation" if k < split_at[1] else "test"
        for k, i in enumerate(permutation)
    }
    paths = []
    for i in range(trajectories):
        path = simulate_path(q, probability, float(observation_time), rng)
        paths.append(
            {
                "trajectory_id": digest(["natural", seed, i])[:24],
                "split": split_by_index[i],
                **path,
            }
        )
    files = {
        **_files_for_paths(paths, grid, "natural"),
        **_files_for_paths(_pressure_paths(grid), grid, "pressure"),
    }
    model, targets = dfr_model()
    manifest = {
        "schema_name": "homological-observability.dfr-dataset",
        "protocol_version": 1,
        "data_version": "dfr-1",
        "model": model_to_dict(model),
        "targets": cochains_to_dict(targets),
        "schemes": {
            name: cochains_to_dict(dfr_model(name)[0].readouts) for name in SCHEMES
        },
        "generator": {
            "method": "direct-CTMC",
            "rng": "numpy.PCG64",
            "software_version": __version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "source_commit": SOURCE_COMMIT,
            "source_url": SOURCE_URL,
            "paper_url": "https://proceedings.mlr.press/v202/seifner23a.html",
        },
        "config": {
            "trajectories": trajectories,
            "seed": seed,
            "split_seed": split_seed,
            "observation_time": float(observation_time),
            "grid_points": grid_points,
            "parameters": {"temperature": 1, "V": 1, "b": 1, "r": 1},
        },
        "grid": grid,
        "rate_matrix": q.tolist(),
        "initial_law": {
            "kind": "numerically_solved_stationary",
            "probabilities": probability.tolist(),
            "max_stationarity_residual": float(np.max(np.abs(probability @ q))),
        },
        "split_ids": {
            s: [p["trajectory_id"] for p in paths if p["split"] == s]
            for s in ("train", "validation", "test")
        },
        "pressure": {
            "kind": "constructed_equal_weight_ambiguity",
            "weights": [0.5, 0.5],
            "natural_sampling_frequency": None,
            "scope": "same full snapshot grid and W; DeltaW labels 0 and 2",
        },
        "files": {
            name: hashlib.sha256(json_bytes(value)).hexdigest()
            for name, value in files.items()
        },
    }
    manifest["dataset_id"] = digest(manifest)
    directory.mkdir(parents=True)
    for name, value in files.items():
        (directory / name).write_bytes(json_bytes(value))
    (directory / "manifest.json").write_bytes(json_bytes(manifest))
    return manifest


def load_dataset(directory=None):
    """Load a dataset, rejecting malformed documents before feature extraction."""
    try:
        return _load_dataset(directory)
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise ValueError("malformed DFR dataset document") from error


def _load_dataset(directory):
    """Load and cross-check the version, hashes, split identities and paired views."""
    directory = (
        resources.files("homological_observability").joinpath("data", "dfr")
        if directory is None
        else Path(directory)
    )
    manifest = json.loads(directory.joinpath("manifest.json").read_bytes())
    if (
        manifest.get("protocol_version") != 1
        or type(manifest["protocol_version"]) is not int
    ):
        raise ValueError("DFR dataset protocol_version must equal integer 1")
    if (
        manifest.get("schema_name") != "homological-observability.dfr-dataset"
        or manifest.get("data_version") != "dfr-1"
    ):
        raise ValueError("unsupported DFR dataset identity")
    if manifest.get("dataset_id") != digest(
        {k: v for k, v in manifest.items() if k != "dataset_id"}
    ):
        raise ValueError("dataset manifest identity mismatch")
    expected_files = {
        f"{p}-{suffix}.json"
        for p in ("natural", "pressure")
        for suffix in ("events", "labels", *(f"inputs-{s}" for s in SCHEMES))
    }
    if set(manifest["files"]) != expected_files:
        raise ValueError("unexpected dataset files")
    files = {}
    for name, expected in manifest["files"].items():
        content = directory.joinpath(name).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"dataset file digest mismatch: {name}")
        value = json.loads(content)
        if (
            type(value.get("protocol_version")) is not int
            or value["protocol_version"] != 1
        ):
            raise ValueError("dataset member protocol mismatch")
        files[name] = value
    model, targets = dfr_model()
    if manifest["model"] != model_to_dict(model) or manifest[
        "targets"
    ] != cochains_to_dict(targets):
        raise ValueError("DFR graph or target identity mismatch")
    if manifest["schemes"] != {
        name: cochains_to_dict(dfr_model(name)[0].readouts) for name in SCHEMES
    }:
        raise ValueError("DFR scheme identity mismatch")
    grid = manifest["grid"]
    if (
        not isinstance(grid, list)
        or len(grid) < 2
        or grid[0] != 0
        or any(type(t) not in (int, float) or not math.isfinite(t) for t in grid)
        or any(b <= a for a, b in zip(grid, grid[1:]))
    ):
        raise ValueError("invalid observation grid")
    if (
        len(grid) != manifest["config"]["grid_points"]
        or grid[-1] != manifest["config"]["observation_time"]
    ):
        raise ValueError("grid/config identity mismatch")
    expected_grid = np.linspace(0, grid[-1], len(grid))
    if not np.allclose(grid, expected_grid, rtol=1e-14, atol=0):
        raise ValueError("the DFR application requires a regular grid")
    q = np.asarray(manifest["rate_matrix"], dtype=float)
    probability = np.asarray(manifest["initial_law"]["probabilities"], dtype=float)
    if manifest["initial_law"]["kind"] != "numerically_solved_stationary" or manifest[
        "config"
    ]["parameters"] != {"temperature": 1, "V": 1, "b": 1, "r": 1}:
        raise ValueError("DFR initial-law or parameter metadata mismatch")
    if q.shape != (6, 6) or not np.allclose(q, rate_matrix(), rtol=1e-14, atol=0):
        raise ValueError("DFR rate identity mismatch")
    if (
        probability.shape != (6,)
        or not np.all(np.isfinite(probability))
        or np.any(probability <= 0)
        or abs(probability.sum() - 1) > 1e-12
        or np.max(np.abs(probability @ q)) > 1e-12
    ):
        raise ValueError("invalid stationary initial law")
    seen = set()
    for prefix in ("natural", "pressure"):
        events = files[f"{prefix}-events.json"]["rows"]
        if not isinstance(events, list) or not events:
            raise ValueError("dataset has no trajectories")
        for p in events:
            if (
                set(p) != {"trajectory_id", "split", "times", "states"}
                or not isinstance(p["trajectory_id"], str)
                or not p["trajectory_id"]
                or p["trajectory_id"] in seen
            ):
                raise ValueError("invalid or duplicate trajectory identity")
            seen.add(p["trajectory_id"])
            if p["split"] not in (
                ("pressure",)
                if prefix == "pressure"
                else ("train", "validation", "test")
            ):
                raise ValueError("invalid trajectory split")
        expected_views = _files_for_paths(events, grid, prefix)
        for name, expected in expected_views.items():
            # Canonical bytes distinguish bool/int/float, unlike Python equality.
            if json_bytes(files[name]) != json_bytes(expected):
                raise ValueError(f"trajectory/view/label alignment mismatch: {name}")
    natural = files["natural-events.json"]["rows"]
    if len(natural) != manifest["config"]["trajectories"]:
        raise ValueError("trajectory count mismatch")
    split_ids = {
        s: [p["trajectory_id"] for p in natural if p["split"] == s]
        for s in ("train", "validation", "test")
    }
    if any(not ids for ids in split_ids.values()) or manifest["split_ids"] != split_ids:
        raise ValueError("whole-trajectory split mismatch")
    pressure = files["pressure-inputs-w.json"]["rows"]
    labels = files["pressure-labels.json"]["rows"]
    if (
        len(pressure) != 2
        or pressure[0]["snapshots"] != pressure[1]["snapshots"]
        or pressure[0]["readouts"] != pressure[1]["readouts"]
        or [r["DeltaW"] for r in labels] != [0, 2]
        or manifest["pressure"]["weights"] != [0.5, 0.5]
    ):
        raise ValueError("balanced ambiguity pressure contract failed")
    return {"manifest": manifest, "files": files}


def selected_rows(dataset, scheme, split, cohort):
    if scheme not in SCHEMES or cohort not in ("natural", "pressure"):
        raise ValueError("unknown scheme or cohort")
    if split not in (
        ("pressure",) if cohort == "pressure" else ("train", "validation", "test")
    ):
        raise ValueError("split does not belong to the selected cohort")
    return [
        row
        for row in dataset["files"][f"{cohort}-inputs-{scheme}.json"]["rows"]
        if row["split"] == split
    ]


def feature_view(dataset, scheme="w", *, split="test", cohort="natural"):
    """Return model features and separate alignment metadata, never truth values."""
    rows = selected_rows(dataset, scheme, split, cohort)
    columns = [f"snapshot_{i}" for i in range(len(dataset["manifest"]["grid"]))] + list(
        SCHEMES[scheme]
    )
    x = np.asarray(
        [
            [int(s) for s in row["snapshots"]]
            + [row["readouts"][name] for name in SCHEMES[scheme]]
            for row in rows
        ],
        dtype=np.int64,
    )
    return {
        "trajectory_ids": [row["trajectory_id"] for row in rows],
        "columns": columns,
        "X": x,
        "task": task_identity(dataset, scheme, split, cohort),
    }


def task_identity(dataset, scheme, split, cohort):
    rows = selected_rows(dataset, scheme, split, cohort)
    identity = {
        "dataset_id": dataset["manifest"]["dataset_id"],
        "scheme_id": scheme,
        "split": split,
        "cohort": cohort,
        "target_name": "DeltaW",
        "trajectory_ids": [row["trajectory_id"] for row in rows],
    }
    return {
        **{k: v for k, v in identity.items() if k != "trajectory_ids"},
        "task_id": digest(identity),
    }
