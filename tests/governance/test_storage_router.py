from pathlib import Path

import pytest

from dcm.runtime.storage_router import (
    DRIVE_HIERARCHY,
    FolderRegistry,
    StorageRouter,
)


def test_registry_rejects_duplicate_folder_ids():
    with pytest.raises(ValueError, match="DUPLICATE"):
        FolderRegistry.from_mapping({"folders": {"00_control": "same", "01_inputs": "same"}})


def test_route_is_deterministic_and_does_not_guess_remote_ids(tmp_path: Path):
    router = StorageRouter(tmp_path)
    one = router.route(filename="evidence_claims.json", run_id="run-1", period="2026-09-05")
    two = router.route(filename="evidence_claims.json", run_id="run-1", period="2026-09-05")
    assert one.to_dict() == two.to_dict()
    assert one.folder_key == "02_research"
    assert one.remote_folder_id is None
    assert one.relative_path == "02_research/CFB/2026-09-05/evidence_claims.json"


def test_forbidden_objects_never_route_or_stage(tmp_path: Path):
    router = StorageRouter(tmp_path)
    with pytest.raises(ValueError, match="PRIVACY"):
        router.route(filename="raw_capture.har")
    with pytest.raises(ValueError, match="PRIVACY"):
        router.route(filename="research_cache.sqlite3")


def test_stage_is_immutable_and_hash_bound(tmp_path: Path):
    router = StorageRouter(tmp_path)
    route = router.route(filename="claims.json", folder_key="02_research", run_id="r")
    first = router.stage_bytes(route, b'{"safe":true}\n')
    second = router.stage_bytes(route, b'{"safe":true}\n')
    assert first == second
    with pytest.raises(RuntimeError, match="IMMUTABLE"):
        router.stage_bytes(route, b'{"safe":false}\n')


def test_run_route_marks_sqlite_local_only(tmp_path: Path):
    (tmp_path / "claims.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "research_cache.sqlite3").write_bytes(b"sqlite")
    body = StorageRouter(tmp_path).persist_run_route(
        run_id="r", artifact_paths=tmp_path.iterdir()
    )
    assert body["routes"]
    assert any(item["artifact"] == "research_cache.sqlite3" for item in body["blockedLocalOnly"])
    assert set(DRIVE_HIERARCHY) == set(body["drive"]["requiredKeys"])
