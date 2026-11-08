"""Versioned target-task requests, human reports, and replay bundles."""

from __future__ import annotations

import json
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
    if operation == "evaluate":
        record = _object(record, label="record")
        _reject_unknown_fields(
            record, allowed={"kind", "values", "start", "end"}, label="record"
        )
        if "kind" not in record or "values" not in record:
            raise ValueError("record requires kind and values")
    elif record is not None:
        raise ValueError("records are only used by evaluate requests")
    return operation, model, targets, candidates, limits, reverse, record


def load_target_request(path: str | Path) -> dict:
    """Load a strict JSON request; semantic validation occurs on execution."""
    payload = json.loads(
        Path(path).read_text(encoding="utf-8"), parse_int=parse_json_integer
    )
    _parse_request(payload)
    return payload


def run_target_request(document: dict) -> dict:
    """Replay an authored request or the request embedded in an earlier result."""
    operation, model, targets, candidates, limits, reverse, record = _parse_request(
        document
    )
    options = {"limits": limits, "reverse_tree_order": reverse}
    if operation == "design":
        return design_readouts(model, targets, candidates, **options)
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
    return analyze_target(model, targets, **options)


def render_target_text(document: dict) -> str:
    """Explain established conclusions and remaining work in a compact report."""
    result = document["result"]
    lines = [
        f"Target task: {document['operation']} [{document['status']}]",
        "Scope: exact integer cochains on the full cycle group, with known endpoints.",
    ]
    if document["operation"] == "design":
        lines.extend(
            [
                f"Candidate pool feasible: {result['feasible']}",
                f"Fixed channels: {result['fixed_count']}; candidate channels: {result['candidate_count']}",
                f"Minimum added channels: {result['minimum_added']} (proved: {result['minimum_proven']})",
                f"Added-channel bounds: [{result['lower_bound_added']}, {result['upper_bound_added']}]",
                f"Minimum total channels: {result['minimum_total']}",
                f"All tied choices returned: {result['ties_complete']}",
                f"Returned reconstruction certificates complete: {result['certificates_complete']}",
            ]
        )
        for solution in result["solutions"]:
            lines.append(
                "Add: " + (", ".join(solution["added_ids"]) or "no additional channel")
            )
        lines.append(
            "Additional channels apply to future collection or replay from available full paths."
        )
    else:
        lines.append(f"Fixed records determine all targets: {result['sufficient']}")
        if document["operation"] == "evaluate":
            lines.extend(
                [
                    f"Record belongs to the legal integer image: {result['legal_record']}",
                    f"Target values ({result['value_kind']}): {result['target_values']}",
                ]
            )
            if result["reason"]:
                lines.append(f"Reason: {result['reason']}")
        else:
            certificate = result["certificate"]
            lines.append(
                f"Integer/reconstruction certificate complete: {result['certificate_complete']}"
            )
            if certificate and certificate["kind"] == "ambiguity":
                lines.append(
                    "The integer closed-chain witness leaves all fixed records unchanged and changes the target."
                )
    if document["limit"]:
        lines.append(
            f"Stopped at {document['limit']['stage']}: {document['limit']['resource']}."
        )
    lines.append(
        "Exposure-scale explanation: not requested; no cycle enumeration is used by this task."
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
