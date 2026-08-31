"""Team / opponent / event research packets.

One team is researched once and reused for every player on that team AND as
the opponent packet for the other side. Opponent is TEAM-scoped (no new
OPPONENT research subject). Event is researched once per eventId.

Generic fixture pace_multiplier=1.0 is a labeled prior, never research.
"""
from __future__ import annotations

import math
from statistics import mean
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.adapters.basketball_reference import (
    BasketballReferenceSplitAdapter,
    BasketballReferenceTeamAdapter,
    BasketballReferenceTeamGameLogAdapter,
)
from dcm.research.adapters.espn_status import ESPNStatusAdapter
from dcm.research.adapters.official_league import OfficialNBAAdapter, OfficialWNBAAdapter
from dcm.research.lineup import build_lineup_effects
from dcm.research.player_packet import WINDOW_SIZES, window_means


LEAGUE_PACE_PRIOR = {"WNBA": 80.0, "NBA": 100.0, "NCAAB": 68.0}
TEAM_WINDOW_KEYS = ("pts", "opp_pts", "poss", "ortg", "drtg", "fga", "tov")


def _f(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _avg(rows: list[dict[str, Any]], key: str) -> tuple[float | None, int]:
    vals = [_f(r.get(key)) for r in rows]
    vals = [v for v in vals if v is not None]
    return (mean(vals), len(vals)) if vals else (None, 0)


def _s(value: Any) -> str:
    return "" if value is None else str(value)


def estimate_possessions(row: dict[str, Any]) -> float | None:
    explicit = _f(row.get("poss") or row.get("possessions"))
    if explicit is not None:
        return explicit
    fga = _f(row.get("fga"))
    fta = _f(row.get("fta")) or 0.0
    tov = _f(row.get("tov")) or 0.0
    oreb = _f(row.get("oreb")) or 0.0
    if fga is None:
        return None
    return fga + 0.44 * fta + tov - oreb


def normalize_team_log(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    pts = _f(row.get("pts") or row.get("Tm") or row.get("team_pts"))
    opp_pts = _f(row.get("opp_pts") or row.get("Opp") or row.get("opponent_pts"))
    fga = _f(row.get("fga") or row.get("FGA"))
    poss = estimate_possessions(row)
    ortg = None
    drtg = None
    if poss and poss > 1e-6:
        if pts is not None:
            ortg = 100.0 * pts / poss
        if opp_pts is not None:
            drtg = 100.0 * opp_pts / poss
    out = {
        "date": row.get("date") or row.get("date_game") or row.get("gameDate"),
        "opponent": row.get("opp") or row.get("opponent") or row.get("opp_id"),
        "home": row.get("home") if "home" in row else (str(row.get("location") or "").lower() in {"home", "h"}),
        "pts": pts,
        "opp_pts": opp_pts,
        "fga": fga,
        "fta": _f(row.get("fta")),
        "tov": _f(row.get("tov")),
        "oreb": _f(row.get("oreb") or row.get("orb")),
        "poss": poss,
        "ortg": ortg,
        "drtg": drtg,
        "raw": dict(row),
    }
    if pts is None and poss is None and fga is None:
        return None
    return out


def _claims_for(claims: list[dict[str, Any]], scope: str, scope_id: str) -> list[dict[str, Any]]:
    out = []
    for claim in claims or []:
        if str(claim.get("semantic_scope") or "") == scope and str(claim.get("scope_id") or "") == str(scope_id):
            out.append(claim)
    return out


def _merged_value(claims: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for claim in claims:
        value = claim.get("claim_value")
        if isinstance(value, dict):
            merged.update(value)
    return merged


def _fixture_prior_only(merged: dict[str, Any]) -> bool:
    if not merged:
        return True
    pace = merged.get("pace_multiplier")
    matchup = merged.get("matchup_efficiency_multiplier")
    logs = merged.get("team_logs") or merged.get("game_logs") or merged.get("gameLogs")
    html = merged.get("team_html") or merged.get("gamelog_html") or merged.get("html")
    if logs or html or merged.get("adapter_records"):
        return False
    if merged.get("pace") or merged.get("possessions") or merged.get("ortg") or merged.get("drtg"):
        return False
    try:
        return abs(float(pace if pace is not None else 1.0) - 1.0) < 1e-12 and abs(
            float(matchup if matchup is not None else 1.0) - 1.0
        ) < 1e-12
    except (TypeError, ValueError):
        return False


def _logs_from_claims(merged: dict[str, Any], *, retrieved_at: str, source_url: str | None) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    hashes: list[str] = []
    logs: list[dict[str, Any]] = []
    season_fields: dict[str, Any] = {}
    structured = merged.get("team_logs") or merged.get("game_logs") or merged.get("gameLogs")
    if isinstance(structured, list):
        for row in structured:
            norm = normalize_team_log(row) if isinstance(row, dict) else None
            if norm:
                logs.append(norm)
    html = merged.get("team_gamelog_html") or merged.get("gamelog_html")
    if html:
        adapter = BasketballReferenceTeamGameLogAdapter(retrieved_at=retrieved_at)
        recs = adapter.normalize(
            {
                "url": source_url or "fixture://basketball-reference/team-gamelog",
                "html": html,
                "retrievedAt": retrieved_at,
                "publishedAt": retrieved_at,
            }
        )
        for rec in recs:
            if rec.get("contentHash"):
                hashes.append(str(rec["contentHash"]))
            fields = rec.get("fields") or {}
            raw = rec.get("raw") or fields
            norm = normalize_team_log({**raw, **fields})
            if norm:
                logs.append(norm)
    team_html = merged.get("team_html") or merged.get("season_html")
    if team_html:
        adapter = BasketballReferenceTeamAdapter(retrieved_at=retrieved_at)
        recs = adapter.normalize(
            {
                "url": source_url or "fixture://basketball-reference/team",
                "html": team_html,
                "retrievedAt": retrieved_at,
                "publishedAt": retrieved_at,
            }
        )
        for rec in recs:
            if rec.get("contentHash"):
                hashes.append(str(rec["contentHash"]))
            fields = rec.get("fields") or {}
            for key in ("pace", "ortg", "drtg", "net_rtg", "pts", "opp_pts", "possessions", "fg_pct", "fg3_pct", "ft_pct"):
                if fields.get(key) is not None and season_fields.get(key) is None:
                    season_fields[key] = fields.get(key)
    split_html = merged.get("split_html")
    if split_html:
        adapter = BasketballReferenceSplitAdapter(retrieved_at=retrieved_at)
        recs = adapter.normalize(
            {
                "url": source_url or "fixture://basketball-reference/splits",
                "html": split_html,
                "retrievedAt": retrieved_at,
                "publishedAt": retrieved_at,
            }
        )
        for rec in recs:
            if rec.get("contentHash"):
                hashes.append(str(rec["contentHash"]))
    if isinstance(merged.get("adapter_records"), list):
        for rec in merged["adapter_records"]:
            if isinstance(rec, dict) and rec.get("contentHash"):
                hashes.append(str(rec["contentHash"]))
            if isinstance(rec, dict):
                fields = rec.get("fields") or {}
                for key in ("pace", "ortg", "drtg", "net_rtg", "pts", "opp_pts", "possessions"):
                    if fields.get(key) is not None and season_fields.get(key) is None:
                        season_fields[key] = fields.get(key)
    return logs, hashes, season_fields


def build_team_research_packet(
    *,
    team_id: str,
    league: str | None = None,
    sport_family: str | None = None,
    claims: list[dict[str, Any]] | None = None,
    structured_logs: list[dict[str, Any]] | None = None,
    team_html: str | None = None,
    gamelog_html: str | None = None,
    as_of: str = "",
    source_url: str | None = None,
    dependent_offer_count: int = 0,
    applies_to_player_ids: list[str] | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    team_claims = list(claims or [])
    merged = _merged_value(team_claims)
    if team_html:
        merged = {**merged, "team_html": team_html}
    if gamelog_html:
        merged = {**merged, "team_gamelog_html": gamelog_html}
    flags: list[str] = []
    logs, hashes, season_fields = _logs_from_claims(merged, retrieved_at=as_of, source_url=source_url)
    if structured_logs:
        for row in structured_logs:
            norm = normalize_team_log(row)
            if norm:
                logs.append(norm)
    for rec in team_claims:
        h = rec.get("claim_hash") or rec.get("source_hash")
        if h:
            hashes.append(str(h))

    pts, pn = _avg(logs, "pts")
    opp_pts, on = _avg(logs, "opp_pts")
    poss, posn = _avg(logs, "poss")
    ortg, orn = _avg(logs, "ortg")
    drtg, drn = _avg(logs, "drtg")
    if pts is None:
        pts = _f(season_fields.get("pts") or merged.get("pts"))
    if opp_pts is None:
        opp_pts = _f(season_fields.get("opp_pts") or merged.get("opp_pts"))
    if poss is None:
        poss = _f(season_fields.get("possessions") or season_fields.get("pace") or merged.get("pace") or merged.get("possessions"))
    if ortg is None:
        ortg = _f(season_fields.get("ortg") or merged.get("ortg"))
    if drtg is None:
        drtg = _f(season_fields.get("drtg") or merged.get("drtg"))
    league_pace = LEAGUE_PACE_PRIOR.get(str(league or "").upper())
    pace_multiplier = None
    if poss is not None and league_pace:
        pace_multiplier = poss / league_pace
    fixture_only = _fixture_prior_only(merged) and not logs and not season_fields
    evidence_used = (
        len(logs) > 0
        or bool(season_fields)
        or bool(merged.get("pace") or merged.get("possessions") or merged.get("ortg"))
    )
    if fixture_only:
        flags.append("FIXTURE_TEAM_PRIOR")
        evidence_used = False
    if not logs:
        flags.append("NO_USABLE_TEAM_LOGS")
    if evidence_used and len(logs) < 3:
        flags.append("TEAM_SUPPORT_N_LT_3")

    season = merged.get("season") if isinstance(merged.get("season"), dict) else {}
    if season_fields:
        season = {**season_fields, **season, "fromAdapter": True}
    if not season and team_html:
        season = {"fromAdapter": True}
    windows = {f"L{n}": window_means(logs, n, keys=TEAM_WINDOW_KEYS) for n in WINDOW_SIZES} if logs else {}

    parameter_fields: dict[str, Any] = {
        "pace": poss,
        "possessions": poss,
        "ortg": ortg,
        "drtg": drtg,
        "pts_mean": pts,
        "opp_pts_mean": opp_pts,
        "team_context": True if evidence_used else None,
    }
    if pace_multiplier is not None and evidence_used:
        parameter_fields["pace_multiplier"] = pace_multiplier
    parameter_fields = {k: v for k, v in parameter_fields.items() if v is not None}

    body: dict[str, Any] = {
        "schema": "pillars_dcm.team_research_packet.v1",
        "teamId": team_id,
        "name": name or team_id,
        "league": league,
        "sportFamily": sport_family,
        "gameLogs": logs,
        "gameLogCount": len(logs),
        "fullSeasonRetained": True,
        "windows": windows,
        "seasonSummary": season,
        "pace": poss,
        "paceMultiplier": pace_multiplier,
        "ortg": ortg,
        "drtg": drtg,
        "ptsMean": pts,
        "oppPtsMean": opp_pts,
        "support_n": max(pn, posn, orn, drn, on, 0),
        "parameterFields": parameter_fields,
        "sourceHashes": sorted(set(hashes)),
        "asOf": as_of,
        "flags": flags,
        "evidenceUsed": evidence_used,
        "thin": not evidence_used,
        "priorUsedAsResearch": False,
        "fixturePriorOnly": fixture_only,
        "dependentOfferCount": int(dependent_offer_count),
        "appliesToPlayerIds": list(applies_to_player_ids or []),
        "reuseRule": "One team packet serves every player on this team and every opponent-side offer against this team.",
    }
    body["packetId"] = content_hash(
        {"teamId": team_id, "asOf": as_of, "logN": len(logs), "sourceHashes": body["sourceHashes"]}
    )[:24]
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def build_opponent_research_packet(
    team_packet: dict[str, Any],
    *,
    event_id: str = "",
    versus_team_id: str = "",
    h2h_logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reuse a team packet as opponent context. H2H is shrunken, never dominant."""
    h2h = [normalize_team_log(r) for r in (h2h_logs or [])]
    h2h = [r for r in h2h if r]
    h2h_ortg, hn = _avg(h2h, "ortg")
    team_ortg = _f(team_packet.get("ortg"))
    # Shrink H2H toward the opponent's season: tiny n cannot dominate.
    if h2h_ortg is not None and team_ortg is not None:
        shrunken_ortg = (h2h_ortg * hn + team_ortg * 8.0) / (hn + 8.0)
    else:
        shrunken_ortg = team_ortg
    body = {
        "schema": "pillars_dcm.opponent_research_packet.v1",
        "teamId": team_packet.get("teamId"),
        "versusTeamId": versus_team_id,
        "eventId": event_id,
        "reusedTeamPacketId": team_packet.get("packetId"),
        "reusedTeamPacketHash": team_packet.get("contentHash"),
        "pace": team_packet.get("pace"),
        "paceMultiplier": team_packet.get("paceMultiplier"),
        "ortg": team_packet.get("ortg"),
        "drtg": team_packet.get("drtg"),
        "h2hSupportN": hn,
        "h2hOrtgRaw": h2h_ortg,
        "h2hOrtgShrunken": shrunken_ortg,
        "h2hDominates": False,
        "parameterFields": dict(team_packet.get("parameterFields") or {}),
        "evidenceUsed": bool(team_packet.get("evidenceUsed")),
        "thin": bool(team_packet.get("thin")),
        "priorUsedAsResearch": False,
        "asOf": team_packet.get("asOf"),
    }
    if shrunken_ortg is not None:
        body["parameterFields"] = {**body["parameterFields"], "matchup_ortg": shrunken_ortg}
    body["packetId"] = content_hash(
        {"team": team_packet.get("packetId"), "event": event_id, "versus": versus_team_id}
    )[:24]
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def build_event_research_packet(
    *,
    event_id: str,
    claims: list[dict[str, Any]] | None = None,
    offer_sets: list[dict[str, Any]] | None = None,
    as_of: str = "",
    league: str | None = None,
    sport_family: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
    label: str | None = None,
    start: str | None = None,
    venue: str | None = None,
    official_json: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    event_claims = list(claims or [])
    merged = _merged_value(event_claims)
    hashes: list[str] = []
    for rec in event_claims:
        h = rec.get("claim_hash") or rec.get("source_hash")
        if h:
            hashes.append(str(h))
    if official_json is not None:
        adapter: Any = OfficialWNBAAdapter(retrieved_at=as_of) if str(league or "").upper() == "WNBA" else OfficialNBAAdapter(retrieved_at=as_of)
        recs = adapter.normalize(
            {
                "url": "fixture://official/schedule",
                "json": official_json,
                "retrievedAt": as_of,
                "publishedAt": as_of,
                "league": league,
            }
        )
        for rec in recs:
            if rec.get("contentHash"):
                hashes.append(str(rec["contentHash"]))
            fields = rec.get("fields") or {}
            if str(fields.get("eventId") or "") in {str(event_id), ""} or not event_id:
                merged = {**merged, **fields}
    espn_json = merged.get("espn_json") or merged.get("status_json")
    if espn_json:
        recs = ESPNStatusAdapter(retrieved_at=as_of).normalize(
            {"url": "fixture://espn/status", "json": espn_json, "retrievedAt": as_of, "publishedAt": as_of}
        )
        for rec in recs:
            if rec.get("contentHash"):
                hashes.append(str(rec["contentHash"]))
    lineup = build_lineup_effects(merged.get("lineup_effects") or merged.get("on_off") or [])
    sample = (offer_sets or [None])[0] or {}
    start_time = start or merged.get("scheduled_start") or merged.get("start") or sample.get("eventStartTime")
    venue_val = venue or merged.get("venue")
    env = merged.get("environment") or merged.get("event_context")
    rest = merged.get("rest") or merged.get("restDays")
    travel = merged.get("travel") or merged.get("travelMiles")
    game_status = merged.get("gameStatus") or merged.get("status")
    fixture_env = str(env or "") == "neutral_fixture" and not start_time and not venue_val
    evidence_used = bool(start_time or venue_val or (env and not fixture_env) or merged.get("starters_known"))
    flags: list[str] = []
    if fixture_env and not evidence_used:
        flags.append("FIXTURE_EVENT_PRIOR")
    if not start_time:
        flags.append("EVENT_START_MISSING")
    if str(game_status or "").upper() in {"IN_PROGRESS", "LIVE", "FINAL", "SUSPENDED"}:
        flags.append(f"EVENT_STATUS_{str(game_status).upper()}")
    body: dict[str, Any] = {
        "schema": "pillars_dcm.event_research_packet.v1",
        "eventId": event_id,
        "label": label or sample.get("eventLabel") or merged.get("label"),
        "league": league or sample.get("league") or merged.get("league"),
        "sportFamily": sport_family or sample.get("sportFamily") or merged.get("sportFamily"),
        "homeTeam": home_team or merged.get("home") or sample.get("team"),
        "awayTeam": away_team or merged.get("away") or sample.get("opponent"),
        "scheduledStart": start_time,
        "venue": venue_val,
        "environment": env,
        "rest": rest,
        "travel": travel,
        "startersKnown": bool(merged.get("starters_known")),
        "gameStatus": game_status,
        "lineup": lineup,
        "parameterFields": {
            k: v
            for k, v in {
                "scheduled_start": start_time,
                "venue": venue_val,
                "environment": env,
                "starters_known": merged.get("starters_known"),
                "event_context": True if evidence_used else None,
                "pace_multiplier": merged.get("pace_multiplier"),
            }.items()
            if v is not None
        },
        "sourceHashes": sorted(set(hashes)),
        "asOf": as_of,
        "flags": flags,
        "evidenceUsed": evidence_used,
        "thin": not evidence_used,
        "priorUsedAsResearch": False,
        "fixturePriorOnly": fixture_env and not evidence_used,
        "dependentOfferCount": sum(int(s.get("offerCount") or 0) for s in (offer_sets or [])),
    }
    body["packetId"] = content_hash({"eventId": event_id, "asOf": as_of, "start": start_time})[:24]
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def build_entity_packets(
    offer_sets: list[dict[str, Any]],
    *,
    claims: list[dict[str, Any]] | None = None,
    as_of: str = "",
    population: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One team packet per unique team; opponent packets reuse those; one event packet per event."""
    claims = [c for c in (claims or []) if isinstance(c, dict)]
    teams: dict[str, dict[str, Any]] = {}
    events: dict[str, list[dict[str, Any]]] = {}
    team_players: dict[str, set[str]] = {}
    team_meta: dict[str, dict[str, Any]] = {}
    team_dependents: dict[str, int] = {}
    for offer in offer_sets or []:
        team_id = _s(offer.get("team") or offer.get("teamId"))
        opp_id = _s(offer.get("opponent") or offer.get("opponentId"))
        event_id = _s(offer.get("eventId"))
        player_id = _s(offer.get("playerId"))
        n_offers = int(offer.get("offerCount") or len(offer.get("offers") or []))
        if team_id:
            team_players.setdefault(team_id, set()).add(player_id)
            team_dependents[team_id] = team_dependents.get(team_id, 0) + n_offers
            team_meta.setdefault(team_id, {
                "league": offer.get("league"),
                "sportFamily": offer.get("sportFamily"),
                "name": team_id,
            })
        if opp_id:
            team_dependents[opp_id] = team_dependents.get(opp_id, 0) + n_offers
            team_meta.setdefault(opp_id, {
                "league": offer.get("league"),
                "sportFamily": offer.get("sportFamily"),
                "name": opp_id,
            })
        if event_id:
            events.setdefault(event_id, []).append(offer)

    team_packets: list[dict[str, Any]] = []
    for team_id, meta in sorted(team_meta.items()):
        packet = build_team_research_packet(
            team_id=team_id,
            league=meta.get("league"),
            sport_family=meta.get("sportFamily"),
            claims=_claims_for(claims, "TEAM", team_id),
            as_of=as_of,
            dependent_offer_count=team_dependents.get(team_id, 0),
            applies_to_player_ids=sorted(team_players.get(team_id) or []),
            name=meta.get("name"),
        )
        teams[team_id] = packet
        team_packets.append(packet)

    event_packets: list[dict[str, Any]] = []
    opponent_packets: list[dict[str, Any]] = []
    for event_id, offers in sorted(events.items()):
        sample = offers[0]
        home = _s(sample.get("team"))
        away = _s(sample.get("opponent"))
        ev = build_event_research_packet(
            event_id=event_id,
            claims=_claims_for(claims, "EVENT", event_id),
            offer_sets=offers,
            as_of=as_of,
            league=sample.get("league"),
            sport_family=sample.get("sportFamily"),
            home_team=home,
            away_team=away,
            label=sample.get("eventLabel"),
            start=sample.get("eventStartTime"),
        )
        event_packets.append(ev)
        if away and away in teams:
            opponent_packets.append(
                build_opponent_research_packet(teams[away], event_id=event_id, versus_team_id=home)
            )
        if home and home in teams and home != away:
            opponent_packets.append(
                build_opponent_research_packet(teams[home], event_id=event_id, versus_team_id=away)
            )

    body = {
        "schema": "pillars_dcm.entity_research_packets.v1",
        "teamPacketCount": len(team_packets),
        "eventPacketCount": len(event_packets),
        "opponentPacketCount": len(opponent_packets),
        "thinTeamPackets": sum(1 for p in team_packets if p.get("thin")),
        "reuseRule": "N players on one team → 1 TeamResearchPacket. Opponent reuses that packet.",
        "teams": team_packets,
        "events": event_packets,
        "opponents": opponent_packets,
        "populationHash": (population or {}).get("contentHash"),
        "asOf": as_of,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
