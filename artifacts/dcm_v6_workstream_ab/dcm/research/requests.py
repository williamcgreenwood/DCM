"""Hierarchical research requests: SPORT → EVENT → TEAM → PLAYER → MARKET. Compute once."""

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

    for r in rows:
        if r.get("modifier") == "GOBLIN":
            continue
        add(
            "MARKET",
            r["projectionId"],
            "definition_line_history",
            {"market": r.get("market"), "line": r.get("line"), "playerId": r.get("playerId")},
        )
    return list(reqs.values())
