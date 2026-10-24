"""Request-aware views of already computed sampling and lattice records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def sampling_mode(settings: Mapping[str, Any]) -> str:
    if settings.get("alpha") is not None:
        return "asymptotic"
    if settings.get("observation_time") is not None:
        return "finite"
    return "structure"


def sampling_request(settings: Mapping[str, Any]) -> str:
    mode = sampling_mode(settings)
    if mode == "asymptotic":
        alpha = settings["alpha"]
        kind = "exact rational" if isinstance(alpha, str) else "binary floating-point"
        return f"Sampling law: delta = T^(-{alpha}) in reference-rate units; alpha is {kind}."
    if mode == "finite":
        return (
            f"Observation time: {settings['observation_time']}; sampling interval: "
            f"{settings['sampling_interval']} (reference-rate units)."
        )
    return (
        "Structure only: graph and counter information, with no sampling law supplied."
    )


def _table(headers: list[str], rows: list[list[str]], *, markdown: bool) -> list[str]:
    if markdown:
        return [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ] + ["| " + " | ".join(row) + " |" for row in rows]
    widths = [max(len(value) for value in column) for column in zip(headers, *rows)]
    return [
        "  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip()
        for row in [headers, *rows]
    ]


def sampling_tables(
    results: Mapping[str, Mapping[str, Any]],
    settings: Mapping[str, Any],
    *,
    markdown: bool,
    comparison: bool,
) -> list[str]:
    """Read phase values directly; never derive scales or classifications here."""
    mode = sampling_mode(settings)
    if mode == "structure":
        return []
    available = {
        key: value for key, value in results.items() if value.get("phase") is not None
    }
    title = "Sampling scales" if mode == "finite" else "Sampling phases"
    heading = "## " if markdown else ""
    lines = [heading + title, ""]
    if not available:
        return lines + [
            "No sampling results were computed. The requested conditions are recorded above; consult the completion states and recovery notes.",
            "",
        ]
    shared = {}
    for result in available.values():
        for layer in result["phase"]["layers"]:
            shared.setdefault(layer["layer"], layer)
    if mode == "finite":
        headers = ["Layer m", "lambda_m = T delta^(m-1)"]
        rows = [[str(m), repr(layer["lambda"])] for m, layer in sorted(shared.items())]
        lines += [
            "Each scale is shared by configurations computed through that layer."
            if comparison
            else "Cumulative exposure scales at the supplied time and interval.",
            "",
        ]
    else:
        headers = ["Layer m", "1 - alpha(m-1)", "Regime"]
        rows = [
            [str(m), repr(layer["scaling_exponent"]), layer["regime"]]
            for m, layer in sorted(shared.items())
        ]
        lines += [
            "Regimes use the exact sign of the supplied alpha value. Displayed exponents are rounded once to floating point.",
            "",
        ]
    lines += _table(headers, rows, markdown=markdown) + [""]
    if not rows:
        lines += ["There are no computed sampling layers m >= 2.", ""]
    headers = (["Configuration ID"] if comparison else []) + [
        "Layer m",
        "Hidden graded free rank",
        "Hidden graded torsion",
    ]
    if mode == "asymptotic":
        headers += ["Entropy log(T) coefficient"]
    rows = []
    for identifier, result in available.items():
        phases = {layer["layer"]: layer for layer in result["phase"]["layers"]}
        for layer in result["filtration"]["layers"]:
            m = layer["layer"]
            if m < 2:
                continue
            quotient = layer["hidden"]["graded_quotient"]
            torsion = (
                ", ".join(f"Z/{factor}" for factor in quotient["torsion_factors"])
                or "none"
            )
            row = ([identifier] if comparison else []) + [
                str(m),
                str(quotient["free_rank"]),
                torsion,
            ]
            if mode == "asymptotic":
                row += [repr(phases[m]["entropy_log_t_coefficient"])]
            rows.append(row)
    lines += _table(headers, rows, markdown=markdown) + [""]
    lines += [
        "These quotients describe newly hidden information relative to the preceding layer. Zero free rank can coexist with finite torsion. Only computed layers are shown.",
        "",
    ]
    if mode == "asymptotic":
        if not comparison:
            result = next(iter(available.values()))
            lines += [
                "Total entropy log(T) coefficient on the computed horizon: "
                + repr(result["phase"]["entropy_log_t_coefficient"])
                + ".",
                "",
            ]
        lines += [
            "Entropy coefficients describe asymptotic log(T) growth; zero does not establish finite-time recovery.",
            "",
        ]
    else:
        lines += [
            "A finite lambda_m is an exposure scale, not a recovery probability or an error bound.",
            "",
        ]
    return lines
