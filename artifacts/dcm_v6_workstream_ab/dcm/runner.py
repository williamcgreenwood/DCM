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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.identity.resolve import freeze_map, resolve_row
from dcm.ingest.board import freeze_board, write_board
from dcm.ingest.har import ingest_har
from dcm.model.distributions import from_worlds
from dcm.model.grade import grade as grade_of
from dcm.model.line_surface import surface as line_surface
from dcm.model.worlds import MARKET_FROM_STATS, simulate_player_worlds, value_from_stats
from dcm.research.provider import FileProvider, FixtureProvider, collect
from dcm.research.requests import build_requests
from dcm.runtime.checkpoint import load_checkpoint, write_checkpoint
from dcm.runtime.dag import Dag
from dcm.runtime.governor import Governor
from dcm.runtime.mount_v541 import mount_default
from dcm.runtime.perf import StageTimer
from dcm.runtime.store import IndexedStore
from dcm.selection.portfolio import build_card
from dcm.sports.common.plugin import selection_state

LEARNING_REVISION = "LR000000"
PREDICTIVE_CLAIM = "NONE"
SOFTWARE = "6.0.0+WSAB.E2E.LR000000"
SCHEMA = "PHASE_BC_SCHEMA_V1_2026-08-25"
N_WORLDS = 64
N_SERIOUS = 128

SYNTHETIC = Path("/workspace/artifacts/dcm_v6_workstream_ab/fixtures/synthetic_har.json")

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
    output_root: Path,
    synthetic: bool = False,
    research: str = "fixture",
    evidence_dir: Path | None = None,
    workspace: Path = Path("/workspace"),
    resume: Path | None = None,
) -> dict[str, Any]:
    if resume:
        ck = load_checkpoint(resume)
        output_root = Path(ck["artifactRoot"])
        # Re-enter from HAR freeze artifacts (deterministic).
        board = json.loads((output_root / "board.json").read_text(encoding="utf-8"))
        ingest_meta = json.loads((output_root / "input_manifest.json").read_text(encoding="utf-8"))
        mount = json.loads((output_root / "MOUNT_STATE.json").read_text(encoding="utf-8"))
        har_sha = ingest_meta["harSha256"]
        run_id = ck["runId"]
        dest = output_root
        stages_done = set(ck.get("completedStages") or [])
    else:
        stages_done = set()
        mount = mount_default(workspace)
        t = StageTimer("HAR")
        if synthetic:
            raw = json.loads(SYNTHETIC.read_text(encoding="utf-8"))
            raw_bytes = SYNTHETIC.read_bytes()
        else:
            if input_path is None or not input_path.is_file():
                raise FileNotFoundError("HAR missing. Pass --input or --synthetic.")
            raw_bytes = input_path.read_bytes()
            raw = raw_bytes
        ingest = ingest_har(raw, raw_bytes=raw_bytes)
        har_sha = ingest["harSha256"]
        run_id = _run_id(har_sha, forecast_cutoff)
        dest = output_root / run_id
        dest.mkdir(parents=True, exist_ok=True)
        board = freeze_board(ingest, mount=mount, cutoff=forecast_cutoff)
        write_board(board, dest / "board.json")
        (dest / "input_manifest.json").write_text(
            json.dumps({"harSha256": har_sha, "adapter": ingest["adapter"], "parserVersion": ingest["parserVersion"]}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        (dest / "MOUNT_STATE.json").write_text(json.dumps(mount, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
                "nextDeterministicAction": "write evidence/ then --resume checkpoint.json",
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

    gov = Governor(max_worlds=N_WORLDS, serious_worlds=N_SERIOUS)
    t = StageTimer("MODEL")
    world_cache: dict[tuple[str, str], list[dict[str, float]]] = {}
    modeled: list[dict[str, Any]] = []
    classified: list[dict[str, Any]] = []
    conservation_failures = 0
    unsupported = excluded = unresolved = 0
    for row in rows:
        state, blocker = _classify(row)
        rec: dict[str, Any] = {"row": row, "state": state, "blocker": blocker}
        if state == "EXCLUDED_GOBLIN":
            excluded += 1
            classified.append(rec)
            continue
        if state == "UNSUPPORTED":
            unsupported += 1
            classified.append(rec)
            continue
        if state == "UNRESOLVED":
            unresolved += 1
            classified.append(rec)
            continue
        key = (row["eventId"], row["playerId"])
        try:
            if key not in world_cache:
                world_cache[key] = simulate_player_worlds(row, n=gov.max_worlds, seed=har_sha)
            values = [value_from_stats(row["market"], w) for w in world_cache[key]]
        except KeyError:
            rec["state"] = "UNSUPPORTED"
            rec["blocker"] = "UNSUPPORTED_FAIL_CLOSED"
            unsupported += 1
            classified.append(rec)
            continue
        except RuntimeError:
            conservation_failures += 1
            rec["state"] = "UNRESOLVED"
            rec["blocker"] = "PRIMITIVE_CONSERVATION_FAILURE"
            unresolved += 1
            classified.append(rec)
            continue
        dist = from_worlds(values, float(row["line"]))
        if abs(dist["pHigher"] + dist["pLower"] + dist["pPush"] - 1.0) > 1e-6:
            raise RuntimeError("SIMPLEX_FAILURE")
        side = row.get("side")
        if side not in {"MORE", "LESS"}:
            side = "MORE" if row.get("offeredHigher") and dist["pHigher"] >= dist["pLower"] else "LESS"
        selected_p = dist["pHigher"] if side == "MORE" else dist["pLower"]
        demon = row.get("modifier") == "DEMON"
        fragility = 0.42 if demon else 0.18
        lb = max(0.01, selected_p - 0.07)
        serious = selected_p >= 0.52 or demon
        surf = line_surface(values, float(row["line"])) if serious else {
            "offered_line": float(row["line"]),
            "offered_probability": dist["pHigher"],
            "break_even_line": float(row["line"]),
            "true_unclamped_line_tolerance": 0.0,
            "edge_elasticity": 0.0,
            "robustness_area": 0.0,
            "pHigher": dist["pHigher"],
            "pLower": dist["pLower"],
            "pPush": dist["pPush"],
            "mean": dist["mean"],
        }
        g = grade_of(
            selected_p=selected_p,
            lower_bound=lb,
            demon=demon,
            fragility=fragility,
            robustness_area=surf["robustness_area"],
            elasticity=surf["edge_elasticity"],
            false_sign=max(0.04, 0.5 - abs(selected_p - 0.5)),
        )
        score = selected_p * 0.45 + lb * 0.25 - fragility * 0.1
        rec.update(
            {
                "state": "MODELED",
                "grade": g,
                "selectedSide": side,
                "selectedP": selected_p,
                "pHigher": dist["pHigher"],
                "pLower": dist["pLower"],
                "pPush": dist["pPush"],
                "mean": dist["mean"],
                "lowerBound": lb,
                "lineSurface": surf,
                "selectionScore": score,
                "researchOnly": blocker in {"RESEARCH_ONLY_NOT_SELECTABLE", "SHADOW_SUPPORTED_NOT_SELECTABLE"},
            }
        )
        modeled.append(rec)
        classified.append(rec)

    n_worlds = dag.add("EVENT_WORLDS", "board", parents=[n_res.key])
    dag.complete(n_worlds.key, content_hash({"events": len({k[0] for k in world_cache}), "n": N_WORLDS}))
    model_perf = t.finish(OutputRows=len(modeled), NodeCount=len(world_cache))
    (dest / "performance" / "model.json").write_text(json.dumps(model_perf, indent=2) + "\n", encoding="utf-8")
    stages_done.add("MODEL")

    ranked = sorted(modeled, key=lambda p: p.get("selectionScore") or 0, reverse=True)
    for i, p in enumerate(ranked, 1):
        p["rank"] = i
    qualified = [
        p
        for p in ranked
        if p.get("grade") == "PLAYABLE" and not p.get("researchOnly") and p["row"].get("modifier") != "GOBLIN"
    ]
    card = build_card(qualified)
    n_rank = dag.add("RANK", "board", parents=[n_worlds.key])
    dag.complete(n_rank.key, content_hash([p["row"]["projectionId"] for p in ranked[:25]]))
    n_port = dag.add("PORTFOLIO", "board", parents=[n_rank.key])
    dag.complete(n_port.key, content_hash([p["row"]["projectionId"] for p in card]))

    def slim(p: dict) -> dict:
        r = p["row"]
        return {
            "rank": p.get("rank"),
            "player": r.get("playerName"),
            "team": r.get("team"),
            "opponent": r.get("opponent"),
            "event": r.get("eventLabel"),
            "market": r.get("market"),
            "line": r.get("line"),
            "direction": p.get("selectedSide"),
            "modifier": r.get("modifier"),
            "selectedP": p.get("selectedP"),
            "pHigher": p.get("pHigher"),
            "pLower": p.get("pLower"),
            "pPush": p.get("pPush"),
            "lowerBound": p.get("lowerBound"),
            "grade": p.get("grade"),
            "state": p.get("state"),
            "blocker": p.get("blocker"),
            "trueLineTolerance": (p.get("lineSurface") or {}).get("true_unclamped_line_tolerance"),
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
        json.dumps({"maxPerEvent": 2, "uniquePlayer": True, "eventOnce": True}, indent=2) + "\n",
        encoding="utf-8",
    )

    states_count = {}
    for p in classified:
        states_count[p["state"]] = states_count.get(p["state"], 0) + 1

    run_state = "EMPTY_CARD_COMPLETE" if not card and board["accounting"]["raw_projection_rows"] > 0 else "COMPLETE_FROZEN"
    if unsupported:
        run_state = "COMPLETE_WITH_UNSUPPORTED_ROWS" if card or qualified else run_state

    freeze = {
        "runId": run_id,
        "dcmVersion": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "optimizedDcm60Claim": False,
        "hostPerformanceCertified": False,
        "chatgptOperable": research == "fixture" or bundle["complete"],
        "softwareE2eComplete": True,
        "runState": run_state,
        "v5Decoder": mount.get("har_decoder"),
        "v5MountState": mount.get("state"),
        "schemaId": SCHEMA,
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
        "top25QualifiedCount": len(top25_qualified),
        "dag": dag.snapshot(),
    }
    freeze["frozenForecastHash"] = content_hash(
        {k: v for k, v in freeze.items() if k not in {"frozenForecastHash", "dag"}}
        | {"card": [p["projectionId"] for p in strict_card], "ranked": [p["projectionId"] for p in top25_ranked]}
    )
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
    p.add_argument("--input", type=Path, default=None)
    p.add_argument("--out", type=Path, default=Path("/workspace/dcm_v6/RUNS"))
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--cutoff", default="2026-08-28T00:00:00Z")
    p.add_argument("--research", choices=["fixture", "file"], default="fixture")
    p.add_argument("--evidence-dir", type=Path, default=None)
    p.add_argument("--resume", type=Path, default=None)
    p.add_argument("--workspace", type=Path, default=Path("/workspace"))
    p.add_argument("--version", default=SOFTWARE)
    args = p.parse_args(argv)
    try:
        result = run_dcm(
            input_path=args.input,
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
