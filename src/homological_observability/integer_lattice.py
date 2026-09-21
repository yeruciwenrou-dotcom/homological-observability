"""Exact integer-lattice operations used by homological filtrations."""

from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Sequence

from sympy import ZZ, ImmutableMatrix, Matrix, eye
from sympy.matrices.matrixbase import MatrixBase
from sympy.matrices.normalforms import (
    hermite_normal_form,
    smith_normal_decomp,
    smith_normal_form,
)


def _require_integer_matrix(matrix: MatrixBase, *, label: str) -> None:
    if any(not entry.is_Integer for entry in matrix):
        raise TypeError(f"{label} requires an integer matrix")


def _freeze(matrix: MatrixBase) -> ImmutableMatrix:
    return ImmutableMatrix(matrix)


@dataclass(frozen=True)
class QuotientInvariants:
    """Invariant-factor summary of a finitely generated abelian quotient."""

    free_rank: int
    torsion_factors: tuple[int, ...]

    @property
    def is_trivial(self) -> bool:
        return self.free_rank == 0 and not self.torsion_factors

    @property
    def finite_order(self) -> int | None:
        if self.free_rank:
            return None
        return prod(self.torsion_factors, start=1)


def zero_lattice(ambient_rank: int) -> ImmutableMatrix:
    if isinstance(ambient_rank, bool) or not isinstance(ambient_rank, int):
        raise TypeError("ambient_rank must be an integer")
    if ambient_rank < 0:
        raise ValueError("ambient_rank must be nonnegative")
    return ImmutableMatrix.zeros(ambient_rank, 0)


def column_lattice(
    generators: Sequence[MatrixBase], ambient_rank: int
) -> ImmutableMatrix:
    """Return a deterministic HNF basis for an integer column lattice."""

    if isinstance(ambient_rank, bool) or not isinstance(ambient_rank, int):
        raise TypeError("ambient_rank must be an integer")
    if ambient_rank < 0:
        raise ValueError("ambient_rank must be nonnegative")
    if not generators:
        return zero_lattice(ambient_rank)
    if any(generator.shape != (ambient_rank, 1) for generator in generators):
        raise ValueError("lattice generators have inconsistent dimensions")
    if ambient_rank == 0:
        return zero_lattice(ambient_rank)
    matrix = Matrix(
        ambient_rank,
        len(generators),
        [generator[row, 0] for row in range(ambient_rank) for generator in generators],
    )
    _require_integer_matrix(matrix, label="column_lattice")
    return _freeze(hermite_normal_form(matrix))


def integer_kernel(matrix: MatrixBase) -> ImmutableMatrix:
    """Return a saturated integer basis of a homomorphism kernel."""

    _require_integer_matrix(matrix, label="integer_kernel")
    mutable = Matrix(matrix)
    diagonal, left, right = smith_normal_decomp(mutable, domain=ZZ)
    if diagonal != left * mutable * right:
        raise AssertionError("invalid Smith decomposition")
    if abs(int(left.det())) != 1 or abs(int(right.det())) != 1:
        raise AssertionError("Smith transformations must be unimodular")
    rank = sum(diagonal[index, index] != 0 for index in range(min(diagonal.shape)))
    kernel = right[:, rank:]
    if mutable * kernel != Matrix.zeros(mutable.rows, kernel.cols):
        raise AssertionError("Smith kernel failed exact verification")
    return _freeze(kernel)


def hidden_lattice(lattice: MatrixBase, readout: MatrixBase) -> ImmutableMatrix:
    """Compute ``lattice intersect ker_Z(readout)`` exactly."""

    _require_integer_matrix(lattice, label="hidden_lattice")
    _require_integer_matrix(readout, label="hidden_lattice")
    if lattice.rows != readout.cols:
        raise ValueError("readout and lattice use different homology coordinates")
    if lattice.cols == 0:
        return zero_lattice(lattice.rows)
    kernel = integer_kernel(readout * lattice)
    hidden = hermite_normal_form(Matrix(lattice * kernel))
    if readout * hidden != Matrix.zeros(readout.rows, hidden.cols):
        raise AssertionError("hidden lattice is not in the readout kernel")
    return _freeze(hidden)


def image_lattice(lattice: MatrixBase, readout: MatrixBase) -> ImmutableMatrix:
    """Compute the exact image lattice of a readout."""

    _require_integer_matrix(lattice, label="image_lattice")
    _require_integer_matrix(readout, label="image_lattice")
    if lattice.rows != readout.cols:
        raise ValueError("readout and lattice use different homology coordinates")
    if readout.rows == 0 or lattice.cols == 0:
        return zero_lattice(readout.rows)
    return _freeze(hermite_normal_form(Matrix(readout * lattice)))


def inclusion_coordinates(
    sub: MatrixBase, super_lattice: MatrixBase
) -> ImmutableMatrix:
    """Express a sublattice basis in a containing lattice basis."""

    _require_integer_matrix(sub, label="inclusion_coordinates")
    _require_integer_matrix(super_lattice, label="inclusion_coordinates")
    if sub.rows != super_lattice.rows:
        raise ValueError("lattices must share an ambient group")
    if sub.cols == 0:
        return ImmutableMatrix.zeros(super_lattice.cols, 0)
    if super_lattice.cols == 0:
        raise ValueError("a nonzero lattice cannot lie in the zero lattice")
    mutable_super = Matrix(super_lattice)
    mutable_sub = Matrix(sub)
    try:
        coordinates, parameters = mutable_super.gauss_jordan_solve(mutable_sub)
    except ValueError as error:
        raise ValueError("the first lattice is not contained in the second") from error
    if parameters.rows:
        raise AssertionError("a lattice basis must have unique inclusion coordinates")
    if mutable_super * coordinates != mutable_sub:
        raise ValueError("the first lattice is not contained in the second")
    if any(not entry.is_Integer for entry in coordinates):
        raise ValueError("lattice inclusion coordinates were not integral")
    return _freeze(coordinates)


def quotient_invariants(
    sub: MatrixBase, super_lattice: MatrixBase
) -> QuotientInvariants:
    """Return the invariant factors of ``super_lattice / sub``."""

    coordinates = inclusion_coordinates(sub, super_lattice)
    if coordinates.cols == 0:
        return QuotientInvariants(
            free_rank=super_lattice.cols,
            torsion_factors=(),
        )
    diagonal = smith_normal_form(Matrix(coordinates), domain=ZZ)
    factors = tuple(
        abs(int(diagonal[index, index]))
        for index in range(min(diagonal.shape))
        if diagonal[index, index] != 0
    )
    if len(factors) != sub.cols:
        raise AssertionError("a lattice inclusion must have full column rank")
    return QuotientInvariants(
        free_rank=super_lattice.cols - sub.cols,
        torsion_factors=tuple(factor for factor in factors if factor > 1),
    )


def lattice_signature(
    lattice: MatrixBase, ambient_rank: int
) -> tuple[int, QuotientInvariants]:
    """Summarize a lattice by rank and its ambient quotient."""

    ambient = ImmutableMatrix(eye(ambient_rank))
    return lattice.cols, quotient_invariants(lattice, ambient)
