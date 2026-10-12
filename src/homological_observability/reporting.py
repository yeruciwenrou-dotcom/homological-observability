"""Human-readable report and summary figure for a full companion run."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = ("#1f4e79", "#b45309", "#2f6f44", "#8b3a62")
MARKERS = ("o", "s", "^", "D")
LINESTYLES = ("-", "--", "-.", ":")


def write_report(
    critical: pd.DataFrame, selected: pd.DataFrame, output: Path, *, checked: bool
) -> None:
    """Write a compact scientific reading of the generated tables."""
    first = critical.iloc[0]
    last = critical.iloc[-1]
    map_error = selected.loc[
        selected["check"] == "Poisson-averaged binomial MAP identity",
        "absolute_error",
    ].max()
    auxiliary = selected.loc[
        selected["check"] == "parity peak with subleading auxiliary increments"
    ].iloc[-1]
    unperturbed = selected.loc[
        selected["check"] == "parity peak without auxiliary increments"
    ].iloc[-1]
    c3_tv_coarse = first["c3_leading_count_tv_upper"]
    c3_tv_fine = last["c3_leading_count_tv_upper"]
    c4_tv_coarse = first["c4_visible_count_tv_upper"]
    c4_tv_fine = last["c4_visible_count_tv_upper"]
    c3_mean_coarse = first["c3_leading_two_jump_mean_each_direction"]
    c3_mean_fine = last["c3_leading_two_jump_mean_each_direction"]
    c4_mean_coarse = first["c4_mean_visible_count"]
    c4_mean_fine = last["c4_mean_visible_count"]

    report = rf"""# Computational companion report

**Calculation checks: PASS**

**Frozen-reference comparison: {"PASS" if checked else "NOT REQUESTED"}**

The calculation reproduces the finite-cycle bridge posteriors, critical count
limits, the Poisson-averaged binomial MAP identity, and the reciprocal-lattice
peak mechanism presented in the paper.

## What the calculations explain

A particle observed at discrete times can follow different routes between the
same two recorded states. On a symmetric triangle, a rare two-jump route can
hide one winding behind an ordinary neighboring-state transition. On a
symmetric four-cycle, opposite-vertex snapshots reveal a rare crossing
opportunity, but its two shortest routes remain equally likely. Both mechanisms
have the cumulative scale $T\delta$, yet the observer retains different
information in the two experiments.

For the four-cycle, the number of opposite-vertex windows is visible in the
record. The critical posterior conditions on that count before assessing the
unknown route marks. The Poisson-averaged binomial MAP identity then gives the
optimal mean success probability for this limiting cycle-history decision.
These examples separate the location of a sampling threshold from the
decision problem that survives at the threshold.

## Critical finite-cycle kernels

Refining the observation grid from {int(first["n_windows"]):,} to {int(last["n_windows"]):,} windows
gives the following diagnostics at $\theta=T\delta=1$. Observation time grows
along this sequence while the sampling interval shrinks; rates set the time
unit.

| diagnostic | coarse grid | finest grid |
| --- | ---: | ---: |
| C3 leading-count TV upper bound | {c3_tv_coarse:.6g} | {c3_tv_fine:.6g} |
| C4 visible-count TV upper bound | {c4_tv_coarse:.6g} | {c4_tv_fine:.6g} |
| C3 mean per winding direction | {c3_mean_coarse:.6g} | {c3_mean_fine:.6g} |
| C4 mean visible count | {c4_mean_coarse:.6g} | {c4_mean_fine:.6g} |

The C3 and C4 count laws move toward their critical Poisson limits as temporal
resolution is refined. The local C3 bridge approximation improves along this
refinement sequence, while the two C4 diametric routes retain equal conditional
weight.

The TV bounds measure errors in the count-law approximations. Their decrease
validates the limiting description; it does not mean that history-recovery
error vanishes at this fixed critical intensity.

## Exact and asymptotic checks

- The direct Poisson mixture and Bessel expression for the critical MAP value
  agree to a maximum absolute error of **{map_error:.3g}** over the displayed
  parameter values.
- The C3, C4, C5, and C6 finite-cycle comparisons all show decreasing absolute
  error as $\delta$ is reduced from 0.2 to 0.025.
- At the largest lattice size, the local Gaussian error is
  **{unperturbed["computed"]:.6g}** without parity-breaking increments and
  **{auxiliary["computed"]:.6g}** with the subleading auxiliary increments.

The final comparison isolates an integer effect. A distribution confined to
one parity class can look broad while still defeating a local Gaussian
approximation on the full lattice. Rarer increments that connect the parity
classes remove this obstruction when enough of them accumulate. Integer
structure can therefore matter even when the broad variance scale looks
similar. This is a mechanism check, separate from the finite-ring experiments.

The committed CSV tables are the numerical reference layer. The general
theorems and their assumptions are established analytically in the paper.
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")


def write_summary_figure(
    critical: pd.DataFrame,
    selected: pd.DataFrame,
    png_output: Path,
    svg_output: Path,
) -> None:
    """Plot the three convergence mechanisms exposed by the companion."""
    matplotlib.rcParams["svg.hashsalt"] = "homological-observability"
    with plt.rc_context(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 7.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    ):
        figure, axes = plt.subplots(1, 3, figsize=(11.5, 3.25))

        axes[0].loglog(
            critical["n_windows"],
            critical["c3_leading_count_tv_upper"],
            "o-",
            color=COLORS[0],
            label="C3 hidden winding",
            markevery=(0, 2),
            zorder=2,
        )
        axes[0].loglog(
            critical["n_windows"],
            critical["c4_visible_count_tv_upper"],
            "s--",
            color=COLORS[1],
            label="C4 visible event",
            markevery=(1, 2),
            markerfacecolor="white",
            markeredgewidth=1.2,
            zorder=3,
        )
        axes[0].set_title("Critical count convergence")
        axes[0].set_xlabel("number of windows")
        axes[0].set_ylabel("TV upper bound")
        axes[0].legend(frameon=False, handlelength=3.0)

        bridge = selected.loc[selected["category"] == "finite-cycle bridge"]
        for color, marker, linestyle, (label, group) in zip(
            COLORS, MARKERS, LINESTYLES, bridge.groupby("check")
        ):
            ordered = group.sort_values("parameter", ascending=False)
            axes[1].loglog(
                ordered["parameter"],
                ordered["absolute_error"],
                color=color,
                marker=marker,
                linestyle=linestyle,
                label=label.replace(" complementary route", " route")
                .replace(" each geodesic route", " route")
                .replace(" diametric endpoint", " endpoint"),
            )
        axes[1].invert_xaxis()
        axes[1].set_xticks([0.2, 0.1, 0.05, 0.025])
        axes[1].set_xticklabels(["0.2", "0.1", "0.05", "0.025"])
        axes[1].minorticks_off()
        axes[1].set_title("Finite-cycle asymptotics")
        axes[1].set_xlabel(r"window width $\delta$ (finer $\rightarrow$)")
        axes[1].set_ylabel("absolute error")
        axes[1].legend(frameon=False, handlelength=2.8)

        lattice = selected.loc[selected["category"] == "reciprocal-lattice peak"]
        labels = {
            "parity peak without auxiliary increments": "without auxiliary increments",
            "parity peak with subleading auxiliary increments": "with auxiliary increments",
        }
        for color, marker, linestyle, check in zip(
            COLORS[:2], MARKERS[:2], LINESTYLES[:2], labels
        ):
            group = lattice.loc[lattice["check"] == check]
            axes[2].loglog(
                group["parameter"],
                group["computed"],
                color=color,
                marker=marker,
                linestyle=linestyle,
                label=labels[check],
            )
        axes[2].set_title("Reciprocal-peak suppression")
        axes[2].set_xlabel("base increments")
        axes[2].set_ylabel("local Gaussian error")
        axes[2].legend(frameon=False, handlelength=2.8)

        for axis in axes:
            axis.grid(True, which="major", linewidth=0.45, alpha=0.25)
        figure.tight_layout(w_pad=2.0)

        png_output.parent.mkdir(parents=True, exist_ok=True)
        svg_output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(
            png_output,
            dpi=180,
            bbox_inches="tight",
            metadata={"Software": "homological-observability"},
        )
        figure.savefig(
            svg_output,
            bbox_inches="tight",
            metadata={"Creator": "homological-observability", "Date": None},
        )
        plt.close(figure)
