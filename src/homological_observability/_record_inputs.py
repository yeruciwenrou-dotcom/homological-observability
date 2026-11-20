"""Validated, labeled inputs shared by finite-record inference and protocol studies."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from ._comparison_provenance import producer_identity
from ._integer_io import check_output_integers
from .comparison import _sha256
from .model import _array, _object, _reject_unknown_fields, parse_model
from .serialization import cochains_to_dict, model_to_dict
from .version import __version__


def fields(value, allowed, required, label):
    obj = _object(value, label=label)
    _reject_unknown_fields(obj, allowed=set(allowed), label=label)
    missing = set(required) - obj.keys()
    if missing:
        raise ValueError(f"{label} is missing {sorted(missing)!r}")
    return obj


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def number(value, label):
    if type(value) not in (int, float):
        raise TypeError(f"{label} must be a finite number")
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} is outside floating-point range") from error
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True)
class SolverLimits:
    tolerance: float = 1e-6
    max_grid_points: int = 65536
    max_matrix_entries: int = 4000000

    def __post_init__(self):
        if not 0 < number(self.tolerance, "tolerance") < 1:
            raise ValueError("tolerance must be strictly between zero and one")
        for name in ("max_grid_points", "max_matrix_entries"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")


class DirectedRates:
    """Validated sparse rates. Allocate the dense row generator only on demand."""

    def __init__(self, vertices, rates):
        self.vertices = vertices
        self.rates = rates
        self.matrix = None
        totals = dict.fromkeys(vertices, 0.0)
        for (u, _), rate in rates.items():
            totals[u] += rate
        if any(not math.isfinite(v) for v in totals.values()):
            raise ValueError(
                "total exit rates must be finite in the declared time unit"
            )
        self.totals = totals

    def dense(self, max_entries):
        if len(self.vertices) ** 2 > max_entries:
            return None
        if self.matrix is None:
            self.matrix = np.zeros((len(self.vertices), len(self.vertices)))
            index = {v: i for i, v in enumerate(self.vertices)}
            for (u, v), rate in self.rates.items():
                self.matrix[index[u], index[v]] = rate
            np.fill_diagonal(self.matrix, [-self.totals[v] for v in self.vertices])
        return self.matrix


def rate_array(items, model):
    """Make a row generator in canonical vertex order from labeled directed rates."""
    by_edge = {}
    for item in _array(items, label="rates"):
        fields(item, ("from", "to", "rate"), ("from", "to", "rate"), "directed rate")
        edge = (text(item["from"], "from"), text(item["to"], "to"))
        rate = number(item["rate"], "rate")
        if edge in by_edge or rate <= 0:
            raise ValueError("each directed edge needs one strictly positive rate")
        by_edge[edge] = rate
    expected = {*model.edges, *((v, u) for u, v in model.edges)}
    if by_edge.keys() != expected:
        raise ValueError("rates must cover exactly both directions of every model edge")
    q = DirectedRates(model.vertices, dict(sorted(by_edge.items())))
    normalized = [
        {"from": u, "to": v, "rate": by_edge[u, v]} for u, v in sorted(by_edge)
    ]
    return q, normalized


def common_request(request, *, extra, required):
    common = {
        "schema_version",
        "model",
        "target",
        "time_unit",
        "target_unit",
        "rates",
        "limits",
        "reverse_tree_order",
    }
    fields(
        request,
        common | set(extra),
        {"schema_version", "model", "target", "time_unit"} | set(required),
        "request",
    )
    if type(request["schema_version"]) is not int or request["schema_version"] != 1:
        raise ValueError("finite-record request schema_version must be integer 1")
    model = parse_model(request["model"])
    if request["model"].get("analysis"):
        raise ValueError(
            "filtration settings belong to the topology task; supply a graph and cochains here"
        )
    model_doc = model_to_dict(model)
    target = parse_model({**model_doc, "readouts": [request["target"]]}).readouts[0]
    limits = SolverLimits(
        **fields(
            request.get("limits", {}), SolverLimits.__dataclass_fields__, (), "limits"
        )
    )
    reverse = request.get("reverse_tree_order", False)
    if type(reverse) is not bool:
        raise TypeError("reverse_tree_order must be boolean")
    normalized = {
        "schema_version": 1,
        "model": model_doc,
        "target": cochains_to_dict((target,))[0],
        "target_unit": text(request.get("target_unit", "count"), "target_unit"),
        "time_unit": text(request["time_unit"], "time_unit"),
        "limits": asdict(limits),
        "reverse_tree_order": reverse,
    }
    q = None
    if "rates" in request:
        q, normalized["rates"] = rate_array(request["rates"], model)
    return normalized, model, target, q, limits


def observation(raw, model):
    fields(raw, ("times", "states", "counts"), ("times", "states", "counts"), "record")
    times = [number(t, "snapshot time") for t in _array(raw["times"], label="times")]
    states = _array(raw["states"], label="states")
    counts = _object(raw["counts"], label="counts")
    if not times or len(times) != len(states):
        raise ValueError("a record needs one state per time and at least one snapshot")
    vertices = set(model.vertices)
    if any(not isinstance(s, str) or s not in vertices for s in states):
        raise ValueError("a snapshot state lies outside the model")
    if counts.keys() != {r.name for r in model.readouts} or any(
        type(v) is not int for v in counts.values()
    ):
        raise ValueError(
            "counts must give one signed integer for every declared readout"
        )
    check_output_integers(counts)
    dt = 0.0
    if len(times) > 1:
        dt = (times[-1] - times[0]) / (len(times) - 1)
        if (
            not math.isfinite(dt)
            or dt <= 0
            or any(
                b <= a or not math.isclose(b - a, dt, rel_tol=1e-10, abs_tol=0.0)
                for a, b in zip(times, times[1:])
            )
        ):
            raise ValueError(
                "snapshot times must define a finite, strictly increasing regular grid"
            )
    return {"times": times, "states": list(states), "counts": dict(counts)}, dt


def result_document(name, request, status, result):
    check_output_integers(request)
    doc = {
        "schema_name": "homological-observability." + name,
        "schema_version": 1,
        "software": {"name": "homological-observability", "version": __version__},
        "producer": producer_identity(),
        "request": request,
        "request_sha256": _sha256(request),
        "status": status,
        "result": result,
    }
    check_output_integers(result)
    return doc
