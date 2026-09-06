"""Registry hash is computed from committed bytes, never a fabricated constant."""
from __future__ import annotations

import hashlib
from pathlib import Path

from dcm.algorithms.registry import (
    algorithm_registry_sha256,
    assert_catalog_matches_committed_json,
    catalog_bytes,
    load_algorithm_registry,
    registry_path,
)

ROOT = Path(__file__).resolve().parents[2]


def test_algorithm_registry_hash_from_committed_bytes():
    assert_catalog_matches_committed_json()
    path = registry_path()
    blob = path.read_bytes()
    assert blob == catalog_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    assert algorithm_registry_sha256() == digest
    pkg_copy = ROOT / "src" / "dcm" / "algorithms" / "data" / "algorithm_registry.json"
    assert pkg_copy.read_bytes() == blob
    source = (ROOT / "src" / "dcm" / "algorithms" / "registry.py").read_text(encoding="utf-8")
    assert "bba7b082bf67e12d87e675ac58d5b6f96d9cbad9b6a487a0aa157bf7cef9e599" not in source
    assert digest not in source
    records = load_algorithm_registry()
    assert all(r.registry_record_hash for r in records)
    ids = [r.algorithm_id for r in records]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
