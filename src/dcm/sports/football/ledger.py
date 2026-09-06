"""Build a football EventWorld + PrimitiveStatLedger from explicit or generated state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dcm.contracts.codes import FailureCode
from dcm.contracts.hashes import content_hash
from dcm.contracts.immutables import FrozenMap
from dcm.contracts.schemas import (
    DiscreteEventRegime,
    EventLatentState,
    EventWorld,
    EventWorldSet,
    PrimitiveStatEntry,
    PrimitiveStatLedger,
    StatSemanticType,
)
from dcm.sports.football.appearance import appearance_process_for
from dcm.sports.football.conservation import conservation_passed, evaluate_football_conservation
from dcm.sports.football.efficiency import apply_efficiency, player_efficiency
from dcm.sports.football.opportunity import TeamOpportunityPool, player_opportunity
from dcm.sports.football.registry import DEFINITION_VERSION, PRIMITIVE_SPECS, SPORT


class ConservationError(RuntimeError):
    def __init__(self, code: FailureCode, message: str, failures):
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.failures = failures


@dataclass(frozen=True)
class FootballPlayerSpec:
    player_id: str
    team_id: str
    role: str
    opportunity: dict[str, float]
    rates: dict[str, float]
    primitives: dict[str, float] | None = None  # if set, used as-is (must still conserve)


@dataclass(frozen=True)
class FootballWorldBuild:
    world_set: EventWorldSet
    world: EventWorld
    ledger: PrimitiveStatLedger


def _entry(entity_type: str, entity_id: str, team_id: str, key: str, value: float) -> PrimitiveStatEntry:
    spec = PRIMITIVE_SPECS[key]
    return PrimitiveStatEntry(
        entity_type=entity_type,
        entity_id=entity_id,
        team_id=team_id,
        stat_key=key,
        value=float(value),
        unit=spec["unit"],
        primitive_definition_version=DEFINITION_VERSION,
        semantic_type=StatSemanticType.PRIMITIVE,
    )


def _player_primitives(spec: FootballPlayerSpec) -> dict[str, float]:
    if spec.primitives is not None:
        return dict(spec.primitives)
    opp = player_opportunity(**{k: spec.opportunity.get(k, 0.0) for k in (
        "off_snaps", "routes", "targets", "dropbacks", "pass_att",
        "designed_rush_att", "scramble_att", "rz_att", "fg_att", "xp_att", "punt_att",
    )})
    return apply_efficiency(opp.shares.as_dict(), spec.rates, spec.role)


def build_football_world(
    *,
    event_id: str,
    league: str,
    teams: dict[str, TeamOpportunityPool],
    players: list[FootballPlayerSpec],
    team_pass_yds: dict[str, float] | None = None,
    team_rush_yds: dict[str, float] | None = None,
    world_index: int = 0,
    evidence_graph_hash: str = "ev_test",
    parameter_snapshot_hash: str = "par_test",
    allow_invalid: bool = False,
    extra_team_stats: dict[str, dict[str, float]] | None = None,
) -> FootballWorldBuild:
    appearance = appearance_process_for(league)
    entries: list[PrimitiveStatEntry] = []

    rec_yds_by_team: dict[str, float] = {tid: 0.0 for tid in teams}
    rush_yds_by_team: dict[str, float] = {tid: 0.0 for tid in teams}
    for spec in players:
        prim = _player_primitives(spec)
        rec_yds_by_team[spec.team_id] = rec_yds_by_team.get(spec.team_id, 0.0) + prim.get("rec_yds", 0.0)
        rush_yds_by_team[spec.team_id] = rush_yds_by_team.get(spec.team_id, 0.0) + prim.get("rush_yds", 0.0)
        for key in PRIMITIVE_SPECS:
            if PRIMITIVE_SPECS[key]["entity"] != "PLAYER":
                continue
            entries.append(_entry("PLAYER", spec.player_id, spec.team_id, key, prim.get(key, 0.0)))

    for team_id, pool in teams.items():
        pool.validate_internal()
        stats = pool.as_team_stats()
        pass_yds = rec_yds_by_team.get(team_id, 0.0) if team_pass_yds is None else float(team_pass_yds[team_id])
        rush_yds = rush_yds_by_team.get(team_id, 0.0) if team_rush_yds is None else float(team_rush_yds[team_id])
        stats["team_pass_yds"] = pass_yds
        stats["team_rec_yds"] = rec_yds_by_team.get(team_id, 0.0) if extra_team_stats is None else extra_team_stats.get(team_id, {}).get("team_rec_yds", rec_yds_by_team.get(team_id, 0.0))
        if extra_team_stats and team_id in extra_team_stats:
            stats.update(extra_team_stats[team_id])
        if "team_rec_yds" not in stats:
            stats["team_rec_yds"] = rec_yds_by_team.get(team_id, 0.0)
        if team_pass_yds is None and "team_pass_yds" not in (extra_team_stats or {}).get(team_id, {}):
            stats["team_pass_yds"] = stats["team_rec_yds"]
        stats["team_rush_yds"] = rush_yds
        for key, value in stats.items():
            if key in PRIMITIVE_SPECS and PRIMITIVE_SPECS[key]["entity"] == "TEAM":
                entries.append(_entry("TEAM", team_id, team_id, key, value))

    world_set = EventWorldSet(
        world_set_id=f"{event_id}:set",
        run_id=f"{event_id}:run",
        event_id=event_id,
        sport=SPORT,
        league=league,
        world_count=1,
        evidence_graph_hash=evidence_graph_hash,
        parameter_snapshot_hash=parameter_snapshot_hash,
        seed_material_hash=content_hash({"event_id": event_id, "index": world_index}),
        primitive_schema_version=DEFINITION_VERSION,
        source_hashes=(evidence_graph_hash, parameter_snapshot_hash),
    )
    ledger = PrimitiveStatLedger(
        event_id=event_id,
        sport=SPORT,
        league=league,
        entries=tuple(entries),
        source_hashes=(world_set.content_hash,),
        primitive_schema_version=DEFINITION_VERSION,
    )
    results = evaluate_football_conservation(ledger)
    valid = conservation_passed(results)
    if not valid and not allow_invalid:
        failed = [r for r in results if not r.passed]
        raise ConservationError(
            FailureCode.PRIMITIVE_CONSERVATION_FAILURE,
            f"{len(failed)} football identities failed",
            failed,
        )
    latents = EventLatentState(
        sport=SPORT,
        league=league,
        payload=FrozenMap({
            "appearance": appearance.as_payload().as_dict(),
            "scoring_environment": "neutral",
        }),
    )
    world = EventWorld(
        world_set_id=world_set.world_set_id,
        world_index=world_index,
        event_latents=latents,
        regimes=(DiscreteEventRegime("STARTER_QB", "ACTIVE", 1.0),),
        player_states=(),
        primitive_ledger_hash=ledger.content_hash,
        valid=valid,
        invariant_failures=tuple(r for r in results if not r.passed),
        source_hashes=(world_set.content_hash, ledger.content_hash),
    )
    return FootballWorldBuild(world_set=world_set, world=world, ledger=ledger)


def corrupt_stat(ledger: PrimitiveStatLedger, entity_id: str, stat_key: str, value: float) -> PrimitiveStatLedger:
    """Return a new ledger with one primitive overwritten. Used by the harness."""
    new_entries = []
    for e in ledger.entries:
        if e.entity_id == entity_id and e.stat_key == stat_key:
            new_entries.append(PrimitiveStatEntry(
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                team_id=e.team_id,
                stat_key=e.stat_key,
                value=float(value),
                unit=e.unit,
                primitive_definition_version=e.primitive_definition_version,
                semantic_type=e.semantic_type,
            ))
        else:
            new_entries.append(e)
    return PrimitiveStatLedger(
        event_id=ledger.event_id,
        sport=ledger.sport,
        league=ledger.league,
        entries=tuple(new_entries),
        source_hashes=ledger.source_hashes + ("corruption",),
        primitive_schema_version=ledger.primitive_schema_version,
    )
