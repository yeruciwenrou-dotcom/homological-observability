# Homological Observability

Research software for cyclic-history observability in known finite Markov
networks. Analyze which accumulated integer cycle directions remain hidden
by snapshots, and how sampling resolution and exact cumulative counters
change the information available.

Use the command line or Python API to:

- Analyze a network's exact integer cycle filtration, hidden directions,
  and asymptotic sampling requirements.
- Compare counter configurations under shared conditions, identify information
  gains and redundant channels, and export a rerunnable study.
- Construct a rate-dependent critical-limit experiment and reproduce the
  reference finite-cycle calculations.

## Installation

Use Python 3.11–3.13. This guide covers unreleased source version `1.2.0.dev0`.
In an activated virtual environment, obtain and install that source:

```bash
git clone --branch feature/configuration-comparison https://github.com/yeruciwenrou-dotcom/homological-observability.git
cd homological-observability
python -m pip install .
```

The [installation guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/README.md#install)
includes virtual environment setup and Windows commands. The published
[1.1.0 package](https://pypi.org/project/homological-observability/1.1.0/)
has its own [versioned guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v1.1.0/README.md).

## Analyze a network

```bash
homological-observability example wedge-c3-c5
```

The example joins a triangle and a five-cycle at one state. A weighted counter
removes the earliest hidden cycle direction while preserving a parity signal
at the next layer. The
[worked example](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/END_TO_END_EXAMPLE.md)
explains the resulting table. Models and reference data are included in the
installed package.

## Compare counter configurations

```bash
homological-observability study-example bridge --output bridge-study.json
homological-observability compare bridge-study.json --output-dir bridge-results
```

Open `bridge-results/comparison.md` to see what the candidate counters retain
and leave hidden. Information equivalence, strict refinement, and
incomparability distinguish choices that can share the same scalar summary.
The study bundle retains the input, exact integer evidence, per-candidate
completion states, and instructions for another run. Use a new output
directory for each study.

The [comparison guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/COMPARISON_GUIDE.md)
explains the example and takes you through preparing your own candidates.

## Python API

```python
import homological_observability as ho

model = ho.load_example("wedge-c3-c5")
result = ho.analyze_model(model)
print(ho.render_text(result))

study = ho.load_study_example("bridge")
comparison = ho.compare_configurations(study)
print(ho.render_comparison_text(comparison))
```

Use `ho.load_model("my-model.json")` for one model or
`ho.load_study("my-study.json")` for several configurations. The
[input guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/MODEL_GUIDE.md)
describes graph, counter, and resource settings; the
[output guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/OUTPUT_CONTRACT.md)
describes structured results and renderers.

## Reproduce the reference calculations

```bash
homological-observability reproduce --check --output-dir generated_results
```

This command compares fresh calculations with the packaged reference data
and writes a report and figure to `generated_results`. For pinned dependencies
and the reader-side test suite, follow the
[reproduction guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/README.md#full-verification-from-source).

## Scope and documentation

The graph must be finite, connected, undirected, and simple. The Markov
interpretation requires positive transition-rate support in both directions
on every edge; critical experiments also require the exact rate values.
Counters are exact cumulative integer measurements. Lattice operations and
finite catalogues are exact when the calculation completes. Sampling
requirements and phase labels describe long-time asymptotic limits; a
finite-run error tolerance requires additional risk analysis.

- [Overview and worked examples](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/README.md)
- [Scientific assumptions](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/docs/SCIENTIFIC_SCOPE.md)
- [Changes by version](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feature/configuration-comparison/CHANGELOG.md)
- [Report an issue](https://github.com/yeruciwenrou-dotcom/homological-observability/issues)

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
