#!/usr/bin/env python3
"""Phase 9 baseline profiler — synthetic/sanitized loads only.

Establishes measured performance truth BEFORE custom native / C++ code.
Never sets hostPerformanceCertified=true. Does not alter RNG or forecast
semantics. Emits JSON + markdown under docs/benchmarks/ (or --out).

Reproducible command (from repo root, package installed or PYTHONPATH=src):

  python benchmarks/baseline/profile_baseline.py \\
    --board-sizes 100 1000 4000 \\
    --world-sizes 64 128 512 2048 \\
    --out docs/benchmarks

Optional larger sizes (skipped automatically when host memory is tight):

  python benchmarks/baseline/profile_baseline.py \\
    --board-sizes 100 1000 4000 10000 \\
    --world-sizes 64 128 512 2048 10000 \\
    --out docs/benchmarks
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import resource
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from dcm.algorithms.cache import LRUCache
from dcm.board_store import BoardStore
from dcm.cfb.event_worlds import simulate_joint_cfb_event_worlds
from dcm.compact import (
    CompactNumericBoard,
    feature_matrix_from_records,
    parameter_matrix_from_snapshots,
)
from dcm.contracts.hashes import content_hash
from dcm.runtime.dag import Dag
from dcm.runtime.perf import StageTimer

SCHEMA = "pillars_dcm.baseline_profile.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _peak_rss_bytes() -> int:
    # Linux ru_maxrss is KiB.
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def _available_ram_bytes() -> int | None:
    try:
        meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in meminfo.splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            return int(parts[1]) * 1024
    return None


def _safe_board_sizes(requested: list[int]) -> tuple[list[int], list[dict[str, Any]]]:
    avail = _available_ram_bytes()
    notes: list[dict[str, Any]] = []
    kept: list[int] = []
    # Rough upper bound: ~2–4 KiB audit dict + indexes per offer; leave headroom.
    for n in requested:
        need = n * 8_000 + 200_000_000
        if avail is not None and n >= 10_000 and avail < need:
            notes.append(
                {
                    "size": n,
                    "skipped": True,
                    "reason": "INSUFFICIENT_MemAvailable",
                    "memAvailableBytes": avail,
                    "estimatedNeedBytes": need,
                }
            )
            continue
        kept.append(n)
    return kept, notes


def _safe_world_sizes(requested: list[int], *, players: int) -> tuple[list[int], list[dict[str, Any]]]:
    avail = _available_ram_bytes()
    notes: list[dict[str, Any]] = []
    kept: list[int] = []
    for n in requested:
        # Each world stores ~11 float fields × players as Python dicts (~2–4 KiB/player/world).
        need = n * players * 4_000 + 150_000_000
        if avail is not None and n >= 10_000 and avail < need:
            notes.append(
                {
                    "size": n,
                    "skipped": True,
                    "reason": "INSUFFICIENT_MemAvailable",
                    "memAvailableBytes": avail,
                    "estimatedNeedBytes": need,
                    "players": players,
                }
            )
            continue
        kept.append(n)
    return kept, notes


def _synthetic_cfb_rows(n: int) -> list[dict[str, Any]]:
    roles = ["QB", "RB", "WR", "WR", "TE", "WR", "RB", "K"]
    markets = {
        "QB": "pass_yds",
        "RB": "rush_yds",
        "WR": "rec_yds",
        "TE": "rec_yds",
        "K": "kicking_pts",
    }
    rows: list[dict[str, Any]] = []
    for i in range(n):
        role = roles[i % len(roles)]
        event = f"CFB_E_{i // 40}"
        team = f"T{(i // 8) % 64:02d}"
        rows.append(
            {
                "projectionId": f"CFB_{i}",
                "sportFamily": "gridiron",
                "league": "CFB",
                "eventId": event,
                "eventLabel": f"CFB Event {i // 40}",
                "playerId": f"P_{i}",
                "playerName": f"Player {i}",
                "teamId": team,
                "team": team,
                "opponent": f"T{((i // 8) + 1) % 64:02d}",
                "market": markets[role],
                "marketLabel": markets[role],
                "line": 10.5 + (i % 250),
                "side": "UNKNOWN",
                "offeredHigher": True,
                "offeredLower": True,
                "modifier": "STANDARD",
                "boardId": "FULL_GAME",
                "productType": "PLAYER_PICKS",
                "role": role,
                "mean": 12.0 + (i % 200),
                "variance": 25.0 + (i % 50),
                "reliability": 0.4 + (i % 50) / 100.0,
                "fragility": 0.1 + (i % 40) / 100.0,
                "oodRisk": 0.05 + (i % 30) / 100.0,
            }
        )
    return rows


def _cfb_team_specs(players: int = 8) -> list[dict[str, Any]]:
    templates = [
        ("QB", "pass_yds", {"role": "QB", "pass_att_mean": 32.0, "pass_att_sd": 4.0, "completion_rate": 0.62, "ypa": 7.2}),
        ("RB", "rush_yds", {"role": "RB", "rush_att_mean": 16.0, "rush_att_sd": 3.0, "ypc": 4.4}),
        ("WR", "rec_yds", {"role": "WR", "routes_mean": 9.0, "routes_sd": 2.0, "target_rate": 0.24, "catch_rate": 0.62}),
        ("WR", "rec_yds", {"role": "WR", "routes_mean": 7.0, "routes_sd": 1.5, "target_rate": 0.20, "catch_rate": 0.58}),
        ("TE", "rec_yds", {"role": "TE", "routes_mean": 5.0, "routes_sd": 1.2, "target_rate": 0.18, "catch_rate": 0.66}),
        ("WR", "rec_yds", {"role": "WR", "routes_mean": 5.5, "routes_sd": 1.0, "target_rate": 0.15, "catch_rate": 0.55}),
        ("RB", "rush_yds", {"role": "RB", "rush_att_mean": 8.0, "rush_att_sd": 2.0, "ypc": 4.0}),
        ("K", "kicking_pts", {"role": "K", "fg_att_mean": 1.8, "xp_att_mean": 3.0}),
    ]
    specs: list[dict[str, Any]] = []
    for i in range(players):
        role, market, params = templates[i % len(templates)]
        specs.append(
            {
                "row": {
                    "playerId": f"{role}_{i}",
                    "eventId": "CFB_BENCH_E0",
                    "teamId": "T00",
                    "role": role,
                    "market": market,
                    "sportFamily": "gridiron",
                    "league": "CFB",
                },
                "snapshot": {"parameters": dict(params)},
            }
        )
    return specs


def _stage_metrics(timer: StageTimer, *, tracemalloc_peak: int | None = None, **extra: Any) -> dict[str, Any]:
    rec = timer.finish(**extra)
    if tracemalloc_peak is not None:
        rec["pythonTracemallocPeakBytes"] = int(tracemalloc_peak)
    return rec


def profile_board_store(board_sizes: list[int]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for n in board_sizes:
        gc.collect()
        rows = _synthetic_cfb_rows(n)
        input_bytes = len(json.dumps(rows).encode("utf-8"))

        tracemalloc.start()
        timer = StageTimer("board_store_build")
        store = BoardStore(rows)
        peak = tracemalloc.get_traced_memory()[1]
        build = _stage_metrics(
            timer,
            tracemalloc_peak=peak,
            boardRows=n,
            inputRows=n,
            inputBytes=input_bytes,
            compactN=store.compact.n,
            sqlitePayloadDuplicated=store.sqlite_has_payload_column(),
        )
        tracemalloc.stop()

        # Query mix: exact offer + event posting list + sqlite + bloom.
        events = sorted({r["eventId"] for r in rows})
        offer_ids = [r["projectionId"] for r in rows[:: max(1, n // 50)]]
        tracemalloc.start()
        timer = StageTimer("board_store_query")
        hit_count = 0
        for oid in offer_ids:
            if store.exact_offer(oid) is not None:
                hit_count += 1
            _ = store.might_have_offer(oid)
        event_hits = 0
        for ev in events[: min(40, len(events))]:
            ids = store.row_ids_for_event(ev)
            event_hits += int(ids.size)
            _ = store.sqlite_event_offers(ev)
        query_peak = tracemalloc.get_traced_memory()[1]
        query = _stage_metrics(
            timer,
            tracemalloc_peak=query_peak,
            boardRows=n,
            exactOfferLookups=len(offer_ids),
            exactOfferHits=hit_count,
            eventLookups=min(40, len(events)),
            eventRowIdsReturned=event_hits,
            outputRows=event_hits,
        )
        tracemalloc.stop()

        # SQLite size estimate via page_count (in-memory DB).
        page_count = store.sqlite.execute("PRAGMA page_count").fetchone()[0]
        page_size = store.sqlite.execute("PRAGMA page_size").fetchone()[0]
        sqlite_bytes = int(page_count) * int(page_size)

        digest = content_hash(
            {
                "n": store.n,
                "offerIdsHead": list(store.offer_ids[:16]),
                "events": sorted(store.by_event_rows.keys())[:32],
                "lineSum": store.compact.line_sum(),
            }
        )
        store.close()
        results.append(
            {
                "stageGroup": "BoardStore",
                "boardRows": n,
                "build": build,
                "query": query,
                "sqliteBytes": sqlite_bytes,
                "outputHash": digest,
                "hostPerformanceCertified": False,
            }
        )
    return results


def profile_compact_ops(board_sizes: list[int]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for n in board_sizes:
        rows = _synthetic_cfb_rows(n)
        feature_recs = [
            {
                "entity": r["playerId"],
                "featureName": f"L5_{r['market']}_mean",
                "value": float(r["mean"]),
            }
            for r in rows
        ]
        snaps = [
            {
                "offerId": r["projectionId"],
                "parameters": {
                    "pass_att_mean": 30.0 if r["role"] == "QB" else 0.0,
                    "rush_att_mean": 12.0 if r["role"] == "RB" else 2.0,
                    "routes_mean": 7.0 if r["role"] in {"WR", "TE"} else 0.0,
                    "minutes_mean": 0.0,
                },
            }
            for r in rows
        ]

        tracemalloc.start()
        timer = StageTimer("compact_board_from_rows")
        board = CompactNumericBoard.from_board_rows(rows)
        from_rows = _stage_metrics(timer, tracemalloc_peak=tracemalloc.get_traced_memory()[1], boardRows=n)
        tracemalloc.stop()

        tracemalloc.start()
        timer = StageTimer("compact_line_sum_soa")
        soa_sum = board.line_sum()
        # Repeat to amortize timer overhead on tiny boards.
        for _ in range(49):
            soa_sum = board.line_sum()
        soa = _stage_metrics(
            timer,
            tracemalloc_peak=tracemalloc.get_traced_memory()[1],
            boardRows=n,
            iterations=50,
            lineSum=soa_sum,
        )
        tracemalloc.stop()

        tracemalloc.start()
        timer = StageTimer("compact_dict_line_sum")
        dict_sum = 0.0
        for _ in range(50):
            dict_sum = sum(float(r["line"]) for r in rows)
        dict_rec = _stage_metrics(
            timer,
            tracemalloc_peak=tracemalloc.get_traced_memory()[1],
            boardRows=n,
            iterations=50,
            lineSum=dict_sum,
        )
        tracemalloc.stop()

        tracemalloc.start()
        timer = StageTimer("feature_matrix_pack")
        fm = feature_matrix_from_records(feature_recs, as_of="2026-09-06T00:00:00Z")
        fm_rec = _stage_metrics(
            timer,
            tracemalloc_peak=tracemalloc.get_traced_memory()[1],
            boardRows=n,
            shape=list(fm.shape),
            matrixBytes=int(fm.values.nbytes),
        )
        tracemalloc.stop()

        tracemalloc.start()
        timer = StageTimer("parameter_matrix_pack")
        pm = parameter_matrix_from_snapshots(snaps)
        pm_rec = _stage_metrics(
            timer,
            tracemalloc_peak=tracemalloc.get_traced_memory()[1],
            boardRows=n,
            shape=list(pm.shape),
            matrixBytes=int(pm.values.nbytes),
        )
        tracemalloc.stop()

        # Cheap matmul / reduction as "compact matrix ops" microbench.
        tracemalloc.start()
        timer = StageTimer("feature_matrix_row_means")
        means = np.nanmean(fm.values, axis=1)
        matmul = _stage_metrics(
            timer,
            tracemalloc_peak=tracemalloc.get_traced_memory()[1],
            boardRows=n,
            finiteMeans=int(np.isfinite(means).sum()),
        )
        tracemalloc.stop()

        speedup = None
        if soa["WallSeconds"] > 0 and dict_rec["WallSeconds"] > 0:
            speedup = dict_rec["WallSeconds"] / soa["WallSeconds"]

        results.append(
            {
                "stageGroup": "CompactMatrix",
                "boardRows": n,
                "fromRows": from_rows,
                "soaLineSum": soa,
                "dictLineSum": dict_rec,
                "soaVsDictSpeedup": speedup,
                "featureMatrix": fm_rec,
                "parameterMatrix": pm_rec,
                "featureRowMeans": matmul,
                "outputHash": content_hash(
                    {
                        "lineSum": soa_sum,
                        "fmShape": list(fm.shape),
                        "pmShape": list(pm.shape),
                        "meanHead": [float(x) for x in means[:8] if np.isfinite(x)],
                    }
                ),
                "hostPerformanceCertified": False,
            }
        )
    return results


def profile_event_world(world_sizes: list[int], *, players: int = 8) -> list[dict[str, Any]]:
    specs = _cfb_team_specs(players)
    results: list[dict[str, Any]] = []
    for n in world_sizes:
        gc.collect()
        tracemalloc.start()
        timer = StageTimer("cfb_event_world_joint")
        out = simulate_joint_cfb_event_worlds(specs, n=n, seed="baseline-profile-20260906")
        peak = tracemalloc.get_traced_memory()[1]
        # Deterministic fingerprint of first player's first few worlds.
        first_pid = specs[0]["row"]["playerId"]
        sample = out["worlds"][first_pid][: min(8, n)]
        digest = content_hash({"meta": out["meta"], "sample": sample, "n": n, "players": players})
        rec = _stage_metrics(
            timer,
            tracemalloc_peak=peak,
            worldCount=n,
            playerCount=players,
            inputRows=players,
            outputRows=n * players,
            conservationFailures=out["meta"].get("conservationFailures"),
            allocationMode=out["meta"].get("allocationMode"),
        )
        wall = float(rec["WallSeconds"])
        rec["worldsPerWallSecond"] = (n / wall) if wall > 0 else None
        rec["playerWorldsPerWallSecond"] = ((n * players) / wall) if wall > 0 else None
        tracemalloc.stop()
        results.append(
            {
                "stageGroup": "CFBEventWorld",
                "worldCount": n,
                "playerCount": players,
                "timing": rec,
                "outputHash": digest,
                "hostPerformanceCertified": False,
            }
        )
    return results


def profile_cache_and_dag() -> dict[str, Any]:
    """Exercise LRU + Dag reuse/invalidation counters (synthetic graph)."""
    cache = LRUCache(64)
    for i in range(200):
        cache.put(f"k{i % 80}", {"i": i})
    for i in range(120):
        cache.get(f"k{i % 90}")

    dag = Dag(cutoff="2026-09-06T00:00:00Z", config_hash="baseline", schema_version="v1", source_versions={"bench": "1"})
    roots = []
    for i in range(40):
        node = dag.add("FEATURE", f"f{i}")
        roots.append(node.key)
        dag.complete(node.key, content_hash({"f": i}))
    params = []
    for i in range(40):
        node = dag.add("PARAMETER", f"p{i}", parents=[roots[i]])
        params.append(node.key)
        dag.complete(node.key, content_hash({"p": i}))
    worlds = []
    for i in range(40):
        node = dag.add("EVENT_WORLDS", f"w{i}", parents=[params[i]])
        worlds.append(node.key)
        dag.complete(node.key, content_hash({"w": i}))
    reused_before = dag.reused()
    invalidated = dag.invalidate([params[0], params[1]], include_roots=True)
    reused_after = dag.reused()
    return {
        "stageGroup": "CacheAndDag",
        "cacheHits": cache.hits,
        "cacheMisses": cache.misses,
        "reusedNodesBefore": reused_before,
        "reusedNodesAfter": reused_after,
        "invalidatedNodes": len(invalidated),
        "invalidatedKeysHead": invalidated[:16],
        "pendingAfter": len(dag.pending()),
        "hostPerformanceCertified": False,
    }


def identify_hotspots(
    board: list[dict[str, Any]],
    compact: list[dict[str, Any]],
    worlds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    # Prefer largest measured EventWorld wall time.
    if worlds:
        worst = max(worlds, key=lambda r: float(r["timing"]["WallSeconds"]))
        t = worst["timing"]
        candidates.append(
            {
                "rank": 0,
                "id": "CFB_EVENTWORLD_JOINT_SAMPLE",
                "evidence": (
                    f"simulate_joint_cfb_event_worlds players={worst['playerCount']} "
                    f"worlds={worst['worldCount']}: wall={t['WallSeconds']:.4f}s "
                    f"cpu={t['CPUSeconds']:.4f}s "
                    f"({t.get('worldsPerWallSecond') or 0:.1f} worlds/s)"
                ),
                "recommendation": (
                    "Phase 11: NumPy-vectorize team play / residual allocation and "
                    "per-player sample_football draws first; C ABI challenger only after "
                    "a measured NumPy win on the same synthetic matrix."
                ),
                "wallSeconds": t["WallSeconds"],
                "module": "dcm.cfb.event_worlds.simulate_joint_cfb_event_worlds",
            }
        )

    if board:
        worst_b = max(board, key=lambda r: float(r["build"]["WallSeconds"]))
        candidates.append(
            {
                "rank": 0,
                "id": "BOARDSTORE_BUILD_INDEXES",
                "evidence": (
                    f"BoardStore build n={worst_b['boardRows']}: "
                    f"wall={worst_b['build']['WallSeconds']:.4f}s "
                    f"cpu={worst_b['build']['CPUSeconds']:.4f}s "
                    f"sqliteBytes={worst_b['sqliteBytes']}"
                ),
                "recommendation": (
                    "Keep SoA posting lists; avoid reintroducing per-row JSON payload. "
                    "Further accel only if representative CFB boards (>4k offers) show "
                    "build dominating end-to-end wall."
                ),
                "wallSeconds": worst_b["build"]["WallSeconds"],
                "module": "dcm.board_store.BoardStore",
            }
        )

    if compact:
        worst_c = max(compact, key=lambda r: float(r["fromRows"]["WallSeconds"]))
        # Also flag dict vs SoA if dict is slower (expected).
        soa = worst_c["soaLineSum"]["WallSeconds"]
        dct = worst_c["dictLineSum"]["WallSeconds"]
        candidates.append(
            {
                "rank": 0,
                "id": "COMPACT_MATRIX_PACK_AND_REDUCE",
                "evidence": (
                    f"CompactNumericBoard.from_board_rows n={worst_c['boardRows']}: "
                    f"wall={worst_c['fromRows']['WallSeconds']:.4f}s; "
                    f"line_sum SoA={soa:.6f}s vs dict={dct:.6f}s "
                    f"(speedup={worst_c.get('soaVsDictSpeedup')})"
                ),
                "recommendation": (
                    "Prefer CompactNumericBoard / FeatureMatrix on numerical hot paths; "
                    "audit boundary conversion only at I/O edges."
                ),
                "wallSeconds": worst_c["fromRows"]["WallSeconds"],
                "module": "dcm.compact",
            }
        )

    candidates.sort(key=lambda c: float(c["wallSeconds"]), reverse=True)
    for i, c in enumerate(candidates[:3], start=1):
        c["rank"] = i
    return candidates[:3]


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# DCM Phase 9 baseline profile")
    lines.append("")
    lines.append(f"- Schema: `{report['schema']}`")
    lines.append(f"- Captured (UTC): `{report['capturedAtUtc']}`")
    lines.append(f"- Host: `{report['host']['platform']}` / Python `{report['host']['python']}`")
    lines.append(f"- `hostPerformanceCertified`: **{report['hostPerformanceCertified']}**")
    lines.append(f"- Certification blocker: `{report['certificationBlocker']}`")
    lines.append("")
    lines.append("## Reproducible command")
    lines.append("")
    lines.append("```bash")
    lines.append(report["reproducibleCommand"])
    lines.append("```")
    lines.append("")
    lines.append("## BoardStore build + query")
    lines.append("")
    lines.append("| offers | build wall s | build CPU s | peak RSS B | query wall s | sqlite B | outputHash |")
    lines.append("|---:|---:|---:|---:|---:|---:|---|")
    for r in report["boardStore"]:
        b, q = r["build"], r["query"]
        lines.append(
            f"| {r['boardRows']} | {b['WallSeconds']:.4f} | {b['CPUSeconds']:.4f} | "
            f"{b['PeakRSSBytesObserved']} | {q['WallSeconds']:.4f} | {r['sqliteBytes']} | "
            f"`{r['outputHash'][:12]}…` |"
        )
    lines.append("")
    lines.append("## Compact matrix ops")
    lines.append("")
    lines.append("| offers | from_rows wall s | SoA line_sum s | dict line_sum s | speedup | FM pack s | PM pack s |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    for r in report["compact"]:
        lines.append(
            f"| {r['boardRows']} | {r['fromRows']['WallSeconds']:.4f} | "
            f"{r['soaLineSum']['WallSeconds']:.6f} | {r['dictLineSum']['WallSeconds']:.6f} | "
            f"{r.get('soaVsDictSpeedup')} | {r['featureMatrix']['WallSeconds']:.4f} | "
            f"{r['parameterMatrix']['WallSeconds']:.4f} |"
        )
    lines.append("")
    lines.append("## CFB EventWorld / distribution path")
    lines.append("")
    lines.append("| worlds | players | wall s | CPU s | worlds/s | peak RSS B | outputHash |")
    lines.append("|---:|---:|---:|---:|---:|---:|---|")
    for r in report["eventWorld"]:
        t = r["timing"]
        lines.append(
            f"| {r['worldCount']} | {r['playerCount']} | {t['WallSeconds']:.4f} | "
            f"{t['CPUSeconds']:.4f} | {t.get('worldsPerWallSecond')} | "
            f"{t['PeakRSSBytesObserved']} | `{r['outputHash'][:12]}…` |"
        )
    lines.append("")
    lines.append("## Cache / DAG counters (synthetic)")
    lines.append("")
    c = report["cacheAndDag"]
    lines.append(
        f"- LRU hits={c['cacheHits']} misses={c['cacheMisses']}; "
        f"reusedNodes {c['reusedNodesBefore']}→{c['reusedNodesAfter']}; "
        f"invalidated={c['invalidatedNodes']}"
    )
    lines.append("")
    lines.append("## Top hotspots for Phase 11 EventWorld accel")
    lines.append("")
    for h in report["hotspots"]:
        lines.append(f"### {h['rank']}. `{h['id']}`")
        lines.append("")
        lines.append(f"- Module: `{h['module']}`")
        lines.append(f"- Evidence: {h['evidence']}")
        lines.append(f"- Recommendation: {h['recommendation']}")
        lines.append("")
    if report.get("skippedSizes"):
        lines.append("## Skipped sizes")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(report["skippedSizes"], indent=2))
        lines.append("```")
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Synthetic/sanitized loads only — not production certification.")
    lines.append("- No HAR bytes committed. No C++ / native extension in this phase.")
    lines.append("- Deterministic `outputHash` values use `content_hash` over stage fingerprints.")
    lines.append("")
    return "\n".join(lines)


def build_report(
    *,
    board_sizes: list[int],
    world_sizes: list[int],
    players: int,
    out_dir: Path,
    command: str,
) -> dict[str, Any]:
    board_kept, board_skip = _safe_board_sizes(board_sizes)
    world_kept, world_skip = _safe_world_sizes(world_sizes, players=players)

    board = profile_board_store(board_kept)
    compact = profile_compact_ops(board_kept)
    worlds = profile_event_world(world_kept, players=players)
    cache = profile_cache_and_dag()
    hotspots = identify_hotspots(board, compact, worlds)

    avail = _available_ram_bytes()
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "capturedAtUtc": _utc_now(),
        "hostPerformanceCertified": False,
        "certificationEligible": False,
        "certificationBlocker": "SYNTHETIC_BASELINE_NOT_PRODUCTION_CERTIFICATION",
        "engineeringFixtureOnly": True,
        "reproducibleCommand": command,
        "host": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "cpuCount": os.cpu_count(),
            "memAvailableBytes": avail,
            "peakRssBytesObserved": _peak_rss_bytes(),
        },
        "requestedBoardSizes": board_sizes,
        "requestedWorldSizes": world_sizes,
        "boardSizes": board_kept,
        "worldSizes": world_kept,
        "eventWorldPlayers": players,
        "skippedSizes": {"board": board_skip, "world": world_skip},
        "boardStore": board,
        "compact": compact,
        "eventWorld": worlds,
        "cacheAndDag": cache,
        "hotspots": hotspots,
        "bytesReadWrite": {
            "note": "Synthetic in-process only; no production HAR I/O in this harness.",
            "boardInputBytesApprox": [
                {"boardRows": r["boardRows"], "inputBytes": r["build"].get("inputBytes")} for r in board
            ],
        },
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DCM Phase 9 baseline profiler (synthetic)")
    parser.add_argument("--board-sizes", type=int, nargs="+", default=[100, 1000, 4000])
    parser.add_argument("--world-sizes", type=int, nargs="+", default=[64, 128, 512, 2048])
    parser.add_argument("--players", type=int, default=8)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "benchmarks")
    parser.add_argument("--tag", type=str, default="20260906")
    parser.add_argument("--smoke", action="store_true", help="Tiny sizes for CI/harness smoke")
    args = parser.parse_args(argv)

    if args.smoke:
        args.board_sizes = [100]
        args.world_sizes = [64]
        args.players = 4

    if any(x <= 0 for x in args.board_sizes + args.world_sizes) or args.players <= 0:
        raise SystemExit("sizes and players must be positive")

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = (
        "python benchmarks/baseline/profile_baseline.py "
        f"--board-sizes {' '.join(str(x) for x in args.board_sizes)} "
        f"--world-sizes {' '.join(str(x) for x in args.world_sizes)} "
        f"--players {args.players} "
        f"--out {out_dir.as_posix()}"
    )
    if args.smoke:
        cmd += " --smoke"

    report = build_report(
        board_sizes=list(args.board_sizes),
        world_sizes=list(args.world_sizes),
        players=int(args.players),
        out_dir=out_dir,
        command=cmd,
    )
    assert report["hostPerformanceCertified"] is False

    stem = f"baseline_profile_{args.tag}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    summary = {
        "ok": True,
        "hostPerformanceCertified": False,
        "json": str(json_path),
        "markdown": str(md_path),
        "boardSizes": report["boardSizes"],
        "worldSizes": report["worldSizes"],
        "hotspotIds": [h["id"] for h in report["hotspots"]],
        "topHotspotWallSeconds": report["hotspots"][0]["wallSeconds"] if report["hotspots"] else None,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
