"""Finite-time Markov bridges on the actual integer joint image.

The zero-frequency endpoint kernels normalize each window. Multiplying their
characteristic functions composes the complete record before any conditioning
on a cumulative count. All caches belong to one model, basis and time step.
"""

from __future__ import annotations

import math
import warnings
from collections import Counter

import numpy as np
from scipy.linalg import expm


class Unresolved(Exception):
    def __init__(self, reason, status="NUMERICALLY_UNRESOLVED"):
        self.reason = reason
        self.status = status


def matrix_exp(a):
    try:
        with (
            warnings.catch_warnings(),
            np.errstate(over="ignore", invalid="ignore", under="ignore"),
        ):
            warnings.simplefilter("ignore", RuntimeWarning)
            out = expm(a)
    except (ArithmeticError, ValueError, np.linalg.LinAlgError) as error:
        raise Unresolved("matrix_exponential_failed") from error
    if not np.isfinite(out).all():
        raise Unresolved("nonfinite_matrix_exponential")
    return out


class FourierBridge:
    def __init__(self, lattice, q, dt, limits):
        self.lattice = lattice
        self.limits = limits
        self.vertex_index = {v: i for i, v in enumerate(lattice.basis.vertices)}
        self.rank = lattice.image.cols
        self.chords = [
            (
                self.vertex_index[u],
                self.vertex_index[v],
                tuple(int(x) for x in lattice.coordinates[:, j]),
            )
            for j, (u, v) in enumerate(lattice.basis.chord_edges)
        ]
        self.max_steps = [
            max(abs(k[d]) for _, _, k in self.chords) for d in range(self.rank)
        ]
        self.load = float(-q.diagonal().min()) * dt
        if not math.isfinite(self.load) or self.load > 1e6:
            raise Unresolved("stiff_window_exceeds_numerical_range")
        self.generator = q * dt
        self.transition = matrix_exp(self.generator)
        self.row_error = float(np.abs(self.transition.sum(axis=1) - 1).max())
        self.tilted = []
        # Chernoff control per coordinate. Integer jumps are scaled by their
        # largest magnitude before taking the real exponential.
        for axis, maximum in enumerate(self.max_steps):
            kernels = []
            for sign in (-1, 1):
                a = self.generator.copy()
                for i, j, steps in self.chords:
                    angle = sign * 2.0 * (steps[axis] / maximum)
                    a[i, j] *= math.exp(angle)
                    a[j, i] *= math.exp(-angle)
                kernels.append(matrix_exp(a))
            self.tilted.append(kernels)
        self.cached_shape = None
        self.cached_kernels = None

    def _grid(self, shape):
        if self.cached_shape == shape:
            return self.cached_kernels
        points = math.prod(shape)
        n = len(self.transition)
        if points > self.limits.max_grid_points or points * n * n > min(
            self.limits.max_matrix_entries,
            np.iinfo(np.intp).max // np.dtype(complex).itemsize,
        ):
            raise Unresolved("fourier_grid_budget", "LIMIT_REACHED")
        self.cached_kernels = None
        self.cached_shape = None
        out = np.empty((points, n, n), dtype=complex)
        for start in range(0, points, 128):
            stop = min(start + 128, points)
            coords = np.unravel_index(np.arange(start, stop), shape)
            a = np.broadcast_to(self.generator, (stop - start, n, n)).astype(complex)
            for i, j, steps in self.chords:
                turns = sum(
                    ((steps[d] % count) * coords[d] % count) / count
                    for d, count in enumerate(shape)
                )
                phase = np.exp((2j * math.pi) * turns)
                a[:, i, j] *= phase
                a[:, j, i] *= phase.conj()
            out[start:stop] = matrix_exp(a)
        self.cached_kernels = out
        self.cached_shape = shape
        return out

    def solve(self, states, support, diagnostics):
        order = [self.vertex_index[s] for s in states]
        pairs = Counter(zip(order, order[1:]))
        if any(self.transition[i, j] <= 0 for i, j in pairs):
            raise Unresolved("snapshot_endpoint_mass_unresolved")
        log_snapshot = math.fsum(
            n * math.log(self.transition[i, j]) for (i, j), n in pairs.items()
        )
        log_snapshot = min(0.0, log_snapshot)
        diagnostics.update(
            log_snapshot_probability=log_snapshot,
            transition_row_residual=self.row_error,
        )
        # Nonnegative real-tilted kernels give conditional exponential moments.
        log_moments = []
        for kernels in self.tilted:
            if any(mat[i, j] <= 0 for mat in kernels for i, j in pairs):
                raise Unresolved("tilted_endpoint_mass_unresolved")
            log_moments.append(
                [
                    math.fsum(n * math.log(mat[i, j]) for (i, j), n in pairs.items())
                    - log_snapshot
                    for mat in kernels
                ]
            )
        eps = np.finfo(float).eps
        with np.errstate(over="ignore", divide="ignore"):
            inverse_endpoints = sum(
                n / float(self.transition[i, j]) for (i, j), n in pairs.items()
            )
        roundoff = (
            16 * eps * len(self.transition) * (1 + self.load) + self.row_error
        ) * inverse_endpoints
        if not math.isfinite(roundoff) or roundoff >= self.limits.tolerance:
            raise Unresolved("snapshot_conditioning_below_precision")
        desired_tail = min(self.limits.tolerance / 32, 1e-10)
        while True:
            shape = []
            for maximum, logs in zip(self.max_steps, log_moments):
                # Compare against the budget before converting a potentially
                # very large integer step to a binary float or creating arrays.
                radius_units = max(
                    1.0, (max(logs) + math.log(2 * self.rank / desired_tail)) / 2
                )
                numerator, denominator = radius_units.as_integer_ratio()
                radius = (maximum * numerator + denominator - 1) // denominator
                if radius > min(
                    self.limits.max_grid_points, self.limits.max_matrix_entries
                ):
                    raise Unresolved("fourier_grid_budget", "LIMIT_REACHED")
                shape.append(max(8, 1 << (2 * radius - 1).bit_length()))
            shape = tuple(shape)
            tail = sum(
                math.exp(min(0, log - 2 * (width // 2) / maximum))
                for maximum, logs, width in zip(self.max_steps, log_moments, shape)
                for log in logs
            )
            diagnostics.update(
                grid_shape=list(shape), wrap_tail_given_snapshots=min(1.0, tail)
            )
            kernels = self._grid(shape)
            cf = np.ones(kernels.shape[0], dtype=complex)
            characteristic_excess = 0.0
            for (i, j), n in pairs.items():
                bridge = kernels[:, i, j] / self.transition[i, j]
                excess = float(np.max(np.abs(bridge))) - 1
                characteristic_excess += n * max(0.0, excess)
                if characteristic_excess >= self.limits.tolerance:
                    raise Unresolved("bridge_characteristic_precision")
                cf *= bridge**n
            raw = np.fft.fftn(cf.reshape(shape)) / cf.size
            mass = raw.real
            negative = float(-np.minimum(mass, 0).sum())
            imaginary = float(np.abs(raw.imag).sum())
            clipped = np.maximum(mass, 0)
            total = float(clipped.sum())
            if not math.isfinite(total) or total <= 0 or not math.isfinite(imaginary):
                raise Unresolved("nonfinite_probability_mass")
            correction = abs(1 - total)
            error = roundoff + negative + imaginary + correction + characteristic_excess
            diagnostics.update(
                raw_negative_mass=negative,
                imaginary_l1=imaginary,
                normalization_correction=correction,
                roundoff_indicator=float(roundoff),
                characteristic_excess=characteristic_excess,
            )
            target, weights = self._fiber(shape, clipped / total, support)
            denominator = float(weights.sum())
            diagnostics["count_probability_given_snapshots"] = denominator
            if denominator <= 0 or error >= self.limits.tolerance * denominator / 4:
                raise Unresolved("cumulative_count_below_precision")
            if tail > self.limits.tolerance * denominator / 4:
                desired_tail = self.limits.tolerance * denominator / 16
                continue
            diagnostics.update(
                log_record_probability=log_snapshot + math.log(min(1.0, denominator)),
                conditional_error_indicator=min(1.0, 2 * (tail + error) / denominator),
            )
            return sorted(
                (int(z), float(p / denominator))
                for z, p in zip(target, weights)
                if p > 0
            )

    def _fiber(self, shape, mass, support):
        # Map centered torus representatives back through the exact HNF image,
        # retaining nonprimitive readouts and the raw endpoint convention.
        axes = [np.arange(n, dtype=np.int64) for n in shape]
        for values in axes:
            values[len(values) // 2 :] -= len(values)
        mesh = np.meshgrid(*axes, indexing="ij", sparse=True)
        image = self.lattice.image
        mask = np.ones(shape, dtype=bool)
        for row in range(image.rows):
            coeffs = [int(x) for x in image[row, :]]
            offset = support["endpoint_offset"][row] if row == 0 else 0
            bound = abs(offset) + sum(abs(c) * n for c, n in zip(coeffs, shape))
            coords = mesh if bound < 2**62 else [x.astype(object) for x in mesh]
            component = offset + sum(c * x for c, x in zip(coeffs, coords))
            if row == 0:
                target = np.broadcast_to(component, shape)
            else:
                observed = support["corrected_counts"][row - 1]
                if abs(observed) > bound:
                    mask.fill(False)
                    break
                mask &= component == observed
        return target[mask], mass[mask]
