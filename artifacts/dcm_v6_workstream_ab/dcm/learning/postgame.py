"""Postgame settlement/audit lifecycle for immutable DCM forecasts.

Model settlement is distinct from PrizePicks lineup economics. Frozen pregame
forecasts are never mutated; postgame outputs are sidecars and future-only
challengers. LR never advances automatically from one result.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.learning.calibration import build_challenger_cells, cell_key
from dcm.learning.sidecar import append_record
from dcm.runtime.freeze import compute_forecast_hash
from dcm.runtime.store import IndexedStore


def _population(run_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (run_dir / "full_population.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def _outcomes(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("outcomes") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("OUTCOMES_MUST_BE_LIST")
    return {str(r["projectionId"]): r for r in rows if isinstance(r, dict) and r.get("projectionId")}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_frozen_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    freeze = json.loads((run_dir / "frozen_forecast.json").read_text(encoding="utf-8"))
    integrity = json.loads((run_dir / "run_integrity.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    population = _population(run_dir)
    strict_card = json.loads((run_dir / "strict_card.json").read_text(encoding="utf-8"))
    top25_ranked = json.loads((run_dir / "top25_ranked.json").read_text(encoding="utf-8"))
    hash_sidecar = (run_dir / "frozen_forecast.sha256").read_text(encoding="utf-8").strip()

    recomputed = compute_forecast_hash(freeze, population, strict_card, top25_ranked)
    declared = str(freeze.get("frozenForecastHash") or "")
    if not declared or recomputed != declared:
        raise RuntimeError("FROZEN_FORECAST_SEMANTIC_HASH_MISMATCH")
    if hash_sidecar != declared:
        raise RuntimeError("FROZEN_FORECAST_SIDECAR_HASH_MISMATCH")
    if str(integrity.get("frozenForecastHash") or "") != declared:
        raise RuntimeError("RUN_INTEGRITY_FORECAST_HASH_MISMATCH")
    if str(checkpoint.get("frozenForecastHash") or "") != declared:
        raise RuntimeError("CHECKPOINT_FORECAST_HASH_MISMATCH")
    if str(integrity.get("runId") or "") != str(freeze.get("runId") or ""):
        raise RuntimeError("RUN_ID_MISMATCH")
    for field in (
        "forecastCutoff", "boardHash", "harSha256", "modelConfigHash",
        "calibrationStateHash", "learningRevision",
    ):
        if integrity.get(field) != freeze.get(field):
            raise RuntimeError(f"RUN_INTEGRITY_{field.upper()}_MISMATCH")
    return freeze, integrity, population


def _result(value: float, line: float, side: str) -> str:
    if abs(value - line) < 1e-9:
        return "PUSH"
    if side == "MORE":
        return "WIN" if value > line else "LOSS"
    return "WIN" if value < line else "LOSS"


def settle_run(run_dir: Path, outcomes_path: Path) -> dict[str, Any]:
    freeze, integrity, population = _verify_frozen_run(run_dir)
    outcomes_sha256 = _sha256_file(outcomes_path)
    outcomes = _outcomes(outcomes_path)
    settlements: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    for p in population:
        pid = str(p.get("projectionId") or "")
        if not pid or p.get("state") != "MODELED" or p.get("direction") not in {"MORE", "LESS"}:
            continue
        out = outcomes.get(pid)
        if out is None:
            settlements.append({"projectionId": pid, "settlement": "UNRESOLVED", "reason": "OUTCOME_MISSING"})
            continue
        admin = str(out.get("administrativeState") or "ACTIVE").upper()
        if admin == "REBOOT":
            settlements.append({
                "projectionId": pid,
                "settlement": "UNRESOLVED",
                "binaryOutcome": None,
                "reason": "PLATFORM_REBOOT_REQUIRES_ENTRY_CONTRACT_AND_PARTICIPATION_FACTS",
                "platformSettlementState": "NOT_COMPUTED",
                "outcomesSha256": outcomes_sha256,
            })
            continue
        if admin in {"DNP", "CANCELLED", "VOID", "INACTIVE"}:
            settlements.append({
                "projectionId": pid,
                "settlement": admin,
                "binaryOutcome": None,
                "platformSettlementState": "NOT_COMPUTED",
                "outcomesSha256": outcomes_sha256,
            })
            continue
        try:
            value = float(out["officialStatValue"])
            line = float(p["line"])
        except (KeyError, TypeError, ValueError):
            settlements.append({"projectionId": pid, "settlement": "UNRESOLVED", "reason": "OFFICIAL_VALUE_INVALID"})
            continue

        result = _result(value, line, str(p["direction"]))
        binary = 1 if result == "WIN" else 0 if result == "LOSS" else None
        forecast_p = float(p.get("evidenceSafeP") or p.get("selectedP") or 0.5)
        rec = {
            "projectionId": pid, "player": p.get("player"), "market": p.get("market"),
            "line": line, "direction": p.get("direction"), "officialStatValue": value,
            "settlement": result, "binaryOutcome": binary, "forecastP": forecast_p,
            "sportingSettlement": result,
            "platformSettlementState": "NOT_COMPUTED_WITHOUT_ENTRY_CONTRACT",
            "outcomesSha256": outcomes_sha256,
            "calibrationKey": cell_key(str(p.get("sportFamily") or ""), str(p.get("league") or ""),
                                       str(p.get("market") or ""), str(p.get("direction") or "")),
        }
        if binary is not None:
            rec["brier"] = (forecast_p - binary) ** 2
            rec["logLoss"] = -(binary * math.log(max(1e-12, forecast_p))
                               + (1 - binary) * math.log(max(1e-12, 1.0 - forecast_p)))
        settlements.append(rec)

        if result == "LOSS":
            lower = float(p.get("lowerBound") or 0.0)
            mechanism = "NORMAL_VARIANCE_OR_UNRESOLVED_MECHANISM"
            model_error = lower >= 0.55
            actual_opp = out.get("actualOpportunity")
            expected_opp = p.get("opportunityMean")
            if actual_opp is not None and expected_opp not in {None, 0}:
                ratio = float(actual_opp) / max(1e-9, float(expected_opp))
                if ratio < 0.75 or ratio > 1.25:
                    mechanism = "OPPORTUNITY_ERROR_CANDIDATE"
                    model_error = True
            audit = {
                "projectionId": pid, "result": result, "mechanism": mechanism,
                "modelErrorCandidate": model_error, "normalVarianceStillPlausible": not model_error,
                "frozenForecastHash": freeze["frozenForecastHash"],
            }
            audits.append(audit)
            if model_error:
                proposal = {
                    "projectionId": pid, "mechanism": mechanism,
                    "proposal": "REGISTER_SHADOW_CHALLENGER_ONLY",
                    "effective": "FUTURE_SLATES_ONLY", "productionChange": False,
                }
                proposal["proposalHash"] = content_hash(proposal)
                proposals.append(proposal)

    calibration = build_challenger_cells(settlements)
    summary = {
        "runId": freeze["runId"], "frozenForecastHash": freeze["frozenForecastHash"],
        "settled": sum(s.get("settlement") in {"WIN", "LOSS", "PUSH"} for s in settlements),
        "wins": sum(s.get("settlement") == "WIN" for s in settlements),
        "losses": sum(s.get("settlement") == "LOSS" for s in settlements),
        "pushes": sum(s.get("settlement") == "PUSH" for s in settlements),
        "unresolved": sum(s.get("settlement") == "UNRESOLVED" for s in settlements),
        "learningRevisionBefore": integrity.get("learningRevision", "LR000000"),
        "learningRevisionAfter": integrity.get("learningRevision", "LR000000"),
        "lrPromoted": False, "calibrationPromotion": "NOT_AUTOMATIC", "predictiveClaim": "NONE",
        "outcomesSha256": outcomes_sha256,
        "frozenRunVerified": True,
        "platformSettlementComputed": False,
        "platformSettlementReason": "ENTRY_CONTRACT_AND_PARTICIPATION_FACTS_REQUIRED",
    }
    for name, data in (
        ("settlement.json", settlements), ("audit.json", audits),
        ("calibration_challenger.json", calibration), ("patch_proposals.json", proposals),
        ("postgame_summary.json", summary),
    ):
        (run_dir / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    store = IndexedStore(run_dir / "index.sqlite")
    cutoff = str(integrity.get("forecastCutoff") or "")
    run_id = str(integrity.get("runId") or freeze["runId"])
    lr = str(integrity.get("learningRevision") or "LR000000")
    append_record(store, "Settlement", cutoff, run_id, lr, {"summary": summary, "rows": settlements}, source_hash=freeze["frozenForecastHash"])
    append_record(store, "Audit", cutoff, run_id, lr, {"rows": audits}, source_hash=freeze["frozenForecastHash"])
    for proposal in proposals:
        append_record(store, "PatchProposal", cutoff, run_id, lr, proposal, source_hash=freeze["frozenForecastHash"])
    store.close()
    return {"summary": summary, "settlements": settlements, "audits": audits,
            "calibration": calibration, "patchProposals": proposals}
