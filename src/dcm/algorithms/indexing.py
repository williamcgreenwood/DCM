"""ChatGPT-native indexing primitives (hash, Bloom, Merkle, SQLite, graphs)."""
from __future__ import annotations

import hashlib
import sqlite3
import struct
from collections import defaultdict
from typing import Any, Hashable, Iterable, Iterator, Mapping, Sequence

from dcm.contracts.hashes import content_hash


def hash_table(pairs: Iterable[tuple[Hashable, Any]] | None = None) -> dict[Hashable, Any]:
    table: dict[Hashable, Any] = {}
    for key, value in pairs or ():
        table[key] = value
    return table


def content_address(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value):
        return value
    return content_hash(value)


class BloomFilter:
    def __init__(self, m_bits: int = 2048, k: int = 4) -> None:
        self.m = max(8, int(m_bits))
        self.k = max(1, int(k))
        self.bits = bytearray((self.m + 7) // 8)

    def _positions(self, key: bytes) -> Iterator[int]:
        digest = hashlib.sha256(key).digest()
        for i in range(self.k):
            start = (i * 4) % (len(digest) - 3)
            yield int.from_bytes(digest[start:start + 4], "big") % self.m

    def add(self, key: str | bytes) -> None:
        raw = key.encode("utf-8") if isinstance(key, str) else key
        for pos in self._positions(raw):
            self.bits[pos // 8] |= 1 << (pos % 8)

    def __contains__(self, key: str | bytes) -> bool:
        raw = key.encode("utf-8") if isinstance(key, str) else key
        for pos in self._positions(raw):
            if not (self.bits[pos // 8] & (1 << (pos % 8))):
                return False
        return True

    def might_contain(self, key: str | bytes) -> bool:
        return key in self


class XorFilterFallback(BloomFilter):
    """Portable XOR-filter stand-in: Bloom with a static snapshot contract."""


class CuckooFilter:
    def __init__(self, capacity: int = 256, bucket_size: int = 4) -> None:
        self.capacity = max(8, capacity)
        self.bucket_size = bucket_size
        self.buckets: list[list[int]] = [[] for _ in range(self.capacity)]

    def _fp(self, key: str) -> int:
        return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)

    def _i1(self, fingerprint: int) -> int:
        return fingerprint % self.capacity

    def _i2(self, i1: int, fingerprint: int) -> int:
        return (i1 ^ (fingerprint % self.capacity)) % self.capacity

    def add(self, key: str) -> bool:
        fp = self._fp(key)
        for idx in (self._i1(fp), self._i2(self._i1(fp), fp)):
            if fp in self.buckets[idx]:
                return True
            if len(self.buckets[idx]) < self.bucket_size:
                self.buckets[idx].append(fp)
                return True
        idx = self._i1(fp)
        victim = self.buckets[idx][0]
        self.buckets[idx][0] = fp
        alt = self._i2(idx, victim)
        if len(self.buckets[alt]) < self.bucket_size:
            self.buckets[alt].append(victim)
            return True
        return False

    def __contains__(self, key: str) -> bool:
        fp = self._fp(key)
        return fp in self.buckets[self._i1(fp)] or fp in self.buckets[self._i2(self._i1(fp), fp)]


class Bitset:
    def __init__(self, n: int = 0) -> None:
        self.n = n
        self.data = bytearray((n + 7) // 8)

    def add(self, i: int) -> None:
        if i >= self.n:
            self.n = i + 1
            needed = (self.n + 7) // 8
            if needed > len(self.data):
                self.data.extend(b"\x00" * (needed - len(self.data)))
        self.data[i // 8] |= 1 << (i % 8)

    def __contains__(self, i: int) -> bool:
        if i < 0 or i >= self.n:
            return False
        return bool(self.data[i // 8] & (1 << (i % 8)))

    def intersection(self, other: "Bitset") -> "Bitset":
        n = min(self.n, other.n)
        out = Bitset(n)
        for i, (a, b) in enumerate(zip(self.data, other.data)):
            out.data[i] = a & b
        return out


def merkle_leaves(values: Sequence[Any]) -> list[str]:
    if not values:
        return [hashlib.sha256(b"").hexdigest()]
    leaves: list[str] = []
    for value in values:
        if isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value):
            leaves.append(value.lower())
        elif isinstance(value, (bytes, bytearray)):
            leaves.append(hashlib.sha256(value).hexdigest())
        else:
            leaves.append(content_hash(value))
    return leaves


def merkle_root(values: Sequence[Any]) -> str:
    layer = merkle_leaves(values)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        nxt: list[str] = []
        for i in range(0, len(layer), 2):
            left = bytes.fromhex(layer[i])
            right = bytes.fromhex(layer[i + 1])
            nxt.append(hashlib.sha256(left + right).hexdigest())
        layer = nxt
    return layer[0]


def merkle_proof(values: Sequence[Any], index: int) -> list[tuple[str, str]]:
    layer = merkle_leaves(values)
    if index < 0 or index >= len(layer):
        raise IndexError("MERKLE_LEAF_INDEX")
    proof: list[tuple[str, str]] = []
    idx = index
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        sibling = idx ^ 1
        side = "L" if sibling < idx else "R"
        proof.append((side, layer[sibling]))
        nxt: list[str] = []
        for i in range(0, len(layer), 2):
            nxt.append(hashlib.sha256(bytes.fromhex(layer[i]) + bytes.fromhex(layer[i + 1])).hexdigest())
        layer = nxt
        idx //= 2
    return proof


class CSRGraph:
    def __init__(self, edges: Iterable[tuple[str, str]] | None = None) -> None:
        fwd: dict[str, list[str]] = defaultdict(list)
        rev: dict[str, list[str]] = defaultdict(list)
        nodes: dict[str, None] = {}
        for a, b in edges or ():
            nodes[a] = None
            nodes[b] = None
            fwd[a].append(b)
            rev[b].append(a)
        self.nodes = tuple(nodes)
        self.forward = {k: tuple(v) for k, v in fwd.items()}
        self.reverse = {k: tuple(v) for k, v in rev.items()}

    def neighbors(self, node: str) -> tuple[str, ...]:
        return self.forward.get(node, ())

    def predecessors(self, node: str) -> tuple[str, ...]:
        return self.reverse.get(node, ())


class HypergraphIncidence:
    def __init__(self) -> None:
        self.edge_members: dict[str, tuple[str, ...]] = {}
        self.member_edges: dict[str, list[str]] = defaultdict(list)

    def add_edge(self, edge_id: str, members: Iterable[str]) -> None:
        uniq = tuple(dict.fromkeys(str(m) for m in members))
        self.edge_members[edge_id] = uniq
        for member in uniq:
            self.member_edges[member].append(edge_id)

    def edges_for(self, member: str) -> tuple[str, ...]:
        return tuple(self.member_edges.get(member, ()))

    def members(self, edge_id: str) -> tuple[str, ...]:
        return self.edge_members.get(edge_id, ())


def bitemporal_key(entity_id: str, claim_type: str, valid_at: str, observed_at: str, cutoff: str) -> tuple[str, str, str, str, str]:
    return (entity_id, claim_type, valid_at, observed_at, cutoff)


def sqlite_composite_index(conn: sqlite3.Connection, table: str, columns: Sequence[str], name: str | None = None) -> str:
    idx = name or f"idx_{table}_{'_'.join(columns)}"
    cols = ", ".join(columns)
    conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {table} ({cols})")
    return idx


def open_memory_index() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE records (entity_id TEXT, claim_type TEXT, valid_at TEXT, observed_at TEXT, cutoff TEXT, payload TEXT)"
    )
    sqlite_composite_index(conn, "records", ("entity_id", "claim_type", "valid_at", "observed_at", "cutoff"))
    sqlite_composite_index(conn, "records", ("cutoff", "entity_id"), name="idx_records_cutoff_entity")
    return conn


class SimHashIndex:
    def __init__(self) -> None:
        self.items: dict[str, int] = {}

    def add(self, key: str, digest: int) -> None:
        self.items[key] = digest

    def nearest(self, digest: int, *, max_distance: int = 8) -> list[tuple[str, int]]:
        from dcm.algorithms.searching import hamming64

        hits = [(k, hamming64(digest, v)) for k, v in self.items.items()]
        hits = [h for h in hits if h[1] <= max_distance]
        hits.sort(key=lambda item: (item[1], item[0]))
        return hits


class MinHashLSHIndex:
    def __init__(self, *, bands: int = 8, rows: int = 4) -> None:
        from dcm.algorithms.searching import LSHIndex

        self.lsh = LSHIndex(bands=bands, rows=rows)
        self.sigs: dict[str, tuple[int, ...]] = {}

    def add(self, key: str, signature: Sequence[int]) -> None:
        sig = tuple(int(x) for x in signature)
        self.sigs[key] = sig
        self.lsh.add(key, sig)

    def query(self, signature: Sequence[int]) -> list[str]:
        return self.lsh.query(signature)


def git_blob_identity(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha256(header + data).hexdigest()
