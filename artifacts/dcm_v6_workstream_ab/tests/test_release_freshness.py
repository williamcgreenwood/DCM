from __future__ import annotations

import json
from pathlib import Path

from dcm.release import build_portable, count_pytest_functions, verify_extraction
from dcm.runtime.schema_root import EXPECTED_SHA256, SCHEMA_V2_EXPECTED_SHA256
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE, load_version_manifest

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]


def test_committed_zip_absent():
    zip_path = REPO / "artifacts" / "dcm_v6_workstream_ab.zip"
    assert not zip_path.exists(), (
        "Committed ZIP is forbidden. Build releases with "
        "python -m pillars_dcm.release / scripts/build_portable.py"
    )


def test_manifests_are_not_stale_41():
    man = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    release_txt = (ROOT / "RELEASE_MANIFEST.txt").read_text(encoding="utf-8")
    assert "41 passed" not in release_txt
    assert "41" not in str(man.get("historical_slice") or "") or int(man.get("reported_test_count") or 0) >= 116
    assert man["learning_revision"] == "LR000000"
    assert man.get("predictive_superiority") in {"NONE", None} or man.get("predictiveClaim") == "NONE"
    assert int(man.get("reported_test_count") or 0) >= 116
    version = load_version_manifest()
    assert version["software"] == SOFTWARE
    assert version["learningRevision"] == LEARNING_REVISION
    assert version["predictiveClaim"] == PREDICTIVE_CLAIM
    assert version["expectedV1Hash"] == EXPECTED_SHA256
    assert version["schemaHash"] == SCHEMA_V2_EXPECTED_SHA256
    pkg = ROOT / "dcm" / "VERSION.json"
    if pkg.is_file():
        assert json.loads(pkg.read_text())["software"] == version["software"]
        assert json.loads(pkg.read_text())["schemaHash"] == version["schemaHash"]


def test_portable_release_builder_and_extraction(tmp_path: Path):
    dest = tmp_path / "portable"
    result = build_portable(dest, workspace=REPO)
    verified = verify_extraction(Path(result["dest"]))
    assert verified["ok"] is True
    assert (dest / "RELEASE_MANIFEST.json").is_file()
    assert (dest / "INSTALL_SHA256").is_file()
    assert (dest / "RUNTIME_PROMPT.md").is_file()
    assert (dest / "HASHES.json").is_file()
    hashes = json.loads((dest / "HASHES.json").read_text())
    assert hashes["expectedV1Hash"] == EXPECTED_SHA256
    assert hashes["phase_bc_schema_v2.json"] == SCHEMA_V2_EXPECTED_SHA256
    n = count_pytest_functions(ROOT / "tests")
    assert n >= 116
