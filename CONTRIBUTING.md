# Contributing

Use the [issue forms](https://github.com/yeruciwenrou-dotcom/homological-observability/issues/new/choose)
for incorrect results, installation problems, and documentation improvements.
Include the software version or source commit, a minimal input, the command
you ran, and the expected and observed results. For a proposed scientific
extension, describe the model and observation assumptions in the issue.

## Development environment

From a source checkout with Python 3.11–3.13, create a virtual environment
using the [installation guide](README.md#install-from-a-source-checkout), then
install the pinned scientific dependencies plus the development tools:

```bash
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
python -m pip install '.[test]'
```

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

Explain the mathematical or numerical reason for a change and add a regression
that distinguishes the corrected result from the error. Closed forms,
independent calculations, and structural invariants are useful comparisons.
Update the input/output guides when a public contract changes.

Keep new calculations in a separate output directory. The committed CSV files
and their packaged copies are the paper's numerical references; changes to
them need an independently justified correction and a matching changelog entry.
Regenerate built-in example reports with `python tools/freeze_examples.py` and
verify them with `python tools/freeze_examples.py --check`.

Submit focused pull requests with the user-visible effect and verification
results. Contributions use the repository's MIT License.
