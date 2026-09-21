# Scientific scope

## The question this software answers

Homological Observability analyzes a known finite support graph for a Markov
jump process observed only at discrete times. Paths between two observations
can share the same endpoints while carrying different integral first-homology
classes. The software asks which of those differences can first occur at each
path-length layer and which remain invisible after integer-valued side
measurements.

When the positive directed rates are also known, the independent critical task
asks how path differences of length $m$ are weighted in the scaling
$T\delta^{m-1}\to\theta$, and constructs the corresponding theorem-derived
marked-Poisson experiment.

The output is exact, inspectable integer and rational data. The integer layer
matters because two visible lattices can have the same real rank while
differing by finite index. Such a difference appears as torsion in a graded
quotient and is lost if the analysis keeps only real vector-space dimensions.

## Supported problem

The supported input is:

- a connected, finite, undirected simple graph $G$;
- bidirectional positive-rate support on every graph edge when applying the
  paper's Markov-process interpretation;
- string vertex identifiers and no self-loops or parallel edges;
- zero or more integer 1-cochains defining a readout
  $\pi:H_1(G;\mathbb Z)\to\mathbb Z^q$;
- an optional maximum filtration layer and simple-cycle budget;
- optionally, either an asymptotic sampling exponent `alpha` or a positive
  observation-time/sampling-interval pair.

The separate `critical` input adds:

- one known, strictly positive exact rate for each direction of every edge;
- a selected layer $m\geq2$ and positive exact critical intensity $\theta$;
- explicit path, preflight and exact integer-digit, output-record, and cycle
  limits;
- optional records for individual paths.

For that input, the software computes:

1. a deterministic integral coordinate system for $H_1(G;\mathbb Z)$;
2. the exact exposure lattice $L_m$ at each requested layer;
3. the exact visible image $\pi(L_m)$;
4. the exact hidden intersection $K_m=L_m\cap\ker\pi$;
5. free ranks and Smith torsion factors for the successive quotients of all
   three filtrations;
6. theorem-derived critical exponents, snapshot-budget exponents, optional
   regimes, and entropy coefficients;
7. a versioned JSON document plus text and Markdown readings of the same
   immutable result.

For a valid critical input, the software additionally computes the exact
stationary law, every path weight at length $m$, graded and visible marks, the
induced readout, the common compound-Poisson Lévy measure, and conditional
critical-endpoint mark laws. These objects are serialized as exact integers
and reduced rational strings.

The topology and integer-lattice analysis does not require rate magnitudes.
Its contract isolates which ambiguity directions exist and when they become
exposed. The critical task consumes the separate exact-rate model only after
constructing that topology at the requested layer. Both tasks require positive
support in both directions. If one directed rate vanishes, the static graph
filtration can include a path witness that the dynamics cannot realize, so
this implementation must not be used unchanged.

## Product roles

The repository has three compatible roles:

- **Research kernel:** analyze a user's finite graph and integer readouts, and
  construct a critical-limit experiment when exact directed rates are known.
- **Reference implementation:** make the integral filtration, coordinate, and
  Smith/Hermite conventions executable and auditable.
- **Paper companion:** reproduce the finite-cycle calculations and frozen
  evidence associated with the manuscript.

The research-kernel role is the broadest, while the other two constrain its
scientific meaning: analysis of new inputs preserves exact integer semantics
and does not silently rewrite the paper evidence.

## Evidence classes

Machine-readable results distinguish four kinds of support:

| Category | Meaning |
| --- | --- |
| `EXACT_INTEGER` | Exact Hermite/Smith calculations and saturated integer kernels |
| `EXACT_COMBINATORIAL` | Complete finite simple-cycle or directed-path enumeration within the declared budget |
| `EXACT_RATIONAL` | Exact stationary probabilities, directed path weights, and critical intensities |
| `ASYMPTOTIC_THEOREM` | A direct application of the paper's asymptotic phase law |

`LIMIT_REACHED` means the requested finite enumeration was not completed. The
result then preserves the validated model, homology basis, and readout, but it
does not expose a partial filtration or phase prediction as if it were
complete.

`PARTIAL_HORIZON` has a different meaning: every requested layer is exact, but
the exposure lattice has not yet reached the full integral homology lattice.
The result may therefore describe the chosen finite horizon, but not the
natural filtration beyond it.

For the independent critical task, `COMPLETE` means the requested layer and
its full experiment were constructed. Natural topology completion remains an
explicit, separate flag. `LIMIT_REACHED` returns no partial catalogue or
marked-Poisson object.

## Supported scope and exclusions

The scientific contract does not cover:

- inference of an unknown graph, unknown rates, or hidden states from data;
- a general Markov-process simulator or trajectory sampler;
- finite-sample risk guarantees, confidence intervals, or numerical error
  bars for the asymptotic phase law or critical-limit experiment;
- noisy, adaptive, or irregular sampling models;
- directed graphs, multigraphs, self-loops, disconnected graphs, or general
  cell complexes;
- real-valued readouts rounded or coerced to integers;
- zero directed rates or support that is not bidirectional;
- trajectory simulation, an exact posterior at finite $(T,\delta)$, or
  unconditional critical MAP solving;
- automatic expansion of the generally infinite total-mark probability table;
- a graphical user interface or plugin framework.

These questions require different scientific inputs, algorithms, or evidence
contracts. They are outside the meaning of a successful result from the
package.

## Interpretation limits

- A small-graph validation sweep is strong implementation evidence, not a
  proof of the paper's general theorems or a performance guarantee for large
  graphs.
- Result matrices use a deterministic homology basis. Their entries can change
  under another valid basis; ranks, quotient invariants, and filtration
  statements are the public scientific content.
- Torsion in a graded quotient records an integral finite-index effect. It must
  not be discarded by replacing integer lattices with real vector spaces.
- A dense, critical, or sparse label is asymptotic in the specified scaling.
  It does not assert that a particular finite dataset has entered that regime.
- The frozen finite-cycle tables verify the advertised examples and
  identities. They do not substitute for the manuscript's hypotheses and
  proofs.

## Scale and resource behavior

Simple-cycle enumeration can grow exponentially. `max_cycles` bounds the
work required for a complete catalogue. When the bound is
exceeded, the software returns `LIMIT_REACHED` and identifies complete and
incomplete components. Users should increase the budget only after considering
the graph size and the value of a complete enumeration.

The implementation is intended for small and medium finite networks where
exact integer answers and an auditable cycle catalogue are more important than
large-scale approximation.

Critical experiments add enumeration of every directed walk of length $m$ and
exact rational arithmetic. `max_paths` bounds the exact walk count;
`max_estimated_integer_digits` controls a preflight admission estimate;
`max_integer_digits` and `max_output_records` apply to observed exact values
and public records. Exceeding any ceiling produces an atomic `LIMIT_REACHED`
result rather than a partial path catalogue or limit law.
