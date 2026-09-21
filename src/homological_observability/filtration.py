"""Exact exposure, visible-image, and hidden homology filtrations."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

import networkx as nx
from sympy import ImmutableMatrix

from .homology import (
    Cycle,
    HomologyBasis,
    canonical_cycle,
    chain_from_walk,
    coordinates_from_cycle_chain,
    cycle_coordinates,
)
from .integer_lattice import (
    QuotientInvariants,
    column_lattice,
    hidden_lattice,
    image_lattice,
    lattice_signature,
    quotient_invariants,
    zero_lattice,
)


class CycleLimitExceeded(RuntimeError):
    """Raised instead of returning a silently truncated exposure filtration."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"more than {limit} simple cycles were encountered")
        self.limit = limit


class PathLimitExceeded(RuntimeError):
    """Raised when the independent path-pair oracle exceeds its test budget."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"more than {limit} graph walks were encountered")
        self.limit = limit


@dataclass(frozen=True)
class FiltrationLayer:
    """All exact lattice data at one path-length layer."""

    layer: int
    exposure: ImmutableMatrix
    visible: ImmutableMatrix
    hidden: ImmutableMatrix
    exposure_graded: QuotientInvariants | None
    visible_graded: QuotientInvariants | None
    hidden_graded: QuotientInvariants | None


@dataclass(frozen=True)
class FiltrationAnalysis:
    """Immutable exact result of the topology-only filtration kernel."""

    basis: HomologyBasis
    readout: ImmutableMatrix
    cycles: tuple[Cycle, ...]
    layers: tuple[FiltrationLayer, ...]

    @property
    def max_layer(self) -> int:
        return len(self.layers) - 1

    def at(self, layer: int) -> FiltrationLayer:
        if isinstance(layer, bool) or not isinstance(layer, int):
            raise TypeError("layer must be an integer")
        if layer < 0 or layer > self.max_layer:
            raise IndexError("layer is outside the computed filtration")
        return self.layers[layer]


def enumerate_simple_cycles(
    basis: HomologyBasis,
    *,
    max_length: int,
    max_cycles: int | None = None,
) -> tuple[Cycle, ...]:
    """Enumerate canonical undirected simple cycles within a length bound."""

    if isinstance(max_length, bool) or not isinstance(max_length, int):
        raise TypeError("max_length must be an integer")
    if max_length < 1:
        raise ValueError("max_length must be positive")
    if max_cycles is not None and (
        isinstance(max_cycles, bool)
        or not isinstance(max_cycles, int)
        or max_cycles < 1
    ):
        raise ValueError("max_cycles must be a positive integer")

    graph = nx.Graph()
    graph.add_nodes_from(basis.vertices)
    graph.add_edges_from(basis.edges)
    cycles: set[Cycle] = set()
    for raw_cycle in nx.simple_cycles(graph, length_bound=max_length):
        if len(raw_cycle) < 3:
            continue
        cycles.add(canonical_cycle(raw_cycle))
        if max_cycles is not None and len(cycles) > max_cycles:
            raise CycleLimitExceeded(max_cycles)
    return tuple(sorted(cycles, key=lambda cycle: (len(cycle), cycle)))


def exposure_filtration(
    basis: HomologyBasis,
    *,
    max_layer: int | None = None,
    max_cycles: int | None = None,
) -> tuple[tuple[Cycle, ...], tuple[ImmutableMatrix, ...]]:
    """Construct the exact integer exposure filtration ``L_m``."""

    if max_layer is None:
        max_layer = ceil(len(basis.vertices) / 2)
    if isinstance(max_layer, bool) or not isinstance(max_layer, int):
        raise TypeError("max_layer must be an integer")
    if max_layer < 1:
        raise ValueError("max_layer must be positive")

    cycles = enumerate_simple_cycles(
        basis,
        max_length=2 * max_layer,
        max_cycles=max_cycles,
    )
    coordinates = {cycle: cycle_coordinates(cycle, basis) for cycle in cycles}
    lattices = [zero_lattice(basis.rank) for _ in range(max_layer + 1)]
    for layer in range(2, max_layer + 1):
        lattices[layer] = column_lattice(
            [coordinates[cycle] for cycle in cycles if len(cycle) <= 2 * layer],
            basis.rank,
        )
    return cycles, tuple(lattices)


def analyze_filtration(
    basis: HomologyBasis,
    *,
    readout: ImmutableMatrix | None = None,
    max_layer: int | None = None,
    max_cycles: int | None = None,
) -> FiltrationAnalysis:
    """Compute ``L_m``, ``pi(L_m)``, ``L_m intersect ker(pi)``, and quotients."""

    if readout is None:
        readout = ImmutableMatrix.zeros(0, basis.rank)
    else:
        readout = ImmutableMatrix(readout)
    if readout.cols != basis.rank:
        raise ValueError("readout and homology basis have different dimensions")
    if any(not entry.is_Integer for entry in readout):
        raise TypeError("readout matrices must be integral")

    cycles, exposure = exposure_filtration(
        basis,
        max_layer=max_layer,
        max_cycles=max_cycles,
    )
    hidden = tuple(
        hidden_lattice(lattice, readout) if readout.rows else lattice
        for lattice in exposure
    )
    visible = tuple(image_lattice(lattice, readout) for lattice in exposure)

    layers: list[FiltrationLayer] = []
    for layer in range(len(exposure)):
        if layer < 2:
            exposure_graded = None
            hidden_graded = None
            visible_graded = None
        else:
            exposure_graded = quotient_invariants(exposure[layer - 1], exposure[layer])
            hidden_graded = quotient_invariants(hidden[layer - 1], hidden[layer])
            visible_graded = quotient_invariants(visible[layer - 1], visible[layer])
            if exposure_graded.free_rank != (
                hidden_graded.free_rank + visible_graded.free_rank
            ):
                raise AssertionError(
                    "graded free ranks violate exact-sequence additivity"
                )
        layers.append(
            FiltrationLayer(
                layer=layer,
                exposure=exposure[layer],
                visible=visible[layer],
                hidden=hidden[layer],
                exposure_graded=exposure_graded,
                visible_graded=visible_graded,
                hidden_graded=hidden_graded,
            )
        )
    return FiltrationAnalysis(
        basis=basis,
        readout=readout,
        cycles=cycles,
        layers=tuple(layers),
    )


def _walks_from(
    graph: nx.Graph, start: str, max_length: int
) -> Iterable[tuple[str, ...]]:
    stack = [(start, (start,), 0)]
    while stack:
        current, walk, length = stack.pop()
        yield walk
        if length == max_length:
            continue
        for neighbor in sorted(graph.neighbors(current), reverse=True):
            stack.append((neighbor, walk + (neighbor,), length + 1))


def path_pair_oracle(
    basis: HomologyBasis,
    *,
    max_length: int,
    max_paths: int | None = None,
) -> ImmutableMatrix:
    """Brute-force the path-pair definition without simple-cycle enumeration."""

    if isinstance(max_length, bool) or not isinstance(max_length, int):
        raise TypeError("max_length must be an integer")
    if max_length < 0:
        raise ValueError("max_length must be nonnegative")
    if max_paths is not None and (
        isinstance(max_paths, bool) or not isinstance(max_paths, int) or max_paths < 1
    ):
        raise ValueError("max_paths must be a positive integer")

    graph = nx.Graph()
    graph.add_nodes_from(basis.vertices)
    graph.add_edges_from(basis.edges)
    paths: dict[tuple[str, str], list[ImmutableMatrix]] = {}
    path_count = 0
    for start in basis.vertices:
        for walk in _walks_from(graph, start, max_length):
            path_count += 1
            if max_paths is not None and path_count > max_paths:
                raise PathLimitExceeded(max_paths)
            paths.setdefault((start, walk[-1]), []).append(chain_from_walk(walk, basis))

    generators: list[ImmutableMatrix] = []
    for chains in paths.values():
        reference = chains[0]
        for chain in chains[1:]:
            difference = chain - reference
            generators.append(coordinates_from_cycle_chain(difference, basis))
    return column_lattice(generators, basis.rank)


def analysis_signature(analysis: FiltrationAnalysis) -> tuple[object, ...]:
    """Return only basis-independent public invariants for regression checks."""

    signature: list[object] = [analysis.basis.rank]
    for layer in analysis.layers[2:]:
        signature.append(
            (
                layer.layer,
                lattice_signature(layer.exposure, analysis.basis.rank),
                lattice_signature(layer.hidden, analysis.basis.rank),
                lattice_signature(layer.visible, analysis.readout.rows),
                layer.exposure_graded,
                layer.hidden_graded,
                layer.visible_graded,
            )
        )
    return tuple(signature)
