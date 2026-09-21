#!/usr/bin/env python3
"""Compatibility wrapper for the packaged appendix reference checks."""

from homological_observability.reference_appendix import (
    BASE_COUNTS,
    DELTAS,
    MAP_MEANS,
    build_results,
    main,
    validate_results,
    write_results,
)

__all__ = [
    "BASE_COUNTS",
    "DELTAS",
    "MAP_MEANS",
    "build_results",
    "main",
    "validate_results",
    "write_results",
]


if __name__ == "__main__":
    main()
