"""Portable release builder.

Releases are built by this module (or scripts/build_portable.py), not by a
committed ZIP blob. A release under dist/ or artifacts/release/ includes an
installable wheel (when build deps are available), COMPLETE_PROJECT_SOURCE.txt,
RELEASE_MANIFEST.json with a required gitCommit, hashes, CAPABILITY.json, and
RUNTIME_PROMPT.md.

The historical artifacts/dcm_v6_workstream_ab.zip is forbidden in git because
ChatGPT can load a stale DCM from it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.runtime.schema_root import EXPECTED_SHA256, SCHEMA_V2_EXPECTED_SHA256, SCHEMA_V2_ID, sha256_file, v2_schema_path
from dcm.sports.common.plugin import CAPABILITIES, PRODUCTION, REGISTRY, RESEARCH, SHADOW, UNSUPPORTED
from dcm.algorithms.constitution import ALGORITHM_CONSTITUTION_VERSION, constitution_sha256
from dcm.algorithms.registry import algorithm_registry_sha256
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE, load_version_manifest, version_json_path

_SKIP_DIR_NAMES = frozenset({"__pycache__", ".pyc", "egg-info", ".egg-info"})
_SKIP_SUFFIXES = frozenset({".pyc", ".pyo", ".so"})
_STATE_LABEL = {
    PRODUCTION: "productionCapable",
    SHADOW: "shadow",
    RESEARCH: "research",
    UNSUPPORTED: "failClosed",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "VERSION.json").is_file() and (parent / "pyproject.toml").is_file():
            return parent
    return here.parents[2] if len(here.parents) > 2 else Path.cwd()


def package_root(workspace: Path) -> Path:
    """Return the Python package discovery root (``src/``), not the archive."""
    src = Path(workspace) / "src"
    if (src / "dcm").is_dir():
        return src
    # Editable/install fallback: parent of this package.
    return Path(__file__).resolve().parents[1]


def count_pytest_functions(tests_root: Path) -> int:
    n = 0
    for path in tests_root.rglob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        n += sum(1 for line in text.splitlines() if line.startswith("def test_"))
    return n


def resolve_git_commit(workspace: Path) -> str:
    """Populate gitCommit from git rev-parse HEAD. FAIL if blank."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("RELEASE_GIT_COMMIT_BLANK") from exc
    sha = (proc.stdout or "").strip()
    if proc.returncode != 0 or not sha:
        raise RuntimeError("RELEASE_GIT_COMMIT_BLANK")
    if any(c not in "0123456789abcdefABCDEF" for c in sha):
        raise RuntimeError("RELEASE_GIT_COMMIT_BLANK")
    return sha


def canonical_package_files(workspace: Path) -> list[tuple[str, Path]]:
    """Ordered (relative, absolute) files of the canonical Python package tree."""
    root = package_root(workspace)
    rows: list[tuple[str, Path]] = []
    for pkg in ("dcm", "pillars_dcm"):
        base = root / pkg
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIR_NAMES or part.endswith(".egg-info") for part in path.parts):
                continue
            if path.suffix in _SKIP_SUFFIXES:
                continue
            rel = path.relative_to(root).as_posix()
            rows.append((rel, path))
    return rows


def build_complete_project_source(workspace: Path) -> tuple[str, str, list[dict[str, str]]]:
    files = canonical_package_files(workspace)
    lines = [
        "# COMPLETE_PROJECT_SOURCE",
        f"# root: {package_root(workspace).as_posix()}",
        f"# fileCount: {len(files)}",
    ]
    entries: list[dict[str, str]] = []
    body_lines: list[str] = []
    for rel, path in files:
        digest = sha256_file(path)
        body_lines.append(f"{digest}  {rel}")
        entries.append({"path": rel, "sha256": digest})
    bundle = _sha256_bytes(("\n".join(body_lines) + "\n").encode("utf-8"))
    lines.extend(body_lines)
    lines.append(f"# bundleSha256: {bundle}")
    lines.append("")
    return "\n".join(lines), bundle, entries


def capability_document() -> dict[str, Any]:
    sports: dict[str, Any] = {}
    for family, manifest in sorted(REGISTRY.items()):
        sports[family] = {
            "productionState": _STATE_LABEL.get(manifest.production_state, manifest.production_state),
            "leagues": list(manifest.leagues),
            "pluginVersion": manifest.plugin_version,
            "pathUnit": manifest.path_unit,
        }
    markets: list[dict[str, str]] = []
    for (family, league, market), state in sorted(CAPABILITIES.items()):
        markets.append(
            {
                "sportFamily": family,
                "league": league,
                "market": market,
                "state": _STATE_LABEL.get(state, state),
            }
        )
    return {
        "document": "PILLARS_DCM_CAPABILITY",
        "software": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "sports": sports,
        "markets": markets,
        "notes": [
            "NBA/WNBA/NFL/CFB productionCapable in software; MLB shadow; soccer/EPL/KBO/NPB/CFL/OTD failClosed after accounting.",
            "productionCapable is a software path, not a certified production selector.",
            "LR000000 / predictive NONE. Not optimized DCM 6.0. Host performance is not certified.",
        ],
    }


def _ensure_build_deps() -> None:
    missing: list[str] = []
    for mod, pkg in (("build", "build"), ("setuptools", "setuptools")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", *missing],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"RELEASE_BUILD_DEPS_MISSING:{','.join(missing)}")


def build_wheel(workspace: Path, dest: Path) -> dict[str, Any]:
    """Build an installable pillars-dcm wheel into dest (and dest/../dist if present)."""
    info: dict[str, Any] = {"built": False, "path": None, "error": None}
    try:
        _ensure_build_deps()
    except RuntimeError as exc:
        info["error"] = str(exc)
        return info
    dest.mkdir(parents=True, exist_ok=True)
    outdir = dest / "wheelhouse"
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(outdir)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        info["error"] = f"RELEASE_WHEEL_SPAWN_FAILED:{type(exc).__name__}"
        return info
    wheels = sorted(outdir.glob("*.whl"))
    if proc.returncode != 0 or not wheels:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        info["error"] = (err[-1] if err else "RELEASE_WHEEL_BUILD_FAILED")[:400]
        return info
    wheel = wheels[-1]
    target = dest / wheel.name
    if wheel.resolve() != target.resolve():
        target.write_bytes(wheel.read_bytes())
    dist = workspace / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    dist_copy = dist / wheel.name
    if dist_copy.resolve() != target.resolve():
        dist_copy.write_bytes(target.read_bytes())
    info["built"] = True
    info["path"] = str(target)
    info["sha256"] = sha256_file(target)
    info["filename"] = target.name
    return info


def build_portable(
    dest: Path,
    *,
    workspace: Path | None = None,
    build_wheel_artifact: bool = True,
) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    root = workspace or repo_root()
    git_commit = resolve_git_commit(root)
    manifest = load_version_manifest()
    version_path = version_json_path()
    schema_path = v2_schema_path(root)
    if schema_path is None:
        raise FileNotFoundError("V2_SCHEMA_MISSING")
    version_hash = sha256_file(version_path)
    schema_hash = sha256_file(schema_path)
    tests_root = repo_root() / "tests"
    test_count = count_pytest_functions(tests_root)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_text, bundle_sha, source_entries = build_complete_project_source(root)
    (dest / "COMPLETE_PROJECT_SOURCE.txt").write_text(source_text, encoding="utf-8")
    capability = capability_document()
    (dest / "CAPABILITY.json").write_text(
        json.dumps(capability, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    wheel_info: dict[str, Any] = {"built": False, "path": None, "error": "skipped"}
    if build_wheel_artifact:
        wheel_info = build_wheel(root, dest)
    release = {
        "document": "PILLARS_DCM_RELEASE_MANIFEST",
        "software": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "optimizedDcm60Claim": False,
        "hostPerformanceCertified": False,
        "gitCommit": git_commit,
        "algorithmConstitutionVersion": ALGORITHM_CONSTITUTION_VERSION,
        "algorithmConstitutionSha256": constitution_sha256(),
        "algorithmRegistrySha256": algorithm_registry_sha256(),
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
        "completeProjectSourceFileCount": len(source_entries),
        "completeProjectSourceBundleSha256": bundle_sha,
        "wheelBuilt": bool(wheel_info.get("built")),
        "wheelFilename": wheel_info.get("filename"),
        "wheelSha256": wheel_info.get("sha256"),
        "wheelError": wheel_info.get("error"),
        "cleanEnvInstall": (
            "python -m dcm.release --out artifacts/release && "
            "python -m venv /tmp/dcm-rel && "
            "/tmp/dcm-rel/bin/pip install artifacts/release/*.whl && "
            "cd /tmp && /tmp/dcm-rel/bin/python -m dcm --help"
        ),
    }
    if not str(release.get("gitCommit") or "").strip():
        raise RuntimeError("RELEASE_GIT_COMMIT_BLANK")
    release["contentHash"] = _sha256_bytes(
        json.dumps({k: v for k, v in release.items() if k != "contentHash"}, sort_keys=True, separators=(",", ":")).encode()
    )
    (dest / "RELEASE_MANIFEST.json").write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    install_lines = [
        f"{version_hash}  VERSION.json",
        f"{schema_hash}  phase_bc_schema_v2.json",
        f"{EXPECTED_SHA256}  PHASE_BC_SCHEMA_V1_expected (bytes absent)",
        f"{bundle_sha}  COMPLETE_PROJECT_SOURCE.txt bundleSha256",
        f"{release['contentHash']}  RELEASE_MANIFEST.json contentHash",
    ]
    if wheel_info.get("sha256") and wheel_info.get("filename"):
        install_lines.append(f"{wheel_info['sha256']}  {wheel_info['filename']}")
    install_text = "\n".join(install_lines) + "\n"
    (dest / "INSTALL_SHA256").write_text(install_text, encoding="utf-8")
    (dest / "INSTALL_SHA256.txt").write_text(install_text, encoding="utf-8")
    prompt = f"""# Pillars DCM portable runtime prompt

Software: {SOFTWARE}
Learning revision: {LEARNING_REVISION}
Predictive claim: {PREDICTIVE_CLAIM}
gitCommit: {git_commit}

This is not optimized DCM 6.0. Host performance is not certified.
Python is the single canonical engine. TypeScript is a viewer only.

Locked pathway: HAR → research population → EvidenceGraph → ParameterSnapshots →
EventWorlds → probabilities → grading → ranking → 0–6 PLAYABLE card → freeze.

Build a portable package (wheel + hashes) from the repo root:

    python -m dcm.release --out artifacts/release
    python -m pillars_dcm.release --out artifacts/release
    python scripts/build_portable.py --out artifacts/release

Install the wheel in a clean environment (no repo on PYTHONPATH):

    python -m venv /tmp/dcm-rel && source /tmp/dcm-rel/bin/activate
    pip install artifacts/release/*.whl
    python -m dcm --help
    python -m dcm --synthetic --research fixture --cutoff-from-capture --account-only --out /tmp/dcm-rel-run

Never load artifacts/dcm_v6_workstream_ab.zip — that blob is not a release
channel. Cutoff is required (--cutoff or --cutoff-from-capture). --version must
match VERSION.json software or softwareShort.

Settle a frozen run (outcomes are supplied; never invented):

    python -m dcm.settle --dest RUNS/<id> --outcomes outcomes.json
"""
    (dest / "RUNTIME_PROMPT.md").write_text(prompt, encoding="utf-8")
    hashes = {
        "VERSION.json": version_hash,
        "phase_bc_schema_v2.json": schema_hash,
        "expectedV1Hash": EXPECTED_SHA256,
        "RELEASE_MANIFEST.contentHash": release["contentHash"],
        "COMPLETE_PROJECT_SOURCE.bundleSha256": bundle_sha,
        "gitCommit": git_commit,
        "algorithmConstitutionVersion": ALGORITHM_CONSTITUTION_VERSION,
        "algorithmConstitutionSha256": constitution_sha256(),
        "algorithmRegistrySha256": algorithm_registry_sha256(),
        "wheelSha256": wheel_info.get("sha256"),
    }
    (dest / "HASHES.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"dest": str(dest), "manifest": release, "hashes": hashes, "wheel": wheel_info, "sourceEntries": source_entries}


def verify_extraction(dest: Path) -> dict[str, Any]:
    dest = Path(dest)
    required = [
        "RELEASE_MANIFEST.json",
        "INSTALL_SHA256",
        "INSTALL_SHA256.txt",
        "RUNTIME_PROMPT.md",
        "HASHES.json",
        "CAPABILITY.json",
        "COMPLETE_PROJECT_SOURCE.txt",
    ]
    missing = [name for name in required if not (dest / name).is_file()]
    if missing:
        raise RuntimeError(f"RELEASE_EXTRACTION_MISSING:{','.join(missing)}")
    manifest = json.loads((dest / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    hashes = json.loads((dest / "HASHES.json").read_text(encoding="utf-8"))
    if not str(manifest.get("gitCommit") or "").strip():
        raise RuntimeError("RELEASE_GIT_COMMIT_BLANK")
    if hashes.get("gitCommit") != manifest.get("gitCommit"):
        raise RuntimeError("RELEASE_GIT_COMMIT_HASH_MISMATCH")
    if hashes.get("expectedV1Hash") != EXPECTED_SHA256:
        raise RuntimeError("RELEASE_V1_HASH_DRIFT")
    if hashes.get("phase_bc_schema_v2.json") != SCHEMA_V2_EXPECTED_SHA256:
        raise RuntimeError("RELEASE_V2_HASH_DRIFT")
    if manifest.get("learningRevision") != "LR000000":
        raise RuntimeError("RELEASE_LR_DRIFT")
    if manifest.get("predictiveClaim") != "NONE":
        raise RuntimeError("RELEASE_PREDICTIVE_DRIFT")
    cap = json.loads((dest / "CAPABILITY.json").read_text(encoding="utf-8"))
    if "sports" not in cap or "markets" not in cap:
        raise RuntimeError("RELEASE_CAPABILITY_INCOMPLETE")
    return {"ok": True, "manifest": manifest}


def verify_complete_project_source(dest: Path, workspace: Path, *, sample: int = 8) -> dict[str, Any]:
    dest = Path(dest)
    text = (dest / "COMPLETE_PROJECT_SOURCE.txt").read_text(encoding="utf-8")
    listed: list[tuple[str, str]] = []
    bundle = ""
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("# bundleSha256:"):
            bundle = line.split(":", 1)[1].strip()
        elif line and not line.startswith("#"):
            digest, sep, rel = line.partition("  ")
            if not sep:
                continue
            listed.append((rel, digest))
            body.append(line)
    recomputed = _sha256_bytes(("\n".join(body) + "\n").encode("utf-8"))
    if bundle != recomputed:
        raise RuntimeError("COMPLETE_PROJECT_SOURCE_BUNDLE_MISMATCH")
    root = package_root(workspace)
    checked = 0
    for rel, digest in listed[: max(sample, 0)] if sample else listed:
        path = root / rel
        if not path.is_file():
            raise RuntimeError(f"COMPLETE_PROJECT_SOURCE_MISSING:{rel}")
        if sha256_file(path) != digest:
            raise RuntimeError(f"COMPLETE_PROJECT_SOURCE_HASH_MISMATCH:{rel}")
        checked += 1
    return {"ok": True, "fileCount": len(listed), "checked": checked, "bundleSha256": bundle}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build a portable DCM release (no committed ZIP).")
    p.add_argument("--out", type=Path, default=Path("artifacts/release"))
    p.add_argument("--workspace", type=Path, default=None)
    p.add_argument("--no-wheel", action="store_true", help="Skip python -m build (still emit hashes + source list).")
    args = p.parse_args(argv)
    result = build_portable(
        args.out,
        workspace=args.workspace,
        build_wheel_artifact=not bool(args.no_wheel),
    )
    verify_extraction(Path(result["dest"]))
    print(
        json.dumps(
            {
                "dest": result["dest"],
                "software": SOFTWARE,
                "gitCommit": result["manifest"]["gitCommit"],
                "schemaHash": result["hashes"]["phase_bc_schema_v2.json"],
                "wheelBuilt": result["wheel"].get("built"),
                "wheel": result["wheel"].get("filename"),
                "completeProjectSourceBundleSha256": result["manifest"]["completeProjectSourceBundleSha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
