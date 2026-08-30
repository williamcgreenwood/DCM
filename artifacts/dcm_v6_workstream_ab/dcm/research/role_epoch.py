"""RoleEpochBuilder stub.

Partitions host-supplied logs by starter/bench and teammate-out when those
claims exist. Does not invent logs.
"""
from __future__ import annotations

from typing import Any


def _as_logs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _alias_minutes(row: dict[str, Any]) -> dict[str, Any]:
    """Expose Basketball-Reference MP as minutes without rejecting other sports."""
    if row.get("minutes") is not None:
        return row
    for key in ("mp", "MP", "MIN", "min"):
        if key in row and row[key] is not None:
            out = dict(row)
            out["minutes"] = row[key]
            return out
    return row


def partition_logs(
    logs: list[dict[str, Any]],
    *,
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    starter: list[dict[str, Any]] = []
    bench: list[dict[str, Any]] = []
    teammate_out: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []
    for row in logs:
        role = str(row.get("role") or row.get("appearance") or "").strip().lower()
        flag = str(row.get("teammate_out") or row.get("teammateOut") or "").strip().lower()
        if flag in {"1", "true", "yes", "out"} or row.get("teammate_out") is True:
            teammate_out.append(row)
        elif role in {"starter", "starting", "start"}:
            starter.append(row)
        elif role in {"bench", "reserve", "second_unit"}:
            bench.append(row)
        else:
            other.append(row)
    claim_roles = []
    for claim in claims or []:
        value = claim.get("claim_value")
        if isinstance(value, dict) and value.get("role"):
            claim_roles.append(str(value.get("role")))
    return {
        "starter": starter,
        "bench": bench,
        "teammate_out": teammate_out,
        "other": other,
        "claim_roles": claim_roles,
        "invented": False,
    }


class RoleEpochBuilder:
    def build(self, player_claim_value: dict[str, Any], claims: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        logs = [_alias_minutes(r) for r in _as_logs(player_claim_value.get("role_epoch_logs") or player_claim_value.get("game_logs"))]
        parts = partition_logs(logs, claims=claims)
        return {
            "builder": "RoleEpochBuilder.stub",
            "log_count": len(logs),
            "partitions": {k: parts[k] for k in ("starter", "bench", "teammate_out", "other")},
            "claim_roles": parts["claim_roles"],
            "invented": False,
            "note": "Partitions only when starter/bench/teammate-out claims exist. Does not fabricate logs.",
        }
