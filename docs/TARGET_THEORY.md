# Target observability: technical derivation

This note is a software-oriented technical supplement to
[Stochastic Histories at Finite Temporal Resolution: Homological Observability
and Information Phase Diagrams in Markov Jump Processes](https://doi.org/10.5281/zenodo.23424849).
The exposure filtration and hidden-history entropy law come from the paper.
The target-image, conditional-entropy and minimum-readout arguments below are
derived here for target diagnosis, readout design and scientific ML applications.

## 1. Full cycle group, sufficiency and certificates

Let a finite connected simple undirected support graph have a positive transition
rate in both directions along each edge. Fix one orientation of each edge and a
spanning tree. Its fundamental-cycle columns $B$ identify the integer cycle group
$H$ with $\mathbb{Z}^b$, where $b=|E|-|V|+1$. An integer cochain integrates signed edge counts;
write $P:H\to\mathbb{Z}^k$ for fixed readouts and $F:H\to\mathbb{Z}^q$ for the targets.

All targets are determined by $P$ on the full cycle group exactly when

```math
\ker_{\mathbb{Z}}P\subseteq\ker_{\mathbb{Z}}F
\quad\Longleftrightarrow\quad
\mathrm{rank}_{\mathbb{Q}}P=
\mathrm{rank}_{\mathbb{Q}}\begin{bmatrix}P\\F\end{bmatrix}.
```

For the forward direction, every rational vector in $\ker P$ becomes an integer
kernel vector after multiplication by a common denominator. Thus $F$ annihilates
the rational kernel, so its rows lie in $P$'s rational row span. Conversely, that
row-span condition gives a rational matrix $D$ with $DP=F$; $Pz=0$ implies $Fz=0$.
The code verifies $DP=F$ exactly before returning the decoder. If ranks differ,
a saturated integer kernel basis has a column $z$ with $Fz\neq0$. Returning $z$,
$Bz$ and $Fz$ witnesses the insufficiency; the product verifies $Pz=0$ and $Fz\neq0$.

`analyze_target` applies this criterion uniformly to **all** records and
trajectories on the stated support. It works directly with fundamental-cycle
coordinates. Additional restrictions from a particular finite observation enter
its conditional history set. A spanning-tree change is an integral unimodular
coordinate change, preserving the criterion and physical cochains.

## 2. Legal integer images and open trajectories

A rational decoder is defined on the legal integer image $P(H)$. The evaluator
first solves $Pc=p$ over $\mathbb{Z}$ via a verified Smith decomposition $UPV=S$. Divisibility
by each nonzero diagonal entry and vanishing of every residual row are necessary
and sufficient for membership. It constructs and verifies an integer preimage.
For example $P(x)=2x$, $F(x)=x$ permits decoding $x=p/2$ for even $p$.
With $P=2I_2$, $F=(1,1)$ and $p=(1,1)$, the record lies outside
$P(H)=2\mathbb{Z}^2$, even though the decoder formula returns the integer 1.

For an open walk chain $x$ from $s$ to $t$, let $h(s,t)$ be the tree
path with the same boundary. Then $x-h=Bc$ for a unique integer $c$. For raw cochain
matrices $A$ and $G$, the evaluator uses

$$
p'=Ax-Ah=Pc,\qquad Gx=D p'+Gh,\qquad P=AB,\ F=GB.
$$

Known endpoints therefore determine pure-gradient targets, whose cycle
restriction is zero. `record_kind="cycle"` accepts the corrected coordinates
without endpoint arguments and returns the cycle contribution $Fc$.

## 3. The exact target ambiguity image

For a legal $p$ choose $c_0\in H$ with $Pc_0=p$. The entire integer solution set is
$c_0+K$, where $K=\ker_{\mathbb{Z}}P$. Consequently the target set is precisely

$$
F(c_0)+M,\qquad M=F(K).
$$

Both inclusions follow directly by subtracting $c_0$ or adding a kernel vector.
The choice of $c_0$ changes the representative but leaves the coset unchanged.
Open-path targets add the known tree-path term. The kernel must be saturated:
independently clearing denominators in rational-nullspace columns can generate
only a proper sublattice. For $P=(2,1,1)$, $F=(0,1,0)$, the true image $M$ is $\mathbb{Z}$;
a naive basis can incorrectly return $2\mathbb{Z}$. The Smith-based kernel and Hermite image
backend preserve this information.

The [discrete flashing ratchet (DFR) example](SCIENTIFIC_ML.md#model-and-data-provenance)
has two triangular rings (0,1,2) and (3,4,5), with switching edges $i\leftrightarrow i+3$.
The counters $W_{\mathrm{ON}}$ and $W_{\mathrm{OFF}}$ count signed crossings
of $2\to0$ and $5\to3$, respectively.
With $W=W_{\mathrm{ON}}+W_{\mathrm{OFF}}$ and
$\Delta W=W_{\mathrm{ON}}-W_{\mathrm{OFF}}$, we have
$\Delta W\equiv W\ (\mathrm{mod}\ 2)$.
At fixed $W$ the image is $2\mathbb{Z}$: a unit ON circulation and a reverse OFF circulation
preserve $W$ while changing $\Delta W$ by 2. These loops can be connected by opposite
traversals of a switching edge, which cancel in every cochain. For endpoints $0\to3$ the
walks [0,3] and [0,1,2,0,3,5,4,3,0,3] have $W=0$ and $\Delta W$ equal to 0 and 2.
The packaged pressure case completes all their transitions before the first
positive snapshot time; every snapshot, including endpoints, agrees.

## 4. Target-image filtration and entropy

Use the paper's integer exposure filtration $L_m$. The existing backend constructs
it from simple cycles of length at most $2m$. Define

$$
K_P^m=L_m\cap\ker P,\qquad
K_{P,F}^m=L_m\cap\ker P\cap\ker F,\qquad M_m=F(K_P^m).
$$

Restriction of $F$ gives a short exact sequence

$$
0\longrightarrow K_{P,F}^m\longrightarrow K_P^m\longrightarrow M_m\longrightarrow0.
$$

Ranks therefore add at each $m$. Nested $L_m$ imply nested $K_P^m$ and $M_m$,
so the graded target rank

$$
g_m=\mathrm{rank}M_m-\mathrm{rank}M_{m-1}
=r_P^m-r_{P,F}^m\geq0
$$

is nonnegative. Here $r$ denotes the corresponding hidden graded free rank.
The implementation constructs the integer images, verifies lattice inclusion,
and checks this rank identity. The free ranks determine the $\log T$ leading
coefficient; the integer lattices also retain finite-index information such as parity.

Let $C$ be the latent integer cycle history, $S$ the snapshots and $PC$ the observed
cochain record. Since $FC$ is a function of $C$, the conditional entropy chain rule is

$$
H(FC\mid S,PC)=H(C\mid S,PC)-H(C\mid S,PC,FC)
=R_P-R_{(P,F)}.
$$

Under the original paper's fixed finite connected bidirectional positive-rate
model, stationary initial law and regular noiseless snapshots, Theorem 5.1 applied
to both entropies on the **same** model gives, for fixed $\alpha>0$,
$\delta=T^{-\alpha}$ and $T/\delta\in\mathbb{N}$ as $T\to\infty$,

$$
H(FC\mid S,PC)=
\frac12\sum_{m\geq2}g_m[1-\alpha(m-1)]_+\log T+o(\log T).
$$

For a fixed snapshot interval $\delta_0>0$, Proposition 5.3 applied to the same
two entropies instead gives, along $T/\delta_0\in\mathbb{N}$,

$$
H(FC\mid S,PC)=\frac12\mathrm{rank}F(\ker P)\log T+O(1).
$$

Here $\mathrm{rank}F(\ker P)=\sum_m g_m$, matching the leading coefficient at
$\alpha=0$. At a layer carrying target rank, the critical exponent is
$\alpha=1/(m-1)$. A zero coefficient gives sublogarithmic target entropy in
this limit. Its residual uncertainty calls for finer asymptotic analysis,
including the conditional limit law at critical scales. For finite inputs
$T,\delta$, the reported $T\delta^{m-1}$ measures exposure at each layer.
Recovery probabilities depend on the dynamics and the conditional history law;
exact reconstruction from counters follows the criterion in section 1.

The global coefficient is available once the computed exposure lattice reaches
$H$; an earlier stop returns a prefix coefficient and `PARTIAL_HORIZON`. The default
horizon is $\lceil |V|/2\rceil$, but early saturation also suffices. Explanation budgets
cover cycles, matrices, integer sizes and cooperative time; explanation status is
independent of the core certificate. A design explanation uses the **fixed** readouts.
To explain a selected augmentation, re-run analysis with its added channels.

## 5. Minimum additional scalar channels

The existing readout $P_0$ is fixed. Candidate rows have unique physical IDs; distinct instruments with
equal cochains remain distinct choices. For each subset $J$ test sufficiency of
$[P_0;P_J]$. If $P_0$ already suffices, the empty addition is optimal. If the entire
pool fails, no subset can succeed by monotonicity. Otherwise search cardinalities
in increasing order. Exhausting all smaller sizes before the first success proves
global cardinality minimality. Exhausting the successful size establishes all
ties. Constructing each returned certificate is a separate operation.

Thus feasibility, minimum proof, tied-set enumeration, output truncation and
certificate completion have independent fields. Stopping mid-size retains
established lower/upper bounds and any proven minimum. A count of discovered ties
equals the total after that size's enumeration is complete. The objective is
the number of added scalar channels, with each candidate counted once.
When all events are available, the candidate pool can include a direct target
counter. Fixed records, restricted instruments and shared targets determine
which choices are available in a particular application.

## 6. Equal-input prediction reference

On the constructed equal-weight pair with targets 0 and 2, a deterministic
function of the identical visible input returns a common real $a$. Its mean
absolute error obeys $(|a|+|2-a|)/2\geq1$ by the triangle inequality. It can equal at
most one target, giving exact-match accuracy $\leq1/2$. For randomized predictors
whose randomness is independent of the hidden label, these bounds hold after
averaging over prediction randomness as well as the equal-weight pair.

The pair's conditional mean is 1, while its realized targets are 0 and 2.
The evaluation adapter distinguishes conditional means, real point predictions
and realized integer values, preserves original values, and scores explicitly
rounded predictions separately. The bounds above use the constructed pair's
equal weights. Natural CTMC predictions are evaluated on their own sampled
trajectories and reported separately.

## 7. Executable evidence

- `tests/test_target_tasks.py`: independent Fraction elimination, exhaustive DFR
  subsets, saturated-kernel and illegal-image counterexamples, integer witness
  checks, finite open-walk reconstruction and alternate trees, and search bounds.
- `tests/test_target_explanation.py`: target-image rank monotonicity and agreement
  with the difference of two existing hidden-history analyses across DFR and the
  $C_3\vee C_5$ wedge, exact $\alpha$ boundaries, alternate trees, pure-gradient targets,
  limited horizons, independent core/explanation status, schemas and replay.
- `tests/test_dfr_application.py`: support and stationary law for a known generator $Q$, direct
  simulation against an independent two-state matrix exponential, reproducible
  seeds, whole-trajectory pairing, full-grid ambiguity, feature separation,
  train-only baseline fitting, tampering/identity failures, point semantics,
  exact reconstruction, prediction replay and CLI behavior.

Run `python -W error -m unittest discover -s tests -v` after source installation.
The [application tutorial](SCIENTIFIC_ML.md) reproduces the fixed-data measurements.
