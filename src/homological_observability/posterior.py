"""Posterior of an integer path target from one observed finite record."""

from __future__ import annotations

from math import fsum

from ._fourier_bridge import FourierBridge, Unresolved
from ._record_inputs import common_request, fields, observation, result_document, text
from ._record_lattice import RecordLattice
from ._target_common import TaskLimit
from .model import _array


def _intervals(value):
    result = []
    names = set()
    for item in _array(value, label="target_sets"):
        fields(item, ("name", "min", "max"), ("name",), "target set")
        name = text(item["name"], "set name")
        a, b = item.get("min"), item.get("max")
        if name in names or any(v is not None and type(v) is not int for v in (a, b)):
            raise ValueError(
                "target sets need unique names and integer interval bounds"
            )
        if a is not None and b is not None and a > b:
            raise ValueError("target set lower bound exceeds upper bound")
        result.append({"name": name, "min": a, "max": b})
        names.add(name)
    return result


class PosteriorSolver:
    """One fixed graph, target, readout system and generator, reusable for a batch."""

    def __init__(self, model, target, q, limits, reverse):
        self.target = target.name
        self.q = q
        self.limits = limits
        self.bridge = None
        self.dt = None
        self.problem = None
        try:
            self.lattice = RecordLattice(model, target, reverse)
        except TaskLimit as error:
            self.problem = error

    def solve(self, record, dt, intervals=()):
        result = {
            "target": self.target,
            "legal_record": None,
            "target_support": None,
            "outcome": "UNRESOLVED",
            "pmf": None,
            "map_candidates": None,
            "map_risk": None,
            "set_probabilities": None,
            "diagnostics": {},
        }
        diagnostics = result["diagnostics"]
        try:
            if self.problem is not None:
                raise self.problem
            support = self.lattice.support(record)
            result.update(support)
            if not support["legal_record"]:
                result["outcome"] = "IMPOSSIBLE_RECORD"
                diagnostics["reason"] = (
                    "nonzero_count_at_zero_duration"
                    if len(record["states"]) == 1
                    else "record_outside_integer_image"
                )
                return "COMPLETE", result
            if support["target_support"]["step"] == 0:
                pairs = [(support["target_support"]["offset"], 1.0)]
                result["outcome"] = "EXACT"
            else:
                if self.lattice.image.cols > 2:
                    raise Unresolved(
                        "effective_joint_rank_above_two", "UNSUPPORTED_RANK"
                    )
                if self.q is None:
                    raise Unresolved(
                        "directed_rates_required_for_probabilities", "RATES_REQUIRED"
                    )
                if self.dt != dt or self.bridge is None:
                    matrix = self.q.dense(self.limits.max_matrix_entries)
                    if matrix is None:
                        raise Unresolved("rate_matrix_budget", "LIMIT_REACHED")
                    self.bridge = FourierBridge(self.lattice, matrix, dt, self.limits)
                    self.dt = dt
                pairs = self.bridge.solve(record["states"], support, diagnostics)
                result["outcome"] = "NUMERICAL_POSTERIOR"
        except TaskLimit as error:
            diagnostics.update(reason=error.resource, stage=error.stage)
            return "LIMIT_REACHED", result
        except Unresolved as error:
            diagnostics["reason"] = error.reason
            return error.status, result
        highest = max(p for _, p in pairs)
        width = 2 * diagnostics.get("conditional_error_indicator", 0.0)
        result.update(
            pmf=[{"value": z, "probability": p} for z, p in pairs],
            map_candidates=[z for z, p in pairs if highest - p <= width],
            map_risk=max(0.0, 1 - highest),
            set_probabilities={
                s["name"]: min(
                    1.0,
                    fsum(
                        p
                        for z, p in pairs
                        if (s["min"] is None or z >= s["min"])
                        and (s["max"] is None or z <= s["max"])
                    ),
                )
                for s in intervals
            },
        )
        return "COMPLETE", result


def infer_target_posterior(request: dict) -> dict:
    """Infer one scalar target from labeled regular snapshots and exact net counts.

    Accepts the same versioned dictionary as the `posterior` command. Rates,
    in inverse units of `time_unit`, are needed only for numerical inference.
    The first state is conditioned on. Structured status preserves an integer
    support result if finite numerical precision or a budget limits inference.
    """
    normalized, model, target, q, limits = common_request(
        request, extra=("record", "target_sets"), required=("record",)
    )
    record, dt = observation(request["record"], model)
    intervals = _intervals(request.get("target_sets", []))
    normalized.update(record=record, target_sets=intervals)
    solver = PosteriorSolver(model, target, q, limits, normalized["reverse_tree_order"])
    status, result = solver.solve(record, dt, intervals)
    if solver.problem is None:
        result["coordinates"] = solver.lattice.description()
    return result_document("posterior", normalized, status, result)
