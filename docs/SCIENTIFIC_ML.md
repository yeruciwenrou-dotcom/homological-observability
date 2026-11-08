# Scientific ML: paired DFR observations and prediction evaluation

This CPU case helps a researcher decide whether their recorded inputs determine
an integer trajectory target, choose an additional counter, and evaluate their
own point predictions on the same paths. It is part of the 2.1.0.dev0 development
branch. It uses the package's existing NumPy/SciPy dependencies.

## Run the complete case

From the repository, install the development source with `python -m pip install -e .`.
Then run:

```bash
python -m homological_observability.applications.dfr run --output-dir dfr-case
python -m homological_observability.applications.dfr evaluate dfr-case/predictions.json --output dfr-evaluation.json
```

Omitting `--dataset` loads the bundled, hashed 64-trajectory fixture.
`dfr-case/case.json` contains the four structural audits, minimum-channel design,
record-by-record exact reconstruction, and separate natural/pressure evaluations.
`report.txt` is the short report; `predictions.json` is an editable, task-bound
prediction file. Output paths must be new. Evaluation replay reproduces the
natural evaluation in `case.json`.

| Observation scheme | Visible features | DeltaW exactly determined? |
| --- | --- | --- |
| `snapshots` | 50 state snapshots, including both endpoints | No |
| `w` | Same snapshots and W | No; DeltaW has W's parity |
| `w-on` | Same snapshots, W and W_ON | Yes: DeltaW = 2 W_ON − W |
| `all` | Same snapshots, W, W_ON, W_OFF, S0, S1, S2 | Yes |

The existing W-only scheme needs **one additional channel**. Both W_ON and W_OFF
are minimum choices. In the fixed fixture, each sufficient scheme reconstructs
all 64 paths with zero mismatch. The natural test set has 13 paths; the
training-median baseline has MAE 6/13 and exact-match accuracy 7/13. These are
fixture measurements, with no neural-network training experiment attached.

The pressure set is a separate, constructed equal-weight pair. Its inputs agree
at **every** snapshot time and in W, while DeltaW is 0 and 2. A deterministic
point prediction from that shared input has MAE at least 1 and exact-match
accuracy at most 1/2. The training-median baseline reaches these bounds. The
pressure pair has no estimated natural sampling frequency.

## Supply your model's predictions

```python
import json
from pathlib import Path
import numpy as np
from homological_observability.applications import dfr

# The loader checks file hashes, model/rate identity, splits and every paired view.
data = dfr.load_dataset()
train = dfr.feature_view(data, "w", split="train")
test = dfr.feature_view(data, "w", split="test")
train_labels = {
    row["trajectory_id"]: row["DeltaW"]
    for row in data["files"]["natural-labels.json"]["rows"]
    if row["split"] == "train"
}
y_train = np.array([train_labels[i] for i in train["trajectory_ids"]])

# A runnable placeholder; replace with model.predict(test["X"]) after fitting
# the model and any preprocessing on the training split only.
y_pred = np.full(len(test["X"]), np.median(y_train))
request = dfr.make_predictions(
    data, y_pred, scheme="w", split="test", semantics="real_point"
)
Path("my-predictions.json").write_text(json.dumps(request), encoding="utf-8")
result = dfr.evaluate_predictions(data, request)
print(result["raw"], result["training_median_baseline"])
```

Use `dfr.feature_view(..., split="validation")` for model selection. Snapshot
values 0 through 5 are **categorical state IDs**, not spatial coordinates. Choose
an appropriate encoding for the learner; learn preprocessing parameters from
training data. Each row is one complete trajectory. All schemes share those
trajectory IDs and splits. `X` contains only the snapshot sequence and the
selected integer counter totals. IDs and column names are separate metadata.

The loader's returned `files` also contains truth for inspection and scoring.
Keep these files out of model features: complete event times/states, event count,
labels, and construction metadata. In particular, do not pass the whole dataset
object to a learner. Labels for validation/test are evaluation targets. IDs are
alignment keys, not predictive inputs. Compare algorithms with the same visible
scheme; compare observation designs with the same learning method and budget,
recording explicitly which information changed.

`make_predictions` accepts a one-dimensional array in `feature_view` row order.
It binds each prediction to a trajectory ID, protocol version, dataset hash,
task hash, target, cohort, split and scheme. The dataset hash covers the graph,
cochains, Q, grid, initial law, seeds, environment and member-file hashes.
The evaluator joins by ID, so file row order may change. It rejects missing,
duplicate or extra IDs, mismatched identities, unsupported versions, booleans,
NaN/infinity, unknown fields and malformed values before producing metrics.

| Prediction semantics | Evaluation |
| --- | --- |
| `integer_realized` | Values must be integral; MAE and exact numeric equality to the realized target |
| `real_point` | Finite real values; MAE and exact numeric equality, with no implicit rounding |
| `conditional_mean` | Finite real values; MAE, with raw exact-match score omitted |

A conditional mean can fall outside the realized-target lattice: labels 0 and 2
may have mean 1 (or labels 1 and 3 mean 2). `rounding="nearest_even"` explicitly
requests Python's nearest-integer, ties-to-even rule. Both original and rounded
values and metrics are retained; rounding does not replace the original output
or enforce the target's parity lattice. MAE evaluates the submitted point values;
it does not test whether a submitted conditional mean is calibrated.

Every evaluation includes label distribution, zero fraction, sample count,
a zero baseline and a median baseline fitted only on natural training labels.
For sufficient schemes it also includes exact reconstruction from visible
records and endpoints. No event log or target label enters that reconstruction.

The identical-input check compares predictions on repeated visible inputs. If
the two pressure predictions differ, the file does not demonstrate a deterministic
function of those inputs; `applicable_to_submitted_point_values` is false. This
can arise from hidden inputs or per-row randomness. It does not prove a leak,
and an unusually successful random realization does not refute an expected-risk
bound. This finite check cannot certify that an arbitrary learner is leakage-free.

## Generate another reproducible sample

```bash
python -m homological_observability.applications.dfr generate --output-dir my-dfr-data --trajectories 256 --seed 42 --split-seed 731
python -m homological_observability.applications.dfr run --dataset my-dfr-data --output-dir my-dfr-case
```

The Python generator additionally accepts `observation_time` and `grid_points`.
It writes a manifest and twelve separate JSON files: four visible schemes,
labels and event logs for each of the natural and pressure populations. The
manifest records the actual producer environment; the bundled fixture remains
byte-identical across installs. Re-generating under another numerical environment
can yield a different dataset identity. Use the saved data for exact replay.
The default whole-trajectory split is 60% training, 20% validation and 20% test,
with integer cut points. Generation uses separate PCG64 streams for paths and
split assignment and includes the initial state at time zero. Snapshots are
right-continuous; exact snapshot time equality takes the post-jump state.

## Known-Q model and source

The DFR support consists of ON states 0,1,2 and OFF states 3,4,5. At temperature,
V, b and r all equal to 1, its row-generator has, for distinct i,j in {0,1,2},

\[
Q_{ij}=e^{-(j-i)/2},\quad Q_{i+3,j+3}=1,\quad
Q_{i,i+3}=Q_{i+3,i}=1,\quad Q_{ii}=-\sum_{j\ne i}Q_{ij}.
\]

The model is independently implemented from the DFR generator in
[NeuralMJP commit 88893cd](https://github.com/pseifner/NeuralMJP/blob/88893cd76822cd4040699f1ccbf5879b7688ce5b/scripts/data_generation/generate_data.py)
and the DFR experiment in Appendix J of
[Seifner et al., Neural Markov Jump Processes, ICML 2023](https://proceedings.mlr.press/v202/seifner23a.html).
The paper describes 50 equidistant, noise-free observations over [0, 2.5] and a
stationary initial law. We include both endpoints. The repository's default
`configs/data/dfr.yaml` instead specifies T=1.25 and non-equidistant sampling;
our manifest records the chosen regular-grid paper setting explicitly.

We solve pi Q=0, sum(pi)=1 numerically and record the residual, rather than using
the upstream code's rounded initial probabilities. Direct exponential holding
times and rate-weighted jumps simulate the known-Q process. These exponential
rates are numerical inputs; they are not passed to the package's separate
exact-rational critical-rate interface. The source paper's full training run is
not reproduced by this small application fixture.

Finite positive rates on the fixed, connected bidirectional support make these
path events admissible. The exact cochain reconstruction is independent of the
numeric rates. The optional audit reports target-image exposure layers and
finite scales T delta^(m−1); finite scales do not provide recovery probabilities.
The [technical derivation](TARGET_THEORY.md) gives the assumptions for asymptotic
entropy coefficients. General finite-time posterior solvers, calibrated
probabilities and controlled neural-training comparisons belong to subsequent
research. Performance qualification and release packaging remain D4 and D5.
