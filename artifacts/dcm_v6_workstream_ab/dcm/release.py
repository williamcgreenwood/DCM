"""Portable release builder.

Releases are built by this module (or scripts/build_portable.py), not by a
committed ZIP blob. The historical artifacts/dcm_v6_workstream_ab.zip is
forbidden in git because ChatGPT can load a stale DCM from it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.runtime.schema_root import EXPECTED_SHA256, SCHEMA_V2_EXPECTED_SHA256, SCHEMA_V2_ID, sha256_file, v2_schema_path
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE, load_version_manifest, version_json_path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "VERSION.json").is_file() and (parent / "pyproject.toml").is_file():
            return parent
    return here.parents[3]


def count_pytest_functions(tests_root: Path) -> int:
    n = 0
    for path in tests_root.rglob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        n += sum(1 for line in text.splitlines() if line.startswith("def test_"))
    return n


def build_portable(dest: Path, *, workspace: Path | None = None) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    root = workspace or repo_root()
    manifest = load_version_manifest()
    version_path = version_json_path()
    schema_path = v2_schema_path(root)
    if schema_path is None:
        raise FileNotFoundError("V2_SCHEMA_MISSING")
    version_hash = sha256_file(version_path)
    schema_hash = sha256_file(schema_path)
    tests_root = Path(__file__).resolve().parents[1] / "tests"
    test_count = count_pytest_functions(tests_root)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    release = {
        "document": "PILLARS_DCM_RELEASE_MANIFEST",
        "software": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "optimizedDcm60Claim": False,
        "hostPerformanceCertified": False,
        "gitCommit": manifest.get("gitCommit") or "",
        "schemaId": SCHEMA_V2_ID,
        "schemaHash": schema_hash,
        "schemaHashExpected": SCHEMA_V2_EXPECTED_SHA256,
        "schemaProductionEligible": False,
        "schemaAcceptedForProduction": False,
        "expectedV1Hash": EXPECTED_SHA256,
        "versionJsonPath": str(version_path),
        "versionJsonSha256": version_hash,
        "schemaPath": str(schema_path),
        "pytestFunctionCount": test_count,
        "pytestNote": "116+ collected tests expected on this branch; 41 is a stale historical count.",
        "createdAtUtc": created,
        "buildCommand": "python -m pillars_dcm.release  OR  python scripts/build_portable.py",
        "committedZipForbidden": True,
        "canonicalEngine": "Python",
        "viewer": "TypeScript (CANONICAL_ENGINE_IS_PYTHON)",
    }
    release["contentHash"] = _sha256_bytes(
        json.dumps({k: v for k, v in release.items() if k != "contentHash"}, sort_keys=True, separators=(",", ":")).encode()
    )
    (dest / "RELEASE_MANIFEST.json").write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    install_lines = [
        f"{version_hash}  VERSION.json",
        f"{schema_hash}  phase_bc_schema_v2.json",
        f"{EXPECTED_SHA256}  PHASE_BC_SCHEMA_V1_expected (bytes absent)",
        f"{release['contentHash']}  RELEASE_MANIFEST.json contentHash",
    ]
    (dest / "INSTALL_SHA256").write_text("\n".join(install_lines) + "\n", encoding="utf-8")
    prompt = f"""# Pillars DCM portable runtime prompt

Software: {SOFTWARE}
Learning revision: {LEARNING_REVISION}
Predictive claim: {PREDICTIVE_CLAIM}

This is not optimized DCM 6.0. Host performance is not certified.
Python is the single canonical engine. TypeScript is a viewer only.

Install from the repo root (no PYTHONPATH):

    python3 -m venv .venv && source .venv/bin/activate
    pip install .
    pillars-dcm --help
    python -m dcm --help
    python -m pillars_dcm --help

Never load artifacts/dcm_v6_workstream_ab.zip — that blob is not a release
channel. Build a portable package with:

    python -m pillars_dcm.release --out <dir>
    python scripts/build_portable.py --out <dir>

Cutoff is required (--cutoff or --cutoff-from-capture). --version must match
VERSION.json software or softwareShort.
"""
    (dest / "RUNTIME_PROMPT.md").write_text(prompt, encoding="utf-8")
    hashes = {
        "VERSION.json": version_hash,
        "phase_bc_schema_v2.json": schema_hash,
        "expectedV1Hash": EXPECTED_SHA256,
        "RELEASE_MANIFEST.contentHash": release["contentHash"],
    }
    (dest / "HASHES.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"dest": str(dest), "manifest": release, "hashes": hashes}


def verify_extraction(dest: Path) -> dict[str, Any]:
    dest = Path(dest)
    required = ["RELEASE_MANIFEST.json", "INSTALL_SHA256", "RUNTIME_PROMPT.md", "HASHES.json"]
    missing = [name for name in required if not (dest / name).is_file()]
    if missing:
        raise RuntimeError(f"RELEASE_EXTRACTION_MISSING:{','.join(missing)}")
    manifest = json.loads((dest / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    hashes = json.loads((dest / "HASHES.json").read_text(encoding="utf-8"))
    if hashes.get("expectedV1Hash") != EXPECTED_SHA256:
        raise RuntimeError("RELEASE_V1_HASH_DRIFT")
    if hashes.get("phase_bc_schema_v2.json") != SCHEMA_V2_EXPECTED_SHA256:
        raise RuntimeError("RELEASE_V2_HASH_DRIFT")
    if manifest.get("learningRevision") != "LR000000":
        raise RuntimeError("RELEASE_LR_DRIFT")
    if manifest.get("predictiveClaim") != "NONE":
        raise RuntimeError("RELEASE_PREDICTIVE_DRIFT")
    return {"ok": True, "manifest": manifest}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build a portable DCM release (no committed ZIP).")
    p.add_argument("--out", type=Path, default=Path("dist/portable"))
    p.add_argument("--workspace", type=Path, default=None)
    args = p.parse_args(argv)
    result = build_portable(args.out, workspace=args.workspace)
    verify_extraction(Path(result["dest"]))
    print(json.dumps({"dest": result["dest"], "software": SOFTWARE, "schemaHash": result["hashes"]["phase_bc_schema_v2.json"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
