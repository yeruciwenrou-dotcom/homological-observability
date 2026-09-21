#!/usr/bin/env python3
"""Compatibility wrapper for the packaged critical-kernel reference checks."""

from homological_observability.reference_critical import (
    DEFAULT_WINDOWS,
    build_results,
    main,
    validate_results,
    write_results,
)

__all__ = [
    "DEFAULT_WINDOWS",
    "build_results",
    "main",
    "validate_results",
    "write_results",
]


if __name__ == "__main__":
    main()
