"""Exact-integer regression tests for the general research kernel."""

from __future__ import annotations

import unittest
from itertools import product

from sympy import ImmutableMatrix, Matrix, eye

from homological_observability.integer_lattice import (
    QuotientInvariants,
    hidden_lattice,
    integer_kernel,
    quotient_invariants,
)


class ExactIntegerBackendTests(unittest.TestCase):
    def test_small_integer_matrix_catalog_has_saturated_kernels(self) -> None:
        checked = 0
        for rows, columns in ((1, 3), (2, 2)):
            for entries in product(range(-2, 3), repeat=rows * columns):
                matrix = Matrix(rows, columns, entries)
                kernel = integer_kernel(matrix)
                self.assertEqual(kernel.cols, columns - matrix.rank())
                self.assertEqual(
                    quotient_invariants(
                        kernel, ImmutableMatrix(eye(columns))
                    ).torsion_factors,
                    (),
                )
                checked += 1
        self.assertEqual(checked, 750)

    def test_smith_decomposition_gives_a_saturated_integer_kernel(self) -> None:
        matrix = Matrix([[2, 4, 6], [0, 2, 2]])
        kernel = integer_kernel(matrix)
        self.assertEqual(matrix * kernel, Matrix.zeros(2, kernel.cols))
        self.assertEqual(kernel.cols, 1)
        self.assertEqual(
            quotient_invariants(kernel, ImmutableMatrix(eye(3))),
            QuotientInvariants(free_rank=2, torsion_factors=()),
        )

    def test_quotient_retains_finite_index(self) -> None:
        sub = ImmutableMatrix([[2, 0], [0, 1]])
        super_lattice = ImmutableMatrix(eye(2))
        invariants = quotient_invariants(sub, super_lattice)
        self.assertEqual(invariants.free_rank, 0)
        self.assertEqual(invariants.torsion_factors, (2,))
        self.assertEqual(invariants.finite_order, 2)

    def test_hidden_lattice_uses_integer_not_rational_kernel(self) -> None:
        lattice = ImmutableMatrix(eye(3))
        readout = ImmutableMatrix([[2, 4, 6]])
        hidden = hidden_lattice(lattice, readout)
        self.assertEqual(readout * hidden, Matrix.zeros(1, 2))
        self.assertEqual(hidden.cols, 2)
        self.assertEqual(
            quotient_invariants(hidden, lattice),
            QuotientInvariants(free_rank=1, torsion_factors=()),
        )

    def test_noninteger_matrices_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            integer_kernel(Matrix([[0.5, 1]]))

    def test_degenerate_integer_kernels_have_exact_shapes(self) -> None:
        for rows, columns in ((0, 0), (0, 3), (3, 0), (3, 2), (2, 3)):
            with self.subTest(rows=rows, columns=columns):
                matrix = Matrix.zeros(rows, columns)
                kernel = integer_kernel(matrix)
                self.assertEqual(kernel.shape, (columns, columns))
                self.assertEqual(
                    matrix * kernel,
                    Matrix.zeros(rows, columns),
                )


if __name__ == "__main__":
    unittest.main()
