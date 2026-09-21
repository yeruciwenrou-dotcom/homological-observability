"""Definition, mechanism, and invariance tests for integer filtrations."""

from __future__ import annotations

import unittest
from itertools import combinations, permutations

from sympy import ImmutableMatrix, Matrix, eye

from homological_observability.analysis import AnalysisStatus, analyze_model
from homological_observability.filtration import (
    PathLimitExceeded,
    analysis_signature,
    path_pair_oracle,
)
from homological_observability.homology import (
    build_homology_basis,
    cycle_coordinates,
)
from homological_observability.integer_lattice import (
    QuotientInvariants,
    lattice_signature,
)
from homological_observability.model import GraphModel, canonical_edge


def cycle_graph(size: int, *, max_layer: int | None = None) -> GraphModel:
    vertices = tuple(f"v{index}" for index in range(size))
    edges = tuple(
        (vertices[index], vertices[(index + 1) % size]) for index in range(size)
    )
    return GraphModel.create(
        name=f"c{size}",
        vertices=vertices,
        edges=edges,
        max_layer=max_layer,
    )


def wedge_c3_c5() -> tuple[GraphModel, tuple[str, ...], tuple[str, ...]]:
    triangle = ("o", "a1", "a2")
    pentagon = ("o", "b1", "b2", "b3", "b4")
    vertices = tuple(sorted(set(triangle + pentagon)))
    edges = tuple(
        (u, v)
        for cycle in (triangle, pentagon)
        for u, v in zip(cycle, cycle[1:] + cycle[:1])
    )
    return (
        GraphModel.create(
            name="wedge-c3-c5",
            vertices=vertices,
            edges=edges,
            max_layer=3,
        ),
        triangle,
        pentagon,
    )


def theta_123() -> GraphModel:
    return GraphModel.create(
        name="theta-1-2-3",
        vertices=("a", "b", "c", "s", "t"),
        edges=(
            ("s", "t"),
            ("a", "s"),
            ("a", "t"),
            ("b", "s"),
            ("b", "c"),
            ("c", "t"),
        ),
        max_layer=3,
    )


def chorded_c6_distance_two() -> GraphModel:
    base = cycle_graph(6)
    return GraphModel.create(
        name="chorded-c6-distance-two",
        vertices=base.vertices,
        edges=base.edges + (("v0", "v2"),),
        max_layer=3,
    )


def chorded_c6_diametric() -> GraphModel:
    base = cycle_graph(6)
    return GraphModel.create(
        name="chorded-c6-diametric",
        vertices=base.vertices,
        edges=base.edges + (("v0", "v3"),),
        max_layer=3,
    )


def barycentric_rp2_graph() -> GraphModel:
    """Build the appendix pure-torsion graph without copied facet data."""

    universe = frozenset(range(4))

    def orbit_vertex(face: frozenset[int]) -> tuple[int, ...]:
        complement = universe - face
        return min(tuple(sorted(face)), tuple(sorted(complement)))

    base_facets = {
        tuple(sorted(orbit_vertex(frozenset(permutation[:size])) for size in (1, 2, 3)))
        for permutation in permutations(range(4))
    }
    if len(base_facets) != 12:
        raise AssertionError("the tetrahedron quotient must have twelve triangles")

    faces: set[tuple[tuple[int, ...], ...]] = set()
    for facet in base_facets:
        for size in (1, 2, 3):
            faces.update(combinations(facet, size))

    def label(face: tuple[tuple[int, ...], ...]) -> str:
        prefix = {1: "v", 2: "e", 3: "f"}[len(face)]
        encoded = "|".join(",".join(map(str, vertex)) for vertex in face)
        return prefix + ":" + encoded

    vertices = tuple(sorted(label(face) for face in faces))
    ordered_faces = sorted(faces, key=lambda face: (len(face), face))
    edges = tuple(
        (label(left), label(right))
        for left, right in combinations(ordered_faces, 2)
        if set(left) < set(right) or set(right) < set(left)
    )
    return GraphModel.create(
        name="subdivided-rp2",
        vertices=vertices,
        edges=edges,
        max_layer=3,
    )


def model_with_wedge_readout(values: tuple[int, int]) -> GraphModel:
    model, triangle, pentagon = wedge_c3_c5()
    basis = build_homology_basis(model)
    cycle_basis = Matrix.hstack(
        cycle_coordinates(triangle, basis),
        cycle_coordinates(pentagon, basis),
    )
    if abs(int(cycle_basis.det())) != 1:
        raise AssertionError("the two wedge cycles must form an integer basis")
    row = Matrix([values]) * cycle_basis.inv()
    if not all(entry.is_Integer for entry in row):
        raise AssertionError("the requested readout was not integral")
    cochain = {
        chord: int(row[0, index])
        for index, chord in enumerate(basis.chord_edges)
        if row[0, index] != 0
    }
    return GraphModel.create(
        name=f"wedge-readout-{values[0]}-{values[1]}",
        vertices=model.vertices,
        edges=model.edges,
        readouts=(("pi", cochain),),
        max_layer=3,
    )


class ExposureFiltrationTests(unittest.TestCase):
    def assert_layer_signature(
        self,
        model: GraphModel,
        expected: dict[int, tuple[int, tuple[int, ...]]],
    ) -> None:
        result = analyze_model(model)
        for layer, (rank, torsion) in expected.items():
            observed_rank, quotient = lattice_signature(
                result.filtration.at(layer).exposure,
                result.basis.rank,
            )
            self.assertEqual(observed_rank, rank)
            self.assertEqual(quotient.torsion_factors, torsion)

    def test_tree_is_the_zero_boundary_case(self) -> None:
        model = GraphModel.create(
            name="tree",
            vertices=("a", "b", "c", "d"),
            edges=(("a", "b"), ("b", "c"), ("c", "d")),
        )
        self.assert_layer_signature(model, {2: (0, ())})

    def test_cycles_c3_through_c5_have_the_expected_first_layer(self) -> None:
        self.assert_layer_signature(cycle_graph(3), {2: (1, ())})
        self.assert_layer_signature(cycle_graph(4), {2: (1, ())})
        self.assert_layer_signature(cycle_graph(5), {2: (0, ()), 3: (1, ())})

    def test_theta_long_cycle_is_generated_at_the_lower_layer(self) -> None:
        self.assert_layer_signature(theta_123(), {2: (2, ()), 3: (2, ())})

    def test_chorded_c6_has_two_distinct_exposure_layers(self) -> None:
        self.assert_layer_signature(chorded_c6_distance_two(), {2: (1, ()), 3: (2, ())})

    def test_paper_chorded_c6_has_both_directions_at_layer_two(self) -> None:
        model = chorded_c6_diametric()
        self.assert_layer_signature(model, {2: (2, ()), 3: (2, ())})
        result = analyze_model(model)
        self.assertEqual(result.filtration.at(2).exposure_graded.free_rank, 2)
        self.assertEqual(result.filtration.at(3).exposure_graded.free_rank, 0)
        self.assertEqual(
            path_pair_oracle(result.basis, max_length=2),
            result.filtration.at(2).exposure,
        )

    def test_wedge_c3_c5_has_two_distinct_exposure_layers(self) -> None:
        self.assert_layer_signature(wedge_c3_c5()[0], {2: (1, ()), 3: (2, ())})

    def test_barycentric_rp2_realizes_a_pure_torsion_layer(self) -> None:
        result = analyze_model(barycentric_rp2_graph(), alpha=0.3)
        layer_two = result.filtration.at(2)
        layer_three = result.filtration.at(3)
        self.assertEqual(
            (len(result.model.vertices), len(result.model.edges), result.basis.rank),
            (37, 108, 72),
        )
        self.assertEqual(
            lattice_signature(layer_two.exposure, result.basis.rank),
            (72, QuotientInvariants(free_rank=0, torsion_factors=(2,))),
        )
        self.assertEqual(layer_three.exposure, ImmutableMatrix(eye(72)))
        self.assertEqual(
            layer_three.exposure_graded,
            QuotientInvariants(free_rank=0, torsion_factors=(2,)),
        )
        self.assertEqual(result.phase.layers[1].hidden_free_rank, 0)
        self.assertEqual(result.phase.layers[1].entropy_log_t_coefficient, 0.0)

    def test_cycle_and_path_budgets_never_return_silent_partial_results(self) -> None:
        model = theta_123()
        limited = GraphModel.create(
            name=model.name,
            vertices=model.vertices,
            edges=model.edges,
            max_layer=3,
            max_cycles=1,
        )
        limited_result = analyze_model(limited)
        self.assertEqual(limited_result.status, AnalysisStatus.LIMIT_REACHED)
        self.assertFalse(limited_result.is_complete)
        self.assertIsNone(limited_result.filtration)
        self.assertIsNone(limited_result.phase)
        self.assertEqual(limited_result.limit.resource, "simple_cycles")
        self.assertEqual(limited_result.limit.limit, 1)
        with self.assertRaises(PathLimitExceeded):
            path_pair_oracle(
                build_homology_basis(model),
                max_length=3,
                max_paths=1,
            )


class IndependentOracleTests(unittest.TestCase):
    def test_path_pair_definition_matches_short_simple_cycles(self) -> None:
        cases = [
            cycle_graph(3, max_layer=3),
            cycle_graph(4, max_layer=3),
            cycle_graph(5, max_layer=3),
            theta_123(),
            chorded_c6_distance_two(),
            chorded_c6_diametric(),
            wedge_c3_c5()[0],
        ]
        for model in cases:
            with self.subTest(model=model.name):
                result = analyze_model(model)
                for layer in (2, 3):
                    self.assertEqual(
                        path_pair_oracle(result.basis, max_length=layer),
                        result.filtration.at(layer).exposure,
                    )


class ReadoutAndInvarianceTests(unittest.TestCase):
    def test_mixed_readouts_preserve_hidden_rank_but_change_visible_torsion(
        self,
    ) -> None:
        one = analyze_model(model_with_wedge_readout((1, 1))).filtration.at(3)
        two = analyze_model(model_with_wedge_readout((2, 1))).filtration.at(3)
        expected_hidden = QuotientInvariants(free_rank=1, torsion_factors=())
        self.assertEqual(one.hidden_graded, expected_hidden)
        self.assertEqual(two.hidden_graded, expected_hidden)
        self.assertTrue(one.visible_graded.is_trivial)
        self.assertEqual(
            two.visible_graded,
            QuotientInvariants(free_rank=0, torsion_factors=(2,)),
        )

    def test_absolute_visible_lattice_retains_finite_index(self) -> None:
        result = analyze_model(model_with_wedge_readout((2, 1)))
        layer_two = result.filtration.at(2)
        self.assertEqual(
            lattice_signature(layer_two.visible, result.readout.rows),
            (1, QuotientInvariants(free_rank=0, torsion_factors=(2,))),
        )

    def test_homology_basis_has_no_mutable_matrix_backdoor(self) -> None:
        result = analyze_model(model_with_wedge_readout((2, 1)))
        self.assertFalse(hasattr(result.basis, "_mutable_fundamental_cycles"))
        with self.assertRaises(TypeError):
            result.basis.fundamental_cycles[0, 0] = 99

    def test_tree_change_and_edge_reversal_preserve_invariants(self) -> None:
        model = model_with_wedge_readout((2, 1))
        reversed_model = GraphModel.create(
            name=model.name,
            vertices=tuple(reversed(model.vertices)),
            edges=tuple((v, u) for u, v in reversed(model.edges)),
            readouts=(
                (
                    model.readouts[0].name,
                    model.readouts[0].as_mapping(),
                ),
            ),
            max_layer=3,
        )
        baseline = analyze_model(model)
        changed = analyze_model(reversed_model, reverse_tree_order=True)
        self.assertEqual(
            analysis_signature(changed.filtration),
            analysis_signature(baseline.filtration),
        )

    def test_vertex_relabeling_preserves_invariants(self) -> None:
        model = model_with_wedge_readout((2, 1))
        labels = {
            vertex: f"z{len(model.vertices) - index:02d}"
            for index, vertex in enumerate(model.vertices)
        }
        relabeled_edges = tuple(
            (labels[u], labels[v]) for u, v in reversed(model.edges)
        )
        relabeled_cochain: dict[tuple[str, str], int] = {}
        for edge, coefficient in model.readouts[0].coefficients:
            mapped = (labels[edge[0]], labels[edge[1]])
            public = canonical_edge(*mapped)
            relabeled_cochain[public] = (
                coefficient if mapped == public else -coefficient
            )
        relabeled = GraphModel.create(
            name="relabeled",
            vertices=tuple(labels[vertex] for vertex in model.vertices),
            edges=relabeled_edges,
            readouts=(("pi", relabeled_cochain),),
            max_layer=3,
        )
        self.assertEqual(
            analysis_signature(
                analyze_model(relabeled, reverse_tree_order=True).filtration
            ),
            analysis_signature(analyze_model(model).filtration),
        )

    def test_model_rejects_noninteger_and_unknown_readouts(self) -> None:
        with self.assertRaises(TypeError):
            GraphModel.create(
                name="bad-real-readout",
                vertices=("a", "b", "c"),
                edges=(("a", "b"), ("b", "c"), ("c", "a")),
                readouts=(("pi", {("a", "b"): 0.5}),),
            )
        with self.assertRaises(ValueError):
            GraphModel.create(
                name="bad-edge-readout",
                vertices=("a", "b", "c"),
                edges=(("a", "b"), ("b", "c"), ("c", "a")),
                readouts=(("pi", {("a", "z"): 1}),),
            )


if __name__ == "__main__":
    unittest.main()
