"""Built-in, versioned examples for the public API and command line."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from importlib import resources
from typing import Any

from .model import GraphModel, parse_model


class ExampleCategory(str, Enum):
    """Scientific role of a built-in example."""

    DEMONSTRATION = "DEMONSTRATION"


@dataclass(frozen=True)
class ExampleSpec:
    """Metadata and package resource for one built-in model."""

    name: str
    title: str
    category: ExampleCategory
    description: str
    resource_name: str


_EXAMPLES = (
    ExampleSpec(
        name="wedge-c3-c5",
        title="Wedge of C3 and C5 with an integer readout",
        category=ExampleCategory.DEMONSTRATION,
        description=(
            "A two-cycle model with staged exposure, a hidden direction, and a "
            "finite-index visible quotient."
        ),
        resource_name="wedge_c3_c5.json",
    ),
)
_BY_NAME = {example.name: example for example in _EXAMPLES}


def list_examples() -> tuple[ExampleSpec, ...]:
    """Return the deterministic built-in example registry."""

    return _EXAMPLES


def get_example(name: str) -> ExampleSpec:
    """Return example metadata or raise a controlled lookup error."""

    try:
        return _BY_NAME[name]
    except KeyError as error:
        available = ", ".join(sorted(_BY_NAME))
        raise ValueError(
            f"unknown example {name!r}; available examples: {available}"
        ) from error


def load_example(name: str) -> GraphModel:
    """Load and validate one package-resident example model."""

    example = get_example(name)
    resource = resources.files("homological_observability").joinpath(
        "data", "examples", example.resource_name
    )
    payload: Any = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"built-in example {name!r} is not a JSON object")
    return parse_model(payload)


def examples_to_dict() -> dict[str, Any]:
    """Return the stable machine-readable example-list contract."""

    return {
        "schema_name": "homological-observability.examples",
        "schema_version": 1,
        "examples": [
            {
                "name": example.name,
                "title": example.title,
                "category": example.category.value,
                "description": example.description,
            }
            for example in _EXAMPLES
        ],
    }
