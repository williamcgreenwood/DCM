"""Top-level DCM runner: HAR → research → worlds → grade → rank → freeze.

python -m dcm.runner --synthetic --out dcm_v6/RUNS
python -m dcm.runner --resume RUNS/<id>/checkpoint.json

LR000000. Predictive claim NONE. Not optimized DCM 6.0.
Does not require the user to supply player logs: FixtureProvider fills structured evidence.
Live web research is FileProvider after the operator writes evidence/.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.algorithms.execution_plan import constitution_run_hashes, persist_har_algorithm_execution_plan
from dcm.algorithms.telemetry import AlgorithmTelemetry
from dcm.cfb.event_worlds import cfb_teammate_groups, simulate_joint_cfb_event_worlds
from dcm.cfb.launch import emit_cfb_forecast_artifacts, persist_algorithm_telemetry, prepare_cfb_research_os
from dcm.cfb.recompute import recompute_full_bundle
from dcm.cfb.refresh import apply_final_refresh
from dcm.research.material_facts import apply_hold_playable, facts_to_features, hold_playable_scope_ids, resolve_material_facts
from dcm.contracts.hashes import content_hash
from dcm.identity.resolve import build_player_index, freeze_map, resolve_row
from dcm.ingest.board import freeze_board, write_board
from dcm.ingest.composite import compose_ingests
from dcm.ingest.har import ingest_har
from dcm.model.distributions import from_worlds
from dcm.model.explanation import (
    build_prop_explanation,
    load_feature_hash_index,
    persist_prop_explanations,
)
from dcm.model.grade import grade as grade_of
from dcm.model.line_surface import surface as line_surface
from dcm.model.parameters import build_parameter_snapshot
from dcm.model.ranking import rank_candidates
from dcm.model.uncertainty import PROBABILITY_CONTRACT_KEYS, RELIABILITY_IS_NOT_PROBABILITY, probability_bundle
from dcm.learning.calibration import apply_calibration, cell_key
from dcm.learning.sidecar import append_ledger_jsonl, append_record
from dcm.model.event_world_joint import (
    basketball_teammate_groups,
    simulate_joint_team_worlds,
    summarize_joint_meta,
)
from dcm.model.market_derive import UnknownMarketError
from dcm.model.quarter_worlds import QuarterPluginIncomplete
from dcm.model.worlds import generate_event_contexts, simulate_player_worlds, value_from_stats
from dcm.research.cache import ResearchCache
from dcm.research.classify import accounting_classify as _classify
from dcm.research.emit import emit_offer_sets_and_manifest, emit_packets_and_graph
from dcm.research.evidence_graph import attach_runtime_lineage
from dcm.research.host_plan import build_host_research_plan
from dcm.research.provider import BundleProvider, FileProvider, FixtureProvider, collect, write_bundle
from dcm.research.requests import plan_research
from dcm.runtime.checkpoint import load_checkpoint, write_checkpoint
from dcm.runtime.cutoff import CutoffRequired, POLICY_DOC, resolve_forecast_cutoff
from dcm.runtime.dag import Dag
from dcm.runtime.freeze import compute_forecast_hash
from dcm.runtime.github_archive import append_index, build_run_audit, certification_fields, materialize_github_pack, push_to_github
from dcm.runtime.governor import Governor
from dcm.runtime.mount_v541 import mount_default
from dcm.runtime.schema_root import SCHEMA_V2_ID, verify_schema, verify_schema_v2
from dcm.runtime.perf import StageTimer
from dcm.runtime.readiness import build_readiness
from dcm.runtime.store import IndexedStore
from dcm.selection.card_layers import (
    EMPTY_ACCOUNT_ONLY,
    EMPTY_ROOT_NOT_CERTIFIED,
    NOT_PRODUCTION_ROOT_CERTIFIED,
    STATUS_START_HARD_BLOCKERS,
    apply_pre_freeze_status_start_gates,
    build_directional_passes,
    is_modeled_playable,
    layer_run_state,
    modeled_empty_card_reason,
    production_certified_rows,
    production_root_accepted,
    started_event_blocker,
    status_start_hard_blocker,
    write_card_layer_files,
)
from dcm.selection.portfolio import build_card, exposure_report
from dcm.version import (
    ExactVersionMismatch,
    LEARNING_REVISION,
    PREDICTIVE_CLAIM,
    SOFTWARE,
    resolve_requested_version,
)

SCHEMA = "PHASE_BC_SCHEMA_V1_2026-08-25"
N_WORLDS = int(__import__("os").environ.get("DCM_FAST_WORLDS", "256"))
N_SERIOUS = int(__import__("os").environ.get("DCM_SERIOUS_WORLDS", "2048"))
N_MAX = int(__import__("os").environ.get("DCM_MAX_WORLDS", "8192"))
MC_SE_TARGET = float(__import__("os").environ.get("DCM_MC_SE_TARGET", "0.008"))

ARTIFACT_ROOT = Path(__file__).resolve().parents[1]
_REPO_CANDIDATE = Path(__file__).resolve().parents[3] if len(Path(__file__).resolve().parents) > 3 else Path.cwd()
DEFAULT_WORKSPACE = _REPO_CANDIDATE if (_REPO_CANDIDATE / "VERSION.json").is_file() else Path.cwd()


def _finalize_archive(
    dest: Path,
    result: dict[str, Any],
    *,
    archive_github: bool = False,
    archive_push: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Always write dest/audit/. Optionally copy+commit+push a GitHub pack."""
    try:
        audit = build_run_audit(dest)
    except Exception as exc:  # noqa: BLE001 — never lose a finished run to archive I/O
        result["auditError"] = type(exc).__name__
        result.setdefault("modelRunCertified", False)
        result.setdefault("selectionCertified", False)
        result.setdefault("evidenceCoverageCertified", False)
        result.setdefault("evidenceTemporalCertified", False)
        result.setdefault("archiveIntegrityCertified", False)
        result.setdefault("productionRootCertified", False)
        result.setdefault("predictiveValidationEarned", False)
        result.setdefault("hashCertifiedPythonFreeze", False)
        result.setdefault("hallucinationRisk", True)
        return result
    result.update(certification_fields(audit))
    result["hallucinationRisk"] = bool(audit.get("hallucinationRisk"))
    result["archivePath"] = str(Path(dest) / "audit")
    result["githubCommit"] = None
    if not archive_github:
        return result
    root = Path(repo_root) if repo_root is not None else DEFAULT_WORKSPACE
    try:
        pack = materialize_github_pack(Path(dest), root)
        run_id = str(result.get("run_id") or audit.get("runId") or Path(dest).name)
        append_index(
            root,
            {
                "runId": run_id,
                "path": f"audit/runs/{run_id}",
                "hallucinationRisk": audit.get("hallucinationRisk"),
                "runState": audit.get("runState") or result.get("runState"),
                "frozenForecastHash": audit.get("frozenForecastHash"),
                "createdAtUtc": audit.get("createdAtUtc"),
                "software": audit.get("software") or SOFTWARE,
                "learningRevision": audit.get("learningRevision") or LEARNING_REVISION,
                "predictiveClaim": audit.get("predictiveClaim") or PREDICTIVE_CLAIM,
                **certification_fields(audit),
            },
        )
        gh = push_to_github(root, run_id, push=bool(archive_push))
        result["archivePath"] = str(pack)
        result["githubCommit"] = gh.get("commit")
        result["githubPushed"] = gh.get("pushed")
        if gh.get("error"):
            result["archiveError"] = gh.get("error")
    except Exception as exc:  # noqa: BLE001
        result["archiveError"] = type(exc).__name__
    return result



def _synthetic_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent / "data" / "synthetic_har.json",
        ARTIFACT_ROOT / "fixtures" / "synthetic_har.json",
        DEFAULT_WORKSPACE / "artifacts" / "dcm_v6_workstream_ab" / "fixtures" / "synthetic_har.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]

SYNTHETIC = _synthetic_path()

def _run_id(har_sha: str, cutoff: str) -> str:
    return "RUN_" + content_hash({"har": har_sha, "cutoff": cutoff, "sw": SOFTWARE})[:16]


def _git_commit_sha(workspace: Path) -> str | None:
    """Best-effort git HEAD. Never writes git config. Missing git is None, not a crash."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    sha = (proc.stdout or "").strip()
    if proc.returncode != 0 or not sha:
        return None
    if any(c not in "0123456789abcdefABCDEF" for c in sha):
        return None
    return sha


def _default_model_config() -> dict[str, Any]:
    return {
        "software": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "fastWorlds": N_WORLDS,
        "seriousWorlds": N_SERIOUS,
        "ceilingWorlds": max(N_SERIOUS, N_MAX),
        "mcSeTarget": MC_SE_TARGET,
    }


def _active_calibration(workspace: Path) -> dict[str, Any]:
    path = workspace / "dcm_v6" / "calibration" / "active_cells.json"
    try:
        cells = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        cells = {}
    return {"cells": cells, "contentHash": content_hash(cells)}


def run_dcm(
    *,
    input_path: Path | None,
    forecast_cutoff: str | None,
    input_paths: list[Path] | None = None,
    output_root: Path,
    synthetic: bool = False,
    research: str = "file",
    evidence_dir: Path | None = None,
    workspace: Path = DEFAULT_WORKSPACE,
    resume: Path | None = None,
    account_only: bool = False,
    bundle_path: Path | None = None,
    research_shadow: bool = False,
    cutoff_from_capture: bool = False,
    archive_github: bool = False,
    archive_push: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if resume:
        ck = load_checkpoint(resume)
        output_root = Path(ck["artifactRoot"])
        # Re-enter from HAR freeze artifacts (deterministic).
        board = json.loads((output_root / "board.json").read_text(encoding="utf-8"))
        ingest_meta = json.loads((output_root / "input_manifest.json").read_text(encoding="utf-8"))
        mount = json.loads((output_root / "MOUNT_STATE.json").read_text(encoding="utf-8"))
        schema_path = output_root / "SCHEMA_STATE.json"
        schema_root = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.is_file() else verify_schema(workspace)
        har_sha = ingest_meta["harSha256"]
        # Frozen source provenance is authoritative on resume. A resume-time CLI
        # default must never change forecast semantics or production gating.
        forecast_cutoff = str(ck.get("forecastCutoff") or board.get("forecastCutoff") or forecast_cutoff or "")
        if not forecast_cutoff:
            raise CutoffRequired("FORECAST_CUTOFF_REQUIRED: resume checkpoint is missing forecastCutoff")
        research_shadow = bool(ck.get("researchShadow", research_shadow))
        synthetic = bool(ingest_meta.get("synthetic", board.get("synthetic", False)))
        run_id = ck["runId"]
        dest = output_root
        model_config_path = dest / "MODEL_CONFIG.json"
        calibration_state_path = dest / "CALIBRATION_STATE.json"
        if not model_config_path.is_file():
            raise RuntimeError("MODEL_CONFIG_MISSING_ON_RESUME")
        if not calibration_state_path.is_file():
            raise RuntimeError("CALIBRATION_STATE_MISSING_ON_RESUME")
        model_config = json.loads(model_config_path.read_text(encoding="utf-8"))
        calibration_state = json.loads(calibration_state_path.read_text(encoding="utf-8"))
        calibration_cells = calibration_state.get("cells") or {}

        board_payload = {k: v for k, v in board.items() if k != "contentHash"}
        if str(board.get("contentHash") or "") != content_hash(board_payload):
            raise RuntimeError("BOARD_HASH_MISMATCH_ON_RESUME")
        if str(board.get("harSha256") or "") != str(ingest_meta.get("harSha256") or ""):
            raise RuntimeError("INPUT_MANIFEST_BOARD_SOURCE_MISMATCH")
        if str(ck.get("modelConfigHash") or "") != content_hash(model_config):
            raise RuntimeError("MODEL_CONFIG_HASH_MISMATCH_ON_RESUME")
        if str(calibration_state.get("contentHash") or "") != content_hash(calibration_cells):
            raise RuntimeError("CALIBRATION_STATE_SELF_HASH_MISMATCH")
        if str(ck.get("calibrationStateHash") or "") != str(calibration_state.get("contentHash") or ""):
            raise RuntimeError("CALIBRATION_STATE_HASH_MISMATCH_ON_RESUME")
        if str(ck.get("mountStateHash") or "") != content_hash(mount):
            raise RuntimeError("MOUNT_STATE_HASH_MISMATCH_ON_RESUME")
        if str(ck.get("schemaStateHash") or "") != content_hash(schema_root):
            raise RuntimeError("SCHEMA_STATE_HASH_MISMATCH_ON_RESUME")
        stages_done = set(ck.get("completedStages") or [])
    else:
        stages_done = set()
        mount = mount_default(workspace)
        schema_root = verify_schema(workspace)
        t = StageTimer("HAR")
        if synthetic:
            raw = json.loads(SYNTHETIC.read_text(encoding="utf-8"))
            raw_bytes = SYNTHETIC.read_bytes()
            ingests = [ingest_har(raw, raw_bytes=raw_bytes)]
        else:
            sources = list(input_paths or ([] if input_path is None else [input_path]))
            if not sources or any(not p.is_file() for p in sources):
                raise FileNotFoundError("HAR missing. Pass one or more --input values or --synthetic.")
            ingests = []
            for source in sources:
                raw_bytes = source.read_bytes()
                ingests.append(ingest_har(raw_bytes, raw_bytes=raw_bytes))
        ingest = compose_ingests(ingests) if len(ingests) > 1 else ingests[0]
        cutoff_info = resolve_forecast_cutoff(
            explicit=forecast_cutoff,
            from_capture=cutoff_from_capture,
            ingest=ingest,
        )
        forecast_cutoff = str(cutoff_info["cutoff"])
        har_sha = ingest["harSha256"]
        run_id = _run_id(har_sha, forecast_cutoff)
        dest = output_root / run_id
        dest.mkdir(parents=True, exist_ok=True)
        model_config = _default_model_config()
        calibration_state = _active_calibration(workspace)
        (dest / "MODEL_CONFIG.json").write_text(
            json.dumps(model_config, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (dest / "CALIBRATION_STATE.json").write_text(
            json.dumps(calibration_state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        calibration_cells = calibration_state.get("cells") or {}
        board = freeze_board(ingest, mount=mount, cutoff=forecast_cutoff, asof_policy="account_capture")
        write_board(board, dest / "board.json")
        (dest / "input_manifest.json").write_text(
            json.dumps(
                {
                    "harSha256": har_sha,
                    "sourceHarSha256s": ingest.get("contributingHarSha256s") or [har_sha],
                    "compositeCaptureId": ingest.get("compositeCaptureId"),
                    "adapter": ingest["adapter"],
                    "parserVersion": ingest["parserVersion"],
                    "synthetic": bool(ingest.get("synthetic")),
                    "sourceMode": (
                        "SYNTHETIC"
                        if bool(ingest.get("synthetic"))
                        else "MULTI_HAR_COMPOSITE"
                        if ingest.get("compositeCaptureId")
                        else "CAPTURED_HAR"
                    ),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (dest / "MOUNT_STATE.json").write_text(json.dumps(mount, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        schema_v2 = verify_schema_v2(workspace)
        schema_root = {**schema_root, "v2": schema_v2, "workingSchemaId": SCHEMA_V2_ID}
        (dest / "SCHEMA_STATE.json").write_text(json.dumps(schema_root, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        stages_done.add("BOARD_FREEZE")
        har_perf = t.finish(InputRows=len(board["rows"]), OutputRows=len(board["rows"]))
        (dest / "logs").mkdir(exist_ok=True)
        (dest / "performance").mkdir(exist_ok=True)
        (dest / "performance" / "har.json").write_text(json.dumps(har_perf, indent=2) + "\n", encoding="utf-8")

    config_hash = content_hash(model_config)
    dag = Dag(
        cutoff=forecast_cutoff,
        config_hash=config_hash,
        schema_version=SCHEMA,
        source_versions={"har": har_sha, "parser": str(board.get("parserVersion")), "software": SOFTWARE},
    )
    n_board = dag.add("BOARD_FREEZE", "board")
    dag.complete(n_board.key, board["contentHash"])
    plan_payload = persist_har_algorithm_execution_plan(
        dest,
        {
            "n_offers": len(board.get("rows") or []),
            "har_sha256": har_sha,
            "consumer": "dcm.runner.run_dcm",
        },
    )
    telemetry = AlgorithmTelemetry()
    for phase in plan_payload.get("phases") or []:
        telemetry.record(
            str(phase.get("algorithmId") or "ALG-SEARCH-001"),
            problem_class=str(phase.get("problemClass") or ""),
            producer="dcm.algorithms.execution_plan.build_har_algorithm_execution_plan",
            consumer=f"HarAlgorithmExecutionPlan.{phase.get('phaseId')}",
            artifact="algorithm_execution_plan.json",
            activated=bool(phase.get("activated", True)),
            phase="SELECTED",
            note="plan selection is not live execution", downstream_used=True)

    rows = [resolve_row(r) for r in board["rows"]]
    id_map = freeze_map(rows)
    (dest / "identities").mkdir(exist_ok=True)
    (dest / "identities" / "map.json").write_text(json.dumps(id_map, indent=2) + "\n", encoding="utf-8")
    player_index = build_player_index(rows)
    (dest / "identities" / "player_index.json").write_text(json.dumps(player_index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    n_id = dag.add("IDENTITY", "board", parents=[n_board.key])
    dag.complete(n_id.key, id_map["contentHash"])

    if account_only:
        classified = []
        counts = {"EXCLUDED_GOBLIN": 0, "UNSUPPORTED": 0, "UNRESOLVED": 0, "MODELED": 0, "SHADOW": 0}
        for row in rows:
            state, blocker = _classify(row)
            classified.append({"row": row, "state": state, "blocker": blocker, "grade": None})
            counts[state] = counts.get(state, 0) + 1
        acc = dict(board.get("accounting") or {})
        acc["classified"] = counts
        acc["goblins_excluded_from_selection"] = counts.get("EXCLUDED_GOBLIN", 0)
        (dest / "accounting.json").write_text(json.dumps(acc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (dest / "population_full.jsonl").write_text("".join(json.dumps({"projectionId": p["row"]["projectionId"], "state": p["state"], "blocker": p["blocker"], "league": p["row"].get("league"), "sportFamily": p["row"].get("sportFamily"), "modifier": p["row"].get("modifier"), "status": p["row"].get("status"), "offeredHigher": p["row"].get("offeredHigher"), "offeredLower": p["row"].get("offeredLower")}) + "\n" for p in classified), encoding="utf-8")
        (dest / "full_population.jsonl").write_text((dest / "population_full.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        hashes = {
            "boardHash": board.get("contentHash"),
            "harSha256": har_sha,
            "schemaV1Expected": "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22",
            **constitution_run_hashes(plan_payload),
        }
        (dest / "hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        persist_algorithm_telemetry(dest, telemetry)
        write_card_layer_files(
            dest,
            top25_ranked=[],
            strict_card=[],
            production_certified=[],
            directional_passes=[],
        )
        run_state = "COMPLETE_WITH_UNSUPPORTED_ROWS" if counts.get("UNSUPPORTED") else "EMPTY_CARD_COMPLETE"
        freeze = {
            "runId": run_id, "runState": run_state, "learningRevision": LEARNING_REVISION,
            "predictiveClaim": PREDICTIVE_CLAIM, "rawRows": len(rows), "accountOnly": True,
            "classified": counts, "boardHash": board.get("contentHash"),
            "cardSize": 0, "modeledCardSize": 0, "playable": 0,
            "productionCertified": False, "notProductionRootCertified": True,
            "productionRootCertification": NOT_PRODUCTION_ROOT_CERTIFIED,
            "executionMode": "RESEARCHED_MODELED",
            "emptyCardReason": EMPTY_ACCOUNT_ONLY,
            "productionEmptyCardReason": EMPTY_ROOT_NOT_CERTIFIED,
        }
        (dest / "freeze.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        planned = plan_research(rows, forecast_cutoff, research_shadow=research_shadow)
        (dest / "research_requests.json").write_text(
            json.dumps(planned["requests"], indent=2) + "\n", encoding="utf-8"
        )
        prepare_cfb_research_os(
            dest,
            rows,
            planned["requests"],
            coverage=None,
            telemetry=telemetry,
        )
        host_plan = build_host_research_plan(
            planned["requests"],
            skipped=planned["skipped"],
            entity_graph=planned["entity_graph"],
            unique_scopes=planned["unique_scopes"],
            eligible_prop_count=planned["eligible_prop_count"],
            research_shadow=research_shadow,
        )
        (dest / "host_research_plan.json").write_text(
            json.dumps(host_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        pop = emit_offer_sets_and_manifest(
            dest, rows, planned=planned, cutoff=forecast_cutoff, research_shadow=research_shadow
        )
        emit_packets_and_graph(
            dest, offer_sets=pop["offerSets"], claims=[], cutoff=forecast_cutoff, population=pop.get("manifest")
        )
        ck = write_checkpoint(dest / "checkpoint.json", {
            "runId": run_id, "dcmVersion": SOFTWARE, "learningRevision": LEARNING_REVISION,
            "forecastCutoff": forecast_cutoff, "artifactRoot": str(dest),
            "researchShadow": research_shadow,
            "completedStages": ["BOARD_FREEZE", "IDENTITY", "ACCOUNT", "RESEARCH_PLAN"],
            "pending": [], "nextDeterministicAction": "none", "rowCounts": counts,
            "modelConfigHash": content_hash(model_config),
            "calibrationStateHash": calibration_state.get("contentHash"),
            "mountStateHash": content_hash(mount),
            "schemaStateHash": content_hash(schema_root),
        })
        return _finalize_archive(
            dest,
            {"run_id": run_id, "dest": str(dest), "runState": run_state, "checkpoint": ck, "integrity": freeze, "board": board},
            archive_github=archive_github,
            archive_push=archive_push,
            repo_root=repo_root,
        )


    t = StageTimer("RESEARCH")
    planned = plan_research(rows, forecast_cutoff, research_shadow=research_shadow)
    requests = planned["requests"]
    (dest / "research_requests.json").write_text(json.dumps(requests, indent=2) + "\n", encoding="utf-8")
    from dcm.research.readiness import require_research_may_begin

    os_art = prepare_cfb_research_os(
        dest,
        rows,
        requests,
        coverage=None,
        telemetry=telemetry,
    )
    require_research_may_begin(dest)
    if research == "file":
        provider: Any = FileProvider(evidence_dir or dest / "evidence")
    elif research == "bundle":
        provider = BundleProvider(bundle_path or dest / "evidence_bundle.jsonl")
    else:
        provider = FixtureProvider(forecast_cutoff)
    research_cache = ResearchCache()
    bundle = collect(requests, provider, cache=research_cache)
    (dest / "evidence").mkdir(exist_ok=True)
    (dest / "evidence" / "claims.json").write_text(json.dumps(bundle["claims"], indent=2) + "\n", encoding="utf-8")
    written = write_bundle(dest / "evidence_bundle.jsonl", bundle["claims"])
    manifest = written.manifest({
        "harSha256": har_sha,
        "boardHash": board.get("contentHash"),
        "forecastCutoff": forecast_cutoff,
        "dcmVersion": SOFTWARE,
    })
    (dest / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "evidence" / "coverage.json").write_text(
        json.dumps(bundle.get("coverage") or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (dest / "evidence" / "conflicts.json").write_text(
        json.dumps(bundle.get("conflicts") or [], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    prepare_cfb_research_os(
        dest,
        rows,
        requests,
        claims=bundle.get("claims") or [],
        coverage=bundle.get("coverage"),
        telemetry=telemetry,
    )
    host_plan = build_host_research_plan(
        requests,
        coverage=bundle.get("coverage"),
        skipped=planned["skipped"],
        entity_graph=planned["entity_graph"],
        unique_scopes=planned["unique_scopes"],
        eligible_prop_count=planned["eligible_prop_count"],
        research_shadow=research_shadow,
    )
    (dest / "host_research_plan.json").write_text(
        json.dumps(host_plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pop = emit_offer_sets_and_manifest(
        dest, rows, planned=planned, cutoff=forecast_cutoff, research_shadow=research_shadow
    )
    emitted = emit_packets_and_graph(
        dest, offer_sets=pop["offerSets"], claims=bundle.get("claims") or [], cutoff=forecast_cutoff,
        population=pop.get("manifest"),
    )
    team_packet_map = {str(p.get("teamId")): p for p in (emitted.get("teamPackets") or []) if p.get("teamId")}
    event_packet_map = {str(p.get("eventId")): p for p in (emitted.get("eventPackets") or []) if p.get("eventId")}
    opponent_packet_map = {
        f"{p.get('eventId')}|{p.get('teamId')}": p for p in (emitted.get("opponentPackets") or [])
    }
    n_res = dag.add("EVIDENCE", "board", parents=[n_id.key])
    # Guarded CFB launch: preserve the established global checkpoint contract
    # for every other execution mode. Only a real (non-synthetic) board with CFB
    # offers may continue through partial research for per-prop modelability.
    cfb_guarded_research_continue = (
        not synthetic
        and bool(bundle.get("claims"))
        and any(
            str(r.get("sportFamily") or "") == "gridiron"
            and str(r.get("league") or "").upper() == "CFB"
            for r in rows
        )
    )
    if not bundle["complete"] and not cfb_guarded_research_continue:
        dag.block(n_res.key, "RESEARCH_INCOMPLETE")
        ck = write_checkpoint(
            dest / "checkpoint.json",
            {
                "runId": run_id,
                "dcmVersion": SOFTWARE,
                "learningRevision": LEARNING_REVISION,
                "forecastCutoff": forecast_cutoff,
                "modelConfigHash": config_hash,
                "calibrationStateHash": calibration_state.get("contentHash"),
                "mountStateHash": content_hash(mount),
                "schemaStateHash": content_hash(schema_root),
                "artifactRoot": str(dest),
                "completedStages": sorted(stages_done),
                "pending": ["EVIDENCE"],
                "nextDeterministicAction": "execute host_research_plan.json, write validated evidence files, then --resume checkpoint.json",
                "rowCounts": {"raw": len(rows)},
                "blockers": ["RESEARCH_INCOMPLETE"],
            },
        )
        return _finalize_archive(
            dest,
            {
                "run_id": run_id,
                "dest": str(dest),
                "runState": "INCOMPLETE_CHECKPOINTED",
                "checkpoint": ck,
                "research": bundle,
            },
            archive_github=archive_github,
            archive_push=archive_push,
            repo_root=repo_root,
        )
    if not bundle["complete"]:
        (dest / "research_partial.json").write_text(
            json.dumps(
                {
                    "state": "PARTIAL_RESEARCH_CONTINUE_CFB_PER_PROP",
                    "missingRequestIds": bundle.get("missing") or [],
                    "malformedRequestIds": bundle.get("malformed") or [],
                    "coverage": bundle.get("coverage") or {},
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
    dag.complete(n_res.key, content_hash([cl["claim_hash"] for cl in bundle["claims"]]))
    research_perf = t.finish(NodeCount=len(requests), CacheHits=bundle["reused"], ResearchCacheHits=bundle.get("cacheHits") or 0)
    (dest / "performance" / "research.json").write_text(json.dumps(research_perf, indent=2) + "\n", encoding="utf-8")
    stages_done.add("RESEARCH")

    canonical_ready = mount.get("state") == "HASH_VERIFIED_EXTRACTED"
    schema_ready = bool(schema_root.get("productionEligible")) and schema_root.get("state") == "HASH_VERIFIED"
    production_research_ready = bool(bundle.get("production_ready"))
    # Preserve the established root gate for non-CFB rows. CFB guarded launch
    # permits row-level selection eligibility only when that row's snapshot has
    # PLAYABLE support; global unrelated coverage remains an audit/certification
    # signal and cannot manufacture a PLAYABLE.
    root_selection_gate = canonical_ready and schema_ready and not synthetic
    global_selection_gate = root_selection_gate and production_research_ready

    gov = Governor(
        fast_worlds=int(model_config["fastWorlds"]),
        serious_worlds=int(model_config["seriousWorlds"]),
        ceiling_worlds=int(model_config["ceilingWorlds"]),
        mc_se_target=float(model_config["mcSeTarget"]),
    )
    t = StageTimer("MODEL")
    world_cache: dict[tuple[str, str, str], list[dict[str, float]]] = {}
    event_context_cache: dict[tuple[str, str, int], list[dict[str, float]]] = {}
    parameter_cache: dict[str, dict[str, Any]] = {}
    modeled: list[dict[str, Any]] = []
    classified: list[dict[str, Any]] = []
    conservation_failures = 0
    unsupported = excluded = unresolved = evidence_blocked = 0
    teammate_groups = basketball_teammate_groups(rows)
    cfb_groups = cfb_teammate_groups(rows)
    joint_world_cache: dict[tuple[str, str, int], dict[str, list[dict[str, float]]]] = {}
    joint_meta_acc: list[dict[str, Any]] = []
    material_facts_payload = resolve_material_facts(bundle.get("claims") or [], cutoff=forecast_cutoff)
    hold_ids = hold_playable_scope_ids(material_facts_payload)
    fact_features = facts_to_features(material_facts_payload, cutoff=forecast_cutoff)

    def _snapshot_for(prow: dict[str, Any]) -> dict[str, Any]:
        oid = str(prow.get("projectionId") or "")
        cached = parameter_cache.get(oid) if oid else None
        if cached is not None:
            return cached
        pid = str(prow.get("playerId") or "")
        eid = str(prow.get("eventId") or "")
        tid = str(prow.get("teamId") or prow.get("team") or "")
        opp = str(prow.get("opponentId") or prow.get("opponent") or "")
        relevant = [
            f for f in fact_features
            if str(f.get("scopeId") or "") in {pid, eid, tid, opp, f"env:{eid}", ""}
        ]
        snap = build_parameter_snapshot(
            prow,
            bundle["claims"],
            team_packets=team_packet_map,
            event_packets=event_packet_map,
            opponent_packets=opponent_packet_map,
            fact_features=relevant or None,
        )
        if oid:
            parameter_cache[oid] = snap
        return snap

    for row in rows:
        state, blocker = _classify(row)
        rec: dict[str, Any] = {"row": row, "state": state, "blocker": blocker}
        if state == "EXCLUDED_GOBLIN":
            excluded += 1; classified.append(rec); continue
        if state == "UNSUPPORTED":
            unsupported += 1; classified.append(rec); continue
        if state == "UNRESOLVED":
            unresolved += 1; classified.append(rec); continue

        snapshot = _snapshot_for(row)
        rec["forecastCutoff"] = forecast_cutoff
        rec["playerStatus"] = snapshot.get("status")
        rec["parameterSnapshot"] = snapshot
        rec["dependencyTags"] = snapshot.get("dependency_tags") or []
        # Status/start hard gates apply even on synthetic/fixture runs.
        snap_blocker = snapshot.get("blocker")
        if snap_blocker in STATUS_START_HARD_BLOCKERS:
            rec["blocker"] = rec.get("blocker") or snap_blocker
        start_blk = started_event_blocker(row, forecast_cutoff)
        if start_blk:
            rec["blocker"] = rec.get("blocker") or start_blk
        is_cfb_guarded_row = (
            str(row.get("sportFamily") or "") == "gridiron"
            and str(row.get("league") or "").upper() == "CFB"
        )
        minimum_model_support = bool(snapshot.get("minimum_model_support", snapshot.get("production_eligible")))
        if is_cfb_guarded_row and not minimum_model_support:
            rec["state"] = "HELD_FOR_RESEARCH"
            support = snapshot.get("model_support") if isinstance(snapshot.get("model_support"), dict) else {}
            blockers = support.get("modelBlockers") or []
            rec["blocker"] = rec.get("blocker") or (blockers[0] if blockers else snapshot.get("blocker") or "MINIMUM_MODEL_SUPPORT_MISSING")
            rec["productionSelectable"] = False
            evidence_blocked += 1
            classified.append(rec)
            continue

        diagnostic_model = is_cfb_guarded_row and not bool(snapshot["production_eligible"])
        row_selection_gate = root_selection_gate if is_cfb_guarded_row else global_selection_gate
        production_selectable = row_selection_gate and bool(snapshot["production_eligible"]) and rec.get("blocker") is None
        if diagnostic_model:
            rec["blocker"] = rec.get("blocker") or snapshot.get("blocker") or "PLAYABLE_SUPPORT_INCOMPLETE"
            evidence_blocked += 1

        key = (str(row["eventId"]), str(row["playerId"]), str(snapshot["parameter_snapshot_hash"]))
        board_id = str(row.get("boardId") or "FULL_GAME")
        try:
            if key not in world_cache:
                ctx_key = (str(row.get("sportFamily") or ""), str(row.get("eventId") or ""), gov.max_worlds)
                if ctx_key not in event_context_cache:
                    event_context_cache[ctx_key] = generate_event_contexts(
                        ctx_key[0], ctx_key[1], n=gov.max_worlds, seed=har_sha
                    )
                group_key = (str(row.get("eventId") or ""), str(row.get("teamId") or ""))
                family = str(row.get("sportFamily") or "")
                league = str(row.get("league") or "").upper()
                group = (cfb_groups if family == "gridiron" and league == "CFB" else teammate_groups).get(group_key) or {}
                use_joint_bball = family == "basketball" and len(group) >= 2
                use_joint_cfb = family == "gridiron" and league == "CFB" and bool(str(row.get("eventId") or ""))
                if use_joint_cfb:
                    group = group or {str(row.get("playerId") or ""): row}
                if use_joint_bball or use_joint_cfb:
                    jkey = (group_key[0], group_key[1], gov.max_worlds)
                    if jkey not in joint_world_cache:
                        specs = []
                        for _pid, prow in group.items():
                            psnap = _snapshot_for(prow)
                            specs.append({"row": prow, "snapshot": psnap})
                        if use_joint_cfb:
                            joint = simulate_joint_cfb_event_worlds(
                                specs,
                                n=gov.max_worlds,
                                seed=har_sha,
                                event_contexts=event_context_cache[ctx_key],
                            )
                        else:
                            joint = simulate_joint_team_worlds(
                                specs,
                                n=gov.max_worlds,
                                seed=har_sha,
                                event_contexts=event_context_cache[ctx_key],
                            )
                        joint_world_cache[jkey] = joint["worlds"]
                        joint_meta_acc.append(joint["meta"])
                    pid = str(row["playerId"])
                    world_cache[key] = joint_world_cache[jkey][pid]
                else:
                    world_cache[key] = simulate_player_worlds(
                        row,
                        n=gov.max_worlds,
                        seed=har_sha,
                        parameter_snapshot=snapshot,
                        event_contexts=event_context_cache[ctx_key],
                    )
            values = [value_from_stats(row["market"], w, board_id=board_id) for w in world_cache[key]]
        except QuarterPluginIncomplete as exc:
            rec["state"] = "UNSUPPORTED"; rec["blocker"] = getattr(exc, "blocker", None) or "QUARTER_PLUGIN_INCOMPLETE"
            unsupported += 1; classified.append(rec); continue
        except UnknownMarketError as exc:
            rec["state"] = "UNSUPPORTED"; rec["blocker"] = getattr(exc, "blocker", None) or "UNVERIFIED_MARKET_DEFINITION"
            unsupported += 1; classified.append(rec); continue
        except KeyError:
            rec["state"] = "UNSUPPORTED"; rec["blocker"] = "UNSUPPORTED_FAIL_CLOSED"
            unsupported += 1; classified.append(rec); continue
        except RuntimeError:
            conservation_failures += 1; rec["state"] = "UNRESOLVED"
            rec["blocker"] = "PRIMITIVE_CONSERVATION_FAILURE"
            unresolved += 1; classified.append(rec); continue

        dist = from_worlds(values, float(row["line"]))
        preliminary = max(
            dist["pHigher"] if row.get("offeredHigher") else 0.0,
            dist["pLower"] if row.get("offeredLower") else 0.0,
        )
        demon = row.get("modifier") == "DEMON"
        decision_threshold = 0.63 if demon else 0.58

        while True:
            target_worlds = gov.next_world_count(
                current=len(values),
                selected_probability=preliminary,
                decision_threshold=decision_threshold,
                production_selectable=production_selectable,
            )
            if target_worlds <= len(values):
                break
            adaptive_ctx_key = (
                str(row.get("sportFamily") or ""),
                str(row.get("eventId") or ""),
                target_worlds,
            )
            if adaptive_ctx_key not in event_context_cache:
                event_context_cache[adaptive_ctx_key] = generate_event_contexts(
                    adaptive_ctx_key[0],
                    adaptive_ctx_key[1],
                    n=target_worlds,
                    seed=har_sha,
                )
            group_key = (str(row.get("eventId") or ""), str(row.get("teamId") or ""))
            family = str(row.get("sportFamily") or "")
            league = str(row.get("league") or "").upper()
            group = (cfb_groups if family == "gridiron" and league == "CFB" else teammate_groups).get(group_key) or {}
            use_joint_bball = family == "basketball" and len(group) >= 2
            use_joint_cfb = family == "gridiron" and league == "CFB" and bool(str(row.get("eventId") or ""))
            if use_joint_cfb:
                group = group or {str(row.get("playerId") or ""): row}
            if use_joint_bball or use_joint_cfb:
                jkey = (group_key[0], group_key[1], target_worlds)
                if jkey not in joint_world_cache:
                    specs = []
                    for _pid, prow in group.items():
                        psnap = _snapshot_for(prow)
                        specs.append({"row": prow, "snapshot": psnap})
                    if use_joint_cfb:
                        joint = simulate_joint_cfb_event_worlds(
                            specs,
                            n=target_worlds,
                            seed=har_sha,
                            event_contexts=event_context_cache[adaptive_ctx_key],
                        )
                    else:
                        joint = simulate_joint_team_worlds(
                            specs,
                            n=target_worlds,
                            seed=har_sha,
                            event_contexts=event_context_cache[adaptive_ctx_key],
                        )
                    joint_world_cache[jkey] = joint["worlds"]
                    joint_meta_acc.append(joint["meta"])
                world_cache[key] = joint_world_cache[jkey][str(row["playerId"])]
            else:
                world_cache[key] = simulate_player_worlds(
                    row,
                    n=target_worlds,
                    seed=har_sha,
                    parameter_snapshot=snapshot,
                    event_contexts=event_context_cache[adaptive_ctx_key],
                )
            values = [value_from_stats(row["market"], w, board_id=board_id) for w in world_cache[key]]
            dist = from_worlds(values, float(row["line"]))
            preliminary = max(
                dist["pHigher"] if row.get("offeredHigher") else 0.0,
                dist["pLower"] if row.get("offeredLower") else 0.0,
            )

        sd = statistics.pstdev(values) if len(values) >= 2 else 0.0
        volatility = min(1.0, sd / (abs(float(dist["mean"])) + 1.0))
        support_n = min(
            int((snapshot.get("opportunity") or {}).get("support_n", 0)),
            int((snapshot.get("efficiency") or {}).get("support_n", 0)),
        )
        offered_sides = []
        if row.get("offeredHigher"): offered_sides.append("MORE")
        if row.get("offeredLower"): offered_sides.append("LESS")
        if not offered_sides:
            rec["state"] = "UNRESOLVED"; rec["blocker"] = "OFFERED_SIDE_UNKNOWN"
            unresolved += 1; classified.append(rec); continue

        evaluations: dict[str, dict[str, Any]] = {}
        for side in offered_sides:
            raw_p = dist["pHigher"] if side == "MORE" else dist["pLower"]
            ckey = cell_key(str(row.get("sportFamily")), str(row.get("league")), str(row.get("market")), side)
            cal = apply_calibration(raw_p, key=ckey, cells=calibration_cells)
            unc = probability_bundle(
                raw_selected_p=float(cal["calibrated"]), n_worlds=len(values),
                support_n=support_n, data_quality=float(snapshot.get("data_quality") or 0.0),
                ood_risk=float(snapshot.get("ood_risk") or 1.0), volatility=volatility,
                synthetic=bool(snapshot.get("synthetic")),
            )
            safe_p = float(unc["evidence_safe_probability"])
            surf = line_surface(values, float(row["line"]), side=side, playable_p=0.63 if demon else 0.58)
            fragility = min(
                1.0,
                0.10 + float(unc["epistemic_uncertainty"]) * 0.70
                + float(snapshot.get("ood_risk") or 0.0) * 0.20
                + min(0.20, float(surf["edge_elasticity"]) * 0.20),
            )
            side_grade = grade_of(
                selected_p=safe_p, lower_bound=float(unc["lower_bound"]), demon=demon,
                fragility=fragility, robustness_area=float(surf["robustness_area"]),
                elasticity=float(surf["edge_elasticity"]), false_sign=float(unc["false_sign_risk"]),
            )
            evaluations[side] = {
                "side": side, "rawP": raw_p, "calibratedP": float(cal["calibrated"]),
                "calibrationState": cal["state"], "evidenceSafeP": safe_p,
                "lowerBound": float(unc["lower_bound"]), "monteCarloSE": float(unc["monte_carlo_se"]),
                "epistemicUncertainty": float(unc["epistemic_uncertainty"]),
                "aleatoricUncertainty": float(unc["aleatoric_uncertainty"]),
                "reliability": float(unc["reliability"]), "falseSignRisk": float(unc["false_sign_risk"]),
                "volatility": volatility, "fragility": fragility, "lineSurface": surf, "grade": side_grade,
            }

        forced = row.get("side") if row.get("side") in evaluations else None
        chosen_side = forced or max(evaluations, key=lambda x: (evaluations[x]["evidenceSafeP"], evaluations[x]["lowerBound"]))
        ev = evaluations[chosen_side]
        selected_line = float(row["line"])
        if chosen_side == "MORE":
            selection_outcomes = bytes(
                2 if value > selected_line else 0 if value < selected_line else 1
                for value in values
            )
        else:
            selection_outcomes = bytes(
                2 if value < selected_line else 0 if value > selected_line else 1
                for value in values
            )
        if blocker in {"RESEARCH_ONLY_NOT_SELECTABLE", "SHADOW_SUPPORTED_NOT_SELECTABLE"}:
            production_selectable = False
        opp = snapshot.get("opportunity") or {}
        opportunity_mean = next((opp[k] for k in ("minutes_mean", "pass_att_mean", "routes_mean", "rush_att_mean", "pa_mean") if k in opp), None)
        rec.update({
            "state": "MODELED_DIAGNOSTIC" if diagnostic_model else "MODELED",
            "grade": ("LEAN" if diagnostic_model and ev["grade"] == "PLAYABLE" else ev["grade"]), "selectedSide": chosen_side,
            "selectedP": ev["rawP"], "rawP": ev["rawP"], "calibratedP": ev["calibratedP"],
            "evidenceSafeP": ev["evidenceSafeP"], "pHigher": dist["pHigher"], "pLower": dist["pLower"],
            "pPush": dist["pPush"], "mean": dist["mean"],
            "median": statistics.median(values) if values else dist["mean"],
            "lowerBound": ev["lowerBound"],
            "lineSurface": ev["lineSurface"], "sideEvaluations": evaluations,
            "opportunityMean": opportunity_mean, "reliability": ev["reliability"],
            "dataQuality": snapshot["data_quality"], "volatility": ev["volatility"],
            "fragility": ev["fragility"], "oodRisk": snapshot["ood_risk"],
            "falseSignRisk": ev["falseSignRisk"], "epistemicUncertainty": ev["epistemicUncertainty"],
            "aleatoricUncertainty": ev["aleatoricUncertainty"], "monteCarloSE": ev["monteCarloSE"],
            "calibrationState": ev["calibrationState"], "parameterSnapshotHash": snapshot["parameter_snapshot_hash"],
            "evidenceHashes": snapshot["evidence_hashes"], "dependencyTags": snapshot["dependency_tags"],
            "productionSelectable": production_selectable,
            "modeledPlayable": (not diagnostic_model) and is_modeled_playable(
                {
                    "row": row,
                    "grade": ev["grade"],
                    "state": "MODELED_DIAGNOSTIC" if diagnostic_model else "MODELED",
                    "blocker": rec.get("blocker") or blocker,
                    "parameterSnapshot": snapshot,
                    "forecastCutoff": forecast_cutoff,
                    "dependencyTags": snapshot.get("dependency_tags") or rec.get("dependencyTags") or [],
                    "playerStatus": snapshot.get("status"),
                },
                cutoff=forecast_cutoff,
                snapshot=snapshot,
            ),
            "researchOnly": blocker in {"RESEARCH_ONLY_NOT_SELECTABLE", "SHADOW_SUPPORTED_NOT_SELECTABLE"},
            "worldCount": len(values),
            "_selectionOutcomes": selection_outcomes,
            "_worldValues": list(values),
        })
        rec = apply_hold_playable(rec, hold_ids)
        gate = status_start_hard_blocker(
            rec, cutoff=forecast_cutoff, snapshot=snapshot,
        )
        if gate:
            rec["blocker"] = rec.get("blocker") or gate
            rec["modeledPlayable"] = False
        modeled.append(rec)
        classified.append(rec)

    (dest / "parameters").mkdir(exist_ok=True)
    (dest / "parameters" / "snapshots.json").write_text(
        json.dumps(parameter_cache, sort_keys=True) + "\n", encoding="utf-8"
    )

    n_worlds = dag.add("EVENT_WORLDS", "board", parents=[n_res.key])
    dag.complete(n_worlds.key, content_hash({"events": len({k[0] for k in world_cache}), "n": N_WORLDS}))
    model_perf = t.finish(
        OutputRows=len(modeled),
        NodeCount=len(world_cache),
        EventContextSets=len(event_context_cache),
        SimulatedPlayerWorlds=sum(len(v) for v in world_cache.values()),
        JointTeams=len(joint_meta_acc),
    )
    (dest / "performance" / "model.json").write_text(json.dumps(model_perf, indent=2) + "\n", encoding="utf-8")
    independent_events = len({k[0] for k in world_cache}) - len({m.get("eventId") for m in joint_meta_acc})
    event_worlds_meta = summarize_joint_meta(joint_meta_acc, independent_events=max(0, independent_events))
    (dest / "event_worlds_meta.json").write_text(
        json.dumps(event_worlds_meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not event_worlds_meta["conservationFlags"]["identitiesHeld"]:
        conservation_failures += 1
    stages_done.add("MODEL")

    if any(
        ((s.get("role_epoch") or {}).get("governedChangePoints") or {}).get("executed")
        for s in parameter_cache.values()
    ):
        telemetry.record("ALG-ML-TIME-001", problem_class="EWMA", producer="dcm.algorithms.ml_families.ewma", consumer="dcm.research.role_epoch.governed_change_points", artifact="parameters/snapshots.json", phase="EXECUTED", downstream_used=True)
        telemetry.record("ALG-ML-TIME-002", problem_class="CUSUM", producer="dcm.algorithms.ml_families.cusum", consumer="dcm.research.role_epoch.governed_change_points", artifact="parameters/snapshots.json", phase="EXECUTED", downstream_used=True)
        telemetry.record("ALG-ML-TIME-003", problem_class="PAGE_HINKLEY", producer="dcm.algorithms.ml_families.page_hinkley", consumer="dcm.research.role_epoch.governed_change_points", artifact="parameters/snapshots.json", phase="EXECUTED", downstream_used=True)

    ranked_t = StageTimer("RANK")
    ranked = rank_candidates(modeled, top_k=25, seed=har_sha)
    telemetry.record("ALG-SORT-001", problem_class="FINAL_RANK", producer="dcm.model.ranking.rank_candidates", consumer="dcm.runner.run_dcm", artifact="top100.json", phase="EXECUTED", downstream_used=True)
    telemetry.record("ALG-SORT-003", problem_class="TOPK_PARTIAL", producer="dcm.model.ranking.rank_candidates", consumer="dcm.runner.run_dcm", artifact="top25_qualified.json", phase="EXECUTED", downstream_used=True)
    started_events = {
        str(p.get("row", p).get("eventId") or "")
        for p in modeled
        if str((p.get("row") or p).get("gameStatus") or "").upper() in {"STARTED", "LIVE", "IN_PROGRESS"}
    }

    def _resimulate_material(rec: dict[str, Any]) -> list[float] | None:
        # Deprecated: material rebuild happens below via snapshots + joint worlds.
        return None

    snapshot_hash_before = content_hash(sorted(str(s.get("parameter_snapshot_hash") or "") for s in parameter_cache.values()))
    world_hash_before = content_hash(sorted(str(k) for k in world_cache))
    feature_hash_before = content_hash([str(f.get("contentHash") or "") for f in fact_features])
    material_fact_hash_before = str(material_facts_payload.get("contentHash") or "")

    refresh = apply_final_refresh(
        ranked,
        claims=bundle.get("claims") or [],
        facts=material_facts_payload,
        cutoff=forecast_cutoff,
        started_events=started_events,
        grade_fn=grade_of,
    )
    _write_refresh = dest / "cfb_final_refresh.json"
    ranked = refresh["modeled"]
    rebuild_players = set(refresh["report"].get("rebuildPlayerIds") or [])
    rebuild_events = set(refresh["report"].get("rebuildEventIds") or [])
    rebuild_teams = set(refresh["report"].get("rebuildTeamIds") or [])
    worlds_rebuilt = 0
    if rebuild_players or rebuild_events or rebuild_teams:
        material_facts_payload = resolve_material_facts(bundle.get("claims") or [], cutoff=forecast_cutoff)
        fact_features = facts_to_features(material_facts_payload, cutoff=forecast_cutoff)
        hold_ids = hold_playable_scope_ids(material_facts_payload)
        affected: list[dict[str, Any]] = []
        for rec in ranked:
            row = rec.get("row") if isinstance(rec.get("row"), dict) else {}
            pid = str(row.get("playerId") or "")
            eid = str(row.get("eventId") or "")
            tid = str(row.get("teamId") or row.get("team") or "")
            if pid in rebuild_players or eid in rebuild_events or tid in rebuild_teams:
                affected.append(rec)
        # Invalidate joint worlds for affected events/teams.
        for jkey in list(joint_world_cache):
            if jkey[0] in rebuild_events or jkey[1] in rebuild_teams:
                joint_world_cache.pop(jkey, None)
        for rec in affected:
            row = dict(rec.get("row") or {})
            oid = str(row.get("projectionId") or "")
            if oid:
                parameter_cache.pop(oid, None)
            snap = _snapshot_for(row)
            rec["parameterSnapshot"] = snap
            rec["parameterSnapshotHash"] = snap.get("parameter_snapshot_hash")
        for rec in affected:
            row = rec.get("row") if isinstance(rec.get("row"), dict) else {}
            family = str(row.get("sportFamily") or "")
            league = str(row.get("league") or "").upper()
            n = len(rec.get("_worldValues") or []) or int(gov.max_worlds)
            ctx_key = (family, str(row.get("eventId") or ""), n)
            if ctx_key not in event_context_cache:
                event_context_cache[ctx_key] = generate_event_contexts(
                    ctx_key[0], ctx_key[1], n=n, seed=har_sha
                )
            group_key = (str(row.get("eventId") or ""), str(row.get("teamId") or ""))
            group = (cfb_groups if family == "gridiron" and league == "CFB" else teammate_groups).get(group_key) or {}
            use_joint_cfb = family == "gridiron" and league == "CFB" and bool(str(row.get("eventId") or ""))
            if use_joint_cfb:
                group = group or {str(row.get("playerId") or ""): row}
                jkey = (group_key[0], group_key[1], n)
                if jkey not in joint_world_cache:
                    specs = []
                    for _pid, prow in group.items():
                        psnap = parameter_cache.get(str(prow.get("projectionId") or "")) or _snapshot_for(prow)
                        specs.append({"row": prow, "snapshot": psnap})
                    if rec not in specs and row:
                        specs.append({"row": row, "snapshot": rec.get("parameterSnapshot") or _snapshot_for(row)})
                    # Dedup by playerId
                    seen_p = set()
                    uniq = []
                    for spec in specs:
                        spid = str((spec.get("row") or {}).get("playerId") or "")
                        if not spid or spid in seen_p:
                            continue
                        seen_p.add(spid)
                        uniq.append(spec)
                    joint = simulate_joint_cfb_event_worlds(
                        uniq,
                        n=n,
                        seed=har_sha,
                        event_contexts=event_context_cache[ctx_key],
                    )
                    joint_world_cache[jkey] = joint["worlds"]
                    joint_meta_acc.append(joint["meta"])
                pid = str(row.get("playerId") or "")
                worlds = (joint_world_cache.get(jkey) or {}).get(pid) or []
            else:
                worlds = simulate_player_worlds(
                    row,
                    n=n,
                    seed=har_sha,
                    parameter_snapshot=rec.get("parameterSnapshot"),
                    event_contexts=event_context_cache[ctx_key],
                )
            rec["_worldValues"] = [
                value_from_stats(str(row.get("market") or ""), w, board_id=str(row.get("boardId") or "FULL_GAME"))
                for w in worlds
            ]
            rec = recompute_full_bundle(rec, grade_fn=grade_of, calibration_cells=calibration_cells)
            worlds_rebuilt += 1
            # write back into ranked
            oid = str(row.get("projectionId") or "")
            for i, existing in enumerate(ranked):
                if str((existing.get("row") or {}).get("projectionId") or "") == oid:
                    ranked[i] = rec
                    break
        ranked = rank_candidates(ranked, top_k=25, seed=har_sha)
        refresh["report"]["worldsRebuilt"] = worlds_rebuilt
        refresh["report"]["rerankedAfterRefresh"] = True
        refresh["report"]["contentHash"] = content_hash({k: v for k, v in refresh["report"].items() if k != "contentHash"})
    rank_perf = ranked_t.finish(OutputRows=len(ranked))
    (dest / "performance" / "rank.json").write_text(json.dumps(rank_perf, indent=2) + "\n", encoding="utf-8")
    _write_refresh.write_text(json.dumps(refresh["report"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    qualified = apply_pre_freeze_status_start_gates(ranked, cutoff=forecast_cutoff)
    card = build_card(qualified)
    exposure = exposure_report(card)
    remaining_actions = 0
    action_doc = None
    schedule_doc = None
    try:
        action_doc = json.loads((dest / "acquisition_actions.json").read_text())
        schedule_doc = json.loads((dest / "acquisition_schedule.json").read_text())
        selected = list((schedule_doc or {}).get("selectedActionIds") or [])
        complete_req = set()
        cov = bundle.get("coverage") or {}
        for row in cov.get("requests") or []:
            if isinstance(row, dict) and row.get("complete"):
                complete_req.add(str(row.get("requestId") or row.get("request_id") or ""))
        actions_by_id = {str(a.get("actionId")): a for a in (action_doc or {}).get("actions") or [] if isinstance(a, dict)}
        unresolved_selected = 0
        for aid in selected:
            act = actions_by_id.get(str(aid)) or {}
            reqs = [str(r) for r in (act.get("requirementIds") or [])]
            if not reqs or any(r not in complete_req for r in reqs):
                unresolved_selected += 1
        remaining_actions = unresolved_selected
    except Exception:
        remaining_actions = 0
    coverage_incomplete = not bool((bundle.get("coverage") or {}).get("complete"))
    host_required = str(research) == "file" and coverage_incomplete
    snapshot_hash_after = content_hash(sorted(str(s.get("parameter_snapshot_hash") or "") for s in parameter_cache.values()))
    world_hash_after = content_hash(sorted(str(k) for k in world_cache) + sorted(str(k) for k in joint_world_cache))
    feature_hash_after = content_hash([str(f.get("contentHash") or "") for f in fact_features])
    material_fact_hash_after = str(material_facts_payload.get("contentHash") or "")
    probability_hash_before = snapshot_hash_before
    probability_hash_after = content_hash([
        {"id": (p.get("row") or {}).get("projectionId"), "p": p.get("evidenceSafeP"), "side": p.get("selectedSide")}
        for p in ranked[:25]
    ])
    ranking_hash_after = content_hash([str((p.get("row") or {}).get("projectionId") or "") for p in ranked[:25]])
    cfb_forecast = emit_cfb_forecast_artifacts(
        dest,
        modeled=ranked,
        qualified=qualified,
        classified=classified,
        telemetry=telemetry,
        unresolved_actions=remaining_actions,
        evidence_imported=bool(bundle.get("claims")),
        material_facts=material_facts_payload,
        actions=action_doc,
        host_required=host_required,
        snapshot_hash_before=snapshot_hash_before,
        snapshot_hash_after=snapshot_hash_after,
        world_hash_before=world_hash_before,
        world_hash_after=world_hash_after,
        feature_hash_before=feature_hash_before,
        feature_hash_after=feature_hash_after,
        material_fact_hash_before=material_fact_hash_before,
        material_fact_hash_after=material_fact_hash_after,
        probability_hash_before=probability_hash_before,
        probability_hash_after=probability_hash_after,
        ranking_hash_before=None,
        ranking_hash_after=ranking_hash_after,
    )
    prepare_cfb_research_os(
        dest,
        rows,
        requests,
        claims=bundle.get("claims") or [],
        coverage=bundle.get("coverage"),
        telemetry=telemetry,
        frontier_offer_ids_set=set(cfb_forecast.get("frontierOfferIds") or []),
    )
    n_rank = dag.add("RANK", "board", parents=[n_worlds.key])
    dag.complete(n_rank.key, content_hash([p["row"]["projectionId"] for p in ranked[:25]]))
    n_port = dag.add("PORTFOLIO", "board", parents=[n_rank.key])
    dag.complete(n_port.key, content_hash({"ids": [p["row"]["projectionId"] for p in card], "exposure": exposure}))

    def slim(p: dict) -> dict:
        r = p["row"]
        surf = p.get("lineSurface") if isinstance(p.get("lineSurface"), dict) else {}
        out = {
            "rank": p.get("rank"), "sportFamily": r.get("sportFamily"), "league": r.get("league"),
            "player": r.get("playerName"), "team": r.get("team"), "opponent": r.get("opponent"),
            "event": r.get("eventLabel"), "market": r.get("market"), "line": r.get("line"),
            "direction": p.get("selectedSide"), "offeredHigher": r.get("offeredHigher"),
            "offeredLower": r.get("offeredLower"), "modifier": r.get("modifier"),
            "selectedP": p.get("selectedP"), "rawP": p.get("rawP"),
            "calibratedP": p.get("calibratedP"), "evidenceSafeP": p.get("evidenceSafeP"),
            "pHigher": p.get("pHigher"), "pLower": p.get("pLower"), "pPush": p.get("pPush"),
            "lowerBound": p.get("lowerBound"), "reliability": p.get("reliability"),
            "dataQuality": p.get("dataQuality"), "volatility": p.get("volatility"),
            "fragility": p.get("fragility"), "oodRisk": p.get("oodRisk"),
            "falseSignRisk": p.get("falseSignRisk"), "epistemicUncertainty": p.get("epistemicUncertainty"),
            "monteCarloSE": p.get("monteCarloSE"), "opportunityMean": p.get("opportunityMean"),
            "grade": p.get("grade"), "state": p.get("state"), "blocker": p.get("blocker"),
            "productionSelectable": p.get("productionSelectable", False),
            "modeledPlayable": p.get("modeledPlayable", False),
            "calibrationState": p.get("calibrationState"), "selectionScore": p.get("selectionScore"),
            "parameterSnapshotHash": p.get("parameterSnapshotHash"),
            "topKInclusionP": p.get("topKInclusionP"), "rankStability": p.get("rankStability"),
            "posteriorRegret": p.get("posteriorRegret"),
            "trueLineTolerance": surf.get("true_unclamped_line_tolerance"),
            "sideEvaluations": p.get("sideEvaluations"), "dependencyTags": p.get("dependencyTags"),
            "projectionId": r.get("projectionId"),
            "median": p.get("median"),
        }
        # Line surface on PLAYABLE/LEAN slim rows (true unclamped; never a display clamp).
        if p.get("grade") in {"PLAYABLE", "LEAN"}:
            out["lineSurface"] = surf
            out["offered_line"] = surf.get("offered_line")
            out["break_even_line"] = surf.get("break_even_line")
            out["playable_break_line"] = surf.get("playable_break_line")
            out["true_unclamped_line_tolerance"] = surf.get("true_unclamped_line_tolerance")
            out["edge_elasticity"] = surf.get("edge_elasticity")
            out["robustness_area"] = surf.get("robustness_area")
        return out

    top25_ranked = [slim(p) for p in ranked[:25]]
    top25_qualified = [slim(p) for p in qualified[:25]]
    top100 = [slim(p) for p in ranked[:100]]
    strict_card = [slim(p) for p in card]
    full_population = [slim(p) for p in classified]
    (dest / "top100.json").write_text(json.dumps(top100, indent=2) + "\n", encoding="utf-8")
    (dest / "top25_qualified.json").write_text(json.dumps(top25_qualified, indent=2) + "\n", encoding="utf-8")
    (dest / "full_population.jsonl").write_text("".join(json.dumps(p) + "\n" for p in full_population), encoding="utf-8")
    (dest / "dependencies.json").write_text(
        json.dumps(exposure, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    evidence_graph: dict[str, Any] = {}
    graph_path = dest / "evidence_graph.json"
    if graph_path.is_file():
        try:
            evidence_graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            evidence_graph = {}
    feature_store_hash = None
    feature_manifest_path = dest / "feature_store_manifest.json"
    if feature_manifest_path.is_file():
        try:
            feature_store_hash = json.loads(feature_manifest_path.read_text(encoding="utf-8")).get("contentHash")
        except (OSError, json.JSONDecodeError):
            feature_store_hash = None
    feature_hash_index = load_feature_hash_index(dest)
    features_for_graph: list[dict[str, Any]] = []
    feat_jsonl = dest / "feature_store.jsonl"
    if feat_jsonl.is_file():
        for line in feat_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                features_for_graph.append(rec)
    evidence_graph = attach_runtime_lineage(
        evidence_graph,
        features=features_for_graph,
        snapshots=list(parameter_cache.values()),
        evaluations=classified,
        selections=strict_card,
        run_id=str(run_id),
        forecast_cutoff=str(forecast_cutoff),
    )
    graph_path.write_text(json.dumps(evidence_graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    explain_src: list[dict[str, Any]] = []
    seen_explain: set[str] = set()
    for p in list(ranked[:25]) + list(card):
        pid = str((p.get("row") or {}).get("projectionId") or "")
        if not pid or pid in seen_explain:
            continue
        seen_explain.add(pid)
        explain_src.append(p)
    explanations: list[dict[str, Any]] = []
    for p in explain_src:
        row = p.get("row") or {}
        snap = p.get("parameterSnapshot") if isinstance(p.get("parameterSnapshot"), dict) else {}
        side_key = str(p.get("selectedSide") or "")
        side_eval = (p.get("sideEvaluations") or {}).get(side_key) if isinstance(p.get("sideEvaluations"), dict) else {}
        if not isinstance(side_eval, dict):
            side_eval = {}
        feat_key = (str(row.get("playerId") or ""), str(row.get("eventId") or ""))
        explanations.append(
            build_prop_explanation(
                row,
                snap,
                {
                    "mean": p.get("mean"),
                    "median": p.get("median"),
                    "pMore": p.get("pHigher"),
                    "pLess": p.get("pLower"),
                    "pPush": p.get("pPush"),
                    "n": p.get("worldCount"),
                },
                side_eval,
                feature_hash_index.get(feat_key) or [],
                p.get("evidenceHashes") or snap.get("evidence_hashes") or [],
            )
        )
    explanations_hash = persist_prop_explanations(dest, explanations)
    git_commit = _git_commit_sha(workspace)
    parameter_snapshot_hashes = sorted({
        str(p.get("parameterSnapshotHash") or "")
        for p in modeled
        if p.get("parameterSnapshotHash")
    })

    states_count = {}
    for p in classified:
        states_count[p["state"]] = states_count.get(p["state"], 0) + 1

    evidence_coverage_complete = bool((bundle.get("coverage") or {}).get("complete"))
    empty_card_reason = modeled_empty_card_reason(
        modeled_card_size=len(card),
        modeled_playable_count=len(qualified),
        evidence_coverage_complete=evidence_coverage_complete,
        research_complete=bool(bundle.get("complete")),
    )

    freeze_t = StageTimer("FREEZE")
    freeze = {
        "runId": run_id,
        "dcmVersion": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "optimizedDcm60Claim": False,
        "hostPerformanceCertified": False,
        "chatgptOperable": True,
        "productionOperable": global_selection_gate,
        "selectionAllowed": global_selection_gate,
        "softwareE2eComplete": True,
        "forecastFrozen": False,
        "freezeState": "PREPARED",
        "v5Decoder": mount.get("har_decoder"),
        "v5MountState": mount.get("state"),
        "schemaId": SCHEMA,
        "schemaState": schema_root.get("state"),
        "schemaHash": schema_root.get("observedSha256"),
        "schemaReady": schema_ready,
        "modelConfigHash": config_hash,
        "calibrationStateHash": calibration_state.get("contentHash"),
        "harSha256": har_sha,
        "forecastCutoff": forecast_cutoff,
        "boardHash": board["contentHash"],
        "rawRows": len(rows),
        "goblins": excluded,
        "unsupported": unsupported,
        "unresolved": unresolved,
        "modeled": len(modeled),
        "playable": len(qualified),
        "cardSize": len(card),
        "modeledCardSize": len(card),
        "eventWorlds": len(world_cache),
        "eventWorldAllocation": event_worlds_meta.get("allocationMode"),
        "jointMinuteConservation": event_worlds_meta.get("conservationFlags"),
        "conservationFailures": conservation_failures,
        "researchRequested": bundle["requested"],
        "researchReused": bundle["reused"],
        "researchComplete": bundle["complete"],
        "productionResearchComplete": production_research_ready,
        "evidenceCoverageComplete": bool((bundle.get("coverage") or {}).get("complete")),
        "evidenceCoverageMissing": int((bundle.get("coverage") or {}).get("missingRequirementCount") or 0),
        "evidenceConflictCount": len(bundle.get("conflicts") or []),
        "evidenceMode": bundle.get("evidence_mode"),
        "canonicalBaselineReady": canonical_ready,
        "schemaReady": schema_ready,
        "evidenceBlocked": evidence_blocked,
        "portfolioExposure": exposure,
        "top25QualifiedCount": len(top25_qualified),
        "cfbTop100Count": int((cfb_forecast.get("top100") or {}).get("count") or 0),
        "cfbTop25Count": int((cfb_forecast.get("top25") or {}).get("count") or 0),
        "cfbPlayablesCount": int((cfb_forecast.get("playables") or {}).get("count") or 0),
        "software": SOFTWARE,
        "gitCommit": git_commit,
        "featureStoreHash": feature_store_hash,
        "evidenceGraphHash": evidence_graph.get("contentHash"),
        "parameterSnapshotHashes": parameter_snapshot_hashes,
        "forecastDecisionCutoff": forecast_cutoff,
        "top25Hash": content_hash(top25_ranked),
        "cardHash": content_hash(strict_card),
        "explanationsHash": explanations_hash,
        "explanationCount": len(explanations),
        "probabilityContract": {
            "reliabilityIsNotProbability": RELIABILITY_IS_NOT_PROBABILITY,
            "separateKeys": list(PROBABILITY_CONTRACT_KEYS),
            "note": "Reliability is not a probability. selectedP, evidenceSafeP, and lowerBound are probabilities; reliability, dataQuality, volatility, fragility, oodRisk, falseSignRisk, monteCarloSE, and epistemicUncertainty are separate uncertainty quantities and must not be treated as P.",
        },
        "dag": dag.snapshot(),
    }
    freeze["freezeBinds"] = {
        "software": SOFTWARE,
        "gitCommit": git_commit,
        "schemaHash": freeze["schemaHash"],
        "featureStoreHash": feature_store_hash,
        "harSha256": har_sha,
        "boardHash": board["contentHash"],
        "evidenceGraphHash": evidence_graph.get("contentHash"),
        "parameterSnapshotHashes": parameter_snapshot_hashes,
        "modelConfigHash": config_hash,
        "calibrationStateHash": calibration_state.get("contentHash"),
        "forecastDecisionCutoff": forecast_cutoff,
        "top25Hash": freeze["top25Hash"],
        "cardHash": freeze["cardHash"],
        "explanationsHash": explanations_hash,
        "frontierStopReason": freeze.get("frontierStopReason"),
        "frontierPassCount": freeze.get("frontierPassCount"),
        "finalRefreshHash": freeze.get("finalRefreshHash"),
        "finalRankingHash": freeze.get("finalRankingHash"),
        "forecastFrozen": freeze.get("forecastFrozen"),
        "freezeState": freeze.get("freezeState"),
        "frontierCheckpointHash": freeze.get("frontierCheckpointHash"),
    }
    readiness = build_readiness(
        mount=mount,
        schema=schema_root,
        research=bundle,
        board=board,
        conservation_failures=conservation_failures,
        software_e2e_complete=True,
        host_performance_certified=False,
        learning_revision=LEARNING_REVISION,
        predictive_claim=PREDICTIVE_CLAIM,
    )
    (dest / "production_readiness.json").write_text(
        json.dumps(readiness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    freeze["productionSelectionReady"] = readiness["productionSelectionReady"]
    freeze["systemCertified"] = readiness["systemCertified"]
    freeze["predictiveValidationEarned"] = readiness["predictiveValidationEarned"]
    root_accepted = production_root_accepted(
        global_selection_gate=global_selection_gate,
        production_selection_ready=bool(readiness["productionSelectionReady"]),
    )
    production_certified = production_certified_rows(strict_card, root_accepted=root_accepted)
    directional_passes = build_directional_passes(ranked, strict_card)
    write_card_layer_files(
        dest,
        top25_ranked=top25_ranked,
        strict_card=strict_card,
        production_certified=production_certified,
        directional_passes=directional_passes,
    )
    freeze["productionCertified"] = bool(root_accepted and production_certified)
    freeze["notProductionRootCertified"] = not root_accepted
    freeze["productionRootCertification"] = (
        "PRODUCTION_ROOT_CERTIFIED" if root_accepted else NOT_PRODUCTION_ROOT_CERTIFIED
    )
    freeze["productionCertifiedCardSize"] = len(production_certified)
    freeze["executionMode"] = "PRODUCTION" if root_accepted else "RESEARCHED_MODELED"
    run_state = layer_run_state(
        root_accepted=root_accepted,
        modeled_card_size=len(card),
        ranked_size=len(top25_ranked),
        unsupported=unsupported,
    )
    freeze["runState"] = run_state
    top25_doc = cfb_forecast.get("top25") or {}
    loop_doc = cfb_forecast.get("frontierLoop") or {}
    frontier_final = bool(top25_doc.get("final"))
    stop_reason = str(loop_doc.get("stopReason") or "")
    research_terminal = research == "fixture" or (
        bool(bundle.get("complete")) and bool((bundle.get("coverage") or {}).get("complete"))
    )
    can_freeze = frontier_final and research_terminal and stop_reason != "EXTERNAL_HOST_REQUIRED"
    freeze["top25Final"] = frontier_final
    freeze["frontierStopReason"] = stop_reason
    freeze["frontierPassCount"] = int(loop_doc.get("frontierPassCount") or 0)
    freeze["finalRefreshHash"] = (refresh.get("report") or {}).get("contentHash")
    freeze["finalRankingHash"] = content_hash([str((p.get("row") or {}).get("projectionId") or "") for p in ranked[:25]])
    freeze["frontierPassStateHash"] = ((cfb_forecast.get("passState") or {}).get("contentHash"))
    if not can_freeze:
        freeze["forecastFrozen"] = False
        freeze["freezeState"] = "FRONTIER_INTERIM"
        freeze["runState"] = "AWAITING_FRONTIER_RESEARCH"
        freeze["note"] = "Interim frontier; not a frozen forecast. Host must acquire remaining frontier actions."
        for stale_path in (dest / "frozen_forecast.json", dest / "frozen_forecast.sha256"):
            stale_path.unlink(missing_ok=True)
    else:
        freeze["forecastFrozen"] = True
        freeze["freezeState"] = "FROZEN"
        (dest / "frontier_checkpoint.json").unlink(missing_ok=True)
    freeze["freezeBinds"] = {
        **(freeze.get("freezeBinds") or {}),
        "frontierStopReason": freeze.get("frontierStopReason"),
        "frontierPassCount": freeze.get("frontierPassCount"),
        "finalRefreshHash": freeze.get("finalRefreshHash"),
        "finalRankingHash": freeze.get("finalRankingHash"),
        "forecastFrozen": freeze.get("forecastFrozen"),
        "top25Final": freeze.get("top25Final"),
        "freezeState": freeze.get("freezeState"),
        "frontierCheckpointHash": freeze.get("frontierCheckpointHash"),
    }
    if empty_card_reason:
        freeze["emptyCardReason"] = empty_card_reason
    if not root_accepted:
        freeze["productionEmptyCardReason"] = EMPTY_ROOT_NOT_CERTIFIED
    freeze["freezeBinds"]["frontierCheckpointHash"] = None
    frontier_checkpoint_hash = None
    if can_freeze:
        freeze["frozenForecastHash"] = compute_forecast_hash(freeze, full_population, strict_card, top25_ranked)
        n_fz = dag.add("FREEZE", "board", parents=[n_port.key])
        dag.complete(n_fz.key, freeze["frozenForecastHash"])
    else:
        frontier_checkpoint = {
            "schema": "pillars_dcm.frontier_checkpoint.v1",
            "runId": run_id,
            "freezeState": freeze.get("freezeState"),
            "top25Final": False,
            "forecastFrozen": False,
            "frontierPassStateHash": freeze.get("frontierPassStateHash"),
            "top25Hash": freeze.get("top25Hash"),
            "nextDeterministicAction": "acquire_frontier_research_and_resume",
        }
        frontier_checkpoint["contentHash"] = content_hash(frontier_checkpoint)
        frontier_checkpoint_hash = frontier_checkpoint["contentHash"]
        freeze["frontierCheckpointHash"] = frontier_checkpoint_hash
        freeze["freezeBinds"]["frontierCheckpointHash"] = frontier_checkpoint_hash
        freeze.pop("frozenForecastHash", None)
        (dest / "frontier_checkpoint.json").write_text(json.dumps(frontier_checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        n_fz = dag.add("FRONTIER_CHECKPOINT", "board", parents=[n_port.key])
        dag.complete(n_fz.key, frontier_checkpoint_hash)
    freeze["dag"] = dag.snapshot()
    if can_freeze:
        (dest / "frozen_forecast.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "freeze.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    freeze_perf = freeze_t.finish(OutputRows=len(card), Frozen=bool(freeze.get("forecastFrozen")))
    (dest / "performance" / "freeze.json").write_text(json.dumps(freeze_perf, indent=2) + "\n", encoding="utf-8")
    stage_rows = []
    for rec in ((har_perf if "har_perf" in locals() else None), research_perf, model_perf, rank_perf, freeze_perf):
        if isinstance(rec, dict):
            stage_rows.append(rec)
    stages_payload = {
        "schema": "pillars_dcm.stage_telemetry.v1",
        "stages": stage_rows,
        "hostPerformanceCertified": False,
    }
    (dest / "performance" / "stages.json").write_text(json.dumps(stages_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if can_freeze:
        (dest / "frozen_forecast.sha256").write_text(freeze["frozenForecastHash"] + "\n", encoding="utf-8")
    (dest / "population_full.jsonl").write_text("".join(json.dumps(p) + "\n" for p in full_population), encoding="utf-8")
    (dest / "accounting.json").write_text(json.dumps({**(board.get("accounting") or {}), "states": states_count, "playable": len(qualified), "cardSize": len(card)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes_payload = {
        "boardHash": board.get("contentHash"),
        "harSha256": har_sha,
        "evidenceGraphHash": evidence_graph.get("contentHash"),
        "featureStoreHash": feature_store_hash,
        "explanationsHash": explanations_hash,
        "gitCommit": git_commit,
        "checkpointPending": not can_freeze,
        "schemaV1Expected": "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22",
        "schemaV2": (schema_root.get("v2") or {}),
        **constitution_run_hashes(plan_payload),
    }
    if can_freeze:
        hashes_payload["frozenForecastHash"] = freeze["frozenForecastHash"]
    else:
        hashes_payload["frontierCheckpointHash"] = frontier_checkpoint_hash
    (dest / "hashes.json").write_text(json.dumps(hashes_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    persist_algorithm_telemetry(dest, telemetry)
    from dcm.algorithms.indexing import merkle_root
    from dcm.runtime.archive_receipt import archive_reconcile, archive_retry, build_archive_receipt, persist_archive_receipt
    hashes_payload = json.loads((dest / "hashes.json").read_text(encoding="utf-8"))
    merkle_subject = str(hashes_payload.get("frozenForecastHash") or hashes_payload.get("frontierCheckpointHash") or "")
    freeze_merkle = merkle_root([
        str(hashes_payload.get("harSha256") or ""),
        merkle_subject,
        str(hashes_payload.get("evidenceGraphHash") or ""),
        str(hashes_payload.get("featureStoreHash") or ""),
        str(hashes_payload.get("runMerkleRoot") or ""),
    ])
    hashes_payload["freezeMerkleRoot" if can_freeze else "frontierCheckpointMerkleRoot"] = freeze_merkle
    (dest / "hashes.json").write_text(json.dumps(hashes_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    persist_archive_receipt(dest, build_archive_receipt(
        dest,
        merkel_root=freeze_merkle,
        hashes=hashes_payload,
        local_status="WRITTEN",
        drive_status="NOT_CONFIGURED",
        github_status="NOT_PUSHED",
    ))
    archive_retry(dest)
    archive_reconcile(dest)

    blockers = []
    if excluded:
        blockers.append({"code": "GOBLIN_SELECTION_FORBIDDEN", "count": excluded})
    if unsupported:
        blockers.append({"code": "UNSUPPORTED_FAIL_CLOSED", "count": unsupported})
    if unresolved:
        blockers.append({"code": "UNRESOLVED", "count": unresolved})
    if conservation_failures:
        blockers.append({"code": "PRIMITIVE_CONSERVATION_FAILURE", "count": conservation_failures})
    flags = freeze.get("jointMinuteConservation") or {}
    if flags.get("identitiesHeld") is False:
        blockers.append({"code": "PRIMITIVE_CONSERVATION_FAILURE", "count": 1, "source": "event_worlds_meta"})
    if not can_freeze:
        blockers.append({"code": "FRONTIER_RESEARCH_REQUIRED", "count": 1})
    (dest / "blockers.json").write_text(json.dumps(blockers, indent=2) + "\n", encoding="utf-8")

    if can_freeze:
        store = IndexedStore(dest / "index.sqlite")
        append_record(
            store,
            "FrozenForecast",
            forecast_cutoff,
            run_id,
            LEARNING_REVISION,
            {"hash": freeze["frozenForecastHash"]},
            source_hash=har_sha,
        )
        store.close()
        append_ledger_jsonl(
            dest,
            "FrozenForecast",
            {"hash": freeze["frozenForecastHash"]},
            cutoff=forecast_cutoff,
            run_id=run_id,
            lr=LEARNING_REVISION,
            source_hash=har_sha,
        )

    integrity = {
        **freeze,
        "states": states_count,
        "accounting": board["accounting"],
        "createdAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (dest / "run_integrity.json").write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint_payload = {
        "runId": run_id,
        "dcmVersion": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "forecastCutoff": forecast_cutoff,
        "modelConfigHash": config_hash,
        "calibrationStateHash": calibration_state.get("contentHash"),
        "mountStateHash": content_hash(mount),
        "schemaStateHash": content_hash(schema_root),
        "artifactRoot": str(dest),
        "completedStages": ["BOARD_FREEZE", "RESEARCH", "MODEL", "RANK", "PORTFOLIO", "FREEZE"] if can_freeze else ["BOARD_FREEZE", "RESEARCH", "MODEL", "RANK", "PORTFOLIO", "FRONTIER_CHECKPOINT"],
        "forecastFrozen": bool(can_freeze),
        "pending": [] if can_freeze else ["FRONTIER_RESEARCH"],
        "nextDeterministicAction": "none" if can_freeze else "acquire_frontier_research_and_resume",
        "rowCounts": states_count,
        "blockers": [b["code"] for b in blockers],
    }
    if can_freeze:
        checkpoint_payload["frozenForecastHash"] = freeze["frozenForecastHash"]
    else:
        checkpoint_payload["frontierCheckpointHash"] = frontier_checkpoint_hash
    write_checkpoint(dest / "checkpoint.json", checkpoint_payload)
    return _finalize_archive(
        dest,
        {
            "run_id": run_id,
            "dest": str(dest),
            "runState": freeze.get("runState"),
            "integrity": integrity,
            "card": strict_card,
            "top25_qualified": top25_qualified,
            "board": board,
            "classified": classified,
            "world_cache": world_cache,
            "dag": dag.snapshot(),
        },
        archive_github=archive_github,
        archive_push=archive_push,
        repo_root=repo_root,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="DCM v6 E2E runner (LR000000, not optimized 6.0)", epilog=POLICY_DOC, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", type=Path, action="append", default=None, help="HAR input; repeat for complementary captures")
    p.add_argument("--out", type=Path, default=DEFAULT_WORKSPACE / "dcm_v6" / "RUNS")
    p.add_argument("--output", type=Path, default=None, help="Alias for --out")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument(
        "--cutoff",
        default=None,
        help="RFC3339 forecast cutoff. Required unless --cutoff-from-capture or --resume.",
    )
    p.add_argument(
        "--cutoff-from-capture",
        action="store_true",
        help="Derive cutoff from HAR startedDateTime / max board_time (CAPTURE_MAX_STARTED_DATETIME).",
    )
    p.add_argument("--research", choices=["fixture", "file", "bundle"], default="file")
    p.add_argument(
        "--research-shadow",
        action="store_true",
        help="Include MLB/shadow rows in deep research (default OFF).",
    )
    p.add_argument("--evidence-dir", type=Path, default=None)
    p.add_argument("--bundle", type=Path, default=None, help="evidence_bundle.jsonl for --research bundle")
    p.add_argument("--account-only", action="store_true", help="Freeze+account every row; skip Monte Carlo")
    p.add_argument("--resume", type=Path, default=None)
    p.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    p.add_argument(
        "--archive-github",
        action="store_true",
        help="Copy a safe audit pack into audit/runs/<runId>/ and append INDEX.jsonl. Commits if git identity/repo are available; a git commit failure does not fail the DCM run. Pushes unless --no-archive-push.",
    )
    p.add_argument(
        "--no-archive-push",
        action="store_true",
        help="With --archive-github, write+commit the pack but do not git push.",
    )
    p.add_argument(
        "--version",
        default=None,
        help="Exact software pin against VERSION.json (software or softwareShort). Omitted defaults to current SOFTWARE.",
    )
    args = p.parse_args(argv)
    try:
        resolved = resolve_requested_version(args.version)
    except ExactVersionMismatch as e:
        print(str(e), file=sys.stderr)
        return 2
    if resolved.get("defaulted"):
        print(f"DCM_VERSION_DEFAULTED software={SOFTWARE}", file=sys.stderr)
    if not args.resume and not args.cutoff and not args.cutoff_from_capture:
        print(
            "FORECAST_CUTOFF_REQUIRED: pass --cutoff <RFC3339> or --cutoff-from-capture. "
            "There is no hardcoded default cutoff.",
            file=sys.stderr,
        )
        return 2
    try:
        result = run_dcm(
            input_path=(args.input[0] if args.input and len(args.input) == 1 else None),
            input_paths=args.input,
            forecast_cutoff=args.cutoff,
            output_root=args.output or args.out,
            synthetic=args.synthetic,
            research=args.research,
            evidence_dir=args.evidence_dir,
            workspace=args.workspace,
            resume=args.resume,
            account_only=args.account_only,
            bundle_path=args.bundle,
            research_shadow=args.research_shadow,
            cutoff_from_capture=args.cutoff_from_capture,
            archive_github=bool(args.archive_github),
            archive_push=bool(args.archive_github) and not bool(args.no_archive_push),
            repo_root=args.workspace,
        )
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    except (CutoffRequired, ExactVersionMismatch) as e:
        print(str(e), file=sys.stderr)
        return 2
    integ = result.get("integrity") or {}
    print(
        json.dumps(
            {
                "runId": result["run_id"],
                "runState": result["runState"],
                "software": SOFTWARE,
                "learningRevision": LEARNING_REVISION,
                "predictiveClaim": PREDICTIVE_CLAIM,
                "optimizedDcm60Claim": False,
                "rawRows": integ.get("rawRows"),
                "modeled": integ.get("modeled"),
                "playable": integ.get("playable"),
                "cardSize": integ.get("cardSize"),
                "modeledCardSize": integ.get("modeledCardSize"),
                "productionCertified": integ.get("productionCertified"),
                "chatgptOperable": integ.get("chatgptOperable"),
                "dest": result["dest"],
                "archivePath": result.get("archivePath"),
                "archiveIntegrityCertified": result.get("archiveIntegrityCertified"),
                "evidenceCoverageCertified": result.get("evidenceCoverageCertified"),
                "evidenceTemporalCertified": result.get("evidenceTemporalCertified"),
                "modelRunCertified": result.get("modelRunCertified"),
                "selectionCertified": result.get("selectionCertified"),
                "productionRootCertified": result.get("productionRootCertified"),
                "predictiveValidationEarned": result.get("predictiveValidationEarned"),
                "hashCertifiedPythonFreeze": result.get("hashCertifiedPythonFreeze"),
                "hallucinationRisk": result.get("hallucinationRisk"),
                "githubCommit": result.get("githubCommit"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
