"""Canonical hashing and lineage enforcement."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Iterable, Mapping

from dcm.contracts.codes import FailureCode


LINEAGE_STAGES = (
    "evidence_graph_hash",
    "parameter_snapshot_hash",
    "event_world_set_hash",
    "primitive_ledger_hash",
    "market_definition_hash",
    "world_projection_hash",
    "entry_contract_hash",
    "settlement_rule_hash",
    "world_lineup_outcome_hash",
)


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Mapping):
        return {str(k): _normalize(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if hasattr(value, "__dict__") and hasattr(value, "__dataclass_fields__"):
        payload = {}
        for name in value.__dataclass_fields__:
            if name in {"content_hash", "created_at_utc"}:
                continue
            payload[name] = _normalize(getattr(value, name))
        return payload
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_lineage(populated: Mapping[str, str], *, through: str) -> None:
    """Raise if any stage before `through` is missing or if a later stage is set without earlier ones."""
    if through not in LINEAGE_STAGES:
        raise ValueError(f"unknown lineage stage: {through}")
    target_idx = LINEAGE_STAGES.index(through)
    for i, stage in enumerate(LINEAGE_STAGES):
        present = bool(populated.get(stage))
        if i <= target_idx and not present:
            raise LineageError(FailureCode.LINEAGE_STAGE_SKIPPED, f"missing required stage {stage}")
        if i > target_idx and present:
            # downstream hashes may exist on a completed object; allowed only after through
            continue


class LineageError(RuntimeError):
    def __init__(self, code: FailureCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


def bind_source_hashes(parts: Iterable[str]) -> tuple[str, ...]:
    return tuple(parts)
