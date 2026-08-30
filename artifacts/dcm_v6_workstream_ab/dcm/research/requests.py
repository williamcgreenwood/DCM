"""Hierarchical research requests: SPORT → EVENT → TEAM → PLAYER → MARKET_DEFINITION / OFFER.

MARKET_DEFINITION is reusable across projections that share platform+league+market+board.
OFFER is projection-specific (line, sides, modifier). MARKET remains as a
compatibility alias keyed by projection for older evidence files.
"""

from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash


def build_requests(rows: list[dict], cutoff: str) -> list[dict]:
    reqs: dict[str, dict] = {}

    def add(scope: str, scope_id: str, need: str, extra: dict[str, Any] | None = None) -> None:
        rec = {
            "scope": scope,
            "scope_id": scope_id,
            "need": need,
            "forecast_cutoff": cutoff,
            **(extra or {}),
        }
        rec["request_id"] = "REQ_" + content_hash(rec)[:16]
        reqs[rec["request_id"]] = rec

    sports = {(r.get("sportFamily"), r.get("league")) for r in rows}
    for family, league in sports:
        add("SPORT", f"{family}:{league}", "rules_calendar_distribution", {"league": league})

    for event_id in {r.get("eventId") for r in rows}:
        sample = next(r for r in rows if r.get("eventId") == event_id)
        add(
            "EVENT",
            event_id,
            "start_venue_starters_environment",
            {"league": sample.get("league"), "label": sample.get("eventLabel")},
        )

    for team in {r.get("teamId") for r in rows}:
        sample = next(r for r in rows if r.get("teamId") == team)
        add("TEAM", team, "role_pace_matchup", {"league": sample.get("league")})

    for player_id in {r.get("playerId") for r in rows}:
        sample = next(r for r in rows if r.get("playerId") == player_id)
        add(
            "PLAYER",
            player_id,
            "status_role_logs_opportunity_efficiency",
            {"name": sample.get("playerName"), "league": sample.get("league")},
        )

    seen_defs: set[str] = set()
    for r in rows:
        if r.get("modifier") == "GOBLIN":
            continue
        def_id = "|".join(
            [
                "prizepicks",
                str(r.get("league") or ""),
                str(r.get("market") or ""),
                str(r.get("boardId") or "FULL_GAME"),
            ]
        )
        if def_id not in seen_defs:
            seen_defs.add(def_id)
            add(
                "MARKET_DEFINITION",
                def_id,
                "exact_stat_definition",
                {"market": r.get("market"), "league": r.get("league"), "boardId": r.get("boardId")},
            )
        add(
            "OFFER",
            r["projectionId"],
            "line_sides_modifier",
            {
                "market": r.get("market"),
                "line": r.get("line"),
                "playerId": r.get("playerId"),
                "definition_id": def_id,
            },
        )
        # Compatibility MARKET request (same id as pre-split) so existing FileProvider
        # evidence keyed by projection still attaches.
        add(
            "MARKET",
            r["projectionId"],
            "definition_line_history",
            {"market": r.get("market"), "line": r.get("line"), "playerId": r.get("playerId")},
        )
    return list(reqs.values())
