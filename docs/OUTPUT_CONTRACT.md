# Output contract

The Python API and CLI expose the same structured results. Use the table to find
the fields that explain your result.

| Task | Python result | JSON contract |
| --- | --- | --- |
| `posterior` | Finite-record posterior dictionary | [Completion status and inference outcome](#single-record-posterior) |
| `compare-protocols` | Paired protocol comparison dictionary | [Study status and per-path results](#paired-recording-protocols) |
| `target` / `design` | Target-task dictionary | [Target task document](#target-task-document) |
| DFR application | Case or evaluation dictionary | [Dataset and prediction protocol](TARGET_TASKS.md#dataset-and-prediction-protocol-v1) |
| `analyze` / `example` | Immutable `TopologyAnalysis` | [Analysis document](#analysis-document-identity) |
| `compare` | Comparison dictionary | [Configuration comparison document](#configuration-comparison-document) |
| `critical` | Immutable `CriticalExperimentResult` | [Critical experiment document](#critical-experiment-document) |
| `reproduce` | Reproduction result | [Calculation checks and reference agreement](#paper-reproduction) |

JSON is the format for downstream processing. Terminal text and the topology
and comparison Markdown reports are intended for reading. Shared references below
cover [exit codes](#process-exit-codes), [schemas](#bundled-schemas),
[earlier and generator formats](#reading-earlier-records), and [renderers](#renderers).

<a name="finite-recording-tasks-and-generator-formats"></a>

## Finite-record results

### Single-record posterior

For a single record, `posterior` writes `homological-observability.posterior`
(v1). Read `status` for completion and `result.outcome` for the inference.
A `COMPLETE` run can determine the target exactly (`EXACT`), return a
`NUMERICAL_POSTERIOR`, or prove that the observations are incompatible with
the model (`IMPOSSIBLE_RECORD`). For an `UNRESOLVED` outcome,
`result.diagnostics.reason` explains what prevented inference.
See [Interpreting a posterior](FINITE_RECORDS.md#interpreting-a-posterior)
for target support, probabilities and error estimates.

### Paired recording protocols

For a protocol study, `compare-protocols` writes
`homological-observability.recording-protocol-comparison` (v1). Its top-level
`status` is `COMPLETE` when every path has a resolved risk under every protocol.
With `PARTIAL`, inspect the individual paths in `result.rows`. The
[protocol summaries](FINITE_RECORDS.md#compare-recording-protocols) in
`result.protocols` retain all paths in the risk bounds.

## Target task document

`analyze_target`, `design_readouts` and `evaluate_target` use independent v1
request and result formats.
See [target JSON and replay](TARGET_TASKS.md#json-and-replay) for their fields.
Existing analysis, comparison and critical formats retain their versions.

Read `result` for the scientific conclusion and `status` for computational
completion. An insufficient target or an illegal record can be a completed
diagnosis. A stopped search can retain a proved minimum without returning all
tied choices or finishing all certificates. Optional `explanation_status`
separately reports exposure-layer completeness; it does not replace the
full-cycle-group target decision.

Text reports state the established conclusion, any unfinished work and the
replay identity. `result.json` retains exact matrices, integer witnesses,
rational decoders and scale values. Decimal exposure scales in text are
approximations for reading. A saved bundle also includes `request.json` and
`report.txt`; each bundle is written to a new directory.

## Analysis document

The `analyze` and `example` commands return the topology analysis described
below. [Comparison](#configuration-comparison-document) and
[critical](#critical-experiment-document) results have their own structures.

### Analysis document identity

For a first reading, check `status` and the completeness fields before using
`summary.first_nonzero_hidden_layer` to locate the earliest unresolved cycle
direction. Then inspect `filtration` for the integer relations and `phase`
for their sampling interpretation. `COMPLETE` certifies that the requested
calculation reached the full cycle lattice. A zero leading entropy coefficient can coexist with
finite critical ambiguity, as the [wedge example](END_TO_END_EXAMPLE.md) shows.

An analysis document has the following identity fields. The version shown
here identifies this example record; a new run records its producing version.

```json
{
  "schema_name": "homological-observability.analysis",
  "schema_version": 3,
  "software": {
    "name": "homological-observability",
    "version": "2.0.0"
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

### Reading earlier records

| Result format | Analysis | Comparison |
| --- | ---: | ---: |
| Earlier | 2 | 1 |
| Default | 3 | 2 |
| Generators | 4 | 3 |

Both backends accept model and study input versions 1 and 2 and write
the normalized input as version 2. In a study, the study and shared model versions must match.
A format-1 numeric input therefore keeps its scientific meaning while its
normalized model or study digest changes. Earlier software cannot read the
new format or exact alpha strings. Keep original records with their original
producer version; rerunning them creates a new record.

For an analysis or comparison result, pass its `schema_version` to the
corresponding loader. With `--backend generators`, use
`load_analysis_schema(version=4)` or `load_comparison_schema(version=3)` for the
[generator outputs](CONVENTIONS.md#shortest-path-generators). Calling either
loader without a version selects the default cycle format. Use `version=1`
with `load_model_schema` or `load_study_schema` for earlier inputs.
Critical input, critical experiment and bundle-manifest formats remain at
version 1. The critical experiment's baseline reference still identifies the
analysis-2 topology fields used by that independent contract.

For a cross-version check, compare scientific fields with their statuses,
scopes and coordinate conventions intact. Do not expect identical hashes or
report bytes after normalization and presentation changes. Exact byte replay
uses the same build, environment, request and options.

### Top-level fields

| Field | Meaning |
| --- | --- |
| `schema_name`, `schema_version` | Schema name and version |
| `software` | Package name and implementation version |
| `artifact_role` | Provenance role of this analysis |
| `status` | `COMPLETE`, `PARTIAL_HORIZON`, or `LIMIT_REACHED` |
| `evidence_categories` | Evidence kinds present in the document |
| `normalized_model_sha256` | Digest of the validated normalized model |
| `model` | Effective normalized request, including API sampling overrides |
| `summary` | Summary of basis-independent results |
| `homology` | Auditable basis, readout coordinates, and rank |
| `filtration` | Exact cycles, lattices, and graded quotients, or `null` |
| `phase` | Theorem-derived phase interpretation, or `null` |
| `limit` | Resource-bound details, or `null` |

No creation timestamp is included. Byte-for-byte reproduction requires the
same normalized input, software build, relevant environment, artifact role,
coordinate options, and serialization settings. A version label alone does
not identify all of those conditions. In particular, `--reverse-tree-order`
changes the homology basis and can change serialized coordinates while
preserving the scientific invariants.

### Topology status and completeness

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

`LIMIT_REACHED` means the selected backend exceeded its catalogue budget
(`max_cycles` for simple cycles or `max_generators` for generators). In that state:

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

### Filtration layers

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

### Phase object

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

The sign test uses the exact rational alpha or the exact binary value of a
numeric alpha; no near-zero tolerance changes the regime. `phase.alpha` and
`model.analysis.alpha` retain the same normalized number or reduced fraction
string. Exact threshold and budget outputs keep their rational-object form. Exponents, entropy coefficients and
finite-scale exposure are rounded to float after exact input arithmetic.
An unrepresentable nonzero result produces the existing controlled error
document and exit code 2, consistently with text output.

The phase object's boundary note identifies the paper's asymptotic law and
the role of the dynamics and observations in finite-run error analysis.

## Configuration comparison document

`compare_configurations(study)` returns a dictionary with
`schema_name: homological-observability.comparison`, `schema_version: 2`, and
`artifact_role: configuration-comparison`. It is already the structured JSON
document and does not need `analysis_to_dict`.

| Field | Meaning |
| --- | --- |
| `status` | `COMPLETE` when every candidate is naturally complete; otherwise `INCOMPLETE` |
| `producer` | Package version, installed-code digest, source identity, and computation environment |
| `study`, `study_sha256` | Normalized shared input and candidates, with a canonical JSON digest |
| `shared_conditions` | Shared graph, analysis settings, coordinate option, and observation contract |
| `rows` | Candidate summaries, statuses, scopes, hidden directions, redundancy, and explanations |
| `results` | Raw analysis documents keyed by configuration ID; error candidates have no entry |
| `relations` | Pairwise information relations, scope, exact certificates, and distinguishing witnesses |
| `explanations` | Study-level interpretation of the computed results |

The raw `results` retain the [analysis contract](#analysis-document-identity),
including `LIMIT_REACHED` records. Each row has its own status:

| Candidate status | Available interpretation |
| --- | --- |
| `COMPLETE` | The exposure reaches the full integer homology lattice |
| `PARTIAL_HORIZON` | Exact conclusions on the exposure lattice through `computed_max_layer` |
| `LIMIT_REACHED` | Read the raw analysis for completed components; hidden summaries and pairwise relations are unavailable |
| `ERROR` | Read `error` and `recovery`; the study retains the candidate's supplied readouts |

Each row and pair declares a `scope`: `FULL_HOMOLOGY`, `COMPUTED_EXPOSURE`, or
`UNAVAILABLE`. Interpret a null `first_hidden_layer` together with that scope:
it can mean no hidden direction on the full lattice, none yet in the computed
layers, or an unavailable calculation. Other missing summaries remain null
rather than becoming zero. A failed candidate does not erase valid neighbors.

### Information relations and certificates

Pairs identify candidates by `left` and `right` IDs. `relation` is one of
`EQUIVALENT`, `LEFT_REFINES_RIGHT`, `RIGHT_REFINES_LEFT`, `INCOMPARABLE`, or
`UNAVAILABLE`. Their meaning follows from [hidden-kernel inclusion on the
common lattice](CONVENTIONS.md#information-relations-between-configurations).

`left_kernel_in_right` and `right_kernel_in_left` each record `included` and,
when true, integer `coordinates` expressing the source kernel basis in the
target kernel basis. A failed inclusion supplies the corresponding
`left_not_right_witness` or `right_not_left_witness`: cycle coordinates,
an oriented physical edge chain, and both readout vectors. The named source
readout vanishes on that witness; the other readout distinguishes it.
Unavailable pairs carry null certificates and witnesses.

`metric_comparison` records scalar comparisons separately from the information
relation. Equal first hidden layers, ranks, or entropy coefficients do not
imply equivalent information. A row's `redundant_channels` lists channels that
can each be removed while all other channels are retained, on the stated
scope; it does not describe their simultaneous removal.

### Comparison bundles

`write_comparison_bundle(comparison, output_dir)` and CLI `--output-dir` write
a new directory containing:

| File | Purpose |
| --- | --- |
| `study.json` | Input for a whole-study rerun |
| `comparison.json`, `comparison.md` | Structured result and readable report |
| `models/config-ID.json` | Input for each candidate, including invalid readouts retained for diagnosis |
| `raw/config-ID.json` | Each available raw analysis |
| `environment.json` | Environment captured when the comparison was computed |
| `README.md` | Rerun and verification instructions |
| `manifest.json` | File paths, byte sizes, and SHA-256 checksums |

The manifest is written last. Its `bundle_status: COMPLETE` means the files
were fully written; the scientific comparison can still be `INCOMPLETE`.
Existing output directories are rejected.

`producer.code_sha256` identifies the installed Python modules and schemas.
`source_commit: null` means no Git commit is asserted. The producer environment
belongs to the original calculation and remains unchanged if the result is
exported later. `shared_conditions.reverse_tree_order` records the coordinate
option, which the exported rerun commands retain. Exact byte comparison uses
the same input, build, options, and environment; across environments, compare
scientific fields with their statuses and scopes intact. See the
[comparison guide](COMPARISON_GUIDE.md) for the reading and replay workflow.

## Critical experiment document

A critical result uses the following identity fields. As in the analysis
example, `software.version` identifies the implementation that produced the
record:

```json
{
  "schema_name": "homological-observability.critical-experiment",
  "schema_version": 1,
  "software": {
    "name": "homological-observability",
    "version": "1.1.0"
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
constructed. The separate `natural_filtration_complete` flag records whether
the exposure filtration has reached all integral homology directions.

`LIMIT_REACHED` is atomic. `groups`, `stationary_law`, `catalogue`, and
`limit_experiment` are all `null`, while `limit` names the resource and the
complete and incomplete components.

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
total-mark law on an observed visible residue. This component representation
specifies the generally infinite total-mark law compactly.

Every complete critical document identifies the object as a theorem-derived
critical-limit generative specification. Finite-time posteriors and
unconditional MAP probabilities require evaluation of the corresponding
conditional laws. See the
[biased C4 example](CRITICAL_EXPERIMENT.md) for a complete example.

## Shared formats and process behavior

These conventions identify results, describe their evidence, and support
programmatic use across tasks.

### Artifact roles

Analysis documents use one of two roles:

| Role | Source |
| --- | --- |
| `fresh-analysis` | A user model passed to `analyze` or the Python API default |
| `builtin-example` | A versioned model selected through the example registry |

Critical experiment documents use
`artifact_role: fresh-critical-experiment`. Their provenance is the normalized
critical model and its digest; the built-in topology example registry is not
used by this task.

Comparison documents use `artifact_role: configuration-comparison`. They
record the normalized study and its digest, the computation's producer, and
the raw single-configuration analyses. Their [bundle](#comparison-bundles)
preserves these records for another run.

### Paper reproduction

`reproduce --format json` prints a manifest with
`schema_name: homological-observability.reproduction` and
`artifact_role: canonical-paper-evidence`. On success, `files` lists the
generated tables, figures and Markdown report.

`status: PASS` means that the calculation checks completed. Read it together
with `checked_against_frozen_reference`: `true` additionally confirms that
both generated CSV tables match the frozen references at `rtol=1e-12` and
`atol=1e-14`; `false` means that comparison was not requested. Use `--check`
for paper reproduction. A mismatch emits `status: FAIL` and exits with code 1.
The Markdown report displays calculation and reference-comparison status
separately. A new run invalidates any previous success report before computing;
a failed or interrupted run leaves a `FAIL` or `INCOMPLETE` report.

Use `files[].sha256` to identify the exact file produced by a run.
Two platforms can write slightly different trailing digits in a CSV file.
The checksums then differ even when the values from each platform match
the reference within tolerance.

Both the checkout's `results/` tree and the installed package's reference
directory are protected from reproduction writes, including file aliases with
different names. All output paths are checked before the first file is written.
The count-TV intervals include rounding and truncated-tail error; their
calculation and reference calibration are described in [numerical methods](NUMERICS.md).

### Evidence categories

- `EXACT_INTEGER` labels integral basis, kernel, image, Hermite, and Smith
  computations.
- `EXACT_COMBINATORIAL` labels complete finite simple-cycle or directed-path
  enumeration. In topology analysis it also covers exact construction of each
  requested exposure lattice from [shortest-path cycle generators](CONVENTIONS.md#shortest-path-generators).
- `EXACT_RATIONAL` labels exact directed-rate products, stationary
  probabilities, path weights, and limit intensities.
- `ASYMPTOTIC_THEOREM` labels quantities obtained by applying the paper's
  phase law.

These categories describe how a field is supported. They are not confidence
levels.

### Process exit codes

| Task | Exit `0` | Exit `1` |
| --- | --- | --- |
| `posterior` | `COMPLETE`, including an `IMPOSSIBLE_RECORD` decision | Rates, rank, precision or a resource limit prevent a complete inference |
| `compare-protocols` | `COMPLETE`: every path has a resolved risk under each protocol | `PARTIAL`: unresolved risks remain in the reported bounds |
| `analyze` / `example` | `COMPLETE` or `PARTIAL_HORIZON` | `LIMIT_REACHED` |
| `compare` | Every candidate is `COMPLETE` | Comparison is `INCOMPLETE`: at least one candidate is partial, limited, or in error |
| `critical` | Requested critical experiment is `COMPLETE` | `LIMIT_REACHED` |
| `target` / `design` | Core is `COMPLETE`; explanation is `COMPLETE` or `NOT_REQUESTED` | Core or requested explanation is incomplete |
| `reproduce` | Calculation checks passed; reference comparison is reported separately | Reference evidence mismatched |

Exit `2` reports CLI usage, file, JSON, validation, or controlled execution
errors, including invalid shared study input and comparison export failures.
Listing examples or writing a study template exits `0` on success.

JSON errors use `schema_name: homological-observability.error`,
`schema_version: 1`, `status: ERROR`, and a message. Terminal errors are written
to standard error. Expected input errors do not print a traceback.

### Bundled schemas

The installed package includes [Draft 2020-12 JSON schemas](../src/homological_observability/schemas)
for its public inputs and results. Open a schema below or load it from Python.

| JSON schema | Python loader |
| --- | --- |
| [Finite-record request](../src/homological_observability/schemas/posterior-request.schema.json) | `load_posterior_request_schema()` |
| [Finite-record posterior](../src/homological_observability/schemas/posterior.schema.json) | `load_posterior_schema()` |
| [Recording protocol study](../src/homological_observability/schemas/protocol-request.schema.json) | `load_protocol_request_schema()` |
| [Paired protocol comparison](../src/homological_observability/schemas/protocol-comparison.schema.json) | `load_protocol_comparison_schema()` |
| [Model input](../src/homological_observability/schemas/model.schema.json) | `load_model_schema()` |
| [Analysis result](../src/homological_observability/schemas/analysis.schema.json) | `load_analysis_schema()` |
| [Configuration study input](../src/homological_observability/schemas/study.schema.json) | `load_study_schema()` |
| [Configuration comparison result](../src/homological_observability/schemas/comparison.schema.json) | `load_comparison_schema()` |
| [Example registry](../src/homological_observability/schemas/examples.schema.json) | `load_examples_schema()` |
| [Reproduction result](../src/homological_observability/schemas/reproduction.schema.json) | `load_reproduction_schema()` |
| [Controlled error](../src/homological_observability/schemas/error.schema.json) | `load_error_schema()` |
| [Critical model input](../src/homological_observability/schemas/critical-model.schema.json) | `load_critical_model_schema()` |
| [Critical experiment result](../src/homological_observability/schemas/critical-experiment.schema.json) | `load_critical_experiment_schema()` |
| [Target request](../src/homological_observability/schemas/target-request.schema.json) | `load_target_request_schema()` |
| [Target result](../src/homological_observability/schemas/target-task.schema.json) | `load_target_task_schema()` |

Each loader returns a fresh dictionary, so callers can construct a validator or
adapt a local copy without mutating package state.

### Matrix encoding

Integer coordinate matrices carry explicit dimensions and row-major data:

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

These coordinate matrices contain exact integers. Critical rates and weights
use rational strings; floating-point values appear in the sampling
interpretation.

## Renderers

Reading surfaces adapt to the effective request. Structure-only reports show
integer filtrations and counter relations. Alpha reports add per-layer
regimes and entropy contributions. Finite time/interval reports show the
computed exposure scales and hidden graded quotients, including torsion.
Partial and unavailable results keep their completion boundaries; a renderer
does not compute missing scientific results.

Topology analysis renderers accept the immutable analysis result:

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

Comparison renderers accept the comparison dictionary directly:

```python
import json

import homological_observability as ho

comparison = ho.compare_configurations(ho.load_study_example("bridge"))
terminal_text = ho.render_comparison_text(comparison)
markdown_text = ho.render_comparison_markdown(comparison)
json_text = (
    json.dumps(
        comparison, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
    )
    + "\n"
)

assert comparison["schema_name"] == "homological-observability.comparison"
assert comparison["status"] == "COMPLETE"
```

The JSON settings above match `compare --format json`. Use
`write_comparison_bundle(comparison, "new-results")` to save the result with
its inputs and environment; the destination must not already exist.

Critical results have separate deterministic renderers:

```python
import homological_observability as ho

model = ho.load_critical_model("examples/biased_c4_critical.json")
result = ho.analyze_critical_model(model)
json_text = ho.render_critical_json(result)
terminal_text = ho.render_critical_text(result)

assert json_text.endswith("\n")
assert "status: COMPLETE" in terminal_text
assert "critical-limit experiment" in terminal_text
```

Critical JSON is the downstream contract; the compact terminal view presents
its main findings for reading.

Target-task dictionaries use `render_target_text(result)` for terminal output.
`write_target_bundle(result, "new-results")` saves `request.json`, `result.json`
and `report.txt` in a new directory. The [target guide](TARGET_TASKS.md)
describes their fields and replay commands.
