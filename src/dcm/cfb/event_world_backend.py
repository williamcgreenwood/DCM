"""CFB EventWorld backend selection (reference Python vs NumPy SoA).

Public joint simulation API stays conceptually identical. The NumPy backend
keeps the same ``random.Random`` + sha256 seed stream (``rngVersion`` v1) so
world ledgers remain bitwise-comparable to the reference path. No silent RNG
semantic change: a future alternate stream requires a version bump + tests.
"""
from __future__ import annotations

import os
from typing import Literal

BackendName = Literal["reference", "numpy"]

RNG_VERSION = "dcm.cfb.event_world.rng.v1"
BACKEND_SCHEMA = "dcm.cfb.event_world.backend.v1-20260906"

# Default when NumPy is importable (always true in the declared runtime).
DEFAULT_BACKEND: BackendName = "numpy"
ENV_VAR = "DCM_EVENTWORLD_BACKEND"


def numpy_available() -> bool:
    try:
        import numpy  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_event_world_backend(requested: str | None = None) -> BackendName:
    """Resolve backend: explicit arg → env → default (numpy if available)."""
    raw = (requested if requested is not None else os.environ.get(ENV_VAR) or "").strip().lower()
    if not raw:
        return DEFAULT_BACKEND if numpy_available() else "reference"
    if raw in {"reference", "python", "ref"}:
        return "reference"
    if raw in {"numpy", "np", "soa"}:
        if not numpy_available():
            return "reference"
        return "numpy"
    raise ValueError(f"UNKNOWN_EVENTWORLD_BACKEND:{raw}")


def backend_meta(backend: BackendName) -> dict[str, str | bool]:
    return {
        "backendSchema": BACKEND_SCHEMA,
        "backend": backend,
        "rngVersion": RNG_VERSION,
        "rngStream": "python.random.Random+sha256-seed-prefix16",
        "numpyAvailable": numpy_available(),
    }
