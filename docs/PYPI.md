# Homological Observability

This project provides companion code and reproducible calculations for
research on homological observability in finite-state Markov jump processes.
The research asks which accumulated cycle histories can be recovered from
discrete observations of a known network.

Given a network and optional integer counters, the code computes hidden cycle
directions and their asymptotic sampling requirements. With transition rates,
it also constructs the critical-limit experiment.

You can reproduce the paper's calculations or apply the methods to your own
networks through the command line and Python API.

## Installation

Use Python 3.11–3.13. In an activated virtual environment, run:

```bash
python -m pip install homological-observability
homological-observability example wedge-c3-c5
```

The example joins a triangle and a five-cycle at one state and compares the
cycle information retained by a weighted counter. Models and reference data
are included in the installed package; no source checkout is needed.

## Python API

```python
import homological_observability as ho

model = ho.load_example("wedge-c3-c5")
result = ho.analyze_model(model)
print(ho.render_text(result))
```

Use `ho.load_model("triangle.json")` to read your own model and
`ho.analysis_to_dict(result)` to obtain a structured result. The
[model guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/main/docs/MODEL_GUIDE.md)
describes inputs and resource limits.

## Reproduce the reference calculations

```bash
homological-observability reproduce --check --output-dir generated_results
```

This command compares fresh calculations with the packaged reference data
and writes a report and figure to `generated_results`. For a source checkout
with pinned dependencies and the reader-side test suite, follow the
[reproduction guide](https://github.com/yeruciwenrou-dotcom/homological-observability#full-verification-from-source).

## Scope and documentation

The graph must be finite, connected, undirected, and simple. Critical
experiments require known positive transition rates in both directions on
each edge. Lattice operations and finite catalogues are exact when the
calculation completes; sampling requirements and phase labels describe
long-time asymptotic limits. They do not supply a finite-run error guarantee.

- [Overview and worked examples](https://github.com/yeruciwenrou-dotcom/homological-observability#readme)
- [Scientific assumptions](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/main/docs/SCIENTIFIC_SCOPE.md)
- [Results and exit codes](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/main/docs/OUTPUT_CONTRACT.md)
- [Changes by version](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/main/CHANGELOG.md)
- [Report an issue](https://github.com/yeruciwenrou-dotcom/homological-observability/issues)

## Companion paper and citation

The software accompanies *Stochastic Histories at Finite Temporal Resolution:
Homological Observability and Information Phase Diagrams in Markov Jump
Processes*.

> **Companion paper:** Read the [preprint on alphaXiv](https://www.alphaxiv.org/abs/2610.homological-observability-markov-jump-processes)
> or access the [archived PDF and paper DOI](https://doi.org/10.5281/zenodo.23424849).

Cite the paper for theoretical results and the software for computations,
including the software version. Version 1.1.1 updates documentation and paper
links; its scientific code and reference data are unchanged from 1.1.0.

The paper cites the archived software version 1.1.0:
[10.5281/zenodo.23329444](https://doi.org/10.5281/zenodo.23329444).
This software DOI identifies the frozen 1.1.0 archive. For computations with
1.1.1, cite version 1.1.1 and the
[repository](https://github.com/yeruciwenrou-dotcom/homological-observability).
[CITATION.cff](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/main/CITATION.cff)
provides software citation metadata and a separate reference to the paper.

Authors: HongZheng Liu, YiNuo Tian, Zhiyue Wu, and Jianqun Cheng.

The software is distributed under the MIT License. The archived paper is
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
