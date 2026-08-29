"""Append-only learning sidecar. Historical forecasts are never rewritten."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dcm.runtime.store import IndexedStore


def append_record(store: IndexedStore, kind: str, cutoff: str, run_id: str, lr: str, payload: dict[str, Any], **keys: Any) -> None:
    if kind not in {"FrozenForecast", "Settlement", "Audit", "PatchProposal", "PromotionDecision"}:
        raise RuntimeError(f"UNKNOWN_LEARNING_KIND: {kind}")
    store.append(kind=kind, cutoff=cutoff, run_id=run_id, lr=lr, payload=payload, **keys)


def mutate_forecast(_path: Path) -> None:
    raise RuntimeError("APPEND_ONLY_LEARNING: historical FrozenForecast records cannot be edited")
