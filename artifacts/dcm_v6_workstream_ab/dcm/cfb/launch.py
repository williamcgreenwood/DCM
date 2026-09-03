"""Guarded CFB launch helpers consumed by the canonical runner and dcm-host.

Does not replace EvidenceGraph, ResearchStore, ranking, SportPlugin, or freeze.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.cfb.accounting import account_cfb_board
from dcm.cfb.reports import (
    cfb_playables_final,
    cfb_prop_flags,
    cfb_top100_preliminary,
    cfb_top25_final,
    frontier_offer_ids,
)
from dcm.contracts.hashes import content_hash
from dcm.research.acquisition import build_acquisition_actions, schedule_acquisition_actions
from dcm.research.indexes import BoardIndexes, EvidenceIndexes
from dcm.research.os_graphs import persist_research_os_graphs


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
    indexes = BoardIndexes(rows, telemetry=tel)
    graphs = persist_research_os_graphs(dest, rows, requests, telemetry=tel, indexes=indexes)
    evidence = EvidenceIndexes(claims or [], telemetry=tel)
    reused = 0
    for req in requests:
        hits = evidence.lookup_scope(str(req.get("scope") or ""), str(req.get("scope_id") or ""))
        if hits:
            reused += 1
    actions = build_acquisition_actions(
        rows,
        requests,
        coverage=coverage,
        evidence=evidence,
        frontier_offer_ids=frontier_offer_ids_set,
        telemetry=tel,
    )
    schedule = schedule_acquisition_actions(actions, telemetry=tel)
    _write(dest / "acquisition_actions.json", actions)
    _write(dest / "acquisition_schedule.json", schedule)
    index_meta = {
        "schema": "pillars_dcm.board_indexes.v1",
        "offerCount": len(indexes.offer_by_id),
        "compositeKeys": len(indexes.composite),
        "events": len(indexes.by_event),
        "subjects": len(indexes.by_subject),
        "reusedEvidenceScopes": reused,
        "algorithms": ["ALG-INDEX-001", "ALG-SEARCH-002", "ALG-INDEX-002", "ALG-INDEX-009", "ALG-SEARCH-008", "ALG-INDEX-016"],
    }
    index_meta["contentHash"] = content_hash(index_meta)
    _write(dest / "board_indexes.json", index_meta)
    indexes.close()
    evidence.close()
    return {
        "accounting": accounting,
        "boardGraph": graphs["boardGraph"],
        "marketDemandGraph": graphs["marketDemandGraph"],
        "requirementGraph": graphs["requirementGraph"],
        "acquisitionActions": actions,
        "acquisitionSchedule": schedule,
        "reusedEvidenceScopes": reused,
        "telemetry": tel,
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
) -> dict[str, Any]:
    dest = Path(dest)
    tel = telemetry or AlgorithmTelemetry()
    attach_cfb_prop_flags(classified)
    top100 = cfb_top100_preliminary(modeled, telemetry=tel)
    top25 = cfb_top25_final(modeled, telemetry=tel)
    playables = cfb_playables_final(qualified, telemetry=tel)
    cfb_modeled = [
        p for p in modeled
        if str(((p.get("row") if isinstance(p.get("row"), dict) else p).get("league") or "")).upper() == "CFB"
    ]
    if cfb_modeled:
        tel.record(
            "ALG-ML-PROB-001",
            problem_class="SHRINKAGE",
            producer="dcm.model.parameters.build_parameter_snapshot",
            consumer="dcm.cfb.launch.emit_cfb_forecast_artifacts",
            artifact="parameters/snapshots.json",
            count=len(cfb_modeled),
            note="Empirical Bayes / RoleEpoch shrinkage already executed during snapshot build",
        )
        tel.record(
            "ALG-CAL-001",
            problem_class="CALIBRATION",
            producer="dcm.learning.calibration.apply_calibration",
            consumer="dcm.runner.run_dcm",
            artifact="CFB_TOP100_PRELIMINARY.json",
            count=len(cfb_modeled),
            note="chronological cells only; empty cells pass through raw p",
        )
        tel.record(
            "ALG-UNCERTAINTY-001",
            problem_class="CONFORMAL",
            producer="dcm.model.uncertainty.probability_bundle",
            consumer="dcm.runner.run_dcm",
            artifact="CFB_TOP100_PRELIMINARY.json",
            count=len(cfb_modeled),
            note="probability persisted separately from Reliability/DQ/Volatility/Fragility/OOD",
        )
    _write(dest / "CFB_TOP100_PRELIMINARY.json", top100)
    _write(dest / "CFB_TOP25_FINAL.json", top25)
    _write(dest / "CFB_PLAYABLES_FINAL.json", playables)
    flags = {
        "schema": "pillars_dcm.cfb_prop_states.v1",
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
        "newMarketsActivatedToday": [],
        "top100Count": int(top100.get("count") or 0),
        "top25Count": int(top25.get("count") or 0),
        "playablesCount": int(playables.get("count") or 0),
        "modeledCfbOffers": len(cfb_modeled),
        "classifiedCfbOffers": len(flags["rows"]),
        "modelableCount": sum(1 for r in flags["rows"] if r.get("propModelable")),
        "playableEligibleCount": sum(1 for r in flags["rows"] if r.get("propPlayableEligible")),
        "frontierEligibleCount": sum(1 for r in flags["rows"] if r.get("propFrontierResearchEligible")),
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
        "report": report,
        "telemetry": tel,
    }


def persist_algorithm_telemetry(dest: Path, telemetry: AlgorithmTelemetry) -> dict[str, Any]:
    dest = Path(dest)
    snap = telemetry.snapshot()
    _write(dest / "algorithm_execution_telemetry.json", snap)
    return snap
