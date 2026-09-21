#!/usr/bin/env python3
"""Inspect a finite-cycle bridge posterior for a chosen observation window."""

from __future__ import annotations

import argparse
import math

from homological_observability import residue_probability, ring_bridge_probability


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycle", type=int, default=4, help="cycle size n")
    parser.add_argument(
        "--residue",
        type=int,
        default=2,
        help="canonical observed residue, 0 <= r < n",
    )
    parser.add_argument(
        "--delta", type=float, default=0.1, help="observation-window width"
    )
    parser.add_argument(
        "--windings",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=(-2, 2),
        help="inclusive winding range to display",
    )
    args = parser.parse_args()
    if args.cycle < 3:
        parser.error("--cycle must be at least 3")
    if not 0 <= args.residue < args.cycle:
        parser.error("--residue must satisfy 0 <= residue < --cycle")
    if not math.isfinite(args.delta) or args.delta <= 0.0:
        parser.error("--delta must be positive and finite")
    lower, upper = args.windings
    if lower > upper:
        parser.error("MIN must not exceed MAX")

    endpoint = residue_probability(args.cycle, args.residue, args.delta)
    rows = []
    for winding in range(lower, upper + 1):
        posterior = ring_bridge_probability(
            args.cycle, args.residue, winding, args.delta
        )
        rows.append(
            (
                winding,
                args.residue + args.cycle * winding,
                posterior,
            )
        )

    print(f"C{args.cycle} bridge: residue={args.residue}, delta={args.delta:g}")
    print(f"endpoint probability: {endpoint:.12g}\n")
    print(f"{'winding':>9}  {'lifted displacement':>19}  {'posterior':>14}")
    for winding, displacement, posterior in rows:
        print(f"{winding:9d}  {displacement:19d}  {posterior:14.10g}")
    shown_mass = sum(row[2] for row in rows)
    print(f"\nposterior mass shown: {shown_mass:.12g}")


if __name__ == "__main__":
    main()
