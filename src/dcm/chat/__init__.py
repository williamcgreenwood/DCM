"""ChatGPT/Grok-native DCM host API.

from dcm.chat import HostSession
session = HostSession.prepare(...)

Lazy exports avoid import cycles with research.observation_execute.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "HostSession": ("dcm.chat.session", "HostSession"),
    "doctor": ("dcm.chat.session", "doctor"),
}

__all__ = ["HostSession", "doctor"]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module = import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value
