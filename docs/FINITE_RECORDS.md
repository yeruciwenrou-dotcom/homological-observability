# Inferring a target from a finite record

Given [your own record](#use-your-own-model) of state snapshots and optional
counters, `posterior` finds which values of a trajectory target are possible.
With known transition rates, it can also estimate their probabilities.

The examples use a flashing ratchet. The target `DeltaW` is the difference
between the signed turns made while the potential is ON and OFF.

| Research question | Example result |
| --- | --- |
| [What does one record tell me?](#use-your-own-model) | With 50 snapshots and total turns, only even values fit. At the supplied rates, zero has probability 99.63%. |
| [Would an extra counter help?](#compare-recording-protocols) | With eight snapshots per path, total turns plus ON turns determine `DeltaW` on all 64 trajectories. |

After [installation](../README.md#install), run either example in the activated
environment. Choose a new output directory for each run.

```sh
homological-observability posterior --example dfr --output-dir dfr-record
```

Open `dfr-record/report.txt` for the probabilities from the single record.

```sh
homological-observability compare-protocols --example dfr --output-dir dfr-protocols
```

Open `dfr-protocols/report.txt` for the comparison across the 64 paths.

Each directory includes `result.json` for further analysis and an editable
`request.json`. To replay the result, pass the saved request to the same command.
The Python functions `infer_target_posterior(request)` and
`compare_recording_protocols(request)` accept the same dictionaries as the CLI.

## Use your own model

Start with the three-state ring included in the [installed package](../README.md#install).
Save its editable input and report in a new directory named `ring`.

```sh
homological-observability posterior --example triangle --output-dir ring
```

Open `ring/report.txt` to see the example result. In `ring/request.json`,
replace the state labels and support edges with those of your model.
The graph follows the existing [model format](MODEL_GUIDE.md). Its `readouts`
are observed counters. The `target` field is a single integer edge cochain in
the same format. A coefficient on `["c","a"]` counts forward crossings
positively and reverse crossings negatively. Use `target_unit` for the
physical unit. To estimate probabilities from known rates, supply one positive
finite rate in each direction of every support edge, labeled by its `from`
and `to` states in inverse units of `time_unit`. The diagonal follows from
zero row sums. Omit `rates` to check which target values fit the record.

Give `record.times` and `record.states` on a regular grid and supply one
whole-record signed integer per channel in `record.counts`. The model assumes
a time-homogeneous finite-state jump process, fully observed noiseless snapshot
states and exact net counters. The posterior conditions on the first state. A
single snapshot spans zero time, so all counters and the target must be zero
on that empty path. After editing the request, run it again:

```sh
homological-observability posterior ring/request.json
```

If your instrument records integer ticks, keep them as JSON integers, including
for absolute timestamps in nanoseconds. The solver takes exact differences
before converting the interval to floating point. All snapshots must fit one
start time and one sampling interval. Integer timestamps fix their coordinates
exactly. A floating timestamp allows half the spacing to its neighbor on each
side, or $5\times10^{-11}$ of the mean interval if larger, to accommodate
rounding when constructing a grid. If successive times round to the same
value, use the original ticks or compute relative times before conversion.

In the bundled ring, `turn` counts net crossings from c to a. Both endpoint
snapshots show a. Each directed rate is one per second and the elapsed time is
one second. The most probable result is zero with probability 0.8417122018.
The optimal conditional error probability under 0–1 loss is 0.1582877982.
In this example the full reference law is proportional to
$I_{3|z|}(2)$ for integer $z$.

Starting from the bundled ring, try two changes to the same input.

1. Add a readout named `double` with coefficient 2 on `["c","a"]`, and set
   `record.counts` to `{"double": 6}`. The target is exactly 3. Rates are
   optional for this determination.
2. Change the observed count to 5. The result gives `IMPOSSIBLE_RECORD` and
   the failed divisibility test on the endpoint-corrected count.

An optional `target_sets` array accepts named inclusive integer intervals.
For example, `[{"name":"nonpositive","max":0}]` gives the probability of a
nonpositive target. Omit one bound for a one-sided interval.

### Python example

The same calculation on your own state labels can be run directly in Python.

```python
from homological_observability import infer_target_posterior

edges = [["free", "bound"], ["bound", "primed"], ["primed", "free"]]
result = infer_target_posterior(
    {
        "schema_version": 1,
        "time_unit": "s",
        "target_unit": "turn",
        "model": {
            "schema_version": 2,
            "name": "Three-state cycle",
            "vertices": ["free", "bound", "primed"],
            "edges": edges,
        },
        "target": {
            "name": "net turns",
            "coefficients": [{"edge": ["primed", "free"], "coefficient": 1}],
        },
        "rates": [
            {"from": u, "to": v, "rate": 1.0}
            for a, b in edges
            for u, v in ((a, b), (b, a))
        ],
        "record": {"times": [0, 1], "states": ["free", "free"], "counts": {}},
    }
)
assert result["result"]["map_candidates"] == [0]
```

## Interpreting a posterior

Read the `result` object in `result.json` in this order.

- **Compatibility.** `legal_record` says whether the integer path counts are
  compatible with the record. `target_support` gives the possible target
  values as an offset plus any integer multiple of a step. Step zero fixes
  the target exactly.
- **Probabilities.** `pmf` gives the estimated distribution on the retained
  domain. `map_candidates` lists possible maximizers at the achieved
  precision. `map_risk` is one minus the largest probability. An exact
  answer has probability one and zero risk.
- **Coordinates.** `endpoint_offset` lists contributions from the known endpoints,
  first for the target, then for the counters in model order. `corrected_counts`
  gives the observed counter totals after subtracting those offsets. `coordinates`
  records the tree, chords and integer image basis for converting back to the
  declared observables.
- **Numerical diagnostics.** `diagnostics` records grid sizes, the estimated
  conditional wrap tail, pre-clipping negative mass, imaginary residual,
  normalization correction, row-sum drift and the precision indicator. Its
  `log_record_probability` field gives the log probability of the subsequent
  snapshots and cumulative counts conditional on the first state. The
  probability of the counts given the snapshots is recorded separately.

The numerical calculation supports effective joint integer image rank one or
two. Redundant and scaled counters retain their integer-image constraints.
An exactly determined target can be decoded at higher rank. A result
with `RATES_REQUIRED` or `UNSUPPORTED_RANK` includes its exact support. A
legal record with insufficient numerical precision has status
`NUMERICALLY_UNRESOLVED`. A grid or exact-algebra budget reports
`LIMIT_REACHED`. The CLI exits with 0 for a completed scientific decision,
including an incompatible measurement, 1 for incomplete inference, and 2 for
invalid input. JSON output is available with `--format json`.

### Numerical precision

Each regular window uses matrix exponentials of the row generator tilted by
the integer chord increments. Its endpoint characteristic function is
normalized by the corresponding transition probability. Window factors are
multiplied before Fourier inversion and conditioning on the observed total.
Positive and negative real tilts estimate a Chernoff tail for each coordinate.
The union of these tails controls wrapping in exact arithmetic. The
floating-point calculation also checks mass loss, negative mass, imaginary
parts and amplification by rare endpoints and rare observed counts. The
reported error indicator combines truncation and measured or estimated
roundoff. It is a numerical diagnostic. Independent closed forms and positive
uniformization recursions provide small-model reference calculations.

The default tolerance is `1e-6`, with at most 65,536 grid points and 4,000,000
complex kernel entries. Set `limits.tolerance`, `limits.max_grid_points` and
`limits.max_matrix_entries` in the request to change these settings. Very
stiff windows above one million maximum-exit-rate time units return an
unresolved numerical status. The shared exact target calculations retain
their own matrix, integer-size and cooperative time budgets.

## Compare recording protocols

The paired DFR example uses the same 64 complete, independently identified
paths in every row of the comparison. Each path spans 2.5 model time units.
For 8 snapshots the fixed-sample means are as follows.

| Available observations | Mean conditional 0–1 risk | Difference from snapshots | Mean encoded bytes per path |
| --- | ---: | ---: | ---: |
| Snapshots | 39.9526% | 0 | 56.0 |
| Snapshots and total turns W | 15.4173% | −24.535 percentage points | 61.2 |
| Snapshots, W and ON turns | 0% | −39.953 percentage points | 70.3 |

On these paths, adding W reduces mean risk by 24.535 percentage points
at the same sampling frequency. The byte counts measure the package's compact
encoding of states and counts. The physical cost of a new measurement depends
on the instrument.

To adapt the study, edit its graph, target, horizon and protocols. Each
protocol specifies a name, a snapshot count including both endpoints, and
a list of channel names taken from the model readouts. The first protocol is
the baseline. To compare nested grids with $n$ and $m$ snapshot points,
choose $m-1$ divisible by $n-1$. Both protocols read the same state at every
shared time. If a jump occurs at that time, both read the new state.
Additional information reduces risk in expectation. A particular realized
record can have higher conditional risk.

Use `source.kind = "events"` to import complete trajectories. Give the source
a name and supply an array of `trajectory_id`, `times` and `states` records.
The time-zero entry names the initial state. Later times increase strictly
and lie below the horizon. For single-record inference, supply the observed
snapshots and net counters. Reprojecting to a new schedule requires the full
event history.

Use `source.kind = "simulate"` with rates, an explicitly labeled
`initial_distribution`, the number of trajectories and a nonnegative seed.
To see a complete editable simulation request, run
`homological-observability compare-protocols --example triangle --output-dir plans`.
The seeded generator is NumPy PCG64. The same simulated paths supply every
candidate. The report gives a 95% Hoeffding interval for the expected paired
risk difference across independent paths, with per-comparison sampling coverage conditional on the numerical risk estimates.
Fixed imported sets report descriptive paired differences. Numerical
precision is accounted for through the diagnostics of each resolved record.

Every path retains its ID and remains in the denominator. Unresolved risks
occupy the full 0–1 range in the sample bounds. To compare protocols against
a 20% mean risk limit, add `"risk_threshold": 0.2` to the request. In the
text report, `MET` means the upper sample bound is at or below the limit,
`EXCEEDED` means the lower bound is above it, and `UNRESOLVED` means the
bounds leave both possibilities open.

Resource columns count snapshots, declared
scalar counters and bytes for the compact UTF-8 JSON representation of the
visible state sequence and counts. Assess instrument costs separately for your setup.

The producer record identifies the installed code and numerical environment.
The request and result schemas are available through
`load_posterior_request_schema()`, `load_posterior_schema()`,
`load_protocol_request_schema()` and `load_protocol_comparison_schema()`.

## A mechanical and chemical target

Which measurements of a kinesin motor determine its net ATP hydrolysis?
In the [six-state model of Liepelt and Lipowsky](https://doi.org/10.1103/PhysRevLett.98.258102),
$M$ counts mechanical steps along $2\to5$, while $A$ and $B$ count transitions
along $6\to1$ and $3\to4$. All three are signed net counts. The target
$F=A+B$ is the net number of ATP molecules hydrolyzed.

```sh
homological-observability posterior --example kinesin --output-dir motor
```

The example record starts in state 1, ends in state 4 and has $M=A=0$.
It determines $F=1$ exactly. To see why, assign $h=0$ to states 1, 2 and 3
and $h=1$ to states 4, 5 and 6. The counts obey $F=2A-M+\Delta h$,
and the observed endpoints give $\Delta h=1$.

Remove channel `A` and its count from `motor/request.json`, then rerun
`homological-observability posterior motor/request.json`. With the mechanical
count and endpoints alone, every odd value of $F$ is possible. The report
gives this exact support with status `RATES_REQUIRED` because assigning
probabilities to the odd values requires transition rates. To use a measured
trace, match its snapshot labels and counters to these chemical states and
transitions.
