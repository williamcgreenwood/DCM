"""Exact, append-only settlement sidecar for typed Outlier Insights claims.

This module intentionally accepts already-normalized outcome evidence.  It
does not scrape, infer a box score, or grade a partial-period claim from a
full-game total.  Missing identity, period, metric, authority, or settlement
rules produce an unresolved ledger record rather than a guessed label.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dcm.contracts.hashes import content_hash
from dcm.learning.sidecar import append_ledger_jsonl


SETTLEMENT_ADAPTER_VERSION = "OUTLIER_INSIGHTS_SETTLEMENT_V1_2026-09-14"
FINAL_RESULTS = frozenset({"WIN", "LOSS", "PUSH", "VOID", "DNP", "UNKNOWN_RULE", "UNRESOLVED", "CONFLICT"})
TRAINING_RESULTS = frozenset({"WIN", "LOSS", "PUSH"})


def _text(value: Any, limit: int = 256) -> str:
    return "" if value is None else str(value).strip()[:limit]


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def _time(value: Any) -> datetime | None:
    text = _text(value, 64)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _key_parts(row: dict[str, Any]) -> tuple[str, str, str, str, float | None, str]:
    event = row.get("event") if isinstance(row.get("event"), dict) else {}
    event_id = _text(row.get("eventId") or event.get("eventId"), 128)
    subject_id = _text(row.get("subjectId") or row.get("playerId") or row.get("teamId"), 128)
    proposition = _text(row.get("proposition"), 128).upper()
    period = _text(row.get("periodLabel"), 64).upper()
    line = _num(row.get("line"))
    direction = _text(row.get("direction"), 32).upper()
    return event_id, subject_id, proposition, period, line, direction


def _outcome_key(row: dict[str, Any]) -> tuple[str, str, str, str, float | None, str]:
    # Outcome evidence uses the same canonical identity fields as a claim.
    return _key_parts(row)


def _parse_explicit_result(outcome: dict[str, Any]) -> str | None:
    value = _text(outcome.get("result") or outcome.get("settlement") or outcome.get("outcome"), 32).upper()
    if value == "TIE":
        value = "PUSH"
    if value in {"CANCELLED", "INACTIVE", "VOIDED"}:
        value = "VOID"
    return value if value in FINAL_RESULTS else None


def _compare(value: float, line: float, direction: str) -> str:
    if abs(value - line) < 1e-12:
        return "PUSH"
    if direction == "HIGHER":
        return "WIN" if value > line else "LOSS"
    if direction == "LOWER":
        return "WIN" if value < line else "LOSS"
    return "UNKNOWN_RULE"


def build_insight_settlement(
    claim: dict[str, Any],
    outcome: dict[str, Any] | None,
    *,
    decision_cutoff: str,
    settlement_rule_hash: str,
    recorded_at: str,
) -> dict[str, Any]:
    """Grade one claim only when identity and settlement semantics are exact."""
    claim_key = _key_parts(claim)
    base: dict[str, Any] = {
        "schema": "pillars_dcm.outlier_insight_settlement.v1",
        "adapterVersion": SETTLEMENT_ADAPTER_VERSION,
        "settlementId": "",
        "claimId": claim.get("claimId"),
        "insightId": claim.get("insightId"),
        "sourceHarSha256": claim.get("sourceHarSha256"),
        "sourceBodyHash": claim.get("sourceBodyHash"),
        "claimHash": claim.get("claimHash"),
        "decisionCutoff": decision_cutoff,
        "recordedAt": recorded_at,
        "claimKey": {
            "eventId": claim_key[0],
            "subjectId": claim_key[1],
            "proposition": claim_key[2],
            "periodLabel": claim_key[3],
            "line": claim_key[4],
            "direction": claim_key[5],
        },
        "settlementRuleHash": settlement_rule_hash,
        "result": "UNRESOLVED",
        "observedValue": None,
        "metric": "",
        "outcomeSourceId": "",
        "outcomeSourceHash": "",
        "outcomeAuthority": "",
        "trainingEligible": False,
        "binaryLabel": None,
        "reason": "OUTCOME_MISSING",
    }
    if not claim_key[0] or not claim_key[1] or not claim_key[2] or claim_key[4] is None:
        base["reason"] = "CLAIM_IDENTITY_INCOMPLETE"
    elif claim_key[5] not in {"HIGHER", "LOWER"}:
        base["reason"] = "CLAIM_DIRECTION_UNSUPPORTED"
    elif outcome is None:
        base["reason"] = "OUTCOME_MISSING"
    else:
        outcome_key = _outcome_key(outcome)
        if outcome_key != claim_key:
            base["reason"] = "OUTCOME_KEY_MISMATCH"
        else:
            explicit = _parse_explicit_result(outcome)
            observed = _num(outcome.get("observedValue") if "observedValue" in outcome else outcome.get("value"))
            result = explicit
            if result is None and observed is not None:
                result = _compare(observed, claim_key[4], claim_key[5])
            if result is None:
                result = "UNKNOWN_RULE"
            base.update(
                {
                    "result": result,
                    "observedValue": observed,
                    "metric": _text(outcome.get("metric"), 128),
                    "outcomeSourceId": _text(outcome.get("sourceId") or outcome.get("sourceUrl"), 512),
                    "outcomeSourceHash": _text(outcome.get("sourceHash"), 128),
                    "outcomeAuthority": _text(outcome.get("authority"), 128),
                    "reason": "GRADED_EXACT_RULE" if result in {"WIN", "LOSS", "PUSH"} else "EXPLICIT_ADMINISTRATIVE_RESULT",
                }
            )
            if result in TRAINING_RESULTS:
                base["binaryLabel"] = 1 if result == "WIN" else 0 if result == "LOSS" else None
                base["trainingEligible"] = bool(
                    base["outcomeSourceHash"]
                    and base["outcomeAuthority"]
                    and settlement_rule_hash
                    and _time(decision_cutoff) is not None
                )
    base["settlementId"] = "SETTLEMENT:" + content_hash(base)
    base["recordHash"] = content_hash(base)
    return base


def settle_insight_population(
    claims: Iterable[dict[str, Any]],
    outcomes: Iterable[dict[str, Any]],
    *,
    decision_cutoff: str,
    settlement_rule_hash: str,
    recorded_at: str,
) -> dict[str, Any]:
    """Settle every supplied claim; selected/parlay legs are not a special subset."""
    outcome_map: dict[tuple[str, str, str, str, float | None, str], list[dict[str, Any]]] = defaultdict(list)
    for outcome in outcomes:
        if isinstance(outcome, dict):
            outcome_map[_outcome_key(outcome)].append(dict(outcome))
    ledger: list[dict[str, Any]] = []
    for claim in claims:
        key = _key_parts(claim)
        matches = outcome_map.get(key, [])
        outcome: dict[str, Any] | None
        if len(matches) == 1:
            outcome = matches[0]
        elif len(matches) > 1:
            outcome = {
                **matches[0],
                "result": "CONFLICT",
                "sourceHash": content_hash(matches),
                "authority": "CONFLICTING_SOURCES",
            }
        else:
            outcome = None
        ledger.append(
            build_insight_settlement(
                claim,
                outcome,
                decision_cutoff=decision_cutoff,
                settlement_rule_hash=settlement_rule_hash,
                recorded_at=recorded_at,
            )
        )
    counts = Counter(str(row.get("result") or "UNRESOLVED") for row in ledger)
    training = sum(1 for row in ledger if row.get("trainingEligible"))
    return {
        "schema": "pillars_dcm.outlier_insight_settlement_ledger.v1",
        "adapterVersion": SETTLEMENT_ADAPTER_VERSION,
        "appendOnly": True,
        "claimCount": len(ledger),
        "settledCount": sum(int(counts.get(result, 0)) for result in ("WIN", "LOSS", "PUSH", "VOID", "DNP")),
        "trainingEligibleCount": training,
        "results": dict(sorted(counts.items())),
        "ledger": ledger,
        "contentHash": content_hash(ledger),
    }


def append_insight_settlements(
    destination: Path,
    ledger: Iterable[dict[str, Any]],
    *,
    run_id: str,
    decision_cutoff: str,
    learning_revision: str = "LR000000",
) -> dict[str, Any]:
    """Append immutable settlement records to the existing DCM sidecar."""
    rows = [dict(row) for row in ledger if isinstance(row, dict)]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    ledger_path = destination / "insight_settlement_ledger.jsonl"
    existing_hashes: set[str] = set()
    if ledger_path.is_file():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            try:
                previous = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(previous, dict) and previous.get("recordHash"):
                existing_hashes.add(str(previous["recordHash"]))
    appended = 0
    new_rows: list[dict[str, Any]] = []
    with ledger_path.open("a", encoding="utf-8") as ledger_file:
        for row in rows:
            record_hash = str(row.get("recordHash") or row.get("settlementId") or "")
            if record_hash in existing_hashes:
                continue
            ledger_file.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            existing_hashes.add(record_hash)
            appended += 1
            new_rows.append(row)
    for row in new_rows:
        append_ledger_jsonl(
            destination,
            "Settlement",
            row,
            cutoff=decision_cutoff,
            run_id=run_id,
            lr=learning_revision,
            source_hash=str(row.get("recordHash") or row.get("settlementId") or ""),
            projection_id=str(row.get("claimId") or ""),
        )
    return {
        "appended": appended,
        "existing": len(rows) - appended,
        "appendOnly": True,
        "ledgerPath": str(ledger_path),
        "contentHash": content_hash(rows),
    }
