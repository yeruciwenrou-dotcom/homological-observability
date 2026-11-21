# Rate-dependent critical experiment

On a four-state ring, a pair of snapshots at opposite vertices reveals that
a crossing occurred, but two equally short routes connect those vertices.
Faster clockwise motion favors one route. An extra cycle counter may resolve
the route ambiguity left by the snapshots.

The `critical` task makes these two effects explicit. With a known graph,
strictly positive directed rates, layer $m$, and intensity $\theta$, it
constructs the exact path catalogue and the theorem-derived marked-Poisson
experiment for

$$
T\delta^{m-1}\longrightarrow\theta.
$$

The topology-only `analyze` task locates the exposure layers; `critical` adds
the path weights and the rule for conditioning on the available readout.
To estimate the target posterior at finite $(T,\delta)$, pass the measured record
and directed rates to the [finite-record solver](FINITE_RECORDS.md#use-your-own-model).

## Run the example

The input file [`examples/biased_c4_critical.json`](../examples/biased_c4_critical.json)
comes with the [source checkout](../README.md#full-verification-from-source).
After [installation](../README.md#install), activate the environment and run
these commands from the repository root. For the archived 2.0.0 source, use its [versioned installation guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v2.0.0/README.md#install).

```sh
homological-observability critical examples/biased_c4_critical.json
homological-observability critical examples/biased_c4_critical.json --format json
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

with rate 2 in the displayed direction and rate 1 in the reverse
direction. Both directed rates are present on every undirected edge, so the
chain is irreducible. Translation symmetry gives the exact stationary law

$$
p(v0)=p(v1)=p(v2)=p(v3)=\frac14,
$$

even though the dynamics is not reversible. The integer readout has
coefficient 1 on the oriented edge $v0\to v1$ and coefficient 0 on the
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

At $m=2$, two shortest paths connect the ordered endpoints $(v0,v2)$. The
catalogue selects the clockwise path as its lexicographic reference. The table shows marks
in the reported Smith coordinates and probabilities conditional on those
endpoints in the critical limit.

| Route | Mark | Leading weight | Conditional probability |
| --- | ---: | ---: | ---: |
| $v0 \to v1 \to v2$ (clockwise) | 0 | $2 \cdot 2 / 2! = 2$ | $4/5$ |
| $v0 \to v3 \to v2$ (counterclockwise) | −1 | $1 \cdot 1 / 2! = 1/2$ | $1/5$ |

Here the visible mark equals the mark on both routes. Normalizing the two
weights gives the endpoint-only probabilities in the last column. The
clockwise route is four times as likely because each of its jumps has twice
the reverse rate. With equal rates the two routes are equally likely.

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
trivial group. Using the exact side readout therefore determines the accumulated
cycle target, resolving the route ambiguity present in the endpoint-only law.

Remove the counter to study the ambiguity left by snapshots alone:

```python
import json
from decimal import Decimal
from pathlib import Path

import homological_observability as ho

payload = json.loads(
    Path("examples/biased_c4_critical.json").read_text(), parse_float=Decimal
)
for label, readouts in (
    ("with cycle counter", payload["readouts"]),
    ("snapshots only", []),
):
    request = {**payload, "readouts": readouts}
    result = ho.analyze_critical_model(ho.parse_critical_model(request))
    document = ho.critical_experiment_to_dict(result)
    print(label, document["groups"]["hidden_kernel"])
```

The `Decimal` parser preserves exact JSON decimal values when adapting this
example to your own rates. The hidden free rank changes from zero to one.
The physical rates, stationary
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

## Use your own rates and counters

Start from `examples/biased_c4_critical.json`, update its `name`, replace the
graph and its two directed rates per edge, then specify the counters, selected
layer, intensity, and resource limits. The [model guide](MODEL_GUIDE.md#critical-experiment-model)
defines these fields; the [output contract](OUTPUT_CONTRACT.md#critical-experiment-document)
explains the exact result.

The result is a critical-limit generative specification: it gives the limiting
mark laws and their conditioning rule. Obtaining a posterior or error
probability at a specified finite observation time requires a further
calculation. See the [scientific scope](SCIENTIFIC_SCOPE.md) for the supported
observation model and the specialized finite-cycle tools.

For a question about which counters distinguish more histories, use a
[configuration study](COMPARISON_GUIDE.md). The
[wedge C3–C5 example](END_TO_END_EXAMPLE.md) explains the exposure layers
without specifying rates; the [paper map](../PAPER_MAP.md) gives the
theoretical sources for both calculations.
