# Mathematical and coordinate conventions

This guide describes the mathematical conventions used in model input,
exact calculations, and serialized results.

## Graph model

The software accepts a connected undirected simple graph
$G=(V,E)$. Vertex identifiers are nonempty strings. Self-loops, parallel
edges, duplicate vertices, disconnected graphs, and edges with unknown
endpoints are rejected.

Every undirected edge has a reference orientation: from the lexicographically
smaller vertex identifier to the larger identifier. This is a coordinate
convention, not a physical direction or transition-rate assignment. Under the
paper's Markov-process interpretation, the undirected edge represents positive
transition-rate support in both directions. The analysis kernel does
not consume rate magnitudes; if a directed rate is zero, the paper's static
exposure filtration no longer applies unchanged.

## Integral first homology

For a connected graph,

$$
\mathrm{rank} H_1(G;\mathbb Z)=|E|-|V|+1.
$$

The implementation builds a deterministic spanning tree by ordered
Kruskal-style edge selection. Each non-tree edge is a chord and determines one
fundamental cycle. Chords are ordered lexicographically, and the fundamental
cycle matrix has an identity block on the chord rows.

This construction gives auditable integer coordinates for
$H_1(G;\mathbb Z)$, but the coordinate matrix is not itself a
basis-independent result. Reversing edge orientations or choosing another
spanning tree changes the matrix by an integral unimodular transformation.
Public invariants must remain unchanged.

## Abstract readout and coordinate matrix

Let

$$
\Lambda=H_1(G;\mathbb Z).
$$

An abstract side readout is a homomorphism

$$
\pi:\Lambda\longrightarrow\mathbb Z^q.
$$

The model represents each component of $\pi$ by an integer 1-cochain on
oriented graph edges. If an input edge is written opposite to the reference
orientation, its coefficient is negated during normalization. Real or boolean
coefficients are rejected; the implementation never rounds a readout to
manufacture an integer map.

After the deterministic homology basis identifies
$\Lambda\cong\mathbb Z^r$, the same homomorphism has an integer matrix

$$
P=[\pi]_{\mathcal B}\in\mathbb Z^{q\times r}.
$$

Thus $\pi$ denotes the basis-independent map and $P$ denotes its matrix in the
chosen basis. If the columns of $B_m$ generate $L_m$ in those coordinates,
the columns of $PB_m$ generate the visible image $\pi(L_m)$. Public
mathematical statements use $\pi(L_m)$; serialized matrices expose $P$ and
$B_m$ so the calculation can be reconstructed.

## Exposure filtration

At layer $m$, the exposure lattice is

$$
L_m=
\left\langle [C]: C\text{ is a simple cycle of length at most }2m\right\rangle_{\mathbb Z}.
$$

Generation is over the integers. Replacing the lattice by its real span would
lose finite-index information and can produce a scientifically different
answer.

Layers zero and one are represented explicitly as zero lattices. Unless the
model sets `max_layer`, the implementation computes through
$\lceil |V|/2\rceil$, which covers every simple-cycle length in a finite
simple graph.

When `max_layer` is smaller, the requested horizon is complete if all layers
through that value are computed. The natural filtration is complete only when
the resulting exposure lattice equals $H_1(G;\mathbb Z)$. Thus a short request
can be certified complete after early saturation, but a proper terminal
sublattice is reported as `PARTIAL_HORIZON`.

Simple cycles are canonicalized up to cyclic rotation and reversal, then
ordered first by length and then lexicographically. `max_cycles` bounds the
complete catalogue. Exceeding it stops the filtration rather than returning a
silent truncation.

## Visible and hidden filtrations

The two readout-dependent filtrations are

$$
\pi(L_m)\subseteq\mathbb Z^q,
\qquad
K_m=L_m\cap\ker\pi\subseteq\Lambda.
$$

The visible image records exposed information retained by the readout. The
hidden lattice records exposed trajectory differences that the readout sends
to zero. The hidden intersection uses a saturated integer kernel obtained from
a Smith decomposition; a rational nullspace basis is not treated as an
integer basis.

For every layer $m\geq2$, the result reports the finitely generated abelian
quotients

$$
\frac{L_m}{L_{m-1}},
\qquad
\frac{\pi(L_m)}{\pi(L_{m-1})},
\qquad
\frac{K_m}{K_{m-1}}.
$$

Each quotient is summarized by its free rank and nontrivial Smith torsion
factors. A factor $2$, for example, denotes a
$\mathbb Z/2\mathbb Z$ component. For a finite quotient, `finite_order` is the
product of the torsion factors; it is `null` when the quotient has positive
free rank.

The graded free ranks obey

$$
\mathrm{rank}\frac{L_m}{L_{m-1}} =
\mathrm{rank}\frac{\pi(L_m)}{\pi(L_{m-1})} +
\mathrm{rank}\frac{K_m}{K_{m-1}}.
$$

Torsion is not determined by this rank identity and must be retained
separately. No bare symbol $J$ is used for the visible image because the paper
reserves related notation for a shifted low-layer object.

## Information relations between configurations

Two counter configurations are compared on the same integer lattice $M$:
the terminal computed exposure lattice, or all of $\Lambda$ once the natural
filtration is complete. For a configuration $A$ with readout $\pi_A$, write

$$
K^A=M\cap\ker\pi_A.
$$

Histories in $M$ have the same readout exactly when their difference lies in
$K^A$. This gives the information relations used by `compare`:

| Relation | Kernel condition on $M$ |
| --- | --- |
| Equivalent information | $K^A=K^B$ |
| $A$ strictly refines $B$ | $K^A\subsetneq K^B$ |
| $B$ strictly refines $A$ | $K^B\subsetneq K^A$ |
| Incomparable information | Neither kernel contains the other |

A smaller kernel distinguishes more histories. Equal ranks, equal first hidden
layers, and equal entropy coefficients alone do not determine these relations.
The comparison checks integer inclusion and returns inclusion coordinates or
an explicit cycle direction that one readout hides and the other distinguishes.
Edge-chain witnesses use the canonical graph orientation.

Equivalent configurations may have different integer image lattices. For
example, $x$ and $2x$ carry the same information under exact measurement:
decoding $x$ from $2x$ is defined on the legal image $2\mathbb Z$. It does not
require an integer inverse on every ambient output value. For open histories,
the common endpoint-reference correction gives the same comparison of cycle
differences.

A channel is individually redundant when removing it leaves the kernel on
$M$ unchanged while retaining every other channel. Several channels can each
pass that test without being removable together. These statements have scope
`COMPUTED_EXPOSURE` when $M$ is a proper sublattice of $\Lambda$, and
`FULL_HOMOLOGY` when $M=\Lambda$. An unavailable calculation supplies no
relation. See the
[output contract](OUTPUT_CONTRACT.md#information-relations-and-certificates)
for the certificate fields and the [comparison guide](COMPARISON_GUIDE.md)
for worked configurations.

## Matrices in JSON

Every integer matrix is encoded with explicit dimensions:

```json
{
  "rows": 2,
  "columns": 0,
  "data": [[], []]
}
```

Explicit dimensions preserve the difference between, for example, a
$2\times0$ zero lattice and a $0\times0$ matrix. Lattice bases are stored by
columns.

## Sampling and phase conventions

The paper fixes a reference transition rate $q_0$ and measures time in units
of $q_0^{-1}$. For physical observation time $T_{\mathrm{phys}}$ and sampling
interval $\Delta_{\mathrm{phys}}$, the dimensionless inputs are
$T=q_0T_{\mathrm{phys}}$ and $\delta=q_0\Delta_{\mathrm{phys}}$. All sampling
inputs here use these normalized units; do not apply the conversion again
to values already normalized. The exposure scale is

$$
T\delta^{m-1}=(q_0T_{\mathrm{phys}})(q_0\Delta_{\mathrm{phys}})^{m-1}.
$$

The critical task uses transition rates divided by the same $q_0$ and
$\theta=\lim T\delta^{m-1}$ in these units. Its rate weights supply the
remaining dynamical factors.

The topology result can be interpreted in either of two mutually exclusive
ways.

With an asymptotic exponent `alpha`, the sampling interval scales as

$$
\delta=T^{-\alpha}.
$$

For layer $m$, the software reports

$$
\alpha_m=\frac{1}{m-1},
\qquad
\text{snapshot-budget exponent}=\frac{m}{m-1},
$$

the scaling exponent $1-\alpha(m-1)$, and the regime `DENSE`, `CRITICAL`, or
`SPARSE` according to its sign. If $d_m$ is the hidden graded free rank, the
reported entropy coefficient is

$$
\frac{d_m}{2}\max\bigl(1-\alpha(m-1),0\bigr).
$$

`DENSE` means that path alternatives at this layer accumulate in the specified
limit; it does not describe graph density. `SPARSE` means that their exposure
vanishes. Recovery of the natural quotient is assured in the sparse limit;
the dense-limit strong converse requires $d_m>0$. At criticality, the
conditional experiment carries information beyond this logarithmic entropy
coefficient. See the [physical interpretation](SCIENTIFIC_SCOPE.md).

At `alpha = 0`, the grid is fixed. Once the natural filtration is complete,
the summed coefficient is $\mathrm{rank}(\ker\pi)/2$, consistent with the
paper's fixed-grid entropy law. Positive `alpha` describes a shrinking grid.

With positive `observation_time` $T$ and `sampling_interval` $\delta$, the
software instead reports the finite-scale control parameter

$$
\lambda_m=T\delta^{m-1}.
$$

It does not assign an asymptotic regime from that finite pair. Both
interpretations are labeled `ASYMPTOTIC_THEOREM`: they apply the paper's phase
law and are not empirical uncertainty estimates.

## Critical-layer rates and marks

The independent critical task supplies one strictly positive rate $q_{xy}$
for each directed version of every support edge. Rates and the critical
intensity $\theta$ are exact positive scalars. JSON decimals are interpreted
exactly; direct Python calls reject binary floating-point inputs.

For a selected layer $m\geq2$, every directed walk
$\gamma=(x_0,\ldots,x_m)$ has leading weight

$$
W(\gamma)=\frac{1}{m!}\prod_{j=0}^{m-1}q_{x_jx_{j+1}}.
$$

For each ordered endpoint pair, the implementation chooses the
lexicographically first shortest path as a reference geodesic. Subtracting its
edge chain from the walk gives an integral cycle, which is projected to

$$
L_m/L_{m-1}.
$$

The induced readout sends this mark to

$$
\pi(L_m)/\pi(L_{m-1}),
$$

and its kernel is identified with $K_m/K_{m-1}$. Marks are serialized in a
constructive Smith presentation with torsion coordinates first and free
coordinates second.

A different reference geodesic translates all marks for a fixed ordered
endpoint by the same quotient element and translates their visible marks by
its induced image. The path weights are unchanged. Reference geodesics and
their coordinate labels are therefore auditable conventions rather than
basis-independent observables.

The exact rate matrix determines the stationary law $p$. Under

$$
T\delta^{m-1}\longrightarrow\theta,
$$

the implementation separates two mechanisms:

- endpoint distance below $m$: nonzero marks contribute to a common
  compound-Poisson Lévy measure, while zero marks are excluded;
- endpoint distance equal to $m$: each ordered endpoint pair has a Poisson
  count and a conditional mark law, with zero marks retained.

Each path contribution has exact intensity $\theta p(x)W(\gamma)$ before
aggregation. The complete object is a theorem-derived
critical-limit generative specification. It is not an exact posterior at
finite $(T,\delta)$, a trajectory simulation, or an unconditional
critical MAP solver.

## Invariant versus coordinate-dependent output

Treat the following as public invariant content:

- graph first Betti number;
- lattice ranks;
- graded free ranks and torsion factors;
- first nonzero exposure, visible, and hidden layers;
- cycle lengths and completeness of the finite catalogue;
- theorem-derived phase exponents and regimes;
- information equivalence, refinement, and individual channel redundancy on
  the declared common lattice;
- exact stationary probabilities, aggregated critical weights, and intensities.

Tree edges, chord edges, fundamental-cycle matrices, readout matrices, and
lattice basis columns are auditable coordinates. They are included so a
researcher can reconstruct the calculation, not because their entries are
canonical under every valid basis choice.

`analyze` and `compare` accept `--reverse-tree-order` to choose another
deterministic spanning tree. Comparison candidates always share the chosen
basis. Integer certificate coordinates and the particular witness selected
can change, while the information relation and the validity of its physical
edge-chain evidence remain unchanged.
