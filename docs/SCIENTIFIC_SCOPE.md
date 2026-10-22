# Physical interpretation and scientific scope

## The question this software answers

A Markov jump network specifies the states a system can occupy and the rates
at which it moves between them. A snapshot records its state at one instant.
Between snapshots, several routes may be possible, including routes whose
integer cycle counts differ. Knowing the network and its rates determines
the probabilities of those routes, but leaves the history of a particular run
to be inferred from its records.

The target here is accumulated cycle history. On a ring it is a net winding
count; on a network with several independent cycles it is an integer vector.
For an open trajectory, fixed endpoint reference paths define these
coordinates. Histories with the same endpoints have an unambiguous cycle
difference, and a change of reference does not change their distinguishability.

This target lies between instantaneous state and a complete trajectory. It
retains cumulative circulation while omitting individual jump times. An
accurate estimate of a long-time average current need not identify the exact
integer count in a single run. Likewise, zero mean current at equilibrium
does not remove the alternative cycle histories compatible with snapshots.

## How local ambiguity accumulates

On a triangle, a direct A → B jump and the route A → C → B differ by one
cycle. The two-jump alternative has probability of order $\delta^2$ in a short
window. A record of duration $T$ contains about $T/\delta$ windows, so these
opportunities accumulate on the scale $T\delta$. Observing for longer gives
more data while also lengthening the history to recover.

The general exposure filtration $L_m$ organizes such path differences by
their short-time order. After weighting by the probability of the visible
endpoints, order $m$ contributes a single-window scale $\delta^m$ and an
accumulated scale

$$
\lambda_m=T\delta^{m-1}.
$$

Times are expressed in units set by a fixed reference rate $q_0$. With physical
times, the dimensionless scale is $(q_0T)(q_0\delta)^{m-1}$; the exact path
intensities additionally depend on the transition rates. The filtration
describes an asymptotic ordering of ambiguities, not a hard cutoff on how many
jumps can occur in a finite window.

An integer side readout $\pi$ represents an additional exact counter, such as
a signed count across a selected edge or a weighted combination of cycle
counts. The kernel intersection $K_m=L_m\cap\ker\pi$ identifies exposed
history differences that leave this counter unchanged. The program computes
these integer relations for a supplied network and readout specification.

For the natural history class modulo $K_{m-1}$, the paper proves recovery
when $\lambda_m\to0$, a conditional limit experiment when
$\lambda_m\to\theta\in(0,\infty)$, and optimal mean recovery probability
tending to zero when $\lambda_m\to\infty$ **and the layer adds a hidden free
direction**. A finite torsion ambiguity need not obey that last conclusion.
The hidden free ranks control leading entropy growth; integer quotients retain
additional finite information such as parity.

## Research uses

Choose a task according to what you want to vary:

| Task | Inputs to vary | Read from the result |
| --- | --- | --- |
| Compare network structures with `analyze` | Graph edges, with the observation protocol fixed | Exposure layers and hidden directions; adding an edge can change more than the cycle count |
| Compare counters with `compare` | Named integer readouts on one shared graph | Information equivalence, strict refinement, incomparable directions, and individually redundant channels |
| Compare sampling scalings with `analyze` | Exponent $\alpha>0$ in $\delta=T^{-\alpha}$ | Which hidden layers are sparse, critical, or dense, and their leading entropy coefficients |
| Compare dynamics with `critical` | Exact positive directed rates at a selected threshold | Path weights, visible opportunity counts, and the limiting conditional mark laws |

The [wedge tutorial](END_TO_END_EXAMPLE.md) explains how a weighted counter
changes the hidden directions. The [comparison guide](COMPARISON_GUIDE.md)
runs several configurations under common conditions and uses exact witnesses
to distinguish an objective tie from equivalent information. The
[critical tutorial](CRITICAL_EXPERIMENT.md) separates the effects of rates and
additional observations. These are model-analysis tasks: the program consumes
a graph, readouts, and optional rates rather than fitting a measured
trajectory.

The resulting exponents give asymptotic sampling guidance. For example,
$N_T=T/\delta$ windows satisfy $\lambda_m\to0$ if
$N_T/T^{m/(m-1)}\to\infty$ in the stated units. This helps compare how recording
requirements grow with observation time. Choosing a sampling interval for a
specified finite-run error tolerance requires additional risk analysis;
counter cost and recording energy are separate inputs to an instrument model.

The package also supplies a reference implementation of the paper's integer
and path constructions and reproducible finite-cycle calculations. General
theorems and proofs remain in the paper.

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

The paper's statistical interpretation fixes the graph, generator, and
readout, starts the process in its stationary law, and uses noiseless regular
vertex snapshots. The exact graph and lattice calculations themselves do not
require a sampled trajectory.

A `compare` study fixes the graph, sampling request, and computation limits
while varying the declared counter configurations. Each counter is an exact
cumulative integer measurement. The study compares the information supplied by
those candidates; it does not generate candidate instruments or assign their
physical costs.

The separate `critical` input adds:

- one known, strictly positive exact rate for each direction of every edge;
- a selected layer $m\geq2$ and positive exact critical intensity $\theta$;
- explicit path, preflight and exact integer-digit, output-record, and cycle
  limits;
- optional records for individual paths.

For topology analysis, the software computes:

1. a deterministic integral coordinate system for $H_1(G;\mathbb Z)$;
2. the exact exposure lattice $L_m$ at each requested layer;
3. the exact visible image $\pi(L_m)$;
4. the exact hidden intersection $K_m=L_m\cap\ker\pi$;
5. free ranks and Smith torsion factors for the successive quotients of all
   three filtrations;
6. theorem-derived critical exponents, snapshot-budget exponents, optional
   regimes, and entropy coefficients;
7. a versioned JSON document plus text and Markdown reports of the same
   immutable result.

For a comparison study, the software performs the topology analysis for each
candidate and compares its hidden kernel on the common computed exposure
lattice. Kernel equality gives equivalent information; strict containment
gives a refinement; otherwise each candidate distinguishes a direction hidden
by the other. Integer containment certificates and physical edge-chain
witnesses make these statements checkable. Individual channel removal tests
identify redundancy on the same scope. The
[coordinate conventions](CONVENTIONS.md#information-relations-between-configurations)
give the precise relation to readout partitions and legal image lattices.

The comparison retains the raw analyses, scalar summaries, relation scope,
and computation identity in one structured result. A report and a rerunnable
bundle expose the same evidence. A scalar objective can favor one candidate
while the two configurations retain incomparable information.

For a valid critical input, the software additionally computes the exact
stationary law, every path weight at length $m$, graded and visible marks, the
induced readout, the common compound-Poisson Lévy measure, and conditional
critical-endpoint mark laws. These objects are serialized as exact integers
and reduced rational strings.

The topology and integer-lattice analysis does not require rate magnitudes.
Its contract isolates which ambiguity directions exist and when they become
exposed. Counter comparisons use this rate-independent topology contract. The
critical task consumes the separate exact-rate model after constructing that
topology at the requested layer. Applying these calculations to a Markov
process requires positive support in both directions. If one directed rate
vanishes, the static graph filtration can include a path witness that the
dynamics cannot realize, so
this implementation must not be used unchanged.

## Evidence classes

Machine-readable results distinguish four kinds of support:

| Category | Meaning |
| --- | --- |
| `EXACT_INTEGER` | Exact Hermite/Smith calculations and saturated integer kernels |
| `EXACT_COMBINATORIAL` | Complete finite simple-cycle or directed-path enumeration within the declared budget |
| `EXACT_RATIONAL` | Exact stationary probabilities, directed path weights, and critical intensities |
| `ASYMPTOTIC_THEOREM` | A direct application of the paper's asymptotic phase law |

In a topology analysis, `LIMIT_REACHED` means the requested finite enumeration
was not completed. The result preserves the validated model, homology basis,
and readout, but it does not expose a partial filtration or phase prediction
as if it were complete.

`PARTIAL_HORIZON` has a different meaning: every requested layer is exact, but
the exposure lattice has not yet reached the full integral homology lattice.
The result may therefore describe the chosen finite horizon, but not the
natural filtration beyond it.

Comparison relations on a partial horizon have scope `COMPUTED_EXPOSURE`.
They do not establish equality or containment on uncomputed directions.
Candidates with `LIMIT_REACHED` or `ERROR` have no asserted information
relations, while valid candidates retain their results. The whole study is
`COMPLETE` only when every candidate is naturally complete; otherwise it is
`INCOMPLETE`. See the
[output contract](OUTPUT_CONTRACT.md#configuration-comparison-document)
for the distinction between scientific completeness and successful export.

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
- a general solver for the posterior at finite $(T,\delta)$, or unconditional
  critical MAP solving;
- automatic expansion of the generally infinite total-mark probability table;
- a graphical user interface or plugin framework.

These questions require different scientific inputs, algorithms, or evidence
contracts. They are outside the meaning of a successful result from the
package.

The source checkout does include specialized finite-cycle bridge calculations
and critical MAP identities for the paper's examples. See the
[computational report](../results/REPORT.md) and
[finite-ring exploration command](../README.md#finite-ring-bridges).

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
