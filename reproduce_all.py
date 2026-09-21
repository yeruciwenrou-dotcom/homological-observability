#!/usr/bin/env python3
"""Compatibility wrapper for the packaged full reproduction command."""

from homological_observability.reproduction import (
    ReproductionMismatch,
    ReproductionResult,
    compare_with_reference,
    main,
    run_reproduction,
    sha256,
    validate_output_directory,
    validated_output_path,
)

__all__ = [
    "ReproductionMismatch",
    "ReproductionResult",
    "compare_with_reference",
    "main",
    "run_reproduction",
    "sha256",
    "validate_output_directory",
    "validated_output_path",
]


if __name__ == "__main__":
    raise SystemExit(main())
