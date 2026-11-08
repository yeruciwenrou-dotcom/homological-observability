# Homological Observability

**Research software for recovering cycle-history targets from finite observations.**
Given a transition graph and integer counter rules, check whether existing
records determine a target, choose additional counters, and reconstruct target
values from sufficient records. Compare observation schemes, study asymptotic
sampling thresholds, and reproduce the paper's finite-model calculations.

Homological observability concerns the recoverability of accumulated cycle
history. A direct A-to-B jump and a route through C can produce the same two
snapshots while differing by one circulation around a triangle. The software
computes the integer relations behind such ambiguities, including finite-index
information such as parity.

Its theoretical basis is:

> Liu, H., Tian, Y., Wu, Z., & Cheng, J. (2026).
> *[Stochastic Histories at Finite Temporal Resolution: Homological Observability
> and Information Phase Diagrams in Markov Jump Processes](https://doi.org/10.5281/zenodo.23424849).*

For finite-state Markov jump processes, the paper derives an information phase
diagram and sharp asymptotic sampling thresholds. The software applies these
results to supplied models and provides exact algebraic target checks.

## Version and installation

This source description accompanies **2.1.0.dev0**, an unreleased development
version. Target diagnosis, readout design and the scientific ML application
require this source. Use Python 3.11–3.13; installation needs internet access.

```bash
git clone --branch feat/target-observability https://github.com/yeruciwenrou-dotcom/homological-observability.git
cd homological-observability
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

On Windows, create the environment with `py -3.12 -m venv .venv` and use
`.venv\Scripts\python.exe` or `.venv\Scripts\homological-observability.exe`
in place of the corresponding `.venv/bin/` command.

The published release is **2.0.0**, installable with
`python -m pip install homological-observability==2.0.0` in a separate environment.
Its [versioned guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v2.0.0/README.md)
covers network analysis, counter comparison, critical experiments and paper
reproduction. These workflows remain available in the development version.

## Try target diagnosis and observation design

The discrete flashing ratchet example asks whether total circulation W determines
the difference DeltaW between ON and OFF circulation. Run the bundled CPU case:

```bash
.venv/bin/python -m homological_observability.applications.dfr run --output-dir dfr-case
```

Read `dfr-case/report.txt`:

- Snapshots and W leave DeltaW unresolved.
- Adding W_ON or W_OFF determines DeltaW; one added scalar channel is the
  minimum within the supplied candidate pool.
- The sufficient schemes evaluated in the case reconstruct all 64 bundled
  trajectories exactly.
- Natural-test prediction scores and the separate constructed ambiguity-pair
  scores have their own sample counts and baselines.

The [scientific ML tutorial](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/docs/SCIENTIFIC_ML.md) explains the model's
sources, paired observation schemes and prediction interface. Users can train
models separately and submit point predictions for evaluation. The supplied
predictor is a training-median baseline.

Use the [target guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/docs/TARGET_TASKS.md) to define your own graph,
fixed counters, targets and candidate channels. Saved requests, results and
reports support inspection and replay.

## Compare counters or reproduce the paper

Compare counter choices on two connected rings:

```bash
.venv/bin/homological-observability study-example bridge --output bridge-study.json
.venv/bin/homological-observability compare bridge-study.json --output-dir bridge-results
```

Read `bridge-results/comparison.md` for hidden directions, exact information
relations and redundant counters. The [comparison guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/docs/COMPARISON_GUIDE.md)
explains how to edit the study for your network.

Reproduce the finite-model paper calculations:

```bash
.venv/bin/homological-observability reproduce --check --output-dir generated_results
```

This writes a scientific report, figure and CSV tables, then checks the tables
against the packaged frozen references. Use a new output directory for each run.
The [reproduction guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/README.md#reproduce-the-paper-evidence) describes
the checks, numerical tolerances and archived source releases.

## Inputs and interpretation

The graph is finite, connected and simple, with positive transition support in
both directions. Observations are regular noiseless state snapshots and exact
integer counters. Structural and target analyses use the support and cochains;
critical-limit experiments additionally use exact positive rates. The DFR
application simulates its documented known-rate model.

Exact target decoding checks integer-image legality and endpoint corrections.
A target's asymptotic entropy coefficient describes a long-time sampling law;
finite exposure scales describe the strength of each layer, without assigning
a finite-run recovery probability. Reports distinguish completed conclusions
from unfinished calculations. See the [scientific scope](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/docs/SCIENTIFIC_SCOPE.md).

## Documentation and citation

- [Main guide and Python API](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/README.md)
- [Model inputs](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/docs/MODEL_GUIDE.md) and [output contracts](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/docs/OUTPUT_CONTRACT.md)
- [Theory and implementation map](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/PAPER_MAP.md)
- [Changes](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/CHANGELOG.md) and [contributing](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/CONTRIBUTING.md)

Cite the paper for theoretical results and the software for computations.
The published 2.0.0 software archive is
[doi:10.5281/zenodo.23618828](https://doi.org/10.5281/zenodo.23618828).
For development results, also record `2.1.0.dev0` and the exact Git commit.
The [citation guide](https://github.com/yeruciwenrou-dotcom/homological-observability/blob/feat/target-observability/README.md#citation-and-license) provides full details.

Authors: HongZheng Liu, YiNuo Tian, Zhiyue Wu, and Jianqun Cheng.
The software uses the MIT License; the archived paper uses CC BY 4.0.
