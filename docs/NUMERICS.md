# Numerical methods and reference calibration

The finite-cycle diagnostics evaluate probabilities numerically, alongside
the exact integer and rational calculations used for graph and critical-limit
analysis. This note explains their count-TV intervals, small-window bridge
evaluation, and reference-table correction.

## Count-TV intervals

For the C3 leading counts $(A,B)$, the finite law is multinomial with
per-direction probability $q$. Its total has law $\mathrm{Bin}(N,2q)$.
The limiting counts are independent $\mathrm{Pois}(\lambda)$ variables,
whose total has law $\mathrm{Pois}(2\lambda)$. Conditional on total $k$,
both vectors have the same $\mathrm{Bin}(k,1/2)$ split. Summing absolute
differences on the disjoint total-count supports gives

$$
\mathrm{TV}\bigl((A,B),(A_\infty,B_\infty)\bigr)
=\mathrm{TV}\bigl(\mathrm{Bin}(N,2q),\mathrm{Pois}(2\lambda)\bigr).
$$

`tv_c3_count_vector` evaluates this one-dimensional distance through total
count `2*cutoff`. `tv_c4_visible_count` evaluates its scalar count distance
through `cutoff`. Both retain the public `(lower, upper)` return type.

The implementation starts with the zero-count probabilities and advances by
positive PMF recurrences. It uses 60-digit decimal arithmetic with separate
downward and upward rounding contexts. The binomial zero-count probability
uses integer exponentiation by repeated multiplication. The Poisson zero-count
probability uses the correctly rounded exponential, bracketed by its adjacent
decimal values. These operations use the rounding guarantees of Python's
[`decimal` module](https://docs.python.org/3/library/decimal.html#decimal.Decimal.exp).

Each absolute difference is enclosed before summation. Half the accumulated
lower sum is a TV lower bound; the upper bound adds half the upper bound on
the two omitted probability masses. Finally, conversion to binary float is
rounded outward. Input probabilities and means are interpreted as their exact
binary values. The intervals cover arithmetic and truncation error for these
count laws; uncertainty in an estimated input probability is a separate input
problem. A short cutoff or very large parameters can produce a broad interval.

The independent tests use 100-digit closed-form PMFs and an exact-rational
finite multinomial law. They cover large $N$, the displayed refinement
sequence, short cutoffs and degenerate probabilities. From the
[development environment](../CONTRIBUTING.md#development-environment), run:

```console
$ .venv/bin/python -m unittest tests.test_numerical_boundaries -v
```

## Reference calibration

The four TV columns in
[`critical_kernel_results.csv`](../results/critical_kernel_results.csv)
and its packaged copy use the rounding-aware intervals above. For the default
C3 sequence, the distances at $N=1600$ and $6400$ are approximately
0.01827715650931175 and 0.00916800996239429.

Earlier evaluations omitted arithmetic error from the interval. This matters
at large counts: for $N=10^9$, $q=0.5/N$, and $\lambda=0.5$, the corrected
distance is approximately $2.76\times10^{-10}$. Independent high-precision
checks support the recalibrated C3 and C4 columns. All other reference columns,
the selected-appendix table, and the comparison tolerances
`rtol=1e-12`, `atol=1e-14` are unchanged.

## Rare-endpoint bridges

For small windows, the bridge evaluator factors
$I_k(2\delta)=\delta^k S_k(\delta^2)/k!$ and divides all weights by the
smallest displacement's weight before summation. The rare-endpoint scale
therefore cancels before it can underflow. For example, either leading
diametric C4 route has conditional probability close to $1/2$ even when its
unconditional endpoint probability is too small for float representation.
The positive series is used for $0<\delta\leq1$. In this interval its
successive terms have ratio $\delta^2/[j(k+j)]$, and the bounded series
converges rapidly. Endpoint evaluation stores the common scale as a binary
mantissa and exponent until the final conversion. Thus a representable
subnormal endpoint mass, such as `residue_probability(4, 2, 1e-160)`, remains
nonzero. Both generic and specialized endpoint APIs raise `ValueError` if
the positive result rounds to zero; the corresponding bridge can still exist.

For $\delta>1$, evaluation retains the exponentially scaled general-order
Bessel functions. This branch requires a resolvable nonzero endpoint sum.
It does not cover every large-ring rare endpoint: for example, the diametric
1000-ring bridge is supported at $\delta=1$ but explicitly rejected just
above it. The 1000-ring values at $\delta=1/4$, $0.3$, and $1$ agree with
independent high-precision ratios.
A conditional result outside the nonzero float range raises `ValueError`.
The winding sum retains the supplied cutoff (expanded by the existing
scale heuristic); these floating evaluations are not certified intervals for
all truncation and rounding errors.

Endpoint representatives are reduced modulo `n`. For bridge probabilities,
the winding coordinate is adjusted at the same time to preserve the lifted
displacement `residue + n*winding`. Equivalent representations therefore use
the same calculation, including very large positive or negative representatives.

The generic floating cycle APIs support `3 <= n <= 1000000` and at most
100001 winding terms (an effective cutoff of 50000). The effective cutoff
includes the scale heuristic, so requesting a smaller cutoff cannot bypass
the budget. An oversized request or an unrepresentable Bessel argument or
order raises `ValueError` before a long summation. These limits apply to
`residue_probability` and `ring_bridge_probability`; exact graph and critical
analysis use their own documented resource controls. The closed-form C4
endpoint evaluator remains available at every positive finite window whose
probability is representable.

## Poisson-averaged MAP

`poisson_averaged_binomial_map_bessel` uses the specialized scaled functions
[`i0e`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.i0e.html)
and [`i1e`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.i1e.html)
for $e^{-\lambda}[I_0(\lambda)+I_1(\lambda)]$. The general-order evaluator
can return an unresolved value at large finite arguments. The specialized
route is checked against independent high-precision evaluation from zero to
the largest finite binary float, and its output must be finite and in $(0,1]$.

## Sampling and exact resource values

Phase labels preserve explicit rational alpha values; numeric inputs retain
their exact binary value. Classification uses the sign of
$1-(m-1)\alpha$. Finite-scale exposure rounds only after evaluating
$T\delta^{m-1}$ on those exact inputs. See the
[sampling contract](MODEL_GUIDE.md#analysis-settings) for range errors and
non-dyadic thresholds.

Critical experiments count all published scientific integers and rationals,
including readouts, induced maps, marks, group orders, counts and total
intensities, against the exact digit ceiling. Resource limits and provenance
metadata are excluded. Exceeding the ceiling preserves the atomic
`LIMIT_REACHED` result contract. Digit counting uses bit lengths followed by
exact power-of-ten comparisons, without first formatting the integer.

Public exact records also have a decimal representation boundary, separate
from computational budgets: at most 4300 digits per integer, or the active
Python integer-string limit when lower. Model construction rejects values
outside that boundary, and `max_integer_digits` cannot exceed it. Decimal
inputs are checked before expanding extreme powers of ten; rational strings
must have bounded numerator and denominator text. Python's global conversion
limit is never changed. With the default interpreter setting, `theta="1e4100"`
returns a serializable `LIMIT_REACHED` result under the default 4096-digit
budget; `theta="1e5000"` is an input error (CLI exit 2). This keeps full exact
model text and its hash available for every accepted input, including limited
results. No truncated identifier stands in for the original model.
