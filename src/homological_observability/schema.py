"""Access to versioned machine-readable package schemas."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def _load_schema(name: str) -> dict[str, Any]:
    resource = resources.files("homological_observability").joinpath("schemas", name)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"the bundled {name} schema must be a JSON object")
    return payload


def _versioned_schema(
    name: str, version: int | None, latest: int, previous: int
) -> dict[str, Any]:
    if version is None:
        version = latest
    if type(version) is not int or version not in (previous, latest):
        raise ValueError(f"{name} schema version must be {previous} or {latest}")
    suffix = "" if version == latest else f"-v{version}"
    return _load_schema(f"{name}{suffix}.schema.json")


def load_analysis_schema(*, version: int | None = None) -> dict[str, Any]:
    """Load a fresh copy of the bundled analysis-result JSON Schema."""

    return _versioned_schema("analysis", version, latest=3, previous=2)


def load_model_schema(*, version: int | None = None) -> dict[str, Any]:
    """Load a fresh copy of the bundled model-input JSON Schema."""

    return _versioned_schema("model", version, latest=2, previous=1)


def load_examples_schema() -> dict[str, Any]:
    """Load a fresh copy of the bundled example-registry JSON Schema."""

    return _load_schema("examples.schema.json")


def load_reproduction_schema() -> dict[str, Any]:
    """Load a fresh copy of the bundled reproduction-result JSON Schema."""

    return _load_schema("reproduction.schema.json")


def load_error_schema() -> dict[str, Any]:
    """Load a fresh copy of the bundled controlled-error JSON Schema."""

    return _load_schema("error.schema.json")


def load_critical_model_schema() -> dict[str, Any]:
    """Load a fresh copy of the bundled critical-model JSON Schema."""

    return _load_schema("critical-model.schema.json")


def load_critical_experiment_schema() -> dict[str, Any]:
    """Load a fresh copy of the bundled critical-experiment JSON Schema."""

    return _load_schema("critical-experiment.schema.json")


def load_study_schema(*, version: int | None = None) -> dict[str, Any]:
    """Load the authored configuration-study JSON Schema."""

    return _versioned_schema("study", version, latest=2, previous=1)


def load_comparison_schema(*, version: int | None = None) -> dict[str, Any]:
    """Load the configuration-comparison result JSON Schema."""

    return _versioned_schema("comparison", version, latest=2, previous=1)
