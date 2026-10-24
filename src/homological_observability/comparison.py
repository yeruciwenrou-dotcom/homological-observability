"""Compare exact cumulative counters under one shared observation model.

Information relations compare hidden integer lattices in a common cycle
coordinate system. Scalar summaries describe particular objectives; they do
not decide whether one configuration contains another's information.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from itertools import combinations
from pathlib import Path
from typing import Any

from sympy import Matrix
from sympy.matrices.matrixbase import MatrixBase

from ._integer_io import check_output_integers, parse_json_integer
from .analysis import TopologyAnalysis, analyze_model
from .integer_lattice import hidden_lattice, inclusion_coordinates
from .model import parse_model
from .serialization import analysis_to_dict, model_to_dict

MAX_CONFIGURATIONS = 64
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be a JSON object with string keys")
    return value


def _fields(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {sorted(unknown)!r}")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _json_copy(value: Any) -> Any:
    """Reject non-JSON/oversized data before hashing or recording evidence."""

    def require_json(item: Any) -> None:
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise TypeError("study JSON object keys must be strings")
            for child in item.values():
                require_json(child)
        elif isinstance(item, list):
            for child in item:
                require_json(child)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise TypeError("study must contain JSON objects, arrays and scalar values")

    require_json(value)
    check_output_integers(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("study must contain finite JSON values") from error
    return json.loads(encoded, parse_int=parse_json_integer)


def _sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def parse_study(document: Mapping[str, Any]) -> dict[str, Any]:
    """Validate shared conditions and preserve candidate-local input errors.

    Graph, sampling settings, candidate identities and envelope fields are
    global requirements. Each candidate's readouts are validated during its
    analysis, allowing one malformed counter to coexist with valid results.
    The returned mapping is detached from the caller's mutable input.
    """
    root = _object(document, "study")
    _fields(
        root,
        {"schema_version", "name", "question", "model", "analysis", "configurations"},
        "study",
    )
    version = root.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("study schema_version must equal integer 1 or 2")
    name = _text(root.get("name"), "study name")
    question = root.get("question", "")
    if not isinstance(question, str):
        raise TypeError("study question must be a string")
    base = _object(root.get("model"), "shared model")
    _fields(base, {"schema_version", "name", "vertices", "edges"}, "shared model")
    if base.get("schema_version") != version:
        raise ValueError("study and shared model schema_version must match")
    settings = _object(root.get("analysis", {}), "shared analysis")
    model = parse_model({**base, "readouts": [], "analysis": settings})
    normalized = model_to_dict(model)
    shared_analysis = normalized.pop("analysis")
    normalized.pop("readouts")

    candidates = root.get("configurations")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("configurations must be a nonempty JSON array")
    if len(candidates) > MAX_CONFIGURATIONS:
        raise ValueError(f"at most {MAX_CONFIGURATIONS} configurations are supported")
    configs = []
    seen = set()
    for index, value in enumerate(candidates):
        label = f"configurations[{index}]"
        config = _object(value, label)
        _fields(config, {"id", "label", "readouts"}, label)
        identifier = config.get("id")
        if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
            raise ValueError(
                f"{label}.id must be 1–64 lowercase letters, digits, '_' or '-', "
                "starting with a letter or digit"
            )
        if identifier in seen:
            raise ValueError("configuration ids must be unique")
        seen.add(identifier)
        if "readouts" not in config:
            raise ValueError(f"{label}.readouts is required; use [] for snapshots only")
        configs.append(
            {
                "id": identifier,
                "label": _text(config.get("label", identifier), label + ".label"),
                "readouts": config["readouts"],
            }
        )
    return _json_copy(
        {
            "schema_version": 2,
            "name": name,
            "question": question,
            "model": normalized,
            "analysis": shared_analysis,
            "configurations": configs,
        }
    )


def load_study(path: str | Path) -> dict[str, Any]:
    """Load a comparison study from a UTF-8 JSON document."""
    study_path = Path(path)
    try:
        document = json.loads(
            study_path.read_text(encoding="utf-8"), parse_int=parse_json_integer
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON study {study_path}: {error.msg}") from error
    return parse_study(document)


def _matrix(matrix: MatrixBase) -> dict[str, Any]:
    return {
        "rows": matrix.rows,
        "columns": matrix.cols,
        "data": [
            [int(matrix[row, col]) for col in range(matrix.cols)]
            for row in range(matrix.rows)
        ],
    }


def _vector(matrix: MatrixBase) -> list[int]:
    return [int(value) for value in matrix]


def _witness(result: TopologyAnalysis, vector: MatrixBase) -> dict[str, Any]:
    chain = result.basis.fundamental_cycles * vector
    return {
        "cycle_coordinates": _vector(vector),
        "edge_chain": [
            {"edge": list(edge), "coefficient": int(chain[index, 0])}
            for index, edge in enumerate(result.basis.edges)
            if chain[index, 0]
        ],
    }


def _empty_row(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": config["id"],
        "label": config["label"],
        "channels": (
            len(config["readouts"]) if isinstance(config["readouts"], list) else None
        ),
        "status": "ERROR",
        "error": None,
        "recovery": None,
        "scope": "UNAVAILABLE",
        "computed_max_layer": None,
        "natural_complete": False,
        "first_hidden_layer": None,
        "computed_hidden_rank": None,
        "entropy_log_t_coefficient": None,
        "visible_torsion": None,
        "hidden_edge_witnesses": [],
        "redundant_channels": None,
        "explanations": [],
    }


def _summarize(
    config: Mapping[str, Any],
    result: TopologyAnalysis,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    row = _empty_row(config)
    row["status"] = result.status.value
    if result.filtration is None:
        row["recovery"] = (
            "Increase analysis.max_cycles only if the larger enumeration fits "
            "your available resources, then rerun into a new directory."
        )
        row["explanations"] = [
            "The cycle enumeration limit was reached. Hidden directions, "
            "phase summaries and information relations are unavailable."
        ]
        return row
    layers = result.filtration.layers
    last = layers[-1]
    full = result.natural_filtration_complete
    row.update(
        {
            "scope": "FULL_HOMOLOGY" if full else "COMPUTED_EXPOSURE",
            "computed_max_layer": last.layer,
            "natural_complete": full,
            "first_hidden_layer": payload["summary"]["first_nonzero_hidden_layer"],
            "computed_hidden_rank": last.hidden.cols,
            "entropy_log_t_coefficient": (
                payload["phase"]["entropy_log_t_coefficient"]
            ),
            "visible_torsion": {
                str(layer.layer): list(layer.visible_graded.torsion_factors)
                for layer in layers
                if layer.visible_graded and layer.visible_graded.torsion_factors
            },
            "hidden_edge_witnesses": [
                _witness(result, last.hidden[:, index])
                for index in range(last.hidden.cols)
            ],
        }
    )
    redundant = []
    for index, readout in enumerate(result.model.readouts):
        remaining = Matrix(result.readout)
        remaining.row_del(index)
        without = hidden_lattice(last.exposure, remaining)
        if without == last.hidden:
            redundant.append(readout.name)
    row["redundant_channels"] = redundant
    scope_text = (
        "the full integer cycle group"
        if full
        else f"the exposure lattice computed through layer {last.layer}"
    )
    notes = []
    if last.hidden.cols:
        notes.append(
            f"{last.hidden.cols} independent hidden integer direction(s) remain "
            f"in {scope_text}; edge-chain witnesses are included."
        )
        notes.append(
            f"The first hidden direction appears at layer "
            f"{row['first_hidden_layer']} within the computed filtration."
        )
    else:
        notes.append(f"No hidden integer cycle direction remains in {scope_text}.")
    if not full:
        notes.append(
            "This is a computed-horizon conclusion; uncomputed layers may "
            "introduce further hidden directions."
        )
    if redundant:
        notes.append(
            "Individually removing any of these channels preserves the "
            f"information on this scope: {', '.join(redundant)}. "
            "This does not authorize removing all of them together."
        )
    if row["visible_torsion"]:
        notes.append(
            "Visible graded quotients contain finite torsion; exact integer "
            "image constraints are retained in the analysis result."
        )
    if row["entropy_log_t_coefficient"] == 0 and last.hidden.cols:
        notes.append(
            "A zero log(T) entropy coefficient does not establish zero "
            "uncertainty or finite-time recovery."
        )
    row["explanations"] = notes
    return row


def _containment(
    sub: MatrixBase,
    sup: MatrixBase,
    detecting_readout: MatrixBase,
) -> tuple[dict[str, Any], MatrixBase | None]:
    """Prove kernel inclusion or return an exactly distinguished direction.

    Both lattices are intersections with the *same* exposure lattice. Thus a
    sub-basis vector outside the other kernel is witnessed by a nonzero exact
    readout. Successful containment additionally records integer coordinates.
    """
    for index in range(sub.cols):
        vector = sub[:, index]
        if any(detecting_readout * vector):
            return {"included": False, "coordinates": None}, vector
    coordinates = inclusion_coordinates(sub, sup)
    return {"included": True, "coordinates": _matrix(coordinates)}, None


def _pair(
    left_row: Mapping[str, Any],
    right_row: Mapping[str, Any],
    left: TopologyAnalysis | None,
    right: TopologyAnalysis | None,
) -> dict[str, Any]:
    pair: dict[str, Any] = {
        "left": left_row["id"],
        "right": right_row["id"],
        "relation": "UNAVAILABLE",
        "scope": "UNAVAILABLE",
        "computed_max_layer": None,
        "left_kernel_in_right": None,
        "right_kernel_in_left": None,
        "left_not_right_witness": None,
        "right_not_left_witness": None,
        "metric_comparison": None,
        "explanations": [],
    }
    if (
        left is None
        or right is None
        or left.filtration is None
        or right.filtration is None
    ):
        pair["explanations"] = [
            "An error or resource limit prevents a common complete computed "
            "scope; no information relation is asserted."
        ]
        return pair
    ll, rr = left.filtration.layers[-1], right.filtration.layers[-1]
    if left.basis != right.basis or ll.layer != rr.layer or ll.exposure != rr.exposure:
        raise AssertionError("comparison candidates must share coordinates and scope")
    full = left.natural_filtration_complete and right.natural_filtration_complete
    pair["scope"] = "FULL_HOMOLOGY" if full else "COMPUTED_EXPOSURE"
    pair["computed_max_layer"] = ll.layer
    l_in_r, l_witness = _containment(ll.hidden, rr.hidden, right.readout)
    r_in_l, r_witness = _containment(rr.hidden, ll.hidden, left.readout)
    pair["left_kernel_in_right"] = l_in_r
    pair["right_kernel_in_left"] = r_in_l
    for key, vector in (
        ("left_not_right_witness", l_witness),
        ("right_not_left_witness", r_witness),
    ):
        if vector is not None:
            pair[key] = {
                **_witness(left, vector),
                "left_readout": _vector(left.readout * vector),
                "right_readout": _vector(right.readout * vector),
            }
    if l_in_r["included"] and r_in_l["included"]:
        pair["relation"] = "EQUIVALENT"
        conclusion = (
            "Both configurations distinguish the same cycle histories on this "
            "scope. Their kernels are equal; their exact output values or "
            "integer image lattices may differ."
        )
    elif l_in_r["included"]:
        pair["relation"] = "LEFT_REFINES_RIGHT"
        conclusion = (
            "The left configuration strictly refines the right on this scope: "
            "its hidden lattice is strictly smaller. The right-not-left witness "
            "is invisible to the right and distinguished by the left."
        )
    elif r_in_l["included"]:
        pair["relation"] = "RIGHT_REFINES_LEFT"
        conclusion = (
            "The right configuration strictly refines the left on this scope: "
            "its hidden lattice is strictly smaller. The left-not-right witness "
            "is invisible to the left and distinguished by the right."
        )
    else:
        pair["relation"] = "INCOMPARABLE"
        conclusion = (
            "Each configuration distinguishes a cycle direction that the other "
            "leaves hidden. Neither information set contains the other; both "
            "directions are supplied as exact edge-chain witnesses."
        )
    first_left, first_right = (
        left_row["first_hidden_layer"],
        right_row["first_hidden_layer"],
    )
    if first_left == first_right:
        first_relation = "TIED"
    elif first_left is None:
        first_relation = "LEFT_HAS_NO_HIDDEN_DIRECTION"
    elif first_right is None:
        first_relation = "RIGHT_HAS_NO_HIDDEN_DIRECTION"
    else:
        first_relation = "LEFT_LATER" if first_left > first_right else "RIGHT_LATER"
    pair["metric_comparison"] = {
        "first_hidden_layer": first_relation,
        "hidden_rank_tied": (
            left_row["computed_hidden_rank"] == right_row["computed_hidden_rank"]
        ),
        "entropy_coefficient_tied": (
            None
            if left_row["entropy_log_t_coefficient"] is None
            or right_row["entropy_log_t_coefficient"] is None
            else left_row["entropy_log_t_coefficient"]
            == right_row["entropy_log_t_coefficient"]
        ),
        "channel_count_difference": left_row["channels"] - right_row["channels"],
    }
    notes = [conclusion]
    if first_relation == "TIED":
        notes.append(
            "The first-hidden-layer objective is tied. An objective tie alone "
            "does not imply information equivalence."
        )
    elif first_relation in ("LEFT_LATER", "RIGHT_LATER"):
        side = "left" if first_relation == "LEFT_LATER" else "right"
        notes.append(
            f"For the first-hidden-layer objective, the {side} configuration "
            "delays the first hidden direction within the computed filtration."
        )
    if not full:
        notes.append(
            f"The relation applies only to the exposure lattice through layer "
            f"{ll.layer}; it is not a full-homology relation."
        )
    pair["explanations"] = notes
    return pair


def _overview(
    rows: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> list[str]:
    counts = {
        status: sum(row["status"] == status for row in rows)
        for status in ("COMPLETE", "PARTIAL_HORIZON", "LIMIT_REACHED", "ERROR")
    }
    overview = [
        f"Compared {len(rows)} configuration(s): {counts['COMPLETE']} naturally "
        f"complete, {counts['PARTIAL_HORIZON']} limited to the requested horizon, "
        f"{counts['LIMIT_REACHED']} resource-limited, and {counts['ERROR']} failed."
    ]
    for scope, description in (
        ("FULL_HOMOLOGY", "the full integer cycle group"),
        ("COMPUTED_EXPOSURE", "the computed exposure lattice only"),
    ):
        identified = [
            row["id"]
            for row in rows
            if row["scope"] == scope and row["computed_hidden_rank"] == 0
        ]
        if identified:
            names = ", ".join(identified[:5])
            if len(identified) > 5:
                names += f", and {len(identified) - 5} more"
            overview.append(
                f"{len(identified)} configuration(s) leave no hidden integer "
                f"cycle direction on {description}: {names}."
            )
    equivalent = sum(pair["relation"] == "EQUIVALENT" for pair in relations)
    incomparable = sum(pair["relation"] == "INCOMPARABLE" for pair in relations)
    if equivalent or incomparable:
        overview.append(
            f"Exact kernel comparisons find {equivalent} equivalent pair(s) "
            f"and {incomparable} incomparable pair(s) on their stated scopes."
            + (
                " Incomparable pairs offer different information, so their "
                "scalar summaries cannot provide a universal ordering."
                if incomparable
                else ""
            )
        )
    redundant = [row["id"] for row in rows if row["redundant_channels"]]
    if redundant:
        overview.append(
            f"{len(redundant)} configuration(s) contain individually redundant "
            "channels; the row explanations identify safe single-channel removals."
        )
    return overview


def compare_configurations(
    study: Mapping[str, Any],
    *,
    reverse_tree_order: bool = False,
) -> dict[str, Any]:
    """Analyze, compare and explain counters under shared exact conditions.

    Every call validates the public input, including mappings returned by
    :func:`parse_study`. Candidate-local input errors are reported in rows;
    invalid shared conditions raise before any scientific result is emitted.
    """
    if not isinstance(reverse_tree_order, bool):
        raise TypeError("reverse_tree_order must be a boolean")
    normalized = parse_study(study)
    rows: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    analyses: dict[str, TopologyAnalysis] = {}
    for config in normalized["configurations"]:
        raw = copy.deepcopy(normalized["model"])
        raw["name"] += "/" + config["id"]
        raw["analysis"] = copy.deepcopy(normalized["analysis"])
        raw["readouts"] = copy.deepcopy(config["readouts"])
        try:
            result = analyze_model(
                parse_model(raw), reverse_tree_order=reverse_tree_order
            )
            payload = analysis_to_dict(result)
            row = _summarize(config, result, payload)
        except (ValueError, TypeError) as error:
            row = _empty_row(config)
            row["error"] = str(error)
            row["recovery"] = (
                "Check this configuration's readout names, graph edges and "
                "integer coefficients, then rerun into a new output directory."
            )
            row["explanations"] = [
                "This configuration could not be analyzed; its original "
                "readout input is preserved in the study."
            ]
        else:
            analyses[config["id"]] = result
            results[config["id"]] = payload
        rows.append(row)
    relations = [
        _pair(left, right, analyses.get(left["id"]), analyses.get(right["id"]))
        for left, right in combinations(rows, 2)
    ]
    from ._comparison_provenance import producer_identity

    output = {
        "schema_name": "homological-observability.comparison",
        "schema_version": 2,
        "artifact_role": "configuration-comparison",
        "status": (
            "COMPLETE"
            if all(row["status"] == "COMPLETE" for row in rows)
            else "INCOMPLETE"
        ),
        "producer": producer_identity(),
        "study": normalized,
        "study_sha256": _sha256(normalized),
        "shared_conditions": {
            "model": copy.deepcopy(normalized["model"]),
            "analysis": copy.deepcopy(normalized["analysis"]),
            "reverse_tree_order": reverse_tree_order,
            "coordinates": (
                "reverse spanning-tree order"
                if reverse_tree_order
                else "default spanning-tree order"
            ),
            "observation_contract": (
                "One supplied connected simple support graph with a shared "
                "regular noiseless snapshot protocol and sampling conditions. "
                "Configurations vary the exact cumulative integer counter rules."
            ),
            "information_contract": (
                "Relations compare kernels on the declared common integer "
                "cycle lattice. Equivalent information is decoded on legal "
                "readout images; an ambient integer inverse is not required."
            ),
        },
        "rows": rows,
        "results": results,
        "relations": relations,
        "explanations": _overview(rows, relations)
        + [
            "Compare the scoped information relations and their witnesses "
            "alongside the objective summaries; scalar ties do not imply "
            "equivalent information.",
            "Channel counts describe the supplied cumulative counters. They "
            "do not establish equal hardware cost or a universal best design.",
            "Entropy coefficients are asymptotic log(T) terms. A zero value "
            "does not establish zero uncertainty or finite-time recovery.",
            "PARTIAL_HORIZON conclusions cover computed exposure only. "
            "LIMIT_REACHED and ERROR candidates carry no missing-layer "
            "or information-relation conclusion.",
        ],
    }
    check_output_integers(output)
    return output
