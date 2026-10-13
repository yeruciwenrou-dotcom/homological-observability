# Changelog

All user-visible software changes are recorded here. The project follows
semantic versioning for packaged interfaces; schema versions are tracked
separately inside their JSON documents.

## 1.1.0 — 2026-10-13

### Added

- Exact exposure, visible-image, and hidden integer filtrations for user-defined
  connected finite simple graphs.
- Smith/Hermite graded quotient invariants, including finite torsion factors.
- Versioned JSON Schemas for topology models and analyses, critical models and
  experiments, example catalogs, reproduction results, and controlled errors.
- Stable top-level Python API and deterministic JSON, text, and Markdown
  renderers.
- `examples`, `example`, `analyze`, `critical`, and `reproduce` CLI tasks with
  documented statuses and exit codes.
- Exact critical-layer path catalogues and theorem-derived marked-Poisson
  experiment specifications for known strictly positive directed edge rates.
- Exact decimal and rational parsing for critical rates and intensity, with
  atomic path, integer-digit, cycle, and output resource limits.
- Built-in wedge-of-C3-and-C5 demonstration with a staged exposure, index-two
  visible quotient, and hidden free direction.
- Rate-biased C4 end-to-end example with an exact nonreversible stationary law,
  conditional critical marks, and a generated machine-readable result.
- Wheel and sdist distributions with installed reference data.
- Python 3.11–3.13 support.

### Changed

- Analysis Schema version 2 separates completion of the requested horizon from
  certification that the natural filtration is complete.
- Analyses that complete a restricted horizon without exposing the full
  integral homology lattice now return `PARTIAL_HORIZON` rather than
  `COMPLETE`.
- `quickstart.py` now creates and manages its validation environment before
  running the reader-side tests and frozen-paper reproduction.
- Generated reports use `Visible` and `Hidden` consistently for the two
  readout sectors.
- Terminal tables align quotient values with their column headings.
- Critical resource controls distinguish an integer-digit preflight admission
  budget from exact digit and output-record ceilings.

### Compatibility

- The source-checkout commands `quickstart.py`, `reproduce_all.py`,
  `critical_kernel_checks.py`, `selected_appendix_checks.py`, and
  `explore_cycles.py` remain supported.

### Fixed

- Reproduction reports distinguish calculation checks from frozen-reference
  comparison, and failed or interrupted runs invalidate earlier success reports.
- Equivalent finite-ring endpoint and winding coordinates use the same bounded
  calculation. Oversized floating-point requests raise explicit range or budget
  errors before summation.
- Source builds require setuptools 77.0.3 or later, matching the SPDX license
  metadata used by the package.
- Software and companion paper metadata include the complete four-author list.
- The shared pinned verification dependencies include JSON Schema validation
  and its dependencies, so fresh quickstart environments and CI can run the
  reader-side tests. Existing quickstart environments refresh automatically.
- Path preflight stops at a certified resource refusal without constructing
  an oversized count. Uncomputed totals remain explicitly unavailable.
- Generated topology integers share one representation boundary across the
  Python API, JSON, text, and Markdown output.
- Maximum-value parentheses display correctly in the GitHub-rendered guides.
- Poisson-averaged MAP evaluation remains finite at large representable means.
- Small-window endpoint probabilities retain representable subnormal mass;
  unresolved positive probabilities raise explicit range errors. Rare bridges
  use stable series through a unit sampling window.
- Exact digit checks no longer format oversized integers before counting.
  Explicit decimal input/output bounds keep rejected requests and limited
  results reportable, including model hashes and command-line diagnostics.
- Direct public graph and readout construction validates integer coefficients,
  graph structure, and analysis settings before scientific computation.
- Phase regimes now follow the exact binary sampling input, including values
  adjacent to non-dyadic thresholds. Exposure and entropy calculations round
  after exact arithmetic and report unrepresentable results consistently.
- C3 and C4 count-TV diagnostics use outward-rounded probability recurrences,
  including arithmetic error and omitted tails in the returned intervals.
- Small-window cycle bridges cancel the rare-endpoint scale before division.
- Reproduction protects both committed and installed references, including
  symbolic and hard-link aliases with different output names.
- Critical digit limits include scientific integers, readout maps, marks and
  derived total intensities, with atomic rejection of oversized results.
- The diametric-chord C6 from Appendix F.4 has its own path-pair regression;
  the existing distance-two chord example remains separately identified.

### Scientific evidence

- The C3/C4 TV columns in the critical-kernel table are recalibrated against
  independent high-precision probabilities. The other reference values and
  existing comparison tolerances are retained. See [numerical methods](docs/NUMERICS.md).
- The exact integer kernel has been checked across all 996 connected graphs in
  the NetworkX graph atlas, including independent path-pair and integer-readout
  comparisons.

## 1.0.0

- Initial computational companion for the paper's exactly solvable finite-cycle
  examples, critical kernels, MAP identity, and reciprocal-lattice peak
  mechanism.
