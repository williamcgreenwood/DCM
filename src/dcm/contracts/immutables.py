"""Deep immutability helpers. frozen=True is not enough if nested maps stay mutable."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping


class FrozenMap(Mapping):
    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any] | None = None):
        raw = {}
        for key, value in dict(data or {}).items():
            raw[str(key)] = deep_freeze(value)
        self._data = MappingProxyType(raw)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"FrozenMap({dict(self._data)!r})"

    def as_dict(self) -> dict:
        return {k: _unfreeze(v) for k, v in self._data.items()}


def deep_freeze(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    if isinstance(value, FrozenMap):
        return value
    if isinstance(value, Mapping):
        return FrozenMap(value)
    if isinstance(value, (list, tuple, set)):
        return tuple(deep_freeze(v) for v in value)
    return value


def _unfreeze(value: Any) -> Any:
    if isinstance(value, FrozenMap):
        return value.as_dict()
    if isinstance(value, tuple):
        return [_unfreeze(v) for v in value]
    return value
