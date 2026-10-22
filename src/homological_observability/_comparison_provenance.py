"""Content identities for the code that actually produced a comparison."""

from __future__ import annotations

import hashlib
import platform
from importlib import metadata, resources
from typing import Any

from .version import __version__


def producer_identity() -> dict[str, Any]:
    """Hash installed Python modules and schemas, without guessing a Git revision.

    A wheel does not normally retain its Git checkout. The content digest works
    for both a checkout and a wheel and avoids attributing a modified checkout
    to its last commit. Paths, timestamps, bytecode and caches are excluded.
    """
    root = resources.files("homological_observability")
    files = [
        (entry.name, entry) for entry in root.iterdir() if entry.name.endswith(".py")
    ]
    files.extend(
        ("schemas/" + entry.name, entry)
        for entry in root.joinpath("schemas").iterdir()
        if entry.name.endswith(".json")
    )
    digest = hashlib.sha256()
    for name, entry in sorted(files):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(entry.read_bytes()).digest())
    return {
        "name": "homological-observability",
        "version": __version__,
        "code_sha256": digest.hexdigest(),
        "source_commit": None,
        "environment": runtime_environment(),
    }


def runtime_environment() -> dict[str, Any]:
    """Record relevant runtime versions separately from the scientific result."""
    dependencies = {}
    for name in ("sympy", "networkx", "numpy", "scipy", "mpmath"):
        try:
            dependencies[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            dependencies[name] = None
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "dependencies": dependencies,
    }
