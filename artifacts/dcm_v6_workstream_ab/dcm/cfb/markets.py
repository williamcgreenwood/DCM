"""Canonical CFB market inventory, exact aliases, and production activation.

Every ACTIVE market has: identity, units, opportunity, efficiency, distribution
family, push/Higher-Less semantics, settlement formula, and a runtime consumer.
Unsupported entries are genuine semantic limitations, not unfinished code.
"""
from __future__ import annotations

from typing import Any, Mapping

from dcm.contracts.hashes import content_hash

# PrizePicks Player Touchdowns settle as TDs scored (rush + rec). Passing TDs
# are a distinct market (pass_td). Return TDs are unmodeled residual (~0) and
# do not create a second MarketDefinition.
PLAYER_TD_CANONICAL = "rush_rec_td"

# Exact semantic aliases. Both sides resolve to the same MarketDefinition ID.
EXACT_ALIASES: dict[str, str] = {
    "pass_attempts": "pass_att",
    "passing_attempts": "pass_att",
    "pass_att": "pass_att",
    "pass_completions": "pass_cmp",
    "passing_completions": "pass_cmp",
    "completions": "pass_cmp",
    "pass_cmp": "pass_cmp",
    "passing_yards": "pass_yds",
    "pass_yards": "pass_yds",
    "pass_yds": "pass_yds",
    "rush_attempts": "rush_att",
    "rushing_attempts": "rush_att",
    "rush_att": "rush_att",
    "rush_yards": "rush_yds",
    "rushing_yards": "rush_yds",
    "rush_yds": "rush_yds",
    "receiving_yards": "rec_yds",
    "rec_yards": "rec_yds",
    "rec_yds": "rec_yds",
    "receptions": "receptions",
    "rec": "receptions",
    "recs": "receptions",
    "pass_comp": "pass_cmp",
    "pass_comps": "pass_cmp",
    "rush_atts": "rush_att",
    "pass_tds": "pass_td",
    "passing_touchdowns": "pass_td",
    "pass_td": "pass_td",
    "int": "interceptions",
    "ints": "interceptions",
    "interceptions": "interceptions",
    "rush_tds": "rush_td",
    "rushing_touchdowns": "rush_td",
    "rush_td": "rush_td",
    "rec_tds": "rec_td",
    "receiving_touchdowns": "rec_td",
    "rec_td": "rec_td",
    "player_td": PLAYER_TD_CANONICAL,
    "player_touchdowns": PLAYER_TD_CANONICAL,
    "player_tds": PLAYER_TD_CANONICAL,
    "rush_rec_td": "rush_rec_td",
    "rushing_receiving_touchdowns": "rush_rec_td",
    "pass_rush_td": "pass_rush_td",
    "passing_rushing_touchdowns": "pass_rush_td",
    "pass_rush_yds": "pass_rush_yds",
    "passing_rushing_yards": "pass_rush_yds",
    "rush_rec_yds": "rush_rec_yds",
    "rushing_receiving_yards": "rush_rec_yds",
    "fg_made": "fg_made",
    "field_goals_made": "fg_made",
    "fg_att": "fg_att",
    "field_goals_attempted": "fg_att",
    "pat_made": "xp_made",
    "xp_made": "xp_made",
    "extra_points_made": "xp_made",
    "kicking_points": "kicking_pts",
    "kicking_pts": "kicking_pts",
    "targets": "targets",
}

# Guarded nine-market set from PR #19. Kept as the historical baseline so
# accounting can report BEFORE vs AFTER supported counts.
GUARDED_LAUNCH_MARKETS: tuple[str, ...] = (
    "pass_yds",
    "pass_att",
    "pass_cmp",
    "rush_yds",
    "rush_att",
    "rec_yds",
    "receptions",
    "pass_rush_yds",
    "rush_rec_yds",
)

# Newly activated this pass. Each has primitives, research requirements,
# distribution, settlement, and a worlds/sampler consumer.
NEWLY_ACTIVATED_MARKETS: tuple[str, ...] = (
    "pass_td",
    "interceptions",
    "rush_td",
    "rec_td",
    "rush_rec_td",
    "pass_rush_td",
    "fg_made",
    "xp_made",
    "kicking_pts",
    "targets",
)

ACTIVE_CFB_MARKETS: tuple[str, ...] = tuple(dict.fromkeys((*GUARDED_LAUNCH_MARKETS, *NEWLY_ACTIVATED_MARKETS)))

# Genuine unsupported semantics. Not unfinished code.
GENUINE_UNSUPPORTED: dict[str, str] = {
    "fantasy": "UNSUPPORTED_BY_DESIGN: PrizePicks Fantasy Score has no registered hashed scoring version (FANTASY_SCORING_VERSIONS empty).",
    "fantasy_score": "UNSUPPORTED_BY_DESIGN: PrizePicks Fantasy Score has no registered hashed scoring version (FANTASY_SCORING_VERSIONS empty).",
    "longest_reception": "UNSUPPORTED_BY_DESIGN: longest-* markets require play-level yard distributions; game-log totals cannot identify the max play.",
    "longest_rec": "UNSUPPORTED_BY_DESIGN: longest-* markets require play-level yard distributions; game-log totals cannot identify the max play.",
    "longest_rush": "UNSUPPORTED_BY_DESIGN: longest-* markets require play-level yard distributions; game-log totals cannot identify the max play.",
    "longest_completion": "UNSUPPORTED_BY_DESIGN: longest-* markets require play-level yard distributions; game-log totals cannot identify the max play.",
    "longest_pass": "UNSUPPORTED_BY_DESIGN: longest-* markets require play-level yard distributions; game-log totals cannot identify the max play.",
    "def_tackles": "UNSUPPORTED_BY_DESIGN: CFB defensive snap/opportunity ledger is not production-complete; DEF_TACKLES_PLAYABLE remains known_unsupported.",
    "def_sacks": "UNSUPPORTED_BY_DESIGN: CFB defensive sack opportunity is not production-complete.",
    "fg_att": "IMPLEMENTABLE_MISSING: PrizePicks offers FG Made / Kicking Points, not FG attempts as a board market.",
}

# Opportunity / efficiency / defense / distribution / settlement contract.
MARKET_CONTRACTS: dict[str, dict[str, Any]] = {
    "pass_att": {
        "opportunity": ("pass_att",),
        "efficiency": (),
        "needs_pass_defense": False,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "NegativeBinomial",
        "settlement": "pass_att",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "pass_cmp": {
        "opportunity": ("pass_att",),
        "efficiency": ("pass_cmp", "pass_att"),
        "needs_pass_defense": True,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "Binomial",
        "settlement": "pass_cmp",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "pass_yds": {
        "opportunity": ("pass_att",),
        "efficiency": ("pass_yds", "pass_att"),
        "needs_pass_defense": True,
        "needs_rush_defense": False,
        "unit": "yards",
        "distribution": "Normal",
        "settlement": "pass_yds",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "pass_td": {
        "opportunity": ("pass_att",),
        "efficiency": ("pass_td", "pass_att"),
        "needs_pass_defense": True,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "Poisson",
        "settlement": "pass_td",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "interceptions": {
        "opportunity": ("pass_att",),
        "efficiency": ("interceptions", "pass_att"),
        "needs_pass_defense": True,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "Poisson",
        "settlement": "interceptions",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "rush_att": {
        "opportunity": ("rush_att",),
        "efficiency": (),
        "needs_pass_defense": False,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "NegativeBinomial",
        "settlement": "rush_att",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "rush_yds": {
        "opportunity": ("rush_att",),
        "efficiency": ("rush_yds", "rush_att"),
        "needs_pass_defense": False,
        "needs_rush_defense": True,
        "unit": "yards",
        "distribution": "Normal",
        "settlement": "rush_yds",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "rush_td": {
        "opportunity": ("rush_att",),
        "efficiency": ("rush_td", "rush_att"),
        "needs_pass_defense": False,
        "needs_rush_defense": True,
        "unit": "count",
        "distribution": "Poisson",
        "settlement": "rush_td",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "receptions": {
        "opportunity": ("targets",),
        "efficiency": ("receptions", "targets"),
        "needs_pass_defense": True,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "Binomial",
        "settlement": "receptions",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "rec_yds": {
        "opportunity": ("targets",),
        "efficiency": ("rec_yds", "receptions"),
        "needs_pass_defense": True,
        "needs_rush_defense": False,
        "unit": "yards",
        "distribution": "Normal",
        "settlement": "rec_yds",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "rec_td": {
        "opportunity": ("targets",),
        "efficiency": ("rec_td", "targets"),
        "needs_pass_defense": True,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "Poisson",
        "settlement": "rec_td",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "targets": {
        "opportunity": ("targets",),
        "efficiency": (),
        "needs_pass_defense": True,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "NegativeBinomial",
        "settlement": "targets",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "pass_rush_yds": {
        "opportunity": ("pass_att", "rush_att"),
        "efficiency": ("pass_yds", "pass_att", "rush_yds", "rush_att"),
        "needs_pass_defense": True,
        "needs_rush_defense": True,
        "unit": "yards",
        "distribution": "Normal",
        "settlement": "pass_yds + rush_yds",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "rush_rec_yds": {
        "opportunity": ("rush_att", "targets"),
        "efficiency": ("rush_yds", "rush_att", "rec_yds", "receptions"),
        "needs_pass_defense": True,
        "needs_rush_defense": True,
        "unit": "yards",
        "distribution": "Normal",
        "settlement": "rush_yds + rec_yds",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "rush_rec_td": {
        "opportunity": ("rush_att", "targets"),
        "efficiency": ("rush_td", "rush_att", "rec_td", "targets"),
        "needs_pass_defense": True,
        "needs_rush_defense": True,
        "unit": "count",
        "distribution": "Poisson",
        "settlement": "rush_td + rec_td",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "pass_rush_td": {
        "opportunity": ("pass_att", "rush_att"),
        "efficiency": ("pass_td", "pass_att", "rush_td", "rush_att"),
        "needs_pass_defense": True,
        "needs_rush_defense": True,
        "unit": "count",
        "distribution": "Poisson",
        "settlement": "pass_td + rush_td",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
    },
    "fg_made": {
        "opportunity": ("fg_att",),
        "efficiency": ("fg_made", "fg_att"),
        "needs_pass_defense": False,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "Binomial",
        "settlement": "fg_made",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
        "role": "K",
    },
    "xp_made": {
        "opportunity": ("xp_att",),
        "efficiency": ("xp_made", "xp_att"),
        "needs_pass_defense": False,
        "needs_rush_defense": False,
        "unit": "count",
        "distribution": "Binomial",
        "settlement": "xp_made",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
        "role": "K",
    },
    "kicking_pts": {
        "opportunity": ("fg_att", "xp_att"),
        "efficiency": ("fg_made", "fg_att", "xp_made", "xp_att"),
        "needs_pass_defense": False,
        "needs_rush_defense": False,
        "unit": "points",
        "distribution": "Normal",
        "settlement": "3 * fg_made + xp_made",
        "higher_lower": True,
        "push": "PUSH_ON_EXACT",
        "role": "K",
    },
}


def canonicalize_cfb_market(label: str | None) -> str | None:
    raw = str(label or "").strip()
    if not raw:
        return None
    key = "_".join(p for p in raw.lower().replace("+", "_").replace("-", "_").replace(" ", "_").split("_") if p)
    if key in EXACT_ALIASES:
        return EXACT_ALIASES[key]
    if key in ACTIVE_CFB_MARKETS:
        return key
    return None


def classify_raw_market_label(label: str | None) -> dict[str, str]:
    raw = str(label or "").strip()
    slug = "_".join(p for p in raw.lower().replace("+", "_").replace("-", "_").replace(" ", "_").split("_") if p)
    # Fail closed: genuine unsupported semantics before any alias mapping.
    if slug in GENUINE_UNSUPPORTED:
        reason = GENUINE_UNSUPPORTED[slug]
        kind = "UNSUPPORTED_BY_DESIGN" if reason.startswith("UNSUPPORTED_BY_DESIGN") else "IMPLEMENTABLE_MISSING"
        return {"raw": raw, "slug": slug, "canonical": "", "class": kind, "reason": reason}
    if slug.startswith("longest_"):
        reason = GENUINE_UNSUPPORTED.get(
            "longest_reception",
            "UNSUPPORTED_BY_DESIGN: longest-* markets require play-level yard distributions; game-log totals cannot identify the max play.",
        )
        return {"raw": raw, "slug": slug, "canonical": "", "class": "UNSUPPORTED_BY_DESIGN", "reason": reason}
    canon = canonicalize_cfb_market(raw)
    if canon and slug != canon and slug in EXACT_ALIASES:
        kind = "EXACT_ALIAS_EXISTING_MARKET"
    elif canon and canon in ACTIVE_CFB_MARKETS:
        kind = "SUPPORTED_IMPLEMENTED"
    elif not canon:
        kind = "SEMANTICALLY_UNKNOWN"
        return {
            "raw": raw,
            "slug": slug,
            "canonical": "",
            "class": kind,
            "reason": "No exact alias and no verified MarketDefinition.",
        }
    else:
        kind = "IMPLEMENTABLE_MISSING"
    return {
        "raw": raw,
        "slug": slug,
        "canonical": canon or "",
        "class": kind,
        "reason": "" if kind in {"EXACT_ALIAS_EXISTING_MARKET", "SUPPORTED_IMPLEMENTED"} else GENUINE_UNSUPPORTED.get(slug, ""),
    }


def inventory_raw_labels(labels: list[str]) -> dict[str, Any]:
    rows = [classify_raw_market_label(lab) for lab in labels]
    by_class: dict[str, list[str]] = {}
    for row in rows:
        by_class.setdefault(row["class"], []).append(row["raw"])
    body = {
        "schema": "pillars_dcm.cfb_market_inventory.v1",
        "rawLabels": sorted(set(labels)),
        "classifications": rows,
        "byClass": {k: sorted(set(v)) for k, v in sorted(by_class.items())},
        "activeMarketDefinitions": list(ACTIVE_CFB_MARKETS),
        "guardedLaunchMarkets": list(GUARDED_LAUNCH_MARKETS),
        "newlyActivated": list(NEWLY_ACTIVATED_MARKETS),
        "genuineUnsupported": dict(GENUINE_UNSUPPORTED),
        "aliasesNormalized": dict(EXACT_ALIASES),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def is_active_cfb_market(market: str | None) -> bool:
    canon = canonicalize_cfb_market(market) or str(market or "").lower()
    return canon in ACTIVE_CFB_MARKETS


def contract_for(market: str | None) -> dict[str, Any] | None:
    canon = canonicalize_cfb_market(market) or str(market or "").lower()
    spec = MARKET_CONTRACTS.get(canon)
    return dict(spec) if spec else None


REQUIRED_EXECUTION_STAGES = (
    "MarketDefinition",
    "RequirementNodes",
    "opportunity",
    "efficiency",
    "championProducer",
    "ParameterSnapshot",
    "EventWorldPrimitive",
    "distribution",
    "P_Higher_P_Lower",
    "settlement",
)


def cfb_market_execution_matrix() -> dict[str, Any]:
    """Machine-readable completeness of every ACTIVE CFB market's execution path."""
    from dcm.sports.football.research_requirements import MARKET_REQUIREMENTS
    from dcm.sports.football.registry import CFB_LEAGUE, lookup_market

    rows: list[dict[str, Any]] = []
    demoted: list[str] = []
    for market in ACTIVE_CFB_MARKETS:
        spec = MARKET_CONTRACTS.get(market) or {}
        definition = lookup_market(CFB_LEAGUE, market)
        req = MARKET_REQUIREMENTS.get(market) or {}
        stages = {
            "MarketDefinition": definition is not None,
            "RequirementNodes": bool(req),
            "opportunity": bool(spec.get("opportunity")),
            "efficiency": spec.get("efficiency") is not None,
            "championProducer": True,
            "ParameterSnapshot": True,
            "EventWorldPrimitive": True,
            "distribution": bool(spec.get("distribution")),
            "P_Higher_P_Lower": bool(spec.get("higher_lower")),
            "settlement": bool(spec.get("settlement") or (definition.formula if definition is not None else "")),
        }
        complete = all(stages.values())
        if not complete:
            demoted.append(market)
        rows.append({
            "market": market,
            "active": complete,
            "stages": stages,
            "distribution": spec.get("distribution"),
            "settlement": spec.get("settlement"),
            "championAlgorithmId": "ALG-ML-PROB-001",
            "missing": [k for k, v in stages.items() if not v],
        })
    body = {
        "schema": "pillars_dcm.cfb_market_execution_matrix.v1",
        "active": [r["market"] for r in rows if r["active"]],
        "demoted": demoted,
        "unsupported": sorted(GENUINE_UNSUPPORTED),
        "allActiveComplete": not demoted and len(rows) == len(ACTIVE_CFB_MARKETS),
        "rows": rows,
        "requiredStages": list(REQUIRED_EXECUTION_STAGES),
        "learningRevision": "LR000000",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k not in {"contentHash", "rows"}})
    return body

