"""Phase B/C immutable object inventory implemented from the published blueprint.

This is a development reconstruction of PHASE_BC_SCHEMA_V1_2026-08-25 field
inventory. It does not claim to be a byte-for-byte copy of the missing
canonical JSON file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.contracts.immutables import FrozenMap, deep_freeze


SCHEMA_VERSION = "PHASE_BC_SCHEMA_V1_2026-08-25"
LEARNING_REVISION = "LR000000"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StatSemanticType(str, Enum):
    PRIMITIVE = "PRIMITIVE"
    DERIVED = "DERIVED"
    COMPOSITE = "COMPOSITE"
    PLATFORM_SCORE = "PLATFORM_SCORE"


class AdministrativeState(str, Enum):
    ACTIVE = "ACTIVE"
    DNP = "DNP"
    REBOOT = "REBOOT"
    CANCELLED = "CANCELLED"
    INVALID_MARKET = "INVALID_MARKET"
    UNRESOLVED = "UNRESOLVED"


class ComparisonState(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    TIE = "TIE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EconomicState(str, Enum):
    COUNTS_AS_WIN = "COUNTS_AS_WIN"
    COUNTS_AS_LOSS = "COUNTS_AS_LOSS"
    TIER_REDUCTION = "TIER_REDUCTION"
    REMOVED = "REMOVED"
    UNRESOLVED = "UNRESOLVED"


class PickSide(str, Enum):
    MORE = "MORE"
    LESS = "LESS"


class PickModifier(str, Enum):
    STANDARD = "STANDARD"
    DEMON = "DEMON"
    GOBLIN = "GOBLIN"
    OTHER = "OTHER"


@dataclass(frozen=True)
class ConservationRule:
    rule_id: str
    sport: str
    league: str
    rule_type: str
    expression: str
    tolerance: float
    rule_version: str
    scope: str = "TEAM_OR_PLAYER"
    overtime_behavior: str = "INCLUDE_IF_DEFINITION_INCLUDES"
    failure_code: str = "PRIMITIVE_CONSERVATION_FAILURE"
    schema_version: str = SCHEMA_VERSION

    def compute_hash(self) -> str:
        return content_hash(self)


@dataclass(frozen=True)
class InvariantResult:
    rule_id: str
    passed: bool
    observed: float | None
    expected: float | None
    residual: float | None
    message: str = ""
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class OpportunityState:
    shares: FrozenMap
    unit: str
    definition_version: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        object.__setattr__(self, "shares", FrozenMap(self.shares) if not isinstance(self.shares, FrozenMap) else self.shares)


@dataclass(frozen=True)
class EfficiencyState:
    rates: FrozenMap
    definition_version: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        object.__setattr__(self, "rates", FrozenMap(self.rates) if not isinstance(self.rates, FrozenMap) else self.rates)


@dataclass(frozen=True)
class DiscreteEventRegime:
    regime_type: str
    regime_value: str
    prior_probability: float
    evidence_ids: tuple[str, ...] = ()
    definition_version: str = "REGIME_V1"
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class EventLatentState:
    sport: str
    league: str
    payload: FrozenMap
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        object.__setattr__(self, "payload", FrozenMap(self.payload) if not isinstance(self.payload, FrozenMap) else self.payload)


@dataclass(frozen=True)
class PlayerWorldState:
    player_id: str
    team_id: str
    role: str
    opportunity: OpportunityState
    efficiency: EfficiencyState
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class PrimitiveStatEntry:
    entity_type: str
    entity_id: str
    team_id: str
    stat_key: str
    value: float
    unit: str
    primitive_definition_version: str
    semantic_type: StatSemanticType = StatSemanticType.PRIMITIVE
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class PrimitiveStatLedger:
    event_id: str
    sport: str
    league: str
    entries: tuple[PrimitiveStatEntry, ...]
    source_hashes: tuple[str, ...]
    primitive_schema_version: str
    schema_version: str = SCHEMA_VERSION
    created_at_utc: datetime = field(default_factory=_utcnow)
    learning_revision: str = LEARNING_REVISION
    content_hash: str = ""

    def __post_init__(self):
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "source_hashes", tuple(self.source_hashes))
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self))

    def values_for(self, entity_id: str) -> dict[str, float]:
        return {e.stat_key: e.value for e in self.entries if e.entity_id == entity_id}

    def team_values(self, team_id: str, entity_type: str = "TEAM") -> dict[str, float]:
        return {
            e.stat_key: e.value
            for e in self.entries
            if e.team_id == team_id and e.entity_type == entity_type
        }

    def find(self, entity_id: str, stat_key: str) -> PrimitiveStatEntry | None:
        for e in self.entries:
            if e.entity_id == entity_id and e.stat_key == stat_key:
                return e
        return None


@dataclass(frozen=True)
class EventWorldSet:
    world_set_id: str
    run_id: str
    event_id: str
    sport: str
    league: str
    world_count: int
    evidence_graph_hash: str
    parameter_snapshot_hash: str
    seed_material_hash: str
    primitive_schema_version: str
    schema_version: str = SCHEMA_VERSION
    created_at_utc: datetime = field(default_factory=_utcnow)
    learning_revision: str = LEARNING_REVISION
    source_hashes: tuple[str, ...] = ()
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self))


@dataclass(frozen=True)
class EventWorld:
    world_set_id: str
    world_index: int
    event_latents: EventLatentState
    regimes: tuple[DiscreteEventRegime, ...]
    player_states: tuple[PlayerWorldState, ...]
    primitive_ledger_hash: str
    valid: bool
    invariant_failures: tuple[InvariantResult, ...]
    schema_version: str = SCHEMA_VERSION
    source_hashes: tuple[str, ...] = ()
    content_hash: str = ""

    def __post_init__(self):
        object.__setattr__(self, "regimes", tuple(self.regimes))
        object.__setattr__(self, "player_states", tuple(self.player_states))
        object.__setattr__(self, "invariant_failures", tuple(self.invariant_failures))
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self))


@dataclass(frozen=True)
class MarketDefinition:
    platform: str
    league: str
    market: str
    definition_version: str
    output_unit: str
    source_stat_keys: tuple[str, ...]
    formula: str | None
    semantic_type: StatSemanticType
    overtime_policy: str
    push_policy: str
    participation_policy_version: str
    reboot_policy_version: str
    verified: bool
    verification_hash: str
    schema_version: str = SCHEMA_VERSION
    content_hash: str = ""

    def key(self) -> tuple[str, str, str, str]:
        return (self.platform, self.league, self.market, self.definition_version)

    def __post_init__(self):
        object.__setattr__(self, "source_stat_keys", tuple(self.source_stat_keys))
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self))


@dataclass(frozen=True)
class WorldProjectionResult:
    world_index: int
    market_definition_hash: str
    entity_id: str
    computed_value: float
    component_values: FrozenMap
    computation_hash: str
    primitive_ledger_hash: str
    schema_version: str = SCHEMA_VERSION
    content_hash: str = ""

    def __post_init__(self):
        object.__setattr__(
            self,
            "component_values",
            FrozenMap(self.component_values) if not isinstance(self.component_values, FrozenMap) else self.component_values,
        )
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self))


@dataclass(frozen=True)
class EntryPickContract:
    projection_id: str
    player_id: str
    team_id: str
    event_id: str
    market_definition_id: str
    line: float
    side: PickSide
    modifier: PickModifier
    offered_side_verified: bool
    leaderboard_point_weight: float
    reboot_rule_version: str
    participation_rule_version: str
    league: str
    stat_key: str
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class EntryContract:
    platform: str
    platform_rule_version: str
    submitted_at: str
    entry_type: str
    stake: float
    currency: str
    picks: tuple[EntryPickContract, ...]
    minimum_guarantee_definition_id: str
    leaderboard_definition_id: str
    payout_display_hash: str
    displayed_leaderboard_payout: float
    displayed_minimum_guarantee_table_hash: str
    schema_version: str = SCHEMA_VERSION
    created_at_utc: datetime = field(default_factory=_utcnow)
    learning_revision: str = LEARNING_REVISION
    source_hashes: tuple[str, ...] = ()
    content_hash: str = ""

    def __post_init__(self):
        object.__setattr__(self, "picks", tuple(self.picks))
        if not self.payout_display_hash:
            raise ValueError("ENTRY_CONTRACT_INCOMPLETE: payout_display_hash required")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self))


@dataclass(frozen=True)
class WorldPickState:
    projection_id: str
    administrative_state: AdministrativeState
    comparison_state: ComparisonState
    economic_state: EconomicState
    official_stat_value: float | None
    comparison_line: float
    reboot_applied: bool
    reason_code: str
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class PickSettlement:
    projection_id: str
    official_stat_value: float | None
    comparison_line: float
    administrative_state: AdministrativeState
    comparison_state: ComparisonState
    economic_state: EconomicState
    participation_evidence_ids: tuple[str, ...]
    official_stat_source_ids: tuple[str, ...]
    official_result_timestamp: str | None
    platform_settlement_timestamp: str | None
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class LineupSettlement:
    original_pick_count: int
    administrative_removed_count: int
    tie_count: int
    payout_tier_count: int
    eligibility_population_count: int
    distinct_remaining_team_count: int
    win_count: int
    loss_count: int
    push_count: int
    minimum_guarantee_return: float
    leaderboard_score: float
    leaderboard_return: float
    leaderboard_return_status: str
    final_platform_return: float
    net_return: float
    settlement_status: str
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class WorldLineupOutcome:
    world_index: int
    pick_states: tuple[WorldPickState, ...]
    lineup: LineupSettlement
    world_projection_hash: str
    entry_contract_hash: str
    settlement_rule_hash: str
    schema_version: str = SCHEMA_VERSION
    source_hashes: tuple[str, ...] = ()
    content_hash: str = ""

    def __post_init__(self):
        object.__setattr__(self, "pick_states", tuple(self.pick_states))
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self))
