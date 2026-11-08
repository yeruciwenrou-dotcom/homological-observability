# Target observability: technical derivation

This technical note supports the target diagnosis and readout design interfaces
and the Scientific ML application. It extends the software's implementation of
[Stochastic Histories at Finite Temporal Resolution: Homological Observability
and Information Phase Diagrams in Markov Jump Processes](https://doi.org/10.5281/zenodo.23424849).
The paper supplies the exposure filtration and hidden-history entropy law.
The target-image, conditional-entropy and measurement-design arguments below
are derived here for these software interfaces.

## 1. Full cycle group, sufficiency and certificates

Let a finite connected simple undirected support graph have a positive transition
rate in both directions along each edge. Fix one orientation of each edge and a
spanning tree. Its fundamental-cycle columns B identify the integer cycle group
H with Z^b, where b=|E|−|V|+1. An integer cochain integrates signed edge counts;
write P:H→Z^k for fixed readouts and F:H→Z^q for the targets.

All targets are determined by P on the full cycle group exactly when

```math
\ker_{\mathbb{Z}}P\subseteq\ker_{\mathbb{Z}}F
\quad\Longleftrightarrow\quad
\mathrm{rank}_{\mathbb{Q}}P=
\mathrm{rank}_{\mathbb{Q}}\begin{bmatrix}P\\F\end{bmatrix}.
```

For the forward direction, every rational vector in ker P becomes an integer
kernel vector after multiplication by a common denominator. Thus F annihilates
the rational kernel, so its rows lie in P's rational row span. Conversely, that
row-span condition gives a rational matrix D with DP=F; Pz=0 implies Fz=0.
The code verifies DP=F exactly before returning the decoder. If ranks differ,
a saturated integer kernel basis has a column z with Fz nonzero. Returning z,
Bz and Fz witnesses the insufficiency; the product verifies Pz=0 and Fz≠0.

The rank criterion concerns **all** possible records and trajectories under this
support. A particular finite observation can carry extra incidental restrictions.
The universal guarantee is the task exposed by `analyze_target`. No simple-cycle
enumeration is required for this decision. A spanning-tree change is an integral
unimodular coordinate change, preserving the criterion and physical cochains.

## 2. Legal integer images and open trajectories

A rational decoder is defined on the legal integer image P(H). The evaluator
first solves Pc=p over Z via a verified Smith decomposition U P V=S. Divisibility
by each nonzero diagonal entry and vanishing of every residual row are necessary
and sufficient for membership. It constructs and verifies an integer preimage.
For example P=2x, F=x permits p/2 for even p. With P=2I2, F=(1,1), p=(1,1),
the formula's integer result 1 does not make the input record legal.

An open walk chain x from s to t is not itself a cycle. Let h(s,t) be the tree
path with the same boundary. Then x−h=Bc for a unique integer c. For raw cochain
matrices A and G, the evaluator uses

$$
p'=Ax-Ah=Pc,\qquad Gx=D p'+Gh,\qquad P=AB,\ F=GB.
$$

Known endpoints therefore retain pure-gradient targets, whose cycle restriction
is zero. `record_kind="cycle"` already uses corrected coordinates and returns Fc;
it forbids endpoints so the two meanings are not mixed.

## 3. The exact target ambiguity image

For a legal p choose c0 in H with Pc0=p. The entire integer solution set is
c0+K, where K=ker_Z P. Consequently the target set is precisely

$$
F(c_0)+M,\qquad M=F(K).
$$

Both inclusions follow directly by subtracting c0 or adding a kernel vector.
The choice of c0 changes the representative but leaves the coset unchanged.
Open-path targets add the known tree-path term. The kernel must be saturated:
independently clearing denominators in rational-nullspace columns can generate
only a proper sublattice. For P=(2,1,1), F=(0,1,0), the true image M is Z;
a naive basis can incorrectly return 2Z. The Smith-based kernel and Hermite image
backend preserve this information. A generic public coset object is deferred.

For DFR, W=W_ON+W_OFF and DeltaW=W_ON−W_OFF, so DeltaW≡W (mod 2).
At fixed W the image is 2Z: a unit ON circulation and a reverse OFF circulation
preserve W while changing DeltaW by 2. These loops can be connected by opposite
traversals of a bridge, which cancel in every cochain. For endpoints 0→3 the
walks [0,3] and [0,1,2,0,3,5,4,3,0,3] have W=0 and DeltaW 0 and 2.
The packaged pressure case completes all their transitions before the first
positive snapshot time; every snapshot, including endpoints, agrees.

## 4. Target-image filtration and entropy

Use the paper's integer exposure filtration L_m. The existing backend constructs
it from simple cycles of length at most 2m. Define

$$
K_P^m=L_m\cap\ker P,\qquad
K_{P,F}^m=L_m\cap\ker P\cap\ker F,\qquad M_m=F(K_P^m).
$$

Restriction of F gives a short exact sequence
0→K_(P,F)^m→K_P^m→M_m→0. Ranks therefore add at each m. Nested L_m imply
nested K_P^m and M_m, so the graded target rank

$$
g_m=\mathrm{rank}M_m-\mathrm{rank}M_{m-1}
=r_P^m-r_{P,F}^m\geq0
$$

is nonnegative. Here r denotes the corresponding hidden graded free rank.
The implementation constructs the integer images, verifies lattice inclusion,
and checks this rank identity. Torsion or finite-index parity information is not
represented by a rank alone and does not contribute a log(T) leading coefficient.

Let C be the latent integer cycle history, S the snapshots and PC the observed
cochain record. Since FC is a function of C, the conditional entropy chain rule is

$$
H(FC\mid S,PC)=H(C\mid S,PC)-H(C\mid S,PC,FC)
=R_P-R_{(P,F)}.
$$

Under the original paper's fixed finite connected bidirectional positive-rate
model, stationary-law and regular long-time sampling assumptions, apply its
hidden-history asymptotic to both terms on the **same** model and sampling
sequence. For delta=T^(−alpha), the resulting target coefficient is

$$
H(FC\mid S,PC)=
\frac12\sum_{m\geq2}g_m[1-\alpha(m-1)]_+\log T+O(1).
$$

At a layer carrying target rank, the critical alpha is 1/(m−1). A zero leading
coefficient alone does not establish deterministic reconstruction or a zero
finite-time error; critical layers and O(1) terms still matter. Finite input
T,delta yields exposure scales T delta^(m−1), not a prediction success probability.
These are distinct from the exact full-group criterion in section 1.

The program reports a global coefficient only when the computed exposure lattice
has reached H. An explicitly shorter horizon returns a prefix coefficient and
`PARTIAL_HORIZON`. The default natural horizon is ceil(|V|/2). Cycle, matrix,
integer-size and cooperative time budgets can stop optional explanation after
the core certificate; its status is independent. Explanations attached to design
refer to the **fixed** readouts before additions. Re-run analysis with a chosen
solution's channels to explain its residual target layers.

## 5. Minimum additional scalar channels

P0 is fixed. Candidate rows have unique physical IDs; distinct instruments with
equal cochains remain distinct choices. For each subset J test sufficiency of
[P0;P_J]. If P0 already suffices, the empty addition is optimal. If the entire
pool fails, no subset can succeed by monotonicity. Otherwise search cardinalities
in increasing order. Exhausting all smaller sizes before the first success proves
global cardinality minimality. Exhausting the successful size establishes all
ties. Constructing each returned certificate is a separate operation.

Thus feasibility, minimum proof, tied-set enumeration, output truncation and
certificate completion have independent fields. Stopping mid-size retains
established lower/upper bounds and any proven minimum. A count of discovered ties
is the total only when that size's enumeration is complete. This optimizes the
number of scalar channels, not hardware costs, noise or numerical conditioning.
A direct target counter is valid and may be the best choice when all events are
available; the task adds value for fixed or restricted records and shared targets.

## 6. Equal-input prediction reference

On the constructed equal-weight pair with targets 0 and 2, a deterministic
function of the identical visible input returns a common real a. Its mean
absolute error obeys (|a|+|2−a|)/2≥1 by the triangle inequality. It can equal at
most one target, giving exact-match accuracy ≤1/2. Random predictors independent
of the hidden label satisfy the same bounds in expectation. Separate sampled
random outputs need not satisfy an empirical two-row bound.

A conditional mean of 1 is legitimate despite the realized targets' even parity.
The evaluation adapter keeps mean/real-point/integer-realized semantics separate,
preserves original values, and scores any explicitly rounded version separately.
The natural CTMC sample and constructed pressure population are scored separately;
no natural-population risk bound is inferred from the balanced construction.

## 7. Executable evidence

- `tests/test_target_tasks.py`: independent Fraction elimination, exhaustive DFR
  subsets, saturated-kernel and illegal-image counterexamples, integer witness
  checks, finite open-walk reconstruction and alternate trees, and search bounds.
- `tests/test_target_explanation.py`: target-image rank monotonicity and agreement
  with the difference of two existing hidden-history analyses across DFR and the
  C3–C5 wedge, exact alpha boundaries, alternate trees, pure-gradient targets,
  limited horizons, independent core/explanation status, schemas and replay.
- `tests/test_dfr_application.py`: known-Q support and stationary law, direct
  simulation against an independent two-state matrix exponential, reproducible
  seeds, whole-trajectory pairing, full-grid ambiguity, feature separation,
  train-only baseline fitting, tampering/identity failures, point semantics,
  exact reconstruction, prediction replay and CLI behavior.

Run `python -W error -m unittest discover -s tests -v` after source installation.
The [application tutorial](SCIENTIFIC_ML.md) reproduces the fixed-data measurements.
