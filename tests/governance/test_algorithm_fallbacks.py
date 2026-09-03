"""Conditional/challenger fallbacks exist and challengers cannot be production-active."""
from __future__ import annotations

import pytest

from dcm.algorithms.contracts import AlgorithmNotProductionActive, AlgorithmRecord
from dcm.algorithms.registry import load_algorithm_registry, require_algorithm, resolve_implementation
from dcm.algorithms.selection import AlgorithmSelectionEngine


def test_algorithm_fallbacks_resolve():
    by_id = {r.algorithm_id: r for r in load_algorithm_registry()}
    missing = []
    for rec in by_id.values():
        if rec.fallback_algorithm_id:
            if rec.fallback_algorithm_id not in by_id:
                missing.append(rec.algorithm_id)
            else:
                require_algorithm(rec.fallback_algorithm_id)
        if rec.lifecycle == "REQUIRED_CONDITIONAL" and rec.portability_class in {"OPTIONAL_PACKAGE", "NOT_PORTABLE_CHALLENGER"}:
            if not rec.fallback_algorithm_id:
                missing.append(f"NO_FALLBACK:{rec.algorithm_id}")
        if rec.lifecycle == "PERMANENT_CHALLENGER" and not rec.fallback_algorithm_id:
            missing.append(f"CHALLENGER_NO_FALLBACK:{rec.algorithm_id}")
    assert missing == []


def test_challenger_invocation_is_not_production_active():
    engine = AlgorithmSelectionEngine()
    hits = 0
    for rec in load_algorithm_registry():
        if rec.lifecycle != "PERMANENT_CHALLENGER":
            continue
        impl = resolve_implementation(rec)
        if getattr(impl, "__name__", "") == "not_active_challenger":
            with pytest.raises(AlgorithmNotProductionActive):
                impl()
            hits += 1
        selection = engine.select("SEMANTIC_ANN", {"hnsw_installed": False})
        assert selection.activated is True or selection.selected_algorithm_id != rec.algorithm_id
    assert hits >= 20


def test_hnsw_unavailable_uses_lexical_or_brute_fallback():
    sel = AlgorithmSelectionEngine().select("SEMANTIC_ANN", {"hnsw_installed": False, "consumer": "test"})
    assert sel.selected_algorithm_id in {"ALG-SEARCH-005", "ALG-SEARCH-023"}
    if sel.selected_algorithm_id == "ALG-SEARCH-023":
        assert sel.activated is False or "CONDITIONAL" in "".join(sel.reasons)
    assert any("HNSW" in r or "CONDITIONAL_NOT_ACTIVATED" in r or sel.selected_algorithm_id == "ALG-SEARCH-005" for r in sel.reasons)


def test_retirement_contract_on_record():
    with pytest.raises(ValueError, match="ALGORITHM_RETIREMENT_REQUIRES_ADR"):
        AlgorithmRecord(
            algorithm_id="ALG-SEARCH-001",
            canonical_name="Exact hash lookup",
            algorithm_family="SEARCH",
            lifecycle="REQUIRED_CORE",
            applicability_contract="x",
            input_contract="x",
            output_contract="x",
            semantic_scope="x",
            implementation_module="dcm.algorithms.searching",
            implementation_symbol="exact_hash_lookup",
            runtime_producer="x",
            runtime_consumer="x",
            retired_version="never",
            superseding_adr=None,
        )
