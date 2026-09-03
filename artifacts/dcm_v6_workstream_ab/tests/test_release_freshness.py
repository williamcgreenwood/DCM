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
    result = build_portable(dest, workspace=REPO, build_wheel_artifact=False)
    verified = verify_extraction(Path(result["dest"]))
    assert verified["ok"] is True
    assert (dest / "RELEASE_MANIFEST.json").is_file()
    assert (dest / "INSTALL_SHA256").is_file()
    assert (dest / "RUNTIME_PROMPT.md").is_file()
    assert (dest / "HASHES.json").is_file()
    assert (dest / "INSTALL_SHA256.txt").is_file()
    assert (dest / "CAPABILITY.json").is_file()
    assert (dest / "COMPLETE_PROJECT_SOURCE.txt").is_file()
    hashes = json.loads((dest / "HASHES.json").read_text())
    assert hashes.get("gitCommit")
    assert hashes.get("algorithmConstitutionVersion") == "DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903"
    assert hashes.get("algorithmConstitutionSha256")
    assert hashes.get("algorithmRegistrySha256")
    assert hashes["expectedV1Hash"] == EXPECTED_SHA256
    assert hashes["phase_bc_schema_v2.json"] == SCHEMA_V2_EXPECTED_SHA256
    n = count_pytest_functions(ROOT / "tests")
    assert n >= 116


def test_release_manifest_requires_git_commit(tmp_path: Path, monkeypatch):
    from dcm.release import build_portable

    monkeypatch.setattr("dcm.release.resolve_git_commit", lambda _ws: "")
    with __import__("pytest").raises(RuntimeError, match="RELEASE_GIT_COMMIT_BLANK"):
        build_portable(tmp_path / "blank", workspace=REPO, build_wheel_artifact=False)


def test_portable_release_git_commit_and_complete_project_source(tmp_path: Path):
    from dcm.release import build_portable, verify_complete_project_source, verify_extraction

    dest = tmp_path / "portable"
    result = build_portable(dest, workspace=REPO, build_wheel_artifact=False)
    verified = verify_extraction(Path(result["dest"]))
    assert verified["ok"] is True
    manifest = json.loads((dest / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["gitCommit"]
    assert len(manifest["gitCommit"]) >= 7
    assert (dest / "INSTALL_SHA256.txt").is_file()
    assert (dest / "CAPABILITY.json").is_file()
    assert (dest / "COMPLETE_PROJECT_SOURCE.txt").is_file()
    cap = json.loads((dest / "CAPABILITY.json").read_text(encoding="utf-8"))
    assert cap["sports"]["basketball"]["productionState"] == "productionCapable"
    assert cap["sports"]["baseball"]["productionState"] == "shadow"
    source = verify_complete_project_source(dest, REPO, sample=12)
    assert source["ok"] is True
    assert source["checked"] >= 8
    assert source["fileCount"] >= 20
    hashes = json.loads((dest / "HASHES.json").read_text(encoding="utf-8"))
    assert hashes["gitCommit"] == manifest["gitCommit"]
    assert hashes["COMPLETE_PROJECT_SOURCE.bundleSha256"] == source["bundleSha256"]
    # Spot-check a few canonical files against disk.
    pkg = REPO / "artifacts" / "dcm_v6_workstream_ab"
    text = (dest / "COMPLETE_PROJECT_SOURCE.txt").read_text(encoding="utf-8")
    found = 0
    for rel in ("dcm/release.py", "dcm/runner.py", "dcm/learning/postgame.py", "pillars_dcm/release.py"):
        needle = f"  {rel}"
        matching = [ln for ln in text.splitlines() if ln.endswith(needle)]
        assert matching, rel
        digest = matching[0].split()[0]
        import hashlib

        disk = hashlib.sha256((pkg / rel).read_bytes()).hexdigest()
        assert digest == disk, rel
        found += 1
    assert found == 4
