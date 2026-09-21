# Computational companion report

**Run status: PASS**

The calculation reproduces the finite-cycle bridge posteriors, critical count
limits, the Poisson-averaged binomial MAP identity, and the reciprocal-lattice
peak mechanism presented in the paper.

## Critical finite-cycle kernels

Refining the observation grid from 25 to 6,400 windows
gives the following diagnostics at $\theta=1$:

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

## Exact and asymptotic checks

- The direct Poisson mixture and Bessel expression for the critical MAP value
  agree to a maximum absolute error of **7.22e-16** over the displayed
  parameter values.
- The C3, C4, C5, and C6 finite-cycle comparisons all show decreasing absolute
  error as $\delta$ is reduced from 0.2 to 0.025.
- At the largest lattice size, the local Gaussian error is
  **0.797822** without parity-breaking increments and
  **0.00127473** with the subleading auxiliary increments.

The committed CSV tables are the numerical reference layer. The general
theorems and their assumptions are established analytically in the paper.
