"""ChatGPT-native sorting and partial-selection primitives."""
from __future__ import annotations

import heapq
from typing import Any, Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")


def timsort(items: Iterable[T], *, key: Callable[[T], Any] | None = None, reverse: bool = False) -> list[T]:
    return sorted(items, key=key, reverse=reverse)


def heap_topk(items: Sequence[T], k: int, *, key: Callable[[T], Any] | None = None) -> list[T]:
    if k <= 0:
        return []
    if k >= len(items):
        return timsort(items, key=key, reverse=True)
    if key is None:
        return heapq.nlargest(k, items)
    return heapq.nlargest(k, items, key=key)


def heap_bottomk(items: Sequence[T], k: int, *, key: Callable[[T], Any] | None = None) -> list[T]:
    if k <= 0:
        return []
    if k >= len(items):
        return timsort(items, key=key)
    if key is None:
        return heapq.nsmallest(k, items)
    return heapq.nsmallest(k, items, key=key)


def _key_of(item: T, key: Callable[[T], Any] | None) -> Any:
    return item if key is None else key(item)


def quickselect(items: Sequence[T], k: int, *, key: Callable[[T], Any] | None = None) -> T:
    if not items:
        raise ValueError("QUICKSELECT_EMPTY")
    if k < 0 or k >= len(items):
        raise IndexError("QUICKSELECT_K")
    arr = list(items)

    def partition(lo: int, hi: int) -> int:
        pivot = _key_of(arr[hi], key)
        i = lo
        for j in range(lo, hi):
            if _key_of(arr[j], key) <= pivot:
                arr[i], arr[j] = arr[j], arr[i]
                i += 1
        arr[i], arr[hi] = arr[hi], arr[i]
        return i

    lo, hi = 0, len(arr) - 1
    while True:
        p = partition(lo, hi)
        if p == k:
            return arr[p]
        if p < k:
            lo = p + 1
        else:
            hi = p - 1


def introselect(items: Sequence[T], k: int, *, key: Callable[[T], Any] | None = None) -> T:
    try:
        return quickselect(items, k, key=key)
    except RecursionError:
        ordered = timsort(items, key=key)
        return ordered[k]


def counting_sort(values: Sequence[int]) -> list[int]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    width = hi - lo + 1
    if width > max(1024, 8 * len(values)):
        return timsort(values)
    counts = [0] * width
    for v in values:
        counts[v - lo] += 1
    out: list[int] = []
    for i, c in enumerate(counts):
        if c:
            out.extend([i + lo] * c)
    return out


def radix_sort(values: Sequence[int]) -> list[int]:
    if not values:
        return []
    offset = -min(0, min(values))
    shifted = [v + offset for v in values]
    max_v = max(shifted)
    exp = 1
    out = list(shifted)
    while max_v // exp > 0:
        buckets: list[list[int]] = [[] for _ in range(10)]
        for v in out:
            buckets[(v // exp) % 10].append(v)
        out = [v for bucket in buckets for v in bucket]
        exp *= 10
    return [v - offset for v in out]


def bucket_sort(values: Sequence[float], *, buckets: int = 10) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return list(values)
    width = (hi - lo) or 1.0
    slots: list[list[float]] = [[] for _ in range(max(1, buckets))]
    for v in values:
        idx = min(buckets - 1, int((v - lo) / width * buckets))
        slots[idx].append(v)
    out: list[float] = []
    for slot in slots:
        out.extend(sorted(slot))
    return out


def k_way_merge(streams: Sequence[Iterable[T]], *, key: Callable[[T], Any] | None = None) -> list[T]:
    heap: list[tuple[Any, int, T]] = []
    iterators = [iter(s) for s in streams]
    for i, it in enumerate(iterators):
        try:
            item = next(it)
        except StopIteration:
            continue
        heapq.heappush(heap, (_key_of(item, key), i, item))
    out: list[T] = []
    while heap:
        _, i, item = heapq.heappop(heap)
        out.append(item)
        try:
            nxt = next(iterators[i])
        except StopIteration:
            continue
        heapq.heappush(heap, (_key_of(nxt, key), i, nxt))
    return out


def external_merge_sort(chunks: Sequence[Sequence[T]], *, key: Callable[[T], Any] | None = None) -> list[T]:
    sorted_chunks = [timsort(chunk, key=key) for chunk in chunks]
    return k_way_merge(sorted_chunks, key=key)


def multi_key_sort(items: Sequence[T], keys: Sequence[Callable[[T], Any]], *, reverse: Sequence[bool] | None = None) -> list[T]:
    flags = list(reverse or [False] * len(keys))
    if len(flags) != len(keys):
        raise ValueError("MULTI_KEY_REVERSE_MISMATCH")
    decorated = []
    for item in items:
        deco = []
        for kfn, rev in zip(keys, flags):
            val = kfn(item)
            deco.append(_Reverse(val) if rev else val)
        decorated.append((tuple(deco), item))
    decorated.sort(key=lambda row: row[0])
    return [item for _, item in decorated]


class _Reverse:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __lt__(self, other: "_Reverse") -> bool:
        return self.value > other.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Reverse) and self.value == other.value


def topological_kahn(nodes: Sequence[str], edges: Sequence[tuple[str, str]]) -> list[str]:
    incoming: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        if a not in adj or b not in incoming:
            raise ValueError(f"TOPO_UNKNOWN_NODE:{a}->{b}")
        adj[a].append(b)
        incoming[b] += 1
    ready = sorted(n for n, c in incoming.items() if c == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for nxt in adj[node]:
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
                ready.sort()
    if len(order) != len(nodes):
        raise ValueError("TOPO_CYCLE")
    return order
