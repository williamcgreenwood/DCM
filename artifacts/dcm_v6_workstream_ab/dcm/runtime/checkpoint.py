"""Atomic checkpoint / resume. write temp → fsync → hash → rename."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash


def atomic_write(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    digest = content_hash(payload)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)
    return digest


def load_checkpoint(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    stored = data.get("checkpointHash")
    check = {k: v for k, v in data.items() if k != "checkpointHash"}
    got = content_hash(check)
    if stored and stored != got:
        raise RuntimeError(f"CHECKPOINT_HASH_MISMATCH: {stored} != {got}")
    return data


def write_checkpoint(dest: Path, payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body.pop("checkpointHash", None)
    digest = content_hash(body)
    body["checkpointHash"] = digest
    atomic_write(dest, body)
    return body
