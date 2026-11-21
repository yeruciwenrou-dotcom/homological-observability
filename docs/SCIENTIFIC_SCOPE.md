# Physical interpretation and scientific scope

## The observation problem

State snapshots taken at finite intervals can be compatible with paths that
wind differently around a network. These alternatives leave uncertainty about
the history that occurred. As observation continues, more snapshots arrive
and the history to be recovered grows with them. The research question is how
temporal resolution and additional readouts determine which cycle-history
differences the record can distinguish.

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

The paper studies this question for finite-state Markov jump processes. It
gives the observer complete knowledge of the transition generator $Q$, so the
benchmark has no uncertainty about the dynamics. Even with this knowledge,
finite-resolution records can leave several cycle histories possible. The
generator determines their conditional probabilities; identifying the realized
history still depends on what the record resolves.

The software implements calculations for this observation
problem. Given a support graph and optional cumulative integer counter rules,
it computes hidden cycle differences, their exposure layers, and asymptotic
sampling requirements. Exact transition rates are additional inputs for
constructing the rate-dependent critical experiment. For a measured finite
record, the [posterior calculation](FINITE_RECORDS.md) uses the known rates to
weight the target values compatible with the snapshots and counters. It also
gives the probability of error when reporting the most likely value.

The [target interfaces](TARGET_TASKS.md) ask a more specific question: do the
fixed readouts and endpoints determine a chosen integer trajectory quantity?
They provide an exact decoder or a closed-chain ambiguity witness, and can
search a supplied pool for the smallest set of additional scalar channels.
This algebraic decision needs the support and counter rules, without numerical
rates or cycle enumeration. Optional explanations connect its unresolved
target directions to the paper's exposure filtration.

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

Times are expressed in units set by a fixed reference rate $q_0$. For physical
observation time $T_{\mathrm{phys}}$ and sampling interval
$\Delta_{\mathrm{phys}}$, use $T=q_0T_{\mathrm{phys}}$ and
$\delta=q_0\Delta_{\mathrm{phys}}$. Thus the dimensionless exposure scale is
$(q_0T_{\mathrm{phys}})(q_0\Delta_{\mathrm{phys}})^{m-1}$; the exact path
intensities additionally depend on the transition rates. The filtration
orders ambiguities by their short-time asymptotic contribution. A finite
window includes paths with arbitrarily many jumps.

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

Choose the row that matches the inputs you have or the measurements you can change.

| Research task | Inputs to vary | What the result tells you |
| --- | --- | --- |
| [Infer a target from one record](FINITE_RECORDS.md#use-your-own-model) | Measured snapshots, signed counts and known rates | Compatible integer values, their probabilities and the error risk of the most likely value |
| [Compare recording protocols](FINITE_RECORDS.md#compare-recording-protocols) | Snapshot spacing and counters on the same complete event paths | Paired changes in error risk, snapshot count and number of counters |
| [Test whether a target is determined](TARGET_TASKS.md#use-your-own-target) | Fixed counters and integer targets | An exact decoder or an ambiguity witness, and target values for legal sufficient records |
| [Choose additional counters](TARGET_TASKS.md#three-calculation-interfaces) | Candidate channels alongside the existing counters | Minimum additions, alternative choices and reconstruction certificates |
| [Evaluate ML predictions](SCIENTIFIC_ML.md#supply-your-models-predictions) | Observation scheme and model predictions | Held-out errors, baselines and a separate test on records with identical inputs |
| [Analyze a network](MODEL_GUIDE.md#from-a-physical-model-to-an-input) | Graph edges at fixed recording rules | Exposure layers and hidden cycle directions |
| [Compare counters](COMPARISON_GUIDE.md#compare-your-own-configurations) | Named integer readouts on one graph | Which schemes distinguish more histories, which retain different information and which channels are redundant |
| [Compare sampling laws](MODEL_GUIDE.md#analysis-settings) | Exponent $\alpha>0$ in $\delta=T^{-\alpha}$ | Sparse, critical and dense layers and their leading entropy coefficients |
| [Construct a critical experiment](CRITICAL_EXPERIMENT.md#use-your-own-rates-and-counters) | Exact positive directed rates at a selected threshold | Path weights, visible opportunity counts and limiting conditional mark laws |

The [worked two-loop example](END_TO_END_EXAMPLE.md) shows how a weighted
counter changes the hidden directions and the resulting sampling requirements.

The resulting exponents give asymptotic sampling guidance. For example,
$N_T=T/\delta$ windows satisfy $\lambda_m\to0$ if
$N_T/T^{m/(m-1)}\to\infty$ in the stated units. This helps compare how recording
requirements grow with observation time. For a finite run with known rates,
[compare candidate protocols](FINITE_RECORDS.md#compare-recording-protocols)
on the same paths to estimate how much an extra snapshot or counter reduces
mean error. The report gives the recording resources for each choice.
An instrument model can assign a monetary or energy cost to those resources.

The package also supplies a reference implementation of the paper's integer
and path constructions and reproducible finite-cycle calculations. General
theorems and proofs remain in the paper.

## Supported problem

For a topology analysis, provide:

- a connected, finite, undirected simple graph $G$;
- bidirectional positive-rate support on every graph edge when applying the
  paper's Markov-process interpretation;
- string vertex identifiers and no self-loops or parallel edges;
- zero or more integer 1-cochains defining a readout
  $\pi:H_1(G;\mathbb Z)\to\mathbb Z^q$;
- an optional maximum filtration layer and simple-cycle budget;
- optionally, either an asymptotic sampling exponent `alpha` or a positive
  observation-time/sampling-interval pair.

The paper establishes its statistical results for a fixed graph and fixed
positive bidirectional rates, a known generator $Q$, a stationary initial
distribution, noiseless regular vertex snapshots, and a fixed exact integral
readout. These conditions govern the theorem-derived sampling interpretations.
The graph and lattice calculations take the graph and readout rules as inputs;
they require neither rate magnitudes nor a sampled trajectory.

A `compare` study fixes the graph, sampling request, and computation limits
while varying the declared counter configurations. Each counter is an exact
cumulative integer measurement. The study compares the information supplied by
those candidates. The researcher supplies the candidate instruments and
assesses their physical costs.

A [finite record](FINITE_RECORDS.md#use-your-own-model) supplies the observed
states on a regular grid and any whole-record signed counts. The posterior
conditions on the first observed state. Known rates are needed to assign
probabilities to unresolved target values. The numerical calculation supports
one scalar target with at most two independent integer coordinates across
the target and counters. Exact reconstruction can also succeed at higher rank.

The separate `critical` input adds:

- one strictly positive exact rate for each direction of every edge;
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

Topology analysis and counter comparison determine which ambiguity directions
exist and when they become exposed, using only the positive bidirectional
support. The critical task also uses the rate magnitudes to weight those
directions. A model with vanishing directed rates requires a support calculation
that follows its allowed transition directions.

## Evidence classes

Topology and critical-limit results distinguish four kinds of support:

| Category | Meaning |
| --- | --- |
| `EXACT_INTEGER` | Exact Hermite/Smith calculations and saturated integer kernels |
| `EXACT_COMBINATORIAL` | Complete finite simple-cycle or directed-path enumeration, or exact construction of each requested exposure lattice from [shortest-path cycle generators](CONVENTIONS.md#shortest-path-generators) |
| `EXACT_RATIONAL` | Exact stationary probabilities, directed path weights, and critical intensities |
| `ASYMPTOTIC_THEOREM` | A direct application of the paper's asymptotic phase law |

In a topology analysis, `LIMIT_REACHED` means the simple-cycle or generator
catalogue exceeded its budget. The result preserves the validated model, homology basis,
and readout; filtration and phase fields are null.

`PARTIAL_HORIZON` has a different meaning: every requested layer is exact, but
the exposure lattice has not yet reached the full integral homology lattice.
The result describes that finite horizon; higher layers remain uncomputed.

Comparison relations on a partial horizon have scope `COMPUTED_EXPOSURE`,
restricting their kernel statements to that lattice.
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

## Interpreting results in a research workflow

The inputs specify a support graph and exact measurement rules. Estimating an
unknown graph, transition rates, or hidden states from data is a separate
inference task. Noisy, adaptive, or irregular observations likewise need an
observation model beyond the noiseless regular snapshots and exact integer
counters used here. For protocol comparisons, supply complete event histories
or simulate paths on your own supported graph from known rates and an initial
distribution. The DFR application also accepts externally trained predictors
and scores them against the recorded experimental targets.

Dense, critical, and sparse labels describe limits under a specified sampling
scaling. The critical result gives a limiting generative specification and
conditioning rule, represented by its component laws. Evaluating a posterior
at finite $(T,\delta)$ or an unconditional critical MAP probability requires
the corresponding conditional-law calculation. The [finite-record solver](FINITE_RECORDS.md) evaluates a scalar target at finite time on a known rate model using its actual joint integer image.

For the paper's finite-cycle examples, the checkout includes specialized
bridge calculations and critical MAP identities. The
[computational report](../results/REPORT.md) explains these results, and the
[finite-ring exploration command](../README.md#finite-ring-bridges) evaluates
individual cases.

When comparing exact results, use ranks, quotient invariants, and filtration
statements. Coordinate matrix entries can change with a valid choice of
homology basis. Retain torsion factors as well as free ranks: a finite-index
effect such as parity disappears if the integer lattices are replaced by
their real spans. The [coordinate conventions](CONVENTIONS.md) describe this
distinction.

## Scale and resource behavior

Target diagnosis and record reconstruction use exact linear and integer
algebra. Readout design adds a subset search that can grow combinatorially
with the candidate pool. The [target limits](TARGET_TASKS.md#exactness-and-guarantees)
bound that search and its certificates; a stopped run retains only the
guarantees established before its stop. Target explanations additionally use
the exposure calculation described below.

For layer calculations on dense graphs, the [shortest-path generator method](CONVENTIONS.md#shortest-path-generators)
recovers the same integer filtration and accepts its own generator budget.
Use enumeration when the list of individual simple cycles is part of the result.
Simple-cycle enumeration can grow exponentially. `max_cycles` bounds the
work required for a complete catalogue. When the bound is
exceeded, the software returns `LIMIT_REACHED` and identifies complete and
incomplete components. Users should increase the budget only after considering
the graph size and the value of a complete enumeration.

Suitability depends on the cycle catalogue and the integer coefficients.
Graphs with the same vertex count can have very different cycle catalogues
and arithmetic costs. The [built-in study measurements](COMPARISON_GUIDE.md#resource-use)
provide small-network baselines; use explicit budgets when trying a new
network.

Critical experiments add enumeration of every directed walk of length $m$ and
exact rational arithmetic. `max_paths` bounds the exact walk count;
`max_estimated_integer_digits` controls a preflight admission estimate;
`max_integer_digits` and `max_output_records` apply to observed exact values
and public records. Exceeding any ceiling produces an atomic `LIMIT_REACHED`
result rather than a partial path catalogue or limit law.
