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
from dcm.model.worlds import MARKET_FROM_STATS, simulate_player_worlds, value_from_stats
from dcm.research.host_plan import build_host_research_plan
from dcm.research.provider import FileProvider, FixtureProvider, collect
from dcm.research.requests import build_requests
from dcm.runtime.checkpoint import load_checkpoint, write_checkpoint
from dcm.runtime.dag import Dag
from dcm.runtime.governor import Governor
from dcm.runtime.mount_v541 import mount_default
from dcm.runtime.schema_root import verify_schema
from dcm.runtime.perf import StageTimer
from dcm.runtime.store import IndexedStore
from dcm.selection.portfolio import build_card, exposure_report
from dcm.sports.common.plugin import selection_state

LEARNING_REVISION = "LR000000"
PREDICTIVE_CLAIM = "NONE"
SOFTWARE = "6.0.0+WSAB.E2E.PRODUCTION_PIPELINE.LR000000"
SCHEMA = "PHASE_BC_SCHEMA_V1_2026-08-25"
N_WORLDS = int(__import__("os").environ.get("DCM_FAST_WORLDS", "256"))
N_SERIOUS = int(__import__("os").environ.get("DCM_SERIOUS_WORLDS", "2048"))

ARTIFACT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = Path(__file__).resolve().parents[3]
SYNTHETIC = ARTIFACT_ROOT / "fixtures" / "synthetic_har.json"

SUPPORTED_FAMILIES = {"basketball", "gridiron", "baseball"}


def _run_id(har_sha: str, cutoff: str) -> str:
    return "RUN_" + content_hash({"har": har_sha, "cutoff": cutoff, "sw": SOFTWARE})[:16]


def _classify(row: dict) -> tuple[str, str | None]:
    if row.get("modifier") == "GOBLIN":
        return "EXCLUDED_GOBLIN", "GOBLIN_SELECTION_FORBIDDEN"
    if row.get("modifier") == "OTHER":
        return "UNRESOLVED", "MODIFIER_UNKNOWN"
    if row.get("side") == "UNKNOWN" and not row.get("offeredHigher") and not row.get("offeredLower"):
        return "UNRESOLVED", "OFFERED_SIDE_UNKNOWN"
    if row.get("sportFamily") == "baseball" and row.get("market") == "hits_runs_rbi" and abs(float(row.get("line", 0)) - 0.5) < 1e-9:
        return "UNRESOLVED", "HALF_LINE_AVOID_BASEBALL_HRRBI_0_5"
    family = row.get("sportFamily") or ""
    cap = selection_state(family, row.get("league") or "", row.get("market") or "")
    if family not in SUPPORTED_FAMILIES or cap == "UNSUPPORTED_FAIL_CLOSED":
        return "UNSUPPORTED", "UNSUPPORTED_FAIL_CLOSED"
    if cap == "RESEARCH_ONLY":
        return "MODELED", "RESEARCH_ONLY_NOT_SELECTABLE"
    if cap == "SHADOW_SUPPORTED":
        return "MODELED", "SHADOW_SUPPORTED_NOT_SELECTABLE"
    market = row.get("market")
    if family == "basketball" and market not in {"pts", "reb", "ast", "pra", "3pm", "stl", "blk"}:
        return "UNSUPPORTED", "UNSUPPORTED_FAIL_CLOSED"
    if family == "gridiron" and market not in MARKET_FROM_STATS and market not in {"pass_yds", "rush_yds", "rec_yds", "receptions", "pass_rush_yds", "rush_rec_yds"}:
        return "UNSUPPORTED", "UNSUPPORTED_FAIL_CLOSED"
    if family == "baseball" and market not in {"h", "tb", "k", "hits_runs_rbi"}:
        return "UNSUPPORTED", "UNSUPPORTED_FAIL_CLOSED"
    return "MODELED", None


def run_dcm(
    *,
    input_path: Path | None,
    forecast_cutoff: str,
    input_paths: list[Path] | None = None,
    output_root: Path,
    synthetic: bool = False,
    research: str = "file",
    evidence_dir: Path | None = None,
    workspace: Path = DEFAULT_WORKSPACE,
    resume: Path | None = None,
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
        synthetic = bool(ingest_meta.get("synthetic", board.get("synthetic", False)))
        run_id = ck["runId"]
        dest = output_root
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
        har_sha = ingest["harSha256"]
        run_id = _run_id(har_sha, forecast_cutoff)
        dest = output_root / run_id
        dest.mkdir(parents=True, exist_ok=True)
        board = freeze_board(ingest, mount=mount, cutoff=forecast_cutoff)
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
        (dest / "SCHEMA_STATE.json").write_text(json.dumps(schema_root, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        stages_done.add("BOARD_FREEZE")
        har_perf = t.finish(InputRows=len(board["rows"]), OutputRows=len(board["rows"]))
        (dest / "logs").mkdir(exist_ok=True)
        (dest / "performance").mkdir(exist_ok=True)
        (dest / "performance" / "har.json").write_text(json.dumps(har_perf, indent=2) + "\n", encoding="utf-8")

    config_hash = content_hash({"sw": SOFTWARE, "n": N_WORLDS, "lr": LEARNING_REVISION})
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

    t = StageTimer("RESEARCH")
    requests = build_requests(rows, forecast_cutoff)
    (dest / "research_requests.json").write_text(json.dumps(requests, indent=2) + "\n", encoding="utf-8")
    if research == "file":
        provider: Any = FileProvider(evidence_dir or dest / "evidence")
    else:
        provider = FixtureProvider(forecast_cutoff)
    bundle = collect(requests, provider)
    (dest / "evidence").mkdir(exist_ok=True)
    (dest / "evidence" / "claims.json").write_text(json.dumps(bundle["claims"], indent=2) + "\n", encoding="utf-8")
    (dest / "evidence" / "coverage.json").write_text(
        json.dumps(bundle.get("coverage") or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (dest / "evidence" / "conflicts.json").write_text(
        json.dumps(bundle.get("conflicts") or [], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    host_plan = build_host_research_plan(requests, coverage=bundle.get("coverage"))
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

    calibration_path = workspace / "dcm_v6" / "calibration" / "active_cells.json"
    try:
        calibration_cells = json.loads(calibration_path.read_text(encoding="utf-8")) if calibration_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        calibration_cells = {}
    canonical_ready = mount.get("state") == "HASH_VERIFIED_EXTRACTED"
    schema_ready = bool(schema_root.get("productionEligible")) and schema_root.get("state") == "HASH_VERIFIED"
    production_research_ready = bool(bundle.get("production_ready"))
    global_selection_gate = canonical_ready and schema_ready and production_research_ready and not synthetic

    gov = Governor(max_worlds=N_WORLDS, serious_worlds=N_SERIOUS)
    t = StageTimer("MODEL")
    world_cache: dict[tuple[str, str, str], list[dict[str, float]]] = {}
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
                world_cache[key] = simulate_player_worlds(
                    row, n=gov.max_worlds, seed=har_sha, parameter_snapshot=snapshot
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
        if production_selectable and preliminary >= 0.52 and gov.serious_worlds > gov.max_worlds:
            world_cache[key] = simulate_player_worlds(
                row, n=gov.serious_worlds, seed=har_sha, parameter_snapshot=snapshot
            )
            values = [value_from_stats(row["market"], w) for w in world_cache[key]]
            dist = from_worlds(values, float(row["line"]))

        demon = row.get("modifier") == "DEMON"
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
    model_perf = t.finish(OutputRows=len(modeled), NodeCount=len(world_cache))
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
    (dest / "top100.json").write_text(json.dumps(top100, indent=2) + "\n", encoding="utf-8")
    (dest / "top25_ranked.json").write_text(json.dumps(top25_ranked, indent=2) + "\n", encoding="utf-8")
    (dest / "top25_qualified.json").write_text(json.dumps(top25_qualified, indent=2) + "\n", encoding="utf-8")
    (dest / "strict_card.json").write_text(json.dumps(strict_card, indent=2) + "\n", encoding="utf-8")
    (dest / "full_population.jsonl").write_text("".join(json.dumps(slim(p)) + "\n" for p in classified), encoding="utf-8")
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
    forecast_hash_payload = {
        "runId": run_id,
        "dcmVersion": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "schemaId": SCHEMA,
        "schemaHash": schema_root.get("observedSha256"),
        "harSha256": har_sha,
        "forecastCutoff": forecast_cutoff,
        "boardHash": board["contentHash"],
        "forecasts": [
            {
                "projectionId": p["row"].get("projectionId"),
                "line": p["row"].get("line"),
                "modifier": p["row"].get("modifier"),
                "offeredHigher": p["row"].get("offeredHigher"),
                "offeredLower": p["row"].get("offeredLower"),
                "state": p.get("state"),
                "blocker": p.get("blocker"),
                "grade": p.get("grade"),
                "selectedSide": p.get("selectedSide"),
                "rawP": p.get("rawP"),
                "calibratedP": p.get("calibratedP"),
                "evidenceSafeP": p.get("evidenceSafeP"),
                "pHigher": p.get("pHigher"),
                "pLower": p.get("pLower"),
                "pPush": p.get("pPush"),
                "lowerBound": p.get("lowerBound"),
                "parameterSnapshotHash": p.get("parameterSnapshotHash"),
                "rank": p.get("rank"),
                "selectionScore": p.get("selectionScore"),
                "productionSelectable": p.get("productionSelectable", False),
            }
            for p in sorted(classified, key=lambda x: str(x["row"].get("projectionId")))
        ],
        "card": [p["projectionId"] for p in strict_card],
        "ranked": [p["projectionId"] for p in top25_ranked],
    }
    freeze["frozenForecastHash"] = content_hash(forecast_hash_payload)
    n_fz = dag.add("FREEZE", "board", parents=[n_port.key])
    dag.complete(n_fz.key, freeze["frozenForecastHash"])
    freeze["dag"] = dag.snapshot()
    (dest / "frozen_forecast.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "frozen_forecast.sha256").write_text(freeze["frozenForecastHash"] + "\n", encoding="utf-8")

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
    p = argparse.ArgumentParser(description="DCM v6 E2E runner (LR000000, not optimized 6.0)")
    p.add_argument("--input", type=Path, action="append", default=None, help="HAR input; repeat for complementary captures")
    p.add_argument("--out", type=Path, default=DEFAULT_WORKSPACE / "dcm_v6" / "RUNS")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--cutoff", default="2026-08-28T00:00:00Z")
    p.add_argument("--research", choices=["fixture", "file"], default="file")
    p.add_argument("--evidence-dir", type=Path, default=None)
    p.add_argument("--resume", type=Path, default=None)
    p.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    p.add_argument("--version", default=SOFTWARE)
    args = p.parse_args(argv)
    try:
        result = run_dcm(
            input_path=(args.input[0] if args.input and len(args.input) == 1 else None),
            input_paths=args.input,
            forecast_cutoff=args.cutoff,
            output_root=args.out,
            synthetic=args.synthetic,
            research=args.research,
            evidence_dir=args.evidence_dir,
            workspace=args.workspace,
            resume=args.resume,
        )
    except FileNotFoundError as e:
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
