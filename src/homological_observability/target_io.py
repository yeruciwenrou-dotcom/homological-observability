"""Versioned target-task requests, human reports, and replay bundles."""

from __future__ import annotations

import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from ._integer_io import check_output_integers, parse_json_integer
from ._target_common import TargetLimits
from .design import design_readouts
from .model import _array, _object, _reject_unknown_fields, parse_model
from .serialization import model_to_dict
from .target import analyze_target, evaluate_target


def _parse_request(document):
    root = _object(document, label="target request")
    _reject_unknown_fields(
        root,
        allowed={
            "schema_version",
            "operation",
            "model",
            "targets",
            "candidates",
            "limits",
            "reverse_tree_order",
            "record",
            "explain",
        },
        label="target request",
    )
    if type(root.get("schema_version")) is not int or root["schema_version"] != 1:
        raise ValueError("target request schema_version must equal integer 1")
    operation = root.get("operation")
    if operation not in ("analyze", "design", "evaluate"):
        raise ValueError("operation must be analyze, design, or evaluate")
    model = parse_model(root.get("model"))
    normalized = model_to_dict(model)
    targets = parse_model(
        {**normalized, "readouts": _array(root.get("targets"), label="targets")}
    ).readouts
    candidates = parse_model(
        {
            **normalized,
            "readouts": _array(root.get("candidates", []), label="candidates"),
        }
    ).readouts
    if operation != "design" and candidates:
        raise ValueError("candidates are only used by design requests")
    limits = _object(root.get("limits", {}), label="limits")
    _reject_unknown_fields(
        limits, allowed=set(TargetLimits.__dataclass_fields__), label="limits"
    )
    limits = TargetLimits(**limits)
    reverse = root.get("reverse_tree_order", False)
    if type(reverse) is not bool:
        raise TypeError("reverse_tree_order must be boolean")
    record = root.get("record")
    explain = root.get("explain", False)
    if type(explain) is not bool:
        raise TypeError("explain must be boolean")
    if operation == "evaluate" and explain:
        raise ValueError("Use analyze to request an exposure explanation.")
    if operation == "evaluate":
        record = _object(record, label="record")
        _reject_unknown_fields(
            record, allowed={"kind", "values", "start", "end"}, label="record"
        )
        if "kind" not in record or "values" not in record:
            raise ValueError("record requires kind and values")
    elif record is not None:
        raise ValueError("records are only used by evaluate requests")
    return operation, model, targets, candidates, limits, reverse, record, explain


def load_target_request(path: str | Path) -> dict:
    """Load a strict JSON request; semantic validation occurs on execution."""
    payload = json.loads(
        Path(path).read_text(encoding="utf-8"), parse_int=parse_json_integer
    )
    _parse_request(payload)
    return payload


def run_target_request(document: dict) -> dict:
    """Replay an authored request or the request embedded in an earlier result."""
    operation, model, targets, candidates, limits, reverse, record, explain = (
        _parse_request(document)
    )
    options = {"limits": limits, "reverse_tree_order": reverse}
    if operation == "design":
        return design_readouts(model, targets, candidates, explain=explain, **options)
    if operation == "evaluate":
        return evaluate_target(
            model,
            targets,
            record["values"],
            record_kind=record["kind"],
            start=record.get("start"),
            end=record.get("end"),
            **options,
        )
    return analyze_target(model, targets, explain=explain, **options)


def _target_limit_note(limit: dict) -> str:
    """Name the stopped calculation and the request setting that controls it."""
    resource = limit["resource"]
    if resource == "solutions":
        return "Increase limits.max_solutions to return more minimum designs."
    rule = {
        "matrix_entries": ("matrix-size", "max_matrix_entries"),
        "integer_bits": ("integer bit-length", "max_integer_bits"),
        "cooperative_seconds": ("time", "max_seconds"),
        "subsets": ("subset search", "max_subsets"),
    }.get(resource)
    stage = {
        "precheck": "initial checks",
        "legal_image": "integer-image check",
        "evaluation": "target evaluation",
        "certificate": "certificate construction",
        "serialization": "output preparation",
        "search": "candidate search",
    }.get(limit["stage"], limit["stage"].replace("_", " "))
    if rule is None:
        return f"The run reached the {resource.replace('_', ' ')} limit during {stage}."
    label, setting = rule
    return (
        f"The {label} limit stopped the run during {stage}. "
        f"Increase limits.{setting} and rerun."
    )


def render_target_text(document: dict) -> str:
    """Summarize the computed target values, designs and certificates."""
    result = document["result"]
    operation = document["operation"]
    targets = [t["name"] for t in document["request"]["targets"]]
    lines = [
        f"Target task: {operation} [{document['status']}]",
        "Targets: " + ", ".join(targets),
        "Scope: exact integer cochains on the full cycle group. Raw path records use known endpoints.",
    ]
    if document["limit"]:
        lines.append(_target_limit_note(document["limit"]))
    if operation == "design":
        lines.append(
            f"Fixed channels: {result['fixed_count']}; candidate channels: {result['candidate_count']}"
        )
        if result["feasible"] is True:
            lines.append(
                "The candidate pool and fixed readouts together determine all targets."
            )
        elif result["feasible"] is False:
            lines.append(
                "Different target values fit the same readings even with every candidate channel."
            )
        if result["minimum_proven"]:
            lines.append(
                f"Minimum added channels: {result['minimum_added']} (proved); total: {result['minimum_total']}."
            )
        else:
            bounds = []
            if result["lower_bound_added"] is not None:
                bounds.append(f"at least {result['lower_bound_added']}")
            if result["upper_bound_added"] is not None:
                bounds.append(f"at most {result['upper_bound_added']}")
            if bounds:
                lines.append(
                    "Bounds on the minimum added channels: " + ", ".join(bounds) + "."
                )
        for solution in result["solutions"]:
            lines.append(
                "Add: " + (", ".join(solution["added_ids"]) or "no additional channel")
            )
        if result["solutions"]:
            if result["ties_complete"]:
                lines.append("All minimum choices are shown.")
            elif result["enumeration_complete"]:
                lines.append(
                    f"Showing {len(result['solutions'])} of {result['ties_found']} minimum choices."
                )
            else:
                lines.append("Further minimum choices may remain.")
            if not result["certificates_complete"]:
                lines.append(
                    "Certificate construction is incomplete for the listed designs."
                )
        if any(s["added_count"] for s in result["solutions"]):
            lines.append(
                "Additional channels apply to future collection or replay from available full paths."
            )
    else:
        if result["sufficient"] is True:
            lines.append("The fixed readouts determine every target for legal records.")
        elif result["sufficient"] is False and (
            operation == "analyze" or result["legal_record"] is not True
        ):
            lines.append(
                "Different histories can share the fixed readouts and have different target values."
            )
        if operation == "evaluate":
            if result["legal_record"] is True:
                lines.append(
                    "The supplied record satisfies the integer-image constraints."
                )
            elif result["legal_record"] is False:
                lines.append("The supplied record is outside the legal integer image.")
            if result["target_values"] is not None:
                lines.append(
                    "Raw target values (including endpoint corrections):"
                    if result["value_kind"] == "raw"
                    else "Cycle target values (in the selected tree convention):"
                )
                lines.extend(
                    f"  {name} = {value}"
                    for name, value in result["target_values"].items()
                )
            elif result["legal_record"] is True and result["sufficient"] is False:
                lines.append(
                    f"Several values of {targets[0]} fit this record."
                    if len(targets) == 1
                    else "Several combinations of target values fit this record."
                )
        else:
            certificate = result["certificate"]
            if result["sufficient"] is not None and not result["certificate_complete"]:
                lines.append(
                    "The rank test finished. Certificate construction is incomplete."
                )
            if certificate and certificate["kind"] == "ambiguity":
                lines.append(
                    "An integer closed-chain witness leaves every fixed readout unchanged:"
                )
                lines.extend(
                    f"  {name} changes by {row[0]}"
                    for name, row in zip(targets, certificate["target_change"]["data"])
                )
            elif certificate:
                lines.append("An exact decoder is included in the structured result.")
    if document["explanation_status"] != "NOT_REQUESTED":
        lines.append(f"Exposure-scale explanation: {document['explanation_status']}")
    explanation = document["explanation"]
    if explanation:
        lines.append(
            "Explanation scope: the fixed readouts before any channel additions."
        )
        for layer in explanation["layers"]:
            if layer["layer"] < 2:
                continue
            detail = f"Layer {layer['layer']}: target rank increment {layer['graded_target_rank']}"
            if layer["critical_alpha"] is not None:
                detail += f"; critical alpha {layer['critical_alpha']}"
            if layer["finite_exposure_scale"] is not None:
                scale = Fraction(layer["finite_exposure_scale"])
                with localcontext() as context:
                    context.prec = 6
                    approximate = Decimal(scale.numerator) / Decimal(scale.denominator)
                detail += f"; exposure scale approximately {approximate}"
            lines.append(detail)
        coefficient = explanation["target_entropy_log_t_coefficient"]
        prefix = explanation["prefix_entropy_log_t_coefficient"]
        if coefficient is not None:
            lines.append(f"Target entropy log(T) coefficient: {coefficient}")
        elif prefix is not None:
            lines.append(
                f"Computed-prefix entropy log(T) coefficient: {prefix}; later layers remain open."
            )
        if explanation["limit"]:
            lines.append(
                f"Explanation stopped: {explanation['limit']['resource']}; established core results are retained."
            )
        lines.append(
            "Exposure scales describe ambiguity accumulation. Entropy coefficients give the leading log(T) term in target uncertainty."
        )
    lines.append(f"Replay request SHA-256: {document['request_sha256']}")
    return "\n".join(lines) + "\n"


def target_json(document: dict) -> str:
    check_output_integers(document)
    return (
        json.dumps(
            document, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
        )
        + "\n"
    )


def write_target_bundle(document: dict, output_dir: str | Path) -> None:
    """Save exact input, result and readable report in a new directory."""
    request = target_json(document["request"])
    result = target_json(document)
    report = render_target_text(document)
    command = "design" if document["operation"] == "design" else "target"
    report += f"\nReplay from this directory:\nhomological-observability {command} request.json --format json\n"
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "request.json").write_text(request, encoding="utf-8")
    (directory / "result.json").write_text(result, encoding="utf-8")
    (directory / "report.txt").write_text(report, encoding="utf-8")
