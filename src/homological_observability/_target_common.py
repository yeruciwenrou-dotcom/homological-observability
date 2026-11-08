"""Shared exact coordinates, provenance and cooperative task budgets."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from typing import Sequence

from sympy import Matrix

from .homology import build_homology_basis, readout_matrix
from .model import GraphModel, IntegerReadout
from .serialization import model_to_dict
from .version import __version__


@dataclass(frozen=True)
class TargetLimits:
    """Task budgets, checked between exact operations.

    ``max_seconds`` is a cooperative deadline, not a hard process timeout.
    One atomic SymPy operation can overrun it. Counts bound search and output;
    matrix-size and bit-length checks also cover prechecks and certificates.
    """

    max_subsets: int = 10000
    max_solutions: int = 100
    max_matrix_entries: int = 100000
    max_integer_bits: int = 4096
    max_seconds: float = 30.0
    max_explanation_cycles: int = 10000

    def __post_init__(self) -> None:
        for name in (
            "max_subsets",
            "max_solutions",
            "max_matrix_entries",
            "max_integer_bits",
            "max_explanation_cycles",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        try:
            valid_seconds = (
                not isinstance(self.max_seconds, bool)
                and isinstance(self.max_seconds, (int, float))
                and math.isfinite(self.max_seconds)
                and self.max_seconds > 0
            )
        except OverflowError:
            valid_seconds = False
        if not valid_seconds:
            raise ValueError(
                "max_seconds must be positive and finite in floating-point range"
            )


class TaskLimit(Exception):
    def __init__(self, stage: str, resource: str):
        super().__init__(f"{stage}: {resource}")
        self.stage = stage
        self.resource = resource


class Budget:
    def __init__(self, limits: TargetLimits):
        self.limits = limits
        self.started = time.monotonic()

    def check(self, stage: str, *matrices) -> None:
        if time.monotonic() - self.started >= self.limits.max_seconds:
            raise TaskLimit(stage, "cooperative_seconds")
        for matrix in matrices:
            self.size(stage, matrix.rows * matrix.cols)
            for entry in matrix:
                for integer in entry.as_numer_denom():
                    if abs(int(integer)).bit_length() > self.limits.max_integer_bits:
                        raise TaskLimit(stage, "integer_bits")

    def size(self, stage: str, entries: int) -> None:
        if entries > self.limits.max_matrix_entries:
            raise TaskLimit(stage, "matrix_entries")


def validate_readouts(model, readouts, *, label, nonempty=False):
    values = tuple(readouts)
    if nonempty and not values:
        raise ValueError(f"{label} must contain at least one integer cochain")
    if any(not isinstance(value, IntegerReadout) for value in values):
        raise TypeError(f"{label} must contain IntegerReadout objects")
    if len({value.name for value in values}) != len(values):
        raise ValueError(f"{label} names must be unique")
    if any(set(value.as_mapping()) - set(model.edges) for value in values):
        raise ValueError(f"{label} refers to unknown edges")
    return values


def cochains_to_dict(readouts: Sequence[IntegerReadout]) -> list[dict]:
    return [
        {
            "name": value.name,
            "coefficients": [
                {"edge": list(edge), "coefficient": coefficient}
                for edge, coefficient in value.coefficients
            ],
        }
        for value in readouts
    ]


def matrix_to_dict(matrix, *, rational=False):
    convert = str if rational else int
    return {
        "rows": matrix.rows,
        "columns": matrix.cols,
        "data": [
            [convert(matrix[i, j]) for j in range(matrix.cols)]
            for i in range(matrix.rows)
        ],
    }


def new_document(
    operation,
    model,
    targets,
    candidates,
    limits,
    reverse,
    record=None,
    *,
    explain=False,
):
    if type(explain) is not bool:
        raise TypeError("explain must be boolean")
    request = {
        "schema_version": 1,
        "operation": operation,
        "model": model_to_dict(model),
        "targets": cochains_to_dict(targets),
        "candidates": cochains_to_dict(candidates),
        "limits": asdict(limits),
        "reverse_tree_order": reverse,
        "record": record,
        "explain": explain,
    }
    encoded = json.dumps(
        request,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "schema_name": "homological-observability.target-task",
        "schema_version": 1,
        "software": {"name": "homological-observability", "version": __version__},
        "operation": operation,
        "request": request,
        "request_sha256": hashlib.sha256(encoded).hexdigest(),
        "status": "COMPLETE",
        "limit": None,
        "basis": None,
        "result": None,
        "explanation_status": "NOT_REQUESTED",
        "explanation": None,
    }


def mark_limited(document, error):
    document["status"] = "LIMIT_REACHED"
    document["limit"] = {"stage": error.stage, "resource": error.resource}


def prepare(model, targets, candidates, budget, reverse):
    beta = len(model.edges) - len(model.vertices) + 1
    # Include the incidence matrix and Smith transformation dimensions before
    # allocation. This check applies even when no subset will be searched.
    total = len(model.readouts) + len(candidates) + len(targets)
    budget.size(
        "precheck",
        max(
            len(model.vertices) * len(model.edges),
            len(model.edges) * beta,
            total * len(model.edges),
            beta * beta,
            total * total,
        ),
    )
    for readout in (*model.readouts, *targets, *candidates):
        if any(
            abs(value).bit_length() > budget.limits.max_integer_bits
            for _, value in readout.coefficients
        ):
            raise TaskLimit("precheck", "integer_bits")
    budget.check("precheck")
    basis = build_homology_basis(model, reverse_tree_order=reverse)
    rows = readout_matrix(basis, (*model.readouts, *candidates, *targets))
    budget.check("precheck", rows, basis.fundamental_cycles)
    a, b = len(model.readouts), len(candidates)
    return (
        basis,
        Matrix(rows[:a, :]),
        Matrix(rows[a : a + b, :]),
        Matrix(rows[a + b :, :]),
    )


def basis_document(basis, p, f):
    return {
        "vertices": list(basis.vertices),
        "edges": [list(e) for e in basis.edges],
        "tree_edges": [list(e) for e in basis.tree_edges],
        "chord_edges": [list(e) for e in basis.chord_edges],
        "cycles": matrix_to_dict(basis.fundamental_cycles),
        "readouts": matrix_to_dict(p),
        "targets": matrix_to_dict(f),
    }


def sufficiency(p, f, budget, *, stage="precheck"):
    joined = p.col_join(f)
    budget.check(stage, p, joined)
    rank_p = p.rank()
    budget.check(stage)
    rank_joint = joined.rank()
    budget.check(stage)
    return rank_p == rank_joint, rank_p, rank_joint


def validate_call(model, targets, limits, reverse):
    if not isinstance(model, GraphModel):
        raise TypeError("model must be a GraphModel")
    targets = validate_readouts(model, targets, label="targets", nonempty=True)
    limits = TargetLimits() if limits is None else limits
    if not isinstance(limits, TargetLimits):
        raise TypeError("limits must be TargetLimits")
    if type(reverse) is not bool:
        raise TypeError("reverse_tree_order must be boolean")
    return targets, limits
