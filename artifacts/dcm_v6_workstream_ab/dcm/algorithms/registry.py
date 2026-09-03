"""Load, hash, and query the permanent algorithm registry."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dcm.algorithms.catalog import ALGORITHM_RECORDS, registry_document
from dcm.algorithms.contracts import AlgorithmRecord
from dcm.contracts.hashes import content_hash


REGISTRY_RELATIVE = "configs/algorithm_registry.json"


def _candidates() -> list[Path]:
    env = os.environ.get("DCM_ALGORITHM_REGISTRY")
    here = Path(__file__).resolve()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    for parent in here.parents:
        out.append(parent / REGISTRY_RELATIVE)
    out.append(here.parent / "data" / "algorithm_registry.json")
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in out:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def registry_path() -> Path:
    for path in _candidates():
        if path.is_file():
            return path
    raise FileNotFoundError("ALGORITHM_REGISTRY_MISSING")


def _hash_record(record: dict[str, Any]) -> str:
    payload = {k: v for k, v in record.items() if k != "registry_record_hash"}
    return content_hash(payload)


def _finalize_records(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    for raw in raw_records:
        rec = dict(raw)
        rec["registry_record_hash"] = _hash_record(rec)
        AlgorithmRecord.from_mapping(rec)
        finalized.append(rec)
    return finalized


def catalog_bytes() -> bytes:
    doc = registry_document()
    doc["algorithms"] = _finalize_records(list(doc["algorithms"]))
    return (json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _canonical_registry_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def load_registry_payload() -> dict[str, Any]:
    try:
        path = registry_path()
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = json.loads(catalog_bytes().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("algorithms"), list):
        raise RuntimeError("ALGORITHM_REGISTRY_INVALID")
    return payload


@lru_cache(maxsize=1)
def load_algorithm_registry() -> tuple[AlgorithmRecord, ...]:
    payload = load_registry_payload()
    records = []
    seen: set[str] = set()
    for raw in payload["algorithms"]:
        rec = AlgorithmRecord.from_mapping(raw)
        if rec.algorithm_id in seen:
            raise RuntimeError(f"ALGORITHM_ID_DUPLICATE:{rec.algorithm_id}")
        seen.add(rec.algorithm_id)
        expected = _hash_record(rec.payload_for_hash())
        if rec.registry_record_hash and rec.registry_record_hash != expected:
            raise RuntimeError(f"ALGORITHM_RECORD_HASH_MISMATCH:{rec.algorithm_id}")
        records.append(rec)
    return tuple(sorted(records, key=lambda r: r.algorithm_id))


def algorithm_registry_sha256(payload: dict[str, Any] | None = None) -> str:
    """Hash exact canonical registry bytes (sort_keys JSON + trailing newline)."""
    if payload is None:
        try:
            return hashlib.sha256(registry_path().read_bytes()).hexdigest()
        except FileNotFoundError:
            return hashlib.sha256(catalog_bytes()).hexdigest()
    return hashlib.sha256(_canonical_registry_bytes(payload)).hexdigest()


def require_algorithm(algorithm_id: str) -> AlgorithmRecord:
    for rec in load_algorithm_registry():
        if rec.algorithm_id == algorithm_id:
            if rec.retired_version:
                raise RuntimeError(f"ALGORITHM_RETIRED:{algorithm_id}")
            return rec
    raise KeyError(f"ALGORITHM_NOT_REGISTERED:{algorithm_id}")


def algorithms_by_lifecycle(lifecycle: str) -> tuple[AlgorithmRecord, ...]:
    return tuple(r for r in load_algorithm_registry() if r.lifecycle == lifecycle)


def algorithms_by_family(family: str) -> tuple[AlgorithmRecord, ...]:
    return tuple(r for r in load_algorithm_registry() if r.algorithm_family == family)


def assert_catalog_matches_committed_json() -> None:
    committed = registry_path().read_bytes()
    expected = catalog_bytes()
    if committed != expected:
        raise RuntimeError("ALGORITHM_REGISTRY_STALE")


def catalog_source_records() -> tuple[dict[str, Any], ...]:
    return ALGORITHM_RECORDS


def resolve_implementation(record: AlgorithmRecord) -> Any:
    mod = importlib.import_module(record.implementation_module)
    obj: Any = mod
    for part in record.implementation_symbol.split("."):
        obj = getattr(obj, part)
    return obj
