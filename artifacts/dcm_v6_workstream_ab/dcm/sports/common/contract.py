"""Executable universal SportPlugin component contract.

A sport is not universal-production-complete because a directory or manifest
exists. Every required component is explicitly bound, import-validated and
classified IMPLEMENTED / PARTIAL / MISSING. Only all-IMPLEMENTED contracts can
be reported as universalProductionComplete.

This validator does not create generic fallbacks and does not promote an
existing capability state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any


IMPLEMENTED = "IMPLEMENTED"
PARTIAL = "PARTIAL"
MISSING = "MISSING"

REQUIRED_COMPONENTS = (
    "IdentityContract",
    "ResearchSchema",
    "SourceAdapterRegistry",
    "CanonicalStatSchema",
    "HistoricalPerformanceSchema",
    "RoleStateSchema",
    "ParticipationModel",
    "OpportunityModel",
    "EfficiencyModel",
    "AffiliationModel",
    "CounterpartyModel",
    "EnvironmentModel",
    "EventWorldModel",
    "PrimitiveOutcomeSchema",
    "ConservationRules",
    "MarketDefinitionRegistry",
    "DistributionRegistry",
    "FeatureSchema",
    "MLModelRegistry",
    "CalibrationPolicy",
    "AvailabilityPolicy",
    "SettlementRules",
    "RebootDNPPolicy",
    "ValidationSuite",
)


@dataclass(frozen=True)
class ComponentBinding:
    component: str
    state: str
    reference: str | None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.component not in REQUIRED_COMPONENTS:
            raise ValueError(f"UNKNOWN_SPORT_PLUGIN_COMPONENT:{self.component}")
        if self.state not in {IMPLEMENTED, PARTIAL, MISSING}:
            raise ValueError(f"UNKNOWN_COMPONENT_STATE:{self.state}")
        if self.state != MISSING and not str(self.reference or "").strip():
            raise ValueError(f"COMPONENT_REFERENCE_REQUIRED:{self.component}")

    def resolve(self) -> tuple[bool, str | None]:
        """Import the configured module/symbol. Missing is an explicit failure."""
        if self.state == MISSING or not self.reference:
            return False, "MISSING"
        module_name, sep, symbol = self.reference.partition(":")
        try:
            module = import_module(module_name)
        except Exception as exc:  # import failure is a contract failure, never swallowed
            return False, f"IMPORT_ERROR:{type(exc).__name__}:{exc}"
        if sep:
            if not hasattr(module, symbol):
                return False, f"SYMBOL_NOT_FOUND:{symbol}"
        return True, None

    def to_dict(self, *, validate_import: bool = True) -> dict[str, Any]:
        resolved, error = (self.resolve() if validate_import else (None, None))
        return {
            "component": self.component,
            "state": self.state,
            "reference": self.reference,
            "notes": self.notes,
            "importResolved": resolved,
            "importError": error,
        }


@dataclass(frozen=True)
class SportPluginContract:
    sport_id: str
    contract_version: str
    declared_capability_state: str
    bindings: tuple[ComponentBinding, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.sport_id:
            raise ValueError("SPORT_PLUGIN_SPORT_ID_REQUIRED")
        if not self.contract_version:
            raise ValueError("SPORT_PLUGIN_CONTRACT_VERSION_REQUIRED")
        names = [b.component for b in self.bindings]
        if len(names) != len(set(names)):
            raise ValueError(f"DUPLICATE_SPORT_PLUGIN_COMPONENT:{self.sport_id}")

    def binding_map(self) -> dict[str, ComponentBinding]:
        return {b.component: b for b in self.bindings}

    def report(self, *, validate_imports: bool = True) -> dict[str, Any]:
        by_name = self.binding_map()
        rows: list[dict[str, Any]] = []
        blockers: list[str] = []
        for component in REQUIRED_COMPONENTS:
            binding = by_name.get(component) or ComponentBinding(
                component=component,
                state=MISSING,
                reference=None,
                notes="No component registered.",
            )
            row = binding.to_dict(validate_import=validate_imports)
            rows.append(row)
            if binding.state != IMPLEMENTED:
                blockers.append(f"{component}:{binding.state}")
            if validate_imports and row["importResolved"] is False and binding.state != MISSING:
                blockers.append(f"{component}:{row['importError']}")
        # Duplicate blocker strings make audits noisy.
        blockers = list(dict.fromkeys(blockers))
        complete = not blockers
        return {
            "sportId": self.sport_id,
            "contractVersion": self.contract_version,
            "declaredCapabilityState": self.declared_capability_state,
            "requiredComponentCount": len(REQUIRED_COMPONENTS),
            "implementedCount": sum(1 for r in rows if r["state"] == IMPLEMENTED),
            "partialCount": sum(1 for r in rows if r["state"] == PARTIAL),
            "missingCount": sum(1 for r in rows if r["state"] == MISSING),
            "universalProductionComplete": complete,
            "productionPromotionAllowedByContract": complete,
            "blockers": blockers,
            "components": rows,
            "failClosedRule": (
                "A declared capability does not imply universal production completeness; "
                "every required component must be IMPLEMENTED and import-resolved."
            ),
        }


REGISTRY: dict[str, SportPluginContract] = {}


def register_contract(contract: SportPluginContract) -> None:
    REGISTRY[contract.sport_id.lower()] = contract


def get_contract(sport_id: str) -> SportPluginContract | None:
    return REGISTRY.get(str(sport_id or "").strip().lower())


def require_contract(sport_id: str) -> SportPluginContract:
    contract = get_contract(sport_id)
    if contract is None:
        raise LookupError(f"SPORT_PLUGIN_CONTRACT_UNSUPPORTED:{sport_id}")
    return contract


def contract_registry_document(*, validate_imports: bool = True) -> dict[str, Any]:
    reports = [
        REGISTRY[key].report(validate_imports=validate_imports)
        for key in sorted(REGISTRY)
    ]
    return {
        "schema": "pillars_dcm.sport_plugin_contract_registry.v1",
        "requiredComponents": list(REQUIRED_COMPONENTS),
        "sportCount": len(reports),
        "productionCompleteSports": [
            report["sportId"] for report in reports if report["universalProductionComplete"]
        ],
        "sports": reports,
        "genericFallbackAllowed": False,
    }


def _b(component: str, state: str, reference: str | None, notes: str = "") -> ComponentBinding:
    return ComponentBinding(component, state, reference, notes)


# Basketball: real current components are registered, but the universal contract
# intentionally remains incomplete where responsibilities are bundled or the
# implementation is still an E2E/minimal registry.
register_contract(
    SportPluginContract(
        sport_id="basketball",
        contract_version="BASKETBALL_PLUGIN_CONTRACT_V1_2026-08-31",
        declared_capability_state="PRODUCTION_SUPPORTED_CURRENT_PATH",
        bindings=(
            _b("IdentityContract", IMPLEMENTED, "dcm.contracts.universal_entities:SubjectRef"),
            _b("ResearchSchema", IMPLEMENTED, "dcm.sports.common.research_schema:REGISTRY"),
            _b("SourceAdapterRegistry", IMPLEMENTED, "dcm.research.adapters:SourceAdapter"),
            _b("CanonicalStatSchema", IMPLEMENTED, "dcm.research.gamelog:normalize_basketball_logs"),
            _b("HistoricalPerformanceSchema", IMPLEMENTED, "dcm.research.gamelog:normalize_basketball_logs"),
            _b("RoleStateSchema", IMPLEMENTED, "dcm.research.role_epoch:RoleEpochBuilder"),
            _b(
                "ParticipationModel",
                IMPLEMENTED,
                "dcm.model.participation:ParticipationModel",
                "Minutes (basketball) and snaps (gridiron) are fit independently; OpportunityModel consumes participation output.",
            ),
            _b("OpportunityModel", IMPLEMENTED, "dcm.model.basketball_opportunity:OpportunityModel"),
            _b("EfficiencyModel", IMPLEMENTED, "dcm.model.basketball_efficiency:EfficiencyModel"),
            _b(
                "AffiliationModel",
                PARTIAL,
                "dcm.research.entity_packets:build_entity_packets",
                "Current team packet/model path is substantive but not a universal AffiliationModel API.",
            ),
            _b(
                "CounterpartyModel",
                PARTIAL,
                "dcm.research.entity_packets:build_entity_packets",
                "Current opponent packet is team-sport specific.",
            ),
            _b(
                "EnvironmentModel",
                PARTIAL,
                "dcm.research.entity_packets:build_entity_packets",
                "Event/environment evidence exists but is not a standalone basketball environment model.",
            ),
            _b("EventWorldModel", IMPLEMENTED, "dcm.model.event_world_joint:simulate_joint_team_worlds"),
            _b("PrimitiveOutcomeSchema", IMPLEMENTED, "dcm.sports.basketball.minimal:PRIMITIVES"),
            _b("ConservationRules", IMPLEMENTED, "dcm.sports.basketball.minimal:basketball_conservation"),
            _b(
                "MarketDefinitionRegistry",
                PARTIAL,
                "dcm.sports.basketball.minimal:BASKETBALL_MARKETS",
                "Registered market definitions live in a module explicitly labeled minimal/E2E; cannot satisfy the universal production contract.",
            ),
            _b("DistributionRegistry", IMPLEMENTED, "dcm.model.distributions:from_worlds"),
            _b(
                "FeatureSchema",
                PARTIAL,
                "dcm.ml.feature_store:FEATURE_FAMILIES",
                "Universal families are declared; packet-shaped basketball observations remain and Feature→graph lineage is first populated at freeze.",
            ),
            _b("MLModelRegistry", IMPLEMENTED, "dcm.learning.registry:load_registry"),
            _b("CalibrationPolicy", IMPLEMENTED, "dcm.learning.calibration:apply_calibration"),
            _b("AvailabilityPolicy", IMPLEMENTED, "dcm.model.availability:availability_mixture"),
            _b("SettlementRules", IMPLEMENTED, "dcm.platform.prizepicks.settlement:settle_world_lineup"),
            _b("RebootDNPPolicy", IMPLEMENTED, "dcm.platform.prizepicks.reboot:evaluate_reboot"),
            _b(
                "ValidationSuite",
                PARTIAL,
                "dcm.runtime.readiness:build_readiness",
                "Runtime readiness is executable, but the full sport-specific validation suite is not represented as one plugin component.",
            ),
        ),
    )
)

register_contract(
    SportPluginContract(
        sport_id="gridiron",
        contract_version="GRIDIRON_PLUGIN_CONTRACT_V1_2026-08-31",
        declared_capability_state="PRODUCTION_SUPPORTED_CURRENT_PATH",
        bindings=(
            _b("IdentityContract", IMPLEMENTED, "dcm.contracts.universal_entities:SubjectRef"),
            _b("ResearchSchema", IMPLEMENTED, "dcm.sports.common.research_schema:REGISTRY"),
            _b("SourceAdapterRegistry", IMPLEMENTED, "dcm.research.adapters:SourceAdapter"),
            _b("CanonicalStatSchema", IMPLEMENTED, "dcm.research.gridiron_gamelog:normalize_gridiron_logs"),
            _b("HistoricalPerformanceSchema", IMPLEMENTED, "dcm.research.gridiron_gamelog:normalize_gridiron_logs"),
            _b("RoleStateSchema", IMPLEMENTED, "dcm.research.role_epoch:RoleEpochBuilder"),
            _b(
                "ParticipationModel",
                IMPLEMENTED,
                "dcm.model.participation:ParticipationModel",
                "Snaps are fit independently of routes/targets/efficiency via ParticipationModel.",
            ),
            _b("OpportunityModel", IMPLEMENTED, "dcm.model.gridiron_models:GridironOpportunityModel"),
            _b("EfficiencyModel", IMPLEMENTED, "dcm.model.gridiron_models:GridironEfficiencyModel"),
            _b(
                "AffiliationModel",
                IMPLEMENTED,
                "dcm.model.gridiron_models:TeamEventModel",
                "Team plays/pass-rate/rush-rate context is executable.",
            ),
            _b(
                "CounterpartyModel",
                IMPLEMENTED,
                "dcm.model.gridiron_models:TeamEventModel",
                "Opponent pass/rush defense is explicit and missing values are blockers.",
            ),
            _b(
                "EnvironmentModel",
                PARTIAL,
                "dcm.model.gridiron_models:TeamEventModel",
                "Surface/weather research gates exist, but no standalone environment-distribution model is registered.",
            ),
            _b("EventWorldModel", IMPLEMENTED, "dcm.sports.football.ledger:build_football_world"),
            _b("PrimitiveOutcomeSchema", IMPLEMENTED, "dcm.sports.football.registry:PRIMITIVE_SPECS"),
            _b("ConservationRules", IMPLEMENTED, "dcm.sports.football.conservation:evaluate_football_conservation"),
            _b("MarketDefinitionRegistry", IMPLEMENTED, "dcm.sports.football.registry:lookup_market"),
            _b("DistributionRegistry", IMPLEMENTED, "dcm.model.distributions:from_worlds"),
            _b(
                "FeatureSchema",
                PARTIAL,
                "dcm.ml.feature_store:FEATURE_FAMILIES",
                "Current feature schema is not yet universal and does not expose all gridiron-specific opportunity families.",
            ),
            _b("MLModelRegistry", IMPLEMENTED, "dcm.learning.registry:load_registry"),
            _b("CalibrationPolicy", IMPLEMENTED, "dcm.learning.calibration:apply_calibration"),
            _b("AvailabilityPolicy", IMPLEMENTED, "dcm.model.availability:availability_mixture"),
            _b("SettlementRules", IMPLEMENTED, "dcm.platform.prizepicks.settlement:settle_world_lineup"),
            _b("RebootDNPPolicy", IMPLEMENTED, "dcm.platform.prizepicks.reboot:evaluate_reboot"),
            _b(
                "ValidationSuite",
                PARTIAL,
                "dcm.runtime.readiness:build_readiness",
                "Sport tests exist, but the validation suite is not yet a single plugin-owned contract.",
            ),
        ),
    )
)
