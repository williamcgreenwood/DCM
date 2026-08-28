"""Football primitive registry covering NFL and CFB.

Physical identities are shared. Platform / Reboot authority is league-keyed.
NFLP (preseason) may build a physical ledger; settlement reboot rows are absent.
"""

from __future__ import annotations

from dcm.contracts.hashes import content_hash
from dcm.contracts.schemas import MarketDefinition, StatSemanticType


NFL_LEAGUE = "NFL"
CFB_LEAGUE = "CFB"
NFLP_LEAGUE = "NFLP"
SPORT = "FOOTBALL"
PLATFORM = "PRIZEPICKS"
DEFINITION_VERSION = "PP_FOOTBALL_PRIM_V1_2026-08-27"
REBOOT_POLICY = "PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1"
PARTICIPATION_POLICY = "PP_PARTICIPATION_V1_2026-08-25"

# Declared dropback identity:
#   dropbacks = pass_att + sacks_taken + scramble_att
# Declared play identity:
#   team_off_plays = pass_att + rush_att + sacks_taken
#   rush_att = designed_rush_att + scramble_att
# Therefore team_off_plays = dropbacks + designed_rush_att
# Sack yards are NOT deducted from pass_yds in this definition version.
# team_pass_yds (gross) reconciles to sum of rec_yds when laterals are unmodeled.

PRIMITIVE_SPECS: dict[str, dict] = {
    "off_snaps": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "routes": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "targets": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "dropbacks": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "pass_att": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "designed_rush_att": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "scramble_att": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "rush_att": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "rz_att": {"unit": "count", "family": "opportunity", "entity": "PLAYER"},
    "pass_cmp": {"unit": "count", "family": "passing", "entity": "PLAYER"},
    "pass_yds": {"unit": "yards", "family": "passing", "entity": "PLAYER"},
    "pass_td": {"unit": "count", "family": "passing", "entity": "PLAYER"},
    "interceptions": {"unit": "count", "family": "passing", "entity": "PLAYER"},
    "sacks_taken": {"unit": "count", "family": "passing", "entity": "PLAYER"},
    "sack_yds": {"unit": "yards", "family": "passing", "entity": "PLAYER"},
    "scramble_yds": {"unit": "yards", "family": "rushing", "entity": "PLAYER"},
    "rush_yds": {"unit": "yards", "family": "rushing", "entity": "PLAYER"},
    "rush_td": {"unit": "count", "family": "rushing", "entity": "PLAYER"},
    "receptions": {"unit": "count", "family": "receiving", "entity": "PLAYER"},
    "rec_yds": {"unit": "yards", "family": "receiving", "entity": "PLAYER"},
    "rec_td": {"unit": "count", "family": "receiving", "entity": "PLAYER"},
    "fg_att": {"unit": "count", "family": "kicking", "entity": "PLAYER"},
    "fg_made": {"unit": "count", "family": "kicking", "entity": "PLAYER"},
    "xp_att": {"unit": "count", "family": "kicking", "entity": "PLAYER"},
    "xp_made": {"unit": "count", "family": "kicking", "entity": "PLAYER"},
    "punt_att": {"unit": "count", "family": "kicking", "entity": "PLAYER"},
    "def_tackles": {"unit": "count", "family": "defense", "entity": "PLAYER"},
    "def_sacks": {"unit": "count", "family": "defense", "entity": "PLAYER"},
    "team_off_plays": {"unit": "count", "family": "team_pool", "entity": "TEAM"},
    "team_dropbacks": {"unit": "count", "family": "team_pool", "entity": "TEAM"},
    "team_pass_att": {"unit": "count", "family": "team_pool", "entity": "TEAM"},
    "team_rush_att": {"unit": "count", "family": "team_pool", "entity": "TEAM"},
    "team_sacks_taken": {"unit": "count", "family": "team_pool", "entity": "TEAM"},
    "team_designed_rush_att": {"unit": "count", "family": "team_pool", "entity": "TEAM"},
    "team_targets": {"unit": "count", "family": "team_pool", "entity": "TEAM"},
    "team_pass_yds": {"unit": "yards", "family": "team_pool", "entity": "TEAM"},
    "team_rec_yds": {"unit": "yards", "family": "team_pool", "entity": "TEAM"},
    "team_rush_yds": {"unit": "yards", "family": "team_pool", "entity": "TEAM"},
}

DERIVED_SPECS: dict[str, dict] = {
    "pass_rush_yds": {
        "unit": "yards",
        "formula": "pass_yds + rush_yds",
        "sources": ("pass_yds", "rush_yds"),
        "semantic": StatSemanticType.COMPOSITE,
    },
    "rush_rec_yds": {
        "unit": "yards",
        "formula": "rush_yds + rec_yds",
        "sources": ("rush_yds", "rec_yds"),
        "semantic": StatSemanticType.COMPOSITE,
    },
    "rush_rec_td": {
        "unit": "count",
        "formula": "rush_td + rec_td",
        "sources": ("rush_td", "rec_td"),
        "semantic": StatSemanticType.COMPOSITE,
    },
    "pass_rush_td": {
        "unit": "count",
        "formula": "pass_td + rush_td",
        "sources": ("pass_td", "rush_td"),
        "semantic": StatSemanticType.COMPOSITE,
    },
    "receptions_plus_rush_att": {
        "unit": "count",
        "formula": "receptions + rush_att",
        "sources": ("receptions", "rush_att"),
        "semantic": StatSemanticType.COMPOSITE,
    },
}

# Verified PrizePicks MORE reboot eligibility under snapshot V1.
# Public page does not publish a complete stat-key list; this frozen registry
# is explicit. Keys not listed are UNRESOLVED, never guessed eligible.
NFL_REBOOT_ELIGIBLE_STATS = frozenset({
    "pass_yds", "pass_att", "pass_cmp", "pass_td", "interceptions",
    "rush_yds", "rush_att", "rush_td",
    "receptions", "rec_yds", "rec_td", "targets",
    "pass_rush_yds", "rush_rec_yds", "rush_rec_td", "pass_rush_td",
})
NFL_REBOOT_EXCLUDED_STATS = frozenset({
    "def_tackles", "def_sacks",
})
# K/P attempt markets: zero-opportunity path, not a generic defensive exclusion.
NFL_SPECIALISTS = frozenset({"K", "P"})
NFL_DEFENSE_ROLES = frozenset({"DEF", "LB", "DL", "DB", "IDP"})

# CFB uses the same physical stats. Reboot requires BOTH stat eligibility
# AND membership in the frozen player registry.
CFB_REBOOT_ELIGIBLE_STATS = NFL_REBOOT_ELIGIBLE_STATS
CFB_PLAYER_REBOOT_ELIGIBLE = frozenset({
    # Frozen explicit list. Not inferred from "skill player" heuristics.
    "CFB_QB_001",
    "CFB_RB_001",
    "CFB_WR_001",
    "CFB_TE_001",
})


def football_primitive_keys() -> tuple[str, ...]:
    return tuple(PRIMITIVE_SPECS.keys())


def football_stat_reboot_eligibility(league: str, stat_key: str, role: str) -> str:
    """Return VERIFIED_TRUE, VERIFIED_FALSE, or UNKNOWN."""
    if league == NFLP_LEAGUE:
        return "UNKNOWN"
    if role in NFL_DEFENSE_ROLES:
        return "VERIFIED_FALSE"
    if stat_key in NFL_REBOOT_EXCLUDED_STATS:
        return "VERIFIED_FALSE"
    eligible = NFL_REBOOT_ELIGIBLE_STATS if league == NFL_LEAGUE else (
        CFB_REBOOT_ELIGIBLE_STATS if league == CFB_LEAGUE else None
    )
    if eligible is None:
        return "UNKNOWN"
    if stat_key in eligible:
        return "VERIFIED_TRUE"
    if stat_key in PRIMITIVE_SPECS or stat_key in DERIVED_SPECS:
        return "VERIFIED_FALSE"
    return "UNKNOWN"


def _market_for(league: str, market: str, sources: tuple[str, ...], unit: str, formula: str | None, semantic: StatSemanticType) -> MarketDefinition:
    payload = MarketDefinition(
        platform=PLATFORM,
        league=league,
        market=market,
        definition_version=DEFINITION_VERSION,
        output_unit=unit,
        source_stat_keys=sources,
        formula=formula,
        semantic_type=semantic,
        overtime_policy="INCLUDE_FULL_GAME",
        push_policy="PUSH_ON_EXACT",
        participation_policy_version=PARTICIPATION_POLICY,
        reboot_policy_version=REBOOT_POLICY,
        verified=True,
        verification_hash="",
    )
    object.__setattr__(payload, "verification_hash", content_hash({
        "key": payload.key(),
        "formula": formula,
        "sources": sources,
        "reboot": REBOOT_POLICY,
    }))
    return payload


def football_market_definitions(*leagues: str) -> tuple[MarketDefinition, ...]:
    if not leagues:
        leagues = (NFL_LEAGUE, CFB_LEAGUE)
    defs = []
    primitive_markets = [
        "pass_yds", "pass_att", "pass_cmp", "pass_td", "interceptions",
        "rush_yds", "rush_att", "rush_td",
        "receptions", "rec_yds", "rec_td", "targets",
        "fg_made", "def_tackles",
    ]
    for league in leagues:
        for key in primitive_markets:
            spec = PRIMITIVE_SPECS[key]
            defs.append(_market_for(
                league, key, (key,), spec["unit"], None, StatSemanticType.PRIMITIVE,
            ))
        for key, spec in DERIVED_SPECS.items():
            defs.append(_market_for(
                league, key, spec["sources"], spec["unit"], spec["formula"], spec["semantic"],
            ))
    return tuple(defs)


def lookup_market(league: str, market: str) -> MarketDefinition | None:
    for item in football_market_definitions(league):
        if item.market == market and item.league == league:
            return item
    return None
