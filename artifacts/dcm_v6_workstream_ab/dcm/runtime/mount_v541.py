"""Exact v5.4.1 root-of-trust mount and bundle reconstruction."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable

EXPECTED_SOURCE = "bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474"
EXPECTED_LEDGER = "a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a"
SOURCE_NAMES = ("Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt", "Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.TXT")
LEDGER_NAMES = ("Pillars_DCM_v5.4.1_Learning_Ledger.xlsx", "Pillars_DCM_v5.4.1_Learning_Ledger.XLSX")
INSTALL_NAMES = ("Pillars_DCM_v5.4.1_INSTALL_SHA256.txt", "Pillars_DCM_v5.4.1_INSTALL_SHA256.TXT")
BLOCK = re.compile(
    rb"^BEGIN EMBEDDED FILE ([0-9]{3}): ([^\r\n]+)\r?\n"
    rb"CONTENT_BYTES: ([0-9]+)\r?\n"
    rb"CONTENT_SHA256: ([0-9a-f]{64})\r?\n"
    rb"={96}\r?\n",
    re.MULTILINE,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_named(names: Iterable[str], roots: Iterable[Path]) -> Path | None:
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.name in names:
            return root
        if root.is_dir():
            for name in names:
                candidate = root / name
                if candidate.is_file():
                    return candidate
    return None


def _safe_path(raw: str) -> PurePosixPath:
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or any(p in {"", ".", ".."} for p in path.parts) or "\\" in raw:
        raise ValueError(f"unsafe embedded path:{raw}")
    return path


def extract_verified_bundle(source: Path, target: Path) -> dict:
    raw = source.read_bytes()
    rows = []
    seqs = []
    for match in BLOCK.finditer(raw):
        seq = int(match.group(1))
        rel = _safe_path(match.group(2).decode("utf-8"))
        size = int(match.group(3))
        expected = match.group(4).decode("ascii")
        content = raw[match.end():match.end() + size]
        if len(content) != size or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"embedded hash mismatch:{rel}")
        rows.append((rel, content))
        seqs.append(seq)
    if not rows or seqs != list(range(1, len(rows) + 1)):
        raise ValueError("canonical bundle sequence invalid")
    target.mkdir(parents=True, exist_ok=True)
    resolved = target.resolve()
    for rel, content in rows:
        dest = target.joinpath(*rel.parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if resolved not in dest.resolve().parents:
            raise ValueError("embedded path escaped mount")
        dest.write_bytes(content)
    return {
        "embedded_files": len(rows),
        "tree_inventory_sha256": hashlib.sha256("\n".join(str(r[0]) for r in rows).encode()).hexdigest(),
    }


def _manifest_ok(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        EXPECTED_SOURCE in text and EXPECTED_LEDGER in text
        and "Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt" in text
        and "Pillars_DCM_v5.4.1_Learning_Ledger.xlsx" in text
    )


def attempt_mount(
    *, dest: Path, source: Path | None, ledger: Path | None, manifest: Path | None = None,
    expected_source: str = EXPECTED_SOURCE, expected_ledger: str = EXPECTED_LEDGER,
    require_complete: bool = False,
) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    state = {
        "expected_source_sha256": expected_source, "expected_ledger_sha256": expected_ledger,
        "observed_source_sha256": None, "observed_ledger_sha256": None,
        "source_path": str(source) if source else None, "ledger_path": str(ledger) if ledger else None,
        "manifest_path": str(manifest) if manifest else None, "copy_path": str(dest),
        "state": "ABSENT_IN_THIS_WORKSPACE", "har_decoder": "NOT_MOUNTED",
        "copied": False, "extracted": False, "canonical_tree": None,
        "note": "Canonical v5.4.1 not fully mounted.",
    }
    if source is None and ledger is None and manifest is None:
        return state
    src_ok = source is not None and source.is_file() and sha256_file(source) == expected_source
    led_ok = ledger is not None and ledger.is_file() and sha256_file(ledger) == expected_ledger
    if source is not None and source.is_file():
        state["observed_source_sha256"] = sha256_file(source)
    if ledger is not None and ledger.is_file():
        state["observed_ledger_sha256"] = sha256_file(ledger)
    if source is not None and not src_ok:
        state["state"] = "HASH_MISMATCH"; state["note"] = "Source SHA-256 mismatch; copy refused."; return state
    if ledger is not None and not led_ok:
        state["state"] = "HASH_MISMATCH"; state["note"] = "Ledger SHA-256 mismatch; copy refused."; return state

    manifest_ok = _manifest_ok(manifest)
    if require_complete and not (src_ok and led_ok and manifest_ok):
        state["state"] = "PARTIAL_CANONICAL_INPUT"
        state["note"] = "Exact source + ledger + install manifest are required."
        return state

    if src_ok:
        shutil.copy2(source, dest / SOURCE_NAMES[0]); state["copied"] = True
    if led_ok:
        shutil.copy2(ledger, dest / LEDGER_NAMES[0]); state["copied"] = True
    if manifest_ok and manifest is not None:
        shutil.copy2(manifest, dest / INSTALL_NAMES[0]); state["copied"] = True

    if src_ok:
        tree = dest / "tree"
        try:
            info = extract_verified_bundle(source, tree)
        except ValueError:
            if require_complete:
                state["state"] = "INVALID_CANONICAL_BUNDLE"
                state["note"] = "Source hash matched but embedded-file verification failed."
                return state
        else:
            state.update(info)
            state["extracted"] = True
            state["canonical_tree"] = str(tree)

    if src_ok and (led_ok or not require_complete):
        state["state"] = "HASH_VERIFIED_EXTRACTED" if state["extracted"] else "HASH_VERIFIED"
        state["har_decoder"] = "V5_CANONICAL_TREE_AVAILABLE" if state["extracted"] else "V5_COPY_MOUNTED"
        state["note"] = "Exact canonical bytes mounted. LR remains LR000000 pending chronological promotion."
    return state


def write_mount_state(state: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


DEFAULT_WORKSPACE = Path(__file__).resolve().parents[4]

def _usable_workspace(requested: Path) -> Path:
    if requested.exists():
        return requested
    try:
        requested.mkdir(parents=True, exist_ok=True)
        return requested
    except (OSError, PermissionError):
        return DEFAULT_WORKSPACE

def mount_default(workspace: Path = DEFAULT_WORKSPACE) -> dict:
    workspace = _usable_workspace(workspace)
    dest = workspace / "dcm_v6" / "canonical_mount" / "v5.4.1_copy"
    env_source = Path(os.environ["DCM_V541_SOURCE"]) if os.environ.get("DCM_V541_SOURCE") else None
    env_ledger = Path(os.environ["DCM_V541_LEDGER"]) if os.environ.get("DCM_V541_LEDGER") else None
    env_manifest = Path(os.environ["DCM_V541_MANIFEST"]) if os.environ.get("DCM_V541_MANIFEST") else None
    roots = (
        workspace / "dcm_v6" / "INBOX", workspace / "INBOX", workspace / "attachments",
        workspace / "artifacts" / "canonical", workspace / "canonical", Path("/mnt/data"), workspace,
    )
    source = env_source if env_source and env_source.is_file() else find_named(SOURCE_NAMES, roots)
    ledger = env_ledger if env_ledger and env_ledger.is_file() else find_named(LEDGER_NAMES, roots)
    manifest = env_manifest if env_manifest and env_manifest.is_file() else find_named(INSTALL_NAMES, roots)
    state = attempt_mount(dest=dest, source=source, ledger=ledger, manifest=manifest, require_complete=True)
    write_mount_state(state, workspace / "dcm_v6" / "canonical_mount" / "MOUNT_STATE.json")
    return state


def main(argv: list[str] | None = None) -> int:
    del argv
    state = mount_default()
    print(json.dumps({k: state.get(k) for k in (
        "state", "har_decoder", "copied", "extracted",
        "observed_source_sha256", "observed_ledger_sha256", "embedded_files",
    )}, indent=2))
    return 0 if state["state"] in {"HASH_VERIFIED_EXTRACTED", "ABSENT_IN_THIS_WORKSPACE", "PARTIAL_CANONICAL_INPUT"} else 2


if __name__ == "__main__":
    sys.exit(main())
