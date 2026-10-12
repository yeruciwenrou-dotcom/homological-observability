# Computational companion report

**Calculation checks: PASS**

**Frozen-reference comparison: PASS**

The calculation reproduces the finite-cycle bridge posteriors, critical count
limits, the Poisson-averaged binomial MAP identity, and the reciprocal-lattice
peak mechanism presented in the paper.

## What the calculations explain

A particle observed at discrete times can follow different routes between the
same two recorded states. On a symmetric triangle, a rare two-jump route can
hide one winding behind an ordinary neighboring-state transition. On a
symmetric four-cycle, opposite-vertex snapshots reveal a rare crossing
opportunity, but its two shortest routes remain equally likely. Both mechanisms
have the cumulative scale $T\delta$, yet the observer retains different
information in the two experiments.

For the four-cycle, the number of opposite-vertex windows is visible in the
record. The critical posterior conditions on that count before assessing the
unknown route marks. The Poisson-averaged binomial MAP identity then gives the
optimal mean success probability for this limiting cycle-history decision.
These examples separate the location of a sampling threshold from the
decision problem that survives at the threshold.

## Critical finite-cycle kernels

Refining the observation grid from 25 to 6,400 windows
gives the following diagnostics at $\theta=T\delta=1$. Observation time grows
along this sequence while the sampling interval shrinks; rates set the time
unit.

| diagnostic | coarse grid | finest grid |
| --- | ---: | ---: |
| C3 leading-count TV upper bound | 0.139006 | 0.00916801 |
| C4 visible-count TV upper bound | 0.134346 | 0.00914885 |
| C3 mean per winding direction | 0.33516 | 0.487655 |
| C4 mean visible count | 0.679305 | 0.975361 |

The C3 and C4 count laws move toward their critical Poisson limits as temporal
resolution is refined. The local C3 bridge approximation improves along this
refinement sequence, while the two C4 diametric routes retain equal conditional
weight.

The TV bounds measure errors in the count-law approximations. Their decrease
validates the limiting description; it does not mean that history-recovery
error vanishes at this fixed critical intensity.

## Exact and asymptotic checks

- The direct Poisson mixture and Bessel expression for the critical MAP value
  agree to a maximum absolute error of **7.22e-16** over the displayed
  parameter values.
- The C3, C4, C5, and C6 finite-cycle comparisons all show decreasing absolute
  error as $\delta$ is reduced from 0.2 to 0.025.
- At the largest lattice size, the local Gaussian error is
  **0.797822** without parity-breaking increments and
  **0.00127473** with the subleading auxiliary increments.

The final comparison isolates an integer effect. A distribution confined to
one parity class can look broad while still defeating a local Gaussian
approximation on the full lattice. Rarer increments that connect the parity
classes remove this obstruction when enough of them accumulate. Integer
structure can therefore matter even when the broad variance scale looks
similar. This is a mechanism check, separate from the finite-ring experiments.

The committed CSV tables are the numerical reference layer. The general
theorems and their assumptions are established analytically in the paper.
