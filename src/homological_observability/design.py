"""Minimum additional scalar readouts with separate optimality and tie status."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations

from sympy import Matrix

from ._target_common import (
    Budget,
    TargetLimits,
    TaskLimit,
    basis_document,
    mark_limited,
    new_document,
    prepare,
    sufficiency,
    validate_call,
    validate_readouts,
)
from ._target_explanation import attach_explanation
from .model import GraphModel, IntegerReadout
from .target import _certificate


def design_readouts(
    model: GraphModel,
    targets: Sequence[IntegerReadout],
    candidates: Sequence[IntegerReadout],
    *,
    limits: TargetLimits | None = None,
    reverse_tree_order: bool = False,
    explain: bool = False,
) -> dict:
    """Keep model.readouts fixed and minimize the number of added channels.

    Candidate names identify physical scalar channels. Distinct names remain
    distinct choices even when their cochains are equal. Smaller cardinalities
    are exhausted before a minimum is claimed. Returning every tied choice and
    producing reconstruction certificates have independent completion flags.
    """
    targets, limits = validate_call(model, targets, limits, reverse_tree_order)
    candidates = validate_readouts(model, candidates, label="candidates")
    if {r.name for r in candidates} & {r.name for r in model.readouts}:
        raise ValueError("candidate IDs must differ from fixed readout names")
    document = new_document(
        "design",
        model,
        targets,
        candidates,
        limits,
        reverse_tree_order,
        explain=explain,
    )
    result = {
        "feasible": None,
        "fixed_count": len(model.readouts),
        "candidate_count": len(candidates),
        "minimum_added": None,
        "minimum_total": None,
        "lower_bound_added": None,
        "upper_bound_added": None,
        "minimum_proven": False,
        "enumeration_complete": False,
        "ties_complete": False,
        "certificates_complete": False,
        "output_truncated": False,
        "ties_found": 0,
        "subsets_examined": 0,
        "fully_searched_through": -1,
        "solutions": [],
    }
    document["result"] = result
    budget = Budget(limits)
    selected = []
    basis = None
    try:
        basis, p, pool, f = prepare(
            model, targets, candidates, budget, reverse_tree_order
        )
        document["basis"] = basis_document(basis, p, f)
        if sufficiency(p, f, budget)[0]:
            result.update(
                feasible=True,
                minimum_added=0,
                minimum_total=len(model.readouts),
                lower_bound_added=0,
                upper_bound_added=0,
                minimum_proven=True,
                enumeration_complete=True,
                ties_found=1,
                fully_searched_through=0,
            )
            selected = [()]
        elif not sufficiency(p.col_join(pool), f, budget)[0]:
            result.update(
                feasible=False,
                enumeration_complete=True,
                ties_complete=True,
                certificates_complete=True,
            )
        else:
            result["feasible"] = True
            result["lower_bound_added"] = 1
            result["upper_bound_added"] = len(candidates)
            result["fully_searched_through"] = 0
            for size in range(1, len(candidates) + 1):
                for subset in combinations(range(len(candidates)), size):
                    budget.check("search")
                    if result["subsets_examined"] >= limits.max_subsets:
                        raise TaskLimit("search", "subsets")
                    combined = p.col_join(pool[list(subset), :])
                    enough = sufficiency(combined, f, budget, stage="search")[0]
                    result["subsets_examined"] += 1
                    if enough:
                        result.update(
                            minimum_added=size,
                            minimum_total=len(model.readouts) + size,
                            lower_bound_added=size,
                            upper_bound_added=size,
                            minimum_proven=True,
                        )
                        result["ties_found"] += 1
                        if len(selected) < limits.max_solutions:
                            selected.append(subset)
                        else:
                            result["output_truncated"] = True
                result["fully_searched_through"] = size
                if result["minimum_proven"]:
                    result["enumeration_complete"] = True
                    break
                result["lower_bound_added"] = size + 1
    except TaskLimit as error:
        mark_limited(document, error)

    # Preserve the solutions and proven minimum if enumeration or certificate
    # work runs out of resources. No repeated homology/filtration construction.
    result["solutions"] = [
        {
            "added_ids": [candidates[i].name for i in subset],
            "added_count": len(subset),
            "total_count": len(model.readouts) + len(subset),
            "readout_ids": [r.name for r in model.readouts]
            + [candidates[i].name for i in subset],
            "certificate": None,
        }
        for subset in selected
    ]
    if selected:
        try:
            for subset, solution in zip(selected, result["solutions"]):
                added = pool[list(subset), :] if subset else Matrix.zeros(0, p.cols)
                solution["certificate"] = _certificate(
                    p.col_join(added), f, basis, True, budget
                )
            result["certificates_complete"] = True
            budget.check("serialization")
        except TaskLimit as error:
            if document["limit"] is None:
                mark_limited(document, error)
    result["ties_complete"] = (
        result["enumeration_complete"] and not result["output_truncated"]
    )
    if result["output_truncated"] and document["limit"] is None:
        mark_limited(document, TaskLimit("serialization", "solutions"))
    if explain:
        attach_explanation(document, model, budget, basis)
    return document
