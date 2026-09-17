"""HAR-only autonomous closure for Insights/run-slate.

Operator policy (code law):

1. The operator supplies HARs only. Insights captures that already contain
   exact line + HIGHER/LOWER *are* the fresh platform capture. Never ask for a
   second "current board HAR" as a required next step.
2. Optional board HARs must not block Top100/Top25 research or the
   research → settle → train → playables loop.
3. Do not invent outcomes, sides, or probabilities. predictiveClaim stays
   NONE unless chronological production gates are actually earned.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from dcm.chat.state import read_json
from dcm.contracts.hashes import content_hash
from dcm.learning.insight_settlement import (
    append_insight_settlements,
    settle_insight_population,
)
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM


AUTONOMOUS_PHASE_ORDER = ("RESEARCH", "SETTLE", "TRAIN", "PLAYABLES")
MIN_TRAINING_LABELS = 20
SETTLEMENT_RULE_HASH_UNAVAILABLE = "UNAVAILABLE_NO_VALIDATED_RULE_HASH"

# Required-ask language that must never appear on Insights-only receipts.
_BOARD_HAR_ASK_RE = re.compile(
    r"(provide\s+a\s+current\s+(platform\s+)?board(\s*/\s*har|\s+har)?"
    r"|current\s+platform\s+board(\s*/\s*har|\s+har)?"
    r"|required\s+(next\s+step[:\s]+)?(current\s+)?(platform\s+)?board\s*har"
    r"|optional\s+board\s+har.{0,40}required"
    r"|ask\s+(the\s+)?operator\s+for\s+(a\s+)?(current\s+)?board\s+har)",
    re.IGNORECASE,
)

_FINAL_STATUSES = frozenset({
    "FINAL", "FINALIZED", "CLOSED", "COMPLETE", "COMPLETED", "OFFICIAL",
    "SETTLED", "POSTGAME", "POST_GAME", "ENDED", "FINISHED",
})
_FUTURE_STATUSES = frozenset({
    "FUTURE", "SCHEDULED", "PRE_GAME", "PREGAME", "UPCOMING", "NOT_STARTED",
})


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def insights_line_side_count(claims: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        try:
            line = float(claim.get("line"))
        except (TypeError, ValueError):
            continue
        if line != line or abs(line) == float("inf"):
            continue
        direction = str(claim.get("direction") or "").upper()
        direction_class = str(claim.get("directionClass") or "")
        if direction_class == "HIGHER_LOWER" and direction in {"HIGHER", "LOWER"}:
            count += 1
    return count


def classify_claim_event_timing(
    claim: Mapping[str, Any],
    *,
    cutoff: str | None,
) -> str:
    """Return FINAL, FUTURE, or UNKNOWN without inventing a result.

    FINAL is only assigned from an observed event status. A scheduled start
    after the decision cutoff is FUTURE. Anything else stays UNKNOWN so
    settlement remains deferred rather than guessed.
    """
    event = claim.get("event") if isinstance(claim.get("event"), Mapping) else {}
    identity = claim.get("harIdentity") if isinstance(claim.get("harIdentity"), Mapping) else {}
    identity_event = identity.get("event") if isinstance(identity.get("event"), Mapping) else {}
    status = str(
        claim.get("eventStatus")
        or event.get("status")
        or identity_event.get("status")
        or ""
    ).strip().upper().replace(" ", "_")
    if status in _FINAL_STATUSES:
        return "FINAL"
    if status in _FUTURE_STATUSES:
        return "FUTURE"
    scheduled = _parse_time(
        event.get("scheduledTime")
        or identity_event.get("scheduledTime")
        or claim.get("scheduledTime")
    )
    decision = _parse_time(cutoff)
    if scheduled is not None and decision is not None and scheduled > decision:
        return "FUTURE"
    return "UNKNOWN"


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from iter_strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from iter_strings(item)


def _is_required_board_har_ask(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    lower = value.lower()
    if any(prefix in lower for prefix in ("do not ", "don't ", "never ", "not a required", "must not")):
        return False
    if _BOARD_HAR_ASK_RE.search(value):
        return True
    return False


def receipt_requires_board_har(payload: Mapping[str, Any] | None) -> bool:
    """True when a receipt treats a board HAR as a required operator ask."""
    if not isinstance(payload, Mapping):
        return False
    if payload.get("boardHarRequired") is True:
        return True
    contract = payload.get("operatorContract") if isinstance(payload.get("operatorContract"), Mapping) else {}
    if contract.get("boardHarRequired") is True:
        return True
    next_input = str(payload.get("nextRequiredOperatorInput") or contract.get("nextRequiredOperatorInput") or "NONE")
    if "board" in next_input.lower() and "har" in next_input.lower() and next_input.upper() != "NONE":
        return True
    asks = list(contract.get("requiredOperatorAsks") or []) + list(payload.get("requiredOperatorAsks") or [])
    for ask in asks:
        text = str(ask or "")
        if _is_required_board_har_ask(text) or "board har" in text.lower():
            return True
    pending = []
    research = payload.get("research") if isinstance(payload.get("research"), Mapping) else {}
    actions = research.get("actions") if isinstance(research.get("actions"), Mapping) else {}
    pending.extend(actions.get("pending") or [])
    pending.extend(payload.get("pending") or [])
    for item in pending:
        if _is_required_board_har_ask(str(item or "")):
            return True
    return False


def operator_contract(
    *,
    board_offer_count: int,
    insights_offer_count: int,
    claim_count: int,
) -> dict[str, Any]:
    """HAR-only operator contract fragment for execution receipts."""
    missing_insights_side = int(insights_offer_count) <= 0
    informational_current_offer_missing = (
        missing_insights_side and int(board_offer_count) <= 0 and int(claim_count) > 0
    )
    body = {
        "schema": "pillars_dcm.har_only_operator_contract.v1",
        "harOnly": True,
        "insightsHarIsPlatformCapture": True,
        "boardHarRequired": False,
        "optionalBoardHar": {
            "accepted": True,
            "required": False,
            "blocksResearchTop100": False,
            "blocksResearchTop25": False,
            "blocksAutonomousLoop": False,
        },
        "requiredOperatorAsks": [],
        "informational": {
            "CURRENT_OFFER_MISSING": informational_current_offer_missing,
            "reason": (
                "No Insights line+side and no board offers; informational only."
                if informational_current_offer_missing
                else "Insights line+side (or board offers) are present; board HAR is optional."
            ),
        },
        "nextRequiredOperatorInput": "NONE",
        "note": (
            "Insights HARs that already contain exact line + HIGHER/LOWER are the "
            "fresh platform capture. Do not ask the operator for a second current "
            "board HAR. Continue research → settle → train → playables with typed states."
        ),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def _phase(name: str, status: str, **extra: Any) -> dict[str, Any]:
    row = {"name": name, "status": status, "predictiveClaim": PREDICTIVE_CLAIM}
    row.update(extra)
    return row


def _load_outcomes(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not Path(path).is_file():
        return []
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("outcomes"), list):
        return [dict(row) for row in value["outcomes"] if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("outcomes"), dict):
        rows = []
        for key, row in value["outcomes"].items():
            if isinstance(row, dict):
                item = dict(row)
                item.setdefault("claimId", key)
                rows.append(item)
        return rows
    raise ValueError("OUTCOMES_MUST_BE_LIST_OR_OUTCOMES_MAP")


def _drive_research(
    session: Any | None,
    *,
    observations_imported: bool,
    research_queue_selected: int,
    insight_request_count: int,
) -> dict[str, Any]:
    """Schedule host research; never require a board HAR."""
    extra: dict[str, Any] = {
        "evidenceImportPath": "ALLOWED",
        "boardHarRequired": False,
        "insightRequestCount": int(insight_request_count),
        "researchQueueSelected": int(research_queue_selected),
    }
    if session is None:
        return _phase(
            "RESEARCH",
            "FAILED",
            reason="NO_COMPOSITE_SESSION",
            **extra,
        )
    director_status: dict[str, Any] | None = None
    try:
        from dcm.runtime.run_director import RunDirector

        director = RunDirector(session.dest, workspace=getattr(session, "workspace", None))
        director_status = director.run_until_awaiting()
        extra["directorPhase"] = director_status.get("phase")
        extra["directorBatchId"] = director_status.get("batchId")
        extra["directorWaiting"] = bool(director_status.get("waiting"))
    except Exception as exc:  # noqa: BLE001 — typed autonomous state, not a crash
        extra["directorError"] = type(exc).__name__
        extra["directorErrorCode"] = str(exc)[:180]
    if observations_imported:
        return _phase("RESEARCH", "IMPORTED", **extra)
    if director_status and director_status.get("phase") == "TERMINAL":
        return _phase("RESEARCH", "COMPLETE_NO_FURTHER_BATCH", **extra)
    if director_status and (
        director_status.get("phase") == "AWAITING_RESPONSE" or director_status.get("waiting")
    ):
        return _phase("RESEARCH", "AWAITING_HOST_OBSERVATIONS", **extra)
    if research_queue_selected > 0 or insight_request_count > 0:
        return _phase("RESEARCH", "SCHEDULED", **extra)
    if extra.get("directorError"):
        return _phase("RESEARCH", "FAILED", reason="DIRECTOR_TYPED_FAILURE", **extra)
    return _phase("RESEARCH", "SCHEDULED", **extra)


def _drive_settle(
    *,
    session: Any | None,
    claims: list[dict[str, Any]],
    cutoff: str | None,
    outcomes_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Settle FINAL claims when outcomes exist; defer FUTURE without a HAR ask."""
    timings = [classify_claim_event_timing(claim, cutoff=cutoff) for claim in claims]
    counts = {
        "FINAL": sum(1 for row in timings if row == "FINAL"),
        "FUTURE": sum(1 for row in timings if row == "FUTURE"),
        "UNKNOWN": sum(1 for row in timings if row == "UNKNOWN"),
    }
    deferred: list[dict[str, Any]] = []
    settlement_doc: dict[str, Any] = {
        "schema": "pillars_dcm.settlement_queue.v1",
        "status": "AWAITING_AUTHORITATIVE_OUTCOMES",
        "claimCount": len(claims),
        "settledCount": 0,
        "trainingEligibleCount": 0,
        "exactIdentityRequired": True,
        "futureOnlyLearning": True,
        "outcomesInvented": False,
        "eventTiming": counts,
        "outcomes": [],
    }
    extra = {
        "boardHarRequired": False,
        "eventTiming": counts,
        "outcomesInvented": False,
    }
    if not claims:
        return _phase("SETTLE", "SKIPPED_NO_CLAIMS", **extra), settlement_doc, deferred

    if counts["FUTURE"] or counts["UNKNOWN"]:
        deferred.append(
            {
                "job": "insight_settle",
                "when": "EVENT_FINAL_AND_AUTHORITATIVE_OUTCOMES_AVAILABLE",
                "population": "WHOLE_INSIGHTS_MODELED",
                "futureCount": counts["FUTURE"],
                "unknownCount": counts["UNKNOWN"],
                "boardHarRequired": False,
                "note": (
                    "Do not request a new board HAR. Re-run insight_settle / settle "
                    "when events are FINAL and outcomes can be joined."
                ),
            }
        )

    outcomes: list[dict[str, Any]] = []
    try:
        outcomes = _load_outcomes(outcomes_path)
    except Exception as exc:  # noqa: BLE001
        extra["outcomesError"] = type(exc).__name__
        extra["outcomesErrorCode"] = str(exc)[:180]
        return _phase("SETTLE", "FAILED", reason="OUTCOMES_UNREADABLE", **extra), settlement_doc, deferred

    can_grade = bool(outcomes) and counts["FINAL"] > 0
    if can_grade and cutoff:
        recorded_at = _now_iso()
        result = settle_insight_population(
            claims,
            outcomes,
            decision_cutoff=cutoff,
            settlement_rule_hash=SETTLEMENT_RULE_HASH_UNAVAILABLE,
            recorded_at=recorded_at,
        )
        dest = Path(session.dest) if session is not None else None
        append_result = None
        if dest is not None:
            append_result = append_insight_settlements(
                dest,
                result["ledger"],
                run_id=dest.name,
                decision_cutoff=cutoff,
                learning_revision=LEARNING_REVISION,
            )
        settlement_doc.update(
            {
                "status": "SETTLED_AVAILABLE_FINAL",
                "settledCount": int(result.get("settledCount") or 0),
                "trainingEligibleCount": int(result.get("trainingEligibleCount") or 0),
                "results": result.get("results") or {},
                "append": append_result,
                "adapterVersion": result.get("adapterVersion"),
                "contentHash": result.get("contentHash"),
                "ledger": result.get("ledger") or [],
            }
        )
        extra.update(
            {
                "settledCount": settlement_doc["settledCount"],
                "trainingEligibleCount": settlement_doc["trainingEligibleCount"],
                "results": settlement_doc["results"],
            }
        )
        return _phase("SETTLE", "SETTLED", **extra), settlement_doc, deferred

    if counts["FINAL"] > 0 and not outcomes:
        settlement_doc["status"] = "FINAL_AWAITING_AUTHORITATIVE_OUTCOMES"
        deferred.append(
            {
                "job": "insight_settle",
                "when": "AUTHORITATIVE_OUTCOMES_AVAILABLE",
                "population": "WHOLE_INSIGHTS_MODELED",
                "finalCount": counts["FINAL"],
                "boardHarRequired": False,
                "note": "Events are FINAL; join outcomes when fetchable. Do not recapture a board HAR.",
            }
        )
        return _phase("SETTLE", "AWAITING_AUTHORITATIVE_OUTCOMES", **extra), settlement_doc, deferred
    if counts["FUTURE"] > 0 and counts["FINAL"] == 0:
        settlement_doc["status"] = "DEFERRED_FUTURE"
        return _phase("SETTLE", "DEFERRED_FUTURE", **extra), settlement_doc, deferred
    settlement_doc["status"] = "AWAITING_AUTHORITATIVE_OUTCOMES"
    return _phase("SETTLE", "AWAITING_AUTHORITATIVE_OUTCOMES", **extra), settlement_doc, deferred



def _chatgpt_research_action(
    *,
    run_id: str,
    batch_id: str | None,
    batch_content_sha: str | None,
    packet_path: str | None,
    request_ids: Iterable[str] = (),
    required_fields: Iterable[str] = (),
) -> dict[str, Any]:
    """Describe the durable research handoff; the operator has no manual step."""
    return {
        "schema": "pillars_dcm.autonomous_next_action.v1",
        "type": "CHATGPT_RESEARCH_RESPONSE",
        "owner": "CHATGPT",
        "status": "READY" if batch_id else "WAITING",
        "runId": run_id,
        "batchId": batch_id,
        "batchContentSha": batch_content_sha,
        "packetPath": packet_path,
        "responsePath": f"responses/{batch_id}.response.json" if batch_id else "responses/response.json",
        "requestIds": sorted({str(value) for value in request_ids if str(value)}),
        "requiredFields": sorted({str(value) for value in required_fields if str(value)}),
        "responseSchema": "pillars_dcm.research_response.v1",
        "sourcePolicy": "OFFICIAL_OR_APPROVED_PUBLIC_SOURCES_WITH_URL_HASH_RETRIEVAL_TIME",
        "operatorInputRequired": False,
        "noBoardHarAsk": True,
        "boardHarRequired": False,
        "nextCommand": "autonomous-resume",
        "note": "ChatGPT researches the packet and submits evidence; unresolved facts become typed failures, never guesses or another board-HAR request.",
    }


def _chatgpt_settlement_action(
    *,
    run_id: str,
    claims: Iterable[Mapping[str, Any]],
    cutoff: str | None,
) -> dict[str, Any]:
    rows = [row for row in claims if isinstance(row, Mapping)]
    timing = [classify_claim_event_timing(row, cutoff=cutoff) for row in rows]
    final_count = timing.count("FINAL")
    return {
        "schema": "pillars_dcm.autonomous_next_action.v1",
        "type": "CHATGPT_OUTCOME_RESEARCH",
        "owner": "CHATGPT",
        "status": "READY" if final_count else "WAITING_FOR_EVENT_FINAL",
        "runId": run_id,
        "packetPath": "settlement_queue.json",
        "responsePath": "responses/outcomes.response.json",
        "responseSchema": "pillars_dcm.research_response.v1",
        "outcomeSchema": "outcome_observation.v1",
        "claimCount": len(rows),
        "finalClaimCount": final_count,
        "futureClaimCount": timing.count("FUTURE"),
        "unknownClaimCount": timing.count("UNKNOWN"),
        "requiredFields": [
            "eventId", "subjectId", "proposition", "periodLabel", "line",
            "direction", "observedValue_or_result", "sourceId", "sourceUrl",
            "sourceHash", "authority", "retrievedAt", "publishedAt",
        ],
        "sourcePolicy": "OFFICIAL_OR_APPROVED_AUTHORITATIVE_OUTCOME_SOURCES",
        "operatorInputRequired": False,
        "noBoardHarAsk": True,
        "boardHarRequired": False,
        "nextCommand": "autonomous-resume",
        "note": "Fetch authoritative outcomes after final status and settle every eligible claim; unresolved or conflicting outcomes stay typed and are never invented.",
    }


def _finite_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and abs(parsed) != float("inf") else None


def _training_evaluation_rows(settlement_doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project only exact, settled labels with an already-produced probability."""
    rows: list[dict[str, Any]] = []
    for source in (settlement_doc.get("ledger") or settlement_doc.get("trainingRows") or []):
        if not isinstance(source, Mapping) or not source.get("trainingEligible"):
            continue
        result = str(source.get("result") or "").upper()
        if result not in {"WIN", "LOSS", "PUSH"}:
            continue
        p = None
        for key in ("calibratedP", "selectedP", "predictionP", "modelP", "p"):
            p = _finite_number(source.get(key))
            if p is not None and 0.0 <= p <= 1.0:
                break
        if p is None:
            continue
        rows.append({
            **dict(source),
            "result": result,
            "labelSplit": "supervised",
            "selectedP": p,
            "decisionCutoff": source.get("decisionCutoff") or source.get("recordedAt"),
        })
    return rows


def _drive_train(settlement_doc: Mapping[str, Any], *, session: Any | None = None) -> dict[str, Any]:
    labels = int(settlement_doc.get("trainingEligibleCount") or 0)
    extra: dict[str, Any] = {
        "trainingEligibleCount": labels,
        "minTrainingLabels": MIN_TRAINING_LABELS,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "boardHarRequired": False,
        "modelPathAttempted": False,
        "predictiveCertified": False,
        "productionRootCertified": False,
    }
    if labels <= 0:
        return _phase("TRAIN", "SKIPPED_NO_SETTLEMENT", **extra)
    if labels < MIN_TRAINING_LABELS:
        return _phase("TRAIN", "SKIPPED_INSUFFICIENT_LABELS", **extra)
    rows = _training_evaluation_rows(settlement_doc)
    if not rows:
        return _phase("TRAIN", "SKIPPED_NO_MODEL_INPUTS", reason="SETTLED_LABELS_HAVE_NO_FROZEN_PROBABILITY", **extra)
    extra["modelPathAttempted"] = True
    try:
        from dcm.learning.calibration import evaluate_calibration_readiness
        from dcm.learning.walkforward import run_walkforward

        walkforward = run_walkforward(rows)
        calibration = evaluate_calibration_readiness(rows)
        extra.update({
            "statusDetail": walkforward.get("status"),
            "walkforward": walkforward,
            "calibrationReadiness": calibration,
            "modelReport": walkforward,
        })
        return _phase("TRAIN", "SHADOW_EVALUATED", **extra)
    except Exception as exc:  # typed model boundary; do not fabricate a model
        return _phase(
            "TRAIN",
            "FAILED_MODEL_EVALUATION",
            reason="MODEL_EVALUATION_ERROR",
            errorType=type(exc).__name__,
            errorCode=str(exc)[:180],
            **extra,
        )


def _drive_playables(
    *,
    insights_top25_count: int,
    board_offer_count: int,
    model_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    model = model_result if isinstance(model_result, Mapping) else {}
    model_ready = str(model.get("status") or "") in {"CERTIFIED", "PRODUCTION_CERTIFIED"}
    root_ready = bool(model.get("productionRootCertified"))
    if int(board_offer_count) <= 0:
        reason = "OFFER_REVALIDATION_UNAVAILABLE"
    elif not model_ready or not root_ready:
        reason = "PRODUCTION_MODEL_GATES_NOT_MET"
    else:
        reason = "SELECTION_INPUTS_NOT_FROZEN"
    return _phase(
        "PLAYABLES",
        "ABSTAINED_GATES_NOT_MET",
        count=0,
        insightsTop25Count=int(insights_top25_count),
        boardOfferCount=int(board_offer_count),
        productionSelectionPermitted=False,
        modelPathAttempted=bool(model.get("modelPathAttempted")),
        predictiveCertified=bool(model.get("predictiveCertified")),
        productionRootCertified=root_ready,
        reason=reason,
        boardHarRequired=False,
        note=(
            "Playables are selected only by the production selector after exact "
            "offer revalidation, evidence, settlement, calibrated model, and "
            "root certification. Insights Top25 remains research-only when board=0."
        ),
    )


def advance_autonomous_closure(
    *,
    session: Any | None,
    claims: list[dict[str, Any]],
    board_offer_count: int,
    insights_offer_count: int,
    insights_top25_count: int,
    cutoff: str | None,
    observations_imported: bool,
    research_queue_selected: int,
    outcomes: Path | None = None,
    model_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance research → settle → train → playables with typed states."""
    insight_bridge = {}
    if session is not None:
        insight_bridge = read_json(Path(session.dest) / "insights_host_bridge.json") or {}
    insight_requests = insight_bridge.get("requests") if isinstance(insight_bridge, dict) else []
    insight_request_count = len(insight_requests) if isinstance(insight_requests, list) else 0

    research = _drive_research(
        session,
        observations_imported=observations_imported,
        research_queue_selected=research_queue_selected,
        insight_request_count=insight_request_count,
    )
    settle_phase, settlement_doc, deferred = _drive_settle(
        session=session,
        claims=claims,
        cutoff=cutoff,
        outcomes_path=outcomes,
    )
    train = _drive_train(settlement_doc, session=session)
    playables = _drive_playables(
        insights_top25_count=insights_top25_count,
        board_offer_count=board_offer_count,
        model_result=model_result or train,
    )
    phases = [research, settle_phase, train, playables]
    contract = operator_contract(
        board_offer_count=board_offer_count,
        insights_offer_count=insights_offer_count,
        claim_count=len(claims),
    )
    body = {
        "schema": "pillars_dcm.autonomous_closure.v1",
        "enabled": True,
        "phaseOrder": list(AUTONOMOUS_PHASE_ORDER),
        "phases": phases,
        "operatorContract": contract,
        "deferredJobs": deferred,
        "settlement": settlement_doc,
        "model": train,
        "boardHarRequired": False,
        "requiredOperatorAsks": [],
        "nextRequiredOperatorInput": "NONE",
        "predictiveClaim": PREDICTIVE_CLAIM,
        "learningRevision": LEARNING_REVISION,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    if receipt_requires_board_har(body):
        raise RuntimeError("HAR_ONLY_CONTRACT_VIOLATION: autonomous receipt required a board HAR")
    return body


__all__ = [
    "AUTONOMOUS_PHASE_ORDER",
    "MIN_TRAINING_LABELS",
    "advance_autonomous_closure",
    "classify_claim_event_timing",
    "insights_line_side_count",
    "iter_strings",
    "operator_contract",
    "receipt_requires_board_har",
]
