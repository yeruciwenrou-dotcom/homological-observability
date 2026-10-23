# Homological Observability

This package provides tools for analyzing the
recoverability of accumulated cycle histories in finite-state Markov jump
processes.

A state snapshot records where a system is; its cycle history records the
net circulation accumulated around the network. At finite temporal
resolution, the same sequence of snapshots can hide different net windings,
even when all transition rates are known. Longer observation adds both
snapshots and history to recover. How rapidly must sampling improve to keep
pace, and how can additional counters reduce that requirement?

The theoretical foundation is
*[Stochastic Histories at Finite Temporal Resolution: Homological Observability and Information Phase Diagrams in Markov Jump Processes](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes)*
([paper DOI](https://doi.org/10.5281/zenodo.23424849)). The package also
reproduces the paper's finite-model calculations.

[Read the paper](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes) ·
[Reproduce the calculations](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md#reproduce-the-paper-evidence) ·
[Cite](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md#citation-and-license)

**Analyze your own network.** Provide its transition graph and optional
integer counter rules. Each counter accumulates signed integer increments on
edge crossings. The software computes hidden cycle differences and their
exposure layers, the corresponding asymptotic sampling requirements, and the
information retained by different
counter configurations. Use the command line or Python to obtain explanatory
reports and exact integer evidence.

| Task | Inputs | Guide |
| --- | --- | --- |
| Analyze your own network and observation scheme | Graph, optional counters and sampling parameters | [`analyze`](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md#analyze-your-own-network) |
| Compare counter configurations | Several counter choices on one graph | [`compare`](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md#quick-start) |
| Construct a critical-limit experiment | Graph, optional counters, exact rates, critical layer and intensity | [`critical`](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/CRITICAL_EXPERIMENT.md) |
| Reproduce the paper's calculations | Included models and reference data | [`reproduce`](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md#reproduce-the-paper-evidence) |

The graph must be finite, connected, and simple, with positive transition-rate
support in both directions. The recording protocol uses regular noiseless
state snapshots and optional exact counters. **Network and counter analyses
need no rate values.** The critical experiment uses exact positive rates to
compute path weights and limiting mark distributions.

## Install

Use Python 3.11–3.13. In your working directory, create a virtual environment
and install the package from PyPI:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install homological-observability==1.2.0
```

The [installation guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md#install)
includes Windows commands. On Windows, use
`.venv\Scripts\homological-observability.exe` in place of
`.venv/bin/homological-observability` below, and `.venv\Scripts\python.exe`
in place of `.venv/bin/python`. Activation is optional. Installation needs
internet access; examples and reference data are included in the package.

## Try a counter comparison

A four-state ring and a seven-state ring are connected by a bridge. You can
count signed crossings on either ring: which choice postpones the earliest
remaining cycle-history ambiguity?

```bash
.venv/bin/homological-observability study-example bridge --output bridge-study.json
.venv/bin/homological-observability compare bridge-study.json --output-dir bridge-results
```

Open `bridge-results/comparison.md`. The study completes all six candidates;
three of its results are:

| Configuration | First hidden layer | Remaining hidden rank |
| --- | ---: | ---: |
| Snapshots only | 2 | 2 |
| Counter x on the four-state ring | 4 | 1 |
| Counter y on the seven-state ring | 2 | 1 |

Counting the short ring postpones the first unresolved cycle direction to
layer four. Counting the long ring leaves the earlier ambiguity in place.
The two counters retain different information, even though each leaves one
hidden direction. The study also shows that a weighted counter can tie a
scalar objective without retaining the same information, and that a
proportional extra channel is redundant.

The [worked comparison](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/COMPARISON_GUIDE.md)
explains the hidden layers and the example's sampling law. `COMPLETE` records
the scope of the calculation; the report describes the remaining ambiguity.
The bundle contains structured results, exact witnesses, the input, and replay
instructions. Each run uses a new output directory.

## Reproduce the paper evidence

```bash
.venv/bin/homological-observability reproduce --check --output-dir generated_results
```

This command regenerates the paper's finite-model calculations, compares them
with the packaged reference data, and writes `generated_results/REPORT.md`
and `generated_results/companion_summary.png`. For pinned dependencies
and the reader-side test suite, follow the
[reproduction guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md#full-verification-from-source).

## Analyze your own network

For one observation scheme, prepare `my-model.json` with your graph, optional
counter rules, and any sampling parameters. The
[model input guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/MODEL_GUIDE.md)
explains the fields and includes a complete example. Run:

```bash
.venv/bin/homological-observability analyze my-model.json
```

To compare several counter configurations, adapt the bridge study.
Save a copy of `bridge-study.json` as `my-study.json`. Update the study and
model names, research question, graph, and candidate counters. Replace the
example's `alpha: 0.375` with your own sampling exponent, or remove it for a
comparison of graph and counter information alone. Keep an explicit cycle
enumeration budget, then run:

```bash
.venv/bin/homological-observability compare my-study.json --output-dir my-results
```

The [study editing guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/COMPARISON_GUIDE.md#compare-your-own-configurations)
walks through these choices. The [input guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/MODEL_GUIDE.md)
describes signed edge increments, sampling units, validation, and resource
limits. Every exported study also includes a model file for each candidate,
ready to inspect separately with `analyze`.

## Python API

Run this with the virtual environment's Python interpreter:

```python
import homological_observability as ho

study = ho.load_study_example("bridge")
comparison = ho.compare_configurations(study)
print(ho.render_comparison_text(comparison))
```

Use `ho.load_study("my-study.json")` for your own study. The
[output guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/OUTPUT_CONTRACT.md)
describes structured results and renderers, including single-configuration
analysis and rate-dependent critical experiments.

## Interpretation and further reading

Integer lattice calculations and finite catalogues are exact when complete.
Sampling thresholds, phase labels, and entropy coefficients describe long-time
asymptotic limits under the stated model assumptions. Choosing a sampling
interval for a specified finite-run error tolerance requires additional risk
analysis. Cycle enumeration can grow exponentially; use computation budgets
and check the reported completeness of each result.

- [Overview and first study](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md)
- [Scientific assumptions and research uses](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/SCIENTIFIC_SCOPE.md)
- [Integer layers and sampling: a worked two-loop example](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/END_TO_END_EXAMPLE.md)
- [Rate-dependent critical experiments](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/docs/CRITICAL_EXPERIMENT.md)
- [Changes by version](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/CHANGELOG.md)
- [Report an issue](https://github.com/yeruciwenrou-dotcom/homological-observability/issues)

## Theory and citation

The [paper map](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/PAPER_MAP.md)
connects the software's calculations to the theoretical results and paper evidence.

Cite the paper for theoretical results and the software for computations.
When your work uses both, cite them separately. The
[citation guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.2.0/README.md#citation-and-license)
provides the full paper and software references and a copyable paper BibTeX entry.
Record the software version used and the Git commit for a source checkout.

Authors: HongZheng Liu, YiNuo Tian, Zhiyue Wu, and Jianqun Cheng.

The software is distributed under the MIT License. The archived paper is
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
