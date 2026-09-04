"""CFB reference-implementation helpers consumed by the canonical runner and dcm-host.

Does not replace EvidenceGraph, ResearchStore, ranking, SportPlugin, or freeze.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dcm.algorithms.control_plane import (
    AlgorithmApplicabilityEvaluator,
    AlgorithmBenchmarkRegistry,
    AlgorithmFallbackResolver,
    unused_algorithm_audit,
)
from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.cfb.accounting import account_cfb_board
from dcm.cfb.champion import select_cfb_champions
from dcm.cfb.coextract import fanout_acceptance, harvest_structured_page, FULL_STRUCTURED_PAGE_WHEN_CHEAP
from dcm.cfb.frontier import run_frontier_loop
from dcm.cfb.har_delta import classify_board_delta
from dcm.cfb.markets import inventory_raw_labels, NEWLY_ACTIVATED_MARKETS, cfb_market_execution_matrix
from dcm.cfb.reports import (
    cfb_playables_final,
    cfb_prop_flags,
    frontier_offer_ids,
)
from dcm.contracts.hashes import content_hash
from dcm.research.acquisition import build_acquisition_actions, schedule_acquisition_actions
from dcm.research.cache_layers import ResearchCacheCascade
from dcm.research.indexes import BoardIndexes, EvidenceIndexes
from dcm.research.material_facts import facts_to_features, resolve_material_facts
from dcm.research.os_graphs import persist_research_os_graphs
from dcm.research.readiness import evaluate_research_os_readiness, persist_research_os_readiness
from dcm.research.source_health import default_cfb_source_health
from dcm.runtime.drive_catalog import DriveObjectCatalog


def _write(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return payload


def prepare_cfb_research_os(
    dest: Path,
    rows: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    *,
    claims: list[dict[str, Any]] | None = None,
    coverage: dict[str, Any] | None = None,
    telemetry: AlgorithmTelemetry | None = None,
    frontier_offer_ids_set: set[str] | None = None,
) -> dict[str, Any]:
    """Emit graphs, indexes, and live AcquisitionActions BEFORE web acquisition."""
    dest = Path(dest)
    tel = telemetry or AlgorithmTelemetry()
    accounting = _write(dest / "CFB_HAR_ACCOUNTING.json", account_cfb_board(rows))
    raw_labels = [str(r.get("marketLabel") or r.get("statType") or r.get("market") or "") for r in rows if str(r.get("league") or "").upper() == "CFB"]
    inventory = _write(dest / "CFB_MARKET_INVENTORY.json", inventory_raw_labels([x for x in raw_labels if x]))
    indexes = BoardIndexes(rows, telemetry=tel)
    identity = indexes.resolve_identities()
    indexes.requirement_bitmaps(requests[:32] if len(requests) > 32 else requests)
    graphs = persist_research_os_graphs(dest, rows, requests, telemetry=tel, indexes=indexes)
    evidence = EvidenceIndexes(claims or [], telemetry=tel)
    reused = 0
    for req in requests:
        hits = evidence.lookup_scope(str(req.get("scope") or ""), str(req.get("scope_id") or ""))
        if hits:
            reused += 1
    health = default_cfb_source_health()
    for claim in claims or []:
        sid = str(claim.get("source_id") or claim.get("sourceId") or "")
        if sid:
            health.record_success(sid, yield_n=1, freshness=float(claim.get("freshness") or 0.5) if claim.get("freshness") is not None else None)
    routed = {
        "EVENT": health.route(claim_type="EVENT", sport="CFB"),
        "SUBJECT": health.route(claim_type="SUBJECT", sport="CFB"),
        "AFFILIATION": health.route(claim_type="AFFILIATION", sport="CFB"),
        "ENVIRONMENT": health.route(claim_type="ENVIRONMENT", sport="CFB"),
    }
    routing = health.snapshot()
    routing["routedByClaimType"] = routed
    _write(dest / "source_health.json", routing)
    facts = resolve_material_facts(claims or [], cutoff=None)
    _write(dest / "material_facts.json", facts)
    feature_records = facts_to_features(facts)
    _write(dest / "material_fact_features.json", {
        "schema": "pillars_dcm.material_fact_features.v1",
        "count": len(feature_records),
        "records": feature_records,
        "contentHash": content_hash({"count": len(feature_records), "keys": [r.get("factKey") for r in feature_records]}),
    })
    catalog = DriveObjectCatalog(dest)
    for claim in claims or []:
        digest = str(claim.get("claim_hash") or content_hash(dict(claim)))
        catalog.put(digest, {"kind": "EVIDENCE_CLAIM", "scope": claim.get("semantic_scope") or claim.get("scope"), "scopeId": claim.get("scope_id")})
    identified = {
        digest: catalog.identify(digest)
        for digest in list(catalog.by_hash)[:32]
    }
    _write(dest / "drive_object_catalog.json", {
        **catalog.snapshot(),
        "identifiedEvidence": {k: {"present": v.get("present"), "lookup": v.get("lookup")} for k, v in identified.items()},
        "note": "Identify evidence hashes only. Drive fetch is host-side and fail-closes when unconfigured.",
    })
    cascade = ResearchCacheCascade(dest, drive=catalog)
    for claim in claims or []:
        cascade.put(
            str(claim.get("semantic_scope") or claim.get("scope") or ""),
            str(claim.get("scope_id") or ""),
            dict(claim),
            claim_type=str(claim.get("claim_type") or ""),
        )
    cache_hits = 0
    cache_lookups = 0
    for req in requests:
        rec, layer = cascade.get(str(req.get("scope") or ""), str(req.get("scope_id") or ""))
        cache_lookups += 1
        if rec is not None:
            cache_hits += 1
    cache_snap = cascade.snapshot()
    cache_snap["requestLookups"] = cache_lookups
    cache_snap["requestHits"] = cache_hits
    _write(dest / "research_cache_cascade.json", cache_snap)
    cascade.close()
    prior_board = dest / "board.json"
    prev_rows: list[dict[str, Any]] = []
    if prior_board.is_file():
        try:
            prev_payload = json.loads(prior_board.read_text(encoding="utf-8"))
            prev_rows = list(prev_payload.get("rows") or []) if isinstance(prev_payload, dict) else []
        except (OSError, json.JSONDecodeError):
            prev_rows = []
    delta = classify_board_delta(prev_rows, rows)
    _write(dest / "cfb_har_delta.json", delta)
    pages: list[dict[str, Any]] = []
    acquired_pages: list[dict[str, Any]] = []
    for claim in claims or []:
        page = claim.get("structured_page") or claim.get("page")
        if isinstance(page, dict):
            acquired_pages.append(page)
    if acquired_pages:
        for page in acquired_pages:
            harvested = harvest_structured_page(page, rows, policy=FULL_STRUCTURED_PAGE_WHEN_CHEAP)
            pages.append(harvested)
        coextract_status = "ACQUIRED_STRUCTURED_PAGES"
    else:
        coextract_status = "NO_ACQUIRED_STRUCTURED_PAGE"
    _write(dest / "cfb_coextraction.json", {
        "schema": "pillars_dcm.cfb_coextraction_run.v1",
        "status": coextract_status,
        "pages": pages,
        "pageCount": len(pages),
        "note": "harvest_structured_page consumes host-acquired pages only; HAR board rows are not reconstructed into fake gamebooks.",
    })
    evaluator = AlgorithmApplicabilityEvaluator()
    fallback = AlgorithmFallbackResolver()
    bench = AlgorithmBenchmarkRegistry()
    control = {
        "schema": "pillars_dcm.cfb_control_plane.v1",
        "applicability": [
            evaluator.evaluate("RESEARCH_SCHEDULE", {"consumer": "dcm.cfb.launch", "one_prop_one_search": False}),
            evaluator.evaluate("FUZZY_IDENTITY", {"exact_hit": True, "consumer": "dcm.cfb.launch"}),
            evaluator.evaluate("SEMANTIC_ANN", {"hnsw_installed": False, "consumer": "dcm.cfb.launch"}),
        ],
        "fallback": fallback.resolve("ALG-SEARCH-023", "SEMANTIC_ANN", {"hnsw_installed": False}),
        "benchmarks": bench.snapshot(),
    }
    control["contentHash"] = content_hash({k: v for k, v in control.items() if k != "contentHash"})
    _write(dest / "algorithm_control_plane.json", control)
    actions = build_acquisition_actions(
        rows,
        requests,
        coverage=coverage,
        evidence=evidence,
        frontier_offer_ids=frontier_offer_ids_set,
        telemetry=tel,
        source_health=health,
    )
    schedule = schedule_acquisition_actions(actions, telemetry=tel)
    _write(dest / "acquisition_actions.json", actions)
    _write(dest / "acquisition_schedule.json", schedule)
    fanout = fanout_acceptance(actions, requests)
    _write(dest / "cfb_fanout_acceptance.json", fanout)
    index_meta = {
        "schema": "pillars_dcm.board_indexes.v1",
        "offerCount": len(indexes.offer_by_id),
        "compositeKeys": len(indexes.composite),
        "events": len(indexes.by_event),
        "subjects": len(indexes.by_subject),
        "reusedEvidenceScopes": reused,
        "queriedEvents": int(identity.get("queriedEvents") or 0),
        "exactIdentityCount": int(identity.get("exactCount") or 0),
        "skippedFuzzy": int(identity.get("skippedFuzzy") or 0),
        "fuzzyHits": int(identity.get("fuzzyCount") or 0),
        "nearDuplicatePairs": int(identity.get("nearDuplicatePairs") or 0),
        "identityFirst": True,
        "algorithms": [
            "ALG-INDEX-001", "ALG-SEARCH-002", "ALG-INDEX-002", "ALG-INDEX-009",
            "ALG-SEARCH-008", "ALG-INDEX-016",
        ],
        "retrievalCascade": identity.get("retrievalCascade") or {},
        "note": "Fuzzy/FTS/RRF/MMR/LSH execute only on projectionId miss. Exact IDs skip them.",
    }
    index_meta["contentHash"] = content_hash(index_meta)
    _write(dest / "board_indexes.json", index_meta)
    readiness = evaluate_research_os_readiness(
        board_graph=graphs["boardGraph"],
        market_demand_graph=graphs["marketDemandGraph"],
        requirement_graph=graphs["requirementGraph"],
        indexes_meta=index_meta,
        reused_evidence_scopes=reused,
        acquisition_actions=actions,
        source_routing=routing,
    )
    persist_research_os_readiness(dest, readiness)
    indexes.close()
    evidence.close()
    return {
        "accounting": accounting,
        "inventory": inventory,
        "boardGraph": graphs["boardGraph"],
        "marketDemandGraph": graphs["marketDemandGraph"],
        "requirementGraph": graphs["requirementGraph"],
        "acquisitionActions": actions,
        "acquisitionSchedule": schedule,
        "reusedEvidenceScopes": reused,
        "readiness": readiness,
        "materialFacts": facts,
        "sourceHealth": routing,
        "harDelta": delta,
        "cacheCascade": cache_snap,
        "fanout": fanout,
        "controlPlane": control,
        "telemetry": tel,
        "identity": identity,
        "featureRecords": feature_records,
        "coextractionStatus": coextract_status,
    }


def attach_cfb_prop_flags(classified: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for rec in classified:
        row = rec.get("row") if isinstance(rec.get("row"), dict) else {}
        if str(row.get("league") or "").upper() != "CFB":
            continue
        rec.update(cfb_prop_flags(rec))
    return classified


def emit_cfb_forecast_artifacts(
    dest: Path,
    *,
    modeled: list[dict[str, Any]],
    qualified: list[dict[str, Any]],
    classified: list[dict[str, Any]],
    telemetry: AlgorithmTelemetry | None = None,
    unresolved_actions: int = 0,
    evidence_imported: bool = False,
    material_facts: dict[str, Any] | None = None,
    actions: dict[str, Any] | None = None,
    host_required: bool = False,
) -> dict[str, Any]:
    dest = Path(dest)
    tel = telemetry or AlgorithmTelemetry()
    attach_cfb_prop_flags(classified)
    loop = run_frontier_loop(
        modeled,
        telemetry=tel,
        unresolved_actions=unresolved_actions,
        evidence_imported=evidence_imported,
        material_facts=material_facts,
        actions=actions,
        host_required=host_required,
    )
    top100 = loop["preliminary"]
    top25 = loop["top25"]
    playables = cfb_playables_final(qualified, telemetry=tel)
    cfb_modeled = [
        p for p in modeled
        if str(((p.get("row") if isinstance(p.get("row"), dict) else p).get("league") or "")).upper() == "CFB"
    ]
    if cfb_modeled:
        _write(dest / "cfb_ml_primitives.json", {
            "schema": "pillars_dcm.cfb_ml_primitives.v1",
            "empiricalBayes": "ACTIVE_IN_PARAMETER_SNAPSHOT",
            "empiricalBayesAlgorithmId": "ALG-ML-PROB-001",
            "isotonic": "INACTIVE_ZERO_ELIGIBLE_SETTLEMENTS",
            "conformal": "INACTIVE_INSUFFICIENT_CALIBRATION_DATA",
            "ood": "ACTIVE_ON_FEATURE_STATE",
            "oodAlgorithmId": "ALG-UNCERTAINTY-004",
            "championSelector": "SHADOW_DIAGNOSTIC",
            "learningRevision": "LR000000",
            "predictiveClaim": "NONE",
            "note": "Isotonic and conformal stay inactive at LR000000. Empirical Bayes already produced ParameterSnapshots. OOD uses log feature state, never current-slate p.",
        })
        tel.record(
            "ALG-ML-PROB-001",
            problem_class="SHRINKAGE",
            producer="dcm.model.gridiron_models.empirical_bayes_shrink",
            consumer="dcm.model.parameters.build_parameter_snapshot",
            artifact="parameters/snapshots.json",
            count=len(cfb_modeled),
            note="Champion producer already executed inside ParameterSnapshots; launch does not re-shrink current-slate p",
            phase="EXECUTED",
            downstream_used=True,
            lifecycle_state="EXECUTED",
        )
        tel.record(
            "ALG-CAL-001",
            problem_class="CALIBRATION",
            producer="dcm.algorithms.ml_families.isotonic_regression",
            consumer="dcm.cfb.launch.emit_cfb_forecast_artifacts",
            artifact="cfb_ml_primitives.json",
            count=1,
            note="chronological settlement cells empty at LR000000; isotonic not trained",
            phase="INACTIVE_INSUFFICIENT_DATA",
            activated=False,
            lifecycle_state="INACTIVE_INSUFFICIENT_DATA",
        )
        tel.record(
            "ALG-UNCERTAINTY-001",
            problem_class="CONFORMAL",
            producer="dcm.algorithms.ml_families.split_conformal",
            consumer="dcm.runner.run_dcm",
            artifact="cfb_ml_primitives.json",
            count=1,
            note="no chronological calibration residuals; conformal inactive",
            phase="INACTIVE_INSUFFICIENT_DATA",
            activated=False,
            lifecycle_state="INACTIVE_INSUFFICIENT_DATA",
        )
        tel.record(
            "ALG-UNCERTAINTY-004",
            problem_class="OOD",
            producer="dcm.algorithms.ml_families.zscore_ood",
            consumer="dcm.model.parameters.build_parameter_snapshot",
            artifact="parameters/snapshots.json",
            count=len(cfb_modeled),
            note="OOD on log/opportunity feature state; never mapped into P(Higher)",
            phase="EXECUTED",
            downstream_used=True,
        )
        champions = select_cfb_champions(cfb_modeled)
        _write(dest / "cfb_champion_challenger.json", champions)
        tel.record(
            "ALG-ML-TABULAR-001",
            problem_class="ML_TABULAR",
            producer="dcm.cfb.champion.select_cfb_champions",
            consumer="dcm.cfb.launch.emit_cfb_forecast_artifacts",
            artifact="cfb_champion_challenger.json",
            count=int(champions.get("marketCount") or 0),
            note="Selector table is SHADOW_DIAGNOSTIC; actual producer is Empirical Bayes in snapshots",
            phase="SHADOW_DIAGNOSTIC",
            activated=False,
            lifecycle_state="SHADOW_DIAGNOSTIC",
        )
        matrix = cfb_market_execution_matrix()
        _write(dest / "cfb_market_execution_matrix.json", matrix)
    _write(dest / "CFB_TOP100_PRELIMINARY.json", top100)
    _write(dest / "CFB_TOP25_FINAL.json", top25)
    _write(dest / "CFB_PLAYABLES_FINAL.json", playables)
    _write(dest / "cfb_frontier_loop.json", loop["loop"])
    flags = {
        "schema": "pillars_dcm.cfb_prop_states.v1",
        "globalCoverageComplete": all(bool(cfb_prop_flags(p).get("propResearchComplete")) for p in classified if str((p.get("row") or {}).get("league") or "").upper() == "CFB") if classified else False,
        "rows": [
            {
                "offer_id": (p.get("row") or {}).get("projectionId"),
                **cfb_prop_flags(p),
                "state": p.get("state"),
                "grade": p.get("grade"),
                "blocker": p.get("blocker"),
            }
            for p in classified
            if str((p.get("row") or {}).get("league") or "").upper() == "CFB"
        ],
    }
    flags["contentHash"] = content_hash({k: v for k, v in flags.items() if k != "contentHash"})
    _write(dest / "cfb_prop_states.json", flags)
    report = {
        "schema": "pillars_dcm.cfb_launch_report.v1",
        "learningRevision": "LR000000",
        "predictiveClaim": "NONE",
        "productionRootCertified": False,
        "hostComputesProbabilities": False,
        "newMarketsActivatedToday": list(NEWLY_ACTIVATED_MARKETS),
        "top100Count": int(top100.get("count") or 0),
        "top25Count": int(top25.get("count") or 0),
        "playablesCount": int(playables.get("count") or 0),
        "frontierResearchPasses": int(loop["loop"].get("frontierPassCount") or 0),
        "top25Final": bool(top25.get("final")),
        "modeledCfbOffers": len(cfb_modeled),
        "classifiedCfbOffers": len(flags["rows"]),
        "modelableCount": sum(1 for r in flags["rows"] if r.get("propModelable")),
        "playableEligibleCount": sum(1 for r in flags["rows"] if r.get("propPlayableEligible")),
        "frontierEligibleCount": sum(1 for r in flags["rows"] if r.get("propFrontierResearchEligible")),
        "researchCompleteCount": sum(1 for r in flags["rows"] if r.get("propResearchComplete")),
        "top100Hash": top100.get("contentHash"),
        "top25Hash": top25.get("contentHash"),
        "playablesHash": playables.get("contentHash"),
        "note": "Top100/Top25 are rankings of modeled CFB, not recommendations. Empty playables is legal.",
    }
    report["contentHash"] = content_hash({k: v for k, v in report.items() if k != "contentHash"})
    _write(dest / "CFB_LAUNCH_REPORT.json", report)
    return {
        "top100": top100,
        "top25": top25,
        "playables": playables,
        "frontierOfferIds": sorted(frontier_offer_ids(top100)),
        "frontierLoop": loop["loop"],
        "report": report,
        "telemetry": tel,
    }


def persist_algorithm_telemetry(dest: Path, telemetry: AlgorithmTelemetry) -> dict[str, Any]:
    dest = Path(dest)
    snap = telemetry.snapshot()
    _write(dest / "algorithm_execution_telemetry.json", snap)
    audit = unused_algorithm_audit(telemetry)
    _write(dest / "unused_algorithm_audit.json", audit)
    return snap
