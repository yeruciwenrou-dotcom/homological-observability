#!/usr/bin/env python3
"""Validate every public JSON document against its bundled schema."""

from __future__ import annotations

import copy
import json
from fractions import Fraction
from pathlib import Path

from jsonschema import Draft202012Validator

import homological_observability as ho
from homological_observability.examples import examples_to_dict, load_example

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    schemas = {
        "analysis": ho.load_analysis_schema(),
        "model": ho.load_model_schema(),
        "examples": ho.load_examples_schema(),
        "reproduction": ho.load_reproduction_schema(),
        "error": ho.load_error_schema(),
        "critical_model": ho.load_critical_model_schema(),
        "critical_experiment": ho.load_critical_experiment_schema(),
        "study": ho.load_study_schema(),
        "comparison": ho.load_comparison_schema(),
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    validators = {
        name: Draft202012Validator(schema) for name, schema in schemas.items()
    }

    model = load_example("wedge-c3-c5")
    validators["model"].validate(ho.model_to_dict(model))
    validators["analysis"].validate(ho.analysis_to_dict(ho.analyze_model(model)))
    validators["examples"].validate(examples_to_dict())

    limited_payload = ho.model_to_dict(model)
    limited_payload["analysis"]["max_cycles"] = 1
    limited_result = ho.analyze_model(ho.parse_model(limited_payload))
    validators["analysis"].validate(ho.analysis_to_dict(limited_result))

    partial_payload = ho.model_to_dict(model)
    partial_payload["analysis"]["max_layer"] = 2
    partial_result = ho.analyze_model(ho.parse_model(partial_payload))
    partial_document = ho.analysis_to_dict(partial_result)
    validators["analysis"].validate(partial_document)
    if partial_result.status is not ho.AnalysisStatus.PARTIAL_HORIZON:
        raise AssertionError("the low-layer validation case must be partial")
    partial_document["status"] = "COMPLETE"
    if validators["analysis"].is_valid(partial_document):
        raise AssertionError("the analysis schema accepted a false COMPLETE status")

    validators["reproduction"].validate(
        {
            "schema_name": "homological-observability.reproduction",
            "schema_version": 1,
            "artifact_role": "canonical-paper-evidence",
            "status": "PASS",
            "checked_against_frozen_reference": True,
            "output_directory": "generated_results",
            "files": [{"name": "evidence.csv", "sha256": "0" * 64}],
        }
    )
    validators["reproduction"].validate(
        {
            "schema_name": "homological-observability.reproduction",
            "schema_version": 1,
            "artifact_role": "canonical-paper-evidence",
            "status": "FAIL",
            "message": "reference mismatch",
        }
    )
    validators["error"].validate(
        {
            "schema_name": "homological-observability.error",
            "schema_version": 1,
            "status": "ERROR",
            "message": "invalid input",
        }
    )

    critical_vertices = ("v0", "v1", "v2")
    critical_edges = (("v0", "v1"), ("v1", "v2"), ("v2", "v0"))
    critical_rates = {
        (start, end): Fraction(1)
        for edge in critical_edges
        for start, end in (edge, edge[::-1])
    }
    critical_model = ho.CriticalModel.create(
        name="c3-critical-schema-check",
        vertices=critical_vertices,
        edges=critical_edges,
        rates=critical_rates,
        layer=2,
        theta=Fraction(1),
    )
    validators["critical_model"].validate(ho.critical_model_to_dict(critical_model))
    critical_document = ho.critical_experiment_to_dict(
        ho.analyze_critical_model(critical_model)
    )
    validators["critical_experiment"].validate(critical_document)

    public_critical_model = ho.load_critical_model(
        ROOT / "examples/biased_c4_critical.json"
    )
    validators["critical_model"].validate(
        ho.critical_model_to_dict(public_critical_model)
    )
    public_critical_document = json.loads(
        (ROOT / "examples/biased_c4_critical_result.json").read_text(encoding="utf-8")
    )
    validators["critical_experiment"].validate(public_critical_document)
    fresh_critical_document = ho.critical_experiment_to_dict(
        ho.analyze_critical_model(public_critical_model)
    )
    validators["critical_experiment"].validate(fresh_critical_document)
    # The published example remains the original 1.1.0 record. A later software
    # producer may change its version label while every scientific field stays
    # exactly equal; no frozen evidence is rewritten to impersonate a new run.
    if public_critical_document["software"]["version"] != "1.1.0":
        raise AssertionError("the public critical example lost its frozen producer")
    if fresh_critical_document["software"]["version"] != ho.__version__:
        raise AssertionError("the fresh critical result has the wrong producer")
    frozen_science = copy.deepcopy(public_critical_document)
    fresh_science = copy.deepcopy(fresh_critical_document)
    frozen_science["software"].pop("version")
    fresh_science["software"].pop("version")
    if frozen_science != fresh_science:
        raise AssertionError("the public critical example's scientific result changed")
    false_limited_document = copy.deepcopy(critical_document)
    false_limited_document["status"] = "LIMIT_REACHED"
    if validators["critical_experiment"].is_valid(false_limited_document):
        raise AssertionError(
            "the critical schema accepted complete data under LIMIT_REACHED"
        )
    limited_critical_model = ho.CriticalModel.create(
        name="c3-critical-schema-limit-check",
        vertices=critical_vertices,
        edges=critical_edges,
        rates=critical_rates,
        layer=2,
        theta=Fraction(1),
        limits=ho.CriticalLimits.create(max_paths=1),
    )
    limited_critical_document = ho.critical_experiment_to_dict(
        ho.analyze_critical_model(limited_critical_model)
    )
    validators["critical_experiment"].validate(limited_critical_document)
    if limited_critical_document["catalogue"] is not None:
        raise AssertionError("a limited critical result exposed a partial catalogue")
    false_complete_document = copy.deepcopy(limited_critical_document)
    false_complete_document["status"] = "COMPLETE"
    if validators["critical_experiment"].is_valid(false_complete_document):
        raise AssertionError(
            "the critical schema accepted a resource-limited result as COMPLETE"
        )

    for name in ("minimal", "bridge", "theta"):
        study = ho.load_study_example(name)
        validators["study"].validate(study)
        validators["comparison"].validate(ho.compare_configurations(study))
    incomplete_study = ho.load_study_example("bridge")
    incomplete_study["configurations"][0]["readouts"] = "invalid counter payload"
    validators["comparison"].validate(ho.compare_configurations(incomplete_study))
    for settings in ({"max_layer": 2}, {"max_cycles": 1}):
        bounded_study = ho.load_study_example("bridge")
        bounded_study["analysis"].update(settings)
        bounded_result = ho.compare_configurations(bounded_study)
        validators["comparison"].validate(bounded_result)
        false_complete = copy.deepcopy(bounded_result)
        false_complete["status"] = "COMPLETE"
        if validators["comparison"].is_valid(false_complete):
            raise AssertionError("the comparison schema accepted false completeness")

    print("PASS: all public JSON documents satisfy their bundled schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
