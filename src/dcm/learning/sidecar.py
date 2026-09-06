"""Append-only learning sidecar. Historical forecasts are never rewritten."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dcm.runtime.store import IndexedStore

LEDGER_KINDS = frozenset(
    {"FrozenForecast", "Settlement", "Audit", "PatchProposal", "PromotionDecision"}
)
LEDGER_FILENAME = "learning_ledger.jsonl"


def _require_kind(kind: str) -> str:
    if kind not in LEDGER_KINDS:
        raise RuntimeError(f"UNKNOWN_LEARNING_KIND: {kind}")
    return kind


def append_record(store: IndexedStore, kind: str, cutoff: str, run_id: str, lr: str, payload: dict[str, Any], **keys: Any) -> None:
    _require_kind(kind)
    store.append(kind=kind, cutoff=cutoff, run_id=run_id, lr=lr, payload=payload, **keys)


def append_ledger_jsonl(
    dest: Path,
    kind: str,
    payload: dict[str, Any],
    *,
    cutoff: str = "",
    run_id: str = "",
    lr: str = "",
    source_hash: str | None = None,
    projection_id: str | None = None,
) -> None:
    """Append one immutable JSONL record. Never rewrites prior lines."""
    _require_kind(kind)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    rec: dict[str, Any] = {
        "kind": kind,
        "cutoff": cutoff,
        "runId": run_id,
        "learningRevision": lr,
        "sourceHash": source_hash,
        "projectionId": projection_id,
        "payload": payload,
    }
    path = dest / LEDGER_FILENAME
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")


def read_ledger_jsonl(dest: Path) -> list[dict[str, Any]]:
    path = Path(dest) / LEDGER_FILENAME
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def mutate_forecast(_path: Path) -> None:
    raise RuntimeError("APPEND_ONLY_LEARNING: historical FrozenForecast records cannot be edited")
