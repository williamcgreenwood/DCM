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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.identity.resolve import freeze_map, resolve_row
from dcm.ingest.board import freeze_board, write_board
from dcm.ingest.composite import compose_ingests
from dcm.ingest.har import ingest_har
from dcm.model.distributions import from_worlds
from dcm.model.grade import grade as grade_of
from dcm.model.line_surface import surface as line_surface
from dcm.model.parameters import build_parameter_snapshot
from dcm.model.ranking import rank_candidates
from dcm.model.uncertainty import probability_bundle
from dcm.learning.calibration import apply_calibration, cell_key
from dcm.model.worlds import generate_event_contexts, simulate_player_worlds, value_from_stats
from dcm.research.classify import accounting_classify as _classify
from dcm.research.host_plan import build_host_research_plan
from dcm.research.provider import BundleProvider, FileProvider, FixtureProvider, collect, write_bundle
from dcm.research.requests import plan_research
from dcm.runtime.checkpoint import load_checkpoint, write_checkpoint
from dcm.runtime.cutoff import CutoffRequired, POLICY_DOC, resolve_forecast_cutoff
from dcm.runtime.dag import Dag
from dcm.runtime.freeze import compute_forecast_hash
from dcm.runtime.governor import Governor
from dcm.runtime.mount_v541 import mount_default
from dcm.runtime.schema_root import SCHEMA_V2_ID, verify_schema, verify_schema_v2
from dcm.runtime.perf import StageTimer
from dcm.runtime.readiness import build_readiness
from dcm.runtime.store import IndexedStore
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

    rows = [resolve_row(r) for r in board["rows"]]
    id_map = freeze_map(rows)
    (dest / "identities").mkdir(exist_ok=True)
    (dest / "identities" / "map.json").write_text(json.dumps(id_map, indent=2) + "\n", encoding="utf-8")
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
        hashes = {"boardHash": board.get("contentHash"), "harSha256": har_sha, "schemaV1Expected": "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22"}
        (dest / "hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run_state = "COMPLETE_WITH_UNSUPPORTED_ROWS" if counts.get("UNSUPPORTED") else "EMPTY_CARD_COMPLETE"
        freeze = {
            "runId": run_id, "runState": run_state, "learningRevision": LEARNING_REVISION,
            "predictiveClaim": PREDICTIVE_CLAIM, "rawRows": len(rows), "accountOnly": True,
            "classified": counts, "boardHash": board.get("contentHash"),
        }
        (dest / "freeze.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        planned = plan_research(rows, forecast_cutoff, research_shadow=research_shadow)
        (dest / "research_requests.json").write_text(
            json.dumps(planned["requests"], indent=2) + "\n", encoding="utf-8"
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
        return {"run_id": run_id, "dest": str(dest), "runState": run_state, "checkpoint": ck, "integrity": freeze, "board": board}


    t = StageTimer("RESEARCH")
    planned = plan_research(rows, forecast_cutoff, research_shadow=research_shadow)
    requests = planned["requests"]
    (dest / "research_requests.json").write_text(json.dumps(requests, indent=2) + "\n", encoding="utf-8")
    if research == "file":
        provider: Any = FileProvider(evidence_dir or dest / "evidence")
    elif research == "bundle":
        provider = BundleProvider(bundle_path or dest / "evidence_bundle.jsonl")
    else:
        provider = FixtureProvider(forecast_cutoff)
    bundle = collect(requests, provider)
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
    n_res = dag.add("EVIDENCE", "board", parents=[n_id.key])
    if not bundle["complete"]:
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
        return {
            "run_id": run_id,
            "dest": str(dest),
            "runState": "INCOMPLETE_CHECKPOINTED",
            "checkpoint": ck,
            "research": bundle,
        }
    dag.complete(n_res.key, content_hash([c["claim_hash"] for c in bundle["claims"]]))
    research_perf = t.finish(NodeCount=len(requests), CacheHits=bundle["reused"])
    (dest / "performance" / "research.json").write_text(json.dumps(research_perf, indent=2) + "\n", encoding="utf-8")
    stages_done.add("RESEARCH")

    canonical_ready = mount.get("state") == "HASH_VERIFIED_EXTRACTED"
    schema_ready = bool(schema_root.get("productionEligible")) and schema_root.get("state") == "HASH_VERIFIED"
    production_research_ready = bool(bundle.get("production_ready"))
    global_selection_gate = canonical_ready and schema_ready and production_research_ready and not synthetic

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

    for row in rows:
        state, blocker = _classify(row)
        rec: dict[str, Any] = {"row": row, "state": state, "blocker": blocker}
        if state == "EXCLUDED_GOBLIN":
            excluded += 1; classified.append(rec); continue
        if state == "UNSUPPORTED":
            unsupported += 1; classified.append(rec); continue
        if state == "UNRESOLVED":
            unresolved += 1; classified.append(rec); continue

        snapshot = build_parameter_snapshot(row, bundle["claims"])
        parameter_cache[str(row["projectionId"])] = snapshot
        production_selectable = global_selection_gate and bool(snapshot["production_eligible"]) and blocker is None
        if not snapshot["production_eligible"] and not synthetic and blocker is None:
            rec["blocker"] = snapshot.get("blocker") or "EVIDENCE_INSUFFICIENT"
            evidence_blocked += 1

        key = (str(row["eventId"]), str(row["playerId"]), str(snapshot["parameter_snapshot_hash"]))
        try:
            if key not in world_cache:
                ctx_key = (str(row.get("sportFamily") or ""), str(row.get("eventId") or ""), gov.max_worlds)
                if ctx_key not in event_context_cache:
                    event_context_cache[ctx_key] = generate_event_contexts(
                        ctx_key[0], ctx_key[1], n=gov.max_worlds, seed=har_sha
                    )
                world_cache[key] = simulate_player_worlds(
                    row,
                    n=gov.max_worlds,
                    seed=har_sha,
                    parameter_snapshot=snapshot,
                    event_contexts=event_context_cache[ctx_key],
                )
            values = [value_from_stats(row["market"], w) for w in world_cache[key]]
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
            world_cache[key] = simulate_player_worlds(
                row,
                n=target_worlds,
                seed=har_sha,
                parameter_snapshot=snapshot,
                event_contexts=event_context_cache[adaptive_ctx_key],
            )
            values = [value_from_stats(row["market"], w) for w in world_cache[key]]
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
            "state": "MODELED", "grade": ev["grade"], "selectedSide": chosen_side,
            "selectedP": ev["rawP"], "rawP": ev["rawP"], "calibratedP": ev["calibratedP"],
            "evidenceSafeP": ev["evidenceSafeP"], "pHigher": dist["pHigher"], "pLower": dist["pLower"],
            "pPush": dist["pPush"], "mean": dist["mean"], "lowerBound": ev["lowerBound"],
            "lineSurface": ev["lineSurface"], "sideEvaluations": evaluations,
            "opportunityMean": opportunity_mean, "reliability": ev["reliability"],
            "dataQuality": snapshot["data_quality"], "volatility": ev["volatility"],
            "fragility": ev["fragility"], "oodRisk": snapshot["ood_risk"],
            "falseSignRisk": ev["falseSignRisk"], "epistemicUncertainty": ev["epistemicUncertainty"],
            "aleatoricUncertainty": ev["aleatoricUncertainty"], "monteCarloSE": ev["monteCarloSE"],
            "calibrationState": ev["calibrationState"], "parameterSnapshotHash": snapshot["parameter_snapshot_hash"],
            "evidenceHashes": snapshot["evidence_hashes"], "dependencyTags": snapshot["dependency_tags"],
            "productionSelectable": production_selectable,
            "researchOnly": blocker in {"RESEARCH_ONLY_NOT_SELECTABLE", "SHADOW_SUPPORTED_NOT_SELECTABLE"},
            "worldCount": len(values),
            "_selectionOutcomes": selection_outcomes,
        })
        modeled.append(rec)
        classified.append(rec)

    (dest / "parameters").mkdir(exist_ok=True)
    (dest / "parameters" / "snapshots.json").write_text(
        json.dumps(parameter_cache, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    n_worlds = dag.add("EVENT_WORLDS", "board", parents=[n_res.key])
    dag.complete(n_worlds.key, content_hash({"events": len({k[0] for k in world_cache}), "n": N_WORLDS}))
    model_perf = t.finish(
        OutputRows=len(modeled),
        NodeCount=len(world_cache),
        EventContextSets=len(event_context_cache),
        SimulatedPlayerWorlds=sum(len(v) for v in world_cache.values()),
    )
    (dest / "performance" / "model.json").write_text(json.dumps(model_perf, indent=2) + "\n", encoding="utf-8")
    stages_done.add("MODEL")

    ranked = rank_candidates(modeled, top_k=25, seed=har_sha)
    qualified = [
        p for p in ranked
        if p.get("grade") == "PLAYABLE" and p.get("productionSelectable")
        and p["row"].get("modifier") != "GOBLIN"
    ]
    card = build_card(qualified)
    exposure = exposure_report(card)
    n_rank = dag.add("RANK", "board", parents=[n_worlds.key])
    dag.complete(n_rank.key, content_hash([p["row"]["projectionId"] for p in ranked[:25]]))
    n_port = dag.add("PORTFOLIO", "board", parents=[n_rank.key])
    dag.complete(n_port.key, content_hash({"ids": [p["row"]["projectionId"] for p in card], "exposure": exposure}))

    def slim(p: dict) -> dict:
        r = p["row"]
        return {
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
            "calibrationState": p.get("calibrationState"), "selectionScore": p.get("selectionScore"),
            "parameterSnapshotHash": p.get("parameterSnapshotHash"),
            "topKInclusionP": p.get("topKInclusionP"), "rankStability": p.get("rankStability"),
            "posteriorRegret": p.get("posteriorRegret"),
            "trueLineTolerance": (p.get("lineSurface") or {}).get("true_unclamped_line_tolerance"),
            "sideEvaluations": p.get("sideEvaluations"), "dependencyTags": p.get("dependencyTags"),
            "projectionId": r.get("projectionId"),
        }

    top25_ranked = [slim(p) for p in ranked[:25]]
    top25_qualified = [slim(p) for p in qualified[:25]]
    top100 = [slim(p) for p in ranked[:100]]
    strict_card = [slim(p) for p in card]
    full_population = [slim(p) for p in classified]
    (dest / "top100.json").write_text(json.dumps(top100, indent=2) + "\n", encoding="utf-8")
    (dest / "top25_ranked.json").write_text(json.dumps(top25_ranked, indent=2) + "\n", encoding="utf-8")
    (dest / "top25_qualified.json").write_text(json.dumps(top25_qualified, indent=2) + "\n", encoding="utf-8")
    (dest / "strict_card.json").write_text(json.dumps(strict_card, indent=2) + "\n", encoding="utf-8")
    (dest / "full_population.jsonl").write_text("".join(json.dumps(p) + "\n" for p in full_population), encoding="utf-8")
    (dest / "dependencies.json").write_text(
        json.dumps(exposure, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    states_count = {}
    for p in classified:
        states_count[p["state"]] = states_count.get(p["state"], 0) + 1

    if not global_selection_gate:
        run_state = "EMPTY_CARD_COMPLETE"
    elif not card and board["accounting"]["raw_projection_rows"] > 0:
        run_state = "EMPTY_CARD_COMPLETE"
    elif unsupported:
        run_state = "COMPLETE_WITH_UNSUPPORTED_ROWS"
    else:
        run_state = "COMPLETE_FROZEN"

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
        "executionMode": "PRODUCTION" if global_selection_gate else "ENGINEERING_OR_BLOCKED",
        "softwareE2eComplete": True,
        "runState": run_state,
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
        "eventWorlds": len(world_cache),
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
        "dag": dag.snapshot(),
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
    freeze["frozenForecastHash"] = compute_forecast_hash(
        freeze,
        full_population,
        strict_card,
        top25_ranked,
    )
    n_fz = dag.add("FREEZE", "board", parents=[n_port.key])
    dag.complete(n_fz.key, freeze["frozenForecastHash"])
    freeze["dag"] = dag.snapshot()
    (dest / "frozen_forecast.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "freeze.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "frozen_forecast.sha256").write_text(freeze["frozenForecastHash"] + "\n", encoding="utf-8")
    (dest / "population_full.jsonl").write_text("".join(json.dumps(p) + "\n" for p in full_population), encoding="utf-8")
    (dest / "accounting.json").write_text(json.dumps({**(board.get("accounting") or {}), "states": states_count, "playable": len(qualified), "cardSize": len(card)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "hashes.json").write_text(json.dumps({"boardHash": board.get("contentHash"), "harSha256": har_sha, "frozenForecastHash": freeze["frozenForecastHash"], "checkpointPending": False, "schemaV1Expected": "6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22", "schemaV2": (schema_root.get("v2") or {})}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    blockers = []
    if excluded:
        blockers.append({"code": "GOBLIN_SELECTION_FORBIDDEN", "count": excluded})
    if unsupported:
        blockers.append({"code": "UNSUPPORTED_FAIL_CLOSED", "count": unsupported})
    if unresolved:
        blockers.append({"code": "UNRESOLVED", "count": unresolved})
    (dest / "blockers.json").write_text(json.dumps(blockers, indent=2) + "\n", encoding="utf-8")

    store = IndexedStore(dest / "index.sqlite")
    store.append(kind="freeze", cutoff=forecast_cutoff, run_id=run_id, lr=LEARNING_REVISION, payload={"hash": freeze["frozenForecastHash"]}, source_hash=har_sha)
    store.close()

    integrity = {
        **freeze,
        "states": states_count,
        "accounting": board["accounting"],
        "createdAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (dest / "run_integrity.json").write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_checkpoint(
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
            "completedStages": ["BOARD_FREEZE", "RESEARCH", "MODEL", "RANK", "PORTFOLIO", "FREEZE"],
            "pending": [],
            "nextDeterministicAction": "none",
            "rowCounts": states_count,
            "blockers": [b["code"] for b in blockers],
            "frozenForecastHash": freeze["frozenForecastHash"],
        },
    )
    return {
        "run_id": run_id,
        "dest": str(dest),
        "runState": run_state,
        "integrity": integrity,
        "card": strict_card,
        "top25_qualified": top25_qualified,
        "board": board,
        "classified": classified,
        "world_cache": world_cache,
        "dag": dag.snapshot(),
    }


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
                "chatgptOperable": integ.get("chatgptOperable"),
                "dest": result["dest"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
