# Rate-dependent critical experiment

On a four-state ring, a pair of snapshots at opposite vertices reveals that
a crossing occurred, but two equally short routes connect those vertices.
Faster clockwise motion favors one route. An extra cycle counter may resolve
the remaining history ambiguity even though the snapshots alone cannot.

The `critical` task makes these two effects explicit. With a known graph,
strictly positive directed rates, layer $m$, and intensity $\theta$, it
constructs the exact path catalogue and the theorem-derived marked-Poisson
experiment for

$$
T\delta^{m-1}\longrightarrow\theta.
$$

The topology-only `analyze` task locates the exposure layers; `critical` adds
the path weights and the rule for conditioning on the available readout.
The result specifies a limit experiment. An exact posterior at finite $(T,\delta)$
requires a separate calculation.

## Run the example

Run these commands from the repository root with the virtual environment
activated. Without activation, use the platform-specific executable paths in
the [installation instructions](../README.md#install-from-a-source-checkout).

```console
$ homological-observability critical examples/biased_c4_critical.json
$ homological-observability critical examples/biased_c4_critical.json --format json
```

The compact view reports:

```text
Critical homological observability: biased-c4-critical
status: COMPLETE
artifact role: fresh-critical-experiment
layer: 2
theta: 1
directed paths: 16
homology rank: 1
aggregated weights: 12
critical catalogue empty: false
common compound-Poisson intensity: 0
critical endpoint intensity: 5/2
```

The complete deterministic result is preserved as
[`biased_c4_critical_result.json`](../examples/biased_c4_critical_result.json).

## Model and rates

The example is a four-cycle

$$
v0\longrightarrow v1\longrightarrow v2\longrightarrow v3\longrightarrow v0
$$

with rate $2$ in the displayed direction and rate $1$ in the reverse
direction. Both directed rates are present on every undirected edge, so the
chain is irreducible. Translation symmetry gives the exact stationary law

$$
p(v0)=p(v1)=p(v2)=p(v3)=\frac14,
$$

even though the dynamics is not reversible. The integer readout has
coefficient $1$ on the oriented edge $v0\to v1$ and coefficient $0$ on the
other edges in their reference orientations.

The full input is
[`biased_c4_critical.json`](../examples/biased_c4_critical.json). Rates and
$\theta$ are exact values, not binary floating-point approximations.

## Where the probabilities come from

For a walk $\gamma=(x_0,\ldots,x_m)$ of length $m$, the catalogue records the
leading weight

$$
W(\gamma)=\frac{1}{m!}\prod_{j=0}^{m-1}q_{x_jx_{j+1}}.
$$

At $m=2$, the ordered endpoints $(v0,v2)$ have two shortest paths. The
lexicographically selected reference path is $v0\to v1\to v2$; it has mark
$0$ and weight

$$
\frac{2\cdot2}{2!}=2.
$$

The alternative $v0\to v3\to v2$ differs by one cycle direction. In the
reported Smith coordinates its mark and visible mark are both $-1$, and its
weight is

$$
\frac{1\cdot1}{2!}=\frac12.
$$

In the critical limit, conditioning on this ordered endpoint gives the exact
mark law

$$
\Pr(0\mid v0,v2)=\frac45,
\qquad
\Pr(-1\mid v0,v2)=\frac15.
$$

The factor of four comes from two clockwise rate factors, each twice its
counterclockwise counterpart. Equal rates would instead give equal route
weights. These are conditional path-mark probabilities before applying the
extra readout, not the final history-recovery probabilities.

The associated Poisson intensity is

$$
\theta p(v0)\left(2+\frac12\right)=\frac58.
$$

There are four ordered antipodal endpoint pairs, so their total intensity is
$4(5/8)=5/2$. The zero mark remains part of each conditional critical-endpoint
law. By contrast, zero marks are excluded from the common-endpoint Lévy
measure; in this example no nonzero common-endpoint mark remains, so its total
intensity is zero.

## What the counter changes

The supplied readout counts signed crossings of $v0\to v1$. After the known
endpoint correction, it measures the ring's sole integer cycle coordinate.
The induced readout is injective and the reported `hidden_kernel` is the
trivial group. Consequently the two route weights above do not imply a
residual 20% error after using all the observations: the exact side readout
already determines the accumulated cycle target.

Remove the counter to study the ambiguity left by snapshots alone:

```python
import json
from pathlib import Path

import homological_observability as ho

payload = json.loads(Path("examples/biased_c4_critical.json").read_text())
for label, readouts in (
    ("with cycle counter", payload["readouts"]),
    ("snapshots only", []),
):
    request = {**payload, "readouts": readouts}
    result = ho.analyze_critical_model(ho.parse_critical_model(request))
    document = ho.critical_experiment_to_dict(result)
    print(label, document["groups"]["hidden_kernel"])
```

The hidden free rank changes from zero to one. The physical rates, stationary
law, and total critical endpoint intensity $5/2$ stay the same; what changes
is how much of the accumulated mark the observations reveal. Each antipodal
endpoint count is visible in the snapshot record. Conditional on those counts,
the unresolved routes supply the random marks. Averaging out the counts would
discard information the observer actually has.

Together, the rate comparison and counter comparison separate two questions:
how likely competing histories are, and which of them the records distinguish.

## Read the JSON result

| Object | Meaning |
| --- | --- |
| `model` | Normalized graph, readouts, exact directed rates, layer, $\theta$, and limits |
| `topology` | Topology analysis and its requested/natural completeness flags |
| `groups` | Smith presentations of $L_m/L_{m-1}$, the visible quotient, the hidden kernel, and the induced readout |
| `stationary_law` | Exact rational generator and stationary probabilities |
| `catalogue` | Reference geodesics and weights aggregated by ordered endpoint and graded mark |
| `limit_experiment` | Common compound-Poisson and critical conditional-mark components |
| `resources` | Declared ceilings and measured usage |
| `limit` | Resource boundary for `LIMIT_REACHED`, otherwise `null` |

The geodesics and individual Smith coordinates are representation-dependent.
Changing a reference geodesic translates every mark for the same ordered
endpoint by a fixed group element; the exact path weights do not change.
Quotient ranks, torsion factors, the induced readout, and the resulting law
under the declared convention are the stable scientific content.

## Python API

The Python API uses the same model and result objects as the command-line tool:

```python
from fractions import Fraction

import homological_observability as ho

model = ho.load_critical_model("examples/biased_c4_critical.json")
result = ho.analyze_critical_model(model)
payload = ho.critical_experiment_to_dict(result)

assert result.status is ho.CriticalStatus.COMPLETE
assert payload["stationary_law"]["probabilities"] == ["1/4"] * 4
assert payload["summary"]["critical_total_intensity"] == "5/2"
assert Fraction(
    payload["limit_experiment"]["critical_endpoint_components"][0]["poisson_intensity"]
) == Fraction(5, 8)
```

JSON decimals are parsed exactly, and rational strings such as `"5/8"` are
accepted. Direct Python construction accepts integers, `Decimal`, `Fraction`,
or canonical exact strings; binary `float` values are rejected. Exact decimal
records must fit the [model representation boundary](MODEL_GUIDE.md#critical-settings).

## Completeness and resource limits

`COMPLETE` for this task means that the requested layer, its entire directed
path catalogue, exact weights, and limit experiment were constructed. The
separate `natural_filtration_complete` flag states whether the topology has
already exposed all of $H_1(G;\mathbb Z)$. A critical experiment can therefore
complete at a requested layer before the natural topology filtration ends.

The five limits bound directed paths, a preflight estimate of rational digit
growth, the observed digits in exact public values, the observed
public record count, and topology cycle enumeration. The preflight estimate has
its own `max_estimated_integer_digits` budget; `max_integer_digits` and
`max_output_records` are exact ceilings and do not inherit the preflight
estimate. If a ceiling is exceeded, the task returns `LIMIT_REACHED` atomically:
no partial groups, catalogue, stationary law, or marked-Poisson object is
presented as complete. Set `audit_paths` to `true` only when individual records
for walks of length $m$ are needed; the default aggregated catalogue is the
more compact result. This option reduces public output, while the
internal construction still enumerates all requested paths.

## Interpretation boundary

The result is an exact construction of the paper's critical-limit generative
specification from a known model. It provides the limiting mark laws and the
rule for conditioning a total-mark law on an observed visible residue. It is
not a trajectory simulation, an empirical fit, an unconditional critical MAP
solver, a finite-sample error guarantee, or an expanded probability table over
the generally infinite total-mark support.

For topology-only inputs, begin with the
[wedge C3–C5 example](END_TO_END_EXAMPLE.md). The complete field definitions
are in the [model guide](MODEL_GUIDE.md) and [output contract](OUTPUT_CONTRACT.md),
and the implementation-to-paper chain is recorded in the
[paper map](../PAPER_MAP.md).
