"""Postgame settlement/audit lifecycle for immutable DCM forecasts.

Model settlement is distinct from PrizePicks lineup economics. Frozen pregame
forecasts are never mutated; postgame outputs are sidecars and future-only
challengers. LR never advances automatically from one result.

settle_run(dest, outcomes) settles the FULL modeled population
(full_population.jsonl or population_full.jsonl), not only the 0-6 card.
Outcomes are supplied; this module never invents results.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.learning.calibration import build_challenger_cells, cell_key
from dcm.learning.failure_class import classify_failure
from dcm.learning.sidecar import append_ledger_jsonl, append_record, mutate_forecast
from dcm.runtime.freeze import compute_forecast_hash
from dcm.runtime.store import IndexedStore

SETTLEMENT_RESULTS = frozenset(
    {"WIN", "LOSS", "PUSH", "VOID", "DNP", "REBOOT", "UNKNOWN_PLATFORM_RULE"}
)
VOID_ADMIN = frozenset({"VOID", "CANCELLED", "INACTIVE"})
BINARY_RESULTS = frozenset({"WIN", "LOSS"})


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


def _population(run_dir: Path) -> list[dict[str, Any]]:
    """Prefer the post-model slim population; fall back to the account-time dump."""
    for name in ("full_population.jsonl", "population_full.jsonl"):
        path = run_dir / name
        rows = _load_jsonl(path)
        if rows:
            return rows
    raise FileNotFoundError("POPULATION_MISSING: full_population.jsonl or population_full.jsonl")


def _modeled_rows(population: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in population:
        pid = str(row.get("projectionId") or "")
        if not pid or pid in seen:
            continue
        if str(row.get("state") or "") != "MODELED":
            continue
        seen.add(pid)
        out.append(row)
    return out


def _card_ids(run_dir: Path) -> set[str]:
    path = run_dir / "strict_card.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    rows = data if isinstance(data, list) else data.get("picks") or data.get("card") or []
    if not isinstance(rows, list):
        return set()
    return {str(r.get("projectionId") or "") for r in rows if isinstance(r, dict) and r.get("projectionId")}


def _outcomes(path: Path) -> dict[str, dict[str, Any]]:
    """Parse a synthetic/official outcome map. Never invent missing keys."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        if isinstance(data.get("outcomes"), list):
            rows = data["outcomes"]
        elif isinstance(data.get("outcomes"), dict):
            rows = []
            for pid, val in data["outcomes"].items():
                if isinstance(val, dict):
                    rec = dict(val)
                    rec.setdefault("projectionId", pid)
                    rows.append(rec)
                else:
                    rows.append({"projectionId": pid, "result": val})
        else:
            rows = []
            for pid, val in data.items():
                if pid in {"document", "schema", "runId"}:
                    continue
                if isinstance(val, dict):
                    rec = dict(val)
                    rec.setdefault("projectionId", pid)
                    rows.append(rec)
                elif isinstance(val, str):
                    rows.append({"projectionId": pid, "result": val})
    else:
        raise ValueError("OUTCOMES_MUST_BE_LIST_OR_MAP")
    for rec in rows:
        if not isinstance(rec, dict):
            continue
        pid = str(rec.get("projectionId") or "")
        if pid:
            out[pid] = rec
    return out


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
    """PrizePicks sporting compare: MORE wins above the line, LESS below, exact is PUSH."""
    if abs(value - line) < 1e-9:
        return "PUSH"
    if side == "MORE":
        return "WIN" if value > line else "LOSS"
    return "WIN" if value < line else "LOSS"


def _normalize_result(raw: Any) -> str | None:
    if raw is None:
        return None
    token = str(raw).strip().upper()
    if token in {"TIE"}:
        token = "PUSH"
    if token in {"CANCELLED", "INACTIVE", "VOIDED"}:
        token = "VOID"
    if token in SETTLEMENT_RESULTS:
        return token
    return None


def _settle_row(
    prop: dict[str, Any],
    out: dict[str, Any] | None,
    *,
    outcomes_sha256: str,
) -> dict[str, Any]:
    pid = str(prop.get("projectionId") or "")
    base = {
        "projectionId": pid,
        "player": prop.get("player"),
        "market": prop.get("market"),
        "line": prop.get("line"),
        "direction": prop.get("direction"),
        "grade": prop.get("grade"),
        "state": prop.get("state"),
        "outcomesSha256": outcomes_sha256,
        "platformSettlementState": "NOT_COMPUTED_WITHOUT_ENTRY_CONTRACT",
        "calibrationKey": cell_key(
            str(prop.get("sportFamily") or ""),
            str(prop.get("league") or ""),
            str(prop.get("market") or ""),
            str(prop.get("direction") or ""),
        ),
    }
    if out is None:
        rec = {
            **base,
            "settlement": "UNKNOWN_PLATFORM_RULE",
            "result": "UNKNOWN_PLATFORM_RULE",
            "binaryOutcome": None,
            "reason": "OUTCOME_MISSING",
        }
        return rec

    explicit = _normalize_result(
        out.get("result") or out.get("settlement") or out.get("outcome")
    )
    admin = str(out.get("administrativeState") or out.get("admin") or "").upper()
    if explicit is None and admin:
        if admin == "REBOOT":
            explicit = "REBOOT"
        elif admin == "DNP":
            explicit = "DNP"
        elif admin in VOID_ADMIN:
            explicit = "VOID"
        elif admin == "UNRESOLVED":
            explicit = "UNKNOWN_PLATFORM_RULE"

    if explicit in {"REBOOT", "DNP", "VOID", "UNKNOWN_PLATFORM_RULE"}:
        rec = {
            **base,
            "settlement": explicit,
            "result": explicit,
            "binaryOutcome": None,
            "reason": str(out.get("reason") or explicit),
            "platformSettlementState": "NOT_COMPUTED",
        }
        if explicit == "REBOOT":
            rec["reason"] = out.get("reason") or "PLATFORM_REBOOT_REQUIRES_ENTRY_CONTRACT_AND_PARTICIPATION_FACTS"
        return rec

    if explicit in {"WIN", "LOSS", "PUSH"}:
        binary = 1 if explicit == "WIN" else 0 if explicit == "LOSS" else None
        rec = {**base, "settlement": explicit, "result": explicit, "binaryOutcome": binary}
        if out.get("officialStatValue") is not None:
            rec["officialStatValue"] = out.get("officialStatValue")
        _attach_scores(rec, prop, binary)
        rec["sportingSettlement"] = explicit
        return rec

    # No explicit result: compute WIN/LOSS/PUSH only from supplied officialStatValue.
    # Missing stats are UNKNOWN_PLATFORM_RULE — never invented.
    try:
        value = float(out["officialStatValue"])
        line = float(prop["line"])
        side = str(prop.get("direction") or "")
    except (KeyError, TypeError, ValueError):
        return {
            **base,
            "settlement": "UNKNOWN_PLATFORM_RULE",
            "result": "UNKNOWN_PLATFORM_RULE",
            "binaryOutcome": None,
            "reason": "OFFICIAL_VALUE_INVALID",
        }
    if side not in {"MORE", "LESS"}:
        return {
            **base,
            "settlement": "UNKNOWN_PLATFORM_RULE",
            "result": "UNKNOWN_PLATFORM_RULE",
            "binaryOutcome": None,
            "reason": "DIRECTION_UNKNOWN",
            "officialStatValue": value,
        }
    result = _result(value, line, side)
    binary = 1 if result == "WIN" else 0 if result == "LOSS" else None
    rec = {
        **base,
        "line": line,
        "officialStatValue": value,
        "settlement": result,
        "result": result,
        "binaryOutcome": binary,
        "sportingSettlement": result,
    }
    _attach_scores(rec, prop, binary)
    return rec


def _attach_scores(rec: dict[str, Any], prop: dict[str, Any], binary: int | None) -> None:
    forecast_p = float(prop.get("evidenceSafeP") or prop.get("selectedP") or 0.5)
    rec["forecastP"] = forecast_p
    if binary is not None:
        rec["brier"] = (forecast_p - binary) ** 2
        rec["logLoss"] = -(
            binary * math.log(max(1e-12, forecast_p))
            + (1 - binary) * math.log(max(1e-12, 1.0 - forecast_p))
        )


def _summarize(freeze: dict[str, Any], integrity: dict[str, Any], settlements: list[dict[str, Any]], outcomes_sha256: str) -> dict[str, Any]:
    by_result = Counter(str(s.get("result") or s.get("settlement") or "") for s in settlements)
    by_grade = Counter(str(s.get("grade") or "") for s in settlements)
    by_market = Counter(str(s.get("market") or "") for s in settlements)
    sporting = {"WIN", "LOSS", "PUSH"}
    return {
        "runId": freeze["runId"],
        "frozenForecastHash": freeze["frozenForecastHash"],
        "modeledSettled": len(settlements),
        "settled": sum(s.get("settlement") in sporting for s in settlements),
        "wins": by_result.get("WIN", 0),
        "losses": by_result.get("LOSS", 0),
        "pushes": by_result.get("PUSH", 0),
        "voids": by_result.get("VOID", 0),
        "dnp": by_result.get("DNP", 0),
        "reboot": by_result.get("REBOOT", 0),
        "unknownPlatformRule": by_result.get("UNKNOWN_PLATFORM_RULE", 0),
        "unresolved": by_result.get("UNKNOWN_PLATFORM_RULE", 0),
        "byResult": dict(sorted(by_result.items())),
        "byGrade": dict(sorted(by_grade.items())),
        "byMarket": dict(sorted(by_market.items())),
        "learningRevisionBefore": integrity.get("learningRevision", "LR000000"),
        "learningRevisionAfter": integrity.get("learningRevision", "LR000000"),
        "lrPromoted": False,
        "calibrationPromotion": "NOT_AUTOMATIC",
        "predictiveClaim": "NONE",
        "outcomesSha256": outcomes_sha256,
        "frozenRunVerified": True,
        "platformSettlementComputed": False,
        "platformSettlementReason": "ENTRY_CONTRACT_AND_PARTICIPATION_FACTS_REQUIRED",
    }


def settle_run(run_dir: Path, outcomes_path: Path, *, card_only: bool = False) -> dict[str, Any]:
    run_dir = Path(run_dir)
    outcomes_path = Path(outcomes_path)
    freeze_bytes = (run_dir / "frozen_forecast.json").read_bytes()
    freeze, integrity, population = _verify_frozen_run(run_dir)
    outcomes_sha256 = _sha256_file(outcomes_path)
    outcomes = _outcomes(outcomes_path)
    modeled = _modeled_rows(population)
    if card_only:
        keep = _card_ids(run_dir)
        modeled = [p for p in modeled if str(p.get("projectionId") or "") in keep]

    settlements: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    for prop in modeled:
        out = outcomes.get(str(prop.get("projectionId") or ""))
        rec = _settle_row(prop, out, outcomes_sha256=outcomes_sha256)
        classified = classify_failure(
            predicted_side=str(rec.get("direction") or prop.get("direction") or ""),
            outcome=str(rec.get("result") or rec.get("settlement") or ""),
            snapshot_fields={**prop, **rec, **(out or {})},
        )
        rec["failureClass"] = classified["failureClass"]
        rec["failureClassPermanentPatch"] = False
        rec["failureClassReasons"] = classified.get("reasons") or []
        rec["frozenForecastHash"] = freeze["frozenForecastHash"]
        rec["evidenceGraphHash"] = freeze.get("evidenceGraphHash") or integrity.get("evidenceGraphHash")
        rec["parameterSnapshotHash"] = prop.get("parameterSnapshotHash")
        rec["researchReuseNotDecidedByResult"] = True
        rec["futureOnlyLearning"] = True
        settlements.append(rec)
        if rec.get("settlement") == "LOSS":
            lower = float(prop.get("lowerBound") or 0.0)
            mechanism = "NORMAL_VARIANCE_OR_UNRESOLVED_MECHANISM"
            model_error = lower >= 0.55
            out = out or {}
            actual_opp = out.get("actualOpportunity")
            expected_opp = prop.get("opportunityMean")
            if actual_opp is not None and expected_opp not in {None, 0}:
                ratio = float(actual_opp) / max(1e-9, float(expected_opp))
                if ratio < 0.75 or ratio > 1.25:
                    mechanism = "OPPORTUNITY_ERROR_CANDIDATE"
                    model_error = True
            audit = {
                "projectionId": rec["projectionId"],
                "result": rec["settlement"],
                "mechanism": mechanism,
                "modelErrorCandidate": model_error,
                "normalVarianceStillPlausible": not model_error,
                "frozenForecastHash": freeze["frozenForecastHash"],
            }
            audits.append(audit)
            if model_error:
                proposal = {
                    "projectionId": rec["projectionId"],
                    "mechanism": mechanism,
                    "proposal": "REGISTER_SHADOW_CHALLENGER_ONLY",
                    "effective": "FUTURE_SLATES_ONLY",
                    "productionChange": False,
                }
                proposal["proposalHash"] = content_hash(proposal)
                proposals.append(proposal)

    calibration = build_challenger_cells(settlements)
    summary = _summarize(freeze, integrity, settlements, outcomes_sha256)
    summary["cardOnly"] = bool(card_only)

    (run_dir / "settlements.jsonl").write_text(
        "".join(json.dumps(s, sort_keys=True) + "\n" for s in settlements),
        encoding="utf-8",
    )
    (run_dir / "settlement_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Backward-compatible names used by earlier postgame tests.
    (run_dir / "settlement.json").write_text(
        json.dumps(settlements, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_dir / "audit.json").write_text(json.dumps(audits, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "calibration_challenger.json").write_text(
        json.dumps(calibration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_dir / "patch_proposals.json").write_text(
        json.dumps(proposals, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_dir / "postgame_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    cutoff = str(integrity.get("forecastCutoff") or "")
    run_id = str(integrity.get("runId") or freeze["runId"])
    lr = str(integrity.get("learningRevision") or "LR000000")
    freeze_hash = str(freeze["frozenForecastHash"])

    store = IndexedStore(run_dir / "index.sqlite")
    for rec in settlements:
        append_record(
            store,
            "Settlement",
            cutoff,
            run_id,
            lr,
            rec,
            source_hash=freeze_hash,
            player_id=rec.get("player"),
            market=rec.get("market"),
        )
        append_ledger_jsonl(
            run_dir,
            "Settlement",
            rec,
            cutoff=cutoff,
            run_id=run_id,
            lr=lr,
            source_hash=freeze_hash,
            projection_id=str(rec.get("projectionId") or ""),
        )
    append_record(store, "Audit", cutoff, run_id, lr, {"rows": audits}, source_hash=freeze_hash)
    for proposal in proposals:
        append_record(store, "PatchProposal", cutoff, run_id, lr, proposal, source_hash=freeze_hash)
    store.close()

    graph_path = run_dir / "evidence_graph.json"
    if graph_path.is_file():
        try:
            from dcm.research.evidence_graph import attach_runtime_lineage
            from dcm.research.research_store import ResearchStore
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            settlement_graph = attach_runtime_lineage(
                graph,
                selections=json.loads((run_dir / "strict_card.json").read_text(encoding="utf-8"))
                if (run_dir / "strict_card.json").is_file() else [],
                run_id=run_id,
                forecast_cutoff=cutoff,
                frozen_forecast_hash=freeze_hash,
                settlements=settlements,
            )
            (run_dir / "settlement_lineage.json").write_text(
                json.dumps(settlement_graph, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            persist = ResearchStore(run_dir / "research_store")
            for rec in settlements:
                persist.put_outcome(rec)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    after = (run_dir / "frozen_forecast.json").read_bytes()
    if after != freeze_bytes:
        mutate_forecast(run_dir / "frozen_forecast.json")
        raise RuntimeError("FROZEN_FORECAST_REWRITTEN")
    return {
        "summary": summary,
        "settlements": settlements,
        "audits": audits,
        "calibration": calibration,
        "patchProposals": proposals,
    }
