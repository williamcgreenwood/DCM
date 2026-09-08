"""Host session filesystem helpers. No model logic lives here."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.chat.contracts import HOST_STATE_SCHEMA
from dcm.contracts.hashes import content_hash


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    try:
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError:
        pass


def default_host_state(dest: Path, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": HOST_STATE_SCHEMA,
        "runDest": str(dest),
        "preparedAt": utc_now(),
        "coverageEvaluated": False,
        "forecastFrozen": False,
        "researchLoopCount": 0,
        "lastCommand": None,
        "probabilityEngine": "python-dcm",
        "hostComputesProbabilities": False,
    }
    if extra:
        body.update(extra)
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
