"""Constructive and independent checks for the critical path catalogue."""

from __future__ import annotations

import unittest
from fractions import Fraction
from itertools import product

import networkx as nx
from sympy import ImmutableMatrix, Matrix, eye

from homological_observability._critical_catalogue import (
    InducedQuotientMap,
    QuotientElement,
    QuotientPresentation,
    build_critical_path_catalogue,
    build_marked_poisson_experiment,
)
from homological_observability.analysis import analyze_model
from homological_observability.homology import (
    chain_from_walk,
    coordinates_from_cycle_chain,
)
from homological_observability.integer_lattice import quotient_invariants
from homological_observability.model import GraphModel


def cycle_model(size: int, *, max_layer: int) -> GraphModel:
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


def exact_rates(model: GraphModel) -> dict[tuple[str, str], Fraction]:
    directed = sorted((u, v) for edge in model.edges for u, v in (edge, edge[::-1]))
    return {edge: Fraction(index + 1, index + 2) for index, edge in enumerate(directed)}


def contained_in_column_lattice(vector: Matrix, lattice: Matrix) -> bool:
    """Independent membership oracle using exact linear solving, not Smith form."""

    if lattice.cols == 0:
        return vector == Matrix.zeros(vector.rows, vector.cols)
    try:
        coordinates, parameters = lattice.gauss_jordan_solve(vector)
    except ValueError:
        return False
    return (
        parameters.rows == 0
        and lattice * coordinates == vector
        and all(entry.is_Integer for entry in coordinates)
    )


def walks_of_length(
    graph: nx.Graph,
    start: str,
    length: int,
) -> tuple[tuple[str, ...], ...]:
    walks = [(start,)]
    for _ in range(length):
        walks = [
            walk + (neighbor,)
            for walk in walks
            for neighbor in sorted(graph.neighbors(walk[-1]))
        ]
    return tuple(walks)


class ConstructiveQuotientTests(unittest.TestCase):
    def test_smith_coordinates_match_an_independent_membership_oracle(self) -> None:
        cases = (
            Matrix.zeros(2, 0),
            Matrix([[2], [0]]),
            Matrix([[2], [4]]),
            Matrix([[2, 4], [6, 8]]),
        )
        super_lattice = ImmutableMatrix([[1, 1], [0, 2]])
        for inclusion in cases:
            with self.subTest(inclusion=inclusion.tolist()):
                sub_lattice = ImmutableMatrix(Matrix(super_lattice) * inclusion)
                presentation = QuotientPresentation.create(
                    sub_lattice,
                    super_lattice,
                )
                self.assertEqual(
                    presentation.invariants,
                    quotient_invariants(sub_lattice, super_lattice),
                )
                vectors = [Matrix(values) for values in product(range(-2, 3), repeat=2)]
                labels = {
                    tuple(vector): presentation.project_super_coordinates(vector)
                    for vector in vectors
                }
                for vector in vectors:
                    label = labels[tuple(vector)]
                    representative = Matrix(
                        presentation.representative_super_coordinates(label)
                    )
                    self.assertTrue(
                        contained_in_column_lattice(
                            vector - representative,
                            inclusion,
                        )
                    )
                    self.assertEqual(
                        presentation.project_ambient(Matrix(super_lattice) * vector),
                        label,
                    )
                for left in vectors:
                    for right in vectors:
                        self.assertEqual(
                            labels[tuple(left)] == labels[tuple(right)],
                            contained_in_column_lattice(left - right, inclusion),
                        )

    def test_induced_map_is_exact_and_well_defined_on_torsion(self) -> None:
        source = QuotientPresentation.create(
            ImmutableMatrix([[2], [0]]),
            ImmutableMatrix(eye(2)),
        )
        target = QuotientPresentation.create(
            ImmutableMatrix([[2]]),
            ImmutableMatrix([[1]]),
        )
        induced = InducedQuotientMap.create(
            source,
            target,
            ImmutableMatrix([[1, 0]]),
        )
        hidden = QuotientPresentation.create(
            ImmutableMatrix.zeros(2, 0),
            ImmutableMatrix([[0], [1]]),
        )
        hidden_inclusion = InducedQuotientMap.create(
            hidden,
            source,
            ImmutableMatrix(eye(2)),
        )
        self.assertEqual(source.invariants.torsion_factors, (2,))
        self.assertEqual(target.invariants.torsion_factors, (2,))
        kernel = set()
        for torsion in range(2):
            for free in range(-3, 4):
                element = QuotientElement(torsion=(torsion,), free=(free,))
                image = induced.apply(element)
                ambient_image = Matrix([[1, 0]]) * Matrix(
                    source.representative_ambient(element)
                )
                self.assertEqual(target.project_ambient(ambient_image), image)
                self.assertEqual(image == target.zero, torsion == 0)
                if image == target.zero:
                    kernel.add(element)
        hidden_image = {
            hidden_inclusion.apply(QuotientElement(torsion=(), free=(value,)))
            for value in range(-3, 4)
        }
        self.assertEqual(kernel, hidden_image)

        shifted = Matrix([5, -2])
        representative = Matrix(
            source.representative_super_coordinates(
                source.project_super_coordinates(shifted)
            )
        )
        self.assertTrue(
            contained_in_column_lattice(
                shifted - representative,
                Matrix([[2], [0]]),
            )
        )

    def test_zero_rank_quotient_has_exact_empty_coordinates(self) -> None:
        presentation = QuotientPresentation.create(
            ImmutableMatrix.zeros(0, 0),
            ImmutableMatrix.zeros(0, 0),
        )
        self.assertEqual(presentation.zero, QuotientElement(torsion=(), free=()))
        self.assertEqual(
            presentation.project_ambient(Matrix.zeros(0, 1)),
            presentation.zero,
        )
        self.assertEqual(
            presentation.representative_ambient(presentation.zero).shape,
            (0, 1),
        )


class CriticalPathCatalogueTests(unittest.TestCase):
    def test_common_and_critical_endpoint_mechanisms_are_separated(self) -> None:
        triangle = cycle_model(3, max_layer=2)
        triangle_analysis = analyze_model(triangle).filtration
        self.assertIsNotNone(triangle_analysis)
        triangle_catalogue = build_critical_path_catalogue(
            triangle_analysis,
            rates=exact_rates(triangle),
            layer=2,
        )
        self.assertEqual(len(triangle_catalogue.terms), 12)
        self.assertEqual(len(triangle_catalogue.common_endpoint_weights()), 6)
        self.assertEqual(triangle_catalogue.critical_endpoint_weights(), ())
        self.assertTrue(
            all(
                item.label != triangle_catalogue.graded_group.zero
                for item in triangle_catalogue.common_endpoint_weights()
            )
        )

        square = cycle_model(4, max_layer=2)
        square_analysis = analyze_model(square).filtration
        self.assertIsNotNone(square_analysis)
        square_catalogue = build_critical_path_catalogue(
            square_analysis,
            rates=exact_rates(square),
            layer=2,
        )
        self.assertEqual(len(square_catalogue.terms), 16)
        self.assertEqual(square_catalogue.common_endpoint_weights(), ())
        self.assertEqual(len(square_catalogue.critical_endpoint_weights()), 8)
        self.assertTrue(
            all(
                item.endpoint_distance == 2
                for item in square_catalogue.critical_endpoint_weights()
            )
        )

    def test_leading_weights_use_exact_directed_rate_products(self) -> None:
        model = cycle_model(3, max_layer=2)
        rates = exact_rates(model)
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        catalogue = build_critical_path_catalogue(
            analysis,
            rates=rates,
            layer=2,
        )
        term = next(term for term in catalogue.terms if term.walk == ("v0", "v1", "v2"))
        self.assertEqual(
            term.leading_weight,
            rates[("v0", "v1")] * rates[("v1", "v2")] / 2,
        )
        self.assertIsInstance(term.leading_weight, Fraction)

    def test_catalogue_enumerates_walks_with_repeated_vertices(self) -> None:
        model = cycle_model(5, max_layer=3)
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        catalogue = build_critical_path_catalogue(
            analysis,
            rates=exact_rates(model),
            layer=3,
        )
        self.assertIn(
            ("v0", "v1", "v0", "v1"),
            {term.walk for term in catalogue.terms},
        )

    def test_geodesic_change_is_an_endpoint_wise_affine_translation(self) -> None:
        base = cycle_model(4, max_layer=2)
        model = GraphModel.create(
            name="c4-visible",
            vertices=base.vertices,
            edges=base.edges,
            readouts=(("pi", {("v0", "v1"): 2}),),
            max_layer=2,
        )
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        rates = exact_rates(model)
        baseline = build_critical_path_catalogue(
            analysis,
            rates=rates,
            layer=2,
        )
        changed = build_critical_path_catalogue(
            analysis,
            rates=rates,
            layer=2,
            geodesics={("v0", "v2"): ("v0", "v3", "v2")},
        )
        translation, visible_translation = baseline.gauge_translation_to(
            changed,
            "v0",
            "v2",
        )
        self.assertNotEqual(translation, baseline.graded_group.zero)
        self.assertNotEqual(visible_translation, baseline.visible_group.zero)
        baseline_terms = {
            term.walk: term
            for term in baseline.terms
            if term.start == "v0" and term.end == "v2"
        }
        changed_terms = {
            term.walk: term
            for term in changed.terms
            if term.start == "v0" and term.end == "v2"
        }
        self.assertEqual(set(baseline_terms), set(changed_terms))
        for walk, term in baseline_terms.items():
            changed_term = changed_terms[walk]
            self.assertEqual(
                changed_term.label,
                baseline.graded_group.add(term.label, translation),
            )
            self.assertEqual(
                changed_term.visible_label,
                baseline.visible_group.add(
                    term.visible_label,
                    visible_translation,
                ),
            )
            self.assertEqual(changed_term.leading_weight, term.leading_weight)

    def test_rates_reject_inexact_or_incomplete_inputs(self) -> None:
        model = cycle_model(3, max_layer=2)
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        rates = exact_rates(model)
        rates[("v0", "v1")] = 0.5
        with self.assertRaises(TypeError):
            build_critical_path_catalogue(analysis, rates=rates, layer=2)
        del rates[("v0", "v1")]
        with self.assertRaises(ValueError):
            build_critical_path_catalogue(analysis, rates=rates, layer=2)


class MarkedPoissonExperimentTests(unittest.TestCase):
    def test_c3_and_c4_match_the_closed_form_critical_mechanisms(self) -> None:
        triangle = cycle_model(3, max_layer=2)
        triangle_analysis = analyze_model(triangle).filtration
        self.assertIsNotNone(triangle_analysis)
        triangle_experiment = build_marked_poisson_experiment(
            triangle_analysis,
            rates={edge: 1 for edge in exact_rates(triangle)},
            layer=2,
            theta=1,
        )
        self.assertEqual(
            triangle_experiment.stationary_law.probabilities,
            (Fraction(1, 3),) * 3,
        )
        self.assertEqual(
            sorted(atom.intensity for atom in triangle_experiment.common_levy_measure),
            [Fraction(1, 2), Fraction(1, 2)],
        )
        self.assertEqual(triangle_experiment.common_total_intensity, 1)
        self.assertEqual(triangle_experiment.critical_endpoint_components, ())

        square = cycle_model(4, max_layer=2)
        square_analysis = analyze_model(square).filtration
        self.assertIsNotNone(square_analysis)
        square_experiment = build_marked_poisson_experiment(
            square_analysis,
            rates={edge: 1 for edge in exact_rates(square)},
            layer=2,
            theta=1,
        )
        self.assertEqual(square_experiment.common_levy_measure, ())
        self.assertEqual(len(square_experiment.critical_endpoint_components), 4)
        self.assertEqual(square_experiment.critical_total_intensity, 1)
        for component in square_experiment.critical_endpoint_components:
            self.assertEqual(component.poisson_intensity, Fraction(1, 4))
            self.assertEqual(
                sorted(mark.probability for mark in component.mark_law),
                [Fraction(1, 2), Fraction(1, 2)],
            )

    def test_nonreversible_c3_has_exact_stationary_and_directional_weights(
        self,
    ) -> None:
        model = cycle_model(3, max_layer=2)
        rates = {
            ("v0", "v1"): Fraction(2),
            ("v1", "v0"): Fraction(1),
            ("v1", "v2"): Fraction(3),
            ("v2", "v1"): Fraction(4),
            ("v2", "v0"): Fraction(5),
            ("v0", "v2"): Fraction(2),
        }
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        experiment = build_marked_poisson_experiment(
            analysis,
            rates=rates,
            layer=2,
            theta=1,
        )
        self.assertEqual(
            experiment.stationary_law.probabilities,
            (Fraction(3, 8), Fraction(13, 32), Fraction(7, 32)),
        )
        self.assertEqual(
            sorted(atom.intensity for atom in experiment.common_levy_measure),
            [Fraction(75, 32), Fraction(337, 64)],
        )
        probability_row = Matrix([experiment.stationary_law.probabilities])
        self.assertEqual(
            probability_row * Matrix(experiment.stationary_law.generator),
            Matrix.zeros(1, 3),
        )

    def test_critical_endpoint_law_changes_only_by_the_geodesic_translation(
        self,
    ) -> None:
        model = cycle_model(4, max_layer=2)
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        rates = {edge: 1 for edge in exact_rates(model)}
        baseline = build_marked_poisson_experiment(
            analysis,
            rates=rates,
            layer=2,
            theta=2,
        )
        changed = build_marked_poisson_experiment(
            analysis,
            rates=rates,
            layer=2,
            theta=2,
            geodesics={("v0", "v2"): ("v0", "v3", "v2")},
        )
        translation, _ = baseline.catalogue.gauge_translation_to(
            changed.catalogue,
            "v0",
            "v2",
        )
        baseline_components = {
            (item.start, item.end): item
            for item in baseline.critical_endpoint_components
        }
        changed_components = {
            (item.start, item.end): item
            for item in changed.critical_endpoint_components
        }
        self.assertEqual(set(baseline_components), set(changed_components))
        for endpoints, component in baseline_components.items():
            changed_component = changed_components[endpoints]
            self.assertEqual(
                component.poisson_intensity,
                changed_component.poisson_intensity,
            )
            expected = {
                (
                    baseline.catalogue.graded_group.add(mark.label, translation)
                    if endpoints == ("v0", "v2")
                    else mark.label
                ): mark.probability
                for mark in component.mark_law
            }
            self.assertEqual(
                {mark.label: mark.probability for mark in changed_component.mark_law},
                expected,
            )

    def test_zero_graded_group_keeps_visible_endpoint_zero_marks(self) -> None:
        model = GraphModel.create(
            name="path-3",
            vertices=("v0", "v1", "v2"),
            edges=(("v0", "v1"), ("v1", "v2")),
            max_layer=2,
        )
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        experiment = build_marked_poisson_experiment(
            analysis,
            rates={
                ("v0", "v1"): 1,
                ("v1", "v0"): 1,
                ("v1", "v2"): 1,
                ("v2", "v1"): 1,
            },
            layer=2,
            theta=1,
        )
        self.assertEqual(
            experiment.catalogue.graded_group.zero, QuotientElement((), ())
        )
        self.assertEqual(experiment.common_levy_measure, ())
        self.assertEqual(len(experiment.critical_endpoint_components), 2)
        for component in experiment.critical_endpoint_components:
            self.assertEqual(component.poisson_intensity, Fraction(1, 6))
            self.assertEqual(len(component.mark_law), 1)
            self.assertEqual(component.mark_law[0].label, QuotientElement((), ()))
            self.assertEqual(component.mark_law[0].probability, 1)

    def test_endpoint_weight_sums_match_an_independent_matrix_power(self) -> None:
        model = cycle_model(5, max_layer=3)
        rates = exact_rates(model)
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        experiment = build_marked_poisson_experiment(
            analysis,
            rates=rates,
            layer=3,
            theta=Fraction(7, 5),
        )
        vertices = model.vertices
        index = {vertex: position for position, vertex in enumerate(vertices)}
        weighted_adjacency = [[Fraction(0) for _ in vertices] for _ in vertices]
        for (start, end), rate in rates.items():
            weighted_adjacency[index[start]][index[end]] = rate

        def multiply(
            left: list[list[Fraction]],
            right: list[list[Fraction]],
        ) -> list[list[Fraction]]:
            return [
                [
                    sum(
                        (
                            left[row][inner] * right[inner][column]
                            for inner in range(len(vertices))
                        ),
                        start=Fraction(0),
                    )
                    for column in range(len(vertices))
                ]
                for row in range(len(vertices))
            ]

        powered = weighted_adjacency
        for _ in range(2):
            powered = multiply(powered, weighted_adjacency)
        observed: dict[tuple[str, str], Fraction] = {}
        for item in experiment.catalogue.aggregate_weights():
            key = (item.start, item.end)
            observed[key] = observed.get(key, Fraction(0)) + item.leading_weight
        for start in vertices:
            for end in vertices:
                self.assertEqual(
                    observed.get((start, end), Fraction(0)),
                    powered[index[start]][index[end]] / 6,
                )

    def test_theta_requires_a_positive_exact_value(self) -> None:
        model = cycle_model(3, max_layer=2)
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        rates = exact_rates(model)
        for invalid in (0, -1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build_marked_poisson_experiment(
                    analysis,
                    rates=rates,
                    layer=2,
                    theta=invalid,
                )
        with self.assertRaises(TypeError):
            build_marked_poisson_experiment(
                analysis,
                rates=rates,
                layer=2,
                theta=0.5,
            )


class PropositionSixThreeOracleTests(unittest.TestCase):
    def test_exhaustive_small_walk_pairs_satisfy_the_cost_bound(self) -> None:
        cases = (
            cycle_model(3, max_layer=2),
            cycle_model(4, max_layer=2),
            cycle_model(5, max_layer=3),
        )
        checked = 0
        nonzero = 0
        equality = 0
        for model in cases:
            analysis = analyze_model(model).filtration
            self.assertIsNotNone(analysis)
            layer = model.max_layer
            self.assertIsNotNone(layer)
            lower = Matrix(analysis.at(layer - 1).exposure)
            graph = nx.Graph()
            graph.add_nodes_from(model.vertices)
            graph.add_edges_from(model.edges)
            paths: dict[tuple[str, str], list[tuple[str, ...]]] = {}
            for start in model.vertices:
                for length in range(layer + 1):
                    for walk in walks_of_length(graph, start, length):
                        paths.setdefault((start, walk[-1]), []).append(walk)

            for (start, end), endpoint_paths in paths.items():
                distance = nx.shortest_path_length(graph, start, end)
                for left in endpoint_paths:
                    for right in endpoint_paths:
                        r = len(left) - 1
                        s = len(right) - 1
                        if r > s:
                            continue
                        difference = chain_from_walk(
                            left, analysis.basis
                        ) - chain_from_walk(
                            right,
                            analysis.basis,
                        )
                        coordinates = Matrix(
                            coordinates_from_cycle_chain(difference, analysis.basis)
                        )
                        checked += 1
                        if contained_in_column_lattice(coordinates, lower):
                            continue
                        nonzero += 1
                        cost = r + s - distance
                        self.assertGreaterEqual(cost, layer)
                        if cost == layer:
                            equality += 1
                            self.assertEqual(r, distance)
                            self.assertEqual(s, layer)
        self.assertGreater(checked, 100)
        self.assertGreater(nonzero, 0)
        self.assertGreater(equality, 0)

    def test_catalogue_matches_independent_product_enumeration(self) -> None:
        model = cycle_model(5, max_layer=3)
        analysis = analyze_model(model).filtration
        self.assertIsNotNone(analysis)
        catalogue = build_critical_path_catalogue(
            analysis,
            rates=exact_rates(model),
            layer=3,
        )
        graph = nx.Graph()
        graph.add_nodes_from(model.vertices)
        graph.add_edges_from(model.edges)
        oracle = {
            vertices
            for vertices in product(model.vertices, repeat=4)
            if all(
                graph.has_edge(tail, head) for tail, head in zip(vertices, vertices[1:])
            )
        }
        self.assertEqual({term.walk for term in catalogue.terms}, oracle)


if __name__ == "__main__":
    unittest.main()
