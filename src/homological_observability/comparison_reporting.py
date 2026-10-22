"""Reading surfaces and portable bundles for one computed comparison."""

from __future__ import annotations

import hashlib
import json
import string
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any


def load_study_example(name: str) -> dict[str, Any]:
    """Load an editable comparison study: bridge, theta, or minimal."""
    if name not in ("bridge", "theta", "minimal"):
        raise ValueError("unknown study example; choose bridge, theta, or minimal")
    from .comparison import parse_study

    resource = resources.files("homological_observability").joinpath(
        "data", "studies", name + ".json"
    )
    return parse_study(json.loads(resource.read_text(encoding="utf-8")))


def _json(document: Any) -> str:
    return (
        json.dumps(
            document, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
        )
        + "\n"
    )


def _plain(value: Any) -> str:
    # User labels remain text in terminal/Markdown, even when they contain newlines.
    return "".join(char for char in " ".join(str(value).split()) if char.isprintable())


def _markdown(value: Any) -> str:
    return "".join(
        "\\" + char if char in string.punctuation else char for char in _plain(value)
    )


def _cell(value: Any) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        # repr retains tiny positive values at the exact binary-alpha boundary.
        return repr(value)
    return _plain(value)


def _first_hidden(row: Mapping[str, Any]) -> str:
    value = row.get("first_hidden_layer")
    if value is not None:
        return str(value)
    if row.get("scope") == "FULL_HOMOLOGY":
        return "none"
    if row.get("scope") == "COMPUTED_EXPOSURE":
        return "none in computed layers"
    return "unavailable"


def _name(row: Mapping[str, Any]) -> str:
    label, identifier = _plain(row["label"]), row["id"]
    return label if label == identifier else f"{label} [{identifier}]"


def _scope(record: Mapping[str, Any]) -> str:
    if record["scope"] == "FULL_HOMOLOGY":
        return "the full integer cycle group"
    if record["scope"] == "COMPUTED_EXPOSURE":
        return f"computed exposure through layer {record['computed_max_layer']} only"
    return "unavailable"


def _summary(document: Mapping[str, Any]) -> list[str]:
    """Select facts from reported metrics without interpreting the free-text question."""
    rows = document["rows"]
    complete = sum(row["status"] == "COMPLETE" for row in rows)
    notes = []
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in rows:
        if row["scope"] != "UNAVAILABLE":
            key = (row["scope"], row["computed_max_layer"], row["channels"])
            groups.setdefault(key, []).append(row)
    for group in groups.values():
        scope = _scope(group[0])
        resolved = [row for row in group if row["computed_hidden_rank"] == 0]
        channel_count = group[0]["channels"]
        prefix = (
            f"Among the evaluated {channel_count}-channel configurations on {scope}"
        )
        if resolved:
            notes.append(
                prefix
                + ", no hidden integer direction remains for: "
                + "; ".join(_name(row) for row in resolved)
                + "."
            )
        if len(group) > 1 and not resolved:
            first = max(row["first_hidden_layer"] for row in group)
            tied = [row for row in group if row["first_hidden_layer"] == first]
            notes.append(
                prefix
                + f", the latest reported first hidden layer is {first}: "
                + "; ".join(_name(row) for row in tied)
                + "."
            )
    lookup = {row["id"]: row for row in rows}
    for kind in ("EQUIVALENT", "INCOMPARABLE"):
        matches = [pair for pair in document["relations"] if pair["relation"] == kind]
        if not matches:
            continue
        # Prefer the pair that makes a scalar tie's interpretation explicit.
        pair = next(
            (
                p
                for p in matches
                if p["metric_comparison"]["first_hidden_layer"] == "TIED"
            ),
            matches[0],
        )
        left, right = _name(lookup[pair["left"]]), _name(lookup[pair["right"]])
        if kind == "EQUIVALENT":
            notes.append(
                f"{left} and {right} carry the same information on {_scope(pair)}."
            )
        else:
            tie = pair["metric_comparison"]["first_hidden_layer"] == "TIED"
            notes.append(
                f"{left} and {right} carry incomparable information on {_scope(pair)}. "
                + ("Their first-hidden-layer values are tied. " if tie else "")
                + "Each distinguishes a history difference that the other leaves hidden."
            )
    if any(row["scope"] == "COMPUTED_EXPOSURE" for row in rows):
        notes.append("Computed-exposure conclusions leave uncomputed layers open.")
    unavailable = [row for row in rows if row["scope"] == "UNAVAILABLE"]
    if unavailable:
        notes.append(
            "No information conclusion is available for: "
            + "; ".join(_name(row) for row in unavailable)
            + ". See the status and recovery notes."
        )
    notes.append(f"{complete} of {len(rows)} configurations are naturally complete.")
    return notes


def _conditions(document: Mapping[str, Any]) -> list[str]:
    study = document["study"]
    model, analysis = study["model"], study["analysis"]
    notes = [
        f"Network: {_plain(model['name'])}; {len(model['vertices'])} vertices, "
        f"{len(model['edges'])} edges. All configurations use this graph, the same "
        "snapshots and exact cumulative integer counters."
    ]
    if analysis.get("alpha") is not None:
        notes.append(
            f"Sampling law: delta = T^(-{analysis['alpha']}) in reference-rate units."
        )
    elif analysis.get("observation_time") is not None:
        notes.append(
            f"Observation time: {analysis['observation_time']}; sampling interval: "
            f"{analysis['sampling_interval']} (reference-rate units)."
        )
    else:
        notes.append(
            "No sampling parameters supplied; entropy coefficients are unavailable."
        )
    horizon = analysis.get("max_layer")
    budget = analysis.get("max_cycles")
    notes.append(
        "Requested horizon: "
        + (f"through layer {horizon}" if horizon is not None else "natural horizon")
        + "; cycle enumeration budget: "
        + (str(budget) if budget is not None else "unbounded")
        + ". Coordinates: "
        + document["shared_conditions"]["coordinates"]
        + "."
    )
    return notes


def _counter_definitions(document: Mapping[str, Any], identifier: str) -> str:
    result = document["results"].get(identifier)
    if result is None:
        return "Input could not be validated; see the recovery note and saved model."
    readouts = result["model"]["readouts"]
    if not readouts:
        return "Snapshots only; no additional counter."
    definitions = []
    for readout in readouts[:8]:
        coefficients = readout["coefficients"]
        terms = [
            f"{item['coefficient']} C({_plain(item['edge'][0])} → {_plain(item['edge'][1])})"
            for item in coefficients[:8]
        ]
        expression = " + ".join(terms) if terms else "0"
        if len(coefficients) > 8:
            expression += f" + … ({len(coefficients) - 8} further terms in the model)"
        definitions.append(f"{_plain(readout['name'])} = {expression}")
    if len(readouts) > 8:
        definitions.append(f"{len(readouts) - 8} further counters in the model")
    return "; ".join(definitions)


def _row_notes(row: Mapping[str, Any]) -> list[str]:
    notes = []
    if row["scope"] != "UNAVAILABLE":
        notes.append(f"Results cover {_scope(row)}.")
        if row["redundant_channels"]:
            notes.append(
                "Any one of these channels can be removed while preserving this information: "
                + ", ".join(_plain(name) for name in row["redundant_channels"])
                + ". Remove one at a time; simultaneous removal needs a new comparison."
            )
        if row["visible_torsion"]:
            notes.append(
                "Finite visible quotient factors: "
                + "; ".join(
                    f"layer {layer}: {factors}"
                    for layer, factors in row["visible_torsion"].items()
                )
                + "."
            )
    elif row["status"] == "LIMIT_REACHED":
        notes.append(
            "The cycle enumeration budget was exhausted; metrics are unavailable."
        )
    if row.get("error"):
        notes.append("Error: " + _plain(row["error"]))
    if row.get("recovery"):
        notes.append(_plain(row["recovery"]))
    return notes


_RELATION_LABELS = {
    "EQUIVALENT": "Same information",
    "LEFT_REFINES_RIGHT": "First contains more information",
    "RIGHT_REFINES_LEFT": "Second contains more information",
    "INCOMPARABLE": "Incomparable information",
    "UNAVAILABLE": "Unavailable",
}


def _representative_pairs(document: Mapping[str, Any]) -> list[tuple[int, Any]]:
    indexed = list(enumerate(document["relations"]))
    selected = []
    for kinds in (
        ("INCOMPARABLE",),
        ("EQUIVALENT",),
        ("LEFT_REFINES_RIGHT", "RIGHT_REFINES_LEFT"),
    ):
        matches = [
            (index, pair) for index, pair in indexed if pair["relation"] in kinds
        ]
        if matches:
            selected.append(
                next(
                    (
                        (index, pair)
                        for index, pair in matches
                        if pair["metric_comparison"]["first_hidden_layer"] == "TIED"
                    ),
                    matches[0],
                )
            )
    return selected


def _evidence(document: Mapping[str, Any], *, markdown: bool) -> list[str]:
    rows = {row["id"]: row for row in document["rows"]}
    escape = _markdown if markdown else _plain
    lines = []
    for index, pair in _representative_pairs(document):
        left, right = _name(rows[pair["left"]]), _name(rows[pair["right"]])
        title = f"{left} / {right}"
        lines += [("### " if markdown else "  ") + escape(title), ""]
        lines += [
            escape(_RELATION_LABELS[pair["relation"]] + f" on {_scope(pair)}."),
            "",
        ]
        if pair["relation"] == "EQUIVALENT":
            lines += [
                "Both exact kernel inclusions hold; the two configurations distinguish "
                "the same histories on this scope. Their counter values can differ.",
                "",
                f"Certificates in comparison.json: `relations[{index}].left_kernel_in_right` "
                f"and `relations[{index}].right_kernel_in_left`.",
                "",
            ]
        for key, hidden, detected in (
            ("left_not_right_witness", left, right),
            ("right_not_left_witness", right, left),
        ):
            witness = pair[key]
            if witness is None:
                continue
            lines += [
                escape(
                    f"A history difference hidden from {hidden} and detected by {detected}:"
                ),
                "",
            ]
            if markdown:
                lines += ["| Oriented edge | Integer coefficient |", "|---|---:|"]
            for term in witness["edge_chain"][:12]:
                edge = f"{_plain(term['edge'][0])} → {_plain(term['edge'][1])}"
                lines.append(
                    f"| {escape(edge)} | {term['coefficient']} |"
                    if markdown
                    else f"    {edge}: {term['coefficient']}"
                )
            if len(witness["edge_chain"]) > 12:
                lines += [
                    "",
                    f"Showing 12 of {len(witness['edge_chain'])} nonzero edge coefficients; the full witness is in the JSON record.",
                ]
            lines += [
                "",
                escape(
                    f"Readout changes: {left}: {witness['left_readout']}; "
                    f"{right}: {witness['right_readout']}."
                ),
                "",
                f"Exact witness in comparison.json: `relations[{index}].{key}`.",
                "",
            ]
    if not lines:
        lines = [
            "No comparable pair has an exact witness to display. Consult the configuration statuses above.",
            "",
        ]
    lines += [
        "These are representative relations. The complete comparison.json retains every "
        "relation, both readout vectors, all containment certificates and hidden-direction bases.",
        "",
    ]
    return lines


def render_comparison_text(document: Mapping[str, Any]) -> str:
    """Render the same computed metrics and certificates as the Markdown report."""
    study = document["study"]
    lines = [f"{_plain(study['name'])} — {document['status']}"]
    if study.get("question"):
        lines += [_plain(study["question"])]
    lines += (
        [""] + _summary(document) + ["", "Shared conditions"] + _conditions(document)
    )
    lines += ["", "Configurations"]
    for row in document["rows"]:
        lines += [
            f"  {_name(row)}: {row['status']}; channels={_cell(row['channels'])}; "
            f"first hidden={_first_hidden(row)}; hidden rank={_cell(row['computed_hidden_rank'])}; "
            f"entropy log(T) coefficient={_cell(row['entropy_log_t_coefficient'])}",
            "    Counters: " + _counter_definitions(document, row["id"]),
        ] + ["    " + note for note in _row_notes(row)]
    rows = {row["id"]: row for row in document["rows"]}
    lines += ["", "Information relations (first / second)"]
    for pair in document["relations"]:
        lines.append(
            f"  {_name(rows[pair['left']])} / {_name(rows[pair['right']])}: "
            f"{_RELATION_LABELS[pair['relation']]}; {_scope(pair)}"
        )
    lines += ["", "Representative exact evidence", ""] + _evidence(
        document, markdown=False
    )
    lines += [
        "Channel counts describe the declared counters, not hardware cost. "
        "Entropy coefficients are asymptotic log(T) terms; zero does not establish finite-time recovery.",
        "Use --output-dir NEW_DIRECTORY for linked reports and replay inputs, or --format json for all exact evidence.",
        "",
    ]
    return "\n".join(lines)


def render_comparison_markdown(document: Mapping[str, Any]) -> str:
    """Build a readable report from the same comparison object as JSON/text."""
    study = document["study"]
    lines = [
        "# " + _markdown(study["name"]),
        "",
        f"Status: **{document['status']}**",
        "",
    ]
    if study.get("question"):
        lines += [_markdown(study["question"]), ""]
    lines += ["## Main findings", ""]
    lines += ["- " + _markdown(note) for note in _summary(document)]
    lines += ["", "## Shared conditions", ""]
    lines += ["- " + _markdown(note) for note in _conditions(document)]
    lines += [
        "",
        "Channel counts describe declared counters; they do not assign hardware cost. "
        "Metric summaries and information relations answer different questions.",
        "",
        "## Configuration comparison",
        "",
        "| Configuration | Channels | Status | First hidden layer | Hidden rank | Entropy log(T) coefficient |",
        "|---|---:|---|---|---:|---:|",
    ]
    for row in document["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown(_name(row)),
                    _cell(row["channels"]),
                    row["status"],
                    _first_hidden(row),
                    _cell(row["computed_hidden_rank"]),
                    _cell(row["entropy_log_t_coefficient"]),
                ]
            )
            + " |"
        )
    lines += [
        "",
        "Hidden rank refers to each candidate's computed horizon. In the first-hidden-layer "
        "column, 'none' applies to the full cycle group, 'none in computed layers' "
        "applies only to the computed exposure, and 'unavailable' records no conclusion. "
        "Entropy coefficients describe "
        "asymptotic log(T) growth; zero does not establish finite-time recovery.",
        "",
        "## Counters and configuration notes",
        "",
        "C(u → v) is the signed cumulative edge count: a jump u → v adds one and "
        "a reverse jump subtracts one. Readout vectors below follow each configuration's counter order.",
        "",
    ]
    for row in document["rows"]:
        lines += [
            "### " + _markdown(_name(row)),
            "",
            _markdown(_counter_definitions(document, row["id"])),
            "",
        ]
        lines += ["- " + _markdown(note) for note in _row_notes(row)]
        lines += ["", f"[Saved model](models/config-{row['id']}.json)"]
        if row["id"] in document["results"]:
            lines[-1] += f" · [Full analysis](raw/config-{row['id']}.json)"
        lines += [""]
    lines += [
        "## Information relations",
        "",
        "A more informative configuration distinguishes every history difference "
        "distinguished by the other, and some additional differences. Incomparable "
        "configurations each reveal differences the other leaves hidden.",
        "",
        "| First configuration | Second configuration | Information relation | Scope |",
        "|---|---|---|---|",
    ]
    rows = {row["id"]: row for row in document["rows"]}
    for pair in document["relations"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown(_name(rows[pair["left"]])),
                    _markdown(_name(rows[pair["right"]])),
                    _RELATION_LABELS[pair["relation"]],
                    _scope(pair),
                ]
            )
            + " |"
        )
    lines += ["", "## Representative exact evidence", ""] + _evidence(
        document, markdown=True
    )
    lines += [
        "## Files and reproducibility",
        "",
        "[Study input](study.json) · [All exact evidence](comparison.json) · "
        "[Replay instructions](README.md) · [Computation environment](environment.json)",
        "",
        "The JSON record preserves the complete graph, conditions, counter definitions, "
        "per-configuration analyses and exact certificates. Information equivalence applies "
        "on the stated integer cycle lattice and the legal readout images.",
        "",
        "<details>",
        "<summary>Input and software identity</summary>",
        "",
        "Study SHA-256: `" + document["study_sha256"] + "`.",
        "",
        "Producer: `"
        + document["producer"]["version"]
        + "`; code SHA-256: `"
        + document["producer"]["code_sha256"]
        + "`.",
        "",
        "</details>",
        "",
    ]
    return "\n".join(lines)


def write_comparison_bundle(
    document: Mapping[str, Any], output_dir: str | Path
) -> Path:
    """Write a fresh bundle; the final manifest marks successful export.

    Scientific INCOMPLETE and successful bundle export are separate states.
    Existing directories are never reused, including an interrupted earlier run.
    """
    from .comparison import parse_study

    study = parse_study(document["study"])
    expected_hash = hashlib.sha256(
        json.dumps(
            study,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if document.get("study_sha256") != expected_hash:
        raise ValueError("comparison study identity does not match its saved input")
    ids = {config["id"] for config in study["configurations"]}
    if set(document["results"]) - ids or {row["id"] for row in document["rows"]} != ids:
        raise ValueError("comparison configuration identities do not match its study")
    reverse = document["shared_conditions"]["reverse_tree_order"]
    if not isinstance(reverse, bool):
        raise ValueError("comparison reverse_tree_order must be a boolean")
    replay_flag = " --reverse-tree-order" if reverse else ""
    files = {
        "study.json": _json(study),
        "comparison.json": _json(document),
        "comparison.md": render_comparison_markdown(document),
        "environment.json": _json(document["producer"]["environment"]),
        "README.md": (
            "# Replay this configuration study\n\n"
            "Read the [comparison report](comparison.md), or inspect its "
            "[exact evidence](comparison.json) and [study input](study.json).\n\n"
            "## Run the study again\n\n"
            "1. Use the software build identified below and the package versions in "
            "[environment.json](environment.json).\n"
            "2. Open a terminal in this directory and run into a new destination:\n\n"
            "```sh\nhomological-observability compare study.json --output-dir replay"
            + replay_flag
            + "\n```\n\n"
            "3. Compare `comparison.json` with `replay/comparison.json`. Exact bytes "
            "agree for the same inputs, build, coordinate option and environment. "
            "Use a fresh destination for each further replay.\n\n"
            "The report retains each candidate's completion state. Exit code 0 means "
            "all candidates are naturally complete; 1 means at least one is partial, "
            "resource-limited or invalid; 2 means the command could not finish. "
            "Read the candidate's recovery note before adjusting the study.\n\n"
            "## Inspect one configuration\n\n"
            "Follow the model and full-analysis links in the comparison report. "
            "A saved model can also be analyzed separately:\n\n"
            "```sh\nhomological-observability analyze models/config-ID.json"
            + replay_flag
            + "\n```\n\n"
            "Replace `ID` with the configuration identifier from the report. "
            "The `raw/` directory retains each analyzed configuration. Invalid "
            "candidates retain their input in `models/` and their validation error "
            "in `comparison.json`; correct the indicated readout and rerun.\n\n"
            "## Software and environment\n\n"
            f"Producer version: `{document['producer']['version']}`.\n\n"
            f"Code SHA-256: `{document['producer']['code_sha256']}`.\n\n"
            "The code digest identifies the installed implementation. Use the matching "
            "source or wheel when a version label can refer to several builds. "
            "[environment.json](environment.json) records the original computation "
            "environment; the JSON result also retains this producer record. A changed "
            "digest identifies changed software even when scientific results agree.\n\n"
            "[manifest.json](manifest.json) lists file sizes and SHA-256 checksums. "
            "Its `bundle_status: COMPLETE` records a finished export. Scientific "
            "completeness is reported separately in [comparison.md](comparison.md).\n"
        ),
    }
    for config in study["configurations"]:
        identifier = config["id"]
        model = dict(study["model"])
        model.update(
            name=study["model"]["name"] + "/" + identifier,
            readouts=config["readouts"],
            analysis=study["analysis"],
        )
        if identifier in document["results"]:
            raw = document["results"][identifier]
            model = raw["model"]
            files["raw/config-" + identifier + ".json"] = _json(raw)
        files["models/config-" + identifier + ".json"] = _json(model)
    # Materialize all strings before reserving the destination. No serialization
    # failure can leave a directory that looks like a finished bundle.
    encoded = {name: content.encode("utf-8") for name, content in files.items()}
    manifest = {
        "schema_version": 1,
        "bundle_status": "COMPLETE",
        "files": [
            {
                "path": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for name, content in sorted(encoded.items())
        ],
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=False)
    for name, content in encoded.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
    with (destination / "manifest.json").open("x", encoding="utf-8") as stream:
        stream.write(_json(manifest))
    return destination
