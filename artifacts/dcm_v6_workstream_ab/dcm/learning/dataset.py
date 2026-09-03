"""Training-dataset builder from settled DCM runs. Never invents settlements.

python -m dcm.learning.dataset --dest RUNS/<id> [--out path]
python -m dcm.dataset --dest RUNS/<id> [--out path]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from dcm.contracts.hashes import content_hash
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE

SCHEMA_VERSION = "dcm.training_dataset.v1-20260830"
SCHEMA_ID = "pillars_dcm.training_dataset.v1"
MANIFEST_SCHEMA = "pillars_dcm.training_dataset_manifest.v1"

SUPERVISED_RESULTS = frozenset({"WIN", "LOSS", "PUSH"})
AUDIT_RESULTS = frozenset(
    {"VOID", "DNP", "UNKNOWN", "UNKNOWN_PLATFORM_RULE", "REBOOT", "CANCELLED"}
)
SLIM_FIELDS = (
    "projectionId",
    "player",
    "team",
    "opponent",
    "event",
    "market",
    "line",
    "direction",
    "modifier",
    "grade",
    "state",
    "selectedP",
    "rawP",
    "calibratedP",
    "evidenceSafeP",
    "pHigher",
    "pLower",
    "pPush",
    "lowerBound",
    "reliability",
    "dataQuality",
    "volatility",
    "fragility",
    "oodRisk",
    "falseSignRisk",
    "opportunityMean",
    "parameterSnapshotHash",
    "calibrationState",
    "selectionScore",
    "sportFamily",
    "league",
    "blocker",
)

class SettlementsMissing(RuntimeError):
    """Run dest has no settlements sidecar; builder will not invent labels."""

def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows

def _index_by_pid(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = str(row.get("projectionId") or "")
        if pid and pid not in out:
            out[pid] = row
    return out

def _settlements(run_dir: Path) -> list[dict[str, Any]]:
    jsonl = _load_jsonl(run_dir / "settlements.jsonl")
    if jsonl:
        return jsonl
    data = _load_json(run_dir / "settlement.json")
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []

def _population(run_dir: Path) -> dict[str, dict[str, Any]]:
    for name in ("full_population.jsonl", "population_full.jsonl"):
        rows = _load_jsonl(run_dir / name)
        if rows:
            return _index_by_pid(rows)
    return {}

def _event_starts(run_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    board = _load_json(run_dir / "board.json")
    rows: list[Any] = []
    if isinstance(board, dict):
        raw = board.get("rows") or board.get("projections") or board.get("board") or []
        if isinstance(raw, list):
            rows = raw
    elif isinstance(board, list):
        rows = board
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("projectionId") or "")
        start = str(row.get("eventStartTime") or row.get("eventStart") or row.get("startTime") or "")
        if pid and start:
            out[pid] = start
    pos = _load_json(run_dir / "player_offer_sets.json")
    if isinstance(pos, dict):
        pos = pos.get("sets") or pos.get("playerOfferSets") or pos.get("rows") or []
    if not isinstance(pos, list):
        pos = []
    for rec in pos:
        if not isinstance(rec, dict):
            continue
        start = str(rec.get("eventStartTime") or rec.get("eventStart") or "")
        if not start:
            continue
        for offer in rec.get("offers") or []:
            if isinstance(offer, dict):
                pid = str(offer.get("projectionId") or "")
                if pid and pid not in out:
                    out[pid] = start
    return out

def _feature_hashes(run_dir: Path) -> tuple[dict[str, list[str]], str]:
    by_pid: dict[str, list[str]] = {}
    for rec in _load_jsonl(run_dir / "prop_explanations.jsonl"):
        pid = str(rec.get("projectionId") or "")
        hashes = [str(h) for h in (rec.get("featureHashes") or []) if h]
        if pid and hashes:
            by_pid[pid] = hashes
    manifest = _load_json(run_dir / "feature_store_manifest.json")
    schema_hash = ""
    if isinstance(manifest, dict):
        schema_hash = str(manifest.get("contentHash") or manifest.get("featureSchemaHash") or "")
    return by_pid, schema_hash

def _decision_cutoff(freeze: dict[str, Any]) -> str:
    binds = freeze.get("freezeBinds") if isinstance(freeze.get("freezeBinds"), dict) else {}
    return str(
        freeze.get("forecastDecisionCutoff")
        or binds.get("forecastDecisionCutoff")
        or freeze.get("forecastCutoff")
        or freeze.get("decisionCutoff")
        or ""
    )

def _label_split(result: str) -> str | None:
    token = str(result or "").strip().upper()
    if token in {"TIE"}:
        token = "PUSH"
    if token in {"CANCELLED", "INACTIVE", "VOIDED"}:
        token = "VOID"
    if token in SUPERVISED_RESULTS:
        return "supervised"
    if token in AUDIT_RESULTS:
        return "audit"
    if not token:
        return None
    return "audit"

def build_training_row(
    settlement: dict[str, Any],
    *,
    slim: dict[str, Any] | None,
    freeze: dict[str, Any],
    feature_hashes: list[str],
    feature_schema_hash: str,
    event_start: str,
) -> dict[str, Any] | None:
    """Join freeze slim + hashes + settlement. Returns None if no real settlement."""
    result = str(settlement.get("result") or settlement.get("settlement") or "").strip().upper()
    split = _label_split(result)
    if split is None:
        return None
    slim = slim if isinstance(slim, dict) else {}
    pid = str(settlement.get("projectionId") or slim.get("projectionId") or "")
    if not pid:
        return None
    row: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "schemaId": SCHEMA_ID,
        "runId": freeze.get("runId"),
        "frozenForecastHash": freeze.get("frozenForecastHash"),
        "learningRevision": freeze.get("learningRevision") or LEARNING_REVISION,
        "predictiveClaim": freeze.get("predictiveClaim") or PREDICTIVE_CLAIM,
        "software": freeze.get("dcmVersion") or freeze.get("software") or SOFTWARE,
        "decisionCutoff": _decision_cutoff(freeze),
        "eventStart": event_start or slim.get("eventStartTime") or slim.get("eventStart") or "",
        "labelSplit": split,
        "settlement": result,
        "result": result,
        "binaryOutcome": settlement.get("binaryOutcome"),
        "featureHashes": list(feature_hashes),
        "featureSchemaHash": feature_schema_hash,
        "inventedSettlement": False,
        "trainedModel": False,
        "failureClass": settlement.get("failureClass"),
        "failureClassPermanentPatch": False,
    }
    for key in SLIM_FIELDS:
        if key in slim:
            row[key] = slim[key]
        elif key in settlement and key not in row:
            row[key] = settlement[key]
    row["projectionId"] = pid
    row["parameterSnapshotHash"] = (
        slim.get("parameterSnapshotHash")
        or settlement.get("parameterSnapshotHash")
        or row.get("parameterSnapshotHash")
    )
    if row.get("selectedP") is None:
        row["selectedP"] = settlement.get("forecastP") or slim.get("evidenceSafeP")
    return row

def build_dataset(dests: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build rows from one or more settled run dests. Never invents settlements."""
    rows: list[dict[str, Any]] = []
    source_ids: list[str] = []
    skipped = 0
    missing_files = 0
    for dest in dests:
        dest = Path(dest)
        freeze = _load_json(dest / "frozen_forecast.json")
        if not isinstance(freeze, dict):
            freeze = _load_json(dest / "run_integrity.json") or {}
        settlements = _settlements(dest)
        if not settlements:
            if not (dest / "settlements.jsonl").is_file() and not (dest / "settlement.json").is_file():
                missing_files += 1
                continue
        if not settlements:
            continue
        pop = _population(dest)
        starts = _event_starts(dest)
        feat_by_pid, schema_hash = _feature_hashes(dest)
        source_ids.append(str(freeze.get("runId") or dest.name))
        for rec in settlements:
            pid = str(rec.get("projectionId") or "")
            row = build_training_row(
                rec,
                slim=pop.get(pid) or {},
                freeze=freeze if isinstance(freeze, dict) else {},
                feature_hashes=feat_by_pid.get(pid) or [],
                feature_schema_hash=schema_hash,
                event_start=starts.get(pid) or "",
            )
            if row is None:
                skipped += 1
                continue
            rows.append(row)
    if not rows and missing_files == len(dests):
        raise SettlementsMissing(
            "SETTLEMENTS_MISSING: no settlements.jsonl (will not invent WIN/LOSS labels)"
        )
    supervised = sum(1 for r in rows if r.get("labelSplit") == "supervised")
    audit = sum(1 for r in rows if r.get("labelSplit") == "audit")
    schema_hash = content_hash(
        {"schemaVersion": SCHEMA_VERSION, "schemaId": SCHEMA_ID, "fields": list(SLIM_FIELDS)}
    )
    body = {
        "schema": MANIFEST_SCHEMA,
        "schemaVersion": SCHEMA_VERSION,
        "schemaId": SCHEMA_ID,
        "schemaHash": schema_hash,
        "rowCount": len(rows),
        "supervisedCount": supervised,
        "auditCount": audit,
        "skippedUnlabeled": skipped,
        "sourceRunIds": source_ids,
        "inventedSettlements": False,
        "trainedModel": False,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "software": SOFTWARE,
        "note": "VOID/DNP/UNKNOWN/REBOOT are audit-only; supervised labels are WIN/LOSS/PUSH from supplied settlements.",
    }
    body["contentHash"] = content_hash({"manifest": {k: v for k, v in body.items() if k != "contentHash"}, "rows": rows})
    return rows, body

def write_dataset(dests: list[Path], out: Path) -> dict[str, Any]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows, manifest = build_dataset(dests)
    jsonl = out / "training_dataset.jsonl"
    jsonl.write_text(
        "".join(json.dumps(r, sort_keys=True, ensure_ascii=True) + "\n" for r in rows),
        encoding="utf-8",
    )
    (out / "training_dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Build a chronological training JSONL from settled DCM runs. Does not invent settlements."
    )
    p.add_argument("--dest", action="append", type=Path, required=True, help="Settled run directory (repeatable)")
    p.add_argument("--out", type=Path, default=None, help="Output directory (default: first --dest)")
    args = p.parse_args(argv)
    dests = [Path(d) for d in args.dest]
    out = Path(args.out) if args.out is not None else dests[0]
    try:
        manifest = write_dataset(dests, out)
    except SettlementsMissing as exc:
        print(str(exc))
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
