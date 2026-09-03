"""Evidence -> player/event parameter snapshot.

Opportunity and efficiency are deliberately separate. Production selection
requires non-synthetic evidence, a verified market definition, and support for
both opportunity and efficiency. Small samples shrink toward declared priors.

Website/HTML parsing lives in dcm.research.adapters. This module consumes
already-normalized logs (aliases via gamelog.normalize_basketball_logs /
gridiron_gamelog.normalize_gridiron_logs) and never parses host pages inline.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.model.basketball_efficiency import EfficiencyModel
from dcm.model.basketball_opportunity import OpportunityModel
from dcm.model.gridiron_models import (
    GridironEfficiencyModel,
    GridironOpportunityModel,
    TeamEventModel,
)
from dcm.model.availability import availability_mixture
from dcm.model.participation import ParticipationModel
from dcm.research.classify import market_definition_id
from dcm.research.gamelog import normalize_basketball_logs
from dcm.research.gridiron_gamelog import normalize_gridiron_logs
from dcm.research.role_epoch import RoleEpochBuilder
from dcm.research.scopes import claims_for
from dcm.sports.football.research_requirements import assess_football_support


def _f(v: Any, default: float) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _pairs(claims: list[dict], scope: str, scope_id: str) -> list[tuple[dict, dict]]:
    out = []
    for c in claims_for(claims, scope, scope_id):
        if isinstance(c.get("claim_value"), dict):
            out.append((c, c["claim_value"]))
    return sorted(out, key=lambda x: str(x[0].get("observed_at") or ""))


def _merge(pairs: list[tuple[dict, dict]]) -> dict:
    out: dict[str, Any] = {}
    for _, value in pairs:
        out.update(value)
    return out


def _avg(logs: list[dict], key: str) -> tuple[float | None, int]:
    vals = []
    for r in logs:
        try:
            x = float(r[key])
            if math.isfinite(x):
                vals.append(x)
        except (KeyError, TypeError, ValueError):
            pass
    return (mean(vals), len(vals)) if vals else (None, 0)


def _sd(logs: list[dict], key: str, fallback: float) -> float:
    vals = []
    for r in logs:
        try:
            vals.append(float(r[key]))
        except (KeyError, TypeError, ValueError):
            pass
    return pstdev(vals) if len(vals) >= 2 else fallback


def _shrink(sample: float | None, n: int, prior: float, prior_n: float = 5.0) -> float:
    if sample is None or n <= 0:
        return prior
    return (sample * n + prior * prior_n) / (n + prior_n)


def build_parameter_snapshot(
    row: dict[str, Any],
    claims: list[dict[str, Any]],
    *,
    team_packets: dict[str, dict[str, Any]] | None = None,
    event_packets: dict[str, dict[str, Any]] | None = None,
    opponent_packets: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    player_pairs = _pairs(claims, "SUBJECT", str(row.get("playerId") or row.get("subjectId") or ""))
    team_pairs = _pairs(claims, "AFFILIATION", str(row.get("teamId") or row.get("affiliationId") or ""))
    opp_pairs = _pairs(claims, "COUNTERPARTY", str(row.get("opponentId") or row.get("opponent") or ""))
    event_pairs = _pairs(claims, "EVENT", str(row.get("eventId") or ""))
    env_pairs = _pairs(claims, "ENVIRONMENT", f"env:{row.get('eventId') or ''}")
    sport_id = f"{row.get('sportFamily') or ''}:{row.get('league') or ''}"
    sport_pairs = _pairs(claims, "SPORT", sport_id)
    competition_pairs = _pairs(claims, "COMPETITION", sport_id)
    def_id = market_definition_id(row)
    def_pairs = _pairs(claims, "MARKET_DEFINITION", def_id)
    offer_pairs = _pairs(claims, "OFFER", str(row.get("projectionId") or ""))
    legacy_market_pairs = _pairs(claims, "MARKET", str(row.get("projectionId") or ""))
    # MARKET_DEFINITION + OFFER are canonical. Legacy MARKET is a migration fallback only.
    if def_pairs:
        market_pairs = def_pairs
        market = {**_merge(legacy_market_pairs), **_merge(offer_pairs), **_merge(def_pairs)}
        used_legacy_market = False
    elif offer_pairs:
        market_pairs = offer_pairs
        market = {**_merge(legacy_market_pairs), **_merge(offer_pairs)}
        used_legacy_market = bool(legacy_market_pairs) and not def_pairs
    else:
        market_pairs = legacy_market_pairs
        market = _merge(legacy_market_pairs)
        used_legacy_market = bool(legacy_market_pairs)
    player, team, event, sport = map(_merge, (player_pairs, team_pairs, event_pairs, sport_pairs))
    counterparty = _merge(opp_pairs)
    environment = _merge(env_pairs)
    competition = _merge(competition_pairs)
    if environment:
        event = {**event, **{k: v for k, v in environment.items() if v is not None}}
    if competition:
        sport = {**sport, **{k: v for k, v in competition.items() if k not in sport}}
    if counterparty:
        team = {**team, **{k: v for k, v in counterparty.items() if k not in team or team.get(k) in (None, "", 1.0)}}
    team_evidence_used = False
    opp_id = str(row.get("opponentId") or row.get("opponent") or "")
    team_id = str(row.get("teamId") or row.get("team") or "")
    event_id = str(row.get("eventId") or "")
    if team_packets:
        tp = team_packets.get(team_id) or team_packets.get(str(row.get("team") or ""))
        if tp and tp.get("evidenceUsed"):
            team = {**team, **dict(tp.get("parameterFields") or {})}
            team_evidence_used = True
            team["teamPacketHash"] = tp.get("contentHash")
            team["priorUsedAsResearch"] = False
        elif tp:
            team["teamPacketHash"] = tp.get("contentHash")
            team["priorUsedAsResearch"] = False
            team["teamEvidenceUsed"] = False
        if opp_id:
            op_team = team_packets.get(opp_id)
            if op_team and op_team.get("evidenceUsed"):
                team["opponent"] = dict(op_team.get("parameterFields") or {})
                event["opponent"] = dict(op_team.get("parameterFields") or {})
    if opponent_packets:
        for op in opponent_packets.values() if isinstance(opponent_packets, dict) else []:
            if str(op.get("teamId") or "") == opp_id and str(op.get("eventId") or "") in {event_id, str(op.get("eventId") or "")}:
                if op.get("evidenceUsed"):
                    event["opponent"] = {**(event.get("opponent") if isinstance(event.get("opponent"), dict) else {}), **dict(op.get("parameterFields") or {})}
                    break
    if event_packets:
        ep = event_packets.get(event_id)
        if ep and ep.get("evidenceUsed"):
            event = {**event, **dict(ep.get("parameterFields") or {})}
            event["eventPacketHash"] = ep.get("contentHash")

    claim_pairs = list(
        player_pairs + team_pairs + opp_pairs + event_pairs + env_pairs + sport_pairs + competition_pairs + def_pairs + offer_pairs
    )
    if used_legacy_market or not (def_pairs or offer_pairs):
        claim_pairs.extend(legacy_market_pairs)
    all_claims = [c for c, _ in claim_pairs]
    synthetic = any(str(c.get("source_id") or "").upper().startswith("FIXTURE_") or bool(c.get("synthetic")) for c in all_claims)
    rel = mean([_f(c.get("reliability"), 0.0) for c in all_claims]) if all_claims else 0.0
    fresh = mean([_f(c.get("freshness"), 0.0) for c in all_claims]) if all_claims else 0.0
    logs = player.get("role_epoch_logs") or player.get("game_logs") or []
    logs = [r for r in logs if isinstance(r, dict)] if isinstance(logs, list) else []
    opp = player.get("opportunity") if isinstance(player.get("opportunity"), dict) else {}
    eff = player.get("efficiency") if isinstance(player.get("efficiency"), dict) else {}
    family = str(row.get("sportFamily") or "")
    params: dict[str, Any] = {"family": family}
    opp_n = int(_f(opp.get("support_n"), len(logs)))
    eff_n = int(_f(eff.get("support_n"), len(logs)))

    logs_normalized = 0
    logs_rejected = 0
    evidence_used = False
    opportunity_support_from_logs = 0
    minutes_source = "PRIOR"

    role_epoch_summary: dict[str, Any] | None = None
    shrinkage_out = {"roleWeight": 0.0, "seasonWeight": 0.0, "priorWeight": 1.0}
    participation_state: dict[str, Any] | None = None
    football_support: dict[str, Any] | None = None

    if family == "basketball":
        league = str(row.get("league") or "") or None
        norm = normalize_basketball_logs(logs, league=league)
        full_logs = norm["logs"]
        logs_normalized = len(full_logs)
        logs_rejected = len(norm["rejected"])
        today_context = {
            "role": player.get("role"),
            "projected_role": player.get("projected_role") or player.get("role"),
            "status": player.get("status"),
            "teammate_out": player.get("teammate_out") or event.get("teammate_out"),
            "league": league,
        }
        role_epoch = RoleEpochBuilder().build(player, claims=all_claims, today_context=today_context)
        comparable_raw = role_epoch.get("comparable_logs") or []
        if comparable_raw:
            comp_norm = normalize_basketball_logs(comparable_raw, league=league)
            comparable = comp_norm["logs"] or full_logs
        else:
            comparable = full_logs
        shrinkage_out = dict(role_epoch.get("shrinkage") or shrinkage_out)
        role_support = int(role_epoch.get("support_n") or 0)
        minutes, mn = _avg(comparable, "minutes")
        fga, fn = _avg(comparable, "fga")
        tpa, tn = _avg(comparable, "tpa")
        fta, ftan = _avg(comparable, "fta")
        reb, rn = _avg(comparable, "reb")
        ast, an = _avg(comparable, "ast")
        opportunity_support_from_logs = mn
        # Thin role-comparable sample is not opportunity evidence by itself.
        if mn >= 3 and minutes is not None:
            evidence_used = True
            minutes_source = "LOGS"
            opp_n = max(opp_n, mn)
        elif mn > 0 and minutes is not None:
            evidence_used = False
            minutes_source = "LOGS"
            opp_n = mn
        else:
            # Labeled PRIOR for engineering only. Do not treat generic minutes as
            # player research, and do not let claimed support_n paper over mn==0.
            evidence_used = False
            minutes_source = "PRIOR"
            opp_n = 0
        pace = _f(team.get("pace_multiplier"), 1.0) * _f(event.get("pace_multiplier"), 1.0)
        matchup = _f(team.get("matchup_efficiency_multiplier"), 1.0) * _f(event.get("matchup_efficiency_multiplier"), 1.0)
        if team.get("ortg") is not None:
            params["ortg"] = _f(team.get("ortg"), 0.0)
        if team.get("drtg") is not None:
            params["drtg"] = _f(team.get("drtg"), 0.0)
        opp_ctx = event.get("opponent") if isinstance(event.get("opponent"), dict) else {}
        if opp_ctx.get("ortg") is not None:
            params["opponent_ortg"] = _f(opp_ctx.get("ortg"), 0.0)
        if opp_ctx.get("drtg") is not None:
            params["opponent_drtg"] = _f(opp_ctx.get("drtg"), 0.0)
        params["teamEvidenceUsed"] = bool(team_evidence_used)
        params["paceFromTeamPacket"] = bool(team_evidence_used and team.get("pace_multiplier") is not None)

        role_multiplier = _f(opp.get("role_multiplier"), 1.0)
        part_fit = ParticipationModel().fit(
            comparable,
            family="basketball",
            league=league,
            shrinkage=shrinkage_out,
            role_multiplier=role_multiplier,
            support_n=role_support,
            season_logs=full_logs,
        )
        participation_state = part_fit
        opp_fit = OpportunityModel().fit(
            comparable,
            season_logs=full_logs,
            pace=pace,
            shrinkage=shrinkage_out,
            league=league,
            role_multiplier=role_multiplier,
            support_n=role_support,
            participation=part_fit,
        )
        eff_fit = EfficiencyModel().fit(
            comparable,
            matchup=matchup,
            shrinkage=shrinkage_out,
            league=league,
        )
        if opp.get("minutes_mean") is not None:
            mm = _f(opp.get("minutes_mean"), opp_fit["minutes_mean"]) * role_multiplier
        else:
            mm = opp_fit["minutes_mean"]

        def _rate_claimed(claim_map: dict, key: str, fitted: float, mul: float = 1.0) -> float:
            if key in claim_map and claim_map.get(key) is not None:
                return _f(claim_map.get(key), fitted) * mul
            return fitted

        params.update({
            "minutes_mean": mm,
            "minutes_sd": max(0.75, _f(opp.get("minutes_sd"), opp_fit["minutes_sd"])),
            "fga_per_min": max(0.01, _rate_claimed(eff, "fga_per_min", opp_fit["fga_per_min"], pace)),
            "three_pa_share": max(0.0, min(1.0, _rate_claimed(eff, "three_pa_share", opp_fit["three_pa_share"]))),
            "two_fg_pct": max(0.05, min(0.95, _rate_claimed(eff, "two_fg_pct", eff_fit["two_fg_pct"], matchup if "two_fg_pct" in eff else 1.0))),
            "three_fg_pct": max(0.05, min(0.80, _rate_claimed(eff, "three_fg_pct", eff_fit["three_fg_pct"], matchup if "three_fg_pct" in eff else 1.0))),
            "fta_per_min": max(0.0, _rate_claimed(eff, "fta_per_min", opp_fit["fta_per_min"], pace)),
            "ft_pct": max(0.2, min(1.0, _rate_claimed(eff, "ft_pct", eff_fit["ft_pct"]))),
            "reb_per_min": max(0.0, _rate_claimed(eff, "reb_per_min", opp_fit["reb_per_min"], pace)),
            "ast_per_min": max(0.0, _rate_claimed(eff, "ast_per_min", opp_fit["ast_per_min"], pace)),
            "stl_per_min": max(0.0, _f(eff.get("stl_per_min"), opp_fit["stl_per_min"]) if "stl_per_min" in eff else opp_fit["stl_per_min"]),
            "blk_per_min": max(0.0, _f(eff.get("blk_per_min"), opp_fit["blk_per_min"]) if "blk_per_min" in eff else opp_fit["blk_per_min"]),
            "tov_per_min": max(0.0, _f(eff.get("tov_per_min"), opp_fit["tov_per_min"]) if "tov_per_min" in eff else opp_fit["tov_per_min"]),
            "priorWeight": shrinkage_out.get("priorWeight"),
            "playerWeight": shrinkage_out.get("seasonWeight"),
            "roleWeight": shrinkage_out.get("roleWeight"),
            "opportunityInputHash": opp_fit.get("inputHash"),
            "efficiencyInputHash": eff_fit.get("inputHash"),
            "participationInputHash": part_fit.get("inputHash"),
            "_log_support": {
                "logsNormalized": logs_normalized,
                "logsRejected": logs_rejected,
                "evidenceUsed": evidence_used,
                "opportunitySupportFromLogs": opportunity_support_from_logs,
                "minutesSource": minutes_source,
                "roleSupportN": role_support,
                "selectedEpoch": (role_epoch.get("selected_epoch") or {}).get("label"),
            },
        })
        role_epoch_summary = {
            "builder": role_epoch.get("builder"),
            "selected_epoch": role_epoch.get("selected_epoch"),
            "support_n": role_support,
            "shrinkage": shrinkage_out,
            "invented": False,
            "epochCount": len(role_epoch.get("epochs") or []),
            "projectedRole": role_epoch.get("projectedRole"),
        }
        logs = comparable
        eff_n = max(eff_n, fn, rn, an, int(eff_fit.get("support_n") or 0))
    elif family == "gridiron":
        league = str(row.get("league") or "") or None
        role = str(player.get("role") or row.get("role") or "QB").upper()
        params["role"] = role
        norm = normalize_gridiron_logs(logs, league=league)
        full_logs = norm["logs"]
        logs_normalized = len(full_logs)
        logs_rejected = len(norm["rejected"])
        today_context = {
            "role": player.get("role") or role,
            "projected_role": player.get("projected_role") or player.get("role") or role,
            "status": player.get("status"),
            "league": league,
            "sportFamily": "gridiron",
            "qb_id": player.get("qb_id"),
        }
        role_epoch = RoleEpochBuilder().build(player, claims=all_claims, today_context=today_context)
        comparable_raw = role_epoch.get("comparable_logs") or []
        if comparable_raw:
            comp_norm = normalize_gridiron_logs(comparable_raw, league=league)
            comparable = comp_norm["logs"] or full_logs
        else:
            comparable = full_logs
        shrinkage_out = dict(role_epoch.get("shrinkage") or shrinkage_out)
        role_support = int(role_epoch.get("support_n") or 0)
        opponent = event.get("opponent") if isinstance(event.get("opponent"), dict) else {}
        if not opponent and isinstance(team.get("opponent"), dict):
            opponent = team["opponent"]
        team_event = TeamEventModel().fit(
            team, event, opponent, league=league, market=str(row.get("market") or ""),
        )
        pace = _f(team_event.get("pace"), 1.0)
        matchup = _f(team.get("matchup_efficiency_multiplier"), 1.0) * _f(event.get("matchup_efficiency_multiplier"), 1.0)
        part_fit = ParticipationModel().fit(
            comparable,
            family="gridiron",
            league=league,
            shrinkage=shrinkage_out,
            support_n=role_support,
            season_logs=full_logs,
            role=role,
        )
        participation_state = part_fit
        opp_fit = GridironOpportunityModel().fit(
            comparable,
            season_logs=full_logs,
            pace=pace,
            shrinkage=shrinkage_out,
            league=league,
            role=role,
            support_n=role_support,
            team_plays=team_event.get("plays"),
            pass_rate=team_event.get("pass_rate"),
            participation=part_fit,
        )
        eff_fit = GridironEfficiencyModel().fit(
            comparable,
            matchup=matchup,
            shrinkage=shrinkage_out,
            league=league,
            role=role,
            pass_defense=team_event.get("pass_defense"),
            rush_defense=team_event.get("rush_defense"),
        )
        opportunity_support_from_logs = int(opp_fit.get("support_n") or 0)
        if opportunity_support_from_logs >= 3:
            evidence_used = True
            minutes_source = "LOGS"
            opp_n = max(opp_n, opportunity_support_from_logs)
        elif opportunity_support_from_logs > 0:
            evidence_used = False
            minutes_source = "LOGS"
            opp_n = opportunity_support_from_logs
        else:
            evidence_used = False
            minutes_source = "PRIOR"
            opp_n = 0
        params.update({k: v for k, v in opp_fit.items() if k not in {"shrinkage", "inputHash", "logSupport", "definition_version"}})
        params.update({k: v for k, v in eff_fit.items() if k not in {"shrinkage", "inputHash", "makesAttemptedSupport", "definition_version", "role"}})
        params["role"] = role
        params["team_plays"] = team_event.get("plays")
        params["pass_rate"] = team_event.get("pass_rate")
        params["rush_rate"] = team_event.get("rush_rate")
        params["pace"] = team_event.get("pace")
        params["pass_defense"] = team_event.get("pass_defense")
        params["rush_defense"] = team_event.get("rush_defense")
        params["league"] = league
        params["consensus_spread"] = team_event.get("consensus_spread")
        params["game_total"] = team_event.get("game_total")
        params["event_regime_weights"] = team_event.get("event_regime_weights")
        params["starter_curtailment"] = team_event.get("starter_curtailment")
        params["priorWeight"] = shrinkage_out.get("priorWeight")
        params["playerWeight"] = shrinkage_out.get("seasonWeight")
        params["roleWeight"] = shrinkage_out.get("roleWeight")
        params["opportunityInputHash"] = opp_fit.get("inputHash")
        params["efficiencyInputHash"] = eff_fit.get("inputHash")
        params["participationInputHash"] = part_fit.get("inputHash")
        params["_log_support"] = {
            "logsNormalized": logs_normalized,
            "logsRejected": logs_rejected,
            "evidenceUsed": evidence_used,
            "opportunitySupportFromLogs": opportunity_support_from_logs,
            "minutesSource": minutes_source,
            "roleSupportN": role_support,
            "selectedEpoch": (role_epoch.get("selected_epoch") or {}).get("label"),
            "teamEventMissing": list(team_event.get("missing") or []),
        }
        role_epoch_summary = {
            "builder": role_epoch.get("builder"),
            "selected_epoch": role_epoch.get("selected_epoch"),
            "support_n": role_support,
            "shrinkage": shrinkage_out,
            "invented": False,
            "epochCount": len(role_epoch.get("epochs") or []),
            "projectedRole": role_epoch.get("projectedRole"),
            "mode": "gridiron",
            "qbIdentity": role_epoch.get("qbIdentity"),
        }
        logs = comparable
        eff_n = max(eff_n, int(eff_fit.get("support_n") or 0), opportunity_support_from_logs)
        params["_team_event_blocker"] = team_event.get("playableBlocker")
        football_support = assess_football_support(
            market=str(row.get("market") or ""),
            role=role,
            status=str(player.get("status") or "UNKNOWN"),
            logs=full_logs,
            definition_verified=bool(market.get("definition_verified")),
            team_event=team_event,
        )
        # Market-specific support counts replace generic all-purpose support for
        # guarded-launch decisions. Pure opportunity markets do not require an
        # irrelevant efficiency sample just to be modelable.
        opp_n = int(football_support.get("opportunitySupportN") or 0)
        eff_n = int(football_support.get("efficiencySupportN") or 0)
    elif family == "baseball":
        pa, pan = _avg(logs, "PA")
        params.update({
            "pa_mean": _f(opp.get("pa_mean"), _shrink(pa, pan, 4.2)),
            "pa_sd": max(0.2, _f(opp.get("pa_sd"), _sd(logs, "PA", 0.8))),
            "bb_rate": _f(eff.get("bb_rate"), 0.09), "hbp_rate": _f(eff.get("hbp_rate"), 0.01),
            "sf_rate": _f(eff.get("sf_rate"), 0.02), "sh_rate": _f(eff.get("sh_rate"), 0.005),
            "so_rate": _f(eff.get("so_rate"), 0.24), "hr_rate": _f(eff.get("hr_rate"), 0.04),
            "triple_rate": _f(eff.get("triple_rate"), 0.005), "double_rate": _f(eff.get("double_rate"), 0.05),
            "single_rate": _f(eff.get("single_rate"), 0.15), "run_per_pa": _f(eff.get("run_per_pa"), 0.14),
            "rbi_per_pa": _f(eff.get("rbi_per_pa"), 0.12),
        })
        opp_n = max(opp_n, pan)
        eff_n = max(eff_n, len(logs))

    status = str(player.get("status") or "UNKNOWN").strip().upper()
    definition_verified = bool(market.get("definition_verified"))
    # Sport-level context is consumed for reliability/freshness (via all_claims).
    _ = sport
    active_statuses = {"ACTIVE", "AVAILABLE", "PROBABLE", "EXPECTED_ACTIVE"}
    inactive_statuses = {"OUT", "DNP", "INACTIVE", "SUSPENDED", "IR", "PUP"}
    uncertain_statuses = {"QUESTIONABLE", "GTD", "GAME_TIME_DECISION", "DOUBTFUL", "LIMITED"}
    status_eligible = status in active_statuses
    gridiron_defense_ok = family != "gridiron" or bool((football_support or {}).get("playableSupport"))
    minimum_model_support = (
        bool((football_support or {}).get("modelable"))
        if family == "gridiron"
        else (definition_verified and opp_n >= 1 and eff_n >= 1 and status not in inactive_statuses)
    )
    production_eligible = (
        not synthetic and status_eligible
        and opp_n >= 3 and eff_n >= 3 and definition_verified
        and gridiron_defense_ok
    )
    data_quality = max(0.0, min(1.0, rel * 0.65 + fresh * 0.20 + min(1.0, min(opp_n, eff_n) / 10.0) * 0.15))
    ood = max(0.0, min(1.0, _f(player.get("ood_risk"), 0.15 if min(opp_n, eff_n) >= 5 else 0.45)))
    blocker = None
    if synthetic: blocker = "SYNTHETIC_EVIDENCE_NOT_SELECTABLE"
    elif not definition_verified: blocker = "UNVERIFIED_MARKET_DEFINITION"
    elif status in inactive_statuses: blocker = "PLAYER_NOT_ACTIVE"
    elif status in uncertain_statuses: blocker = "PLAYER_STATUS_UNCERTAIN"
    elif status not in active_statuses: blocker = "PLAYER_STATUS_UNKNOWN"
    elif family == "gridiron" and football_support and football_support.get("playableBlockers"):
        blocker = str(football_support["playableBlockers"][0])
    elif opp_n < 3: blocker = "INSUFFICIENT_OPPORTUNITY_SAMPLE"
    elif eff_n < 3: blocker = "INSUFFICIENT_EFFICIENCY_SAMPLE"
    elif family == "gridiron" and params.get("_team_event_blocker"):
        blocker = str(params.get("_team_event_blocker"))

    role = str(player.get("role") or row.get("role") or "UNKNOWN")
    tags = {f"EVENT:{row.get('eventId')}", f"TEAM:{row.get('teamId')}", f"ROLE:{row.get('teamId')}:{role}"}
    if player.get("qb_id"): tags.add(f"QBUNIT:{row.get('teamId')}:{player['qb_id']}")
    if player.get("injury_dependency_id"): tags.add(f"INJURY:{player['injury_dependency_id']}")
    if event.get("weather_state_hash"): tags.add(f"WEATHER:{event['weather_state_hash']}")
    snapshot = {
        "playerId": row.get("playerId"), "eventId": row.get("eventId"), "market": row.get("market"),
        "status": status, "role": role, "opportunity": {"support_n": opp_n}, "efficiency": {"support_n": eff_n},
        "parameters": params, "reliability": rel, "freshness": fresh, "data_quality": data_quality,
        "ood_risk": ood, "synthetic": synthetic, "definition_verified": definition_verified,
        "minimum_model_support": minimum_model_support,
        "model_support": football_support if family == "gridiron" else None,
        "production_eligible": production_eligible, "blocker": blocker, "dependency_tags": sorted(tags),
        "evidence_hashes": sorted(str(c.get("claim_hash") or "") for c in all_claims if c.get("claim_hash")),
        "scopes_used": sorted({
            *(["SPORT"] if sport_pairs else []),
            *(["COMPETITION"] if competition_pairs else []),
            *(["EVENT"] if event_pairs else []),
            *(["ENVIRONMENT"] if env_pairs else []),
            *(["AFFILIATION"] if team_pairs else []),
            *(["COUNTERPARTY"] if opp_pairs else []),
            *(["SUBJECT"] if player_pairs else []),
            *(["TEAM"] if team_pairs else []),
            *(["PLAYER"] if player_pairs else []),
            *(["MARKET_DEFINITION"] if def_pairs else []),
            *(["OFFER"] if offer_pairs else []),
            *(["MARKET"] if used_legacy_market else []),
        }),
        "legacy_market_fallback": used_legacy_market,
        "priorWeight": shrinkage_out.get("priorWeight"),
        "playerWeight": shrinkage_out.get("seasonWeight"),
        "roleWeight": shrinkage_out.get("roleWeight"),
        "teamEvidenceUsed": bool(team_evidence_used),
        "teamPriorUsedAsResearch": False,
        "availabilityMixture": availability_mixture(status),
        "layers": {
            "subject": {
                "subjectId": row.get("playerId") or row.get("subjectId"),
                "status": status,
                "role": role,
            },
            "affiliation": {
                "affiliationId": row.get("teamId") or row.get("affiliationId"),
                "evidenceUsed": bool(team_evidence_used),
            },
            "counterparty": {
                "counterpartyId": row.get("opponentId") or row.get("opponent"),
            },
            "event": {"eventId": row.get("eventId")},
            "environment": {k: environment.get(k) for k in ("weather", "surface", "venue", "environment") if k in environment} if environment else {},
            "market": {
                "definition_verified": definition_verified,
                "legacy_market_fallback": used_legacy_market,
            },
            "availability": availability_mixture(status),
            "participation": {
                "unit": (participation_state or {}).get("unit"),
                "mean": (participation_state or {}).get("mean"),
                "source": (participation_state or {}).get("source"),
                "inputHash": (participation_state or {}).get("inputHash"),
            } if participation_state else {},
            "opportunity": {"support_n": opp_n, "inputHash": params.get("opportunityInputHash")},
            "efficiency": {"support_n": eff_n, "inputHash": params.get("efficiencyInputHash")},
            "lineage": {
                "evidenceHashes": sorted(str(c.get("claim_hash") or "") for c in all_claims if c.get("claim_hash")),
                "participationInputHash": params.get("participationInputHash"),
                "opportunityInputHash": params.get("opportunityInputHash"),
                "efficiencyInputHash": params.get("efficiencyInputHash"),
            },
        },
    }
    if role_epoch_summary is not None:
        snapshot["role_epoch"] = role_epoch_summary
    if participation_state is not None:
        snapshot["participation"] = {
            "unit": participation_state.get("unit"),
            "mean": participation_state.get("mean"),
            "sd": participation_state.get("sd"),
            "source": participation_state.get("source"),
            "support_n": participation_state.get("support_n"),
            "inputHash": participation_state.get("inputHash"),
            "definition_version": participation_state.get("definition_version"),
        }
    for key in ("minutes_mean", "minutes_sd", "pass_att_mean", "pass_att_sd", "rush_att_mean", "rush_att_sd", "routes_mean", "routes_sd", "pa_mean", "pa_sd"):
        if key in params:
            snapshot["opportunity"][key] = params[key]
    snapshot["parameter_snapshot_hash"] = content_hash(snapshot)
    return snapshot
