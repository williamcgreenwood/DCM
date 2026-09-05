"""Public model namespace with lazy exports.

The model package is imported by identity and research code.  Eagerly
importing explanations here pulls in the feature store, which pulls in
research packets, which then imports this package again.  Lazy exports keep
the public convenience API while making every submodule independently
importable in a clean installed environment.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "from_worlds": ("dcm.model.distributions", "from_worlds"),
    "grade": ("dcm.model.grade", "grade"),
    "surface": ("dcm.model.line_surface", "surface"),
    "simulate_player_worlds": ("dcm.model.worlds", "simulate_player_worlds"),
    "value_from_stats": ("dcm.model.worlds", "value_from_stats"),
    "derive_market": ("dcm.model.market_derive", "derive_market"),
    "build_prop_explanation": ("dcm.model.explanation", "build_prop_explanation"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module = import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value
