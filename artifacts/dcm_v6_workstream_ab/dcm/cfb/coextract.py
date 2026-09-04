"""Multi-entity co-extraction. One game/team source populates every board entity.

No one-prop-one-search. A single gamebook/event page may satisfy Event,
Team A, Team B, QB, RB, WR, TE, opponent context, team totals, and
individual stat lines visible on that page.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.contracts.hashes import content_hash

BOARD_ONLY = "BOARD_ONLY"
BOARD_PLUS_COUNTERPARTS = "BOARD_PLUS_COUNTERPARTS"
BOARD_PLUS_FREE_PAGE_ROWS = "BOARD_PLUS_FREE_PAGE_ROWS"
FULL_STRUCTURED_PAGE_WHEN_CHEAP = "FULL_STRUCTURED_PAGE_WHEN_CHEAP"

HARVEST_POLICIES = (
    BOARD_ONLY,
    BOARD_PLUS_COUNTERPARTS,
    BOARD_PLUS_FREE_PAGE_ROWS,
    FULL_STRUCTURED_PAGE_WHEN_CHEAP,
)


def _board_ids(rows: list[Mapping[str, Any]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {
        "events": set(),
        "teams": set(),
        "subjects": set(),
        "offers": set(),
    }
    for row in rows:
        if str(row.get("league") or "").upper() != "CFB":
            continue
        if row.get("eventId"):
            out["events"].add(str(row["eventId"]))
        if row.get("teamId") or row.get("team"):
            out["teams"].add(str(row.get("teamId") or row.get("team")))
        if row.get("opponentId") or row.get("opponent"):
            out["teams"].add(str(row.get("opponentId") or row.get("opponent")))
        if row.get("playerId"):
            out["subjects"].add(str(row["playerId"]))
        if row.get("projectionId"):
            out["offers"].add(str(row["projectionId"]))
    return out


def harvest_structured_page(
    page: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    policy: str = BOARD_PLUS_FREE_PAGE_ROWS,
) -> dict[str, Any]:
    """Extract every relevant board entity visible in one structured page.

    `page` is already-fetched structured content (gamebook / event / team page),
    never live HTML. The host supplies observations; this function only fans
    them out onto board entities.
    """
    if policy not in HARVEST_POLICIES:
        raise ValueError(f"UNKNOWN_HARVEST_POLICY:{policy}")
    board = _board_ids(rows)
    event_id = str(page.get("eventId") or page.get("event_id") or "")
    teams = [str(t) for t in (page.get("teams") or []) if t]
    players = page.get("players") or page.get("stat_lines") or []
    if isinstance(players, Mapping):
        players = [{"playerId": k, **(v if isinstance(v, dict) else {})} for k, v in players.items()]
    claims: list[dict[str, Any]] = []
    if event_id and (policy != BOARD_ONLY or event_id in board["events"]):
        claims.append({
            "semantic_scope": "EVENT",
            "scope_id": event_id,
            "claim_type": "event_context",
            "claim_value": {k: v for k, v in page.items() if k not in {"players", "stat_lines", "teams"}},
        })
    for team in teams:
        on_board = team in board["teams"]
        counterpart = bool(board["teams"]) and not on_board
        if on_board or (counterpart and policy in {BOARD_PLUS_COUNTERPARTS, BOARD_PLUS_FREE_PAGE_ROWS, FULL_STRUCTURED_PAGE_WHEN_CHEAP}):
            claims.append({
                "semantic_scope": "AFFILIATION" if on_board else "COUNTERPARTY",
                "scope_id": team,
                "claim_type": "team_context",
                "claim_value": {"team_context": True, "eventId": event_id},
            })
    extracted_subjects = 0
    free_rows = 0
    for rec in players:
        if not isinstance(rec, Mapping):
            continue
        pid = str(rec.get("playerId") or rec.get("id") or "")
        if not pid:
            continue
        if pid in board["subjects"]:
            claims.append({
                "semantic_scope": "SUBJECT",
                "scope_id": pid,
                "claim_type": "game_line",
                "claim_value": dict(rec),
            })
            extracted_subjects += 1
        elif policy in {BOARD_PLUS_FREE_PAGE_ROWS, FULL_STRUCTURED_PAGE_WHEN_CHEAP}:
            claims.append({
                "semantic_scope": "SUBJECT",
                "scope_id": pid,
                "claim_type": "free_page_row",
                "claim_value": dict(rec),
            })
            free_rows += 1

    unique_scopes = sorted({(c["semantic_scope"], c["scope_id"]) for c in claims})
    offers = max(1, len(board["offers"]))
    scopes = max(1, len(unique_scopes))
    body = {
        "schema": "pillars_dcm.cfb_coextraction.v1",
        "policy": policy,
        "eventId": event_id,
        "claimCount": len(claims),
        "uniqueScopeCount": len(unique_scopes),
        "boardSubjectHits": extracted_subjects,
        "freePageRows": free_rows,
        "boardOfferCount": len(board["offers"]),
        "compressionRatio": round(offers / 1.0, 4),
        "fanout": len(unique_scopes),
        "claims": claims,
        "note": "One AcquisitionAction / page harvest must satisfy many requirements when shared evidence exists.",
    }
    body["offersPerAction"] = len(board["offers"])
    body["scopesPerPage"] = scopes
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "claims"}})
    return body


def fanout_acceptance(actions: Mapping[str, Any], requirements: list[Mapping[str, Any]]) -> dict[str, Any]:
    """executed AcquisitionActions << independent unresolved prop requirements."""
    action_n = int(actions.get("actionCount") or 0)
    req_n = len(requirements)
    fanouts = [int(a.get("dependentOfferCount") or 0) for a in (actions.get("actions") or [])]
    max_fanout = max(fanouts) if fanouts else 0
    avg_fanout = (sum(fanouts) / len(fanouts)) if fanouts else 0.0
    body = {
        "schema": "pillars_dcm.cfb_fanout_acceptance.v1",
        "actions": action_n,
        "requirements": req_n,
        "maxFanout": max_fanout,
        "avgFanout": avg_fanout,
        "onePropOneSearch": bool(action_n >= req_n and req_n > 1 and max_fanout <= 1),
        "accepted": action_n < req_n or max_fanout > 1 or req_n <= 1,
    }
    body["contentHash"] = content_hash(body)
    return body
