# Homological Observability

[![PyPI](https://img.shields.io/pypi/v/homological-observability)](https://pypi.org/project/homological-observability/)
[![DOI: 10.5281/zenodo.23329442](docs/zenodo-doi.svg)](https://doi.org/10.5281/zenodo.23329442)

Analyze what your observations reveal about a system's accumulated cycle
history, and compare counters that could reveal more. Homological
Observability is research software for scientists working with a known
finite-state Markov jump model and considering how to observe it.

Provide the network and candidate **exact cumulative integer counter rules**.
The software identifies cycle-history differences that remain hidden,
compares the information retained by each configuration, and computes
asymptotic sampling requirements. Results include an explanatory report,
exact integer evidence, and saved inputs for another run. Use it through the
command line or Python.

| You provide | You can determine |
| --- | --- |
| A known transition graph | Which cycle-history ambiguities arise between snapshots |
| Counter rules as signed integer increments on edges | Which ambiguities each counter resolves, and which channels are redundant |
| Optional sampling parameters | Asymptotic regimes, or exposure scales at a specified time and sampling interval |

The supported graph is finite, connected, and simple, with positive
transition-rate support in both directions on every edge. The observation
model uses regular noiseless state snapshots and exact counters. Counter
comparison needs the graph and measurement rules; exact rates are needed
for the separate rate-dependent critical experiment. The input describes a
model and observation scheme, rather than a measured trajectory.

[Try a comparison](#quick-start) · [Use your own network](#analyze-your-own-network) ·
[Python API](#python-api) · [Scientific scope](#scope-and-interpretation) ·
[Documentation](#documentation-and-feedback)

## Install

Use Python 3.11–3.13. These instructions cover the unreleased `1.2.0.dev0`
source version. The published [1.1.0 package](https://pypi.org/project/homological-observability/1.1.0/)
has its own [installation and usage guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.1.0/README.md).

Clone the source and enter its root directory:

```bash
git clone --branch feature/configuration-comparison https://github.com/yeruciwenrou-dotcom/homological-observability.git
cd homological-observability
```

Create a virtual environment and install the package. On macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
```

<details>
<summary>Windows PowerShell</summary>

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install .
```

Python 3.11 or 3.13 can be selected in place of 3.12.

</details>

These commands use the virtual environment directly, so activation is optional.
Installation needs internet access; examples and reference data are included
in the package.
The commands below run from this directory. In the linked guides, use
`.venv\Scripts\homological-observability.exe` in place of
`.venv/bin/homological-observability` on Windows, and
`.venv\Scripts\python.exe` in place of `.venv/bin/python`.

## Quick start

Suppose your model has a four-state ring and a seven-state ring joined by a
bridge. State snapshots leave some circulation between observations unknown.
You can add a counter on either ring: **which choice postpones the earliest
remaining cycle ambiguity?**

Call the signed edge counter on the short ring $x$, and the one on the long
ring $y$. A forward crossing adds one and a reverse crossing subtracts one.
The built-in study compares these choices with snapshots alone and with
weighted combinations of the same counters.

### Compare counter configurations

Create the study input, then run it into a new results directory:

```bash
.venv/bin/homological-observability study-example bridge --output bridge-study.json
.venv/bin/homological-observability compare bridge-study.json --output-dir bridge-results
```

<details>
<summary>Windows PowerShell</summary>

```powershell
.venv\Scripts\homological-observability.exe study-example bridge --output bridge-study.json
.venv\Scripts\homological-observability.exe compare bridge-study.json --output-dir bridge-results
```

</details>

The terminal output begins:

```text
Connected rings: select a counter and detect redundancy — COMPLETE
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
5. Choose an explicit `max_cycles` budget and run into a new directory:

```bash
.venv/bin/homological-observability compare my-study.json --output-dir my-results
```

<details>
<summary>Windows PowerShell</summary>

```powershell
.venv\Scripts\homological-observability.exe compare my-study.json --output-dir my-results
```

</details>

The [input guide](docs/MODEL_GUIDE.md) explains how to translate a physical
model into graph and counter fields. The [comparison guide](docs/COMPARISON_GUIDE.md#compare-your-own-configurations)
walks through editing a study and checking its assumptions.

Cycle enumeration can grow exponentially with the network. Keep a budget
when trying an unfamiliar graph. A `LIMIT_REACHED` result identifies the
exhausted limit; `PARTIAL_HORIZON` restricts conclusions to the computed
layers. The [status guide](docs/COMPARISON_GUIDE.md#check-completeness-and-recover-from-errors)
explains how to continue each calculation.

For a single configuration, use `analyze` with a model file. Every exported
study includes such a file for each candidate; for example:

```bash
.venv/bin/homological-observability analyze bridge-results/models/config-x.json
```

<details>
<summary>Windows PowerShell</summary>

```powershell
.venv\Scripts\homological-observability.exe analyze bridge-results/models/config-x.json
```

</details>

## Python API

Run this example with `.venv/bin/python` on macOS/Linux or
`.venv\Scripts\python.exe` on Windows. The bridge model is included in the
installed package:

```python
import homological_observability as ho

study = ho.load_study_example("bridge")
comparison = ho.compare_configurations(study)
print(ho.render_comparison_text(comparison))
```

Use `ho.load_study("my-study.json")` for a saved study. To work with one
configuration, use `ho.load_model(path)` and `ho.analyze_model(model)`.
The [comparison guide](docs/COMPARISON_GUIDE.md) covers editable Python inputs
and saving study bundles; the [output guide](docs/OUTPUT_CONTRACT.md) describes
the result objects and renderers.

## Scope and interpretation

The software computes exact integer cycle lattices, their visible images and
hidden directions. It retains finite-index information, such as parity,
that ordinary real rank can miss. Counter comparisons use these exact
relations on the reported scope.

Sampling thresholds, phase labels, and entropy coefficients apply the
long-time asymptotic results for a fixed graph, generator, and readout, with
a stationary initial law. A sampling interval chosen to meet a specified
finite-run error tolerance needs additional risk analysis. The
[scientific scope](docs/SCIENTIFIC_SCOPE.md) explains the physical question,
assumptions, and interpretation of each type of result.

The theoretical foundation is
*[Stochastic Histories at Finite Temporal Resolution: Homological Observability and Information Phase Diagrams in Markov Jump Processes](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes)*.
The [paper map](PAPER_MAP.md) connects implemented objects to the manuscript;
the software also reproduces its finite-model calculations.

## Documentation and feedback

| Your next task | Guide |
| --- | --- |
| Compare counters and understand their differences | [Comparison studies](docs/COMPARISON_GUIDE.md) |
| Prepare a model or study | [Input fields and physical modeling](docs/MODEL_GUIDE.md) |
| Understand integer layers, parity, and sampling requirements | [Worked two-loop example](docs/END_TO_END_EXAMPLE.md) |
| Add known rates and construct a critical-limit experiment | [Rate-dependent critical experiment](docs/CRITICAL_EXPERIMENT.md) |
| Interpret structured results or handle incomplete calculations | [Output fields, statuses, and formats](docs/OUTPUT_CONTRACT.md) |
| Check mathematical or numerical details | [Conventions](docs/CONVENTIONS.md) · [Numerical methods](docs/NUMERICS.md) |
| Reproduce the paper's finite-model calculations | [Reproduction commands](#reproduce-the-paper-evidence) · [Computational report](results/REPORT.md) |
| Inspect changes or contribute | [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) |

Use [Issues](https://github.com/yeruciwenrou-dotcom/homological-observability/issues/new/choose)
to report a problem or discuss a research use.

## Reproduce the paper evidence

With the package installed, regenerate the finite-cycle calculations and
compare them with the packaged references:

```bash
.venv/bin/homological-observability reproduce --check --output-dir generated_results
```

<details>
<summary>Windows PowerShell</summary>

```powershell
.venv\Scripts\homological-observability.exe reproduce --check --output-dir generated_results
```

</details>

Open `generated_results/REPORT.md` for the scientific summary and
`generated_results/companion_summary.png` for the figure. The calculations
cover finite-cycle bridge posteriors, critical kernels, a Poisson-averaged MAP
identity, and reciprocal-lattice peak suppression. Reference acceptance uses
documented numerical tolerances; the [output guide](docs/OUTPUT_CONTRACT.md#artifact-roles)
describes how results and file identities are compared.

<details>
<summary>Verify a source checkout or explore finite-ring bridges</summary>

### Full verification from source

From the source directory, run:

```bash
python3 quickstart.py
```

On Windows:

```powershell
py -3.12 quickstart.py
```

The script installs pinned dependencies, runs the reader-side test suite,
and reproduces the frozen paper calculations. It manages the repository's
`.venv`, reusing it for the same Python version and recreating it when the
interpreter's major or minor version changes. Keep any separately managed
environment in another directory. Installation needs internet access.
Fresh outputs are kept separate from the reference files in `results/`.

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

## Citation and license

Cite the software for computations performed with this package:

> Liu, H., Tian, Y., Wu, Z., & Cheng, J. (2026). *Homological Observability:
> Cycle Histories and Sampling Thresholds in Markov Jump Processes* (Version 1.1.0) [Computer
> software]. Zenodo. https://doi.org/10.5281/zenodo.23329444

This DOI identifies the archived 1.1.0 release. Record the version used and,
for a source checkout, the exact Git commit. GitHub's citation menu and
[`CITATION.cff`](CITATION.cff) provide the software citation.

Cite the paper for theoretical results. It is available on
[alphaXiv](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes),
with version 1 and its PDF archived on Zenodo:
[10.5281/zenodo.23424849](https://doi.org/10.5281/zenodo.23424849).

Software authors: HongZheng Liu, YiNuo Tian, Zhiyue Wu, and Jianqun Cheng.

The software is available under the [MIT License](LICENSE). The archived
paper is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
