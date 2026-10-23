# Homological Observability

Analyze what your observations reveal about accumulated cycle history, and
compare counters that could reveal more. Homological Observability is
research software for scientists working with a known finite-state Markov
jump model and considering how to observe it.

Provide a transition graph and candidate **exact cumulative integer counter
rules**. The software identifies hidden cycle-history differences, compares
information gains and redundant channels, and computes asymptotic sampling
requirements. It produces explanatory reports, exact integer evidence, and
saved inputs for another run, through the command line or Python.

The graph must be finite, connected, and simple, with positive transition-rate
support in both directions on every edge. The observation model uses regular
noiseless state snapshots and exact counters. Inputs specify a model and
measurement rules, rather than a measured trajectory. Counter comparisons
need rate support; rate-dependent critical experiments also need exact
rates.

## Install

Use Python 3.11–3.13. These instructions cover unreleased source version
`1.2.0.dev0`:

```bash
git clone --branch feature/configuration-comparison https://github.com/yeruciwenrou-dotcom/homological-observability.git
cd homological-observability
python3 -m venv .venv
.venv/bin/python -m pip install .
```

The [installation guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/README.md#install)
includes Windows commands. On Windows, use
`.venv\Scripts\homological-observability.exe` in place of
`.venv/bin/homological-observability` below, and `.venv\Scripts\python.exe`
in place of `.venv/bin/python`. Activation is optional. The published
[1.1.0 package](https://pypi.org/project/homological-observability/1.1.0/)
has its own [installation and usage guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.1.0/README.md).

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

The [worked comparison](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/COMPARISON_GUIDE.md)
explains the hidden layers and the example's sampling law. `COMPLETE` records
the scope of the calculation; the report describes the remaining ambiguity.
The bundle contains structured results, exact witnesses, the input, and replay
instructions. Each run uses a new output directory.

## Use your own model

Save a copy of `bridge-study.json` as `my-study.json`. Update the study and
model names, research question, graph, and candidate counters. Replace the
example's `alpha: 0.375` with your own sampling exponent, or remove it for a
comparison of graph and counter information alone. Keep an explicit cycle
enumeration budget, then run:

```bash
.venv/bin/homological-observability compare my-study.json --output-dir my-results
```

The [study editing guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/COMPARISON_GUIDE.md#compare-your-own-configurations)
walks through these choices. The [input guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/MODEL_GUIDE.md)
describes signed edge increments, sampling units, validation, and resource
limits. Use `analyze` with a model file when you need just one configuration.

## Python API

Run this with the virtual environment's Python interpreter:

```python
import homological_observability as ho

study = ho.load_study_example("bridge")
comparison = ho.compare_configurations(study)
print(ho.render_comparison_text(comparison))
```

Use `ho.load_study("my-study.json")` for your own study. The
[output guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/OUTPUT_CONTRACT.md)
describes structured results and renderers, including single-configuration
analysis and rate-dependent critical experiments.

## Interpretation and further reading

Integer lattice calculations and finite catalogues are exact when complete.
Sampling thresholds, phase labels, and entropy coefficients describe long-time
asymptotic limits under the stated model assumptions. Choosing a sampling
interval for a specified finite-run error tolerance requires additional risk
analysis. Cycle enumeration can grow exponentially; use computation budgets
and check the reported completeness of each result.

- [Overview and first study](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/README.md)
- [Scientific assumptions and research uses](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/SCIENTIFIC_SCOPE.md)
- [Integer layers and sampling: a worked two-loop example](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/END_TO_END_EXAMPLE.md)
- [Rate-dependent critical experiments](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/CRITICAL_EXPERIMENT.md)
- [Changes by version](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/CHANGELOG.md)
- [Report an issue](https://github.com/yeruciwenrou-dotcom/homological-observability/issues)

## Reproduce the reference calculations

```bash
.venv/bin/homological-observability reproduce --check --output-dir generated_results
```

This command compares fresh calculations with the packaged reference data
and writes a report and figure to `generated_results`. For pinned dependencies
and the reader-side test suite, follow the
[reproduction guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/README.md#full-verification-from-source).

## Theory and citation

The theoretical foundation is *Stochastic Histories at Finite Temporal
Resolution: Homological Observability and Information Phase Diagrams in
Markov Jump Processes*. Read the
[preprint on alphaXiv](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes)
or the [archived paper](https://doi.org/10.5281/zenodo.23424849).

Cite the paper for theoretical results and the software for computations.
Record the software version used and the Git commit for a source checkout.
Software citation metadata is available in
[CITATION.cff](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/CITATION.cff).

Authors: HongZheng Liu, YiNuo Tian, Zhiyue Wu, and Jianqun Cheng.

The software is distributed under the MIT License. The archived paper is
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
