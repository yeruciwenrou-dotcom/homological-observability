# Target-task assessment

Target diagnosis helps decide whether existing records answer a research question.
Readout design finds minimum additions within a declared candidate pool and
returns exact reconstruction certificates. This assessment checks those tasks
against independent calculations, simple alternatives and paired DFR records.
It accompanies the [task guide](TARGET_TASKS.md),
[technical derivation](TARGET_THEORY.md) ([PDF](TARGET_THEORY.pdf)) and
[Scientific ML application](SCIENTIFIC_ML.md).

## Repeat the assessment

After the [development installation](../CONTRIBUTING.md#development-environment),
run from the checkout:

```bash
.venv/bin/python tools/assess_target_tasks.py --output-dir target-assessment
```

Use a new output directory. The script saves correctness, baseline and record
results separately, then an `assessment.json` containing all results, environment,
source SHA-256 and stage timings. The committed
[measurement record](../results/target_task_assessment.json) identifies the
source that produced this summary. The source digest covers Python files in
`src/`, `tools/` and `tests/`, in the script's documented traversal order.

## Correctness and simple alternatives

An independent `Fraction` elimination works directly on edge cochains modulo
gradients, without calling the product's cycle-basis or Smith routines. It
exhausts every candidate subset for 29 cases: two DFR tasks, the bridge, theta
and minimal example graphs, and 24 seeded integer-cochain cases. Two tree
orders agree on feasibility, minimum cardinality and every tied solution.
Edge-chain ambiguity witnesses and all returned decoders are checked against
the original cochains. Existing regression tests additionally exercise integer
image legality, saturated kernels, endpoints, distinct instrument IDs and limits.

The baseline comparison uses the same task and candidate pools. Deletion and
target-deficit greedy selection each run in forward, reverse and seeded orders.

| Task | Exact minimum additions | Minimum choices | Observed ordered baselines |
| --- | ---: | ---: | --- |
| DFR, W already recorded | 1 | 2 | All six runs also find one addition |
| DFR, no fixed counters | 2 | 3 | Deletion finds two; greedy finds two or five |
| DFR, W fixed and a direct target counter available | 1 | 3 | All runs find one addition, including direct recording |
| Constructed deletion-order example | 1 | 1 | Reverse deletion retains two; other deletion orders find one |

The constructed example illustrates order dependence; it is not a physical
DFR measurement. These results support exact minimum proofs and complete tied
choices. Simple methods also solve several cases optimally. A short exact
rank/enumeration script is a valid alternative for a fixed small problem.
The product adds validated inputs, legal-record evaluation, certificates,
completion states and replay to that calculation.

The existing `compare` workflow independently identifies that adding DeltaW to
W strictly refines the full-history information. Native `analyze_target` answers
the focused sufficiency question directly. Their output responsibilities differ,
as do those of a rank-only script and certificate-producing design; their recorded
times are not an equal-work speed comparison.

## Paired records and reconstruction

The same 64 bundled natural trajectories, snapshots and split IDs are used for
each scheme. Both sufficient schemes reconstruct all 64 targets without error.

| Scheme | Counters per trajectory | Signed int64 counter bytes | Compact JSON bytes, including snapshots and IDs |
| --- | ---: | ---: | ---: |
| W | 1 | 512 | 18,885 |
| W + W_ON | 2 | 1,024 | 19,466 |
| All candidates | 6 | 3,072 | 21,492 |

Using two instead of six counters reduces the counter payload by 66.7%, or the
whole JSON record by about 9.4% under this encoding. Snapshot storage remains.
The same-count alternative W + S0 is insufficient; its pressure-pair inputs
agree while the targets are 0 and 2. Channel choice matters as well as count.

A direct DeltaW accumulator, the two-counter scheme and the six-counter scheme
are timed on the same event trajectories. If all events are available and only
DeltaW is needed, direct accumulation is a natural choice. The design task is
useful when channels are restricted, records already exist, or measurements
must serve several questions. Counter counts do not specify hardware cost.

The [prediction tutorial](SCIENTIFIC_ML.md) reports natural-data and constructed
pressure results separately and accepts predictions from a user's model.
This assessment measures exact reconstruction and recording overhead; it does
not measure neural-network training improvements.

## Scale and budgets

Measurements use Linux x86-64, Python 3.12.14, SymPy 1.14.0 and NetworkX 3.6.1.
Each scale point runs in a fresh process on a shared host. The constructed
triangle families vary cycle rank beta, candidate count m, target count q and
integer size. They are reproducible resource probes, separate from the DFR case.

| beta / m / q | Subsets examined | Wall time, seconds | Result |
| --- | ---: | ---: | --- |
| 2 / 4 / 1 | 4 | 0.02 | Complete; minimum 1, 2 ties |
| 4 / 8 / 2 | 36 | 0.04 | Complete; minimum 2, 4 ties |
| 8 / 12 / 2 | 78 | 0.08 | Complete; minimum 2, 4 ties |
| 8 / 12 / 4 | 793 | 0.89 | Complete; minimum 4, 16 ties |
| 16 / 16 / 4 | 2,516 | 5.93 | Complete; minimum 4, 1 tie |
| 16 / 16 / 4, two-second budget | 967 | 2.00 | Search limited; partial result retained |

Peak process RSS is about 123–124 MiB in these probes, including Python and
imports. It is not incremental algorithm memory. The raw record separates
coordinate preparation, rank decisions, certificates, optional explanation and
JSON encoding. Deterministic replay agrees for non-time-limited results.

Additional probes verify subset and output caps, a matrix-size rejection before
search, 1,024-bit coefficients, and an explanation limit that preserves a complete
core result. A discovered minimum, all ties, returned certificates and optional
explanation have separate completion fields; a limit does not erase established
facts or imply that all requested work finished.

The current defaults remain 10,000 subsets, 100 returned solutions, 100,000
matrix entries, 4,096-bit integers, 30 cooperative seconds and 10,000 explanation
cycles. The measured small pools are suitable starting examples. General subset
search is combinatorial; candidate count alone cannot predict completion. Review
partial-result fields before raising a budget. `max_seconds` is checked between
exact operations, so one atomic operation can overrun it. Applications needing
a hard deadline should run the task in a separate process with an external timeout.
