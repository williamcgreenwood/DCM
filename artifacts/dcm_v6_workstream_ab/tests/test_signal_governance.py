from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.ml.feature_store import SIGNAL_FEATURE_CONSUMER, signal_evaluation_feature_records
from dcm.signals.compiler import SignalCompiler
from dcm.signals.contracts import LifecycleState, SignalField, SignalOperatorSpec, SignalStage
from dcm.signals.donor_accounting import audit_donor_matrix
from dcm.signals.executor import SignalExecutor
from dcm.signals.integration_gate import BindingCatalog


ROOT = Path(__file__).resolve().parents[3]
DONOR_MATRIX = ROOT / "docs" / "donor" / "p380x" / "DONOR_COMPONENT_MATRIX.json"
SCHEMA = ROOT / "artifacts" / "dcm_v6_workstream_ab" / "dcm" / "signals" / "schemas" / "SignalOperatorSpec.schema.json"


def field(name: str = "minutes", unit: str = "minute", temporal: str = "PRE_CUTOFF") -> SignalField:
    return SignalField(name=name, unit=unit, dimension="count", temporal_class=temporal)


def spec(operator_id: str, **overrides) -> SignalOperatorSpec:
    values = {
        "operator_id": operator_id,
        "version": "1.0.0",
        "stage": SignalStage.FEATURE,
        "family": "OPPORTUNITY",
        "sports": ("basketball",),
        "competitions": ("NBA",),
        "market_definitions": ("pts",),
        "semantic_scopes": ("Subject", "Event", "MarketDefinition"),
        "required_inputs": (field(),),
        "outputs": (field("minutes_signal", "minute"),),
        "transformation_id": "identity.v1",
        "lifecycle_state": LifecycleState.ACTIVE_FEATURE,
        "consumers": (SIGNAL_FEATURE_CONSUMER,),
        "tests": ("test_signal_governance",),
    }
    values.update(overrides)
    return SignalOperatorSpec(**values)


def compiled_one(candidate: SignalOperatorSpec, catalog: BindingCatalog | None = None):
    return SignalCompiler(catalog).compile([candidate]).operators[0]


def test_active_operator_with_zero_consumer_fails_activation():
    item = compiled_one(spec("orphan", consumers=()))
    assert item.lifecycle_state == LifecycleState.REJECTED_INVALID
    assert "ACTIVE_OPERATOR_CONSUMER_REQUIRED" in item.reasons


def test_dependency_cycle_fails_compile():
    registry = SignalCompiler().compile([
        spec("a", dependencies=("b",), transformation_id="a.v1"),
        spec("b", dependencies=("a",), transformation_id="b.v1"),
    ])
    assert registry.execution_order == ()
    assert all("DEPENDENCY_CYCLE" in item.reasons for item in registry.operators)


def test_active_dependency_must_also_be_executable():
    registry = SignalCompiler().compile([
        spec("candidate_parent", lifecycle_state=LifecycleState.CANDIDATE, transformation_id="parent.v1"),
        spec("active_child", dependencies=("candidate_parent",), transformation_id="child.v1"),
    ])
    child = registry.by_id()["active_child"]
    assert child.lifecycle_state == LifecycleState.REJECTED_INVALID
    assert "DEPENDENCY_NOT_EXECUTABLE:candidate_parent" in child.reasons


def test_missing_unit_or_dimension_fails_contract_ingestion():
    with pytest.raises(ValueError, match="SIGNAL_FIELD_UNIT_REQUIRED"):
        field(unit="")
    with pytest.raises(ValueError, match="SIGNAL_FIELD_DIMENSION_REQUIRED"):
        SignalField(name="minutes", unit="minute", dimension="")


def test_baseball_pitch_operator_cannot_bind_to_hockey_generically():
    candidate = spec(
        "fragile_arm",
        sports=("hockey",),
        competitions=("NHL",),
        market_definitions=(),
        required_inputs=(field("pitch_count", "pitch"),),
        outputs=(field("arm_fatigue", "index"),),
        transformation_id="rolling_pitch_load.v1",
    )
    item = compiled_one(candidate)
    assert item.lifecycle_state == LifecycleState.REJECTED_INVALID
    assert "NORMALIZED_FIELD_UNAVAILABLE:hockey:pitch_count" in item.reasons


def test_invalid_market_definition_pair_fails():
    candidate = spec(
        "bad_market",
        sports=("baseball",),
        competitions=("MLB",),
        market_definitions=("pts",),
        required_inputs=(field("pitch_count", "pitch"),),
    )
    item = compiled_one(candidate)
    assert any(reason.startswith("MARKET_DEFINITION_UNSUPPORTED:baseball:MLB:pts") for reason in item.reasons)


def test_post_cutoff_input_fails():
    item = compiled_one(spec("leak", required_inputs=(field(temporal="POST_CUTOFF"),)))
    assert "POST_CUTOFF_INPUT_FORBIDDEN:minutes" in item.reasons


def test_compiled_hash_is_deterministic_across_source_ordering():
    candidates = [spec("a", transformation_id="a.v1"), spec("b", transformation_id="b.v1")]
    forward = SignalCompiler().compile(candidates)
    reverse = SignalCompiler().compile(list(reversed(candidates)))
    assert forward.registry_hash == reverse.registry_hash
    assert forward.execution_order == reverse.execution_order


def test_semantic_duplicates_do_not_execute_twice():
    candidates = [spec("alias_a"), spec("alias_b")]
    registry = SignalCompiler().compile(candidates)
    assert registry.counts()["REJECTED_DUPLICATE"] == 1
    calls = []

    def handler(inputs, deps):
        calls.append(inputs["minutes"])
        return {"minutes_signal": inputs["minutes"]}

    evaluations = SignalExecutor(registry, {"alias_a": handler, "alias_b": handler}).execute({"minutes": 30})
    assert len(evaluations) == 1
    assert calls == [30]


def test_overlap_groups_are_preserved_for_related_non_duplicates():
    registry = SignalCompiler().compile([
        spec("rolling_5", overlap_group="RECENT_MINUTES", transformation_id="rolling_mean.5"),
        spec("rolling_10", overlap_group="RECENT_MINUTES", transformation_id="rolling_mean.10"),
    ])
    assert {item.overlap_group for item in registry.operators} == {"RECENT_MINUTES"}
    assert len(registry.execution_order) == 2


@pytest.mark.parametrize("behavior", ["FORCED_PREDICTION", "CONFIDENCE_TO_PROBABILITY", "PARLAY_FILLER"])
def test_rejected_donor_behavior_cannot_activate(behavior):
    item = compiled_one(spec(f"forbidden_{behavior.lower()}", behavior_class=behavior))
    assert item.lifecycle_state == LifecycleState.REJECTED_INVALID
    assert f"FORBIDDEN_BEHAVIOR_CLASS:{behavior}" in item.reasons


def test_probability_and_hard_gate_override_flags_are_structurally_impossible():
    with pytest.raises(ValueError, match="DIRECT_PROBABILITY_CHANGE_FORBIDDEN"):
        spec("probability_mutator", can_change_probability_directly=True)
    with pytest.raises(ValueError, match="HARD_GATE_OVERRIDE_FORBIDDEN"):
        spec("gate_override", can_override_hard_gate=True)


def test_active_hard_gate_requires_canonical_authorization():
    candidate = spec(
        "gate",
        stage=SignalStage.HARD_GATE,
        lifecycle_state=LifecycleState.ACTIVE_HARD_GATE,
        hard_gate_authorization="UNSUPPORTED_MARKET_GATE",
    )
    rejected = compiled_one(candidate)
    assert rejected.lifecycle_state == LifecycleState.REJECTED_INVALID
    catalog = BindingCatalog(hard_gate_authorizations=frozenset({"UNSUPPORTED_MARKET_GATE"}))
    accepted = compiled_one(candidate, catalog)
    assert accepted.lifecycle_state == LifecycleState.ACTIVE_HARD_GATE


def test_feature_store_is_an_explicit_runtime_consumer():
    registry = SignalCompiler().compile([spec("minutes_context")])
    evaluations = SignalExecutor(
        registry,
        {"minutes_context": lambda inputs, deps: {"minutes_signal": inputs["minutes"] / 48.0}},
    ).execute({"minutes": 36})
    records = signal_evaluation_feature_records(
        evaluations, entity="player-1", event_id="event-1", as_of="2026-09-01T00:00:00Z"
    )
    assert len(records) == 1
    assert records[0]["featureName"] == "signal:minutes_context:minutes_signal"
    assert records[0]["signalEvaluationHash"] == evaluations[0].output_hash
    assert "probability" not in records[0]


def test_donor_matrix_accounts_for_all_58_without_activation():
    report = audit_donor_matrix(DONOR_MATRIX)
    assert report.component_count == 58
    assert report.active_count == 0
    assert report.complete is True
    assert report.exact_archive_state == "EXACT_ARCHIVE_BYTES_UNAVAILABLE"
    assert sum(report.disposition_counts.values()) == 58


def test_donor_matrix_cannot_silently_self_activate(tmp_path):
    payload = json.loads(DONOR_MATRIX.read_text())
    payload["components"][0]["active"] = True
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="DONOR_MATRIX_CANNOT_SELF_ACTIVATE"):
        audit_donor_matrix(path)


def test_schema_is_draft_2020_12_and_source_parse_is_non_destructive():
    schema = json.loads(SCHEMA.read_text())
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    source = {
        "operator_id": "source",
        "version": "1",
        "stage": "FEATURE",
        "family": "OPPORTUNITY",
        "sports": ["basketball"],
        "required_inputs": [{"name": "minutes", "unit": "minute", "dimension": "count"}],
        "outputs": [{"name": "minutes_signal", "unit": "minute", "dimension": "count"}],
        "transformation_id": "identity.v1",
        "lifecycle_state": "CANDIDATE",
        "can_change_probability_directly": False,
        "can_override_hard_gate": False,
        "extension": {"allOf": [{"$ref": "#/$defs/field"}], "oneOf": [1, 2]},
    }
    before = json.loads(json.dumps(source))
    SignalOperatorSpec.from_mapping(source)
    assert source == before
