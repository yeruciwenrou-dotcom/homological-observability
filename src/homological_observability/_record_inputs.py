"""Validated, labeled inputs shared by finite-record inference and protocol studies."""

from __future__ import annotations

import math
import sys
from dataclasses import asdict, dataclass
from itertools import pairwise

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


def time_coordinate(value, label):
    """Keep integer ticks exact in comparisons and in the replay request."""
    return value if type(value) is int else number(value, label)


# Half the smallest float spacing is an exact unit for both coordinates and
# their rounding uncertainties, including subnormal timestamps.
_CLOCK_FRACTION_BITS = math.ulp(0.0).as_integer_ratio()[1].bit_length()


def _clock_ticks(value):
    if type(value) is int:
        return value << _CLOCK_FRACTION_BITS, 0, 0
    numerator, denominator = value.as_integer_ratio()
    ticks = numerator << (_CLOCK_FRACTION_BITS - (denominator.bit_length() - 1))
    mantissa, exponent = math.frexp(abs(value))
    half_ulp = 1 << max(0, _CLOCK_FRACTION_BITS + exponent - 54) if value else 1
    # On the side toward zero, a normal power of two borders a finer bin.
    if mantissa == 0.5 and abs(value) > sys.float_info.min:
        if value > 0:
            return ticks, half_ulp // 2, half_ulp
        return ticks, half_ulp, half_ulp // 2
    return ticks, half_ulp, half_ulp


def _steepest_clock_slope(bands):
    """Largest (low[j] - high[i]) / (j - i) for all i < j."""
    hull = []
    best_num, best_den = 0, 0
    for j, (low, high) in enumerate(bands):
        if hull:
            # The steepest line to (j, low) touches the lower convex hull of
            # earlier upper endpoints. Its edge slopes are increasing.
            left, right = 0, len(hull) - 1
            while left < right:
                mid = (left + right) // 2
                i, y = hull[mid]
                k, z = hull[mid + 1]
                if (low - y) * (k - i) >= (z - y) * (j - i):
                    left = mid + 1
                else:
                    right = mid
            i, y = hull[left]
            num, den = low - y, j - i
            if not best_den or num * best_den > best_num * den:
                best_num, best_den = num, den

        while len(hull) >= 2:
            i, y = hull[-2]
            k, z = hull[-1]
            if (z - y) * (j - k) < (high - z) * (k - i):
                break
            hull.pop()
        hull.append((j, high))
    return best_num, best_den


def _regular_step(times):
    if len(times) == 1:
        return 0.0
    if any(b <= a for a, b in pairwise(times)):
        raise ValueError(
            "snapshot times must increase strictly; use relative times or integer "
            "ticks if successive timestamps coincide at the input precision"
        )
    if all(type(t) is int for t in times):
        step = times[1] - times[0]
        if any(b - a != step for a, b in pairwise(times)):
            raise ValueError("snapshot times must define a regular grid")
        return number(step, "snapshot interval")

    windows = len(times) - 1
    first = _clock_ticks(times[0])[0]
    span = _clock_ticks(times[-1])[0] - first
    # Measure coordinates relative to the first timestamp. The extra scale
    # represents half the existing 1e-10 interval tolerance exactly.
    scale = 2 * 10**10 * windows

    def bands():
        for t in times:
            ticks, below, above = _clock_ticks(t)
            center = (ticks - first) * scale
            if type(t) is int:
                yield center, center
            else:
                yield (
                    center - max(below * scale, span),
                    center + max(above * scale, span),
                )

    num, den = span * scale, windows
    # At a fixed step, all bands must allow a common origin. This single pass
    # handles ordinary records without storing a hull.
    origin_lo = origin_hi = None
    for i, (low, high) in enumerate(bands()):
        lo, hi = den * low - i * num, den * high - i * num
        origin_lo = lo if origin_lo is None else max(origin_lo, lo)
        origin_hi = hi if origin_hi is None else min(origin_hi, hi)
        if origin_lo > origin_hi:
            # A free origin and slope exist exactly when all pairwise lower
            # slope bounds fit below all upper bounds. Reflecting the bands
            # gives the upper bound with the same O(n log n) hull algorithm.
            lower, lower_den = _steepest_clock_slope(bands())
            reflected, upper_den = _steepest_clock_slope((-b, -a) for a, b in bands())
            upper = -reflected
            if lower * upper_den > upper * lower_den:
                raise ValueError("snapshot times must define a regular grid")
            # Use the middle of the feasible interval when rounding prevents
            # the endpoint estimate from fitting the complete record.
            num = lower * upper_den + upper * lower_den
            den = 2 * lower_den * upper_den
            break
    try:
        return num / ((den * scale) << _CLOCK_FRACTION_BITS)
    except OverflowError as error:
        raise ValueError("snapshot interval is outside floating-point range") from error


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
    times = [
        time_coordinate(t, "snapshot time") for t in _array(raw["times"], label="times")
    ]
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
    record = {"times": times, "states": list(states), "counts": dict(counts)}
    return record, _regular_step(times)


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
