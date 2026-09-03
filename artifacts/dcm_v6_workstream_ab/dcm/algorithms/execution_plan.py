"""HAR AlgorithmExecutionPlan: emitted before external research."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from dcm.algorithms.constitution import ALGORITHM_CONSTITUTION_VERSION, constitution_sha256
from dcm.algorithms.contracts import AlgorithmSelection, HarAlgorithmExecutionPlan
from dcm.algorithms.indexing import merkle_root
from dcm.algorithms.registry import algorithm_registry_sha256
from dcm.algorithms.selection import AlgorithmSelectionEngine
from dcm.contracts.hashes import content_hash


HAR_PHASES = (
    ("H0_SAFE_PARSE", "CONTENT_ADDRESS", "streaming/safe parse + payload hash"),
    ("H1_CANONICALIZE", "EXACT_IDENTITY", "canonical identity resolution"),
    ("H1_ALIAS", "MULTI_ALIAS_SCAN", "Aho-Corasick/trie alias recognition"),
    ("H1_DEDUP", "NEAR_DUPLICATE", "hash/MinHash/SimHash duplicate detection"),
    ("H2_GROUP", "HAR_GROUPING", "composite-key grouping"),
    ("H2_MERGE", "ENTITY_MERGE", "Union-Find alias consolidation"),
    ("H2_COMMUNITY", "RESEARCH_COMMUNITY", "connected components"),
    ("H3_INDEX", "HOT_HASH_INDEX", "L0 hash + L1 sqlite composite indexes"),
    ("H4_GRAPH", "GRAPH_TRAVERSAL", "forward/reverse graph/hypergraph"),
    ("H4_CYCLES", "CYCLE_SAFETY", "Tarjan SCC / topo validation"),
    ("H5_RETRIEVE", "EXACT_IDENTITY", "reusable-evidence cheapest-exact retrieval"),
    ("H6_SCHEDULE", "RESEARCH_SCHEDULE", "weighted set-cover / submodular lazy heap"),
    ("H6_PACK", "BATCH_PACK", "constrained batch packing"),
    ("H7_TOPK", "TOPK_PARTIAL", "frontier partial selection"),
    ("H7_RANK", "FINAL_RANK", "deterministic stable ranking"),
    ("H8_PERSIST", "MERKLE_INTEGRITY", "content-address + Merkle run integrity"),
    ("H8_CACHE", "HOT_CACHE", "current-run cache before Drive/web"),
)


def build_har_algorithm_execution_plan(
    context: Mapping[str, Any] | None = None,
    *,
    engine: AlgorithmSelectionEngine | None = None,
) -> HarAlgorithmExecutionPlan:
    ctx = dict(context or {})
    engine = engine or AlgorithmSelectionEngine()
    selections: list[AlgorithmSelection] = []
    phases: list[dict[str, Any]] = []
    evaluated: list[str] = []
    for phase_id, problem, note in HAR_PHASES:
        sel = engine.select(problem, {**ctx, "consumer": f"HarAlgorithmExecutionPlan.{phase_id}"})
        selections.append(sel)
        evaluated.extend(sel.evaluated_conditionals)
        phases.append(
            {
                "phaseId": phase_id,
                "problemClass": problem,
                "algorithmId": sel.selected_algorithm_id,
                "activated": sel.activated,
                "reasons": list(sel.reasons),
                "note": note,
            }
        )
    # BoardGraph/RequirementGraph remain R1. Research may begin only after the
    # algorithm plan exists; those graphs are recorded as not-yet-claimed.
    notes = [
        "R0 emits AlgorithmExecutionPlan before research.",
        "BoardGraph/MarketDemandGraph/RequirementGraph remain the next Research OS tranche and are not claimed complete.",
        "One-prop-one-search is non-compliant when shared evidence can satisfy multiple requirements.",
    ]
    payload = {
        "schema": "pillars_dcm.har_algorithm_execution_plan.v1",
        "constitutionVersion": ALGORITHM_CONSTITUTION_VERSION,
        "constitutionSha256": constitution_sha256(),
        "algorithmRegistrySha256": algorithm_registry_sha256(),
        "phases": phases,
        "selections": [s.to_dict() for s in selections],
        "evaluatedConditionals": list(dict.fromkeys(evaluated)),
        "notes": notes,
        "nOffers": ctx.get("n_offers"),
        "nEvents": ctx.get("n_events"),
    }
    plan_hash = content_hash(payload)
    merkle = merkle_root(
        [
            payload["constitutionSha256"],
            payload["algorithmRegistrySha256"],
            plan_hash,
        ]
    )
    payload["planMerkle"] = merkle
    return HarAlgorithmExecutionPlan(
        schema=payload["schema"],
        constitution_version=ALGORITHM_CONSTITUTION_VERSION,
        constitution_sha256=payload["constitutionSha256"],
        registry_sha256=payload["algorithmRegistrySha256"],
        phases=tuple(phases),
        selections=tuple(selections),
        evaluated_conditionals=tuple(payload["evaluatedConditionals"]),
        plan_hash=plan_hash,
        research_may_begin=True,
        notes=tuple(notes),
    )


def constitution_run_hashes(plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sidecar hashes for hashes.json. Not forecast-semantic fields."""
    ident = {
        "algorithmConstitutionVersion": ALGORITHM_CONSTITUTION_VERSION,
        "algorithmConstitutionSha256": constitution_sha256(),
        "algorithmRegistrySha256": algorithm_registry_sha256(),
    }
    if plan:
        ident["algorithmExecutionPlanHash"] = plan.get("planHash")
        ident["runMerkleRoot"] = merkle_root(
            [
                ident["algorithmConstitutionSha256"],
                ident["algorithmRegistrySha256"],
                str(plan.get("planHash") or ""),
            ]
        )
    return ident


def persist_har_algorithm_execution_plan(dest: Path, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    plan = build_har_algorithm_execution_plan(context)
    payload = plan.to_dict()
    import json

    (dest / "algorithm_execution_plan.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload
