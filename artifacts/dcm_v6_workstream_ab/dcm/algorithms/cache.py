"""Hot-cache primitives used before Drive/web retrieval."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Hashable


class LRUCache:
    def __init__(self, capacity: int = 256) -> None:
        self.capacity = max(1, int(capacity))
        self._data: OrderedDict[Hashable, Any] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: Hashable, default: Any = None) -> Any:
        if key in self._data:
            self._data.move_to_end(key)
            self.hits += 1
            return self._data[key]
        self.misses += 1
        return default

    def put(self, key: Hashable, value: Any) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.capacity:
            self._data.popitem(last=False)

    def __contains__(self, key: object) -> bool:
        return key in self._data


class LFUCache:
    def __init__(self, capacity: int = 256) -> None:
        self.capacity = max(1, int(capacity))
        self._data: dict[Hashable, Any] = {}
        self._freq: dict[Hashable, int] = {}

    def get(self, key: Hashable, default: Any = None) -> Any:
        if key not in self._data:
            return default
        self._freq[key] = self._freq.get(key, 0) + 1
        return self._data[key]

    def put(self, key: Hashable, value: Any) -> None:
        if key not in self._data and len(self._data) >= self.capacity:
            victim = min(self._freq, key=lambda k: (self._freq[k], str(k)))
            self._data.pop(victim, None)
            self._freq.pop(victim, None)
        self._data[key] = value
        self._freq[key] = self._freq.get(key, 0) + 1
