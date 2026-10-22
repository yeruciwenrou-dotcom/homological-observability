# Contributing

Corrections, reproducible examples, and documentation improvements are welcome.
Use the [issue forms](https://github.com/yeruciwenrou-dotcom/homological-observability/issues/new/choose)
to report a problem, including the version or commit, a minimal input, and
the expected and observed results. For a research question or proposed
extension, open a regular issue describing the model and observation assumptions.

## Development environment

From a source checkout with Python 3.11–3.13, create a virtual environment
and install the pinned dependencies and development tools. On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -c requirements.txt -e '.[test]'
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -c requirements.txt -e '.[test]'
```

This editable installation uses your working source files. In the checks
below, Windows users can replace `python` with `.venv\Scripts\python.exe`
and `ruff` with `.venv\Scripts\ruff.exe`; activation is optional.

Run the checks relevant to the change:

```bash
python -W error -m unittest discover -s tests -v
python -W error reproduce_all.py
python tests/validate_schema.py
python tests/validate_graph_atlas.py
python tests/validate_distribution.py
ruff check .
ruff format --check .
```

The distribution check builds a wheel and source archive, then installs and
exercises each in a separate environment outside the checkout. It needs
internet access for build tools and dependencies. CI runs these checks on
each pull request.

## Scientific changes

For a calculation fix, explain the mathematical or numerical reason and add
a regression that distinguishes the corrected result from the error. Closed forms,
independent calculations, and structural invariants are useful comparisons.
Update the input/output guides when a public contract changes.

Keep new calculations in a separate output directory. The committed CSV files
and their packaged copies are the paper's numerical references; changes to
them need an independently justified correction and a matching changelog entry.

Check the existing example reports with:

```bash
python tools/freeze_examples.py --check
```

This compares their scientific fields with the current implementation while
preserving each reference's producing version. Regenerating the archived
examples requires the corresponding 1.1.0 environment. For a new model or
comparison study, save fresh results in a new directory and include the input,
software version, and checks that establish the expected result.

Submit focused pull requests with the user-visible effect and verification
results. Contributions use the repository's MIT License.
