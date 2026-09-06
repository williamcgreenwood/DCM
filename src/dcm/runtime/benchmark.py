"""Reproducible engineering throughput benchmark for DCM boards.

This harness deliberately uses synthetic board data + fixture evidence and can
never set hostPerformanceCertified=true. Production certification requires a
representative real-evidence workload on the intended host with explicit SLOs.
"""
from __future__ import annotations

import argparse
import json
import resource
import tempfile
import time
from pathlib import Path
from typing import Any

from dcm.runner import run_dcm


def _row(i: int) -> dict[str, Any]:
    basketball = i % 2 == 0
    if basketball:
        return {
            "projectionId": f"NBA_{i}",
            "sportFamily": "basketball",
            "league": "NBA",
            "eventId": f"NBA_E_{i // 20}",
            "eventLabel": f"NBA Event {i // 20}",
            "playerId": f"NBA_P_{i}",
            "playerName": f"NBA Player {i}",
            "teamId": f"N{(i // 10) % 30:02d}",
            "team": f"N{(i // 10) % 30:02d}",
            "opponent": f"N{((i // 10) + 1) % 30:02d}",
            "market": "pts",
            "marketLabel": "Points",
            "line": 20.5 + (i % 10),
            "side": "UNKNOWN",
            "offeredHigher": True,
            "offeredLower": True,
            "modifier": "STANDARD",
            "boardId": "FULL_GAME",
            "productType": "PLAYER_PICKS",
            "role": "G",
        }
    return {
        "projectionId": f"NFL_{i}",
        "sportFamily": "gridiron",
        "league": "NFL",
        "eventId": f"NFL_E_{i // 20}",
        "eventLabel": f"NFL Event {i // 20}",
        "playerId": f"NFL_P_{i}",
        "playerName": f"NFL Player {i}",
        "teamId": f"F{(i // 10) % 32:02d}",
        "team": f"F{(i // 10) % 32:02d}",
        "opponent": f"F{((i // 10) + 1) % 32:02d}",
        "market": "pass_yds",
        "marketLabel": "Passing Yards",
        "line": 225.5 + (i % 20),
        "side": "UNKNOWN",
        "offeredHigher": True,
        "offeredLower": True,
        "modifier": "STANDARD",
        "boardId": "FULL_GAME",
        "productType": "PLAYER_PICKS",
        "role": "QB",
    }


def _har(n: int) -> dict[str, Any]:
    return {
        "_pillars": {"kind": "BENCHMARK_HAR", "synthetic": True},
        "log": {
            "version": "1.2",
            "creator": {"name": "dcm-benchmark", "version": "1"},
            "entries": [
                {
                    "startedDateTime": "2026-08-29T00:00:00Z",
                    "request": {
                        "method": "GET",
                        "url": "https://api.prizepicks.com/projections?page=1&benchmark=1",
                        "headers": [],
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({"data": [_row(i) for i in range(n)]}),
                        },
                    },
                }
            ],
        },
    }


def benchmark_board(n: int, *, output_root: Path, workspace: Path) -> dict[str, Any]:
    input_path = output_root / f"benchmark_{n}.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(json.dumps(_har(n)), encoding="utf-8")
    t0 = time.perf_counter()
    cpu0 = time.process_time()
    result = run_dcm(
        input_path=input_path,
        forecast_cutoff="2026-08-29T00:00:00Z",
        output_root=output_root / "runs",
        research="fixture",
        workspace=workspace,
    )
    wall = time.perf_counter() - t0
    cpu = time.process_time() - cpu0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "boardRows": n,
        "wallSeconds": wall,
        "cpuSeconds": cpu,
        "rowsPerWallSecond": n / wall if wall > 0 else None,
        "peakRSSBytesObserved": int(rss) * 1024,
        "runState": result["runState"],
        "modeled": int((result.get("integrity") or {}).get("modeled") or 0),
        "engineeringFixtureOnly": True,
        "hostPerformanceCertified": False,
        "certificationEligible": False,
        "certificationBlocker": "SYNTHETIC_FIXTURE_WORKLOAD_NOT_PRODUCTION_CERTIFICATION",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DCM synthetic throughput benchmark")
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 500, 1000, 2500, 5000])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if any(size <= 0 for size in args.sizes):
        raise SystemExit("all benchmark sizes must be positive")
    if args.out is None:
        temp = tempfile.TemporaryDirectory(prefix="dcm_benchmark_")
        root = Path(temp.name)
    else:
        temp = None
        root = args.out
    workspace = root / "workspace"
    results = [benchmark_board(size, output_root=root, workspace=workspace) for size in args.sizes]
    report = {
        "benchmarkType": "ENGINEERING_SYNTHETIC_THROUGHPUT",
        "hostPerformanceCertified": False,
        "results": results,
    }
    (root / "benchmark_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    if temp is not None:
        temp.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
