"""Constitution document, identity, and HAR execution-plan gates."""
from __future__ import annotations

from dcm.algorithms.constitution import (
    ALGORITHM_CONSTITUTION_VERSION,
    constitution_identity,
    constitution_sha256,
    load_constitution_text,
    prompt_declared_constitution_sha256,
)
from dcm.algorithms.execution_plan import build_har_algorithm_execution_plan
from dcm.algorithms.registry import load_algorithm_registry
from dcm.algorithms.selection import AlgorithmSelectionEngine


def test_constitution_version_and_body():
    text = load_constitution_text()
    assert ALGORITHM_CONSTITUTION_VERSION in text
    assert "REQUIRED_CORE" in text
    assert "REQUIRED_CONDITIONAL" in text
    assert "PERMANENT_CHALLENGER" in text
    assert "Weighted set-cover" in text or "Weighted set cover" in text
    assert "Submodular" in text or "submodular" in text
    ident = constitution_identity()
    assert ident["version"] == ALGORITHM_CONSTITUTION_VERSION
    assert len(ident["sha256"]) == 64
    assert ident["sha256"] == constitution_sha256(text)
    assert ident["promptDeclaredSha256"] == "bba7b082bf67e12d87e675ac58d5b6f96d9cbad9b6a487a0aa157bf7cef9e599"
    assert ident["promptDeclaredSha256"] == prompt_declared_constitution_sha256()
    assert ident["registrySha256"]


def test_har_algorithm_execution_plan_before_research():
    plan = build_har_algorithm_execution_plan({"n_offers": 8, "hnsw_installed": False, "leiden_installed": False})
    payload = plan.to_dict()
    assert payload["researchMayBegin"] is True
    assert payload["constitutionVersion"] == ALGORITHM_CONSTITUTION_VERSION
    assert payload["constitutionSha256"] == constitution_sha256()
    assert payload["algorithmRegistrySha256"]
    assert payload["planHash"]
    phase_ids = [p["phaseId"] for p in payload["phases"]]
    assert "H0_SAFE_PARSE" in phase_ids
    assert "H2_GROUP" in phase_ids
    assert "H6_SCHEDULE" in phase_ids
    assert "H7_RANK" in phase_ids
    assert any(p["algorithmId"] == "ALG-GROUP-001" for p in payload["phases"] if p["phaseId"] == "H2_GROUP")
    assert "ALG-SEARCH-023" in payload["evaluatedConditionals"] or any(
        "CONDITIONAL_NOT_ACTIVATED:ALG-SEARCH-023" in r for s in payload["selections"] for r in s["reasons"]
    ) or any("CONDITIONAL_NOT_ACTIVATED" in r for s in payload["selections"] for r in s["reasons"])
    engine = AlgorithmSelectionEngine()
    fuzzy = engine.select("FUZZY_IDENTITY", {"exact_hit": True, "consumer": "test"})
    assert fuzzy.selected_algorithm_id == "ALG-SEARCH-001"
    ann = engine.select("SEMANTIC_ANN", {"hnsw_installed": False, "consumer": "test"})
    assert ann.selected_algorithm_id != "ALG-SEARCH-023" or not ann.activated
    sched = engine.select("RESEARCH_SCHEDULE", {"one_prop_one_search": True, "consumer": "test"})
    assert "ONE_PROP_ONE_SEARCH_NONCOMPLIANT" in sched.reasons
    assert len(load_algorithm_registry()) >= 150
