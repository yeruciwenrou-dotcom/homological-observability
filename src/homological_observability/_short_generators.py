"""Integral generators of the cycle-length filtration from all rooted BFS trees."""

import networkx as nx
from sympy import ImmutableMatrix, Matrix, eye
from sympy.matrices.normalforms import hermite_normal_form

from .homology import canonical_cycle
from .integer_lattice import zero_lattice


class GeneratorLimitExceeded(RuntimeError):
    def __init__(self, limit):
        super().__init__(f"more than {limit} distinct short-cycle generators")
        self.limit = limit


def generator_exposure(basis, horizon, max_generators):
    """Generate every requested layer over Z with one shortest-path tree per root.

    On any simple cycle of length L, root the BFS at a vertex of the cycle.
    The sum of the rooted fundamental circulations along its oriented edges
    telescopes to the cycle over Z. Each circulation reduces to a simple cycle
    of length at most L, by the two distances along the original cycle. Thus
    truncating by length generates the entire short-cycle lattice in each layer.
    """
    graph = nx.Graph()
    graph.add_nodes_from(basis.vertices)
    graph.add_edges_from(basis.edges)
    seen = set()
    if horizon >= 2 and basis.rank:
        for root in basis.vertices:
            paths = nx.single_source_shortest_path(graph, root, cutoff=horizon)
            for u, pu in paths.items():
                for v in graph[u]:
                    if u >= v or v not in paths:
                        continue
                    pv = paths[v]
                    # Delete the shared root prefix and either orientation of
                    # a tree edge, then close the two paths with u--v.
                    m = 0
                    while m < min(len(pu), len(pv)) and pu[m] == pv[m]:
                        m += 1
                    length = len(pu) + len(pv) - 2 * m + 1
                    if 3 <= length <= 2 * horizon:
                        cycle = canonical_cycle(pu[m - 1 :] + pv[m:][::-1])
                        seen.add(cycle)
                        if max_generators is not None and len(seen) > max_generators:
                            raise GeneratorLimitExceeded(max_generators)
    generators = tuple(sorted(seen, key=lambda c: (len(c), c)))
    by_layer = {}
    for cycle in generators:
        by_layer.setdefault((len(cycle) + 1) // 2, []).append(cycle)
    chords = {edge: i for i, edge in enumerate(basis.chord_edges)}
    lattice = zero_lattice(basis.rank)
    full = ImmutableMatrix(eye(basis.rank))
    exposure = [lattice, lattice]
    for layer in range(2, horizon + 1):
        if lattice != full and layer in by_layer:
            cols = []
            for cycle in by_layer[layer]:
                column = [0] * basis.rank
                for u, v in zip(cycle, cycle[1:] + cycle[:1]):
                    e = (u, v) if u < v else (v, u)
                    if e in chords:
                        column[chords[e]] = 1 if u < v else -1
                cols.append(Matrix(column))
            lattice = ImmutableMatrix(
                hermite_normal_form(Matrix.hstack(Matrix(lattice), *cols))
            )
        exposure.append(lattice)
    return generators, tuple(exposure)
