"""Reading surfaces and portable bundles for one computed comparison."""

from __future__ import annotations

import hashlib
import json
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
    return " ".join(str(value).split())


def _markdown(value: Any) -> str:
    text = _plain(value)
    for char in ("\\", "`", "*", "_", "[", "]", "<", ">", "|"):
        text = text.replace(char, "\\" + char)
    return text


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


def render_comparison_text(document: Mapping[str, Any]) -> str:
    """Render the computed facts; this surface performs no scientific inference."""
    study = document["study"]
    lines = [f"{_plain(study['name'])} — {document['status']}"]
    if study.get("question"):
        lines += [_plain(study["question"])]
    lines += [""] + [_plain(item) for item in document["explanations"]]
    lines += ["", "Configurations"]
    for row in document["rows"]:
        lines.append(
            f"  {row['id']} ({_plain(row['label'])}): {row['status']}; "
            f"channels={_cell(row['channels'])}; first hidden={_first_hidden(row)}; "
            f"hidden rank={_cell(row['computed_hidden_rank'])}; "
            f"entropy log(T) coefficient={_cell(row['entropy_log_t_coefficient'])}"
        )
        lines += ["    " + _plain(item) for item in row["explanations"]]
        if row.get("error"):
            lines += ["    " + _plain(row["error"])]
        if row.get("recovery"):
            lines += ["    " + _plain(row["recovery"])]
    lines += ["", "Information relations"]
    for relation in document["relations"]:
        lines.append(
            f"  {relation['left']} / {relation['right']}: "
            f"{relation['relation']} [{relation['scope']}]"
        )
    lines += [
        "",
        "Shared analysis: " + json.dumps(study["analysis"], sort_keys=True),
        "Study SHA-256: " + document["study_sha256"],
        "Use --output-dir NEW_DIRECTORY for the report, integer witnesses and replay inputs.",
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
    for item in document["explanations"]:
        lines += [_markdown(item), ""]
    lines += [
        "",
        "## Configuration comparison",
        "",
        "| Configuration | Channels | Status | First hidden layer | Hidden rank at computed horizon | Entropy log(T) coefficient |",
        "|---|---:|---|---|---:|---:|",
    ]
    for row in document["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown(row["label"]) + " (`" + row["id"] + "`)",
                    _cell(row["channels"]),
                    row["status"],
                    _first_hidden(row),
                    _cell(row["computed_hidden_rank"]),
                    _cell(row["entropy_log_t_coefficient"]),
                ]
            )
            + " |"
        )
    lines += ["", "## What the configurations reveal", ""]
    for row in document["rows"]:
        lines += ["### " + _markdown(row["label"]), ""]
        lines += [_markdown(item) for item in row["explanations"]]
        if row.get("error"):
            lines += ["", "Error: " + _markdown(row["error"])]
        if row.get("recovery"):
            lines += ["", _markdown(row["recovery"])]
        lines += [""]
    lines += [
        "## Pairwise information relations",
        "",
        "| Left | Right | Relation | Scope |",
        "|---|---|---|---|",
    ]
    for relation in document["relations"]:
        lines.append(
            f"| {relation['left']} | {relation['right']} | "
            f"{relation['relation']} | {relation['scope']} |"
        )
    lines += [
        "",
        "<details>",
        "<summary>Read the explanation for each pair</summary>",
        "",
    ]
    for relation in document["relations"]:
        lines += [
            f"### {relation['left']} / {relation['right']}",
            "",
            f"**{relation['relation']}** — scope: `{relation['scope']}`.",
            "",
        ]
        lines += [_markdown(item) for item in relation["explanations"]] + [""]
    lines += ["</details>", ""]
    lines += [
        "## Conditions and exact evidence",
        "",
        "Shared graph and settings are saved in [study.json](study.json). "
        "The [machine-readable comparison](comparison.json) retains integer "
        "containment certificates, oriented-edge witnesses and per-configuration results.",
        "",
        "```json",
        _json(document["shared_conditions"]).rstrip(),
        "```",
        "",
        "Study SHA-256: `" + document["study_sha256"] + "`.",
        "",
        "Producer: `"
        + document["producer"]["version"]
        + "`; code SHA-256: `"
        + document["producer"]["code_sha256"]
        + "`.",
        "",
        "[Replay instructions](README.md) include the exact inputs and environment record.",
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
            "Start with comparison.md. comparison.json contains the same conclusions "
            "and exact integer evidence. A manifest with bundle_status COMPLETE "
            "marks a fully written bundle; the scientific status may be INCOMPLETE.\n\n"
            f"Producer version: {document['producer']['version']}\n\n"
            f"Code SHA-256: {document['producer']['code_sha256']}\n\n"
            "Use the same software build and the versions in environment.json for "
            "an exact replay. Development builds require the matching source or wheel; "
            "the version label alone does not identify their content.\n\n"
            "From this directory, with that build installed:\n\n"
            "```sh\nhomological-observability compare study.json --output-dir replay"
            + replay_flag
            + "\n```\n\n"
            "Compare comparison.json with replay/comparison.json. Deterministic "
            "scientific fields contain no timing; producer records the original "
            "calculation environment. Exact bytes agree for the same inputs, "
            "build, coordinate option and environment. "
            "A changed producer digest identifies changed software even if the "
            "scientific results agree. Use a fresh destination for each replay.\n\n"
            "The models/ files can also be passed individually to "
            "`homological-observability analyze MODEL.json"
            + replay_flag
            + "`. raw/ preserves each successfully "
            "analyzed configuration under the existing analysis schema. Invalid "
            "configurations retain their input in models/ and their error in "
            "comparison.json. Correct the indicated readout and rerun the study.\n\n"
            "Information equivalence applies to exact cumulative readouts on their "
            "legal image and the stated cycle lattice. Entropy coefficients are "
            "asymptotic quantities; zero does not assert finite-time recovery.\n"
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
