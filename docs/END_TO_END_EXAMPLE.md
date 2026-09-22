# End-to-end example: a wedge of C3 and C5

This example follows a complete analysis from graph input to phase
interpretation. One cycle appears earlier than the other, the visible image
changes by finite index without changing real rank, and a hidden free
direction appears at the same layer.

## Network and readout

The graph is the wedge $C_3\vee C_5$: a triangle and a five-cycle share the
vertex `o`.

![The wedge of C3 and C5, with the two nonzero coefficients of the integer side readout highlighted.](wedge_c3_c5.svg)

Its first Betti number is two. Let $e_3$ and $e_5$ denote the triangle and
five-cycle coordinates. The integer side readout is chosen so that

$$
\pi(e_3)=2,
\qquad
\pi(e_5)=1.
$$

In the deterministic homology basis, these values are represented by the
matrix $P=[\pi]_{\mathcal B}$. The abstract object reported in scientific
statements is the image $\pi(L_m)$; $P$ is its auditable coordinate
representation.

The complete input is
[`examples/wedge_c3_c5.json`](../examples/wedge_c3_c5.json). It requests layers
through three, a cycle budget of `100000`, and the asymptotic exponent
$\alpha=1/2$ through the field `alpha`. Although the graph-size natural horizon
is four, layer three already exposes all of $H_1(G;\mathbb Z)$, so the result is
certified `COMPLETE`.

## Analysis at a glance

| Step | Computed object | Result in this example |
| --- | --- | --- |
| Validate the network | Connected simple graph and normalized edge cochains | $C_3\vee C_5$ with one integer readout |
| Construct homology | $\Lambda=H_1(G;\mathbb Z)$ | $\Lambda\cong\mathbb Z^2$ with coordinates $e_3,e_5$ |
| Expose short cycles | $L_2$ | $\langle e_3\rangle$ |
| Expose the full graph cycle space | $L_3$ | $\langle e_3,e_5\rangle$ |
| Apply the readout | $\pi(L_m)$ and $K_m$ | Visible index-two change and one hidden free direction |
| Interpret the filtration | Graded quotients and phase data | Visible $\mathbb Z/2\mathbb Z$ at layer three; hidden layer critical at $\alpha=1/2$ |

## Run the example

```console
$ homological-observability example wedge-c3-c5
$ homological-observability example wedge-c3-c5 --format json
```

The first command gives a compact table. The second emits the exact versioned
document stored as
[`examples/wedge_c3_c5_result.json`](../examples/wedge_c3_c5_result.json).
A human-readable summary of the same result is available in
[`examples/wedge_c3_c5_result.md`](../examples/wedge_c3_c5_result.md).

## Layer two: triangle exposure

Simple cycles of length at most four include the triangle but not the
five-cycle. Therefore

$$
L_2=\langle e_3\rangle,
\qquad
\pi(L_2)=2\mathbb Z,
\qquad
K_2=L_2\cap\ker\pi=0.
$$

Relative to the zero previous layer, the exposure and visible quotients each
have free rank one. The visible generator is $2$, not $1$. Retaining that
integer scale is necessary for detecting what changes at the next layer.

## Layer three: five-cycle exposure

At length bound six, the five-cycle becomes available:

$$
L_3=\langle e_3,e_5\rangle=\mathbb Z^2,
\qquad
\pi(L_3)=\langle2,1\rangle=\mathbb Z,
$$

and

$$
K_3=\langle-e_3+2e_5\rangle.
$$

The three graded quotients are

$$
\frac{L_3}{L_2}\cong\mathbb Z,
\qquad
\frac{\pi(L_3)}{\pi(L_2)}\cong\mathbb Z/2\mathbb Z,
\qquad
\frac{K_3}{K_2}\cong\mathbb Z.
$$

### Why real rank is insufficient

Both $\pi(L_2)=2\mathbb Z$ and $\pi(L_3)=\mathbb Z$ span the same
one-dimensional real vector space. A calculation that keeps only real rank
therefore reports rank one at both layers and sees no change.

The integer inclusion $2\mathbb Z\subset\mathbb Z$ has index two. Modulo the
old visible lattice, the final image has two cosets: even and odd. The quotient
$\mathbb Z/2\mathbb Z$ records the newly accessible odd class. It is a
finite-index effect in the graded visible image, not torsion in
$H_1(G;\mathbb Z)$ itself.

### Why the readout misses the hidden direction

The generator of $K_3$ combines the two cycle directions as
$-e_3+2e_5$. The readout sends it to

$$
\pi(-e_3+2e_5)=-2+2=0.
$$

Thus distinct exposed trajectory classes can differ along this integral
direction while producing the same side-readout value. This is the hidden
ambiguity that contributes to the information phase law.

## Phase interpretation

The paper assigns layer $m$ the critical exponent

$$
\alpha_m=\frac{1}{m-1}.
$$

With the requested $\alpha=1/2$:

| Layer $m$ | Hidden graded free rank $d_m$ | Scaling exponent $1-\alpha(m-1)$ | Regime |
| ---: | ---: | ---: | --- |
| 2 | 0 | $1/2$ | `DENSE` |
| 3 | 1 | $0$ | `CRITICAL` |

The new hidden free direction appears exactly at its asymptotic activation
threshold. Its leading logarithmic entropy coefficient is

$$
\frac{d_3}{2}\max\bigl(1-\alpha(3-1),0\bigr)=0.
$$

This zero does not mean that the ambiguity vanishes. At criticality the limit
can retain nontrivial order-one uncertainty; the coefficient records only the
leading growth proportional to $\log T$.

These phase labels apply the paper's asymptotic theorem. They do not estimate a
finite-sample error probability for this graph.

## Read it through the Python API

```python
import homological_observability as ho

model = ho.load_example("wedge-c3-c5")
result = ho.analyze_model(model)
document = ho.analysis_to_dict(
    result,
    artifact_role=ho.ArtifactRole.BUILTIN_EXAMPLE,
)

layer3 = document["filtration"]["layers"][3]
assert layer3["visible"]["graded_quotient"]["torsion_factors"] == [2]
assert layer3["hidden"]["graded_quotient"]["free_rank"] == 1
assert document["phase"]["layers"][1]["regime"] == "CRITICAL"
```

## Change the sampling request

The exact lattices do not depend on $\alpha$, observation time, or sampling
interval. To inspect finite-scale control parameters instead of asymptotic
regimes, remove `alpha` and provide both

```json
{
  "observation_time": 100.0,
  "sampling_interval": 0.1
}
```

inside the `analysis` object. The phase result then reports
$\lambda_2=10$ and $\lambda_3=1$ while leaving regime labels `null`.

## Evidence boundary

This example demonstrates staged exposure, an index-two visible inclusion, a
hidden free direction, and the phase-law translation in one small network. Its
integer statements are exact. Its phase statements are theorem-derived
asymptotic predictions.

This topology-only example does not establish large-graph performance,
numerically prove the general theorem, or determine rate-dependent path
weights. The separate [biased C4 critical experiment](CRITICAL_EXPERIMENT.md)
shows how known exact rates generate one complete critical-limit law. Neither
finite example replaces the manuscript's general proof.
