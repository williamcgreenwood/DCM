"""One command: mount gate + HAR ingest + board.json freeze + WSAB bind.

Does not promote LR. Does not claim optimized DCM 6.0.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dcm.contracts.hashes import content_hash
from dcm.ingest.board import freeze_board, write_board
from dcm.ingest.har import ingest_har
from dcm.runtime.cutoff import CutoffRequired, derive_cutoff_from_capture
from dcm.runtime.mount_v541 import mount_default
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE

ARTIFACT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = Path(__file__).resolve().parents[4]
SYNTHETIC_FIXTURE = ARTIFACT_ROOT / "fixtures" / "synthetic_har.json"


def _run_id(har_sha256: str, cutoff: str) -> str:
    return "RUN_" + content_hash({"har": har_sha256, "cutoff": cutoff})[:16]


def run_har(*, inbox: Path | None, out_root: Path, synthetic: bool, cutoff: str | None, workspace: Path, cutoff_from_capture: bool = False) -> dict:
    mount = mount_default(workspace)
    if synthetic:
        raw = json.loads(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))
        raw_bytes = SYNTHETIC_FIXTURE.read_bytes()
    else:
        if inbox is None or not inbox.is_file():
            raise FileNotFoundError("INBOX HAR missing. Pass --inbox or --synthetic.")
        raw_bytes = inbox.read_bytes()
        raw = raw_bytes
    ingest = ingest_har(raw, raw_bytes=raw_bytes)
    if not cutoff:
        if not cutoff_from_capture:
            raise CutoffRequired("FORECAST_CUTOFF_REQUIRED: pass --cutoff or --cutoff-from-capture")
        cutoff = derive_cutoff_from_capture(ingest)
    board = freeze_board(ingest, mount=mount, cutoff=cutoff)
    run_id = _run_id(ingest["harSha256"], cutoff)
    dest = out_root / run_id
    dest.mkdir(parents=True, exist_ok=True)
    write_board(board, dest / "board.json")
    integrity = {
        "runId": run_id,
        "software": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "v5MountState": mount.get("state"),
        "v5Decoder": mount.get("har_decoder"),
        "harSha256": ingest["harSha256"],
        "sourceAdapter": ingest["adapter"],
        "parserVersion": ingest["parserVersion"],
        "boardHash": board["contentHash"],
        "rawRows": board["accounting"]["raw_projection_rows"],
        "goblinRows": board["accounting"]["goblin_rows"],
        "wsabBoundRows": board["accounting"]["wsab_bound_rows"],
        "boardComplete": board["accounting"]["raw_projection_rows"] > 0,
        "lifecycle": "INTEGRATED_DEVELOPMENT",
        "optimizedDcm60Claim": False,
        "createdAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (dest / "integrity.json").write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "accounting.json").write_text(json.dumps(board["accounting"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "MOUNT_STATE.json").write_text(json.dumps(mount, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"run_id": run_id, "dest": str(dest), "integrity": integrity, "board": board, "mount": mount}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="DCM v6 HAR → board.json (LR000000, no v5 mutation)")
    p.add_argument("--inbox", type=Path, default=DEFAULT_WORKSPACE / "dcm_v6" / "INBOX" / "current.har")
    p.add_argument("--out", type=Path, default=DEFAULT_WORKSPACE / "dcm_v6" / "RUNS")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--cutoff", default=None, help="RFC3339 forecast cutoff. Required unless --cutoff-from-capture.")
    p.add_argument("--cutoff-from-capture", action="store_true")
    p.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    args = p.parse_args(argv)
    try:
        result = run_har(
            inbox=None if args.synthetic else args.inbox,
            out_root=args.out,
            synthetic=args.synthetic,
            cutoff=args.cutoff,
            workspace=args.workspace,
            cutoff_from_capture=args.cutoff_from_capture,
        )
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    except CutoffRequired as e:
        print(str(e), file=sys.stderr)
        return 2
    integ = result["integrity"]
    print(json.dumps({
        "runId": integ["runId"],
        "adapter": integ["sourceAdapter"],
        "harSha256": integ["harSha256"],
        "rawRows": integ["rawRows"],
        "goblinRows": integ["goblinRows"],
        "wsabBoundRows": integ["wsabBoundRows"],
        "v5MountState": integ["v5MountState"],
        "learningRevision": integ["learningRevision"],
        "predictiveClaim": integ["predictiveClaim"],
        "dest": result["dest"],
    }, indent=2))
    return 0 if integ["boardComplete"] else 3


if __name__ == "__main__":
    sys.exit(main())
