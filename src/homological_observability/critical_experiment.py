"""Public contract for exact critical-layer marked-Poisson experiments."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterator
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, fields, is_dataclass, replace
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from math import factorial
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from ._critical_catalogue import (
    CriticalEndpointComponent as _CriticalEndpointComponent,
)
from ._critical_catalogue import (
    CriticalPathCatalogue as _InternalCatalogue,
)
from ._critical_catalogue import (
    MarkedPoissonExperiment as _InternalExperiment,
)
from ._critical_catalogue import QuotientElement as _InternalElement
from ._critical_catalogue import build_marked_poisson_experiment
from ._integer_io import (
    check_integer_text,
    decimal_digits,
    integer_text_limit,
    parse_json_integer,
)
from .analysis import AnalysisStatus, _analyze_topology
from .integer_lattice import QuotientInvariants
from .model import GraphModel, parse_model
from .version import __version__

ExactScalar: TypeAlias = int | Decimal | Fraction | str
DirectedEdge: TypeAlias = tuple[str, str]

CRITICAL_MODEL_SCHEMA_VERSION = 1
CRITICAL_EXPERIMENT_SCHEMA_NAME = "homological-observability.critical-experiment"
CRITICAL_EXPERIMENT_SCHEMA_VERSION = 1
CRITICAL_ARTIFACT_ROLE = "fresh-critical-experiment"

_EXACT_STRING = re.compile(
    r"-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*|(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)?\Z"
)


class CriticalStatus(str, Enum):
    """Completion states for the independent critical experiment task."""

    COMPLETE = "COMPLETE"
    LIMIT_REACHED = "LIMIT_REACHED"


@dataclass(frozen=True)
class CriticalLimits:
    """Explicit resource ceilings for one critical experiment request."""

    max_paths: int = 100_000
    max_estimated_integer_digits: int = 4096
    max_integer_digits: int = 4096
    max_output_records: int = 100_000
    max_cycles: int = 100_000

    def __post_init__(self) -> None:
        values = {
            "max_paths": self.max_paths,
            "max_estimated_integer_digits": self.max_estimated_integer_digits,
            "max_integer_digits": self.max_integer_digits,
            "max_output_records": self.max_output_records,
            "max_cycles": self.max_cycles,
        }
        for label, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
            check_integer_text(value, label=label)

        if self.max_integer_digits > integer_text_limit():
            raise ValueError(
                "max_integer_digits exceeds the decimal input/output limit "
                f"of {integer_text_limit()} digits"
            )

    @classmethod
    def create(
        cls,
        *,
        max_paths: int = 100_000,
        max_estimated_integer_digits: int = 4096,
        max_integer_digits: int = 4096,
        max_output_records: int = 100_000,
        max_cycles: int = 100_000,
    ) -> CriticalLimits:
        return cls(
            max_paths=max_paths,
            max_estimated_integer_digits=max_estimated_integer_digits,
            max_integer_digits=max_integer_digits,
            max_output_records=max_output_records,
            max_cycles=max_cycles,
        )


def _exact_positive(value: ExactScalar, *, label: str) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"{label} must be an integer, Decimal, Fraction, or exact string"
        )
    if isinstance(value, str):
        if not _EXACT_STRING.fullmatch(value):
            raise ValueError(f"{label} is not a canonical exact number")
        if "/" in value:
            parts = value.split("/")
            if any(len(part.lstrip("-")) > integer_text_limit() for part in parts):
                raise ValueError(f"{label} exceeds the decimal input/output limit")
            value = Fraction(value)
        else:
            try:
                value = Decimal(value)
            except ArithmeticError as error:
                raise ValueError(f"{label} is not a valid exact number") from error
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{label} must be finite and positive")
        # Bound decimal expansion before Fraction can allocate a huge power of ten.
        # This is an input-representation check, separate from scientific budgets.
        _, digits, exponent = value.as_tuple()
        trailing = 0
        for digit in reversed(digits):
            if digit:
                break
            trailing += 1
        exponent += trailing
        if value.adjusted() >= integer_text_limit() or exponent < -integer_text_limit():
            raise ValueError(f"{label} exceeds the decimal input/output limit")
        value = Fraction(value)
    if not isinstance(value, int | Fraction):
        raise TypeError(
            f"{label} must be an integer, Decimal, Fraction, or exact string"
        )
    result = Fraction(value)
    if result <= 0:
        raise ValueError(f"{label} must be positive")
    check_integer_text(result.numerator, label=label)
    check_integer_text(result.denominator, label=label)
    return result


def _expected_directed_edges(edges: tuple[tuple[str, str], ...]) -> set[DirectedEdge]:
    return {(u, v) for edge in edges for u, v in (edge, edge[::-1])}


def _normalize_rates(
    edges: tuple[tuple[str, str], ...],
    rates: Mapping[DirectedEdge, ExactScalar],
) -> tuple[tuple[DirectedEdge, Fraction], ...]:
    if not isinstance(rates, MappingABC):
        raise TypeError("rates must be a mapping from directed edges to exact values")
    normalized: dict[DirectedEdge, Fraction] = {}
    for edge, value in rates.items():
        if (
            not isinstance(edge, tuple)
            or len(edge) != 2
            or not all(isinstance(vertex, str) for vertex in edge)
        ):
            raise TypeError("rate keys must be directed string edge pairs")
        if edge in normalized:
            raise ValueError(f"directed rate {edge!r} is duplicated")
        normalized[edge] = _exact_positive(value, label=f"rate {edge!r}")
    expected = _expected_directed_edges(edges)
    if set(normalized) != expected:
        missing = sorted(expected - set(normalized))
        extra = sorted(set(normalized) - expected)
        raise ValueError(
            "directed rates do not match the support: "
            f"missing={missing!r}, extra={extra!r}"
        )
    return tuple(sorted(normalized.items()))


@dataclass(frozen=True)
class CriticalModel:
    """Validated graph, rates, layer, intensity, and resource policy."""

    graph: GraphModel
    rates: tuple[tuple[DirectedEdge, Fraction], ...]
    layer: int
    theta: Fraction
    limits: CriticalLimits
    audit_paths: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.graph, GraphModel):
            raise TypeError("graph must be a GraphModel")
        if (
            isinstance(self.layer, bool)
            or not isinstance(self.layer, int)
            or self.layer < 2
        ):
            raise ValueError("layer must be an integer greater than or equal to 2")
        if self.graph.max_layer != self.layer:
            raise ValueError("graph.max_layer must equal the critical layer")
        if not isinstance(self.limits, CriticalLimits):
            raise TypeError("limits must be a CriticalLimits instance")
        if self.graph.max_cycles != self.limits.max_cycles:
            raise ValueError("graph.max_cycles must equal limits.max_cycles")
        if not isinstance(self.theta, Fraction) or self.theta <= 0:
            raise TypeError("theta must be a positive Fraction in a normalized model")
        _exact_positive(self.theta, label="theta")
        if not isinstance(self.audit_paths, bool):
            raise TypeError("audit_paths must be boolean")
        normalized_rates = _normalize_rates(self.graph.edges, dict(self.rates))
        if self.rates != normalized_rates:
            raise ValueError("rates must use normalized directed-edge order")

        normalized_graph = GraphModel.create(
            name=self.graph.name,
            vertices=self.graph.vertices,
            edges=self.graph.edges,
            readouts=tuple(
                (readout.name, readout.as_mapping()) for readout in self.graph.readouts
            ),
            max_layer=self.layer,
            max_cycles=self.limits.max_cycles,
        )
        if self.graph != normalized_graph:
            raise ValueError("graph must be a normalized topology model")

    @classmethod
    def create(
        cls,
        *,
        name: str,
        vertices: tuple[str, ...] | list[str],
        edges: tuple[tuple[str, str], ...] | list[tuple[str, str]],
        rates: Mapping[DirectedEdge, ExactScalar],
        layer: int,
        theta: ExactScalar,
        readouts: tuple[tuple[str, Mapping[tuple[str, str], int]], ...] = (),
        limits: CriticalLimits | None = None,
        audit_paths: bool = False,
    ) -> CriticalModel:
        if isinstance(layer, bool) or not isinstance(layer, int) or layer < 2:
            raise ValueError("layer must be an integer greater than or equal to 2")
        if not isinstance(audit_paths, bool):
            raise TypeError("audit_paths must be boolean")
        resource_limits = limits if limits is not None else CriticalLimits.create()
        if not isinstance(resource_limits, CriticalLimits):
            raise TypeError("limits must be a CriticalLimits instance")
        resource_limits = CriticalLimits.create(
            max_paths=resource_limits.max_paths,
            max_estimated_integer_digits=(resource_limits.max_estimated_integer_digits),
            max_integer_digits=resource_limits.max_integer_digits,
            max_output_records=resource_limits.max_output_records,
            max_cycles=resource_limits.max_cycles,
        )
        graph = GraphModel.create(
            name=name,
            vertices=vertices,
            edges=edges,
            readouts=readouts,
            max_layer=layer,
            max_cycles=resource_limits.max_cycles,
        )
        return cls(
            graph=graph,
            rates=_normalize_rates(graph.edges, rates),
            layer=layer,
            theta=_exact_positive(theta, label="theta"),
            limits=resource_limits,
            audit_paths=audit_paths,
        )

    def rate_mapping(self) -> Mapping[DirectedEdge, Fraction]:
        """Return an immutable directed-rate mapping."""

        return MappingProxyType(dict(self.rates))


@dataclass(frozen=True, order=True)
class CriticalMark:
    """Canonical coordinates in a fixed Smith quotient presentation."""

    torsion: tuple[int, ...]
    free: tuple[int, ...]


@dataclass(frozen=True)
class CriticalGroup:
    """Basis-independent invariants with an explicitly dependent coordinate tag."""

    free_rank: int
    torsion_factors: tuple[int, ...]

    @property
    def finite_order(self) -> int | None:
        if self.free_rank:
            return None
        return math.prod(self.torsion_factors, start=1)


@dataclass(frozen=True)
class CriticalInducedReadout:
    """Images of the canonical source generators under the graded readout."""

    torsion_generator_images: tuple[CriticalMark, ...]
    free_generator_images: tuple[CriticalMark, ...]


@dataclass(frozen=True)
class CriticalGeodesic:
    start: str
    end: str
    walk: tuple[str, ...]


@dataclass(frozen=True)
class CriticalWeight:
    start: str
    end: str
    endpoint_distance: int
    mechanism: str
    label: CriticalMark
    visible_label: CriticalMark
    path_count: int
    leading_weight: Fraction


@dataclass(frozen=True)
class CriticalAuditPath:
    walk: tuple[str, ...]
    endpoint_distance: int
    label: CriticalMark
    visible_label: CriticalMark
    rate_product: Fraction
    leading_weight: Fraction


@dataclass(frozen=True)
class CriticalCatalogueResult:
    """Finite aggregated catalogue and optional individual path audit records."""

    geodesics: tuple[CriticalGeodesic, ...]
    weights: tuple[CriticalWeight, ...]
    path_count: int
    audit_paths: tuple[CriticalAuditPath, ...] | None


@dataclass(frozen=True)
class CriticalStationaryLaw:
    vertices: tuple[str, ...]
    generator: tuple[tuple[Fraction, ...], ...]
    probabilities: tuple[Fraction, ...]


@dataclass(frozen=True)
class CriticalLevyAtom:
    label: CriticalMark
    visible_label: CriticalMark
    intensity: Fraction


@dataclass(frozen=True)
class CriticalConditionalMark:
    label: CriticalMark
    visible_label: CriticalMark
    probability: Fraction


@dataclass(frozen=True)
class CriticalEndpointResult:
    start: str
    end: str
    poisson_intensity: Fraction
    mark_law: tuple[CriticalConditionalMark, ...]


@dataclass(frozen=True)
class CriticalLimit:
    resource: str
    limit: int
    observed_or_estimated: int | None
    measurement: str
    complete_components: tuple[str, ...]
    incomplete_components: tuple[str, ...]


@dataclass(frozen=True)
class CriticalResourceUsage:
    path_count: int | None
    output_records: int | None
    maximum_integer_digits: int | None


@dataclass(frozen=True)
class CriticalExperimentResult:
    """Atomic public result for a theorem-derived critical-limit experiment."""

    model: CriticalModel
    status: CriticalStatus
    homology_rank: int | None
    natural_max_layer: int | None
    natural_filtration_complete: bool | None
    graded_group: CriticalGroup | None
    visible_group: CriticalGroup | None
    hidden_group: CriticalGroup | None
    induced_readout: CriticalInducedReadout | None
    stationary_law: CriticalStationaryLaw | None
    catalogue: CriticalCatalogueResult | None
    common_levy_measure: tuple[CriticalLevyAtom, ...] | None
    critical_endpoint_components: tuple[CriticalEndpointResult, ...] | None
    resource_usage: CriticalResourceUsage
    limit: CriticalLimit | None

    def __post_init__(self) -> None:
        if not isinstance(self.model, CriticalModel):
            raise TypeError("model must be a CriticalModel")
        if not isinstance(self.status, CriticalStatus):
            raise TypeError("status must be a CriticalStatus")
        components = (
            self.graded_group,
            self.visible_group,
            self.hidden_group,
            self.induced_readout,
            self.stationary_law,
            self.catalogue,
            self.common_levy_measure,
            self.critical_endpoint_components,
        )
        if self.status is CriticalStatus.COMPLETE:
            if any(component is None for component in components):
                raise ValueError("a complete result must carry every component")
            if self.limit is not None:
                raise ValueError("a complete result cannot carry a resource limit")
        else:
            if any(component is not None for component in components):
                raise ValueError("a limited result cannot carry partial components")
            if self.limit is None:
                raise ValueError("a limited result must identify its resource limit")

    @property
    def is_complete(self) -> bool:
        return self.status is CriticalStatus.COMPLETE


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


def _reject_unknown(value: Mapping[str, Any], *, allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {sorted(unknown)!r}")


def parse_critical_model(payload: Mapping[str, Any]) -> CriticalModel:
    """Parse an exact-valued mapping; use ``load_critical_model`` for JSON files."""

    root = _object(payload, label="critical model")
    _reject_unknown(
        root,
        allowed={
            "schema_version",
            "name",
            "vertices",
            "edges",
            "readouts",
            "rates",
            "critical",
        },
        label="critical model",
    )
    if isinstance(root.get("schema_version"), bool) or root.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")

    critical = _object(root.get("critical"), label="critical")
    _reject_unknown(
        critical,
        allowed={"layer", "theta", "limits", "audit_paths"},
        label="critical",
    )
    layer = critical.get("layer")
    if isinstance(layer, bool) or not isinstance(layer, int) or layer < 2:
        raise ValueError("critical.layer must be an integer greater than or equal to 2")
    audit_paths = critical.get("audit_paths", False)
    if not isinstance(audit_paths, bool):
        raise TypeError("critical.audit_paths must be boolean")
    limits_value = _object(critical.get("limits"), label="critical.limits")
    _reject_unknown(
        limits_value,
        allowed={
            "max_paths",
            "max_estimated_integer_digits",
            "max_integer_digits",
            "max_output_records",
            "max_cycles",
        },
        label="critical.limits",
    )
    limits = CriticalLimits.create(
        max_paths=limits_value.get("max_paths"),
        max_estimated_integer_digits=limits_value.get("max_estimated_integer_digits"),
        max_integer_digits=limits_value.get("max_integer_digits"),
        max_output_records=limits_value.get("max_output_records"),
        max_cycles=limits_value.get("max_cycles"),
    )

    raw_rates = _array(root.get("rates"), label="rates")
    rates: dict[DirectedEdge, ExactScalar] = {}
    for index, raw_rate in enumerate(raw_rates):
        label = f"rates[{index}]"
        rate = _object(raw_rate, label=label)
        _reject_unknown(rate, allowed={"edge", "rate"}, label=label)
        raw_edge = _array(rate.get("edge"), label=f"{label}.edge")
        if len(raw_edge) != 2 or any(
            not isinstance(vertex, str) for vertex in raw_edge
        ):
            raise TypeError(f"{label}.edge must contain exactly two strings")
        edge = (raw_edge[0], raw_edge[1])
        if edge in rates:
            raise ValueError(f"{label}.edge duplicates an earlier directed edge")
        rates[edge] = rate.get("rate")

    graph_payload = {
        "schema_version": 1,
        "name": root.get("name"),
        "vertices": root.get("vertices"),
        "edges": root.get("edges"),
        "readouts": root.get("readouts", []),
        "analysis": {
            "max_layer": layer,
            "max_cycles": limits.max_cycles,
        },
    }
    graph = parse_model(graph_payload)
    return CriticalModel(
        graph=graph,
        rates=_normalize_rates(graph.edges, rates),
        layer=layer,
        theta=_exact_positive(critical.get("theta"), label="theta"),
        limits=limits,
        audit_paths=audit_paths,
    )


def load_critical_model(path: str | Path) -> CriticalModel:
    """Load a UTF-8 critical model while preserving JSON decimals exactly."""

    model_path = Path(path)
    try:
        payload = json.loads(
            model_path.read_text(encoding="utf-8"),
            parse_float=Decimal,
            parse_int=parse_json_integer,
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            f"invalid JSON critical model {model_path}: {error.msg}"
        ) from error
    return parse_critical_model(_object(payload, label="critical model"))


def _fraction_text(value: Fraction) -> str:
    return str(value)


def critical_model_to_dict(model: CriticalModel) -> dict[str, Any]:
    """Return the normalized, exact machine representation of a critical model."""

    return {
        "schema_version": CRITICAL_MODEL_SCHEMA_VERSION,
        "name": model.graph.name,
        "vertices": list(model.graph.vertices),
        "edges": [list(edge) for edge in model.graph.edges],
        "readouts": [
            {
                "name": readout.name,
                "coefficients": [
                    {"edge": list(edge), "coefficient": coefficient}
                    for edge, coefficient in readout.coefficients
                ],
            }
            for readout in model.graph.readouts
        ],
        "rates": [
            {"edge": list(edge), "rate": _fraction_text(rate)}
            for edge, rate in model.rates
        ],
        "critical": {
            "layer": model.layer,
            "theta": _fraction_text(model.theta),
            "limits": {
                "max_paths": model.limits.max_paths,
                "max_estimated_integer_digits": (
                    model.limits.max_estimated_integer_digits
                ),
                "max_integer_digits": model.limits.max_integer_digits,
                "max_output_records": model.limits.max_output_records,
                "max_cycles": model.limits.max_cycles,
            },
            "audit_paths": model.audit_paths,
        },
    }


def normalized_critical_model_sha256(model: CriticalModel) -> str:
    """Hash the normalized exact model, independent of input formatting."""

    canonical = json.dumps(
        critical_model_to_dict(model),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _directed_walk_count(
    graph: GraphModel, layer: int, *, max_paths: int
) -> int | None:
    """Count exactly, or stop once the requested path budget is exceeded."""
    if len(graph.vertices) <= 2:
        return 2 * len(graph.edges)
    mutable = {vertex: [] for vertex in graph.vertices}
    for left, right in graph.edges:
        mutable[left].append(right)
        mutable[right].append(left)
    adjacency = {vertex: tuple(neighbors) for vertex, neighbors in mutable.items()}
    counts = {vertex: 1 for vertex in graph.vertices}
    for step in range(layer):
        counts = {
            vertex: sum(counts[neighbor] for neighbor in adjacency[vertex])
            for vertex in graph.vertices
        }
        total = sum(counts.values())
        if total > max_paths and step + 1 < layer:
            # Every walk extends on a connected bidirectional support. The
            # final count exceeds the budget, but its exact value is uncomputed.
            return None
    try:
        check_integer_text(total, label="directed path count")
    except ValueError:
        return None
    return total


def _integer_digits(value: Fraction | int) -> int:
    fraction = Fraction(value)
    return max(
        decimal_digits(fraction.numerator),
        decimal_digits(fraction.denominator),
    )


def _estimated_integer_digits(model: CriticalModel) -> int | None:
    input_digits = max(
        [_integer_digits(model.theta)]
        + [_integer_digits(rate) for _, rate in model.rates]
    )
    vertex_factor = max(1, len(model.graph.vertices))
    subtotal = (
        input_digits * max(model.layer, vertex_factor)
        + decimal_digits(max(1, len(model.graph.edges)))
        + 4
    )
    try:
        check_integer_text(subtotal, label="preflight estimate")
    except ValueError:
        return None
    # This lower bound already suffices for refusal; do not expand m! first.
    if subtotal > model.limits.max_estimated_integer_digits:
        return subtotal
    return subtotal + decimal_digits(factorial(model.layer))


def _limit_result(
    model: CriticalModel,
    *,
    resource: str,
    limit: int,
    observed_or_estimated: int | None,
    measurement: str,
    complete_components: tuple[str, ...],
    incomplete_components: tuple[str, ...],
    path_count: int | None,
    output_records: int | None = None,
    maximum_integer_digits: int | None = None,
    homology_rank: int | None = None,
    natural_max_layer: int | None = None,
    natural_filtration_complete: bool | None = None,
) -> CriticalExperimentResult:
    return CriticalExperimentResult(
        model=model,
        status=CriticalStatus.LIMIT_REACHED,
        homology_rank=homology_rank,
        natural_max_layer=natural_max_layer,
        natural_filtration_complete=natural_filtration_complete,
        graded_group=None,
        visible_group=None,
        hidden_group=None,
        induced_readout=None,
        stationary_law=None,
        catalogue=None,
        common_levy_measure=None,
        critical_endpoint_components=None,
        resource_usage=CriticalResourceUsage(
            path_count=path_count,
            output_records=output_records,
            maximum_integer_digits=maximum_integer_digits,
        ),
        limit=CriticalLimit(
            resource=resource,
            limit=limit,
            observed_or_estimated=observed_or_estimated,
            measurement=measurement,
            complete_components=complete_components,
            incomplete_components=incomplete_components,
        ),
    )


def _mark(value: _InternalElement) -> CriticalMark:
    return CriticalMark(torsion=value.torsion, free=value.free)


def _group(value: QuotientInvariants) -> CriticalGroup:
    return CriticalGroup(
        free_rank=value.free_rank,
        torsion_factors=value.torsion_factors,
    )


def _induced_readout(catalogue: _InternalCatalogue) -> CriticalInducedReadout:
    source = catalogue.graded_group
    torsion_images = []
    for position in range(len(source.torsion_moduli)):
        coordinates = [0] * len(source.torsion_moduli)
        coordinates[position] = 1
        torsion_images.append(
            _mark(
                catalogue.induced_readout.apply(
                    _InternalElement(
                        torsion=tuple(coordinates),
                        free=(0,) * source.free_rank,
                    )
                )
            )
        )
    free_images = []
    for position in range(source.free_rank):
        coordinates = [0] * source.free_rank
        coordinates[position] = 1
        free_images.append(
            _mark(
                catalogue.induced_readout.apply(
                    _InternalElement(
                        torsion=(0,) * len(source.torsion_moduli),
                        free=tuple(coordinates),
                    )
                )
            )
        )
    return CriticalInducedReadout(
        torsion_generator_images=tuple(torsion_images),
        free_generator_images=tuple(free_images),
    )


def _public_catalogue(
    catalogue: _InternalCatalogue,
    *,
    audit_paths: bool,
) -> CriticalCatalogueResult:
    path_counts: dict[tuple[str, str, _InternalElement], int] = {}
    for term in catalogue.terms:
        key = (term.start, term.end, term.label)
        path_counts[key] = path_counts.get(key, 0) + 1
    weights = tuple(
        CriticalWeight(
            start=item.start,
            end=item.end,
            endpoint_distance=item.endpoint_distance,
            mechanism=(
                "common-endpoint"
                if item.endpoint_distance < catalogue.layer
                else "critical-endpoint"
            ),
            label=_mark(item.label),
            visible_label=_mark(item.visible_label),
            path_count=path_counts[(item.start, item.end, item.label)],
            leading_weight=item.leading_weight,
        )
        for item in catalogue.aggregate_weights()
    )
    paths = (
        tuple(
            CriticalAuditPath(
                walk=term.walk,
                endpoint_distance=term.endpoint_distance,
                label=_mark(term.label),
                visible_label=_mark(term.visible_label),
                rate_product=term.leading_weight * factorial(catalogue.layer),
                leading_weight=term.leading_weight,
            )
            for term in catalogue.terms
        )
        if audit_paths
        else None
    )
    return CriticalCatalogueResult(
        geodesics=tuple(
            CriticalGeodesic(
                start=reference.start,
                end=reference.end,
                walk=reference.walk,
            )
            for reference in catalogue.geodesics
        ),
        weights=weights,
        path_count=len(catalogue.terms),
        audit_paths=paths,
    )


def _public_stationary_law(
    experiment: _InternalExperiment,
) -> CriticalStationaryLaw:
    law = experiment.stationary_law
    return CriticalStationaryLaw(
        vertices=law.vertices,
        generator=tuple(
            tuple(
                Fraction(int(value.p), int(value.q)) for value in law.generator.row(i)
            )
            for i in range(law.generator.rows)
        ),
        probabilities=law.probabilities,
    )


def _public_endpoints(
    components: tuple[_CriticalEndpointComponent, ...],
) -> tuple[CriticalEndpointResult, ...]:
    return tuple(
        CriticalEndpointResult(
            start=component.start,
            end=component.end,
            poisson_intensity=component.poisson_intensity,
            mark_law=tuple(
                CriticalConditionalMark(
                    label=_mark(mark.label),
                    visible_label=_mark(mark.visible_label),
                    probability=mark.probability,
                )
                for mark in component.mark_law
            ),
        )
        for component in components
    )


def _exact_values(value: Any) -> Iterator[int | Fraction]:
    """Visit exact numbers within selected scientific components."""
    if isinstance(value, bool):
        return
    if isinstance(value, int | Fraction):
        yield value
    elif is_dataclass(value):
        for field in fields(value):
            yield from _exact_values(getattr(value, field.name))
        if isinstance(value, CriticalGroup):
            yield from _exact_values(value.finite_order)
    elif isinstance(value, tuple):
        for item in value:
            yield from _exact_values(item)


def _input_exact_values(model: CriticalModel) -> Iterator[int | Fraction]:
    yield from _exact_values(
        (
            model.layer,
            model.theta,
            model.rates,
            model.graph.readouts,
            len(model.graph.vertices),
        )
    )


def _scientific_exact_values(
    result: CriticalExperimentResult,
) -> Iterator[int | Fraction]:
    """Include integer marks, maps, counts and derived summary intensities.

    Resource-policy values and provenance are metadata, so they are not visited.
    """
    yield from _input_exact_values(result.model)
    yield from _exact_values(
        (
            result.homology_rank,
            result.natural_max_layer,
            result.graded_group,
            result.visible_group,
            result.hidden_group,
            result.induced_readout,
            result.stationary_law,
            result.catalogue,
            result.common_levy_measure,
            result.critical_endpoint_components,
        )
    )
    yield sum(
        (atom.intensity for atom in result.common_levy_measure or ()), Fraction(0)
    )
    yield sum(
        (item.poisson_intensity for item in result.critical_endpoint_components or ()),
        Fraction(0),
    )


def analyze_critical_model(model: CriticalModel) -> CriticalExperimentResult:
    """Construct the exact one-layer critical-limit experiment atomically."""

    if not isinstance(model, CriticalModel):
        raise TypeError("model must be a CriticalModel")
    input_digits = max(_integer_digits(value) for value in _input_exact_values(model))
    if input_digits > model.limits.max_integer_digits:
        return _limit_result(
            model,
            resource="integer_digits",
            limit=model.limits.max_integer_digits,
            observed_or_estimated=input_digits,
            measurement="exact",
            complete_components=("model-validation",),
            incomplete_components=("topology", "catalogue", "limit-experiment"),
            path_count=None,
            maximum_integer_digits=input_digits,
        )
    path_count = _directed_walk_count(
        model.graph, model.layer, max_paths=model.limits.max_paths
    )
    if path_count is None or path_count > model.limits.max_paths:
        return _limit_result(
            model,
            resource="directed_paths",
            limit=model.limits.max_paths,
            observed_or_estimated=path_count,
            measurement="unavailable" if path_count is None else "exact",
            complete_components=("model-validation", "path-count-preflight"),
            incomplete_components=("topology", "catalogue", "limit-experiment"),
            path_count=path_count,
        )

    estimated_digits = _estimated_integer_digits(model)
    if (
        estimated_digits is None
        or estimated_digits > model.limits.max_estimated_integer_digits
    ):
        return _limit_result(
            model,
            resource="estimated_integer_digits",
            limit=model.limits.max_estimated_integer_digits,
            observed_or_estimated=estimated_digits,
            measurement=(
                "unavailable" if estimated_digits is None else "preflight-estimate"
            ),
            complete_components=("model-validation", "resource-preflight"),
            incomplete_components=("topology", "catalogue", "limit-experiment"),
            path_count=path_count,
            output_records=None,
            maximum_integer_digits=None,
        )

    topology = _analyze_topology(model.graph)
    if topology.status is AnalysisStatus.LIMIT_REACHED:
        if topology.limit is None:
            raise AssertionError("a limited topology result must identify its resource")
        return _limit_result(
            model,
            resource=topology.limit.resource,
            limit=topology.limit.limit,
            observed_or_estimated=None,
            measurement="unavailable",
            complete_components=("model-validation", "homology"),
            incomplete_components=("topology", "catalogue", "limit-experiment"),
            path_count=path_count,
            output_records=None,
            maximum_integer_digits=None,
            homology_rank=topology.basis.rank,
            natural_max_layer=topology.natural_max_layer,
            natural_filtration_complete=False,
        )
    if topology.filtration is None:
        raise AssertionError("a completed critical horizon must have a filtration")

    internal = build_marked_poisson_experiment(
        topology.filtration,
        rates=model.rate_mapping(),
        layer=model.layer,
        theta=model.theta,
    )
    catalogue = _public_catalogue(internal.catalogue, audit_paths=model.audit_paths)
    stationary_law = _public_stationary_law(internal)
    common_levy = tuple(
        CriticalLevyAtom(
            label=_mark(atom.label),
            visible_label=_mark(atom.visible_label),
            intensity=atom.intensity,
        )
        for atom in internal.common_levy_measure
    )
    endpoints = _public_endpoints(internal.critical_endpoint_components)
    current_layer = topology.filtration.at(model.layer)
    if current_layer.hidden_graded is None:
        raise AssertionError("a nonzero layer must carry hidden quotient invariants")

    complete = CriticalExperimentResult(
        model=model,
        status=CriticalStatus.COMPLETE,
        homology_rank=topology.basis.rank,
        natural_max_layer=topology.natural_max_layer,
        natural_filtration_complete=topology.natural_filtration_complete,
        graded_group=_group(internal.catalogue.graded_group.invariants),
        visible_group=_group(internal.catalogue.visible_group.invariants),
        hidden_group=_group(current_layer.hidden_graded),
        induced_readout=_induced_readout(internal.catalogue),
        stationary_law=stationary_law,
        catalogue=catalogue,
        common_levy_measure=common_levy,
        critical_endpoint_components=endpoints,
        resource_usage=CriticalResourceUsage(
            path_count=path_count,
            output_records=(
                len(catalogue.geodesics)
                + len(catalogue.weights)
                + (len(catalogue.audit_paths) if catalogue.audit_paths else 0)
                + len(common_levy)
                + len(endpoints)
                + sum(len(component.mark_law) for component in endpoints)
            ),
            maximum_integer_digits=None,
        ),
        limit=None,
    )
    maximum_digits = max(
        _integer_digits(value) for value in _scientific_exact_values(complete)
    )
    if maximum_digits > model.limits.max_integer_digits:
        return _limit_result(
            model,
            resource="integer_digits",
            limit=model.limits.max_integer_digits,
            observed_or_estimated=maximum_digits,
            measurement="exact",
            complete_components=("model-validation", "topology"),
            incomplete_components=("catalogue", "limit-experiment"),
            path_count=path_count,
            output_records=complete.resource_usage.output_records,
            maximum_integer_digits=maximum_digits,
            homology_rank=topology.basis.rank,
            natural_max_layer=topology.natural_max_layer,
            natural_filtration_complete=topology.natural_filtration_complete,
        )
    if complete.resource_usage.output_records > model.limits.max_output_records:
        return _limit_result(
            model,
            resource="output_records",
            limit=model.limits.max_output_records,
            observed_or_estimated=complete.resource_usage.output_records,
            measurement="exact",
            complete_components=("model-validation", "topology"),
            incomplete_components=("catalogue", "limit-experiment"),
            path_count=path_count,
            output_records=complete.resource_usage.output_records,
            maximum_integer_digits=maximum_digits,
            homology_rank=topology.basis.rank,
            natural_max_layer=topology.natural_max_layer,
            natural_filtration_complete=topology.natural_filtration_complete,
        )
    return replace(
        complete,
        resource_usage=CriticalResourceUsage(
            path_count=path_count,
            output_records=complete.resource_usage.output_records,
            maximum_integer_digits=maximum_digits,
        ),
    )


def _mark_dict(mark: CriticalMark) -> dict[str, Any]:
    return {"torsion": list(mark.torsion), "free": list(mark.free)}


def _group_dict(group: CriticalGroup) -> dict[str, Any]:
    return {
        "free_rank": group.free_rank,
        "torsion_factors": list(group.torsion_factors),
        "finite_order": group.finite_order,
        "coordinate_convention": "constructive-smith-normal-form",
        "representation_dependent_coordinates": True,
        "evidence_category": "EXACT_INTEGER",
    }


def _matrix_dict(matrix: tuple[tuple[Fraction, ...], ...]) -> dict[str, Any]:
    rows = len(matrix)
    columns = len(matrix[0]) if rows else 0
    return {
        "rows": rows,
        "columns": columns,
        "data": [[_fraction_text(value) for value in row] for row in matrix],
    }


def critical_experiment_to_dict(result: CriticalExperimentResult) -> dict[str, Any]:
    """Serialize one result into the versioned critical-experiment contract."""

    if not isinstance(result, CriticalExperimentResult):
        raise TypeError("result must be a CriticalExperimentResult")
    model = result.model
    complete = result.status is CriticalStatus.COMPLETE
    if complete and any(
        value is None
        for value in (
            result.graded_group,
            result.visible_group,
            result.hidden_group,
            result.induced_readout,
            result.stationary_law,
            result.catalogue,
            result.common_levy_measure,
            result.critical_endpoint_components,
        )
    ):
        raise AssertionError("a complete result must carry every experiment component")
    if not complete and any(
        value is not None
        for value in (
            result.graded_group,
            result.visible_group,
            result.hidden_group,
            result.induced_readout,
            result.stationary_law,
            result.catalogue,
            result.common_levy_measure,
            result.critical_endpoint_components,
        )
    ):
        raise AssertionError("a limited result must not expose a partial experiment")

    groups = None
    stationary = None
    catalogue_document = None
    experiment_document = None
    critical_catalogue_empty = None
    common_total = None
    critical_total = None
    if complete:
        graded = result.graded_group
        visible = result.visible_group
        hidden = result.hidden_group
        induced = result.induced_readout
        law = result.stationary_law
        catalogue = result.catalogue
        levy = result.common_levy_measure
        endpoints = result.critical_endpoint_components
        assert graded is not None
        assert visible is not None
        assert hidden is not None
        assert induced is not None
        assert law is not None
        assert catalogue is not None
        assert levy is not None
        assert endpoints is not None
        groups = {
            "graded": _group_dict(graded),
            "visible": _group_dict(visible),
            "hidden_kernel": _group_dict(hidden),
            "induced_readout": {
                "source_torsion_generator_images": [
                    _mark_dict(mark) for mark in induced.torsion_generator_images
                ],
                "source_free_generator_images": [
                    _mark_dict(mark) for mark in induced.free_generator_images
                ],
                "kernel_identification": "K_m/K_(m-1)",
                "evidence_category": "EXACT_INTEGER",
            },
        }
        stationary = {
            "vertices": list(law.vertices),
            "generator": _matrix_dict(law.generator),
            "probabilities": [_fraction_text(value) for value in law.probabilities],
            "evidence_category": "EXACT_RATIONAL",
        }
        catalogue_document = {
            "aggregation": "ordered-endpoint-and-graded-mark",
            "geodesic_convention": (
                "lexicographically-first shortest path under normalized vertex order"
            ),
            "geodesics": [
                {
                    "start": reference.start,
                    "end": reference.end,
                    "walk": list(reference.walk),
                    "representation_dependent": True,
                }
                for reference in catalogue.geodesics
            ],
            "weights": [
                {
                    "start": weight.start,
                    "end": weight.end,
                    "endpoint_distance": weight.endpoint_distance,
                    "mechanism": weight.mechanism,
                    "label": _mark_dict(weight.label),
                    "visible_label": _mark_dict(weight.visible_label),
                    "path_count": weight.path_count,
                    "leading_weight": _fraction_text(weight.leading_weight),
                }
                for weight in catalogue.weights
            ],
            "audit_paths": (
                [
                    {
                        "walk": list(path.walk),
                        "endpoint_distance": path.endpoint_distance,
                        "label": _mark_dict(path.label),
                        "visible_label": _mark_dict(path.visible_label),
                        "rate_product": _fraction_text(path.rate_product),
                        "leading_weight": _fraction_text(path.leading_weight),
                    }
                    for path in catalogue.audit_paths
                ]
                if catalogue.audit_paths is not None
                else None
            ),
            "evidence_categories": ["EXACT_COMBINATORIAL", "EXACT_RATIONAL"],
        }
        common_total_fraction = sum(
            (atom.intensity for atom in levy), start=Fraction(0)
        )
        critical_total_fraction = sum(
            (component.poisson_intensity for component in endpoints),
            start=Fraction(0),
        )
        common_total = _fraction_text(common_total_fraction)
        critical_total = _fraction_text(critical_total_fraction)
        experiment_document = {
            "interpretation": "theorem-derived critical-limit generative specification",
            "scaling": "T * delta^(m-1) -> theta",
            "common_endpoint_component": {
                "distribution": "compound-poisson",
                "levy_measure": [
                    {
                        "label": _mark_dict(atom.label),
                        "visible_label": _mark_dict(atom.visible_label),
                        "intensity": _fraction_text(atom.intensity),
                    }
                    for atom in levy
                ],
                "total_intensity": common_total,
                "zero_marks_excluded": True,
            },
            "critical_endpoint_components": [
                {
                    "start": component.start,
                    "end": component.end,
                    "count_distribution": "poisson",
                    "poisson_intensity": _fraction_text(component.poisson_intensity),
                    "conditional_mark_law": [
                        {
                            "label": _mark_dict(mark.label),
                            "visible_label": _mark_dict(mark.visible_label),
                            "probability": _fraction_text(mark.probability),
                        }
                        for mark in component.mark_law
                    ],
                    "zero_marks_retained": True,
                }
                for component in endpoints
            ],
            "components_mutually_independent": True,
            "observable_rule": "apply the induced graded readout to the total mark",
            "posterior_kernel_rule": (
                "restrict the total-mark law to the observed visible residue "
                "and renormalize"
            ),
            "infinite_support_probability_table_expanded": False,
            "evidence_category": "ASYMPTOTIC_THEOREM",
            "boundary_note": (
                "This is a critical-limit generative specification, not an exact "
                "finite-(T, delta) posterior or an unconditional critical MAP solver."
            ),
        }
        zero = CriticalMark(
            torsion=(0,) * len(graded.torsion_factors),
            free=(0,) * graded.free_rank,
        )
        critical_catalogue_empty = all(
            weight.label == zero for weight in catalogue.weights
        )

    return {
        "schema_name": CRITICAL_EXPERIMENT_SCHEMA_NAME,
        "schema_version": CRITICAL_EXPERIMENT_SCHEMA_VERSION,
        "software": {
            "name": "homological-observability",
            "version": __version__,
        },
        "artifact_role": CRITICAL_ARTIFACT_ROLE,
        "status": result.status.value,
        "evidence_categories": (
            [
                "EXACT_INTEGER",
                "EXACT_COMBINATORIAL",
                "EXACT_RATIONAL",
                "ASYMPTOTIC_THEOREM",
            ]
            if complete
            else []
        ),
        "normalized_model_sha256": normalized_critical_model_sha256(model),
        "model": critical_model_to_dict(model),
        "summary": {
            "layer": model.layer,
            "theta": _fraction_text(model.theta),
            "vertex_count": len(model.graph.vertices),
            "edge_count": len(model.graph.edges),
            "homology_rank": result.homology_rank,
            "natural_max_layer": result.natural_max_layer,
            "natural_filtration_complete": result.natural_filtration_complete,
            "path_count": result.resource_usage.path_count,
            "aggregated_weight_count": (
                len(result.catalogue.weights) if result.catalogue is not None else None
            ),
            "critical_catalogue_empty": critical_catalogue_empty,
            "common_total_intensity": common_total,
            "critical_total_intensity": critical_total,
            "audit_paths_included": model.audit_paths if complete else False,
        },
        "topology": {
            "baseline_schema_name": "homological-observability.analysis",
            "baseline_schema_version": 2,
            "requested_layer_complete": complete,
            "natural_filtration_complete": result.natural_filtration_complete,
        },
        "groups": groups,
        "stationary_law": stationary,
        "catalogue": catalogue_document,
        "limit_experiment": experiment_document,
        "resources": {
            "limits": {
                "max_paths": model.limits.max_paths,
                "max_estimated_integer_digits": (
                    model.limits.max_estimated_integer_digits
                ),
                "max_integer_digits": model.limits.max_integer_digits,
                "max_output_records": model.limits.max_output_records,
                "max_cycles": model.limits.max_cycles,
            },
            "usage": {
                "path_count": result.resource_usage.path_count,
                "output_records": result.resource_usage.output_records,
                "maximum_integer_digits": (
                    result.resource_usage.maximum_integer_digits
                ),
            },
        },
        "limit": (
            {
                "resource": result.limit.resource,
                "limit": result.limit.limit,
                "observed_or_estimated": result.limit.observed_or_estimated,
                "measurement": result.limit.measurement,
                "complete_components": list(result.limit.complete_components),
                "incomplete_components": list(result.limit.incomplete_components),
            }
            if result.limit is not None
            else None
        ),
    }


def render_critical_json(result: CriticalExperimentResult) -> str:
    """Render stable UTF-8 JSON with a trailing newline."""

    return (
        json.dumps(
            critical_experiment_to_dict(result),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def render_critical_text(result: CriticalExperimentResult) -> str:
    """Render a compact terminal view from the structured result contract."""

    document = critical_experiment_to_dict(result)
    summary = document["summary"]
    lines = [
        f"Critical homological observability: {result.model.graph.name}",
        f"status: {document['status']}",
        f"artifact role: {document['artifact_role']}",
        f"layer: {summary['layer']}",
        f"theta: {summary['theta']}",
        f"directed paths: {summary['path_count']}",
    ]
    if document["status"] == CriticalStatus.LIMIT_REACHED.value:
        limit = document["limit"]
        lines.extend(
            [
                f"resource limit: {limit['resource']}={limit['limit']}",
                "observed or estimated: "
                f"{limit['observed_or_estimated']} ({limit['measurement']})",
                "No partial catalogue or limit experiment was returned.",
            ]
        )
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            f"homology rank: {summary['homology_rank']}",
            f"aggregated weights: {summary['aggregated_weight_count']}",
            f"critical catalogue empty: {str(summary['critical_catalogue_empty']).lower()}",
            f"common compound-Poisson intensity: {summary['common_total_intensity']}",
            f"critical endpoint intensity: {summary['critical_total_intensity']}",
            "",
            "Evidence: exact integer quotient coordinates, finite path enumeration, "
            "and exact rational weights.",
            "Boundary: the marked-Poisson object is a theorem-derived critical-limit "
            "specification, not a finite-sample posterior.",
        ]
    )
    return "\n".join(lines) + "\n"
