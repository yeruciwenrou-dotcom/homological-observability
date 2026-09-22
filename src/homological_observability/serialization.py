"""Stable serialization and human-facing rendering for analysis results."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import Enum
from fractions import Fraction
from typing import Any

from sympy.matrices.matrixbase import MatrixBase

from ._integer_io import check_output_integers
from .analysis import AnalysisStatus, TopologyAnalysis
from .integer_lattice import QuotientInvariants
from .model import GraphModel
from .version import __version__

SCHEMA_NAME = "homological-observability.analysis"
SCHEMA_VERSION = 2


class ArtifactRole(str, Enum):
    """Provenance role of one serialized analysis document."""

    FRESH_ANALYSIS = "fresh-analysis"
    BUILTIN_EXAMPLE = "builtin-example"


class EvidenceCategory(str, Enum):
    """Kinds of evidence represented in an analysis document."""

    EXACT_INTEGER = "EXACT_INTEGER"
    EXACT_COMBINATORIAL = "EXACT_COMBINATORIAL"
    ASYMPTOTIC_THEOREM = "ASYMPTOTIC_THEOREM"


def model_to_dict(model: GraphModel) -> dict[str, Any]:
    """Return the normalized public model contract used for stable hashing."""

    analysis = {
        key: value
        for key, value in (
            ("max_layer", model.max_layer),
            ("max_cycles", model.max_cycles),
            ("alpha", model.alpha),
            ("observation_time", model.observation_time),
            ("sampling_interval", model.sampling_interval),
        )
        if value is not None
    }
    return {
        "schema_version": 1,
        "name": model.name,
        "vertices": list(model.vertices),
        "edges": [list(edge) for edge in model.edges],
        "readouts": [
            {
                "name": readout.name,
                "coefficients": [
                    {"edge": list(edge), "coefficient": coefficient}
                    for edge, coefficient in readout.coefficients
                ],
            }
            for readout in model.readouts
        ],
        "analysis": analysis,
    }


def normalized_model_sha256(model: GraphModel) -> str:
    """Hash the normalized model rather than path- or whitespace-dependent input."""

    canonical = json.dumps(
        model_to_dict(model),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _matrix(matrix: MatrixBase) -> dict[str, Any]:
    return {
        "rows": matrix.rows,
        "columns": matrix.cols,
        "data": [
            [int(matrix[row, column]) for column in range(matrix.cols)]
            for row in range(matrix.rows)
        ],
    }


def _fraction(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _quotient(value: QuotientInvariants | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "free_rank": value.free_rank,
        "torsion_factors": list(value.torsion_factors),
        "finite_order": value.finite_order,
        "evidence_category": EvidenceCategory.EXACT_INTEGER.value,
    }


def _lattice(
    basis: MatrixBase,
    quotient: QuotientInvariants | None,
) -> dict[str, Any]:
    return {
        "ambient_rank": basis.rows,
        "rank": basis.cols,
        "basis_columns": _matrix(basis),
        "graded_quotient": _quotient(quotient),
        "evidence_category": EvidenceCategory.EXACT_INTEGER.value,
    }


def _first_nonzero_rank(layers: list[dict[str, Any]], field: str) -> int | None:
    for layer in layers:
        if layer[field]["rank"]:
            return int(layer["layer"])
    return None


def analysis_to_dict(
    result: TopologyAnalysis,
    *,
    artifact_role: ArtifactRole | str = ArtifactRole.FRESH_ANALYSIS,
) -> dict[str, Any]:
    """Serialize one result into the versioned, deterministic output contract."""

    try:
        role = ArtifactRole(artifact_role)
    except ValueError as error:
        allowed = ", ".join(value.value for value in ArtifactRole)
        raise ValueError(f"artifact_role must be one of: {allowed}") from error

    model_document = model_to_dict(result.model)
    homology = {
        "rank": result.basis.rank,
        "edge_orientation": "lexicographically-smaller vertex to larger vertex",
        "tree_edges": [list(edge) for edge in result.basis.tree_edges],
        "chord_edges": [list(edge) for edge in result.basis.chord_edges],
        "fundamental_cycle_matrix": _matrix(result.basis.fundamental_cycles),
        "readout_names": [readout.name for readout in result.model.readouts],
        "readout_matrix": _matrix(result.readout),
        "coordinate_warning": (
            "Basis matrices depend on the deterministic spanning-tree convention; "
            "ranks and quotient invariants are the basis-independent public results."
        ),
        "evidence_category": EvidenceCategory.EXACT_INTEGER.value,
    }

    if result.filtration is None:
        filtration_document = None
        phase_document = None
        summary = {
            "homology_rank": result.basis.rank,
            "requested_max_layer": result.requested_max_layer,
            "natural_max_layer": result.natural_max_layer,
            "computed_max_layer": None,
            "requested_horizon_complete": result.requested_horizon_complete,
            "natural_filtration_complete": result.natural_filtration_complete,
        }
        evidence_categories = [EvidenceCategory.EXACT_INTEGER.value]
    else:
        layers = [
            {
                "layer": layer.layer,
                "maximum_cycle_length": 2 * layer.layer,
                "exposure": _lattice(layer.exposure, layer.exposure_graded),
                "visible": _lattice(layer.visible, layer.visible_graded),
                "hidden": _lattice(layer.hidden, layer.hidden_graded),
            }
            for layer in result.filtration.layers
        ]
        filtration_document = {
            "cycles": [
                {"vertices": list(cycle), "length": len(cycle)}
                for cycle in result.filtration.cycles
            ],
            "layers": layers,
            "evidence_categories": [
                EvidenceCategory.EXACT_COMBINATORIAL.value,
                EvidenceCategory.EXACT_INTEGER.value,
            ],
        }
        summary = {
            "homology_rank": result.basis.rank,
            "requested_max_layer": result.requested_max_layer,
            "natural_max_layer": result.natural_max_layer,
            "computed_max_layer": result.filtration.max_layer,
            "requested_horizon_complete": result.requested_horizon_complete,
            "natural_filtration_complete": result.natural_filtration_complete,
            "cycle_count": len(result.filtration.cycles),
            "first_nonzero_exposure_layer": _first_nonzero_rank(layers, "exposure"),
            "first_nonzero_visible_layer": _first_nonzero_rank(layers, "visible"),
            "first_nonzero_hidden_layer": _first_nonzero_rank(layers, "hidden"),
        }
        if result.phase is None:
            raise AssertionError(
                "complete filtration results must carry a phase result"
            )
        phase_document = {
            "interpretation": "paper-derived asymptotic prediction",
            "alpha": result.phase.alpha,
            "observation_time": result.phase.observation_time,
            "sampling_interval": result.phase.sampling_interval,
            "entropy_log_t_coefficient": result.phase.entropy_log_t_coefficient,
            "layers": [
                {
                    "layer": layer.layer,
                    "hidden_free_rank": layer.hidden_free_rank,
                    "critical_alpha": _fraction(layer.critical_alpha),
                    "snapshot_budget_exponent": _fraction(
                        layer.snapshot_budget_exponent
                    ),
                    "scaling_exponent": layer.scaling_exponent,
                    "regime": layer.regime.value if layer.regime is not None else None,
                    "lambda": layer.lambda_value,
                    "entropy_log_t_coefficient": (layer.entropy_log_t_coefficient),
                }
                for layer in result.phase.layers
            ],
            "evidence_category": EvidenceCategory.ASYMPTOTIC_THEOREM.value,
            "boundary_note": (
                "These values apply the paper's asymptotic law; they are not "
                "finite-sample error bars or confidence guarantees."
            ),
        }
        evidence_categories = [
            EvidenceCategory.EXACT_INTEGER.value,
            EvidenceCategory.EXACT_COMBINATORIAL.value,
            EvidenceCategory.ASYMPTOTIC_THEOREM.value,
        ]

    limit = (
        {
            "resource": result.limit.resource,
            "limit": result.limit.limit,
            "complete_components": list(result.limit.complete_components),
            "incomplete_components": list(result.limit.incomplete_components),
        }
        if result.limit is not None
        else None
    )
    document = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "software": {
            "name": "homological-observability",
            "version": __version__,
        },
        "artifact_role": role.value,
        "status": result.status.value,
        "evidence_categories": evidence_categories,
        "normalized_model_sha256": normalized_model_sha256(result.model),
        "model": model_document,
        "summary": summary,
        "homology": homology,
        "filtration": filtration_document,
        "phase": phase_document,
        "limit": limit,
    }
    check_output_integers(document)
    return document


def _as_document(
    value: TopologyAnalysis | Mapping[str, Any],
    *,
    artifact_role: ArtifactRole | str,
) -> dict[str, Any]:
    if isinstance(value, TopologyAnalysis):
        return analysis_to_dict(value, artifact_role=artifact_role)
    document = dict(value)
    check_output_integers(document)
    return document


def render_json(
    value: TopologyAnalysis | Mapping[str, Any],
    *,
    artifact_role: ArtifactRole | str = ArtifactRole.FRESH_ANALYSIS,
) -> str:
    """Render stable UTF-8 JSON with a trailing newline."""

    document = _as_document(value, artifact_role=artifact_role)
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _torsion_label(quotient: Mapping[str, Any] | None) -> str:
    if quotient is None:
        return "n/a"
    factors = quotient["torsion_factors"]
    return "×".join(f"Z/{factor}" for factor in factors) if factors else "none"


def _markdown_torsion_label(quotient: Mapping[str, Any]) -> str:
    factors = quotient["torsion_factors"]
    if not factors:
        return "none"
    summands = [rf"\mathbb Z/{factor}\mathbb Z" for factor in factors]
    return "$" + r"\oplus".join(summands) + "$"


def render_text(
    value: TopologyAnalysis | Mapping[str, Any],
    *,
    artifact_role: ArtifactRole | str = ArtifactRole.FRESH_ANALYSIS,
) -> str:
    """Render a compact terminal view from the same structured contract."""

    document = _as_document(value, artifact_role=artifact_role)
    model = document["model"]
    lines = [
        f"Homological observability: {model['name']}",
        f"status: {document['status']}",
        f"artifact role: {document['artifact_role']}",
        f"normalized model sha256: {document['normalized_model_sha256']}",
        f"homology rank: {document['homology']['rank']}",
        f"requested max layer: {document['summary']['requested_max_layer']}",
        f"computed max layer: {document['summary']['computed_max_layer']}",
        f"natural max layer: {document['summary']['natural_max_layer']}",
        "requested horizon complete: "
        + str(document["summary"]["requested_horizon_complete"]).lower(),
        "natural filtration complete: "
        + str(document["summary"]["natural_filtration_complete"]).lower(),
    ]
    if document["status"] == AnalysisStatus.LIMIT_REACHED.value:
        limit = document["limit"]
        lines.extend(
            [
                f"resource limit: {limit['resource']}={limit['limit']}",
                "complete components: " + ", ".join(limit["complete_components"]),
                "incomplete components: " + ", ".join(limit["incomplete_components"]),
            ]
        )
        return "\n".join(lines) + "\n"

    if document["status"] == AnalysisStatus.PARTIAL_HORIZON.value:
        lines.extend(
            [
                "",
                "Partial horizon: all requested layers were computed, but the "
                "natural filtration is not complete.",
            ]
        )

    rows = [
        [
            "layer",
            "exposure",
            "visible",
            "hidden",
            "E quotient",
            "V quotient",
            "H quotient",
            "regime",
        ]
    ]
    phase_layers = {layer["layer"]: layer for layer in document["phase"]["layers"]}
    for layer in document["filtration"]["layers"]:
        if layer["layer"] < 2:
            continue
        entries = []
        for field in ("exposure", "visible", "hidden"):
            quotient = layer[field]["graded_quotient"]
            entries.append(
                f"r{quotient['free_rank']};torsion={_torsion_label(quotient)}"
            )
        regime = phase_layers[layer["layer"]]["regime"] or "not-evaluated"
        rows.append(
            [
                str(layer["layer"]),
                str(layer["exposure"]["rank"]),
                str(layer["visible"]["rank"]),
                str(layer["hidden"]["rank"]),
                *entries,
                regime,
            ]
        )
    widths = [max(map(len, column)) for column in zip(*rows)]
    lines.append("")
    for row in rows:
        lines.append(
            "  ".join(
                value.rjust(width) if index < 4 else value.ljust(width)
                for index, (value, width) in enumerate(zip(row, widths))
            ).rstrip()
        )
    lines.extend(
        [
            "",
            "Evidence: exact integer lattices and finite cycle enumeration; phase "
            "labels are paper-derived asymptotic predictions.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_markdown(
    value: TopologyAnalysis | Mapping[str, Any],
    *,
    artifact_role: ArtifactRole | str = ArtifactRole.FRESH_ANALYSIS,
) -> str:
    """Render a durable Markdown summary from the structured contract."""

    document = _as_document(value, artifact_role=artifact_role)
    model = document["model"]
    lines = [
        f"# Homological observability: {model['name']}",
        "",
        f"- Status: `{document['status']}`",
        f"- Artifact role: `{document['artifact_role']}`",
        f"- Homology rank: {document['homology']['rank']}",
        f"- Requested maximum layer: {document['summary']['requested_max_layer']}",
        f"- Computed maximum layer: {document['summary']['computed_max_layer']}",
        f"- Natural maximum layer: {document['summary']['natural_max_layer']}",
        "- Requested horizon complete: "
        f"`{str(document['summary']['requested_horizon_complete']).lower()}`",
        "- Natural filtration complete: "
        f"`{str(document['summary']['natural_filtration_complete']).lower()}`",
        f"- Normalized model SHA-256: `{document['normalized_model_sha256']}`",
    ]
    if document["status"] == AnalysisStatus.LIMIT_REACHED.value:
        limit = document["limit"]
        lines.extend(
            [
                "",
                "## Incomplete analysis",
                "",
                f"The `{limit['resource']}` resource limit of {limit['limit']} was reached.",
                "",
                "Complete components: " + ", ".join(limit["complete_components"]),
                "",
                "Incomplete components: " + ", ".join(limit["incomplete_components"]),
            ]
        )
        return "\n".join(lines) + "\n"

    if document["status"] == AnalysisStatus.PARTIAL_HORIZON.value:
        lines.extend(
            [
                "",
                "## Partial horizon",
                "",
                "Every requested layer was computed, but the natural filtration "
                "is not complete. Higher layers may expose additional cycle "
                "directions.",
            ]
        )

    lines.extend(
        [
            "",
            "## Exact filtration",
            "",
            "Here **visible** denotes $\\pi(L_m)$ and **hidden** denotes "
            "$K_m=L_m\\cap\\ker\\pi$. Each quotient is taken relative to the "
            "previous layer.",
            "",
            "| Layer $m$ | Exposure rank | Visible rank | Hidden rank | "
            "Exposure quotient | Visible quotient | Hidden quotient | Regime |",
            "| ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    phase_layers = {layer["layer"]: layer for layer in document["phase"]["layers"]}
    for layer in document["filtration"]["layers"]:
        if layer["layer"] < 2:
            continue
        quotients = []
        for field in ("exposure", "visible", "hidden"):
            quotient = layer[field]["graded_quotient"]
            quotients.append(
                f"free rank {quotient['free_rank']}; torsion "
                f"{_markdown_torsion_label(quotient)}"
            )
        regime = phase_layers[layer["layer"]]["regime"] or "not evaluated"
        lines.append(
            f"| {layer['layer']} | {layer['exposure']['rank']} | "
            f"{layer['visible']['rank']} | {layer['hidden']['rank']} | "
            f"{quotients[0]} | {quotients[1]} | {quotients[2]} | {regime} |"
        )
    lines.extend(
        [
            "",
            "## Evidence boundary",
            "",
            "The filtration uses exact integer lattice operations and finite cycle "
            "enumeration. Phase labels apply the paper's asymptotic theorem; they "
            "are not finite-sample error bars or confidence guarantees.",
        ]
    )
    return "\n".join(lines) + "\n"
