# Homological Observability

[![PyPI v2.2.0](https://img.shields.io/badge/PyPI-v2.2.0-007ec6?logo=pypi)](https://pypi.org/project/homological-observability/2.2.0/)
[![Software DOI: 10.5281/zenodo.24422331](docs/zenodo-doi.svg)](https://doi.org/10.5281/zenodo.24422331)
[![alphaXiv Paper](docs/alphaxiv-badge.svg)](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes)

**Homological observability is the recoverability of a system's accumulated
cycle history from observations with finite temporal resolution.**

This repository provides Python tools to identify hidden cycle information in
your own network, find the sampling thresholds for recovering it, and determine
which counters recover a chosen trajectory target.

> **Paper:** Liu, H., Tian, Y., Wu, Z., & Cheng, J. (2026).<br>
> *Stochastic Histories at Finite Temporal Resolution: Homological Observability
> and Information Phase Diagrams in Markov Jump Processes*.<br>
> [Read and discuss the paper on alphaXiv](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes)

[Physical interpretation](#physical-interpretation) · [Install](#install) ·
[Quick start](#quick-start) · [Python API](#python-api) · [Documentation](#documentation-and-feedback)

## [New in 2.2](https://github.com/yeruciwenrou-dotcom/homological-observability/releases/tag/v2.2.0)

With known transition rates, [use a single record](docs/FINITE_RECORDS.md#use-your-own-model)
to estimate the probabilities of different values of a target such as net winding.
[Compare sampling schedules and counters](docs/FINITE_RECORDS.md#compare-recording-protocols)
on the same event trajectories to see how each choice changes the risk of a wrong estimate.

## Choose a task

| Research question | Start here |
| --- | --- |
| What can snapshots hide about a trajectory? | [Physical interpretation](#physical-interpretation) |
| Which target values fit my record, and how likely is each? | [Use your own record](docs/FINITE_RECORDS.md#use-your-own-model) |
| Would more snapshots or another counter reduce error? | [Compare recording protocols](docs/FINITE_RECORDS.md#compare-recording-protocols) |
| Which cycles stay hidden as sampling changes? | [Analyze a network](#analyze-your-own-network) · [Sampling thresholds](docs/SCIENTIFIC_SCOPE.md#how-local-ambiguity-accumulates) |
| Do two counter schemes reveal the same information? | [Compare counters](#compare-counter-configurations) |
| Which extra counters would determine my target? | [Design a readout](docs/TARGET_TASKS.md#use-your-own-target) |
| Do my model’s inputs determine the target I want to predict? | [Scientific ML example](#target-analysis-and-scientific-ml) · [Test predictions](docs/SCIENTIFIC_ML.md#supply-your-models-predictions) |
| What critical limit follows from my graph and rates? | [Construct a critical experiment](docs/CRITICAL_EXPERIMENT.md) |
| Can I reproduce the paper’s calculations? | [Run the reproduction checks](#reproduce-the-paper-evidence) |

## Physical interpretation

Two snapshots show a system at A and then at B. It could have moved directly
from A to B or followed A → C → B. The two paths produce identical snapshots
but differ by one circulation around the triangle.

![Three-state ring: the blue direct A-to-B path and orange A-to-C-to-B path give the same snapshots but differ by one circulation.](docs/snapshot_ambiguity.svg)

Information acquisition is itself a physical process. A recorder’s dynamics
and resources constrain what it can register. Here that constraint enters
through the interval between snapshots. Knowing the transition rates gives
the conditional probabilities of the possible windings. Several can retain
positive probability given the same noiseless record.

A longer observation supplies more snapshots and also lengthens the history
whose winding we want to recover. A detour that changes the winding may be
very unlikely in one short interval, yet a long run offers many opportunities
for such detours to accumulate. How fast must the sampling interval shrink
for the record to determine the accumulated winding of that single run?

For stationary finite-state Markov jump processes, **the theory establishes an
information phase diagram and sharp sampling thresholds for recovering
accumulated cycle histories.** When hidden cycle directions are present, the
number of snapshots must grow faster than the observation time for the
probability of exact recovery to approach one. The theory gives the posterior
laws at critical sampling scales. Under power-law sampling, the coefficient
of logarithmic growth in the residual entropy varies with the sampling
exponent. Its slope changes reveal how many independent hidden cycle
directions emerge at each threshold.

These information transitions persist at equilibrium under detailed balance.
Forward and reverse circulations then balance on average, and the steady-state
entropy production rate is zero. An individual trajectory can still accumulate
net turns between snapshots.

The supported graph is finite, connected, and simple, with positive
transition-rate support in both directions on every edge. The recording
protocol uses regular noiseless state snapshots and optional exact counters.
Integer calculations use the graph and the counter definitions. Transition
rates enter when estimating probabilities for a finite record or computing
path weights in a [critical experiment](docs/CRITICAL_EXPERIMENT.md).

See [Scope and interpretation](#scope-and-interpretation) for result meanings
and the [scientific scope](docs/SCIENTIFIC_SCOPE.md) for the physical assumptions.

## Install

Use Python 3.11–3.13. Create and activate a virtual environment.

**macOS or Linux**

```sh
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install version 2.2.0 in the activated environment on either platform.

```sh
python -m pip install homological-observability==2.2.0
homological-observability --version
```

The command reports `2.2.0`. You can run the [quick start](#quick-start) from any
working directory. Examples that refer to files in `examples/` and the full
verification script require a [source checkout](#full-verification-from-source).

<details>
<summary>Using an earlier version</summary>

Follow the [2.1.0 usage guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v2.1.0/README.md#install)
for an existing 2.1.0 installation. To reproduce work with version 2.0.0, install
`homological-observability==2.0.0` in a separate environment and follow its
[versioned guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v2.0.0/README.md).
For upgrades from 1.x, see the [format and API changes](docs/OUTPUT_CONTRACT.md#reading-earlier-records).

</details>

## Quick start

A flashing ratchet can turn while its potential is ON or OFF. A counter
records the sum of the two signed turn counts (`W`). How well can you infer
their difference (`DeltaW`, ON minus OFF) from that total and a set of snapshots?

```sh
homological-observability posterior --example dfr --output-dir my-record
homological-observability compare-protocols --example dfr --output-dir my-study
```

Open `my-record/report.txt` for one trajectory observed at 50 snapshot times.
Its total-turn count allows only even values of `DeltaW`. With the supplied
transition rates, the most probable value is zero (99.63%).

Open `my-study/report.txt` to compare three ways to observe the **same 64
simulated trajectories** with eight snapshots per path. For each protocol,
the table gives the conditional probability of a wrong best guess for `DeltaW`,
averaged over the 64 records.

| Recorded observations | Mean error risk |
| --- | ---: |
| Snapshots | 39.95% |
| Snapshots and total turns | 15.42% |
| Snapshots, total turns and ON turns | 0% |

Recording signed ON turns (`W_ON`) gives `DeltaW = 2 W_ON − W` on every
trajectory. That identity explains the zero risk in the last row. The report
also gives the snapshot count, counter count and encoded record size for each
protocol.

### Use your own measurements

Start with an editable record from a three-state ring. Each run with
`--output-dir` needs a new directory and saves the input, a human-readable
report, and a machine-readable `result.json`.

```sh
homological-observability posterior --example triangle --output-dir my-ring
```

Edit `my-ring/request.json` to supply your states, directed rates, target
and observations. Run the saved request to see the result for your record.

```sh
homological-observability posterior my-ring/request.json
```

The [finite-record guide](docs/FINITE_RECORDS.md) explains the input fields,
numerical precision and how to import event trajectories for a comparison.
The [kinesin example](docs/FINITE_RECORDS.md#a-mechanical-and-chemical-target)
uses the six-state molecular motor model of [Liepelt and Lipowsky (2007)](https://doi.org/10.1103/PhysRevLett.98.258102).
In the example record, the endpoints and net mechanical step count establish
that net ATP hydrolysis is odd. One additional chemical count fixes it at one ATP molecule.
For a network with proposed counters, [compare their hidden cycle directions](#compare-counter-configurations).

### Target analysis and scientific ML

Suppose you want to train a model to predict `DeltaW`. On the same 64 ratchet
trajectories, the ML example uses 50 snapshots per path. Can those snapshots
and total turns determine the target for every history? How accurately does
a predictor use that information on held-out paths?

Run the [six-state discrete flashing ratchet (DFR) example](docs/SCIENTIFIC_ML.md#model-and-data-provenance)
on a CPU:

```bash
python -m homological_observability.applications.dfr run --output-dir dfr-case
```

Open **`dfr-case/report.txt`**. It reports:

| Recorded information | Can it determine DeltaW? | Next step |
| --- | --- | --- |
| Snapshots and W | No: distinct histories can share the same record | Add a counter for W_ON or W_OFF |
| Snapshots, W and W_ON | Yes: DeltaW = 2 W_ON − W | Reconstruct from the recorded values |
| Snapshots, W and W_OFF | Yes: DeltaW = W − 2 W_OFF | An equally small alternative |

The search proves that **one extra scalar channel is sufficient and necessary
within the supplied pool**. On the bundled dataset, each sufficient scheme
evaluated by the case reconstructs all 64 trajectories with zero mismatch.
This diagnosis helps choose the next experiment: add the missing count to
future collection, replay available full event logs to obtain it, or choose a
prediction target and evaluation suited to the existing records.

The case saves the structural results in `case.json`. With snapshots and total
turns as the available inputs, the baseline predicts the training-set median
on every path. It matches `DeltaW` on 7 of 13 held-out paths. The
[scientific ML guide](docs/SCIENTIFIC_ML.md#run-the-complete-case) shows
how to replay the scores from `dfr-case/predictions.json` or
[evaluate your own predictions](docs/SCIENTIFIC_ML.md#supply-your-models-predictions)
on the same paths. A separate
constructed ambiguity pair tests what identical visible inputs can leave
unresolved; its scores are reported separately from naturally sampled data.

To run just the structural calculations from a [source checkout](#full-verification-from-source),
use the [target request](examples/dfr_target.json) and [design request](examples/dfr_design.json).

```bash
homological-observability target examples/dfr_target.json
homological-observability design examples/dfr_design.json --output-dir dfr-design
```

The [target guide](docs/TARGET_TASKS.md#use-your-own-target) shows how to use your
own graph, fixed records, targets and candidate channels. Each output directory
must be new so that earlier results remain available for comparison and replay.

## Compare counter configurations

Suppose your model has a four-state ring and a seven-state ring joined by a
bridge. State snapshots leave some circulation between observations unknown.
You can add a counter on either ring: **which choice postpones the earliest
remaining cycle ambiguity?**

Call the signed edge counter on the short ring $x$, and the one on the long
ring $y$. A forward crossing adds one and a reverse crossing subtracts one.
The built-in study compares these choices with snapshots alone and with
weighted combinations of the same counters.

### Run the bridge study

Create the study input, then run it into a new results directory:

```bash
homological-observability study-example bridge --output bridge-study.json
homological-observability compare bridge-study.json --output-dir bridge-results
```

The terminal output begins:

```text
Connected rings: select a counter and detect redundancy - COMPLETE
With one channel, which candidate delays the first hidden free layer?
```

Open **`bridge-results/comparison.md`** for the findings and their exact
witnesses. Start with these three configurations:

| Configuration | First hidden layer | Remaining hidden rank |
| --- | ---: | ---: |
| Snapshots only | 2 | 2 |
| Counter $x$ on the four-state ring | 4 | 1 |
| Counter $y$ on the seven-state ring | 2 | 1 |

The first hidden layer identifies the earliest short-time order at which a
free cycle-history direction remains unresolved. A layer $m$ has accumulated
scale $T\delta^{m-1}$, where $T$ is observation time and $\delta$ is the sampling
interval, both in fixed reference-rate units. For this task, counting the
short ring is useful: it moves that first unresolved direction from layer two
to layer four. Counting the long ring leaves the earlier ambiguity in place.

Both choices leave one hidden direction, but they hide different directions.
The full study also shows that a weighted counter $z=2x+y$ ties $x$ on the
first-hidden-layer objective while retaining different information; adding
$2z$ alongside $z$ is redundant. This is why the report compares exact
information relations as well as scalar summaries.

`COMPLETE` means all six configurations were analyzed over the full integer
cycle group. It describes the scope of the calculation; the remaining hidden
directions describe the unresolved history. The study uses the sampling law
$\delta=T^{-3/8}$. The [comparison guide](docs/COMPARISON_GUIDE.md) explains all
six choices and their sampling interpretation.

Keep the results directory to share or repeat the study. Its `README.md`
gives the replay command, `study.json` holds the input, and `comparison.json`
retains the full structured evidence. Each run uses a new output directory.

## Analyze your own network

Use `analyze` for a single observation scheme, or `compare` for a study of
several counter configurations. Both take a graph and optional counter rules;
sampling parameters are optional. For a specific trajectory target, use
[`target` and `design`](docs/TARGET_TASKS.md#use-your-own-target) with the same
graph and cochain conventions.

### Analyze one configuration

Prepare `my-model.json` using the [model input guide](docs/MODEL_GUIDE.md),
then run:

```bash
homological-observability analyze my-model.json
```

Each exported study also includes a model file for every candidate. For
example, you can use `bridge-results/models/config-x.json` with the same
command to inspect the short-ring counter on its own. The
[worked two-loop example](docs/END_TO_END_EXAMPLE.md) explains a single
analysis and its integer results.

### Compare your own configurations

Save a copy of `bridge-study.json` as `my-study.json` and adapt the same study:

1. Set the study `name`, its `question`, and `model.name` to describe your task.
2. Replace `model.vertices` and `model.edges` with your graph.
3. Give each candidate an `id` and a readable `label`, then define its counters
   in `readouts`. Each integer edge coefficient specifies a signed increment;
   an empty readout list represents snapshots alone.
4. Replace the example's `alpha: 0.375` with your own sampling exponent, or
   remove it to compare graph and counter information without a sampling law.
   For a finite-scale request, remove `alpha` and set both `observation_time`
   and `sampling_interval` in the stated reference-rate units.
5. Set `analysis.max_cycles` in the study JSON to bound the default cycle
   enumeration, then run into a new directory:

```bash
homological-observability compare my-study.json --output-dir my-results
```

The [input guide](docs/MODEL_GUIDE.md) explains how to translate a physical
model into graph and counter fields. The [comparison guide](docs/COMPARISON_GUIDE.md#compare-your-own-configurations)
walks through editing a study and checking its assumptions.

For dense graphs, both `analyze` and `compare` accept
`--backend generators --max-generators 1000` to compute each integer layer
from [shortest-path cycle generators](docs/CONVENTIONS.md#shortest-path-generators)
within the chosen budget. On the complete graph with eight vertices,
56 generators give the same layers as all 8,018 simple cycles.

`LIMIT_REACHED` identifies the exhausted limit. `PARTIAL_HORIZON` restricts
conclusions to the computed layers. The [status guide](docs/COMPARISON_GUIDE.md#check-completeness-and-recover-from-errors)
explains how to continue each calculation.

## Python API

Run this example with `python` in the activated environment. The installed
package includes the bridge model.

```python
import homological_observability as ho

study = ho.load_study_example("bridge")
comparison = ho.compare_configurations(study)
print(ho.render_comparison_text(comparison))
```

In the report, counting the short ring moves the first hidden layer from 2
to 4. Counting the long ring leaves it at 2. The [bridge study](#compare-counter-configurations)
explains why two counters with the same remaining hidden rank give different results.

For your own structural study, use `ho.load_study("my-study.json")`. For
one configuration, load the graph and readouts with `ho.load_model(path)`.
These functions are available in the imported module `ho`.

| Structural task | Python functions |
| --- | --- |
| [Analyze a model](docs/MODEL_GUIDE.md) | `analyze_model` |
| [Compare counters](docs/COMPARISON_GUIDE.md) | `compare_configurations` |
| [Design a readout](docs/TARGET_TASKS.md#three-calculation-interfaces) | `analyze_target`, `design_readouts`, `evaluate_target` |
| [Critical limit](docs/CRITICAL_EXPERIMENT.md) | `analyze_critical_model` |

For **finite observations**, choose the input that matches your study.

- With [one measured record](docs/FINITE_RECORDS.md#use-your-own-model), call `ho.infer_target_posterior(request)`.
- To [compare protocols](docs/FINITE_RECORDS.md#compare-recording-protocols) on complete or simulated event paths, use `ho.compare_recording_protocols`.

For paired trajectory data and `dfr.evaluate_predictions`, see the
[scientific ML example in Python](docs/SCIENTIFIC_ML.md#supply-your-models-predictions).

The guides include editable inputs and result handling. The
[output guide](docs/OUTPUT_CONTRACT.md) describes the structured results and exit codes.
The [target guide](docs/TARGET_TASKS.md#json-and-replay) covers target requests,
results and replay.

## Scope and interpretation

The software computes exact integer cycle lattices, their visible images and
hidden directions. It retains finite-index information, such as parity,
that ordinary real rank can miss. Counter comparisons use these exact
relations on the reported scope.

Sampling thresholds, phase labels, and entropy coefficients apply the
long-time asymptotic results for a fixed graph, generator, and readout, with
a stationary initial law. For a finite observation, `posterior` conditions
on the first recorded state and uses the known rates to estimate the
distribution of one integer target. The numerical solver supports up to two
independent integer coordinates across the target and all counters. An exact
target can also be decoded at higher rank. The [scientific scope](docs/SCIENTIFIC_SCOPE.md)
gives the assumptions behind each result.

The [paper map](PAPER_MAP.md) connects implemented objects to the theoretical
results and the reproduced finite-model calculations.

### Exact sampling requests

Model and study format 2 accept `"alpha": "1/3"`.
This gives an exactly critical fourth layer. A JSON number such as
`0.3333333333333333` keeps its binary floating-point value and gives a slightly
positive exponent at that layer. Use the fraction when your intended law is
exactly one third. Phase classification uses the exact value supplied.

Reports follow the request: structure alone shows hidden information and
counter relations; an exponent adds phases and entropy contributions; a
finite observation time and interval add exposure scales with each hidden
graded quotient. Each result states which layers were computed.

## Reproduce the paper evidence

Start with [Install](#install) in a new working directory; the package includes
the models and reference data needed here. Then regenerate the finite-cycle
calculations and compare them with the packaged references:

```bash
homological-observability reproduce --check --output-dir generated_results
```

Successful verification prints:

```text
PASS: all calculation checks completed
PASS: generated tables agree with frozen reference results
```

The same files are available in `generated_results/` and in the repository.

| What to inspect | Reference files |
| --- | --- |
| Interpretation of the checks | [Computational report](results/REPORT.md) |
| Three numerical checks in one figure | [PNG preview](results/companion_summary.png) · [Scalable SVG](results/companion_summary.svg) |
| Numerical values | [Appendix checks](results/selected_appendix_checks.csv) · [Critical kernels](results/critical_kernel_results.csv) |

The calculations cover finite-cycle bridge posteriors, critical kernels, a Poisson-averaged MAP
identity, and reciprocal-lattice peak suppression. Reference acceptance uses
documented numerical tolerances; the [output guide](docs/OUTPUT_CONTRACT.md#artifact-roles)
describes how results and file identities are compared.

<details>
<summary>Verify a source checkout or explore finite-ring bridges</summary>

### Full verification from source

To verify version 2.2.0, unpack the [source ZIP](https://github.com/yeruciwenrou-dotcom/homological-observability/archive/refs/tags/v2.2.0.zip) or clone its tag:

```sh
git clone --branch v2.2.0 --single-branch https://github.com/yeruciwenrou-dotcom/homological-observability.git
cd homological-observability
```

If you unpacked the ZIP, open the directory containing `quickstart.py`.
The [main branch](https://github.com/yeruciwenrou-dotcom/homological-observability/tree/main) tracks ongoing development.

Run `python3 quickstart.py` on macOS or Linux, or `py -3.12 quickstart.py` on
Windows. To install the checkout in an existing activated environment for
interactive use, run `python -m pip install .` from the repository root.

The script installs pinned dependencies, runs the reader-side test suite,
and reproduces the frozen paper calculations. It manages the repository's
`.venv`, reusing it for the same Python version and recreating it when the
interpreter's major or minor version changes. Keep any separately managed
environment in another directory. Installation needs internet access.
Fresh outputs are kept separate from the reference files in `results/`.

For historical reproduction, the
[2.0.0 source archive](https://zenodo.org/records/23618828) includes that
release's code, documentation, tests, dependency pins and reference results.
Unpack `homological-observability-2.0.0-source.zip` into a separate directory
and run the same script from its root.

### Finite-ring bridges

To inspect winding probabilities between opposite-vertex snapshots on a
symmetric four-state ring, run from the source directory:

```bash
.venv/bin/python explore_cycles.py --cycle 4 --residue 2 --delta 0.1
```

On Windows:

```powershell
.venv\Scripts\python.exe explore_cycles.py --cycle 4 --residue 2 --delta 0.1
```

The two shortest routes have equal weight. The table also reports the
probability mass covered by the displayed range.

</details>

## Documentation and feedback

| What you need | Guides and references |
| --- | --- |
| Prepare inputs and compare measurements | [Model inputs](docs/MODEL_GUIDE.md) · [Counter comparisons](docs/COMPARISON_GUIDE.md) · [Worked two-loop example](docs/END_TO_END_EXAMPLE.md) |
| Analyze observations or predictions | [Finite records and protocols](docs/FINITE_RECORDS.md) · [Target and readout design](docs/TARGET_TASKS.md) · [Scientific ML](docs/SCIENTIFIC_ML.md) |
| Connect a calculation to the theory | [Paper map](PAPER_MAP.md) · [Scientific scope](docs/SCIENTIFIC_SCOPE.md) · [Critical experiments](docs/CRITICAL_EXPERIMENT.md) |
| Check a target derivation | [Technical note](docs/TARGET_THEORY.md) · [Printable PDF](docs/TARGET_THEORY.pdf) · [Validation results](docs/TARGET_VALIDATION.md) |
| Interpret an output or check a method | [Output fields and status codes](docs/OUTPUT_CONTRACT.md) · [Conventions](docs/CONVENTIONS.md) · [Numerical methods](docs/NUMERICS.md) |
| Verify paper results | [Reproduction commands](#reproduce-the-paper-evidence) · [Computational report](results/REPORT.md) |

For version history, see the [changelog](CHANGELOG.md). The
[contributing guide](CONTRIBUTING.md) explains how to propose changes.
Use [Issues](https://github.com/yeruciwenrou-dotcom/homological-observability/issues/new/choose)
to report a problem or discuss a research use.

## Citation and license

Cite the paper for theoretical results and the software for computations.
When your work uses both, cite them separately.

### Paper

<details>
<summary>Copy the paper citation as BibTeX</summary>

```bibtex
@misc{liu2026stochastic_histories,
  author = {Liu, HongZheng and Tian, YiNuo and Wu, Zhiyue and Cheng, Jianqun},
  title = {{Stochastic Histories at Finite Temporal Resolution:
            Homological Observability and Information Phase Diagrams
            in Markov Jump Processes}},
  year = {2026},
  howpublished = {Zenodo},
  doi = {10.5281/zenodo.23424849},
  url = {https://doi.org/10.5281/zenodo.23424849},
  note = {Preprint, version 1}
}
```

</details>

### Software

For computations made with [version 2.2.0](https://github.com/yeruciwenrou-dotcom/homological-observability/releases/tag/v2.2.0), cite:

> Liu, H., Tian, Y., Wu, Z., & Cheng, J. (2026). *Homological Observability:
> Cycle Histories and Sampling Thresholds in Markov Jump Processes* (Version 2.2.0) [Computer
> software]. https://doi.org/10.5281/zenodo.24422331

The software series is archived at
[doi:10.5281/zenodo.23329442](https://doi.org/10.5281/zenodo.23329442).
GitHub's citation menu and
[`CITATION.cff`](CITATION.cff) provide the software citation.

Software authors: HongZheng Liu, YiNuo Tian, Zhiyue Wu, and Jianqun Cheng.

The software is available under the [MIT License](LICENSE). The archived
paper is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
