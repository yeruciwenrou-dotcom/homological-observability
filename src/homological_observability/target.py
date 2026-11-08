"""Target sufficiency and exact decoding on the full integer cycle group."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import networkx as nx
from sympy import ZZ, Matrix
from sympy.matrices.normalforms import smith_normal_decomp

from ._integer_io import check_integer_text
from ._target_common import (
    Budget,
    TargetLimits,
    TaskLimit,
    basis_document,
    mark_limited,
    matrix_to_dict,
    new_document,
    prepare,
    sufficiency,
    validate_call,
)
from ._target_explanation import attach_explanation
from .homology import chain_from_walk
from .integer_lattice import integer_kernel
from .model import GraphModel, IntegerReadout


def _certificate(p, f, basis, sufficient, budget):
    budget.check("certificate", p, f)
    if sufficient:
        if p.rows == 0:
            decoder = Matrix.zeros(f.rows, 0)
        elif p.cols == 0:
            decoder = Matrix.zeros(f.rows, p.rows)
        else:
            solution, parameters = p.T.gauss_jordan_solve(f.T)
            decoder = solution.subs(dict.fromkeys(parameters, 0)).T
        budget.check("certificate", decoder)
        if decoder * p != f:
            raise AssertionError("target decoder failed exact verification")
        return {
            "kind": "decoder",
            "decoder": matrix_to_dict(decoder, rational=True),
            "domain": "integer_image_of_readouts",
        }
    kernel = integer_kernel(p)
    budget.check("certificate", kernel)
    change = f * kernel
    index = next(j for j in range(kernel.cols) if any(change[:, j]))
    witness = kernel[:, index]
    chain = basis.fundamental_cycles * witness
    budget.check("certificate", witness, chain, change[:, index])
    if any(p * witness) or not any(f * witness):
        raise AssertionError("target ambiguity witness failed exact verification")
    return {
        "kind": "ambiguity",
        "cycle_coordinates": matrix_to_dict(witness),
        "edge_chain": matrix_to_dict(chain),
        "target_change": matrix_to_dict(change[:, index]),
    }


def analyze_target(
    model: GraphModel,
    targets: Sequence[IntegerReadout],
    *,
    limits: TargetLimits | None = None,
    reverse_tree_order: bool = False,
    explain: bool = False,
) -> dict:
    """Decide whether the model's fixed readouts determine every target.

    Returns an exact rational decoder or an integer closed-chain witness.
    The default core task does not enumerate cycles. ``explain=True`` adds a
    separately bounded target-image filtration after the core certificate.
    """
    targets, limits = validate_call(model, targets, limits, reverse_tree_order)
    document = new_document(
        "analyze", model, targets, (), limits, reverse_tree_order, explain=explain
    )
    result = {
        "sufficient": None,
        "rank_readouts": None,
        "rank_joint": None,
        "certificate": None,
        "certificate_complete": False,
    }
    document["result"] = result
    budget = Budget(limits)
    basis = None
    try:
        basis, p, _, f = prepare(model, targets, (), budget, reverse_tree_order)
        document["basis"] = basis_document(basis, p, f)
        sufficient, rank_p, rank_joint = sufficiency(p, f, budget)
        result.update(
            sufficient=sufficient, rank_readouts=rank_p, rank_joint=rank_joint
        )
        result["certificate"] = _certificate(p, f, basis, sufficient, budget)
        result["certificate_complete"] = True
        budget.check("serialization")
    except TaskLimit as error:
        mark_limited(document, error)
    if explain:
        attach_explanation(document, model, budget, basis)
    return document


def _integer_preimage(p, value, budget):
    """Solve Pz=value over Z, checking every Smith row and divisibility."""
    budget.check("legal_image", p, value)
    if p.rows == 0:
        return Matrix.zeros(p.cols, 1)
    if p.cols == 0:
        return Matrix.zeros(0, 1) if not any(value) else None
    diagonal, left, right = smith_normal_decomp(p, domain=ZZ)
    budget.check("legal_image", diagonal, left, right)
    if diagonal != left * p * right or abs(left.det()) != 1 or abs(right.det()) != 1:
        raise AssertionError("invalid Smith decomposition for legal-image decoding")
    transformed = left * value
    coordinates = Matrix.zeros(p.cols, 1)
    for row in range(p.rows):
        divisor = diagonal[row, row] if row < p.cols else 0
        if divisor:
            if transformed[row] % divisor:
                return None
            coordinates[row] = transformed[row] // divisor
        elif transformed[row]:
            return None
    preimage = right * coordinates
    budget.check("legal_image", preimage)
    if p * preimage != value:
        raise AssertionError("integer preimage failed exact verification")
    return preimage


def _record(model, values, kind, start, end):
    if kind not in ("raw", "cycle"):
        raise ValueError("record_kind must be raw or cycle")
    if not isinstance(values, Mapping) or set(values) != {
        r.name for r in model.readouts
    }:
        raise ValueError("record keys must exactly match the fixed readout names")
    for value in values.values():
        if type(value) is not int:
            raise TypeError("record values must be integers")
        check_integer_text(value, label="record value")
    if kind == "raw":
        if start not in model.vertices or end not in model.vertices:
            raise ValueError("raw records require start and end vertices in the model")
    elif start is not None or end is not None:
        raise ValueError(
            "cycle records already have endpoint corrections; omit endpoints"
        )
    return {"kind": kind, "values": dict(values), "start": start, "end": end}


def evaluate_target(
    model: GraphModel,
    targets: Sequence[IntegerReadout],
    record: Mapping[str, int],
    *,
    record_kind: str = "raw",
    start: str | None = None,
    end: str | None = None,
    limits: TargetLimits | None = None,
    reverse_tree_order: bool = False,
) -> dict:
    """Decode one legal record without computing an exposure filtration.

    Raw records require endpoints and return raw path targets. Cycle records
    return cycle targets in the declared spanning-tree convention. An illegal
    integer image or insufficient observations produce no target value.
    """
    targets, limits = validate_call(model, targets, limits, reverse_tree_order)
    record = _record(model, record, record_kind, start, end)
    document = new_document(
        "evaluate", model, targets, (), limits, reverse_tree_order, record
    )
    result = {
        "sufficient": None,
        "legal_record": None,
        "target_values": None,
        "corrected_record": None,
        "endpoint_readouts": None,
        "endpoint_targets": None,
        "value_kind": record_kind,
        "reason": None,
    }
    document["result"] = result
    budget = Budget(limits)
    try:
        basis, p, _, f = prepare(model, targets, (), budget, reverse_tree_order)
        document["basis"] = basis_document(basis, p, f)
        values = Matrix(
            len(model.readouts), 1, [record["values"][r.name] for r in model.readouts]
        )
        budget.check("precheck", values)
        reference = Matrix.zeros(len(model.edges), 1)
        if record_kind == "raw":
            tree = nx.Graph()
            tree.add_nodes_from(model.vertices)
            tree.add_edges_from(basis.tree_edges)
            reference = chain_from_walk(nx.shortest_path(tree, start, end), basis)
        all_readouts = (*model.readouts, *targets)
        endpoint = Matrix(
            len(all_readouts),
            1,
            [
                sum(
                    r.as_mapping().get(edge, 0) * reference[i, 0]
                    for i, edge in enumerate(model.edges)
                )
                for r in all_readouts
            ],
        )
        corrected = values - endpoint[: len(model.readouts), :]
        budget.check("precheck", endpoint, corrected)
        result["corrected_record"] = {
            r.name: int(corrected[i, 0]) for i, r in enumerate(model.readouts)
        }
        result["endpoint_readouts"] = {
            r.name: int(endpoint[i, 0]) for i, r in enumerate(model.readouts)
        }
        offset = endpoint[len(model.readouts) :, :]
        result["endpoint_targets"] = {
            r.name: int(offset[i, 0]) for i, r in enumerate(targets)
        }
        result["sufficient"] = sufficiency(p, f, budget)[0]
        preimage = _integer_preimage(p, corrected, budget)
        result["legal_record"] = preimage is not None
        if preimage is None:
            result["reason"] = "record_outside_integer_image"
        elif not result["sufficient"]:
            result["reason"] = "target_not_determined_by_record"
        else:
            target_values = f * preimage + offset
            budget.check("evaluation", target_values)
            result["target_values"] = {
                r.name: int(target_values[i, 0]) for i, r in enumerate(targets)
            }
        budget.check("serialization")
    except TaskLimit as error:
        mark_limited(document, error)
    return document
