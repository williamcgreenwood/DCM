"""Fail-closed activation gate using current SportPlugin/market contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from dcm.signals.contracts import ACTIVE_STATES, LifecycleState, SignalOperatorSpec
from dcm.sports.common.plugin import CAPABILITIES, REGISTRY as SPORT_PLUGINS, UNSUPPORTED


FORBIDDEN_BEHAVIOR_CLASSES = frozenset({
    "CONFIDENCE_TO_PROBABILITY",
    "FALSE_CERTAINTY_PROBABILITY_TRANSFORM",
    "FORCED_PREDICTION",
    "FORCED_INVERSE",
    "PARLAY_FILLER",
    "FORCED_CARD_SIZE",
    "FRAUD_DETERMINATION",
    "UNVERIFIED_LEAK_HARD_GATE",
    "HOST_SPECIFIC_REQUIRED_DEPENDENCY",
})


DEFAULT_UNITS: dict[str, dict[str, str]] = {
    "basketball": {
        "minutes": "minute", "possessions": "possession", "pts": "point",
        "reb": "rebound", "ast": "assist", "fga": "attempt", "tpa": "attempt",
    },
    "gridiron": {
        "snaps": "snap", "routes": "route", "targets": "target", "dropbacks": "dropback",
        "carries": "carry", "pass_yds": "yard", "rush_yds": "yard", "rec_yds": "yard",
        "receptions": "reception",
    },
    "baseball": {
        "pa": "plate_appearance", "bf": "batter_faced", "pitch_count": "pitch",
        "pitches": "pitch", "h": "hit", "tb": "base", "k": "strikeout",
    },
}


@dataclass(frozen=True)
class BindingCatalog:
    normalized_units: Mapping[str, Mapping[str, str]] = field(default_factory=lambda: DEFAULT_UNITS)
    consumers: frozenset[str] = frozenset({
        "dcm.ml.feature_store.signal_evaluation_feature_records",
        "dcm.audit.trace.signal_evaluations",
    })
    hard_gate_authorizations: frozenset[str] = frozenset()

    def sport_exists(self, sport: str) -> bool:
        return sport in SPORT_PLUGINS

    def market_is_applicable(self, sport: str, competition: str, market: str) -> bool:
        return CAPABILITIES.get((sport, competition, market), UNSUPPORTED) != UNSUPPORTED

    def unit_for(self, sport: str, field_name: str) -> str | None:
        return self.normalized_units.get(sport, {}).get(field_name.strip().lower())


class SignalIntegrationGate:
    def __init__(self, catalog: BindingCatalog | None = None):
        self.catalog = catalog or BindingCatalog()

    def validate(self, spec: SignalOperatorSpec) -> tuple[str, ...]:
        reasons: list[str] = []
        if not spec.sports:
            reasons.append("SPORT_SCOPE_REQUIRED")
        for sport in spec.sports:
            if not self.catalog.sport_exists(sport):
                reasons.append(f"SPORT_PLUGIN_UNSUPPORTED:{sport}")
        if spec.market_definitions and not spec.competitions:
            reasons.append("COMPETITION_REQUIRED_FOR_MARKET_BINDING")
        for sport in spec.sports:
            for competition in spec.competitions:
                for market in spec.market_definitions:
                    if not self.catalog.market_is_applicable(sport, competition, market):
                        reasons.append(f"MARKET_DEFINITION_UNSUPPORTED:{sport}:{competition}:{market}")
        for field_spec in (*spec.required_inputs, *spec.outputs):
            if not field_spec.normalized:
                reasons.append(f"NORMALIZED_FIELD_REQUIRED:{field_spec.name}")
            if field_spec.temporal_class.upper() in {"POST_CUTOFF", "FUTURE", "SETTLED_OUTCOME"}:
                reasons.append(f"POST_CUTOFF_INPUT_FORBIDDEN:{field_spec.name}")
        for sport in spec.sports:
            for required in spec.required_inputs:
                bound_unit = self.catalog.unit_for(sport, required.name)
                if bound_unit is None:
                    reasons.append(f"NORMALIZED_FIELD_UNAVAILABLE:{sport}:{required.name}")
                elif bound_unit.lower() != required.unit.lower():
                    reasons.append(
                        f"UNIT_MISMATCH:{sport}:{required.name}:required={required.unit}:bound={bound_unit}"
                    )
        if spec.behavior_class.upper() in FORBIDDEN_BEHAVIOR_CLASSES:
            reasons.append(f"FORBIDDEN_BEHAVIOR_CLASS:{spec.behavior_class.upper()}")
        if spec.lifecycle_state in ACTIVE_STATES:
            if not spec.consumers:
                reasons.append("ACTIVE_OPERATOR_CONSUMER_REQUIRED")
            for consumer in spec.consumers:
                if consumer not in self.catalog.consumers:
                    reasons.append(f"CONSUMER_UNREGISTERED:{consumer}")
            if not spec.tests:
                reasons.append("ACTIVE_OPERATOR_TEST_REQUIRED")
        if spec.lifecycle_state == LifecycleState.ACTIVE_HARD_GATE:
            if not spec.hard_gate_authorization:
                reasons.append("HARD_GATE_AUTHORIZATION_REQUIRED")
            elif spec.hard_gate_authorization not in self.catalog.hard_gate_authorizations:
                reasons.append(f"HARD_GATE_AUTHORIZATION_UNKNOWN:{spec.hard_gate_authorization}")
        return tuple(sorted(set(reasons)))
