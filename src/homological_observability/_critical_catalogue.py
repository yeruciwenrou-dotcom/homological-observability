"""Exact critical-layer quotient coordinates and finite path catalogues."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import factorial
from typing import Iterable

import networkx as nx
from sympy import ZZ, ImmutableMatrix, Matrix, Rational
from sympy.matrices.matrixbase import MatrixBase
from sympy.matrices.normalforms import smith_normal_decomp

from .filtration import FiltrationAnalysis
from .homology import (
    HomologyBasis,
    chain_from_walk,
    coordinates_from_cycle_chain,
)
from .integer_lattice import QuotientInvariants, inclusion_coordinates


def _require_integer_matrix(matrix: MatrixBase, *, label: str) -> None:
    if any(not entry.is_Integer for entry in matrix):
        raise TypeError(f"{label} requires an integer matrix")


def _coordinates_in_basis(
    vectors: MatrixBase,
    basis: MatrixBase,
    *,
    label: str,
) -> ImmutableMatrix:
    """Express columns in an independent integer basis, including zero bases."""

    vectors = Matrix(vectors)
    basis = Matrix(basis)
    _require_integer_matrix(vectors, label=label)
    _require_integer_matrix(basis, label=label)
    if vectors.rows != basis.rows:
        raise ValueError(f"{label} uses incompatible ambient dimensions")
    if vectors.cols == 0:
        return ImmutableMatrix.zeros(basis.cols, 0)
    if basis.cols == 0:
        if vectors != Matrix.zeros(vectors.rows, vectors.cols):
            raise ValueError(f"{label} is outside the target lattice")
        return ImmutableMatrix.zeros(0, vectors.cols)
    try:
        coordinates, parameters = basis.gauss_jordan_solve(vectors)
    except ValueError as error:
        raise ValueError(f"{label} is outside the target lattice") from error
    if parameters.rows:
        raise AssertionError("lattice bases must have independent columns")
    if basis * coordinates != vectors:
        raise ValueError(f"{label} is outside the target lattice")
    if any(not entry.is_Integer for entry in coordinates):
        raise ValueError(f"{label} has nonintegral lattice coordinates")
    return ImmutableMatrix(coordinates)


@dataclass(frozen=True, order=True)
class QuotientElement:
    """Canonical torsion and free coordinates in a fixed quotient presentation."""

    torsion: tuple[int, ...]
    free: tuple[int, ...]


@dataclass(frozen=True)
class QuotientPresentation:
    """Constructive Smith coordinates for ``super_lattice / sub_lattice``."""

    sub_lattice: ImmutableMatrix
    super_lattice: ImmutableMatrix
    smith_diagonal: ImmutableMatrix
    smith_left: ImmutableMatrix
    smith_left_inverse: ImmutableMatrix
    torsion_positions: tuple[int, ...]
    torsion_moduli: tuple[int, ...]

    @classmethod
    def create(
        cls,
        sub_lattice: MatrixBase,
        super_lattice: MatrixBase,
    ) -> QuotientPresentation:
        sub = ImmutableMatrix(sub_lattice)
        super_basis = ImmutableMatrix(super_lattice)
        _require_integer_matrix(sub, label="quotient presentation")
        _require_integer_matrix(super_basis, label="quotient presentation")
        if sub.rows != super_basis.rows:
            raise ValueError("quotient lattices must share an ambient group")
        if Matrix(sub).rank() != sub.cols:
            raise ValueError("the sublattice columns must form a basis")
        if Matrix(super_basis).rank() != super_basis.cols:
            raise ValueError("the containing lattice columns must form a basis")

        inclusion = inclusion_coordinates(sub, super_basis)
        mutable = Matrix(inclusion)
        diagonal, left, right = smith_normal_decomp(mutable, domain=ZZ)
        if diagonal != left * mutable * right:
            raise AssertionError("invalid Smith decomposition for quotient")
        if abs(int(left.det())) != 1 or abs(int(right.det())) != 1:
            raise AssertionError("Smith transformations must be unimodular")
        if sub.cols > super_basis.cols:
            raise AssertionError("a sublattice cannot have larger rank")
        diagonal_entries = tuple(
            abs(int(diagonal[index, index])) for index in range(sub.cols)
        )
        if any(entry == 0 for entry in diagonal_entries):
            raise AssertionError("a lattice inclusion must have full column rank")
        torsion_positions = tuple(
            index for index, entry in enumerate(diagonal_entries) if entry > 1
        )
        left_inverse = left.inv()
        if any(not entry.is_Integer for entry in left_inverse):
            raise AssertionError("a unimodular Smith transform must invert integrally")
        if left * left_inverse != Matrix.eye(left.rows):
            raise AssertionError("invalid inverse Smith transform")
        return cls(
            sub_lattice=sub,
            super_lattice=super_basis,
            smith_diagonal=ImmutableMatrix(diagonal),
            smith_left=ImmutableMatrix(left),
            smith_left_inverse=ImmutableMatrix(left_inverse),
            torsion_positions=torsion_positions,
            torsion_moduli=tuple(
                diagonal_entries[index] for index in torsion_positions
            ),
        )

    @property
    def free_rank(self) -> int:
        return self.super_lattice.cols - self.sub_lattice.cols

    @property
    def invariants(self) -> QuotientInvariants:
        return QuotientInvariants(
            free_rank=self.free_rank,
            torsion_factors=self.torsion_moduli,
        )

    @property
    def zero(self) -> QuotientElement:
        return QuotientElement(
            torsion=(0,) * len(self.torsion_moduli),
            free=(0,) * self.free_rank,
        )

    def _validate_element(self, element: QuotientElement) -> None:
        if len(element.torsion) != len(self.torsion_moduli):
            raise ValueError("the quotient element has the wrong torsion dimension")
        if len(element.free) != self.free_rank:
            raise ValueError("the quotient element has the wrong free dimension")
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in element.torsion + element.free
        ):
            raise TypeError("quotient coordinates must be integers")
        if any(
            value < 0 or value >= modulus
            for value, modulus in zip(element.torsion, self.torsion_moduli)
        ):
            raise ValueError("torsion coordinates are outside canonical ranges")

    def project_super_coordinates(self, coordinates: MatrixBase) -> QuotientElement:
        coordinates = Matrix(coordinates)
        _require_integer_matrix(coordinates, label="quotient projection")
        if coordinates.shape != (self.super_lattice.cols, 1):
            raise ValueError("super-lattice coordinates have the wrong dimension")
        smith_coordinates = Matrix(self.smith_left) * coordinates
        torsion = tuple(
            int(smith_coordinates[position, 0]) % modulus
            for position, modulus in zip(
                self.torsion_positions,
                self.torsion_moduli,
            )
        )
        free = tuple(
            int(smith_coordinates[position, 0])
            for position in range(self.sub_lattice.cols, self.super_lattice.cols)
        )
        return QuotientElement(torsion=torsion, free=free)

    def project_ambient(self, vector: MatrixBase) -> QuotientElement:
        vector = Matrix(vector)
        if vector.shape != (self.super_lattice.rows, 1):
            raise ValueError("ambient quotient vectors must be columns")
        coordinates = _coordinates_in_basis(
            vector,
            self.super_lattice,
            label="quotient projection",
        )
        return self.project_super_coordinates(coordinates)

    def representative_super_coordinates(
        self,
        element: QuotientElement,
    ) -> ImmutableMatrix:
        self._validate_element(element)
        smith_coordinates = Matrix.zeros(self.super_lattice.cols, 1)
        for position, value in zip(self.torsion_positions, element.torsion):
            smith_coordinates[position, 0] = value
        for offset, value in enumerate(element.free, start=self.sub_lattice.cols):
            smith_coordinates[offset, 0] = value
        coordinates = Matrix(self.smith_left_inverse) * smith_coordinates
        if any(not entry.is_Integer for entry in coordinates):
            raise AssertionError("canonical quotient representative is not integral")
        return ImmutableMatrix(coordinates)

    def representative_ambient(self, element: QuotientElement) -> ImmutableMatrix:
        return ImmutableMatrix(
            Matrix(self.super_lattice)
            * Matrix(self.representative_super_coordinates(element))
        )

    def add(
        self,
        left: QuotientElement,
        right: QuotientElement,
    ) -> QuotientElement:
        self._validate_element(left)
        self._validate_element(right)
        return QuotientElement(
            torsion=tuple(
                (left_value + right_value) % modulus
                for left_value, right_value, modulus in zip(
                    left.torsion,
                    right.torsion,
                    self.torsion_moduli,
                )
            ),
            free=tuple(
                left_value + right_value
                for left_value, right_value in zip(left.free, right.free)
            ),
        )

    def negate(self, element: QuotientElement) -> QuotientElement:
        self._validate_element(element)
        return QuotientElement(
            torsion=tuple(
                (-value) % modulus
                for value, modulus in zip(element.torsion, self.torsion_moduli)
            ),
            free=tuple(-value for value in element.free),
        )

    def subtract(
        self,
        left: QuotientElement,
        right: QuotientElement,
    ) -> QuotientElement:
        return self.add(left, self.negate(right))


@dataclass(frozen=True)
class InducedQuotientMap:
    """An exact homomorphism between two constructive quotient presentations."""

    source: QuotientPresentation
    target: QuotientPresentation
    super_coordinate_matrix: ImmutableMatrix

    @classmethod
    def create(
        cls,
        source: QuotientPresentation,
        target: QuotientPresentation,
        ambient_map: MatrixBase,
    ) -> InducedQuotientMap:
        ambient_map = Matrix(ambient_map)
        _require_integer_matrix(ambient_map, label="induced quotient map")
        if ambient_map.shape != (
            target.super_lattice.rows,
            source.super_lattice.rows,
        ):
            raise ValueError("the ambient map has incompatible dimensions")
        mapped_super = ambient_map * Matrix(source.super_lattice)
        coordinate_matrix = _coordinates_in_basis(
            mapped_super,
            target.super_lattice,
            label="induced quotient map",
        )
        mapped_sub = ambient_map * Matrix(source.sub_lattice)
        for column in range(mapped_sub.cols):
            if target.project_ambient(mapped_sub[:, column]) != target.zero:
                raise ValueError("the ambient map does not preserve sublattices")
        return cls(
            source=source,
            target=target,
            super_coordinate_matrix=coordinate_matrix,
        )

    def apply(self, element: QuotientElement) -> QuotientElement:
        source_coordinates = self.source.representative_super_coordinates(element)
        target_coordinates = Matrix(self.super_coordinate_matrix) * Matrix(
            source_coordinates
        )
        return self.target.project_super_coordinates(target_coordinates)


@dataclass(frozen=True)
class GeodesicReference:
    start: str
    end: str
    walk: tuple[str, ...]


@dataclass(frozen=True)
class CriticalPathTerm:
    """One length-``m`` directed jump sequence and its exact leading data."""

    walk: tuple[str, ...]
    endpoint_distance: int
    label: QuotientElement
    visible_label: QuotientElement
    leading_weight: Fraction

    @property
    def start(self) -> str:
        return self.walk[0]

    @property
    def end(self) -> str:
        return self.walk[-1]


@dataclass(frozen=True)
class AggregatedPathWeight:
    start: str
    end: str
    endpoint_distance: int
    label: QuotientElement
    visible_label: QuotientElement
    leading_weight: Fraction


@dataclass(frozen=True)
class ExactStationaryLaw:
    """Exact rational generator and its unique stationary distribution."""

    vertices: tuple[str, ...]
    generator: ImmutableMatrix
    probabilities: tuple[Fraction, ...]

    def probability(self, vertex: str) -> Fraction:
        try:
            index = self.vertices.index(vertex)
        except ValueError as error:
            raise KeyError(vertex) from error
        return self.probabilities[index]


@dataclass(frozen=True)
class LevyAtom:
    """One nonzero graded mark in the common-endpoint compound Poisson law."""

    label: QuotientElement
    visible_label: QuotientElement
    intensity: Fraction


@dataclass(frozen=True)
class ConditionalMark:
    """One graded mark and its exact conditional probability."""

    label: QuotientElement
    visible_label: QuotientElement
    probability: Fraction


@dataclass(frozen=True)
class CriticalEndpointComponent:
    """A visible distance-``m`` endpoint count and its conditional mark law."""

    start: str
    end: str
    poisson_intensity: Fraction
    mark_law: tuple[ConditionalMark, ...]


@dataclass(frozen=True)
class MarkedPoissonExperiment:
    """Exact theorem-derived generative specification at one critical layer.

    The common compound-Poisson process and all endpoint components are mutually
    independent, as required by the limiting experiment.
    """

    theta: Fraction
    stationary_law: ExactStationaryLaw
    catalogue: CriticalPathCatalogue
    common_levy_measure: tuple[LevyAtom, ...]
    critical_endpoint_components: tuple[CriticalEndpointComponent, ...]

    @property
    def common_total_intensity(self) -> Fraction:
        return sum(
            (atom.intensity for atom in self.common_levy_measure),
            start=Fraction(0),
        )

    @property
    def critical_total_intensity(self) -> Fraction:
        return sum(
            (
                component.poisson_intensity
                for component in self.critical_endpoint_components
            ),
            start=Fraction(0),
        )

    def visible_residue(self, label: QuotientElement) -> QuotientElement:
        """Apply the induced graded readout ``bar pi_m`` to a total mark."""

        return self.catalogue.induced_readout.apply(label)


@dataclass(frozen=True)
class CriticalPathCatalogue:
    """Finite exact data underlying the critical marked-path experiment."""

    layer: int
    basis: HomologyBasis
    graded_group: QuotientPresentation
    visible_group: QuotientPresentation
    induced_readout: InducedQuotientMap
    geodesics: tuple[GeodesicReference, ...]
    terms: tuple[CriticalPathTerm, ...]

    def geodesic(self, start: str, end: str) -> tuple[str, ...]:
        for reference in self.geodesics:
            if reference.start == start and reference.end == end:
                return reference.walk
        raise KeyError((start, end))

    def aggregate_weights(self) -> tuple[AggregatedPathWeight, ...]:
        totals: dict[tuple[str, str, QuotientElement], Fraction] = {}
        visible: dict[tuple[str, str, QuotientElement], QuotientElement] = {}
        distances: dict[tuple[str, str, QuotientElement], int] = {}
        for term in self.terms:
            key = (term.start, term.end, term.label)
            totals[key] = totals.get(key, Fraction(0)) + term.leading_weight
            visible[key] = term.visible_label
            distances[key] = term.endpoint_distance
        return tuple(
            AggregatedPathWeight(
                start=start,
                end=end,
                endpoint_distance=distances[(start, end, label)],
                label=label,
                visible_label=visible[(start, end, label)],
                leading_weight=totals[(start, end, label)],
            )
            for start, end, label in sorted(totals)
        )

    def common_endpoint_weights(self) -> tuple[AggregatedPathWeight, ...]:
        """Nonzero marks contributing to the deterministic Levy measure."""

        return tuple(
            item
            for item in self.aggregate_weights()
            if item.endpoint_distance < self.layer
            and item.label != self.graded_group.zero
        )

    def critical_endpoint_weights(self) -> tuple[AggregatedPathWeight, ...]:
        """All marks conditional on endpoint pairs at distance exactly ``m``."""

        return tuple(
            item
            for item in self.aggregate_weights()
            if item.endpoint_distance == self.layer
        )

    def gauge_translation_to(
        self,
        other: CriticalPathCatalogue,
        start: str,
        end: str,
    ) -> tuple[QuotientElement, QuotientElement]:
        """Return the endpoint-wise translations induced by a gauge change."""

        if self.layer != other.layer or self.basis != other.basis:
            raise ValueError("gauge comparison requires the same layer and basis")
        if (
            self.graded_group.sub_lattice != other.graded_group.sub_lattice
            or self.graded_group.super_lattice != other.graded_group.super_lattice
        ):
            raise ValueError("gauge comparison requires the same graded group")
        old_chain = chain_from_walk(self.geodesic(start, end), self.basis)
        new_chain = chain_from_walk(other.geodesic(start, end), self.basis)
        coordinates = coordinates_from_cycle_chain(old_chain - new_chain, self.basis)
        translation = self.graded_group.project_ambient(coordinates)
        return translation, self.induced_readout.apply(translation)


def _walks_of_length(
    graph: nx.Graph,
    start: str,
    length: int,
) -> Iterable[tuple[str, ...]]:
    stack = [(start, (start,), 0)]
    while stack:
        current, walk, used = stack.pop()
        if used == length:
            yield walk
            continue
        for neighbor in sorted(graph.neighbors(current), reverse=True):
            stack.append((neighbor, walk + (neighbor,), used + 1))


def _validated_rates(
    basis: HomologyBasis,
    rates: Mapping[tuple[str, str], Fraction | int],
) -> dict[tuple[str, str], Fraction]:
    expected = {(u, v) for edge in basis.edges for u, v in (edge, edge[::-1])}
    normalized: dict[tuple[str, str], Fraction] = {}
    for edge, value in rates.items():
        if (
            not isinstance(edge, tuple)
            or len(edge) != 2
            or not all(isinstance(vertex, str) for vertex in edge)
        ):
            raise TypeError("rate keys must be directed string edge pairs")
        if isinstance(value, bool) or not isinstance(value, (Fraction, int)):
            raise TypeError("rates must be exact integers or fractions")
        converted = Fraction(value)
        if converted <= 0:
            raise ValueError("every directed support-edge rate must be positive")
        normalized[edge] = converted
    if set(normalized) != expected:
        missing = sorted(expected - set(normalized))
        extra = sorted(set(normalized) - expected)
        raise ValueError(
            f"directed rates do not match the support: missing={missing!r}, extra={extra!r}"
        )
    return normalized


def _validated_positive_fraction(value: Fraction | int, *, label: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (Fraction, int)):
        raise TypeError(f"{label} must be an exact integer or fraction")
    converted = Fraction(value)
    if converted <= 0:
        raise ValueError(f"{label} must be positive")
    return converted


def _fraction_from_sympy(value: object) -> Fraction:
    numerator, denominator = value.as_numer_denom()  # type: ignore[attr-defined]
    if not numerator.is_Integer or not denominator.is_Integer:
        raise AssertionError("stationary probabilities must be rational")
    return Fraction(int(numerator), int(denominator))


def _exact_stationary_law(
    basis: HomologyBasis,
    rates: Mapping[tuple[str, str], Fraction],
) -> ExactStationaryLaw:
    vertices = basis.vertices
    vertex_index = {vertex: index for index, vertex in enumerate(vertices)}
    generator = Matrix.zeros(len(vertices), len(vertices))
    for (start, end), rate in rates.items():
        generator[vertex_index[start], vertex_index[end]] = Rational(
            rate.numerator,
            rate.denominator,
        )
    for index in range(len(vertices)):
        generator[index, index] = -sum(
            generator[index, column] for column in range(len(vertices))
        )

    system = generator.T
    system[len(vertices) - 1, :] = Matrix([[1] * len(vertices)])
    right_hand_side = Matrix.zeros(len(vertices), 1)
    right_hand_side[len(vertices) - 1, 0] = 1
    solution, parameters = system.gauss_jordan_solve(right_hand_side)
    if parameters.rows:
        raise AssertionError("the stationary system must have a unique solution")
    probabilities = tuple(_fraction_from_sympy(value) for value in solution)
    if any(probability <= 0 for probability in probabilities):
        raise AssertionError(
            "an irreducible finite generator must have positive stationary mass"
        )
    if sum(probabilities, start=Fraction(0)) != 1:
        raise AssertionError("stationary probabilities must sum exactly to one")
    probability_row = Matrix(
        [[Rational(value.numerator, value.denominator) for value in probabilities]]
    )
    if probability_row * generator != Matrix.zeros(1, len(vertices)):
        raise AssertionError("computed stationary distribution does not annihilate Q")
    return ExactStationaryLaw(
        vertices=vertices,
        generator=ImmutableMatrix(generator),
        probabilities=probabilities,
    )


def _validated_geodesic(
    graph: nx.Graph,
    start: str,
    end: str,
    overrides: Mapping[tuple[str, str], Sequence[str]] | None,
) -> tuple[str, ...]:
    distance = nx.shortest_path_length(graph, source=start, target=end)
    if overrides is not None and (start, end) in overrides:
        walk = tuple(overrides[(start, end)])
    else:
        distance_to_end = nx.single_source_shortest_path_length(graph, end)
        current = start
        selected = [start]
        while current != end:
            current = min(
                neighbor
                for neighbor in graph.neighbors(current)
                if distance_to_end[neighbor] == distance_to_end[current] - 1
            )
            selected.append(current)
        walk = tuple(selected)
    if not walk or walk[0] != start or walk[-1] != end:
        raise ValueError("a geodesic override has the wrong endpoints")
    if len(walk) - 1 != distance:
        raise ValueError("a geodesic override is not shortest")
    if any(not graph.has_edge(tail, head) for tail, head in zip(walk, walk[1:])):
        raise ValueError("a geodesic override contains a nonedge")
    return walk


def build_critical_path_catalogue(
    analysis: FiltrationAnalysis,
    *,
    rates: Mapping[tuple[str, str], Fraction | int],
    layer: int,
    geodesics: Mapping[tuple[str, str], Sequence[str]] | None = None,
) -> CriticalPathCatalogue:
    """Enumerate all length-``m`` paths and their exact graded weights."""

    if isinstance(layer, bool) or not isinstance(layer, int):
        raise TypeError("layer must be an integer")
    if layer < 2 or layer > analysis.max_layer:
        raise ValueError("layer is outside the computed nontrivial filtration")

    previous = analysis.at(layer - 1)
    current = analysis.at(layer)
    graded_group = QuotientPresentation.create(previous.exposure, current.exposure)
    visible_group = QuotientPresentation.create(previous.visible, current.visible)
    induced_readout = InducedQuotientMap.create(
        graded_group,
        visible_group,
        analysis.readout,
    )
    exact_rates = _validated_rates(analysis.basis, rates)

    graph = nx.Graph()
    graph.add_nodes_from(analysis.basis.vertices)
    graph.add_edges_from(analysis.basis.edges)
    references: dict[tuple[str, str], tuple[str, ...]] = {}
    terms: list[CriticalPathTerm] = []
    denominator = factorial(layer)
    for start in analysis.basis.vertices:
        for walk in _walks_of_length(graph, start, layer):
            end = walk[-1]
            key = (start, end)
            if key not in references:
                references[key] = _validated_geodesic(
                    graph,
                    start,
                    end,
                    geodesics,
                )
            difference = chain_from_walk(walk, analysis.basis) - chain_from_walk(
                references[key],
                analysis.basis,
            )
            coordinates = coordinates_from_cycle_chain(difference, analysis.basis)
            label = graded_group.project_ambient(coordinates)
            rate_product = Fraction(1)
            for tail, head in zip(walk, walk[1:]):
                rate_product *= exact_rates[(tail, head)]
            terms.append(
                CriticalPathTerm(
                    walk=walk,
                    endpoint_distance=len(references[key]) - 1,
                    label=label,
                    visible_label=induced_readout.apply(label),
                    leading_weight=rate_product / denominator,
                )
            )

    return CriticalPathCatalogue(
        layer=layer,
        basis=analysis.basis,
        graded_group=graded_group,
        visible_group=visible_group,
        induced_readout=induced_readout,
        geodesics=tuple(
            GeodesicReference(start=start, end=end, walk=walk)
            for (start, end), walk in sorted(references.items())
        ),
        terms=tuple(terms),
    )


def build_marked_poisson_experiment(
    analysis: FiltrationAnalysis,
    *,
    rates: Mapping[tuple[str, str], Fraction | int],
    layer: int,
    theta: Fraction | int,
    geodesics: Mapping[tuple[str, str], Sequence[str]] | None = None,
) -> MarkedPoissonExperiment:
    """Construct exact path weights, intensities, and conditional mark laws."""

    exact_theta = _validated_positive_fraction(theta, label="theta")
    exact_rates = _validated_rates(analysis.basis, rates)
    stationary_law = _exact_stationary_law(analysis.basis, exact_rates)
    catalogue = build_critical_path_catalogue(
        analysis,
        rates=exact_rates,
        layer=layer,
        geodesics=geodesics,
    )

    levy_totals: dict[QuotientElement, Fraction] = {}
    for item in catalogue.common_endpoint_weights():
        contribution = (
            exact_theta * stationary_law.probability(item.start) * item.leading_weight
        )
        levy_totals[item.label] = (
            levy_totals.get(item.label, Fraction(0)) + contribution
        )
    common_levy_measure = tuple(
        LevyAtom(
            label=label,
            visible_label=catalogue.induced_readout.apply(label),
            intensity=levy_totals[label],
        )
        for label in sorted(levy_totals)
    )
    if any(
        atom.label == catalogue.graded_group.zero or atom.intensity <= 0
        for atom in common_levy_measure
    ):
        raise AssertionError(
            "the common-endpoint Levy measure must have positive nonzero atoms"
        )

    endpoint_weights: dict[tuple[str, str], list[AggregatedPathWeight]] = {}
    for item in catalogue.critical_endpoint_weights():
        endpoint_weights.setdefault((item.start, item.end), []).append(item)

    critical_endpoint_components: list[CriticalEndpointComponent] = []
    for start, end in sorted(endpoint_weights):
        weights = endpoint_weights[(start, end)]
        total_weight = sum(
            (item.leading_weight for item in weights),
            start=Fraction(0),
        )
        if total_weight <= 0:
            raise AssertionError(
                "a critical endpoint must have positive leading weight"
            )
        mark_law = tuple(
            ConditionalMark(
                label=item.label,
                visible_label=item.visible_label,
                probability=item.leading_weight / total_weight,
            )
            for item in weights
        )
        if (
            sum(
                (mark.probability for mark in mark_law),
                start=Fraction(0),
            )
            != 1
        ):
            raise AssertionError(
                "a conditional critical mark law must normalize exactly"
            )
        critical_endpoint_components.append(
            CriticalEndpointComponent(
                start=start,
                end=end,
                poisson_intensity=(
                    exact_theta * stationary_law.probability(start) * total_weight
                ),
                mark_law=mark_law,
            )
        )

    return MarkedPoissonExperiment(
        theta=exact_theta,
        stationary_law=stationary_law,
        catalogue=catalogue,
        common_levy_measure=common_levy_measure,
        critical_endpoint_components=tuple(critical_endpoint_components),
    )
