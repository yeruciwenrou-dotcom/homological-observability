"""Deterministic integral coordinates for graph first homology."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import networkx as nx
from sympy import ImmutableMatrix, Matrix
from sympy.matrices.matrixbase import MatrixBase

from .model import Edge, GraphModel, IntegerReadout, canonical_edge

Cycle = tuple[str, ...]


@dataclass(frozen=True)
class HomologyBasis:
    """Auditable fundamental-cycle coordinates for ``H_1(G; Z)``."""

    vertices: tuple[str, ...]
    edges: tuple[Edge, ...]
    tree_edges: tuple[Edge, ...]
    chord_edges: tuple[Edge, ...]
    fundamental_cycles: ImmutableMatrix

    @property
    def rank(self) -> int:
        return len(self.chord_edges)


def _spanning_tree(
    vertices: Sequence[str], edges: Sequence[Edge], *, reverse: bool
) -> tuple[Edge, ...]:
    parent = {vertex: vertex for vertex in vertices}

    def find(vertex: str) -> str:
        while parent[vertex] != vertex:
            parent[vertex] = parent[parent[vertex]]
            vertex = parent[vertex]
        return vertex

    tree: list[Edge] = []
    for u, v in sorted(edges, reverse=reverse):
        root_u = find(u)
        root_v = find(v)
        if root_u == root_v:
            continue
        parent[root_v] = root_u
        tree.append((u, v))
    if len(tree) != len(vertices) - 1:
        raise ValueError("failed to construct a spanning tree")
    return tuple(sorted(tree))


def _oriented_edge_sign(u: str, v: str) -> tuple[Edge, int]:
    edge = canonical_edge(u, v)
    return edge, 1 if (u, v) == edge else -1


def build_homology_basis(
    model: GraphModel, *, reverse_tree_order: bool = False
) -> HomologyBasis:
    """Build a fundamental-cycle basis with a chord identity block."""

    tree_edges = _spanning_tree(
        model.vertices,
        model.edges,
        reverse=reverse_tree_order,
    )
    tree_set = set(tree_edges)
    chord_edges = tuple(edge for edge in model.edges if edge not in tree_set)

    tree = nx.Graph()
    tree.add_nodes_from(model.vertices)
    tree.add_edges_from(tree_edges)
    edge_index = {edge: index for index, edge in enumerate(model.edges)}
    fundamental = Matrix.zeros(len(model.edges), len(chord_edges))

    for column, (u, v) in enumerate(chord_edges):
        fundamental[edge_index[(u, v)], column] = 1
        path = nx.shortest_path(tree, source=v, target=u)
        for tail, head in zip(path, path[1:]):
            edge, sign = _oriented_edge_sign(tail, head)
            fundamental[edge_index[edge], column] += sign

    incidence = Matrix.zeros(len(model.vertices), len(model.edges))
    vertex_index = {vertex: index for index, vertex in enumerate(model.vertices)}
    for column, (u, v) in enumerate(model.edges):
        incidence[vertex_index[u], column] = -1
        incidence[vertex_index[v], column] = 1
    if incidence * fundamental != Matrix.zeros(len(model.vertices), len(chord_edges)):
        raise AssertionError("fundamental cycles must be integer 1-cycles")
    for column, chord in enumerate(chord_edges):
        row = edge_index[chord]
        expected = [1 if index == column else 0 for index in range(len(chord_edges))]
        if list(fundamental[row, :]) != expected:
            raise AssertionError("the chord block must be the identity")

    return HomologyBasis(
        vertices=model.vertices,
        edges=model.edges,
        tree_edges=tree_edges,
        chord_edges=chord_edges,
        fundamental_cycles=ImmutableMatrix(fundamental),
    )


def canonical_cycle(nodes: Sequence[str]) -> Cycle:
    """Choose one orientation and cyclic rotation for a simple cycle."""

    cycle = tuple(nodes)
    if len(cycle) < 3 or len(set(cycle)) != len(cycle):
        raise ValueError("a simple cycle must contain at least three distinct vertices")
    reverse = tuple(reversed(cycle))
    representatives = [
        sequence[offset:] + sequence[:offset]
        for sequence in (cycle, reverse)
        for offset in range(len(cycle))
    ]
    return min(representatives)


def chain_from_walk(walk: Sequence[str], basis: HomologyBasis) -> ImmutableMatrix:
    """Return the signed edge chain of a graph walk."""

    edge_index = {edge: index for index, edge in enumerate(basis.edges)}
    chain = Matrix.zeros(len(basis.edges), 1)
    for tail, head in zip(walk, walk[1:]):
        edge, sign = _oriented_edge_sign(tail, head)
        if edge not in edge_index:
            raise ValueError(f"{tail!r}--{head!r} is not an edge")
        chain[edge_index[edge], 0] += sign
    return ImmutableMatrix(chain)


def cycle_coordinates(cycle: Sequence[str], basis: HomologyBasis) -> ImmutableMatrix:
    """Express a simple cycle in the fundamental-cycle basis."""

    representative = canonical_cycle(cycle)
    chain = chain_from_walk(representative + representative[:1], basis)
    edge_index = {edge: index for index, edge in enumerate(basis.edges)}
    coordinates = Matrix([chain[edge_index[chord], 0] for chord in basis.chord_edges])
    if Matrix(basis.fundamental_cycles) * coordinates != chain:
        raise AssertionError("simple-cycle coordinates did not reconstruct the chain")
    return ImmutableMatrix(coordinates)


def readout_matrix(
    basis: HomologyBasis, readouts: Sequence[IntegerReadout]
) -> ImmutableMatrix:
    """Restrict integer edge cochains to fundamental-cycle coordinates."""

    rows: list[list[int]] = []
    for readout in readouts:
        coefficients = readout.as_mapping()
        edge_row = Matrix([[coefficients.get(edge, 0) for edge in basis.edges]])
        cycle_row = edge_row * Matrix(basis.fundamental_cycles)
        rows.append([int(entry) for entry in cycle_row])
    return ImmutableMatrix(rows) if rows else ImmutableMatrix.zeros(0, basis.rank)


def coordinates_from_cycle_chain(
    chain: MatrixBase, basis: HomologyBasis
) -> ImmutableMatrix:
    """Recover homology coordinates of a verified integer cycle chain."""

    if chain.shape != (len(basis.edges), 1):
        raise ValueError("cycle chain has the wrong edge dimension")
    edge_index = {edge: index for index, edge in enumerate(basis.edges)}
    coordinates = (
        Matrix([chain[edge_index[chord], 0] for chord in basis.chord_edges])
        if basis.rank
        else Matrix.zeros(0, 1)
    )
    if Matrix(basis.fundamental_cycles) * coordinates != chain:
        raise ValueError("the supplied chain is not an integer cycle")
    return ImmutableMatrix(coordinates)
