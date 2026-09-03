"""Evidence completeness contracts for production research."""
from __future__ import annotations

from typing import Any

from dcm.research.gamelog import assert_compatible_basketball_logs
from dcm.research.gridiron_gamelog import assert_compatible_gridiron_logs
from dcm.research.scopes import (
    AFFILIATION_SCOPES,
    COUNTERPARTY_SCOPES,
    SUBJECT_SCOPES,
    scopes_match,
)
from dcm.sports.common.research_schema import lookup_research_schema


def _values_for(request: dict[str, Any], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    req_scope = str(request.get("scope") or "")
    req_id = str(request.get("scope_id") or "")
    for claim in claims:
        if (
            scopes_match(req_scope, str(claim.get("semantic_scope") or ""))
            and str(claim.get("scope_id")) == req_id
            and isinstance(claim.get("claim_value"), dict)
        ):
            out.append(dict(claim["claim_value"]))
    return out


def _merge(values: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        merged.update(value)
    return merged



def _league_family(request: dict[str, Any]) -> tuple[str, str]:
    extra = request if isinstance(request, dict) else {}
    league = str(extra.get("league") or extra.get("League") or "").upper()
    family = str(extra.get("sportFamily") or extra.get("sport_family") or "").lower()
    if not family:
        if league in {"NBA", "WNBA"}:
            family = "basketball"
        elif league in {"NFL", "CFB"}:
            family = "gridiron"
    return family, league


_BBALL_LOG_KEYS = {"minutes", "mp", "min", "fga", "tpa", "fta", "fg3a", "3pa", "trb", "reb"}


def _is_basketball_player_request(family: str, logs: list[dict[str, Any]]) -> bool:
    if family == "basketball":
        return True
    if family in {"gridiron", "football", "baseball"}:
        return False
    keys = {str(k).strip().lower() for row in logs for k in row}
    return bool(keys & _BBALL_LOG_KEYS)


def _market_token(request: dict[str, Any]) -> str:
    market = str(request.get("market") or request.get("stat") or "").strip().lower()
    if market:
        return market
    need = str(request.get("need") or "").strip().lower()
    for token in (
        "pra", "3pm", "threes", "points", "pts", "rebounds", "rebound", "reb",
        "assists", "assist", "ast", "steals", "stl", "blocks", "blk", "turnovers", "tov",
        "pass_yds", "pass_att", "pass_cmp", "rush_yds", "rush_att", "rec_yds", "receptions", "pass_rush_yds", "rush_rec_yds",
    ):
        if need == token or need.startswith(token + "_") or need.endswith("_" + token) or f"_{token}_" in need:
            return token
    return ""


def _markets_for_request(request: dict[str, Any]) -> list[str]:
    """Collect market tokens. A PLAYER object existing is never coverage by itself."""
    out: list[str] = []
    token = _market_token(request)
    if token:
        out.append(token)
    extra = request.get("markets") or request.get("dependentMarkets") or []
    if isinstance(extra, str):
        extra = [extra]
    if isinstance(extra, list):
        for item in extra:
            m = str(item or "").strip().lower()
            if m and m not in out:
                out.append(m)
    return out


def _event_missing(request: dict[str, Any], merged: dict[str, Any], values: list[dict[str, Any]]) -> list[str]:
    if not values:
        return ["EVENT_CONTEXT"]
    family, _ = _league_family(request)
    missing: list[str] = []
    if not merged:
        missing.append("EVENT_CONTEXT")
        return missing
    # Fail closed on sport-specific required fields when the family is known.
    if family == "basketball":
        if not (merged.get("event_context") or merged.get("starters_known") or merged.get("scheduled_start") or merged.get("environment")):
            missing.append("BASKETBALL_EVENT_CONTEXT")
        if not (merged.get("scheduled_start") or merged.get("start") or merged.get("starters_known") or merged.get("venue") or merged.get("environment")):
            missing.append("BASKETBALL_EVENT_START_OR_VENUE")
    elif family in {"gridiron", "football"}:
        if not (merged.get("event_context") or merged.get("scheduled_start") or merged.get("environment") or merged.get("starters_known")):
            missing.append("FOOTBALL_EVENT_CONTEXT")
        if not (merged.get("surface") or merged.get("weather") or merged.get("environment") or merged.get("venue")):
            missing.append("FOOTBALL_EVENT_SURFACE_OR_WEATHER")
    return missing


def _team_missing(request: dict[str, Any], merged: dict[str, Any], values: list[dict[str, Any]]) -> list[str]:
    if not values:
        return ["TEAM_CONTEXT"]
    family, _ = _league_family(request)
    missing: list[str] = []
    if not merged:
        missing.append("TEAM_CONTEXT")
        return missing
    if family == "basketball":
        has_real_pace = any(
            merged.get(k) not in (None, "", [], {})
            for k in ("pace", "possessions", "ortg", "drtg", "team_logs", "game_logs", "team_html", "team_gamelog_html")
        )
        pace_m = merged.get("pace_multiplier")
        fixture_one = False
        try:
            fixture_one = pace_m is not None and abs(float(pace_m) - 1.0) < 1e-12
        except (TypeError, ValueError):
            fixture_one = False
        # Generic 1.0 pace_multiplier is a labeled prior, not team research.
        if not has_real_pace and not merged.get("team_context") and (pace_m is None or fixture_one):
            missing.append("BASKETBALL_TEAM_PACE")
    elif family in {"gridiron", "football"}:
        if not (merged.get("team_context") or merged.get("injury_cluster") is not None or merged.get("depth") or merged.get("matchup_efficiency_multiplier")):
            missing.append("FOOTBALL_TEAM_INJURY_OR_DEPTH")
        if not (merged.get("plays") or merged.get("pace") or merged.get("pace_multiplier") or merged.get("matchup_efficiency_multiplier")):
            missing.append("FOOTBALL_TEAM_PLAYS_OR_PACE")
        if merged.get("pass_defense") is None and merged.get("opp_pass_def") is None and merged.get("pass_defense_multiplier") is None:
            missing.append("OPPONENT_PASS_DEFENSE")
        if merged.get("rush_defense") is None and merged.get("opp_rush_def") is None and merged.get("rush_defense_multiplier") is None:
            missing.append("OPPONENT_RUSH_DEFENSE")
    return missing


def _schema_missing(
    request: dict[str, Any],
    merged: dict[str, Any],
    values: list[dict[str, Any]],
    scope: str,
) -> list[str]:
    """SportResearchSchema-driven extras. Does not replace existing field gates."""
    if not values:
        return []
    family, _league = _league_family(request)
    schema = lookup_research_schema(family) if family else None
    if schema is None:
        return []
    missing: list[str] = []
    if scope in SUBJECT_SCOPES:
        reqs = schema.subject_requirements()
        if not merged.get("status") and "status" in (reqs.get("availability") or reqs.get("participation") or []):
            # already covered by PLAYER_STATUS; skip duplicate
            pass
        min_n = int((reqs.get("minimumSupport") or {}).get("role_comparable_history") or 0)
        logs = merged.get("role_epoch_logs") or merged.get("game_logs") or []
        log_n = len([x for x in logs if isinstance(x, dict)]) if isinstance(logs, list) else 0
        if min_n and log_n < min_n and "ROLE_COMPARABLE_GAME_LOGS_MIN_3" not in missing:
            # existing PLAYER path already emits ROLE_COMPARABLE_GAME_LOGS_MIN_3
            pass
    elif scope in AFFILIATION_SCOPES | COUNTERPARTY_SCOPES:
        ctx = schema.context_requirements()
        needed = ctx["affiliation"] if scope in AFFILIATION_SCOPES else ctx["counterparty"]
        if family == "basketball" and "pace_or_possessions" in needed:
            has_pace = any(
                merged.get(k) not in (None, "", [], {})
                for k in ("pace", "possessions", "ortg", "drtg", "team_logs", "game_logs")
            )
            if not has_pace and "BASKETBALL_TEAM_PACE" not in missing:
                # team_missing already emits this for TEAM/AFFILIATION
                pass
        if family in {"gridiron", "football"} and scope in COUNTERPARTY_SCOPES:
            if merged.get("pass_defense") is None and merged.get("opp_pass_def") is None:
                if "OPPONENT_PASS_DEFENSE" not in missing:
                    missing.append("SPORT_SCHEMA_COUNTERPARTY_PASS_DEFENSE")
            if merged.get("rush_defense") is None and merged.get("opp_rush_def") is None:
                if "OPPONENT_RUSH_DEFENSE" not in missing:
                    missing.append("SPORT_SCHEMA_COUNTERPARTY_RUSH_DEFENSE")
    elif scope == "EVENT":
        ctx = schema.context_requirements().get("event") or []
        if family == "basketball" and "scheduled_start" in ctx:
            if not (merged.get("scheduled_start") or merged.get("start") or merged.get("starters_known")):
                if "BASKETBALL_EVENT_START_OR_VENUE" not in missing:
                    pass
    elif scope == "ENVIRONMENT":
        if not (
            merged.get("environment_context")
            or merged.get("environment")
            or merged.get("weather")
            or merged.get("surface")
            or merged.get("venue")
        ):
            missing.append("ENVIRONMENT_CONTEXT")
    return missing


def evaluate_request(request: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    scope = str(request.get("scope") or "")
    values = _values_for(request, claims)
    merged = _merge(values)
    missing: list[str] = []

    if not values:
        missing.append("EVIDENCE_CLAIM")
    elif scope in SUBJECT_SCOPES:
        # SUBJECT/PLAYER object existence is not coverage. Status, role, comparable
        # logs, opportunity, efficiency, and market counting-stats are required.
        status = str(merged.get("status") or "").strip().upper()
        if not status:
            missing.append("PLAYER_STATUS")
        role = str(merged.get("role") or "").strip()
        if not role:
            missing.append("PLAYER_ROLE")
        logs = merged.get("role_epoch_logs") or merged.get("game_logs")
        log_dicts = [x for x in logs if isinstance(x, dict)] if isinstance(logs, list) else []
        if not isinstance(logs, list) or len(log_dicts) < 3:
            missing.append("ROLE_COMPARABLE_GAME_LOGS_MIN_3")
        opportunity = merged.get("opportunity")
        if not isinstance(opportunity, dict):
            missing.append("OPPORTUNITY_EVIDENCE")
        efficiency = merged.get("efficiency")
        if not isinstance(efficiency, dict):
            missing.append("EFFICIENCY_EVIDENCE")
        family, _league = _league_family(request)
        if _is_basketball_player_request(family, log_dicts) and log_dicts:
            markets = _markets_for_request(request)
            if markets:
                for market in markets:
                    compat = assert_compatible_basketball_logs(log_dicts, market=market)
                    for code in compat.get("missing") or []:
                        if code not in missing:
                            missing.append(code)
            else:
                compat = assert_compatible_basketball_logs(log_dicts, market="")
                for code in compat.get("missing") or []:
                    if code not in missing:
                        missing.append(code)
        elif family in {"gridiron", "football"} and log_dicts:
            markets = _markets_for_request(request)
            if markets:
                for market in markets:
                    compat = assert_compatible_gridiron_logs(log_dicts, market=market)
                    for code in compat.get("missing") or []:
                        if code not in missing:
                            missing.append(code)
            else:
                compat = assert_compatible_gridiron_logs(log_dicts, market="")
                for code in compat.get("missing") or []:
                    if code not in missing:
                        missing.append(code)
        missing.extend(_schema_missing(request, merged, values, scope))
    elif scope == "MARKET_DEFINITION":
        if merged.get("definition_verified") is not True:
            missing.append("VERIFIED_MARKET_DEFINITION")
    elif scope == "MARKET":
        # Legacy fallback only — validated if a leftover MARKET request exists.
        if merged.get("definition_verified") is not True:
            missing.append("VERIFIED_MARKET_DEFINITION")
    elif scope == "OFFER":
        if not merged:
            missing.append("OFFER_CONTEXT")
        elif merged.get("offer_recorded") is False:
            missing.append("OFFER_CONTEXT")
    elif scope == "SPORT":
        if not merged:
            missing.append("SPORT_CONTEXT")
    elif scope == "COMPETITION":
        if not merged or not (merged.get("competition_context") or merged.get("league") or merged.get("rules")):
            if not merged:
                missing.append("COMPETITION_CONTEXT")
    elif scope == "EVENT":
        missing.extend(_event_missing(request, merged, values))
        missing.extend(_schema_missing(request, merged, values, scope))
    elif scope in AFFILIATION_SCOPES | {"TEAM"}:
        missing.extend(_team_missing(request, merged, values))
        missing.extend(_schema_missing(request, merged, values, scope))
    elif scope in COUNTERPARTY_SCOPES:
        missing.extend(_team_missing(request, merged, values))
        missing.extend(_schema_missing(request, merged, values, scope))
    elif scope == "ENVIRONMENT":
        missing.extend(_schema_missing(request, merged, values, scope))

    return {
        "requestId": request.get("request_id"),
        "scope": scope,
        "scopeId": request.get("scope_id"),
        "need": request.get("need"),
        "complete": not missing,
        "missing": missing,
        "claimCount": len(values),
    }


def coverage_report(requests: list[dict[str, Any]], claims: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [evaluate_request(req, claims) for req in requests]
    incomplete = [row for row in rows if not row["complete"]]
    return {
        "complete": not incomplete,
        "requested": len(rows),
        "completeRequests": len(rows) - len(incomplete),
        "incompleteRequests": len(incomplete),
        "missingRequirementCount": sum(len(row["missing"]) for row in incomplete),
        "requests": rows,
    }
