"""Minimal basketball world builder for E2E fixture 1. Does not replace the LIVE v5 registry."""

from __future__ import annotations

from dcm.contracts.codes import FailureCode
from dcm.contracts.hashes import content_hash
from dcm.contracts.immutables import FrozenMap
from dcm.contracts.schemas import (
    EventLatentState,
    EventWorld,
    EventWorldSet,
    InvariantResult,
    MarketDefinition,
    PrimitiveStatEntry,
    PrimitiveStatLedger,
    StatSemanticType,
    WorldProjectionResult,
)


NBA_LEAGUE = "NBA"
WNBA_LEAGUE = "WNBA"
SPORT = "BASKETBALL"
DEFINITION_VERSION = "PP_BBALL_PRIM_V1_2026-08-27"
BBALL_REBOOT = "PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1"

PRIMITIVES = {
    "minutes": "minutes",
    "fga": "count",
    "tpa": "count",
    "twopa": "count",
    "fgm": "count",
    "tpm": "count",
    "twopm": "count",
    "fta": "count",
    "ftm": "count",
    "oreb": "count",
    "dreb": "count",
    "reb": "count",
    "ast": "count",
    "stl": "count",
    "blk": "count",
    "tov": "count",
    "pts": "count",
}


def basketball_market(league: str, market: str, sources: tuple[str, ...], formula: str | None, semantic: StatSemanticType) -> MarketDefinition:
    md = MarketDefinition(
        platform="PRIZEPICKS",
        league=league,
        market=market,
        definition_version=DEFINITION_VERSION,
        output_unit="count",
        source_stat_keys=sources,
        formula=formula,
        semantic_type=semantic,
        overtime_policy="INCLUDE_FULL_GAME",
        push_policy="PUSH_ON_EXACT",
        participation_policy_version="PP_PARTICIPATION_V1_2026-08-25",
        reboot_policy_version=BBALL_REBOOT,
        verified=True,
        verification_hash="pending",
    )
    object.__setattr__(md, "verification_hash", content_hash(md.key()))
    return md


BASKETBALL_MARKETS = {
    "pts": lambda lg: basketball_market(lg, "pts", ("pts",), None, StatSemanticType.PRIMITIVE),
    "reb": lambda lg: basketball_market(lg, "reb", ("reb",), None, StatSemanticType.PRIMITIVE),
    "ast": lambda lg: basketball_market(lg, "ast", ("ast",), None, StatSemanticType.PRIMITIVE),
    "pra": lambda lg: basketball_market(lg, "pra", ("pts", "reb", "ast"), "pts + reb + ast", StatSemanticType.COMPOSITE),
    "pr": lambda lg: basketball_market(lg, "pr", ("pts", "reb"), "pts + reb", StatSemanticType.COMPOSITE),
    "pa": lambda lg: basketball_market(lg, "pa", ("pts", "ast"), "pts + ast", StatSemanticType.COMPOSITE),
    "ra": lambda lg: basketball_market(lg, "ra", ("reb", "ast"), "reb + ast", StatSemanticType.COMPOSITE),
}


def basketball_conservation(values: dict[str, float]) -> tuple[InvariantResult, ...]:
    def chk(rule, passed, obs, exp):
        return InvariantResult(rule_id=rule, passed=passed, observed=obs, expected=exp, residual=(obs or 0) - (exp or 0))

    twopa = values["fga"] - values["tpa"]
    fgm = values["twopm"] + values["tpm"]
    reb = values["oreb"] + values["dreb"]
    pts = 2 * values["twopm"] + 3 * values["tpm"] + values["ftm"]
    return (
        chk("2PA", abs(values["twopa"] - twopa) < 1e-9, values["twopa"], twopa),
        chk("FGM", abs(values["fgm"] - fgm) < 1e-9, values["fgm"], fgm),
        chk("REB", abs(values["reb"] - reb) < 1e-9, values["reb"], reb),
        chk("PTS", abs(values["pts"] - pts) < 1e-9, values["pts"], pts),
        chk("MADE_FGA", values["fgm"] <= values["fga"] + 1e-9, values["fgm"], values["fga"]),
        chk("MADE_TPA", values["tpm"] <= values["tpa"] + 1e-9, values["tpm"], values["tpa"]),
        chk("MADE_FTA", values["ftm"] <= values["fta"] + 1e-9, values["ftm"], values["fta"]),
    )


def build_basketball_world(*, event_id: str, league: str, player_id: str, team_id: str, stats: dict[str, float], world_index: int = 0):
    results = basketball_conservation(stats)
    if not all(r.passed for r in results):
        failed = [r.rule_id for r in results if not r.passed]
        raise RuntimeError(f"PRIMITIVE_CONSERVATION_FAILURE: {failed}")
    entries = tuple(
        PrimitiveStatEntry(
            entity_type="PLAYER",
            entity_id=player_id,
            team_id=team_id,
            stat_key=k,
            value=float(stats[k]),
            unit=PRIMITIVES[k],
            primitive_definition_version=DEFINITION_VERSION,
        )
        for k in PRIMITIVES
    )
    world_set = EventWorldSet(
        world_set_id=f"{event_id}:set",
        run_id=f"{event_id}:run",
        event_id=event_id,
        sport=SPORT,
        league=league,
        world_count=1,
        evidence_graph_hash="ev_bball",
        parameter_snapshot_hash="par_bball",
        seed_material_hash=content_hash(event_id),
        primitive_schema_version=DEFINITION_VERSION,
        source_hashes=("ev_bball", "par_bball"),
    )
    ledger = PrimitiveStatLedger(
        event_id=event_id,
        sport=SPORT,
        league=league,
        entries=entries,
        source_hashes=(world_set.content_hash,),
        primitive_schema_version=DEFINITION_VERSION,
    )
    world = EventWorld(
        world_set_id=world_set.world_set_id,
        world_index=world_index,
        event_latents=EventLatentState(sport=SPORT, league=league, payload=FrozenMap({"pace": 100.0})),
        regimes=(),
        player_states=(),
        primitive_ledger_hash=ledger.content_hash,
        valid=True,
        invariant_failures=(),
        source_hashes=(world_set.content_hash, ledger.content_hash),
    )
    return world_set, world, ledger


def project_basketball_market(ledger: PrimitiveStatLedger, player_id: str, market: str, world_index: int = 0) -> WorldProjectionResult:
    if market not in BASKETBALL_MARKETS:
        raise RuntimeError(f"UNVERIFIED_MARKET_DEFINITION: {market}")
    definition = BASKETBALL_MARKETS[market](ledger.league)
    values = ledger.values_for(player_id)
    if definition.formula is None:
        computed = float(values[market])
        components = {market: computed}
    else:
        components = {k: float(values[k]) for k in definition.source_stat_keys}
        computed = sum(components.values())
        if market == "pra" and abs(computed - (values["pts"] + values["reb"] + values["ast"])) > 1e-9:
            raise RuntimeError("DERIVED_IDENTITY_FAILURE")
    return WorldProjectionResult(
        world_index=world_index,
        market_definition_hash=definition.content_hash,
        entity_id=player_id,
        computed_value=computed,
        component_values=FrozenMap(components),
        computation_hash=content_hash({"m": market, "v": computed, "c": components}),
        primitive_ledger_hash=ledger.content_hash,
    )
