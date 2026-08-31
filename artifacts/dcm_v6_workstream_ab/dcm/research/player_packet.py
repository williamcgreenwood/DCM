"""PlayerResearchPacket: full current-season logs, derived windows, no silent priors.

One packet is reused for every offer in a PlayerOfferSet. Last-5 is a window
computed FROM the full log — it never replaces the full log.
"""
from __future__ import annotations

import math
from statistics import mean
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.adapters.basketball_reference import (
    BasketballReferenceGameLogAdapter,
    BasketballReferencePlayerAdapter,
)
from dcm.research.adapters.pro_football_reference import FootballReferenceGameLogAdapter
from dcm.research.gamelog import normalize_basketball_logs
from dcm.research.gridiron_gamelog import normalize_gridiron_logs


WINDOW_SIZES = (3, 5, 10, 15, 20)
WINDOW_KEYS = {n: f"L{n}" for n in WINDOW_SIZES}
WINDOW_STAT_KEYS = ("minutes", "pts", "reb", "ast", "fga", "tpa", "fta")
GRIDIRON_WINDOW_STAT_KEYS = (
    "snaps", "pass_att", "pass_yds", "rush_att", "rush_yds",
    "targets", "receptions", "rec_yds", "routes",
)
GRIDIRON_LEAGUES = frozenset({"NFL", "CFB", "NFLP", "CFL", "UFL"})


def _is_gridiron_identity(identity: dict, league: str | None = None) -> bool:
    fam = str((identity or {}).get("sportFamily") or (identity or {}).get("family") or "").lower()
    if fam in {"gridiron", "football"}:
        return True
    lg = str(league or (identity or {}).get("league") or "").upper()
    return lg in GRIDIRON_LEAGUES


def _f(value: Any) -> float | None:
    if value is None or value is False:
        return None
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _avg(logs: list[dict[str, Any]], key: str) -> tuple[float | None, int]:
    vals = []
    for row in logs:
        x = _f(row.get(key))
        if x is not None:
            vals.append(x)
    return (mean(vals), len(vals)) if vals else (None, 0)


def _sort_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple:
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        date = str(row.get("date") or row.get("gameDate") or raw.get("date_game") or raw.get("date") or "")
        rk = str(raw.get("ranker") or raw.get("Rk") or row.get("rk") or "")
        return (date, rk)

    return sorted(logs, key=key)


def window_means(logs: list[dict[str, Any]], n: int, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Derived window from the FULL log. Does not replace the full log.

    L5/L10/... are slices of the already-normalized season, newest-last.
    tpa/fta means are additive; support_n stays based on minutes/pts/reb/ast/fga
    so existing packet tests remain stable when those extra fields are missing.
    """
    stat_keys = keys or WINDOW_STAT_KEYS
    slice_logs = logs[-n:] if n < len(logs) else list(logs)
    avgs: dict[str, float | None] = {}
    counts: dict[str, int] = {}
    for key in stat_keys:
        mu, cn = _avg(slice_logs, key)
        avgs[f"{key}_mean"] = mu
        counts[key] = cn
    if "pts_mean" in avgs:
        pts, reb, ast = avgs.get("pts_mean"), avgs.get("reb_mean"), avgs.get("ast_mean")
        core = tuple(counts.get(k, 0) for k in ("minutes", "pts", "reb", "ast", "fga"))
        pra = None if pts is None or reb is None or ast is None else pts + reb + ast
    else:
        core = tuple(counts.get(k, 0) for k in stat_keys)
        pra = None
        pts = reb = ast = None
    return {
        "nRequested": n,
        "nAvailable": len(slice_logs),
        **avgs,
        "pra_mean": pra,
        "support_n": min(x for x in core if x) if any(core) else 0,
        "derivedFromFullLog": True,
        "doesNotReplaceFullLog": True,
    }


def _window(logs: list[dict[str, Any]], n: int, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    return window_means(logs, n, keys=keys)


def _pra_identity(logs: list[dict[str, Any]]) -> dict[str, Any]:
    pts, pn = _avg(logs, "pts")
    reb, rn = _avg(logs, "reb")
    ast, an = _avg(logs, "ast")
    components = pts is not None and reb is not None and ast is not None
    support = min([n for n in (pn, rn, an) if n] or [0])
    return {
        "pts_mean": pts,
        "reb_mean": reb,
        "ast_mean": ast,
        "pra_mean": (pts + reb + ast) if components else None,
        "componentsPresent": components,
        "support_n": support,
        "identity": "pra = pts + reb + ast",
    }


def _logs_from_adapter_records(records: list[dict[str, Any]], *, league: str | None, gridiron: bool = False) -> dict[str, Any]:
    raw_rows = []
    for rec in records:
        if rec.get("fields") and rec.get("normalized") is True:
            raw_rows.append(rec.get("raw") or rec.get("fields"))
        elif rec.get("raw"):
            raw_rows.append(rec["raw"])
        elif rec.get("fields"):
            raw_rows.append(rec["fields"])
    if gridiron:
        return normalize_gridiron_logs(raw_rows, league=league)
    return normalize_basketball_logs(raw_rows, league=league)


def _logs_from_structured(logs: Any, *, league: str | None, gridiron: bool = False) -> dict[str, Any]:
    rows = [x for x in logs if isinstance(x, dict)] if isinstance(logs, list) else []
    if gridiron:
        return normalize_gridiron_logs(rows, league=league)
    return normalize_basketball_logs(rows, league=league)


def build_player_research_packet(
    *,
    identity: dict[str, Any] | None = None,
    status: str | None = None,
    role_hints: dict[str, Any] | None = None,
    gamelog_records: list[dict[str, Any]] | None = None,
    player_summary_records: list[dict[str, Any]] | None = None,
    structured_logs: list[dict[str, Any]] | None = None,
    gamelog_html: str | None = None,
    player_html: str | None = None,
    offer_set: dict[str, Any] | None = None,
    as_of: str = "",
    league: str | None = None,
    source_url: str | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Build a packet from adapter outputs and/or already-structured logs.

    Does not invent logs. Minutes-invalid rows are rejected and flagged.
    evidenceUsed is true only when usable normalized logs exist.
    """
    ident = dict(identity or {})
    offer = dict(offer_set or {})
    if offer:
        ident.setdefault("playerId", offer.get("playerId"))
        ident.setdefault("playerName", offer.get("playerName"))
        ident.setdefault("sportFamily", offer.get("sportFamily"))
        ident.setdefault("league", offer.get("league"))
        ident.setdefault("team", offer.get("team"))
        ident.setdefault("opponent", offer.get("opponent"))
        ident.setdefault("eventId", offer.get("eventId"))
        ident.setdefault("eventLabel", offer.get("eventLabel"))
        ident.setdefault("eventStartTime", offer.get("eventStartTime"))
    lg = league or ident.get("league")
    gridiron = _is_gridiron_identity(ident, lg)

    flags: list[str] = []
    source_hashes: list[str] = []
    adapter_records: list[dict[str, Any]] = list(gamelog_records or [])
    summary_records: list[dict[str, Any]] = list(player_summary_records or [])

    if gamelog_html:
        if gridiron:
            adapter = FootballReferenceGameLogAdapter(retrieved_at=retrieved_at or as_of)
            parsed = adapter.normalize(
                {
                    "url": source_url or "fixture://pro-football-reference/gamelog",
                    "html": gamelog_html,
                    "retrievedAt": retrieved_at or as_of,
                    "publishedAt": retrieved_at or as_of,
                    "league": lg,
                }
            )
        else:
            adapter = BasketballReferenceGameLogAdapter(retrieved_at=retrieved_at or as_of)
            parsed = adapter.normalize(
                {
                    "url": source_url or "fixture://basketball-reference/gamelog",
                    "html": gamelog_html,
                    "retrievedAt": retrieved_at or as_of,
                    "publishedAt": retrieved_at or as_of,
                    "league": lg,
                }
            )
        adapter_records.extend(parsed)
    if player_html:
        padapter = BasketballReferencePlayerAdapter(retrieved_at=retrieved_at or as_of)
        summary_records.extend(
            padapter.normalize(
                {
                    "url": source_url or "fixture://basketball-reference/player",
                    "html": player_html,
                    "retrievedAt": retrieved_at or as_of,
                    "publishedAt": retrieved_at or as_of,
                    "league": lg,
                }
            )
        )

    for rec in adapter_records + summary_records:
        h = rec.get("contentHash")
        if h:
            source_hashes.append(str(h))

    if adapter_records:
        batch = _logs_from_adapter_records(adapter_records, league=str(lg) if lg else None, gridiron=gridiron)
    else:
        batch = _logs_from_structured(structured_logs, league=str(lg) if lg else None, gridiron=gridiron)

    full_logs = _sort_logs(list(batch.get("logs") or []))
    rejected = list(batch.get("rejected") or [])
    if rejected:
        flags.append("GAMELOG_OPPORTUNITY" if gridiron else "MINUTES_MISSING")
    if not full_logs:
        flags.append("NO_USABLE_GAME_LOGS")

    usable_n = len(full_logs)
    evidence_used = usable_n > 0
    if evidence_used and usable_n < 3:
        flags.append("SUPPORT_N_LT_3")

    win_keys = GRIDIRON_WINDOW_STAT_KEYS if gridiron else None
    windows = {WINDOW_KEYS[n]: _window(full_logs, n, keys=win_keys) for n in WINDOW_SIZES}
    pra = _pra_identity(full_logs) if not gridiron else {
        "pass_yds_mean": _avg(full_logs, "pass_yds")[0],
        "rec_yds_mean": _avg(full_logs, "rec_yds")[0],
        "receptions_mean": _avg(full_logs, "receptions")[0],
        "identity": "pass_rush_yds = pass_yds + rush_yds; rush_rec_yds = rush_yds + rec_yds",
        "componentsPresent": True,
        "support_n": len(full_logs),
    }

    season_summary: dict[str, Any] = {}
    if summary_records:
        season_summary = dict(summary_records[-1].get("fields") or {})
        season_summary["fromAdapter"] = True
    else:
        minutes, mn = _avg(full_logs, "minutes")
        pts, pn = _avg(full_logs, "pts")
        reb, rn = _avg(full_logs, "reb")
        ast, an = _avg(full_logs, "ast")
        season_summary = {
            "fromAdapter": False,
            "games": usable_n,
            "minutes_mean": minutes,
            "pts_mean": pts,
            "reb_mean": reb,
            "ast_mean": ast,
            "derivedFromFullLog": True,
        }

    applies = []
    if offer.get("offers"):
        applies = [str(o.get("projectionId") or "") for o in offer["offers"] if o.get("projectionId")]

    if gridiron:
        opportunity = {
            "support_n": usable_n,
            "from": "FULL_USABLE_LOGS",
            "pass_att_mean": _avg(full_logs, "pass_att")[0],
            "rush_att_mean": _avg(full_logs, "rush_att")[0],
            "routes_mean": _avg(full_logs, "routes")[0],
            "targets_mean": _avg(full_logs, "targets")[0],
            "snaps_mean": _avg(full_logs, "snaps")[0],
        }
        efficiency = {
            "support_n": usable_n,
            "from": "FULL_USABLE_LOGS",
            "pass_yds_mean": _avg(full_logs, "pass_yds")[0],
            "rec_yds_mean": _avg(full_logs, "rec_yds")[0],
            "receptions_mean": _avg(full_logs, "receptions")[0],
            "rush_yds_mean": _avg(full_logs, "rush_yds")[0],
        }
    else:
        opportunity = {
            "support_n": usable_n,
            "from": "FULL_USABLE_LOGS",
            "minutes_mean": _avg(full_logs, "minutes")[0],
        }
        efficiency = {
            "support_n": usable_n,
            "from": "FULL_USABLE_LOGS",
            "pts_mean": _avg(full_logs, "pts")[0],
            "reb_mean": _avg(full_logs, "reb")[0],
            "ast_mean": _avg(full_logs, "ast")[0],
            "fga_mean": _avg(full_logs, "fga")[0],
        }

    packet_id_src = {
        "playerId": ident.get("playerId"),
        "eventId": ident.get("eventId"),
        "asOf": as_of,
        "logN": usable_n,
        "sourceHashes": sorted(set(source_hashes)),
    }
    body: dict[str, Any] = {
        "schema": "pillars_dcm.player_research_packet.v1",
        "packetId": content_hash(packet_id_src)[:24],
        "identity": ident,
        "status": str(status or ident.get("status") or "").strip().upper() or None,
        "roleHints": dict(role_hints or {}),
        "gameLogs": full_logs,
        "gameLogCount": usable_n,
        "gameLogsRejected": rejected,
        "fullSeasonRetained": True,
        "windows": windows,
        "seasonSummary": season_summary,
        "praIdentity": pra,
        "opportunity": opportunity,
        "efficiency": efficiency,
        "sourceHashes": sorted(set(source_hashes)),
        "asOf": as_of,
        "flags": flags,
        "evidenceUsed": evidence_used,
        "thin": not evidence_used,
        "appliesToProjectionIds": applies,
        "offerSetId": offer.get("setId"),
        "priorUsedAsResearch": False,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def build_packets_for_offer_sets(
    offer_sets: list[dict[str, Any]],
    *,
    claims: list[dict[str, Any]] | None = None,
    as_of: str = "",
) -> list[dict[str, Any]]:
    """One packet per PlayerOfferSet. Reused across that set's markets.

    Player claims supply status/role/logs when present. Does not invent logs.
    HTML on a claim is parsed via Basketball-Reference adapters.
    """
    claims = [c for c in (claims or []) if isinstance(c, dict)]
    by_player: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        if str(claim.get("semantic_scope") or "") != "PLAYER":
            continue
        by_player.setdefault(str(claim.get("scope_id") or ""), []).append(claim)

    packets: list[dict[str, Any]] = []
    for offer_set in offer_sets:
        player_id = str(offer_set.get("playerId") or "")
        player_claims = by_player.get(player_id) or []
        merged: dict[str, Any] = {}
        structured_logs: list[dict[str, Any]] = []
        html = None
        player_html = None
        status = None
        role_hints: dict[str, Any] = {}
        extra_records: list[dict[str, Any]] = []
        summary_records: list[dict[str, Any]] = []
        for claim in player_claims:
            value = claim.get("claim_value") if isinstance(claim.get("claim_value"), dict) else {}
            merged.update(value)
            if value.get("status") and not status:
                status = value.get("status")
            if value.get("role"):
                role_hints.setdefault("role", value.get("role"))
            logs = value.get("role_epoch_logs") or value.get("game_logs") or value.get("gameLogs")
            if isinstance(logs, list):
                structured_logs.extend(x for x in logs if isinstance(x, dict))
            html = html or value.get("gamelog_html") or value.get("html") or value.get("raw_html")
            player_html = player_html or value.get("player_html") or value.get("season_html")
            if isinstance(value.get("adapter_records"), list):
                extra_records.extend(x for x in value["adapter_records"] if isinstance(x, dict))
        packets.append(
            build_player_research_packet(
                identity={
                    "playerId": player_id,
                    "playerName": offer_set.get("playerName"),
                    "sportFamily": offer_set.get("sportFamily"),
                    "league": offer_set.get("league"),
                    "team": offer_set.get("team"),
                    "opponent": offer_set.get("opponent"),
                    "eventId": offer_set.get("eventId"),
                    "eventLabel": offer_set.get("eventLabel"),
                    "eventStartTime": offer_set.get("eventStartTime"),
                },
                status=status or merged.get("status"),
                role_hints=role_hints,
                structured_logs=structured_logs or None,
                gamelog_records=extra_records or None,
                player_summary_records=summary_records or None,
                gamelog_html=html,
                player_html=player_html,
                offer_set=offer_set,
                as_of=as_of,
                league=offer_set.get("league"),
            )
        )
    packets.sort(key=lambda p: (str((p.get("identity") or {}).get("playerId") or ""), str((p.get("identity") or {}).get("eventId") or "")))
    return packets


def packets_document(packets: list[dict[str, Any]]) -> dict[str, Any]:
    body = {
        "schema": "pillars_dcm.player_research_packets.v1",
        "packetCount": len(packets),
        "fullSeasonPackets": sum(1 for p in packets if p.get("gameLogCount")),
        "thinPackets": sum(1 for p in packets if p.get("thin")),
        "packets": packets,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
