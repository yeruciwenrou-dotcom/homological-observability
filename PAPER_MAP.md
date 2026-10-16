# Paper map and evidence

This repository provides the companion code for
*[Stochastic Histories at Finite Temporal Resolution: Homological Observability and Information Phase Diagrams in Markov Jump Processes](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes)*, available on alphaXiv and
[archived on Zenodo](https://doi.org/10.5281/zenodo.23424849).
See the [citation information](README.md#citation-and-license) for the
paper and archived software release.

This guide connects the paper's mathematical objects to their implementation
and reproducible evidence. Entries are organized by scientific object.

The physical target is the accumulated integer cycle history of a particular
run observed through vertex snapshots and optional counters. The filtration
determines which history differences can appear at each short-time order;
the critical experiment determines their limiting weights and what remains
after the available observations. For a reader's introduction, start with
[physical interpretation and scope](docs/SCIENTIFIC_SCOPE.md). This page
provides the implementation and evidence trail behind those interpretations.

## Integer homology and filtrations

| Paper object | Computation | Implementation |
| --- | --- | --- |
| Integral homology $\Lambda=H_1(G;\mathbb Z)$ | Ordered spanning tree and fundamental cycles | [homology.py](src/homological_observability/homology.py) |
| Exposure lattice $L_m$ | Simple cycles of length at most $2m$, followed by integer column HNF | [filtration.py](src/homological_observability/filtration.py) |
| Integer side readout $\pi$ | Edge cochains restricted to cycle coordinates | [model.py](src/homological_observability/model.py), [homology.py](src/homological_observability/homology.py) |
| Visible image $\pi(L_m)$ | Exact integer image | [integer_lattice.py](src/homological_observability/integer_lattice.py) |
| Hidden lattice $K_m=L_m\cap\ker\pi$ | Saturated integer kernel and lattice image | [integer_lattice.py](src/homological_observability/integer_lattice.py) |
| Successive graded quotients | Inclusion coordinates and Smith normal form | [integer_lattice.py](src/homological_observability/integer_lattice.py) |
| Phase and entropy laws | Apply the paper's exponents and hidden-rank formulas | [phase.py](src/homological_observability/phase.py) |
| Completeness | Distinguish a completed horizon, full lattice saturation, and exhausted resources | [analysis.py](src/homological_observability/analysis.py) |

The [wedge C3–C5 example](docs/END_TO_END_EXAMPLE.md) exhibits staged exposure,
a visible $\mathbb Z/2\mathbb Z$ quotient, and a hidden free direction. Its
[JSON result](examples/wedge_c3_c5_result.json) records every lattice and graded
quotient. These exact integer calculations retain finite-index effects that
real-rank calculations would lose. Coordinate matrices depend on the chosen
basis; ranks and quotient invariants do not.

Independent checks include:

- [Path-pair definitions and basis invariance](tests/test_filtration.py),
  including both chorded C6 models and a pure-torsion graph.
- [Integer-kernel and quotient tests](tests/test_integer_lattice.py), including
  cases where a rational nullspace basis is insufficient.
- [All 996 connected graph-atlas models](tests/validate_graph_atlas.py), with
  independent path-pair and readout comparisons.
- [Phase laws and sampling boundaries](tests/test_phase.py), together with
  [horizon, resource, and CLI checks](tests/test_product_contract.py).

The Appendix F.4 C6 uses the diametric chord {0,3}: both independent directions
appear in $L_2$. The separate chord {0,2} example has ranks 1 and 2 at layers 2
and 3. The tests identify these as `chorded_c6_diametric` and
`chorded_c6_distance_two`, respectively.

## Rate-dependent critical experiment

| Paper object | Computation | Implementation |
| --- | --- | --- |
| Known generator and stationary law | Positive exact rates in both directions; solve $pQ=0$ over the rationals | [critical_experiment.py](src/homological_observability/critical_experiment.py) |
| Critical marks | Enumerate walks of length $m$, subtract an endpoint reference geodesic, and project to $L_m/L_{m-1}$ | [_critical_catalogue.py](src/homological_observability/_critical_catalogue.py) |
| Induced readout | Map critical marks to the visible quotient using constructive Smith coordinates | [_critical_catalogue.py](src/homological_observability/_critical_catalogue.py) |
| Marked-Poisson limit | Combine stationary masses and path weights under $T\delta^{m-1}\to\theta$ | [_critical_catalogue.py](src/homological_observability/_critical_catalogue.py) |
| Resource completeness | Check path, digit, cycle, and output limits before returning a complete experiment | [critical_experiment.py](src/homological_observability/critical_experiment.py) |

The [biased C4 guide](docs/CRITICAL_EXPERIMENT.md) derives the conditional
probabilities $4/5$ and $1/5$ and total critical intensity $5/2$ from exact
rates. The complete [generated result](examples/biased_c4_critical_result.json)
contains the stationary law, quotient groups, catalogue, and limit experiment.

[Catalogue tests](tests/test_critical_catalogue.py) compare C3–C5 closed forms,
nonreversible weights, repeated-vertex walks, zero marks, torsion, and changes
of reference geodesic. [Public-interface tests](tests/test_critical_product_contract.py)
check exact parsing, serialization, API/CLI agreement, and atomic resource
limits. The output is a critical-limit generative specification; it is not an
exact posterior at finite $(T,\delta)$ or an unconditional critical MAP solver.

## Inputs, outputs, and reproducibility

| Interface | Definition | Checks |
| --- | --- | --- |
| Models and results | [Model guide](docs/MODEL_GUIDE.md), [output contract](docs/OUTPUT_CONTRACT.md), and [bundled schemas](src/homological_observability/schemas) | [Schema validation](tests/validate_schema.py), [model tests](tests/test_model_io.py), and topology/critical interface tests |
| Public Python API and CLI | [Package exports](src/homological_observability/__init__.py), [CLI](src/homological_observability/cli.py) | Equality of the structured API and CLI results |
| Built-in examples | [Example registry](src/homological_observability/examples.py) | [Frozen example checks](tools/freeze_examples.py) and installed-package checks |
| Probability and input boundaries | [Numerical methods](docs/NUMERICS.md) | [High-precision interval tests](tests/test_numerical_boundaries.py) and [extreme-input regressions](tests/test_extreme_inputs.py) |
| Installation and reproduction | [Reproduction API](src/homological_observability/reproduction.py) | [Wheel and sdist checks outside the checkout](tests/validate_distribution.py) |
| Documentation | [README](README.md) and the linked guides | [Executable examples and local-link checks](tests/test_documentation.py) |

JSON Schema checks structure; runtime validation also checks connectivity,
edge and readout semantics, and exact-value limits. Built-in examples are
versioned demonstrations. The frozen tables below are the numerical reference
for paper reproduction.

## Frozen finite-cycle evidence

| Calculation | Implementation and independent check | Reference |
| --- | --- | --- |
| Finite-cycle endpoint and bridge probabilities | [cycles.py](src/homological_observability/cycles.py); [finite-state matrix comparison](tests/test_cycles.py) | [Selected appendix checks](results/selected_appendix_checks.csv) |
| Winding-sector posterior | [explore_cycles.py](explore_cycles.py); lifted-chain comparison | Reader-selected terminal table |
| Small-window C3–C6 asymptotics | [reference_appendix.py](src/homological_observability/reference_appendix.py); refinement checks | [Selected appendix checks](results/selected_appendix_checks.csv) |
| C3/C4 critical count kernels | [critical.py](src/homological_observability/critical.py); independent count laws | [Critical-kernel table](results/critical_kernel_results.csv) |
| Poisson-averaged binomial MAP identity | [critical.py](src/homological_observability/critical.py); direct mixture and high-precision Bessel comparisons | MAP rows in the appendix table |
| Reciprocal-lattice peak suppression | [lattice.py](src/homological_observability/lattice.py); positivity, ordering, and refinement checks | Lattice rows in the appendix table and [summary figure](results/companion_summary.png) |
| Combined reproduction | [reporting.py](src/homological_observability/reporting.py) and [reproduction.py](src/homological_observability/reproduction.py) | [Report](results/REPORT.md) and PNG/SVG figures |

`python quickstart.py` runs the reader-side tests and regenerates these
calculations. Numerical comparison uses the documented tolerances and leaves
the committed references unchanged.

## Evidence boundary

Enumeration and graph-atlas checks support the implementation; they do not
replace proofs for arbitrary finite graphs. The critical task assumes a known
exact generator. The frozen cycle examples establish neither a universal
finite-sample error bound nor extensions to one-way support, multigraphs,
noisy observations, or unknown models. General theorem statements,
hypotheses, and proofs remain in the manuscript.
