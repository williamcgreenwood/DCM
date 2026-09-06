"""AlgorithmSelectionEngine: cheapest exact deterministic strategy first."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dcm.algorithms.contracts import AlgorithmRecord, AlgorithmSelection
from dcm.algorithms.registry import load_algorithm_registry, require_algorithm

PROBLEM_DEFAULTS = {
    "EXACT_IDENTITY": "ALG-SEARCH-001",
    "COMPOSITE_KEY": "ALG-SEARCH-002",
    "ORDERED_RANGE": "ALG-SEARCH-003",
    "LEXICAL_RANK": "ALG-SEARCH-005",
    "MULTI_ALIAS_SCAN": "ALG-SEARCH-008",
    "PREFIX_ALIAS": "ALG-SEARCH-009",
    "FUZZY_IDENTITY": "ALG-SEARCH-010",
    "NEAR_DUPLICATE": "ALG-SEARCH-011",
    "TEXT_DUPLICATE": "ALG-SEARCH-012",
    "HYBRID_FUSION": "ALG-SEARCH-014",
    "RESULT_DIVERSITY": "ALG-SEARCH-015",
    "GRAPH_TRAVERSAL": "ALG-SEARCH-016",
    "SET_COVER": "ALG-SEARCH-019",
    "SUBMODULAR": "ALG-SEARCH-020",
    "SEMANTIC_ANN": "ALG-SEARCH-023",
    "HOT_HASH_INDEX": "ALG-INDEX-001",
    "SQLITE_INDEX": "ALG-INDEX-002",
    "BLOOM_REJECT": "ALG-INDEX-009",
    "CONTENT_ADDRESS": "ALG-INDEX-016",
    "MERKLE_INTEGRITY": "ALG-INDEX-017",
    "FINAL_RANK": "ALG-SORT-001",
    "TOPK_PARTIAL": "ALG-SORT-003",
    "DEPENDENCY_ORDER": "ALG-SORT-008",
    "HAR_GROUPING": "ALG-GROUP-001",
    "ENTITY_MERGE": "ALG-GROUP-002",
    "RESEARCH_COMMUNITY": "ALG-GROUP-003",
    "CYCLE_SAFETY": "ALG-GROUP-004",
    "RESEARCH_SCHEDULE": "ALG-SCHED-001",
    "BATCH_PACK": "ALG-SCHED-003",
    "HOT_CACHE": "ALG-CACHE-001",
    "CALIBRATION": "ALG-CAL-001",
    "CONFORMAL": "ALG-UNCERTAINTY-001",
    "OOD": "ALG-UNCERTAINTY-004",
    "DRIFT": "ALG-ML-TIME-003",
    "SHRINKAGE": "ALG-ML-PROB-001",
}


@dataclass
class AlgorithmSelectionEngine:
    records: tuple[AlgorithmRecord, ...] | None = None

    def __post_init__(self) -> None:
        if self.records is None:
            self.records = load_algorithm_registry()
        self._by_id = {r.algorithm_id: r for r in self.records}

    def record(self, algorithm_id: str) -> AlgorithmRecord:
        rec = self._by_id.get(algorithm_id)
        if rec is None:
            rec = require_algorithm(algorithm_id)
        return rec

    def select(self, problem_class: str, context: Mapping[str, Any] | None = None) -> AlgorithmSelection:
        ctx = dict(context or {})
        consumer = str(ctx.get("consumer") or "HarAlgorithmExecutionPlan")
        default_id = PROBLEM_DEFAULTS.get(str(problem_class).upper())
        if not default_id:
            default_id = "ALG-SEARCH-001"
        primary = self.record(default_id)
        reasons = [
            "CHEAPEST_EXACT_DETERMINISTIC",
            f"PROBLEM_CLASS:{problem_class}",
            f"LIFECYCLE:{primary.lifecycle}",
        ]
        evaluated: list[str] = []
        selected = primary
        activated = True

        if problem_class.upper() == "SEMANTIC_ANN":
            evaluated.append("ALG-SEARCH-023")
            if not ctx.get("hnsw_installed"):
                selected = self.record("ALG-SEARCH-005")
                reasons.append("HNSW_UNAVAILABLE_USE_LEXICAL_OR_BRUTE_COSINE")
                reasons.append("CONDITIONAL_NOT_ACTIVATED:ALG-SEARCH-023")
        if problem_class.upper() == "BATCH_PACK" and not ctx.get("cpsat_available"):
            evaluated.append("ALG-SCHED-005")
            reasons.append("CONDITIONAL_NOT_ACTIVATED:ALG-SCHED-005")
        if problem_class.upper() == "RESEARCH_COMMUNITY" and not ctx.get("leiden_installed"):
            evaluated.append("ALG-GROUP-011")
            reasons.append("CONDITIONAL_NOT_ACTIVATED:ALG-GROUP-011")
            selected = self.record("ALG-GROUP-003")
        if problem_class.upper() == "TOPK_PARTIAL":
            n = int(ctx.get("n") or 0)
            k = int(ctx.get("k") or 0)
            if n and k and k * 8 < n:
                selected = self.record("ALG-SORT-003")
                reasons.append("HEAP_PARTIAL_SELECT_K_LL_N")
            else:
                selected = self.record("ALG-SORT-001")
                reasons.append("FULL_STABLE_SORT_COMPETITIVE")
        if problem_class.upper() == "FUZZY_IDENTITY" and ctx.get("exact_hit"):
            selected = self.record("ALG-SEARCH-001")
            reasons.append("EXACT_HIT_SKIPS_FUZZY")
        if problem_class.upper() in {"SET_COVER", "SUBMODULAR", "RESEARCH_SCHEDULE"} and ctx.get("one_prop_one_search"):
            reasons.append("ONE_PROP_ONE_SEARCH_NONCOMPLIANT")
            selected = self.record("ALG-SCHED-001")

        if selected.lifecycle == "PERMANENT_CHALLENGER":
            activated = False
            reasons.append("CHALLENGER_NOT_PRODUCTION_ACTIVE")
            if selected.fallback_algorithm_id:
                selected = self.record(selected.fallback_algorithm_id)
                activated = True
                reasons.append(f"FALLBACK:{selected.algorithm_id}")

        candidates = tuple(
            r.algorithm_id
            for r in self.records or ()
            if r.algorithm_family == primary.algorithm_family and r.lifecycle != "PERMANENT_CHALLENGER"
        )[:8] or (primary.algorithm_id,)
        return AlgorithmSelection(
            problem_class=str(problem_class),
            selected_algorithm_id=selected.algorithm_id,
            candidates=candidates,
            reasons=tuple(reasons),
            fallback_algorithm_id=selected.fallback_algorithm_id,
            benchmark_threshold=str(ctx.get("benchmark_threshold") or selected.time_complexity_expectation),
            consumer=consumer,
            activated=activated,
            evaluated_conditionals=tuple(evaluated),
        )
