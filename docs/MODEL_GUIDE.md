# Model guide

The package accepts two input formats. `analyze` needs graph
topology and optional integer readouts; `critical` additionally needs every
positive directed rate, a selected layer, and a critical intensity. Fields
are checked against the format required by the selected command.

## From a physical model to an input

Choose vertices for the states resolved by the snapshot detector and edges
for the allowed bidirectional transitions. A cyclic state sequence represents
a possible circulation of the system. The graph should describe the effective
Markov jump model on the timescale of interest.

An extra counter is represented by its signed increment on each oriented edge:
coefficient `1` adds one on a forward crossing and subtracts one on the reverse
crossing; coefficient `0` leaves the counter unchanged. Integer weights allow
several transitions to contribute to one cumulative reading. For open paths,
a known endpoint correction relates this edge reading to the cycle readout.
The `readouts` field specifies what a counter measures, not a measured value
or a time series. An empty list means that only the vertex snapshots are used.

For finite-scale interpretation, choose a fixed rate unit $q_0$ and enter
$q_0T$ as `observation_time` and $q_0\delta$ as `sampling_interval`.
For a critical model, express each rate as $q_{xy}/q_0$ and use the same
normalization for $\theta$. The program has no units field and performs no
automatic unit conversion. The graph-only filtration needs rate support,
whereas the critical path weights also need the rate magnitudes.

The [wedge example](END_TO_END_EXAMPLE.md#compare-observation-choices) shows
how to compare counters; the [critical example](CRITICAL_EXPERIMENT.md)
shows how to add exact rates.

## Topology analysis model

The `analyze` command reads a UTF-8 JSON document with
`schema_version: 1`. The bundled machine-readable schema is available through
`homological_observability.load_model_schema()` and at
[`src/homological_observability/schemas/model.schema.json`](../src/homological_observability/schemas/model.schema.json).

## Minimal model

```json
{
  "schema_version": 1,
  "name": "triangle",
  "vertices": ["a", "b", "c"],
  "edges": [["a", "b"], ["b", "c"], ["a", "c"]]
}
```

The graph must be finite, connected, undirected, and simple. Vertices are
nonempty unique strings. Every edge contains exactly two known, distinct
vertices. Repeating an undirected edge in either orientation is an error.

For the paper's continuous-time Markov interpretation, an undirected edge
means that both directed transition rates are positive. Their numerical values
are unnecessary for the exact filtration and therefore are not accepted by
this model. A one-way or zero-rate edge requires a different,
dynamics-aware support contract.

The parser rejects unknown fields so a misspelling cannot silently change the
scientific request.

## Complete structure

```json
{
  "schema_version": 1,
  "name": "wedge-c3-c5-visible-index-two",
  "vertices": ["o", "a1", "a2", "b1", "b2", "b3", "b4"],
  "edges": [
    ["o", "a1"],
    ["a1", "a2"],
    ["a2", "o"],
    ["o", "b1"],
    ["b1", "b2"],
    ["b2", "b3"],
    ["b3", "b4"],
    ["b4", "o"]
  ],
  "readouts": [
    {
      "name": "pi",
      "coefficients": [
        {"edge": ["a1", "a2"], "coefficient": 2},
        {"edge": ["b1", "b2"], "coefficient": 1}
      ]
    }
  ],
  "analysis": {
    "max_layer": 3,
    "max_cycles": 100000,
    "alpha": 0.5
  }
}
```

The repository copy is
[`examples/wedge_c3_c5.json`](../examples/wedge_c3_c5.json).

## Field reference

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | Input contract version; must be `1` |
| `name` | yes | Nonempty model label propagated into results |
| `vertices` | yes | Unique nonempty string identifiers |
| `edges` | yes | Undirected simple edges, each written as two vertex strings |
| `readouts` | no | Named integer edge 1-cochains; default is none |
| `analysis` | no | Resource and sampling settings; default is `{}` |

## Readouts

Each readout has a unique nonempty name and a list of edge coefficients. Only
nonzero coefficients need to be supplied. Coefficients are integers; booleans,
floats, numeric strings, and automatic rounding are rejected. Public
`IntegerReadout` and `GraphModel` constructors enforce these invariants as
well. Direct construction requires canonical immutable tuples; use
`IntegerReadout.from_mapping` and `GraphModel.create` to normalize input
orientations and ordering.

An input edge is oriented. Internally, every undirected edge is oriented from
the lexicographically smaller vertex name to the larger one. If a coefficient
is supplied in the reverse direction, its sign is reversed during
normalization. The same undirected edge may occur at most once within a
readout.

Several readouts produce a map into $\mathbb Z^q$, with one output coordinate per
readout in the listed order.

## Analysis settings

| Setting | Constraint | Effect |
| --- | --- | --- |
| `max_layer` | positive integer | Highest requested filtration layer |
| `max_cycles` | positive integer | Maximum complete simple-cycle catalogue size |
| `alpha` | finite number, at least zero | Evaluate asymptotic regimes under $\delta=T^{-\alpha}$ |
| `observation_time` | finite positive number | Set $T$ for finite-scale $\lambda_m$ values |
| `sampling_interval` | finite positive number | Set $\delta$ for finite-scale $\lambda_m$ values |

`observation_time` and `sampling_interval` must appear together. The pair is
mutually exclusive with `alpha` because the two requests have different
interpretations.

`max_layer` bounds the path-exposure calculation; it does not set the
detector's time resolution. Sampling information is supplied separately by
`alpha` or the time/interval pair.

Sampling parameters are converted to binary `float`. Phase classification uses
the exact value of that float in $1-(m-1)\alpha$, with equality reserved for
zero. For example, Python's `1/3` is slightly below the exact layer-four
threshold; its phase is `DENSE`, while the next larger float is `SPARSE`.
The result also reports the exact rational threshold for reference.

Finite-scale exposure is evaluated from the binary inputs before rounding the
result to float, so intermediate overflow or underflow does not lose an
otherwise representable value. A nonzero result outside the float range raises
`ValueError` in Python and exits with code 2 in either CLI output format.

If `max_layer` is absent, the kernel computes through $\lceil |V|/2\rceil$. If
`max_cycles` is absent, enumeration is unbounded by the application. Supplying
an explicit budget is recommended for unfamiliar graphs.

A smaller `max_layer` limits the scientific horizon. The result is
`PARTIAL_HORIZON` unless the computed exposure lattice already equals all of
$H_1(G;\mathbb Z)$. In that state the requested layers are exact, but higher
layers may still expose additional directions.

## Run and inspect a model

```console
$ homological-observability analyze examples/wedge_c3_c5.json
$ homological-observability analyze examples/wedge_c3_c5.json --format json
```

Use JSON when processing results in another program. The terminal layout is
intended for people and should not be parsed as a data format.

The Python API equivalent is:

```python
import homological_observability as ho

model = ho.load_model("examples/wedge_c3_c5.json")
result = ho.analyze_model(model)
payload = ho.analysis_to_dict(result)

assert payload["schema_name"] == "homological-observability.analysis"
assert payload["status"] == "COMPLETE"
assert payload["summary"]["natural_filtration_complete"] is True
```

## Validation layers

The JSON Schema checks document shape, primitive types, required pairs, and
mutual exclusion of sampling modes. Runtime validation additionally checks
properties that JSON Schema cannot conveniently establish here, including
connectivity, edge endpoints, undirected duplicates, unique readout names, and
unknown readout edges.

Invalid JSON or an invalid model exits with code 2 and a concise error without
a traceback. A completed restricted horizon emits `PARTIAL_HORIZON` and exits
with code 0. Exceeding `max_cycles` is different: it is a valid request that
could not be completed within the resource budget, so the command emits
`LIMIT_REACHED` and exits with code 1.

## Normalization and provenance

Results include the normalized model and its SHA-256 digest. The digest is
computed from canonical JSON after sorting vertices and edges, normalizing edge
orientations and readout signs, and validating numeric settings. It is
independent of input whitespace and file location.

Two syntactically different files that normalize to the same model therefore
receive the same digest. The original input bytes are not embedded in the
result.

## Critical experiment model

The `critical` command reads a JSON document with `schema_version: 1` under a separate schema:
[`critical-model.schema.json`](../src/homological_observability/schemas/critical-model.schema.json).
It is available in Python through `load_critical_model_schema()`.

The complete example is
[`examples/biased_c4_critical.json`](../examples/biased_c4_critical.json). Its
top-level fields are:

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | Critical input contract version; must be `1` |
| `name` | yes | Nonempty model label propagated into the result |
| `vertices`, `edges` | yes | The same connected undirected simple support accepted by `analyze` |
| `readouts` | yes | Integer edge cochains; use an empty array when none are present |
| `rates` | yes | One strictly positive exact rate for each direction of every support edge |
| `critical` | yes | Layer, intensity, resource limits, and path-audit choice |

Every undirected support edge requires two directed rate records. Missing,
extra, duplicated, zero, or negative rates are rejected. This allows
nonreversible dynamics while preserving the bidirectional positive-support
assumption.

### Exact scalar values

In a JSON file, rates and `critical.theta` may be integer or decimal numeric
tokens, canonical decimal strings, or rational strings such as `"5/8"`.
Decimals are parsed without converting them through binary floating point, and
normalized results serialize all exact scalars as reduced rational strings.

Direct Python construction accepts `int`, `Decimal`, `Fraction`, or canonical
exact strings. It rejects `float`, including apparently simple values such as
`0.5`, because their exact binary value is not the declared scientific input.

### Critical settings

| Setting | Constraint | Effect |
| --- | --- | --- |
| `layer` | integer at least 2 | Selects $L_m/L_{m-1}$ and the directed path catalogue at length $m$ |
| `theta` | positive exact scalar | Sets the limit intensity for $T\delta^{m-1}\to\theta$ |
| `audit_paths` | boolean | Includes every individual path record when `true`; otherwise emits aggregated weights only |
| `limits.max_paths` | positive integer | Bounds the exact number of directed walks of length $m$ |
| `limits.max_estimated_integer_digits` | positive integer | Admission budget for the deterministic preflight estimate of rational digit growth |
| `limits.max_integer_digits` | positive integer | Exact ceiling for numerator and denominator digits in the public inputs and result |
| `limits.max_output_records` | positive integer | Exact ceiling for the public catalogue and limit-experiment record count |
| `limits.max_cycles` | positive integer | Bounds the topology simple-cycle catalogue used at the selected layer |

All five limits are required in JSON so a critical request always carries an
explicit resource policy. The preflight digit estimate may reject a request
before exact construction even when its eventual public values would satisfy
the exact ceiling; it is separate from `max_integer_digits`, which is checked
against observed exact values.
The exact digit count includes integer readouts, group invariants and orders,
induced maps, path and visible marks, scientific counts, rational weights and
total intensities. Resource-policy values, hashes and other provenance metadata
are excluded. Oversized inputs can be rejected before constructing the experiment.

Exact model integers and rational components must fit a decimal record of at
most 4300 digits (or the active Python conversion limit when lower).
`max_integer_digits` cannot exceed this representation ceiling. Out-of-range
model values are rejected at construction as input errors; accepted values
that exceed a computational budget produce atomic `LIMIT_REACHED` results.
For decimal inputs, the reduced decimal exponent is bounded before conversion
to a fraction; a rational string's two components are bounded before parsing.
See [numerical boundaries](NUMERICS.md#sampling-and-exact-resource-values).
`max_output_records` is also checked against the observed result rather than a
preflight estimate. `audit_paths: false` is recommended unless individual
walk-level reconstruction is needed.

### Run and inspect a critical model

```console
$ homological-observability critical examples/biased_c4_critical.json
$ homological-observability critical examples/biased_c4_critical.json --format json
```

The Python API equivalent is:

```python
import homological_observability as ho

model = ho.load_critical_model("examples/biased_c4_critical.json")
result = ho.analyze_critical_model(model)
payload = ho.critical_experiment_to_dict(result)

assert payload["schema_name"] == "homological-observability.critical-experiment"
assert payload["status"] == "COMPLETE"
assert payload["summary"]["critical_total_intensity"] == "5/2"
```

`COMPLETE` means the requested layer and its full critical experiment were
constructed. It does not by itself say that the graph's natural topology
filtration has ended; read `topology.natural_filtration_complete` separately.
A resource ceiling produces `LIMIT_REACHED`, a null catalogue and limit
experiment, and exit code 1. Invalid input produces the controlled error
contract and exit code 2.

The [rate-dependent critical guide](CRITICAL_EXPERIMENT.md) explains how the
example's exact path weights become its conditional mark laws and Poisson
intensities.
