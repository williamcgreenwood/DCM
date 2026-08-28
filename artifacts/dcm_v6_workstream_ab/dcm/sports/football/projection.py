"""Derive market values from a football primitive ledger. Never sample composites."""

from __future__ import annotations

from dcm.contracts.codes import FailureCode
from dcm.contracts.hashes import content_hash
from dcm.contracts.immutables import FrozenMap
from dcm.contracts.schemas import (
    MarketDefinition,
    PrimitiveStatLedger,
    StatSemanticType,
    WorldProjectionResult,
)
from dcm.sports.football.registry import DERIVED_SPECS, lookup_market


class ProjectionError(RuntimeError):
    def __init__(self, code: FailureCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


def _eval_formula(formula: str, values: dict[str, float]) -> float:
    allowed = {k: float(v) for k, v in values.items()}
    # Restricted arithmetic only.
    tokens = formula.replace("+", " + ").replace("-", " - ").split()
    total = 0.0
    sign = 1.0
    for tok in tokens:
        if tok == "+":
            sign = 1.0
        elif tok == "-":
            sign = -1.0
        else:
            if tok not in allowed:
                raise ProjectionError(FailureCode.UNVERIFIED_MARKET_DEFINITION, f"unknown component {tok}")
            total += sign * allowed[tok]
    return total


def project_football_market(
    ledger: PrimitiveStatLedger,
    *,
    player_id: str,
    market: str,
    world_index: int = 0,
    definition: MarketDefinition | None = None,
) -> WorldProjectionResult:
    definition = definition or lookup_market(ledger.league, market)
    if definition is None or not definition.verified:
        raise ProjectionError(FailureCode.UNVERIFIED_MARKET_DEFINITION, f"{ledger.league}/{market}")
    values = ledger.values_for(player_id)
    if definition.semantic_type == StatSemanticType.PRIMITIVE:
        key = definition.source_stat_keys[0]
        if key not in values:
            raise ProjectionError(FailureCode.UNVERIFIED_MARKET_DEFINITION, f"missing primitive {key}")
        computed = float(values[key])
        components = {key: computed}
    else:
        spec = DERIVED_SPECS.get(market)
        if spec is None or definition.formula is None:
            raise ProjectionError(FailureCode.UNVERIFIED_MARKET_DEFINITION, f"no formula for {market}")
        components = {k: float(values.get(k, 0.0)) for k in spec["sources"]}
        computed = _eval_formula(definition.formula, components)
        reconstructed = _eval_formula(spec["formula"], components)
        if abs(computed - reconstructed) > 1e-9:
            raise ProjectionError(FailureCode.DERIVED_IDENTITY_FAILURE, f"{market} formula mismatch")
    computation_hash = content_hash({
        "player_id": player_id,
        "market": market,
        "computed": computed,
        "components": components,
        "definition": definition.content_hash,
        "ledger": ledger.content_hash,
    })
    return WorldProjectionResult(
        world_index=world_index,
        market_definition_hash=definition.content_hash,
        entity_id=player_id,
        computed_value=computed,
        component_values=FrozenMap(components),
        computation_hash=computation_hash,
        primitive_ledger_hash=ledger.content_hash,
    )
