"""Validated graph and integer-readout models for the research kernel.

The exposure, visible-image, and hidden filtrations depend only on the finite
support graph and integer edge cochains, so rate magnitudes are not model
inputs.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from fractions import Fraction
from numbers import Real
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx

from ._integer_io import check_integer_text, parse_json_integer
from ._sampling import Alpha, parse_alpha, validate_exact_alpha

Edge = tuple[str, str]


def canonical_edge(u: str, v: str) -> Edge:
    """Return the public orientation of an undirected edge."""

    if not isinstance(u, str) or not isinstance(v, str):
        raise TypeError("vertex identifiers must be strings")
    if not u or not v:
        raise ValueError("vertex identifiers must be nonempty")
    if u == v:
        raise ValueError("self-loops are outside the supported graph scope")
    return (u, v) if u < v else (v, u)


def normalize_graph(
    vertices: Iterable[str], edges: Iterable[tuple[str, str]]
) -> tuple[tuple[str, ...], tuple[Edge, ...]]:
    """Validate and deterministically order a connected simple graph."""

    raw_vertices = tuple(vertices)
    if not raw_vertices:
        raise ValueError("the graph must contain at least one vertex")
    if any(not isinstance(vertex, str) for vertex in raw_vertices):
        raise TypeError("vertex identifiers must be strings")
    if any(not vertex for vertex in raw_vertices):
        raise ValueError("vertex identifiers must be nonempty")
    if len(set(raw_vertices)) != len(raw_vertices):
        raise ValueError("vertex identifiers must be unique")
    ordered_vertices = tuple(sorted(raw_vertices))

    raw_edges = tuple(edges)
    ordered_edges = tuple(sorted(canonical_edge(u, v) for u, v in raw_edges))
    if len(set(ordered_edges)) != len(ordered_edges):
        raise ValueError("parallel or duplicate edges are outside the supported scope")
    vertex_set = set(ordered_vertices)
    if any(u not in vertex_set or v not in vertex_set for u, v in ordered_edges):
        raise ValueError("every edge endpoint must occur in vertices")

    graph = nx.Graph()
    graph.add_nodes_from(ordered_vertices)
    graph.add_edges_from(ordered_edges)
    if not nx.is_connected(graph):
        raise ValueError("the graph must be connected")
    return ordered_vertices, ordered_edges


@dataclass(frozen=True)
class IntegerReadout:
    """One integer 1-cochain on the public edge orientation."""

    name: str
    coefficients: tuple[tuple[Edge, int], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("readout names must be nonempty strings")
        if not isinstance(self.coefficients, tuple):
            raise TypeError("normalized readout coefficients must be a tuple")
        seen = set()
        for item in self.coefficients:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("readout entries must be (edge, integer) pairs")
            edge, coefficient = item
            if not isinstance(edge, tuple) or len(edge) != 2:
                raise TypeError("readout keys must be oriented string edge pairs")
            if edge != canonical_edge(*edge) or edge in seen:
                raise ValueError("readout edges must be canonical and unique")
            if isinstance(coefficient, bool) or not isinstance(coefficient, int):
                raise TypeError("readout coefficients must be integers")
            check_integer_text(coefficient, label="readout coefficient")
            seen.add(edge)
        if self.coefficients != tuple(sorted(self.coefficients)):
            raise ValueError("readout coefficients must use normalized edge order")

    @classmethod
    def from_mapping(
        cls,
        name: str,
        coefficients: Mapping[tuple[str, str], int],
        *,
        allowed_edges: Sequence[Edge] | None = None,
    ) -> IntegerReadout:
        if not isinstance(name, str) or not name:
            raise ValueError("readout names must be nonempty strings")
        normalized: dict[Edge, int] = {}
        for raw_edge, coefficient in coefficients.items():
            if (
                not isinstance(raw_edge, tuple)
                or len(raw_edge) != 2
                or not all(isinstance(vertex, str) for vertex in raw_edge)
            ):
                raise TypeError("readout keys must be oriented string edge pairs")
            if isinstance(coefficient, bool) or not isinstance(coefficient, int):
                raise TypeError("readout coefficients must be integers")
            edge = canonical_edge(*raw_edge)
            signed_coefficient = coefficient if raw_edge == edge else -coefficient
            normalized[edge] = normalized.get(edge, 0) + signed_coefficient

        if allowed_edges is not None:
            unknown = set(normalized) - set(allowed_edges)
            if unknown:
                raise ValueError(
                    f"readout refers to unknown edges: {sorted(unknown)!r}"
                )
        return cls(
            name=name,
            coefficients=tuple(
                (edge, coefficient)
                for edge, coefficient in sorted(normalized.items())
                if coefficient
            ),
        )

    def as_mapping(self) -> Mapping[Edge, int]:
        return MappingProxyType(dict(self.coefficients))


@dataclass(frozen=True)
class GraphModel:
    """A normalized input to the exact research kernel."""

    name: str
    vertices: tuple[str, ...]
    edges: tuple[Edge, ...]
    readouts: tuple[IntegerReadout, ...] = ()
    max_layer: int | None = None
    max_cycles: int | None = None
    alpha: Alpha | None = None
    observation_time: float | None = None
    sampling_interval: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("model names must be nonempty strings")
        vertices, edges = normalize_graph(self.vertices, self.edges)
        if self.vertices != vertices or self.edges != edges:
            raise ValueError(
                "graph must use normalized vertex and edge tuples; use create"
            )
        if not isinstance(self.readouts, tuple) or any(
            not isinstance(readout, IntegerReadout) for readout in self.readouts
        ):
            raise TypeError("readouts must be a tuple of IntegerReadout objects")
        names = [readout.name for readout in self.readouts]
        if len(set(names)) != len(names):
            raise ValueError("readout names must be unique")
        for readout in self.readouts:
            if set(readout.as_mapping()) - set(self.edges):
                raise ValueError("readout refers to unknown edges")
        for label, value in (
            ("max_layer", self.max_layer),
            ("max_cycles", self.max_cycles),
        ):
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                    raise ValueError(f"{label} must be a positive integer")
                check_integer_text(value, label=label)
        values = validate_sampling_parameters(
            alpha=self.alpha,
            observation_time=self.observation_time,
            sampling_interval=self.sampling_interval,
        )
        for label, value in zip(
            ("alpha", "observation_time", "sampling_interval"), values
        ):
            object.__setattr__(self, label, value)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        vertices: Iterable[str],
        edges: Iterable[tuple[str, str]],
        readouts: Iterable[tuple[str, Mapping[tuple[str, str], int]]] = (),
        max_layer: int | None = None,
        max_cycles: int | None = None,
        alpha: Alpha | None = None,
        observation_time: float | None = None,
        sampling_interval: float | None = None,
    ) -> GraphModel:
        ordered_vertices, ordered_edges = normalize_graph(vertices, edges)
        normalized_readouts = tuple(
            IntegerReadout.from_mapping(
                readout_name,
                coefficients,
                allowed_edges=ordered_edges,
            )
            for readout_name, coefficients in readouts
        )
        return cls(
            name=name,
            vertices=ordered_vertices,
            edges=ordered_edges,
            readouts=normalized_readouts,
            max_layer=max_layer,
            max_cycles=max_cycles,
            alpha=alpha,
            observation_time=observation_time,
            sampling_interval=sampling_interval,
        )


def _validated_sampling_scalar(value: float, *, label: str, positive: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{label} must be a real number")
    try:
        converted = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} is outside the finite float range") from error
    valid_sign = converted > 0.0 if positive else converted >= 0.0
    if not math.isfinite(converted) or not valid_sign:
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{label} must be finite and {qualifier}")
    return converted


def validate_sampling_parameters(
    *,
    alpha: Alpha | None,
    observation_time: float | None,
    sampling_interval: float | None,
) -> tuple[Alpha | None, float | None, float | None]:
    """Validate the mutually exclusive asymptotic and finite-scale inputs."""

    if isinstance(alpha, Fraction):
        alpha = validate_exact_alpha(alpha)
    elif alpha is not None:
        alpha = _validated_sampling_scalar(
            alpha,
            label="alpha",
            positive=False,
        )
    if (observation_time is None) != (sampling_interval is None):
        raise ValueError(
            "observation_time and sampling_interval must be supplied together"
        )
    if observation_time is not None and sampling_interval is not None:
        if alpha is not None:
            raise ValueError(
                "alpha is mutually exclusive with observation_time and sampling_interval"
            )
        observation_time = _validated_sampling_scalar(
            observation_time,
            label="observation_time",
            positive=True,
        )
        sampling_interval = _validated_sampling_scalar(
            sampling_interval,
            label="sampling_interval",
            positive=True,
        )
    return alpha, observation_time, sampling_interval


def _object(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC) or any(
        not isinstance(key, str) for key in value
    ):
        raise TypeError(f"{label} must be a JSON object with string keys")
    return value


def _array(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a JSON array")
    return value


def _reject_unknown_fields(
    value: Mapping[str, Any], *, allowed: set[str], label: str
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {sorted(unknown)!r}")


def parse_model(payload: Mapping[str, Any]) -> GraphModel:
    """Parse the JSON model contract into a validated graph model."""

    root = _object(payload, label="model")
    _reject_unknown_fields(
        root,
        allowed={"schema_version", "name", "vertices", "edges", "readouts", "analysis"},
        label="model",
    )
    schema_version = root.get("schema_version")
    if isinstance(schema_version, bool) or schema_version not in (1, 2):
        raise ValueError("schema_version must equal 1 or 2")

    vertices = _array(root.get("vertices"), label="vertices")
    raw_edges = _array(root.get("edges"), label="edges")
    edges: list[tuple[str, str]] = []
    for index, raw_edge in enumerate(raw_edges):
        edge = _array(raw_edge, label=f"edges[{index}]")
        if len(edge) != 2 or any(not isinstance(vertex, str) for vertex in edge):
            raise TypeError(f"edges[{index}] must contain exactly two string vertices")
        edges.append((edge[0], edge[1]))

    readouts: list[tuple[str, Mapping[tuple[str, str], int]]] = []
    raw_readouts = _array(root.get("readouts", []), label="readouts")
    for readout_index, raw_readout in enumerate(raw_readouts):
        readout = _object(raw_readout, label=f"readouts[{readout_index}]")
        _reject_unknown_fields(
            readout,
            allowed={"name", "coefficients"},
            label=f"readouts[{readout_index}]",
        )
        coefficients: dict[tuple[str, str], int] = {}
        public_edges: set[Edge] = set()
        raw_coefficients = _array(
            readout.get("coefficients"),
            label=f"readouts[{readout_index}].coefficients",
        )
        for coefficient_index, raw_coefficient in enumerate(raw_coefficients):
            label = f"readouts[{readout_index}].coefficients[{coefficient_index}]"
            coefficient = _object(raw_coefficient, label=label)
            _reject_unknown_fields(
                coefficient,
                allowed={"edge", "coefficient"},
                label=label,
            )
            raw_edge = _array(coefficient.get("edge"), label=label + ".edge")
            if len(raw_edge) != 2 or any(
                not isinstance(vertex, str) for vertex in raw_edge
            ):
                raise TypeError(f"{label}.edge must contain exactly two strings")
            oriented_edge = (raw_edge[0], raw_edge[1])
            public_edge = canonical_edge(*oriented_edge)
            if public_edge in public_edges:
                raise ValueError(f"{label}.edge duplicates an earlier undirected edge")
            public_edges.add(public_edge)
            value = coefficient.get("coefficient")
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{label}.coefficient must be an integer")
            coefficients[oriented_edge] = value
        readouts.append((readout.get("name"), coefficients))

    analysis = _object(root.get("analysis", {}), label="analysis")
    _reject_unknown_fields(
        analysis,
        allowed={
            "max_layer",
            "max_cycles",
            "alpha",
            "observation_time",
            "sampling_interval",
        },
        label="analysis",
    )
    return GraphModel.create(
        name=root.get("name"),
        vertices=vertices,
        edges=edges,
        readouts=readouts,
        max_layer=analysis.get("max_layer"),
        max_cycles=analysis.get("max_cycles"),
        alpha=parse_alpha(analysis.get("alpha"), schema_version=schema_version),
        observation_time=analysis.get("observation_time"),
        sampling_interval=analysis.get("sampling_interval"),
    )


def load_model(path: str | Path) -> GraphModel:
    """Load and validate a UTF-8 JSON model file."""

    model_path = Path(path)
    try:
        payload = json.loads(
            model_path.read_text(encoding="utf-8"), parse_int=parse_json_integer
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON model {model_path}: {error.msg}") from error
    return parse_model(_object(payload, label="model"))
