"""Copy-forward canonical v5.4.1 only after SHA-256 match. Never invent bytes."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Iterable

EXPECTED_SOURCE = "bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474"
EXPECTED_LEDGER = "a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a"

SOURCE_NAMES = (
    "Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt",
    "Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.TXT",
)
LEDGER_NAMES = (
    "Pillars_DCM_v5.4.1_Learning_Ledger.xlsx",
    "Pillars_DCM_v5.4.1_Learning_Ledger.XLSX",
)

SEARCH_ROOTS = (
    Path("/workspace/dcm_v6/INBOX"),
    Path("/workspace/INBOX"),
    Path("/workspace/attachments"),
    Path("/workspace/artifacts/canonical"),
    Path("/workspace/canonical"),
    Path("/workspace"),
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
                cand = root / name
                if cand.is_file():
                    return cand
    return None


def attempt_mount(
    *,
    dest: Path,
    source: Path | None,
    ledger: Path | None,
    expected_source: str = EXPECTED_SOURCE,
    expected_ledger: str = EXPECTED_LEDGER,
) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    state = {
        "expected_source_sha256": expected_source,
        "expected_ledger_sha256": expected_ledger,
        "observed_source_sha256": None,
        "observed_ledger_sha256": None,
        "source_path": str(source) if source else None,
        "ledger_path": str(ledger) if ledger else None,
        "copy_path": str(dest),
        "state": "ABSENT_IN_THIS_WORKSPACE",
        "har_decoder": "NOT_MOUNTED",
        "copied": False,
        "note": "Canonical v5.4.1 bytes were not present or did not match. Development HAR adapter is v6-new, not a verified v5 decoder.",
    }
    if source is None and ledger is None:
        return state

    src_ok = False
    led_ok = False
    if source is not None and source.is_file():
        digest = sha256_file(source)
        state["observed_source_sha256"] = digest
        src_ok = digest == expected_source
        if not src_ok:
            state["state"] = "HASH_MISMATCH"
            state["note"] = "Source present but SHA-256 does not match expected v5.4.1. Copy refused."
            return state
    if ledger is not None and ledger.is_file():
        digest = sha256_file(ledger)
        state["observed_ledger_sha256"] = digest
        led_ok = digest == expected_ledger
        if not led_ok:
            state["state"] = "HASH_MISMATCH"
            state["note"] = "Ledger present but SHA-256 does not match expected v5.4.1. Copy refused."
            return state

    if src_ok:
        shutil.copy2(source, dest / source.name)
        state["copied"] = True
    if led_ok:
        shutil.copy2(ledger, dest / ledger.name)
        state["copied"] = True

    if src_ok and (ledger is None or led_ok):
        state["state"] = "HASH_VERIFIED"
        state["har_decoder"] = "V5_COPY_MOUNTED_DECODER_STILL_UNWIRED"
        state["note"] = "Hash-verified copy mounted. Do not treat this as an optimized DCM 6.0 or LR promotion."
    elif not src_ok:
        state["state"] = "ABSENT_IN_THIS_WORKSPACE"
    return state


def write_mount_state(state: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def mount_default(workspace: Path = Path("/workspace")) -> dict:
    dest = workspace / "dcm_v6" / "canonical_mount" / "v5.4.1_copy"
    roots = (
        workspace / "dcm_v6" / "INBOX",
        workspace / "INBOX",
        workspace / "attachments",
        workspace / "artifacts" / "canonical",
        workspace / "canonical",
        workspace,
    )
    source = find_named(SOURCE_NAMES, roots)
    ledger = find_named(LEDGER_NAMES, roots)
    state = attempt_mount(dest=dest, source=source, ledger=ledger)
    write_mount_state(state, workspace / "dcm_v6" / "canonical_mount" / "MOUNT_STATE.json")
    return state


def main(argv: list[str] | None = None) -> int:
    del argv
    state = mount_default()
    print(json.dumps({k: state[k] for k in ("state", "har_decoder", "copied", "observed_source_sha256")}, indent=2))
    return 0 if state["state"] in {"HASH_VERIFIED", "ABSENT_IN_THIS_WORKSPACE"} else 2


if __name__ == "__main__":
    sys.exit(main())
