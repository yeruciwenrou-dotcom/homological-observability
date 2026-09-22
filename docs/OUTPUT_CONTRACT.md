# Output contract

The package returns two immutable result types:
`TopologyAnalysis` for `analyze` and `CriticalExperimentResult` for `critical`.
In each task, the Python API and CLI render the same structured result. JSON is
the format for use by other programs. Terminal text and, for topology
analyses, Markdown provide human-readable output.

## Analysis document identity

Every analysis JSON document begins with:

```json
{
  "schema_name": "homological-observability.analysis",
  "schema_version": 2,
  "software": {
    "name": "homological-observability",
    "version": "1.1.0.dev0"
  },
  "artifact_role": "fresh-analysis",
  "status": "COMPLETE"
}
```

The complete bundled analysis schema is available through
`homological_observability.load_analysis_schema()` and at
[`src/homological_observability/schemas/analysis.schema.json`](../src/homological_observability/schemas/analysis.schema.json).

`schema_version` governs the JSON structure. `software.version` records the
implementation that produced it. Consumers should check both instead of
inferring compatibility from field presence.

## Top-level fields

| Field | Meaning |
| --- | --- |
| `schema_name`, `schema_version` | Schema name and version |
| `software` | Package name and implementation version |
| `artifact_role` | Provenance role of this analysis |
| `status` | `COMPLETE`, `PARTIAL_HORIZON`, or `LIMIT_REACHED` |
| `evidence_categories` | Evidence kinds present in the document |
| `normalized_model_sha256` | Digest of the validated normalized model |
| `model` | Validated, normalized input model |
| `summary` | Summary of basis-independent results |
| `homology` | Auditable basis, readout coordinates, and rank |
| `filtration` | Exact cycles, lattices, and graded quotients, or `null` |
| `phase` | Theorem-derived phase interpretation, or `null` |
| `limit` | Resource-bound details, or `null` |

No creation timestamp is included. Omitting nondeterministic run metadata keeps
the same model and software version byte-stable under sorted JSON rendering.

## Artifact roles

Analysis documents use one of two roles:

| Role | Source |
| --- | --- |
| `fresh-analysis` | A user model passed to `analyze` or the Python API default |
| `builtin-example` | A versioned model selected through the example registry |

Critical experiment documents use
`artifact_role: fresh-critical-experiment`. Their provenance is the normalized
critical model and its digest; the built-in topology example registry is not
used by this task.

The reproduction command emits a separate lightweight document with
`artifact_role: canonical-paper-evidence`. That document describes generated
files and whether the two tables were checked against frozen references; it is
not an analysis result and does not claim the analysis schema name.

Each `files[].sha256` value identifies the exact bytes produced by that run. A
reproduction `PASS` is determined by comparing the generated CSV values with
the frozen references using `rtol=1e-12` and `atol=1e-14`. Platform-dependent
floating-point serialization can change trailing digits and therefore file
hashes without changing the accepted numerical result. These digests are
provenance identifiers, not cross-platform acceptance criteria.

Both the checkout's `results/` tree and the installed package's reference
directory are protected from reproduction writes, including file aliases with
different names. All output paths are checked before the first file is written.
The count-TV intervals include rounding and truncated-tail error; their
calculation and reference calibration are described in [numerical methods](NUMERICS.md).

## Evidence categories

- `EXACT_INTEGER` labels integral basis, kernel, image, Hermite, and Smith
  computations.
- `EXACT_COMBINATORIAL` labels a complete finite simple-cycle or directed-path
  enumeration.
- `EXACT_RATIONAL` labels exact directed-rate products, stationary
  probabilities, path weights, and limit intensities.
- `ASYMPTOTIC_THEOREM` labels quantities obtained by applying the paper's
  phase law.

These categories describe how a field is supported. They are not confidence
levels.

## Topology status and completeness

`COMPLETE` means every requested layer was computed and the natural filtration
is certified complete. Certification occurs when the computed exposure lattice
equals the full integral homology lattice. Computing through
`natural_max_layer` always provides that certification because
`natural_max_layer` is $\lceil \lvert V\rvert/2\rceil$, the graph-size horizon covering
every simple cycle.

`PARTIAL_HORIZON` means every requested layer was computed, but the last
exposure lattice is still a proper sublattice of $H_1(G;\mathbb Z)$. The
reported filtration and phase data are exact within the requested horizon;
higher layers may add cycle directions. This status is not a resource failure.

For both `COMPLETE` and `PARTIAL_HORIZON`, `filtration` and `phase` are objects
and `limit` is `null`.

`LIMIT_REACHED` means simple-cycle enumeration exceeded `max_cycles`. In that
state:

- `homology` and the readout matrix remain valid;
- `filtration` and `phase` are `null`;
- `limit.resource`, `limit.limit`, `complete_components`, and
  `incomplete_components` explain the boundary;
- no truncated lattice is presented as a completed scientific result.

Invalid input is not an analysis state. It produces a controlled error rather
than a result document.

Computed integers must also fit the decimal representation boundary: at most
4,300 digits, or the interpreter's smaller active limit. This covers readout
matrices, lattice bases, quotient invariants, finite group orders, and all other
integer fields in the output document. If any field exceeds that boundary,
`analyze_model` raises `ValueError` before returning a result. The renderers
apply the same check to supplied results and documents. The CLI reports
`ERROR` with exit code `2` in either format; no integer is rounded or truncated.

The `summary` object distinguishes the two notions of completeness:

| Field | Meaning |
| --- | --- |
| `requested_max_layer` | Effective requested horizon; defaults to `natural_max_layer` when `max_layer` is omitted |
| `computed_max_layer` | Last computed layer, or `null` if a resource limit prevented a filtration result |
| `natural_max_layer` | Guaranteed graph-size horizon $\lceil \lvert V\rvert/2\rceil$ |
| `requested_horizon_complete` | Whether every layer through `requested_max_layer` was computed |
| `natural_filtration_complete` | Whether no higher layer can enlarge the exposure, visible, or hidden lattice |

## Process exit codes

| Code | Meaning |
| ---: | --- |
| `0` | Requested topology or critical task completed, or reproduction check passed |
| `1` | A valid topology or critical task hit a resource limit, or reproduction evidence mismatched |
| `2` | CLI usage, file, JSON, model-validation, or controlled execution error |

JSON errors use `schema_name: homological-observability.error`,
`schema_version: 1`, `status: ERROR`, and a message. Terminal errors are written
to standard error. Expected input errors do not print a traceback.

## Bundled schemas

Every public JSON document has a Draft 2020-12 schema bundled in the installed
package:

| Document | Loader | Schema file |
| --- | --- | --- |
| Model input | `load_model_schema()` | [`model.schema.json`](../src/homological_observability/schemas/model.schema.json) |
| Analysis result | `load_analysis_schema()` | [`analysis.schema.json`](../src/homological_observability/schemas/analysis.schema.json) |
| Example registry | `load_examples_schema()` | [`examples.schema.json`](../src/homological_observability/schemas/examples.schema.json) |
| Reproduction result | `load_reproduction_schema()` | [`reproduction.schema.json`](../src/homological_observability/schemas/reproduction.schema.json) |
| Controlled error | `load_error_schema()` | [`error.schema.json`](../src/homological_observability/schemas/error.schema.json) |
| Critical model input | `load_critical_model_schema()` | [`critical-model.schema.json`](../src/homological_observability/schemas/critical-model.schema.json) |
| Critical experiment result | `load_critical_experiment_schema()` | [`critical-experiment.schema.json`](../src/homological_observability/schemas/critical-experiment.schema.json) |

Each loader returns a fresh dictionary, so callers can construct a validator or
adapt a local copy without mutating package state.

## Matrix encoding

Every matrix carries explicit dimensions and row-major data:

```json
{
  "rows": 2,
  "columns": 1,
  "data": [[-1], [2]]
}
```

Lattice generators are columns of `basis_columns`. Explicit dimensions are
required even for zero-column matrices, where `data` contains one empty list
per ambient row.

Matrix entries are exact integers. Floating-point values appear only in the
sampling interpretation.

## Filtration layers

Each layer contains `exposure`, `visible`, and `hidden` lattice objects. A
lattice object records:

- `ambient_rank`;
- lattice `rank`;
- `basis_columns`;
- `graded_quotient` relative to the previous layer;
- `evidence_category`.

Layers 0 and 1 have `graded_quotient: null`. For later layers the quotient has
`free_rank`, `torsion_factors`, `finite_order`, and an exact-integer evidence
label.

Coordinate matrices use the deterministic basis described in
[conventions](CONVENTIONS.md). Ranks and quotient invariants are the
basis-independent mathematical results.

## Phase object

Each phase layer reports exact rational objects for `critical_alpha` and
`snapshot_budget_exponent`:

```json
{
  "numerator": 3,
  "denominator": 2
}
```

When `alpha` was supplied, `scaling_exponent`, `regime`, and entropy
coefficients are populated. When `observation_time` and `sampling_interval`
were supplied, `lambda` is populated instead. With neither sampling request,
the structural critical and budget exponents remain available while optional
evaluations are `null`.

The sign test uses the exact binary value of the normalized `alpha`; no
near-zero tolerance changes the regime. Exponents, entropy coefficients and
finite-scale exposure are rounded to float after exact input arithmetic.
An unrepresentable nonzero result produces the existing controlled error
document and exit code 2, consistently with text output.

The phase object always carries a boundary note stating that these are
paper-derived asymptotic predictions, not finite-sample guarantees.

## Critical experiment document

Every critical result begins with:

```json
{
  "schema_name": "homological-observability.critical-experiment",
  "schema_version": 1,
  "software": {
    "name": "homological-observability",
    "version": "1.1.0.dev0"
  },
  "artifact_role": "fresh-critical-experiment",
  "status": "COMPLETE"
}
```

Its main objects are:

| Field | Meaning |
| --- | --- |
| `model` | Normalized support, readouts, exact rates, critical settings, and limits |
| `summary` | Layer, $\theta$, graph sizes, completeness, counts, and total intensities |
| `topology` | Baseline analysis schema identity and requested/natural completeness flags |
| `groups` | Graded, visible, and hidden quotient presentations plus the induced readout |
| `stationary_law` | Exact generator and stationary probabilities |
| `catalogue` | Reference geodesics and exact weights aggregated by endpoint and mark |
| `limit_experiment` | Common compound-Poisson and critical endpoint components |
| `resources` | Declared limits and observed usage |
| `limit` | Resource boundary for `LIMIT_REACHED`, otherwise `null` |

All exact noninteger values are reduced rational strings, such as `"5/8"`.
Group marks have `torsion` and `free` coordinate arrays. These arrays use the
documented constructive Smith presentation and are representation-dependent;
the group ranks, invariant factors, and induced homomorphism carry the
basis-independent content.

`COMPLETE` means the requested one-layer topology, full path catalogue at
length $m$, exact stationary law, and marked-Poisson specification were all
constructed. It does not imply `natural_filtration_complete: true`; that flag
separately records whether the exposure filtration has reached all integral
homology directions.

`LIMIT_REACHED` is atomic. `groups`, `stationary_law`, `catalogue`, and
`limit_experiment` are all `null`, while `limit` names the resource and the
complete and incomplete components. The document does not expose a truncated
catalogue as a completed experiment.

The resource contract separates admission estimates from exact result limits.
The directed-path preflight stops once it can certify that `max_paths` is
exceeded. If it stops before obtaining the final count, `path_count` and
`limit.observed_or_estimated` are `null`, with `measurement: unavailable`.
This means the exact total was not computed; the resource refusal is certain.
If the final count is obtained and representable, it is reported as `exact`.

`max_estimated_integer_digits` applies only to the deterministic preflight
estimate and is reported with `measurement: preflight-estimate`.
The estimate may stop at a lower bound that already exceeds the budget,
without expanding the layer's factorial. An unrepresentable estimate is
omitted with `measurement: unavailable`.
`max_integer_digits` and `max_output_records` are checked against observed exact
values and records and are reported with `measurement: exact` when exceeded.
`maximum_integer_digits` covers the scientific integers and rationals listed
in the [model guide](MODEL_GUIDE.md#critical-settings), including derived total
intensities. It can therefore be larger than the rate or weight digit count alone.
Model values outside the [decimal representation boundary](MODEL_GUIDE.md#critical-settings)
are input errors, before analysis. Values within that boundary retain their
complete normalized model and hash even in `LIMIT_REACHED` output.

Within `limit_experiment`, zero marks are excluded from the common-endpoint
Lévy measure and retained in each conditional critical-endpoint mark law. The
object records independent limit components and the rule for conditioning a
total-mark law on an observed visible residue. It deliberately does not expand
the generally infinite total-mark probability table.

Every complete critical document states its scientific boundary: the object
is a theorem-derived critical-limit generative specification, not an exact
posterior at finite $(T,\delta)$ or an unconditional critical MAP solver. See the
[biased C4 example](CRITICAL_EXPERIMENT.md) for a complete example.

## Renderers

The public renderers are:

```python
import homological_observability as ho

result = ho.analyze_model(ho.load_model("examples/wedge_c3_c5.json"))
json_text = ho.render_json(result)
terminal_text = ho.render_text(result)
markdown_text = ho.render_markdown(result)

assert json_text.endswith("\n")
assert "Exact filtration" in markdown_text
assert "status: COMPLETE" in terminal_text
```

`render_json` sorts keys, rejects non-finite numbers, preserves Unicode, and
adds one trailing newline. The CLI uses this exact function.

Critical results have separate deterministic renderers:

```python
import homological_observability as ho

model = ho.load_critical_model("examples/biased_c4_critical.json")
result = ho.analyze_critical_model(model)
json_text = ho.render_critical_json(result)
terminal_text = ho.render_critical_text(result)

assert json_text.endswith("\n")
assert "status: COMPLETE" in terminal_text
assert "finite-sample posterior" in terminal_text
```

There is no critical Markdown renderer. The JSON document is the downstream
contract, and the compact terminal view is for reading rather than parsing.
