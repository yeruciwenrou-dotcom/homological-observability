"""Exhaustive small-graph validation for the production filtration modules."""

from __future__ import annotations

import sys
from math import ceil
from pathlib import Path
from time import perf_counter

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from homological_observability.analysis import analyze_model  # noqa: E402
from homological_observability.filtration import (  # noqa: E402
    analysis_signature,
    path_pair_oracle,
)
from homological_observability.model import GraphModel  # noqa: E402


def _string_graph(
    graph: nx.Graph,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    width = max(1, len(str(max(graph.nodes, default=0))))
    labels = {node: f"v{node:0{width}d}" for node in graph.nodes}
    vertices = tuple(labels[node] for node in graph.nodes)
    edges = tuple((labels[u], labels[v]) for u, v in graph.edges)
    return vertices, edges


def main() -> None:
    started = perf_counter()
    graph_count = 0
    oracle_checks = 0
    invariance_checks = 0
    readout_checks = 0

    for graph in nx.graph_atlas_g():
        vertex_count = graph.number_of_nodes()
        if not 1 <= vertex_count <= 7 or not nx.is_connected(graph):
            continue
        vertices, edges = _string_graph(graph)
        max_layer = ceil(vertex_count / 2)
        model = GraphModel.create(
            name=f"atlas-{graph_count}",
            vertices=vertices,
            edges=edges,
            max_layer=max_layer,
        )
        graph_count += 1

        first = analyze_model(model)
        second = analyze_model(model, reverse_tree_order=True)
        if not (
            first.is_complete
            and first.requested_horizon_complete
            and first.natural_filtration_complete
        ):
            raise AssertionError(("natural-horizon completeness", vertices, edges))
        if analysis_signature(first.filtration) != analysis_signature(
            second.filtration
        ):
            raise AssertionError(("tree-orientation invariance", vertices, edges))
        invariance_checks += 1

        terminal = first.filtration.at(max_layer).exposure
        if terminal.cols != first.basis.rank:
            raise AssertionError(("filtration stability", vertices, edges))
        if first.basis.rank and terminal.det() not in (-1, 1):
            raise AssertionError(("terminal lattice is not full", vertices, edges))

        if vertex_count <= 6:
            for layer in range(2, min(3, max_layer) + 1):
                if (
                    path_pair_oracle(first.basis, max_length=layer)
                    != first.filtration.at(layer).exposure
                ):
                    raise AssertionError(("path-pair oracle", layer, vertices, edges))
                oracle_checks += 1

        if first.basis.rank and vertex_count <= 6:
            cochain = {edge: (index % 5) - 2 for index, edge in enumerate(model.edges)}
            readout_model = GraphModel.create(
                name=model.name + "-readout",
                vertices=model.vertices,
                edges=model.edges,
                readouts=(("pi", cochain),),
                max_layer=max_layer,
            )
            first_readout = analyze_model(readout_model)
            second_readout = analyze_model(
                readout_model,
                reverse_tree_order=True,
            )
            if analysis_signature(first_readout.filtration) != analysis_signature(
                second_readout.filtration
            ):
                raise AssertionError(("readout invariance", vertices, edges))
            readout_checks += 1

    elapsed = perf_counter() - started
    print("PASS: connected NetworkX graph atlas validation")
    print(f"graphs: {graph_count}")
    print(f"tree/orientation/stability checks: {invariance_checks}")
    print(f"independent path-pair layer checks: {oracle_checks}")
    print(f"integer-readout invariance checks: {readout_checks}")
    print(f"elapsed_seconds: {elapsed:.3f}")


if __name__ == "__main__":
    main()
