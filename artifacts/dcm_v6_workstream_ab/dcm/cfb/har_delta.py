"""HAR-delta research reuse. Line-only changes must not reacquire history.

Second HAR of the same slate reuses unchanged historical evidence.
Role changes refresh role-dependent state. Opponent changes refresh
opponent requirements. Team changes refresh team context.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.contracts.hashes import content_hash
from dcm.research.cache_layers import (
    NEW_ENTITY_FULL_RESEARCH,
    NEW_OPPONENT_REQUIRED,
    REFRESH_CURRENT_CONTEXT,
    REUSE_VALID,
    ROLE_EPOCH_CHANGED,
    TEAM_CHANGED,
    ResearchCacheCascade,
)


def _oid(row: Mapping[str, Any]) -> str:
    return str(row.get("projectionId") or "")


def _identity(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("playerId") or ""),
        str(row.get("eventId") or ""),
        str(row.get("teamId") or row.get("team") or ""),
        str(row.get("market") or "").lower(),
    )


def classify_board_delta(
    previous_rows: list[Mapping[str, Any]],
    current_rows: list[Mapping[str, Any]],
    *,
    previous_roles: Mapping[str, str] | None = None,
    current_roles: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    prev_by_id = {_oid(r): dict(r) for r in previous_rows if _oid(r)}
    curr_by_id = {_oid(r): dict(r) for r in current_rows if _oid(r)}
    cascade = ResearchCacheCascade()
    rows: list[dict[str, Any]] = []
    reuse = refresh = new_ent = role = opp = team = 0
    for oid, row in curr_by_id.items():
        prev = prev_by_id.get(oid)
        pid = str(row.get("playerId") or "")
        role_changed = bool(
            previous_roles
            and current_roles
            and pid
            and previous_roles.get(pid) != current_roles.get(pid)
        )
        opponent_changed = False
        team_changed = False
        line_only = False
        if prev is None:
            disp = NEW_ENTITY_FULL_RESEARCH
            new_ent += 1
        else:
            opponent_changed = str(prev.get("opponentId") or prev.get("opponent") or "") != str(
                row.get("opponentId") or row.get("opponent") or ""
            )
            team_changed = str(prev.get("teamId") or prev.get("team") or "") != str(
                row.get("teamId") or row.get("team") or ""
            )
            same_identity = _identity(prev) == _identity(row)
            line_only = same_identity and not opponent_changed and not team_changed and not role_changed and (
                float(prev.get("line") or 0) != float(row.get("line") or 0)
                or str(prev.get("side") or "") != str(row.get("side") or "")
            )
            history_unchanged = same_identity and not role_changed and not team_changed and not opponent_changed
            disp = cascade.disposition(
                existing=prev,
                role_epoch_changed=role_changed,
                team_changed=team_changed,
                opponent_changed=opponent_changed,
                line_only=line_only,
                new_entity=False,
            )
            if disp == REUSE_VALID or (history_unchanged and not line_only):
                disp = REUSE_VALID if not line_only else REFRESH_CURRENT_CONTEXT
            if disp == REUSE_VALID:
                reuse += 1
            elif disp == REFRESH_CURRENT_CONTEXT:
                refresh += 1
            elif disp == ROLE_EPOCH_CHANGED:
                role += 1
            elif disp == NEW_OPPONENT_REQUIRED:
                opp += 1
            elif disp == TEAM_CHANGED:
                team += 1
        rows.append({
            "offer_id": oid,
            "disposition": disp,
            "lineOnly": line_only,
            "roleChanged": role_changed,
            "opponentChanged": opponent_changed,
            "teamChanged": team_changed,
        })
    body = {
        "schema": "pillars_dcm.cfb_har_delta.v1",
        "previousOffers": len(prev_by_id),
        "currentOffers": len(curr_by_id),
        "reuseValid": reuse,
        "refreshCurrentContext": refresh,
        "newEntity": new_ent,
        "roleEpochChanged": role,
        "newOpponentRequired": opp,
        "teamChanged": team,
        "rows": rows,
        "note": "Unchanged historical evidence must not be reacquired. Line-only changes reuse history.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "rows"}})
    return body
