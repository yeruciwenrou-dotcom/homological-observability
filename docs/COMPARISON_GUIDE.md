# Compare counter configurations

Use a comparison study to ask which exact cumulative counters change the
cycle histories left hidden by snapshots. One study keeps the network,
sampling parameters, and computation budget fixed, runs the named candidate
configurations, and explains their information relations with integer
witnesses.

This command is available in the **1.2.0 development source**. Install the
checkout containing this guide in an activated Python 3.11–3.13 virtual
environment:

```bash
python -m pip install .
homological-observability study-example bridge --output bridge-study.json
homological-observability compare bridge-study.json --output-dir bridge-results
```

The output directory must be new. Read `bridge-results/comparison.md` for the
comparison and `bridge-results/comparison.json` for its structured evidence.
Omit `--output-dir` for a terminal-only run; add `--format json` to obtain the
same comparison as JSON on standard output. These commands are not included
in the frozen 1.1.0 package.

## Read the answer

The bridge example joins a four-cycle and a seven-cycle by one connecting
edge. The counter `x` counts net passages along one oriented edge of the
four-cycle; `y` does the same for the seven-cycle. For closed histories these
are the two winding coordinates. Every listed graph edge represents positive
transition rates in both directions.

Start with the three simplest candidates:

| Configuration | Channels | First hidden layer | Hidden rank at the complete horizon |
| --- | ---: | ---: | ---: |
| Snapshots only | 0 | 2 | 2 |
| Counter x (C4) | 1 | 4 | 1 |
| Counter y (C7) | 1 | 2 | 1 |

If the aim is to postpone the first hidden free direction using one of these
counters, `x` is the useful choice: its remaining ambiguity first enters at
layer four. Counter `y` leaves the earlier four-cycle ambiguity hidden.
Both counters leave one direction unresolved, but they leave **different**
directions unresolved. Their information is incomparable.

The full study also includes weighted counters:

- `z = 2x + y` also postpones the first hidden layer to four. It ties `x` on
  that objective while retaining different information. A change
  `(x, y) → (x − 1, y + 2)` preserves `z`.
- The pair `(z, 2z)` contains the same exact information as `z`. Its second
  channel is redundant.
- The pair `(z, y)` resolves both cycle coordinates. Its readout matrix has
  determinant two; recovery is valid on the legal image, where
  `x = (z − y) / 2` is an integer.

The channel count describes the number of declared readouts. It does not
assign a hardware cost to building a weighted counter.

The example uses `alpha = 0.375`, meaning the asymptotic sampling law
`delta = T^(-3/8)` in fixed reference-rate units. A zero `log T` entropy
coefficient means that this leading growth term vanishes; hidden critical
uncertainty or finite-time ambiguity can still remain. Read the hidden
lattice and phase together.

## Compare your own configurations

Create an editable starting point:

```bash
homological-observability study-example minimal --output my-study.json
homological-observability compare my-study.json --output-dir my-results
```

The minimal study has a short loop and a long loop sharing a junction. Its
three candidates use snapshots alone, a short-loop counter, or a long-loop
counter. Edit this file in the following order:

1. Replace `model.vertices` and `model.edges` with your connected simple graph.
2. Give each configuration a unique `id` and a readable `label`.
3. Define each counter through its integer coefficients on graph edges.
4. Set a shared `max_cycles` budget and, if needed, sampling parameters in
   `analysis`. Run into a new output directory after each edit.

For a counter coefficient of `1` on `['junction', 'short-a']`, a jump in that
direction adds one and the reverse jump subtracts one. Omitted edges have
coefficient zero. Weighted counters use other integer coefficients. The
[model guide](MODEL_GUIDE.md) gives the full graph and readout rules.

A study has the following parts:

| Field | Meaning |
| --- | --- |
| `schema_version` | `1` for the study format |
| `name` | Study title |
| `question` | Optional description of the research question |
| `model` | Shared topology: model schema version, name, vertices, and edges |
| `analysis` | Shared sampling parameters, horizon, and resource budget |
| `configurations` | Nonempty list of candidates with `id`, optional `label`, and `readouts` |

Place readouts only inside the configurations and analysis settings only in
the study's `analysis` field. This makes the comparison conditions explicit.
Configuration IDs use lowercase letters, digits, underscores, and hyphens.
They start with a letter or digit and contain at most 64 characters. A study
accepts at most 64 configurations. An empty readout list is the snapshots-only
candidate.

Counter values here are exact cumulative measurements. These studies do not
model measurement noise, estimate unknown graphs or rates, or choose physical
instruments. For open histories with known endpoints, cycle coordinates are
understood after the common endpoint-reference correction.

The same study can be run through the Python API:

```python
import homological_observability as ho

study = ho.load_study_example("bridge")
comparison = ho.compare_configurations(study)
print(comparison["status"])
```

For your own saved study, use `ho.load_study("my-study.json")`. For a Python
dictionary, use `ho.parse_study(document)` to validate the shared input.
`ho.render_comparison_text(comparison)` and
`ho.render_comparison_markdown(comparison)` read the same result object;
`ho.write_comparison_bundle(comparison, "new-results")` saves it with its
replay inputs.

## Understand information relations

Each configuration partitions the computed cycle lattice into histories with
the same readout. Its hidden kernel determines that partition. The comparison
uses exact integer containment in common coordinates:

| Relation | Meaning |
| --- | --- |
| `EQUIVALENT` | Both configurations have the same hidden kernel |
| `LEFT_REFINES_RIGHT` | The left configuration has a strictly smaller hidden kernel |
| `RIGHT_REFINES_LEFT` | The right configuration has a strictly smaller hidden kernel |
| `INCOMPARABLE` | Each configuration hides a direction distinguished by the other |
| `UNAVAILABLE` | A required result was not computed |

A refinement retains all distinctions made by the other configuration and
adds at least one. Equal ranks, equal first hidden layers, or equal entropy
coefficients alone do not establish equivalence or refinement. In particular,
`x` and `2x` are equivalent under exact integer measurement even though their
ambient readout image lattices differ.

Redundancy is tested by removing **one channel at a time** while retaining
all the others. In `(z, 2z)`, either channel can be removed individually.
Removing both removes the observation, so the redundant-channel list is
not an instruction to delete every listed channel together.

The report supplies edge-chain witnesses for directions that distinguish
candidates. These use the graph's canonical edge orientation, so they can be
checked against the declared physical counters. Readout decoding is only
asserted on values produced by the model.

For a second illustration, the theta study has three routes between two
states. Several one-channel candidates share the same scalar summary while
hiding different cycle combinations:

```bash
homological-observability study-example theta --output theta-study.json
homological-observability compare theta-study.json --output-dir theta-results
```

## Check completeness and recover from errors

The report preserves a separate status for every candidate:

| Candidate status | How to use the result |
| --- | --- |
| `COMPLETE` | The exposure has reached the full integer homology lattice |
| `PARTIAL_HORIZON` | Conclusions apply only to the computed exposure lattice |
| `LIMIT_REACHED` | The budget stopped computation; missing filtration conclusions are unavailable |
| `ERROR` | Correct this candidate's readouts using the accompanying message |

The comparison is `COMPLETE` only when every candidate is complete. A
partial-horizon relation cannot establish a full-history equivalence or
refinement. A zero hidden rank at a short horizon does not show that later
layers are resolved. Resource limits and candidate errors do not erase the
other candidates' results.

The `compare` command exits with `0` for a complete comparison, `1` when any
candidate is incomplete or has an error, and `2` for invalid shared input or
an output failure. A global error, such as an invalid graph or duplicate
configuration ID, must be corrected before running the study. If a cycle
budget is exhausted, review the graph size and choose an affordable budget;
cycle enumeration can grow exponentially.

Phase labels use the exact binary value represented by a floating-point
`alpha`. For example, the floating-point value nearest `1/3` lies below the
exact threshold. A small positive entropy coefficient must therefore remain
visible rather than be rounded to zero. See the
[sampling parameter rules](MODEL_GUIDE.md) for details.

## Keep and rerun a study

### Observed small-model cost

The following single-run observations used the 1.2.0 development wheel on
Linux x86-64, Python 3.12.14, SymPy 1.14.0 and NetworkX 3.6.1. Each includes
a fresh CLI process, analysis, serialization and complete bundle export.

| Study | Vertices / edges | Simple cycles | Configurations | Largest counter coefficient | Wall time | Peak resident memory |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Bridge | 11 / 12 | 2 | 6 | 4 | 1.89 s | 168 MiB |
| Theta | 8 / 9 | 3 | 5 | 1 | 1.40 s | 167 MiB |
| Minimal | 7 / 8 | 2 | 3 | 1 | 1.32 s | 170 MiB |

These measurements establish a small-model baseline, not a maximum graph
size or a timing guarantee. Other validation processes were active. Simple
cycle enumeration can grow exponentially; `max_cycles` and the 64-candidate
bound limit the declared work. Topology comparison does not construct the
critical-path catalogue used by the separate `critical` command.

### Export and replay

The exported directory contains the input study, structured comparison,
Markdown report, individual model inputs and raw analyses, environment
identity, a checksum manifest, and instructions for another run. The raw
analyses retain the existing single-model output contract. A whole-study
rerun uses the saved input:

```bash
homological-observability compare bridge-results/study.json --output-dir bridge-replay
```

Use the recorded software version or source identity when reproducing a
result. The producer record includes a SHA-256 digest of the actual installed
package's Python modules and schemas. It does not infer a Git commit from
the surrounding working directory; a null `source_commit` means no commit
is asserted. For a development build, retain the corresponding source or
wheel as well as its version label. The output directory is never silently
overwritten. Keep the
original bundle when changing inputs or upgrading the software. The producer
captures the calculation environment, which is preserved in `environment.json`
even when a saved result is exported later. Exact bytes are reproducible with
the same inputs, build, coordinate option and environment; compare scientific
fields with their status and scope intact across environments.

For a coordinate-invariance check, both `compare` and `analyze` accept
`--reverse-tree-order`. The comparison records this choice and its exported
replay instructions retain the flag. Physical conclusions are independent of
the spanning tree, while coordinate matrices can change.

The paper's archived evidence remains tied to software 1.1.0 and its
[version DOI](https://doi.org/10.5281/zenodo.23329444). New comparison studies
are separate research outputs and should record their own producing version.
