# Homological Observability

[![PyPI](https://img.shields.io/pypi/v/homological-observability?logo=pypi)](https://pypi.org/project/homological-observability/)
[![Software DOI: 10.5281/zenodo.23329442](docs/zenodo-doi.svg)](https://doi.org/10.5281/zenodo.23329442)

This repository provides research software for analyzing the
recoverability of accumulated cycle histories in finite-state Markov jump
processes. Use it to study your own network, compare observation schemes,
and reproduce the paper's finite-model calculations.

[Install and try](#install) · [Your network](#analyze-your-own-network) ·
[Read the paper](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes) ·
[Reproduce](#reproduce-the-paper-evidence) · [Cite](#citation-and-license)

A state snapshot records where a system is; its cycle history records the
net circulation accumulated around the network. At finite temporal
resolution, the same sequence of snapshots can hide different net windings,
even when all transition rates are known. Longer observation adds both
snapshots and history to recover. How rapidly must sampling improve to keep
pace, and how can additional counters reduce that requirement?

**What the theory establishes.** The paper organizes unresolved cycle
differences into an integer hierarchy and derives the asymptotic sampling
conditions for recovering accumulated windings. Its information phase diagram
describes how residual uncertainty grows as observation time and sampling
resolution change. These transitions persist at equilibrium under detailed
balance. The [scientific scope](docs/SCIENTIFIC_SCOPE.md) explains the model
assumptions and the connection between topology, recording, and recovery.

**Analyze your own network.** Provide its transition graph and optional
integer counter rules. Each counter accumulates signed integer increments on
edge crossings. Find which cycle differences remain hidden, how sampling
must scale to resolve them, and which counter choices reveal different or
redundant information. The command line and Python API return explanatory
reports backed by exact integer calculations.

| Task | Inputs | Start here |
| --- | --- | --- |
| Analyze your own network and observation scheme | Graph, optional counters and sampling parameters | [Prepare and analyze a model](#analyze-your-own-network) |
| Compare counter configurations | Several counter choices on one graph | [Run a worked comparison](#quick-start) |
| Construct a critical-limit experiment | Graph, optional counters, exact rates, critical layer and intensity | [Add rates and construct the experiment](docs/CRITICAL_EXPERIMENT.md) |
| Reproduce the paper's calculations | Included models and reference data | [Regenerate and check the results](#reproduce-the-paper-evidence) |

The supported graph is finite, connected, and simple, with positive
transition-rate support in both directions on every edge. The recording
protocol uses regular noiseless state snapshots and optional exact counters.
**Network and counter analyses need no rate values.** The critical experiment
uses exact positive rates to compute path weights and limiting mark
distributions.

[Python API](#python-api) · [Scientific scope](#scope-and-interpretation) ·
[Documentation](#documentation-and-feedback)

## Install

Use Python 3.11–3.13. In your working directory, create a virtual environment
and install the package from PyPI. On macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install homological-observability==1.2.1
```

<details>
<summary>Windows PowerShell</summary>

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install homological-observability==1.2.1
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

## Reproduce the paper evidence

Start with [Install](#install) in a new working directory; the package includes
the models and reference data needed here. Then regenerate the finite-cycle
calculations and compare them with the packaged references:

```bash
.venv/bin/homological-observability reproduce --check --output-dir generated_results
```

<details>
<summary>Windows PowerShell</summary>

```powershell
.venv\Scripts\homological-observability.exe reproduce --check --output-dir generated_results
```

</details>

Successful verification prints:

```text
PASS: all calculation checks completed
PASS: generated tables agree with frozen reference results
```

| Result in `generated_results/` | What to read |
| --- | --- |
| `REPORT.md` | Scientific summary and interpretation of the checks |
| `companion_summary.png` | Summary figure |
| `selected_appendix_checks.csv`, `critical_kernel_results.csv` | Numerical tables for further inspection |

The calculations
cover finite-cycle bridge posteriors, critical kernels, a Poisson-averaged MAP
identity, and reciprocal-lattice peak suppression. Reference acceptance uses
documented numerical tolerances; the [output guide](docs/OUTPUT_CONTRACT.md#artifact-roles)
describes how results and file identities are compared.

<details>
<summary>Verify a source checkout or explore finite-ring bridges</summary>

### Full verification from source

For the archived source, download and unpack
`homological-observability-1.2.1-source.zip` from
[Zenodo](https://zenodo.org/records/23604825), then open a terminal in the
extracted `homological-observability-1.2.1` directory. The archive includes
the code, documentation, tests, pinned dependencies, and reference results.

You can also clone the release and enter its source directory:

```bash
git clone --branch v1.2.1 https://github.com/yeruciwenrou-dotcom/homological-observability.git
cd homological-observability
```

Then run:

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

## Analyze your own network

Use `analyze` for a single observation scheme, or `compare` for a study of
several counter configurations. Both take a graph and optional counter rules;
sampling parameters are optional.

### Analyze one configuration

Prepare `my-model.json` using the [model input guide](docs/MODEL_GUIDE.md),
then run:

```bash
.venv/bin/homological-observability analyze my-model.json
```

<details>
<summary>Windows PowerShell</summary>

```powershell
.venv\Scripts\homological-observability.exe analyze my-model.json
```

</details>

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

The [paper map](PAPER_MAP.md) connects implemented objects to the theoretical
results and the reproduced finite-model calculations.

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

## Citation and license

Cite the paper for theoretical results and the software for computations.
When your work uses both, cite them separately.

### Paper

> Liu, H., Tian, Y., Wu, Z., & Cheng, J. (2026). *Stochastic Histories at Finite
> Temporal Resolution: Homological Observability and Information Phase Diagrams
> in Markov Jump Processes* (Version 1) [Preprint]. Zenodo.
> https://doi.org/10.5281/zenodo.23424849

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

> Liu, H., Tian, Y., Wu, Z., & Cheng, J. (2026). *Homological Observability:
> Cycle Histories and Sampling Thresholds in Markov Jump Processes* (Version 1.2.1) [Computer
> software]. Zenodo. https://doi.org/10.5281/zenodo.23604825

Record the software version used and, for a source checkout, the exact Git
commit. GitHub's citation menu and
[`CITATION.cff`](CITATION.cff) provide the software citation.

Software authors: HongZheng Liu, YiNuo Tian, Zhiyue Wu, and Jianqun Cheng.

The software is available under the [MIT License](LICENSE). The archived
paper is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
