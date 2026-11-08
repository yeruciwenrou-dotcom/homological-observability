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
        raise ValueError("evaluate does not compute exposure explanations; use analyze")
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


def render_target_text(document: dict) -> str:
    """Explain established conclusions and remaining work in a compact report."""
    result = document["result"]
    lines = [
        f"Target task: {document['operation']} [{document['status']}]",
        "Targets: " + ", ".join(t["name"] for t in document["request"]["targets"]),
        "Scope: exact integer cochains on the full cycle group; raw path records use known endpoints.",
    ]
    if document["operation"] == "design":
        lines.append(
            {
                True: "The candidate pool can determine all targets with the fixed readouts.",
                False: "Even the entire candidate pool cannot determine all targets with the fixed readouts.",
                None: "Candidate-pool feasibility has not been established.",
            }[result["feasible"]]
        )
        lines.append(
            f"Fixed channels: {result['fixed_count']}; candidate channels: {result['candidate_count']}"
        )
        if result["minimum_proven"]:
            lines.append(
                f"Minimum added channels: {result['minimum_added']} (proved); total: {result['minimum_total']}."
            )
        elif result["feasible"] is not False:
            lower = result["lower_bound_added"]
            upper = result["upper_bound_added"]
            lines.append("The minimum has not been proved.")
            lines.append(
                f"Added-channel bounds: lower {lower if lower is not None else 'unknown'}; "
                f"upper {upper if upper is not None else 'unknown'}."
            )
        for solution in result["solutions"]:
            lines.append(
                "Add: " + (", ".join(solution["added_ids"]) or "no additional channel")
            )
        if result["feasible"] is True:
            lines.append(
                "All minimum choices are shown."
                if result["ties_complete"]
                else "Further choices may remain unsearched or unreturned."
            )
        if not result["certificates_complete"]:
            lines.append("Some reconstruction certificates remain unfinished.")
        if any(s["added_count"] for s in result["solutions"]):
            lines.append(
                "Additional channels apply to future collection or replay from available full paths."
            )
    else:
        lines.append(
            {
                True: "The fixed readouts determine every target for legal records.",
                False: "The fixed readouts do not determine every target: distinct histories can share a record.",
                None: "Target sufficiency has not been established.",
            }[result["sufficient"]]
        )
        if document["operation"] == "evaluate":
            lines.append(
                {
                    True: "The supplied record satisfies the integer-image constraints.",
                    False: "The supplied record is outside the legal integer image; no target value is returned.",
                    None: "Record legality has not been established; no target value is returned.",
                }[result["legal_record"]]
            )
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
            elif result["legal_record"] is True:
                lines.append(
                    "No unique target value has been established for this record."
                )
        else:
            certificate = result["certificate"]
            if not result["certificate_complete"]:
                lines.append(
                    "The certificate remains unfinished; the conclusion above is retained."
                )
            if certificate and certificate["kind"] == "ambiguity":
                lines.append(
                    "An integer closed-chain witness leaves every fixed readout unchanged:"
                )
                lines.extend(
                    f"  {target['name']} changes by {row[0]}"
                    for target, row in zip(
                        document["request"]["targets"],
                        certificate["target_change"]["data"],
                    )
                )
            elif certificate:
                lines.append("An exact decoder is included in the structured result.")
    if document["limit"]:
        lines.append(
            f"Stopped at {document['limit']['stage']}: {document['limit']['resource']}."
        )
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
            "Exposure scales and asymptotic coefficients are not finite-time prediction probabilities."
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
