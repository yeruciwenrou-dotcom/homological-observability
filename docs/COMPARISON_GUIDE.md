# Compare counter configurations

Compare candidate counters on the same network to find what information each
adds, which channels are redundant, and which histories remain hidden. A
study holds the graph, sampling parameters, and computation budget fixed so
that the candidates can be compared directly.

If you ran the [quick start](../README.md#quick-start), continue with
[Read the answer](#read-the-answer) using your existing `bridge-results`.
For a first run, follow the [installation instructions](../README.md#install),
then run the built-in bridge study from the checkout directory.

Commands below use the installed environment directly. On Windows, use
`.venv\Scripts\homological-observability.exe` in place of
`.venv/bin/homological-observability`. Run the Python examples with
`.venv/bin/python` (Windows: `.venv\Scripts\python.exe`).

```bash
.venv/bin/homological-observability study-example bridge --output bridge-study.json
.venv/bin/homological-observability compare bridge-study.json --output-dir bridge-results
```

The output directory must be new. Read `bridge-results/comparison.md` for the
comparison and `bridge-results/comparison.json` for its structured evidence.
Omit `--output-dir` for a terminal-only run; add `--format json` to obtain the
same comparison as JSON on standard output.

## Read the answer

Begin with the report's **Main findings** and **Shared conditions**, then use
**Configuration comparison** for the scalar summaries and **Information
relations** for what each candidate can distinguish.

The bridge example joins a four-cycle and a seven-cycle by one connecting
edge. The counter $x$ counts net passages along one oriented edge of the
four-cycle; $y$ does the same for the seven-cycle. For closed histories these
are the two winding coordinates. Every listed graph edge represents positive
transition rates in both directions.

Start with the three simplest candidates:

| Configuration | Channels | First hidden layer | Hidden rank at the complete horizon |
| --- | ---: | ---: | ---: |
| Snapshots only | 0 | 2 | 2 |
| Counter $x$ on $C_4$ | 1 | 4 | 1 |
| Counter $y$ on $C_7$ | 1 | 2 | 1 |

If the aim is to postpone the first hidden free direction using one of these
counters, $x$ is the useful choice: its remaining ambiguity first enters at
layer four. Counter $y$ leaves the earlier four-cycle ambiguity hidden.
Both counters leave one direction unresolved, but they leave **different**
directions unresolved. Their information is incomparable.

The full study also includes weighted counters:

- $z=2x+y$ also postpones the first hidden layer to four. It ties $x$ on
  that objective while retaining different information. A change
  $(x,y)\mapsto(x-1,y+2)$ preserves $z$.
- The pair $(z,2z)$ contains the same exact information as $z$. Its second
  channel is redundant.
- The pair $(z,y)$ resolves both cycle coordinates. Its readout matrix has
  determinant two; recovery is valid on the legal image, where
  $x=(z-y)/2$ is an integer.

The channel count describes the number of declared readouts. It does not
assign a hardware cost to building a weighted counter.

The example sets `alpha` to $0.375$, meaning the asymptotic sampling law
$\delta=T^{-3/8}$ in fixed reference-rate units. A zero $\log T$ entropy
coefficient means that this leading growth term vanishes; hidden critical
uncertainty or finite-time ambiguity can still remain. Read the hidden
lattice and phase together. For a step-by-step explanation of the underlying
filtration and sampling law, see the [two-loop example](END_TO_END_EXAMPLE.md).

## Compare your own configurations

Save a copy of `bridge-study.json` as `my-study.json` to adapt the network and
counters you have just explored. If you already made this copy while following
the README, continue editing that file.

<details>
<summary>Start from a smaller template</summary>

For a fresh study, you can instead create `my-study.json` with the minimal
example. The destination file must not already exist.

```bash
.venv/bin/homological-observability study-example minimal --output my-study.json
```

This study has a short loop and a long loop sharing a junction. Its
three candidates use snapshots alone, a short-loop counter, or a long-loop
counter.

</details>

For a counter coefficient of `1` on `["a0", "a1"]`, a jump in that
direction adds one and the reverse jump subtracts one. Omitted edges have
coefficient zero. Weighted counters use other integer coefficients. The
[model guide](MODEL_GUIDE.md) gives the full graph and readout rules.

Place readouts only inside the configurations and analysis settings only in
the study's `analysis` field. The shared `model` holds the topology. An empty
readout list is the snapshots-only candidate. The [input reference](MODEL_GUIDE.md)
describes study fields, identifiers, validation, and the 64-candidate limit.

Edit this file in the following order:

1. Update the study's `name` and the `model.name`. Set or remove the optional
   `question` to describe your research question; this text labels the study
   without choosing an optimization objective.
2. Replace `model.vertices` and `model.edges` with your connected simple graph.
3. Give each configuration a unique `id` and a readable `label`, then define
   its counters through integer coefficients on the graph edges.
4. Choose the sampling request below and retain an explicit `max_cycles`
   budget in `analysis`.

Both starting examples include `alpha: 0.375`, which specifies their sampling
law. Confirm what your study needs before running it:

| Your question | Sampling fields in `analysis` |
| --- | --- |
| Which histories do the counters distinguish? | Remove `alpha` to compare the exact structure without choosing a sampling law |
| How do the candidates behave under a chosen asymptotic sampling law? | Set `alpha` to your exponent in $\delta=T^{-\alpha}$; keep `0.375` only if that is your intended law |
| What are the exposure scales at a specified observation time and interval? | Remove `alpha` and provide both `observation_time` and `sampling_interval` in [normalized units](MODEL_GUIDE.md#from-a-physical-model-to-an-input) |

With no sampling fields, the hidden directions, information relations, and
structural critical exponents remain available; evaluated entropy coefficients
are left unset. The finite time/interval pair reports $T\delta^{m-1}$ values,
without assigning asymptotic regime labels or finite-run error probabilities.

Run the edited study into a new directory, then check the report's title,
**Shared conditions**, and candidate labels against your intended question:

```bash
.venv/bin/homological-observability compare my-study.json --output-dir my-results
```

Counter values here are exact cumulative measurements. These studies do not
model measurement noise, estimate unknown graphs or rates, or choose physical
instruments. For open histories with known endpoints, cycle coordinates are
understood after the common endpoint-reference correction.

The Python API follows the same workflow. To try it with a packaged study:

```python
import homological_observability as ho

study = ho.load_study_example("bridge")
comparison = ho.compare_configurations(study)
print(ho.render_comparison_text(comparison))
```

For your edited study, use `ho.load_study("my-study.json")`. For a Python
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
$x$ and $2x$ are equivalent under exact integer measurement even though their
ambient readout image lattices differ.

Redundancy is tested by removing **one channel at a time** while retaining
all the others. In $(z,2z)$, either channel can be removed individually.
Removing both removes the observation, so the redundant-channel list is
not an instruction to delete every listed channel together.

The report's **Representative exact evidence** section shows selected
containment certificates and edge-chain witnesses. Their readout values show
which candidate detects each direction. The linked `comparison.json` retains
the complete evidence. Edge chains use the graph's canonical orientation, so
they can be checked against the declared physical counters. The
[output reference](OUTPUT_CONTRACT.md) explains these records. Readout decoding
applies to values produced by the model.

For a second illustration, the theta study has three routes between two
states. Several one-channel candidates share the same scalar summary while
hiding different cycle combinations:

```bash
.venv/bin/homological-observability study-example theta --output theta-study.json
.venv/bin/homological-observability compare theta-study.json --output-dir theta-results
```

## Check completeness and recover from errors

The report preserves a separate status for every candidate:

| Candidate status | Meaning and next step |
| --- | --- |
| `COMPLETE` | The exposure has reached the full integer homology lattice. Interpret the remaining hidden directions and information relations on that full scope. |
| `PARTIAL_HORIZON` | Conclusions cover only the computed exposure lattice. For a full-network comparison, remove the study's `analysis.max_layer` or raise it, rerun, and check natural completeness. |
| `LIMIT_REACHED` | The computation exceeded its budget. Read the raw result's `limit` field; decide whether a larger `max_cycles` budget is affordable before rerunning. |
| `ERROR` | Follow this candidate's error and recovery message to correct its readouts, then rerun the study. |

The comparison is `COMPLETE` only when every candidate is complete. A
partial-horizon relation cannot establish a full-history equivalence or
refinement. A zero hidden rank at a short horizon does not show that later
layers are resolved. Resource limits and candidate errors do not erase the
other candidates' results.

`max_layer` controls how far the calculation follows cycle exposure. Sampling
parameters describe the observation protocol; changing `alpha` or the sampling
interval does not complete a truncated calculation. When `max_layer` is
omitted, the graph-size horizon covers every simple cycle. The
[analysis settings](MODEL_GUIDE.md#analysis-settings) explain these choices.

The `compare` command exits with `0` for a complete comparison, `1` when any
candidate is incomplete or has an error, and `2` for invalid shared input or
an output failure. A global error, such as an invalid graph or duplicate
configuration ID, must be corrected before running the study. If a cycle
budget is exhausted, review the graph size and choose an affordable budget;
cycle enumeration can grow exponentially.

When interpreting a result near a critical threshold, check the
[sampling parameter rules](MODEL_GUIDE.md#analysis-settings). Phase labels
use the exact binary value stored in `alpha`; for example, the floating-point
value nearest $1/3$ lies below that exact threshold. A very small positive
entropy coefficient can therefore be meaningful.

## Keep and rerun a study

Keep the complete output directory so that another researcher can read the
answer, inspect its evidence, and rerun the same study. Start with
`comparison.md`; `comparison.json` contains the structured result and its
integer certificates. The directory's `README.md` gives the replay command
and the recorded software identity.

For the bridge study above, rerun into a new directory:

```bash
.venv/bin/homological-observability compare bridge-results/study.json --output-dir bridge-replay
```

The bundle also includes `study.json`, each candidate's model and raw analysis,
`environment.json`, and a checksum manifest. Use the recorded software build
and environment when reproducing a result, and retain the corresponding
source or wheel with the bundle. The environment record belongs to the
calculation that produced the result, including when the result is exported
later.

Keep the original bundle when changing inputs or upgrading the software;
exporting always requires a new directory. Exact bytes are reproducible with
the same inputs, build, coordinate option, and environment. Across environments,
compare the scientific fields together with their status and scope. See the
[output reference](OUTPUT_CONTRACT.md) for file identities and provenance.

For a coordinate-invariance check, both `compare` and `analyze` accept
`--reverse-tree-order`. The comparison records this choice and its exported
replay instructions retain the flag. Physical conclusions are independent of
the spanning tree, while coordinate matrices can change.

## Resource use

Choose an explicit `max_cycles` budget when trying an unfamiliar network.
Simple-cycle enumeration can grow exponentially; a small vertex count alone
does not predict the work. A study accepts at most 64 configurations.
Topology comparison uses cycle filtrations; rate-dependent path catalogues
are computed by the separate `critical` command.

The following measurements give a baseline for the built-in studies. Each
includes a fresh CLI process, analysis, serialization, and complete bundle
export.

| Study | Vertices / edges | Simple cycles | Configurations | Largest counter coefficient | Wall time | Peak resident memory |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Bridge | 11 / 12 | 2 | 6 | 4 | 1.89 s | 168 MiB |
| Theta | 8 / 9 | 3 | 5 | 1 | 1.40 s | 167 MiB |
| Minimal | 7 / 8 | 2 | 3 | 1 | 1.32 s | 170 MiB |

<details>
<summary>Measurement context</summary>

Single runs used package 1.2.0.dev0 on Linux x86-64, Python 3.12.14,
SymPy 1.14.0, and NetworkX 3.6.1, with other processes active. These small-model
observations do not establish a maximum graph size or a timing guarantee.

</details>
