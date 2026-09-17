"""Execute the explicit deep-research prompt over a multi-HAR slate.

The slate command is an orchestration boundary.  It runs the canonical
accounting/index/research-queue path for each capture and then for the
chronologically reconciled union.  It does not turn an Insights signal into a
market offer or invent probabilities when the captures contain no trusted
board rows.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

from dcm.algorithms.pipeline_constitution import (
    PIPELINE_CONSTITUTION_ID,
    evaluate_insights_har_pipeline,
)
from dcm.chat.session import HostSession
from dcm.chat.slate_autonomous import (
    AUTONOMOUS_PHASE_ORDER,
    advance_autonomous_closure,
    operator_contract,
    receipt_requires_board_har,
)
from dcm.chat.state import read_json
from dcm.chat.har_only_controller import enhance_slate_result, internal_order
from dcm.contracts.hashes import content_hash
from dcm.ingest.insights import merge_insight_claims
from dcm.research.insight_bridge import insights_offer_snapshots
from dcm.runtime.input_boundary import inspect_input_boundary
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE


SLATE_SCHEMA = "pillars_dcm.slate_run_manifest.v1"
EXECUTION_RECEIPT_SCHEMA = "pillars_dcm.work_codex_execution_receipt.v1"
SLATE_VERSION = "DCM_EXPLICIT_PROMPT_SLATE_V1_2026-09-16"

_SPORT_ORDER = {
    "CFB": 0,
    "NCAAFB": 0,
    "NFL": 1,
    "WNBA": 2,
    "NBA": 3,
    "MLB": 4,
    "SOCCER": 5,
    "NHL": 6,
}

_KNOWN_ERROR_CODES = (
    "HAR_JSON_INVALID",
    "HAR_LOG_REQUIRED",
    "HAR_ENTRIES_REQUIRED",
    "HAR_LIMIT_EXCEEDED",
    "FORECAST_CUTOFF_REQUIRED",
    "NO_HAR_CAPTURES",
    "CHECKPOINT",
    "CONNECTOR_UNAVAILABLE",
    "SOURCE_UNAVAILABLE",
)

_PHASE_WORDS = {
    "ZERO": 0,
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
    "TEN": 10,
    "ELEVEN": 11,
    "TWELVE": 12,
    "THIRTEEN": 13,
    "FOURTEEN": 14,
    "FIFTEEN": 15,
    "SIXTEEN": 16,
    "SEVENTEEN": 17,
    "EIGHTEEN": 18,
    "NINETEEN": 19,
    "TWENTY": 20,
    "TWENTY-ONE": 21,
    "TWENTY-TWO": 22,
    "TWENTY-THREE": 23,
    "TWENTY-FOUR": 24,
    "TWENTY-FIVE": 25,
    "TWENTY-SIX": 26,
}

_PRIVACY = {
    "rawHarPersisted": False,
    "rawBodiesPersisted": False,
    "rawHeadersPersisted": False,
    "rawUrlsPersisted": False,
    "rawArtifactsCommitted": False,
    "rawArtifactsUploaded": False,
    "freeFormInsightTextPersisted": False,
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not Path(path).is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _safe_error(exc: BaseException) -> dict[str, str]:
    text = str(exc).upper()
    code = next((candidate for candidate in _KNOWN_ERROR_CODES if candidate in text), "SLATE_STEP_FAILED")
    return {"errorType": type(exc).__name__, "code": code}


def _prompt_metadata(prompt: Path) -> dict[str, Any]:
    prompt = Path(prompt)
    if not prompt.is_file():
        raise FileNotFoundError("EXECUTION_PROMPT_NOT_FOUND")
    text = prompt.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("EXECUTION_PROMPT_EMPTY")
    phase_ids: set[int] = set()
    for value in re.findall(r"(?im)^\s*(?:#{1,6}\s*)?phase\s+([a-z]+(?:-[a-z]+)?|\d+)\b", text):
        phase_ids.add(int(value) if value.isdigit() else _PHASE_WORDS.get(value.upper(), -1))
    phase_ids.discard(-1)
    return {
        "name": prompt.name,
        "sha256": _sha256_bytes(text.encode("utf-8")),
        "lineCount": len(text.splitlines()),
        "phaseIds": sorted(phase_ids),
        "executionMode": "EXPLICIT_PROMPT_EXECUTED",
    }


def _sport_hint(name: str) -> str:
    upper = str(name).upper()
    for token in sorted(_SPORT_ORDER, key=len, reverse=True):
        if re.search(rf"(?:^|[^A-Z]){re.escape(token)}(?:[^A-Z]|$)", upper):
            return token
    return "UNKNOWN"


def _ordered_inputs(inputs: Iterable[Path]) -> list[Path]:
    paths = [Path(value) for value in inputs]
    if not paths:
        raise ValueError("NO_HAR_CAPTURES")
    if any(not path.is_file() for path in paths):
        raise FileNotFoundError("HAR_INPUT_NOT_FOUND")
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    unique.sort(key=lambda path: (_SPORT_ORDER.get(_sport_hint(path.name), 99), _sport_hint(path.name), path.name, _sha256_file(path)))
    return unique


def _repo_head() -> str | None:
    repo = Path(__file__).resolve().parents[3]
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    value = (proc.stdout or "").strip()
    return value if proc.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{40}", value) else None


def _source_summary(
    path: Path,
    session: HostSession | None,
    boundary: dict[str, Any],
    *,
    processing_order: int,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "processingOrder": processing_order,
        "filename": str(boundary.get("name") or path.name),
        "captureId": f"CAPTURE:{boundary.get('sha256') or _sha256_file(path)}",
        "sha256": boundary.get("sha256") or _sha256_file(path),
        "sizeBytes": int(boundary.get("sizeBytes") or 0),
        "entryCount": int((boundary.get("safeProjection") or {}).get("harEntryCount") or 0),
        "sportHint": _sport_hint(path.name),
        "status": "FAILED" if error else "ACCOUNTED",
        "privacy": dict(_PRIVACY),
    }
    if error:
        summary["error"] = dict(error)
        return summary
    if session is None:
        summary["status"] = "FAILED"
        summary["error"] = {"errorType": "RuntimeError", "code": "SLATE_SESSION_MISSING"}
        return summary

    input_manifest = read_json(session.dest / "input_manifest.json") or {}
    board = read_json(session.dest / "board.json") or {}
    queue = read_json(session.dest / "insights_research_queue.json") or {}
    source_manifest = read_json(session.dest / "insights_source_manifest.json") or {}
    breakdown_manifest = read_json(session.dest / "har_breakdown_manifest.json") or {}
    breakdown: dict[str, Any] = {}
    breakdown_dir = session.dest / "har_breakdowns"
    for candidate in sorted(breakdown_dir.glob("*.json")) if breakdown_dir.is_dir() else []:
        body = read_json(candidate)
        if isinstance(body, dict) and str(body.get("har_sha256") or "") == str(summary["sha256"]):
            breakdown = body
            break
    queue_accounting = queue.get("accounting") if isinstance(queue, dict) else {}
    queue_accounting = queue_accounting if isinstance(queue_accounting, dict) else {}
    source_rows = source_manifest.get("sources") if isinstance(source_manifest, dict) else []
    source_row = source_rows[0] if isinstance(source_rows, list) and source_rows else {}
    capture = breakdown.get("capture") if isinstance(breakdown.get("capture"), dict) else {}
    receipt = {}
    receipts = breakdown_manifest.get("receipts") if isinstance(breakdown_manifest, dict) else []
    if isinstance(receipts, list):
        receipt = next((row for row in receipts if isinstance(row, dict) and row.get("harSha256") == summary["sha256"]), {})
    summary.update(
        {
            "runId": session.dest.name,
            "captureStart": capture.get("captureStart"),
            "captureEnd": capture.get("captureEnd"),
            "recordCount": int((receipt or {}).get("recordCount") or 0),
            "boardOfferCount": len(board.get("rows") or []) if isinstance(board, dict) else 0,
            "insightClaimCount": int(source_row.get("claimCount") or queue_accounting.get("inputClaimCount") or 0),
            "queuedClaimCount": int(queue_accounting.get("queuedClaimCount") or 0),
            "top100Count": int(queue_accounting.get("top100Count") or 0),
            "top25Count": int(queue_accounting.get("top25Count") or 0),
            "productionSelectionPermitted": False,
            "paginationIncomplete": int(
                (capture.get("canonicalIndexStats") or {}).get("insights_pagination_incomplete") or 0
            ) > 0 or any(
                not bool(row.get("paginationComplete"))
                for row in _read_jsonl(session.dest / "insights_claims.jsonl")
            ),
            "harBreakdownHash": (receipt or {}).get("breakdownHash"),
            "inputBoundaryHash": boundary.get("contentHash"),
        }
    )
    privacy = dict(_PRIVACY)
    for source in (boundary, receipt, source_manifest):
        for key in privacy:
            if key in source and isinstance(source.get(key), bool):
                privacy[key] = bool(source[key])
        if isinstance(source.get("privacy"), dict):
            for key in privacy:
                if key in source["privacy"] and isinstance(source["privacy"].get(key), bool):
                    privacy[key] = bool(source["privacy"][key])
    summary["privacy"] = privacy
    summary["contentHash"] = content_hash(summary)
    return summary


def _safe_claim(claim: dict[str, Any]) -> dict[str, Any]:
    """Drop accidental free-form/raw fields if an adapter ever supplies one."""
    forbidden = {"text", "raw", "body", "headers", "cookies", "authorization", "url"}

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): clean(item)
                for key, item in value.items()
                if str(key).strip().lower() not in forbidden
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(dict(claim))


def _step(label: str, fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 — receipt records typed step failure
        return {"name": label, "status": "FAILED", "error": _safe_error(exc)}
    summary: dict[str, Any] = {"name": label, "status": "COMPLETE"}
    if isinstance(result, dict):
        for key in (
            "valid",
            "complete",
            "selectedCount",
            "unresolvedCount",
            "requested",
            "completeRequests",
            "incompleteRequests",
            "documentCount",
            "indexHash",
            "blueprintHash",
        ):
            if key in result:
                summary[key] = result[key]
    return summary


def _write_terminal_artifacts(
    root: Path,
    *,
    composite_dest: Path | None,
    queue: dict[str, Any],
    claims: list[dict[str, Any]],
    board_offer_count: int,
    source_hashes: list[str],
    coverage: dict[str, Any],
    autonomous: dict[str, Any] | None = None,
) -> list[str]:
    queue_accounting = queue.get("accounting") if isinstance(queue, dict) else {}
    queue_accounting = queue_accounting if isinstance(queue_accounting, dict) else {}
    top100 = [dict(row) for row in (queue.get("top100") or []) if isinstance(row, dict)] if isinstance(queue, dict) else []
    top25 = [dict(row) for row in (queue.get("top25") or []) if isinstance(row, dict)] if isinstance(queue, dict) else []
    unresolved: list[dict[str, Any]] = []
    for claim in claims:
        reasons: list[str] = []
        if str(claim.get("disposition") or "") != "PLAYER_PROP_CANDIDATE":
            reasons.append(str(claim.get("disposition") or "UNSUPPORTED_INSIGHT"))
        if not bool(claim.get("paginationComplete")):
            reasons.append("PAGINATION_INCOMPLETE")
        if str(claim.get("harIdentityState") or "") not in {"", "VERIFIED_HAR_LOCAL"}:
            reasons.append(str(claim.get("harIdentityState") or "HAR_IDENTITY_UNRESOLVED"))
        if reasons:
            unresolved.append(
                {
                    "claimId": claim.get("claimId"),
                    "insightId": claim.get("insightId"),
                    "sourceHarSha256": claim.get("sourceHarSha256"),
                    "sourceBodyHash": claim.get("sourceBodyHash"),
                    "leagueId": claim.get("leagueId"),
                    "eventId": (claim.get("event") or {}).get("eventId"),
                    "subjectId": claim.get("subjectId"),
                    "reasons": sorted(set(reasons)),
                }
            )
    unresolved.sort(key=lambda row: (str(row.get("claimId") or ""), str(row.get("sourceHarSha256") or "")))

    paths = ["canonical_claims.jsonl", "unresolved_claims.jsonl", "research_queue_top100.json"]
    _write_jsonl(root / "canonical_claims.jsonl", (_safe_claim(row) for row in sorted(claims, key=lambda row: str(row.get("claimId") or ""))))
    _write_jsonl(root / "unresolved_claims.jsonl", unresolved)
    queue_artifact = {
        "schema": "pillars_dcm.research_queue_top100.v1",
        "queueVersion": queue.get("queueVersion") if isinstance(queue, dict) else None,
        "sourceHarSha256s": source_hashes,
        "rows": top100,
        "accounting": {
            "inputClaimCount": int(queue_accounting.get("inputClaimCount") or len(claims)),
            "queuedClaimCount": int(queue_accounting.get("queuedClaimCount") or len(top100)),
            "top100Count": len(top100),
            "top25Count": len(top25),
            "probabilityStatus": "NONE",
            "selectionStatus": "RESEARCH_ONLY",
            "productionSelectionPermitted": False,
        },
        "contentHash": None,
    }
    queue_artifact["contentHash"] = content_hash({k: v for k, v in queue_artifact.items() if k != "contentHash"})
    _write_json(root / "research_queue_top100.json", queue_artifact)

    packet_dir = root / "research_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    bridge = read_json(composite_dest / "insights_host_bridge.json") if composite_dest else {}
    bridge = bridge if isinstance(bridge, dict) else {}
    event_packets = [dict(row) for row in (bridge.get("eventPackets") or []) if isinstance(row, dict)]
    for packet in sorted(event_packets, key=lambda row: str(row.get("eventId") or row.get("contentHash") or "")):
        packet_hash = str(packet.get("contentHash") or content_hash(packet))
        packet.setdefault("contentHash", packet_hash)
        _write_json(packet_dir / f"event_{packet_hash}.json", packet)
        paths.append(f"research_packets/event_{packet_hash}.json")

    offer_doc_preview = insights_offer_snapshots(list(claims))
    insights_offer_count = int(offer_doc_preview.get("insightsOfferCount") or 0)
    insights_backed = bool(insights_offer_count)
    feature_snapshot = {
        "schema": "pillars_dcm.feature_snapshot.v1",
        "status": "RESEARCH_ONLY_INSIGHTS_OFFER_BACKED" if insights_backed else "ABSTAINED_NO_INSIGHTS_LINE_SIDE",
        "featureCount": 0,
        "inputClaimCount": len(claims),
        "boardOfferCount": int(board_offer_count),
        "insightsOfferCount": insights_offer_count,
        "probabilityStatus": "NONE",
        "reasonCodes": (
            ["INSIGHTS_OFFER_BACKED_RESEARCH_ONLY", "PRODUCTION_MODEL_GATES_NOT_MET"]
            if insights_backed
            else ["INSIGHTS_LINE_SIDE_MISSING", "PRODUCTION_MODEL_GATES_NOT_MET"]
        ),
        "boardHarRequired": False,
    }
    feature_snapshot["contentHash"] = content_hash(feature_snapshot)
    _write_json(root / "feature_snapshot.json", feature_snapshot)
    paths.append("feature_snapshot.json")

    prediction = {
        "schema": "pillars_dcm.prediction_candidates.v1",
        "status": "ABSTAINED",
        "rows": [],
        "productionSelectionPermitted": False,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "boardHarRequired": False,
        "reasonCodes": [
            "INSIGHTS_OFFER_BACKED_RESEARCH_ONLY" if insights_backed else "INSIGHTS_LINE_SIDE_MISSING",
            "NO_CALIBRATED_LABELS",
            "PREDICTIVE_CLAIM_NONE",
        ],
    }
    prediction["contentHash"] = content_hash(prediction)
    _write_json(root / "prediction_candidates.json", prediction)
    paths.append("prediction_candidates.json")

    offer_doc = offer_doc_preview
    _write_json(root / "insights_offer_snapshots.json", offer_doc)
    paths.append("insights_offer_snapshots.json")

    # Insights-backed Top25 remains populated when line+side exist even if boardOfferCount=0.
    insights_top25 = [dict(row) for row in top25 if row.get("offerBacking") == "INSIGHTS_OFFER_BACKED"]
    if not insights_top25:
        insights_top25 = list(top25)
    for row in insights_top25:
        row.setdefault("offerBacking", "INSIGHTS_OFFER_BACKED")
        row.setdefault("candidateClass", "RESEARCH_CANDIDATE")
        row["predictiveClaim"] = PREDICTIVE_CLAIM
        row["learningRevision"] = LEARNING_REVISION
        row["productionEligible"] = False
        row["probability"] = None

    top25_artifact = {
        "schema": "pillars_dcm.top25_research_preview.v1",
        "status": "RESEARCH_ONLY",
        "probabilityStatus": "NONE",
        "productionSelectionPermitted": False,
        "offerBacking": "INSIGHTS_OFFER_BACKED" if insights_top25 else ("CURRENT_OFFER_MISSING" if board_offer_count == 0 else "BOARD_OFFER"),
        "candidateClass": "RESEARCH_CANDIDATE",
        "boardOfferCount": int(board_offer_count),
        "insightsOfferCount": int(offer_doc.get("insightsOfferCount") or 0),
        "rows": insights_top25,
        "diversifiedRows": [dict(row) for row in (queue.get("diversifiedTop25") or []) if isinstance(row, dict)] if isinstance(queue, dict) else [],
        "predictiveClaim": PREDICTIVE_CLAIM,
        "learningRevision": LEARNING_REVISION,
        "boardHarRequired": False,
        "note": (
            "Insights line+side claims back research Top25 even when boardOfferCount=0. "
            "CURRENT_OFFER_MISSING is informational only when no Insights line+side exists. "
            "Playables remain fail-closed without a production model. Optional board HAR is not required."
        ),
    }
    top25_artifact["contentHash"] = content_hash(top25_artifact)
    _write_json(root / "top25.json", top25_artifact)
    paths.append("top25.json")

    playables = {
        "schema": "pillars_dcm.playables.v1",
        "count": 0,
        "ABSTAINED": True,
        "reason": "PRODUCTION_MODEL_GATES_NOT_MET" if insights_top25 else "INSIGHTS_LINE_SIDE_MISSING",
        "boardOfferCount": int(board_offer_count),
        "insightsTop25Count": len(insights_top25),
        "rows": [],
        "predictiveClaim": PREDICTIVE_CLAIM,
        "learningRevision": LEARNING_REVISION,
        "boardHarRequired": False,
        "note": "Playables may be 0 while Insights-backed Top25 is non-empty. Optional board HAR is not a blocker.",
    }
    playables["contentHash"] = content_hash(playables)
    _write_json(root / "playables.json", playables)
    paths.append("playables.json")

    line_buffer = (
        "status,reason,eligibleCount\n"
        + (
            "ABSTAINED,PRODUCTION_MODEL_GATES_NOT_MET,0\n"
            if insights_backed
            else "ABSTAINED,INSIGHTS_LINE_SIDE_MISSING,0\n"
        )
    )
    (root / "line_buffer_report.csv").write_text(line_buffer, encoding="utf-8")
    paths.append("line_buffer_report.csv")

    model_report = {
        "schema": "pillars_dcm.model_report.v1",
        "status": "NOT_RUN_RESEARCH_ONLY",
        "predictiveClaim": PREDICTIVE_CLAIM,
        "learningRevision": LEARNING_REVISION,
        "labels": {"settled": 0, "trainingEligible": 0},
        "calibration": {"status": "NOT_EARNED"},
        "coverage": {
            "requested": int(coverage.get("requested") or 0),
            "completeRequests": int(coverage.get("completeRequests") or 0),
            "incompleteRequests": int(coverage.get("incompleteRequests") or 0),
        },
        "reasonCodes": (
            ["INSIGHTS_OFFER_BACKED_RESEARCH_ONLY", "PRODUCTION_MODEL_GATES_NOT_MET"]
            if insights_backed
            else ["INSIGHTS_LINE_SIDE_MISSING", "PRODUCTION_MODEL_GATES_NOT_MET"]
        ),
        "boardHarRequired": False,
    }
    model_report["contentHash"] = content_hash(model_report)
    _write_json(root / "model_report.json", model_report)
    paths.append("model_report.json")

    settlement = dict((autonomous or {}).get("settlement") or {})
    if not settlement:
        settlement = {
            "schema": "pillars_dcm.settlement_queue.v1",
            "status": "AWAITING_AUTHORITATIVE_OUTCOMES",
            "claimCount": len(claims),
            "settledCount": 0,
            "trainingEligibleCount": 0,
            "exactIdentityRequired": True,
            "futureOnlyLearning": True,
            "outcomesInvented": False,
            "boardHarRequired": False,
            "outcomes": [],
        }
    settlement.setdefault("boardHarRequired", False)
    settlement.setdefault("outcomesInvented", False)
    settlement["contentHash"] = content_hash(settlement)
    _write_json(root / "settlement_queue.json", settlement)
    paths.append("settlement_queue.json")

    audit_lines = [
        "# DCM explicit-prompt slate audit",
        "",
        f"- Execution contract: `{SLATE_VERSION}`",
        f"- HAR sources: `{len(source_hashes)}`",
        f"- Canonical Insight claims: `{len(claims)}`",
        f"- Trusted current board offers: `{int(board_offer_count)}`",
        f"- Research queue Top 100: `{len(top100)}`",
        f"- Research preview Top 25: `{len(insights_top25)}` (Insights-offer-backed)",
        f"- Insights offer snapshots: `{int(offer_doc.get('insightsOfferCount') or 0)}`",
        "- Probability status: `NONE`",
        "- Production selection: `ABSTAINED` (playables may be 0)",
        "- Raw HAR/body/header/URL persistence: `FALSE`",
        "",
        "The queue is an attention allocator. Insights HARs with exact line+side "
        "are the platform capture; an optional board HAR is not a required next "
        "step. Playables remain fail-closed without evidence coverage, "
        "calibration, and the production-root gate. Do not invent outcomes.",
    ]
    (root / "audit_report.md").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
    paths.append("audit_report.md")
    return paths


def _legacy_run_slate(
    *,
    inputs: Iterable[Path],
    run_root: Path,
    prompt: Path,
    cutoff: str | None = None,
    cutoff_from_capture: bool = False,
    workspace: Path,
    research_shadow: bool = True,
    observations: Path | None = None,
    autonomous: bool = True,
    outcomes: Path | None = None,
) -> dict[str, Any]:
    """Run independent captures, the reconciled union, and HAR-only autonomous closure."""
    if not cutoff and not cutoff_from_capture:
        cutoff_from_capture = True
    ordered = _ordered_inputs(inputs)
    prompt_meta = _prompt_metadata(Path(prompt))
    root = Path(run_root)
    root.mkdir(parents=True, exist_ok=True)
    boundaries = {str(path.resolve()): inspect_input_boundary(path) for path in ordered}
    source_records: list[dict[str, Any]] = []
    source_claim_lists: list[list[dict[str, Any]]] = []
    successful_sources: list[Path] = []

    for order, path in enumerate(ordered, 1):
        session: HostSession | None = None
        error: dict[str, str] | None = None
        try:
            session = HostSession.prepare(
                har=path,
                run_root=root / "source_runs",
                cutoff=cutoff,
                cutoff_from_capture=cutoff_from_capture,
                workspace=Path(workspace),
                research_shadow=research_shadow,
            )
            successful_sources.append(path)
            source_claim_lists.append(_read_jsonl(session.dest / "insights_claims.jsonl"))
        except Exception as exc:  # noqa: BLE001 — continue accounting for remaining captures
            error = _safe_error(exc)
        source_records.append(
            _source_summary(path, session, boundaries[str(path.resolve())], processing_order=order, error=error)
        )

    composite_session: HostSession | None = None
    composite_error: dict[str, str] | None = None
    if successful_sources:
        try:
            composite_session = HostSession.prepare(
                input_paths=successful_sources,
                run_root=root / "composite_run",
                cutoff=cutoff,
                cutoff_from_capture=cutoff_from_capture,
                workspace=Path(workspace),
                research_shadow=research_shadow,
            )
        except Exception as exc:  # noqa: BLE001 — preserve source receipts if union fails
            composite_error = _safe_error(exc)
    else:
        composite_error = {"errorType": "RuntimeError", "code": "NO_SUCCESSFUL_HAR_CAPTURES"}

    source_hashes = [str(row.get("sha256") or "") for row in source_records if row.get("sha256")]
    union_hashes = [str(row.get("sha256") or "") for row in source_records if row.get("runId") and row.get("sha256")]
    merged_claims, merged_accounting = merge_insight_claims(source_claim_lists) if source_claim_lists else ([], {})
    queue: dict[str, Any] = {}
    board_offer_count = 0
    composite_summary: dict[str, Any] = {
        "status": "FAILED" if composite_error else "ACCOUNTED",
        "sourceHarSha256s": sorted(union_hashes),
        "error": composite_error,
    }
    steps: list[dict[str, Any]] = []
    coverage: dict[str, Any] = {}
    import_result: dict[str, Any] | None = None
    if composite_session is not None:
        queue = read_json(composite_session.dest / "insights_research_queue.json") or {}
        board = read_json(composite_session.dest / "board.json") or {}
        board_offer_count = len(board.get("rows") or []) if isinstance(board, dict) else 0
        composite_summary = _source_summary(
            Path("composite.har"),
            composite_session,
            {
                "name": "COMPOSITE_UNION",
                "sha256": read_json(composite_session.dest / "input_manifest.json").get("harSha256"),
                "sizeBytes": 0,
                "safeProjection": {"harEntryCount": 0},
                "contentHash": None,
            },
            processing_order=0,
        )
        composite_summary["status"] = "ACCOUNTED"
        composite_summary["sourceHarSha256s"] = sorted(union_hashes)
        composite_summary["contentHash"] = content_hash(composite_summary)

        steps.append(_step("INDEX", composite_session.index_build))
        steps.append(_step("SEARCH_BLUEPRINT", composite_session.search_blueprint))
        steps.append(_step("RESEARCH_QUEUE", lambda: composite_session.next_research_batch(max_entities=25)))
        steps.append(_step("COVERAGE", lambda: composite_session.coverage(select_next=False)))
        steps.append(_step("CHECKPOINT_VERIFY", composite_session.checkpoint_verify))
        coverage = read_json(composite_session.dest / "evidence_coverage.json") or {}
        if observations is not None:
            try:
                import_result = composite_session.import_evidence(Path(observations), select_next=True)
                steps.append(
                    {
                        "name": "EVIDENCE_IMPORT",
                        "status": "COMPLETE",
                        "imported": int(import_result.get("imported") or 0),
                        "rejected": int(import_result.get("rejected") or 0),
                    }
                )
                coverage = read_json(composite_session.dest / "evidence_coverage.json") or coverage
            except Exception as exc:  # noqa: BLE001 — evidence is optional and remains typed
                steps.append({"name": "EVIDENCE_IMPORT", "status": "FAILED", "error": _safe_error(exc)})
    else:
        steps.append({"name": "COMPOSITE", "status": "FAILED", "error": composite_error})

    canonical_claims = _read_jsonl(composite_session.dest / "insights_claims.jsonl") if composite_session else merged_claims
    canonical_claims = [_safe_claim(row) for row in canonical_claims]
    if not canonical_claims and merged_claims:
        canonical_claims = [_safe_claim(row) for row in merged_claims]
    if composite_session is not None and not coverage:
        coverage = read_json(composite_session.dest / "evidence_coverage.json") or {}
    if not isinstance(coverage, dict):
        coverage = {}

    if composite_session is not None:
        composite_manifest = read_json(composite_session.dest / "input_manifest.json") or {}
        composite_breakdown = read_json(composite_session.dest / "har_breakdown_manifest.json") or {}
        composite_boundary = read_json(composite_session.dest / "input_security_boundary.json") or {}
        composite_summary.update(
            {
                "filename": "COMPOSITE_UNION",
                "captureId": f"COMPOSITE:{composite_manifest.get('harSha256') or ''}",
                "sha256": composite_manifest.get("harSha256") or composite_summary.get("sha256"),
                "sportHint": "MIXED",
                "captureStart": min(
                    (str(row.get("captureStart") or "") for row in source_records if row.get("captureStart")),
                    default=None,
                ),
                "captureEnd": max(
                    (str(row.get("captureEnd") or "") for row in source_records if row.get("captureEnd")),
                    default=None,
                ),
                "entryCount": sum(int(row.get("entryCount") or 0) for row in source_records),
                "recordCount": sum(int(row.get("recordCount") or 0) for row in source_records),
                "insightClaimCount": len(canonical_claims),
                "queuedClaimCount": int((queue.get("accounting") or {}).get("queuedClaimCount") or 0),
                "top100Count": int((queue.get("accounting") or {}).get("top100Count") or 0),
                "top25Count": int((queue.get("accounting") or {}).get("top25Count") or 0),
                "paginationIncomplete": any(
                    not bool(row.get("paginationComplete")) for row in canonical_claims
                ),
                "harBreakdownHash": composite_breakdown.get("contentHash"),
                "inputBoundaryHash": composite_boundary.get("contentHash"),
            }
        )
        composite_summary["contentHash"] = content_hash(composite_summary)

    effective_cutoff = str(
        cutoff
        or composite_summary.get("captureEnd")
        or max(
            (str(row.get("captureEnd") or "") for row in source_records if row.get("captureEnd")),
            default="",
        )
        or ""
    ) or None
    execution_id = "SLATE_" + content_hash(
        {"prompt": prompt_meta["sha256"], "sources": sorted(source_hashes), "cutoff": effective_cutoff, "version": SLATE_VERSION}
    )[:16]

    census = {
        "schema": "pillars_dcm.har_census.v1",
        "executionVersion": SLATE_VERSION,
        "prompt": prompt_meta,
        "executionId": execution_id,
        "sourceCount": len(source_records),
        "sources": source_records,
        "union": {
            "runId": composite_session.dest.name if composite_session else None,
            "sourceHarSha256s": sorted(union_hashes),
            "canonicalClaimCount": len(canonical_claims),
            "sourceClaimCountSum": sum(len(rows) for rows in source_claim_lists),
            "changedOrDuplicateAccounting": merged_accounting,
            "boardOfferCount": int(board_offer_count),
            "reconciliationState": "RECONCILED" if composite_session and set(str(row.get("claimId") or "") for row in canonical_claims) == set(str(row.get("claimId") or "") for row in merged_claims) else "UNION_FALLBACK_OR_FAILED",
        },
        "privacy": dict(_PRIVACY),
        "contentHash": None,
    }
    census["contentHash"] = content_hash({k: v for k, v in census.items() if k != "contentHash"})
    _write_json(root / "har_census.json", census)

    queue_top25 = [row for row in ((queue.get("top25") or []) if isinstance(queue, dict) else []) if isinstance(row, dict)]
    insights_top25_count = len(
        [row for row in queue_top25 if row.get("offerBacking") == "INSIGHTS_OFFER_BACKED"] or queue_top25
    )
    research_queue_selected = 0
    for row in steps:
        if row.get("name") == "RESEARCH_QUEUE":
            research_queue_selected = int(row.get("selectedCount") or 0)
    offer_preview = insights_offer_snapshots(canonical_claims)
    insights_offer_count = int(offer_preview.get("insightsOfferCount") or 0)
    autonomous_doc: dict[str, Any] | None = None
    if autonomous:
        autonomous_doc = advance_autonomous_closure(
            session=composite_session,
            claims=canonical_claims,
            board_offer_count=board_offer_count,
            insights_offer_count=insights_offer_count,
            insights_top25_count=insights_top25_count,
            cutoff=effective_cutoff,
            observations_imported=observations is not None and import_result is not None,
            research_queue_selected=research_queue_selected,
            outcomes=Path(outcomes) if outcomes is not None else None,
        )
        _write_json(root / "autonomous_closure.json", autonomous_doc)
    else:
        autonomous_doc = {
            "schema": "pillars_dcm.autonomous_closure.v1",
            "enabled": False,
            "phaseOrder": list(AUTONOMOUS_PHASE_ORDER),
            "phases": [],
            "operatorContract": operator_contract(
                board_offer_count=board_offer_count,
                insights_offer_count=insights_offer_count,
                claim_count=len(canonical_claims),
            ),
            "deferredJobs": [],
            "boardHarRequired": False,
            "requiredOperatorAsks": [],
            "nextRequiredOperatorInput": "NONE",
            "predictiveClaim": PREDICTIVE_CLAIM,
            "learningRevision": LEARNING_REVISION,
        }

    _write_terminal_artifacts(
        root,
        composite_dest=composite_session.dest if composite_session else None,
        queue=queue,
        claims=canonical_claims,
        board_offer_count=board_offer_count,
        source_hashes=sorted(union_hashes),
        coverage=coverage,
        autonomous=autonomous_doc,
    )

    pipeline_gate = evaluate_insights_har_pipeline(
        context={
            "boardOfferCount": board_offer_count,
            "claimCount": len(canonical_claims),
            "top100Count": len((queue.get("top100") or []) if isinstance(queue, dict) else []),
            "top25Count": len((queue.get("top25") or []) if isinstance(queue, dict) else []),
            "consumer": "dcm.chat.slate.run_slate",
        }
    )
    _write_json(root / "pipeline_constitution_receipt.json", pipeline_gate)
    capability_manifest = {
        "schema": "pillars_dcm.capability_manifest.v1",
        "pipelineConstitutionId": PIPELINE_CONSTITUTION_ID,
        "activatedAlgorithmIds": list(pipeline_gate.get("activatedAlgorithmIds") or []),
        "stageOrder": list(pipeline_gate.get("stageOrder") or []),
        "valid": bool(pipeline_gate.get("valid")),
        "blockers": list(pipeline_gate.get("blockers") or []),
        "predictiveClaim": PREDICTIVE_CLAIM,
        "learningRevision": LEARNING_REVISION,
        "consumers": {
            str(row.get("stage")): row.get("consumer")
            for row in (pipeline_gate.get("stages") or [])
            if isinstance(row, dict)
        },
    }
    capability_manifest["contentHash"] = content_hash(capability_manifest)
    _write_json(root / "capability_manifest.json", capability_manifest)

    artifact_paths = [
        path for path in sorted(root.iterdir(), key=lambda path: path.name)
        if path.is_file() and path.name not in {"execution_receipt.json", "run_manifest.json"}
    ]
    artifact_paths.extend(sorted((root / "research_packets").glob("*.json")) if (root / "research_packets").is_dir() else [])
    artifact_hashes = {
        str(path.relative_to(root)): _sha256_file(path)
        for path in artifact_paths
        if path.is_file()
    }
    autonomous_phases = list((autonomous_doc or {}).get("phases") or [])
    settle_status = next((row.get("status") for row in autonomous_phases if row.get("name") == "SETTLE"), "AWAITING_AUTHORITATIVE_OUTCOMES")
    phase_status = [
        {"name": "PROMPT_AUDIT", "status": "COMPLETE", "promptSha256": prompt_meta["sha256"]},
        {"name": "ACCOUNT_EACH_HAR", "status": "COMPLETE" if all(row.get("status") == "ACCOUNTED" for row in source_records) else "PARTIAL"},
        {"name": "RECONCILE_UNION", "status": "COMPLETE" if composite_session else "FAILED"},
        *steps,
        {"name": "TOP100_RESEARCH_QUEUE", "status": "COMPLETE" if queue else "ABSTAINED"},
        {"name": "PREDICTION_AND_SELECTION", "status": "ABSTAINED", "reason": "NO_PRODUCTION_ELIGIBILITY", "boardHarRequired": False},
        {"name": "SETTLEMENT_AND_LEARNING", "status": settle_status, "boardHarRequired": False},
        *autonomous_phases,
    ]
    source_inventory_hash = census["contentHash"]
    receipt = {
        "schema": EXECUTION_RECEIPT_SCHEMA,
        "executionId": execution_id,
        "repository": "williamcgreenwood/DCM",
        "headSha": _repo_head(),
        "sourceInventoryHash": source_inventory_hash,
        "classification": "IMPLEMENTATION_INFERENCE" if composite_session else "EXTERNAL_BLOCKED",
        "implementation": {
            "status": "IMPLEMENTED",
            "requirementIds": [
                "R-HAR-ACCOUNTING",
                "R-INSIGHTS-TYPED",
                "R-RESEARCH-QUEUE",
                "R-PRIVACY-BOUNDARY",
                "R-INSIGHTS-HAR-PIPELINE-CONSTITUTION",
                "R-HAR-ONLY-AUTONOMOUS-CLOSURE",
            ],
            "pipelineConstitutionId": PIPELINE_CONSTITUTION_ID,
            "pipelineConstitutionHash": pipeline_gate.get("contentHash"),
            "activatedAlgorithmIds": list(pipeline_gate.get("activatedAlgorithmIds") or []),
            "changedFiles": [],
            "producerConsumerTests": ["index-build consumes insights_claims.jsonl", "pagination malformed/incomplete fails closed"],
        },
        "research": {
            "runId": composite_session.dest.name if composite_session else None,
            "batchId": None,
            "actions": {
                "completed": ["account_each_har", "reconcile_union", "build_research_queue", "autonomous_closure"],
                "pending": (
                    ["HOST_RESEARCH_OBSERVATIONS_IMPORT_PATH"]
                    if observations is None
                    else []
                ),
                "failed": [row.get("name") for row in phase_status if row.get("status") == "FAILED"],
                "reused": [],
            },
            "boardHarRequired": False,
            "observationCount": int((import_result or {}).get("imported") or 0),
            "importedClaimCount": int((import_result or {}).get("imported") or 0),
            "rejectedObservationCount": int((import_result or {}).get("rejected") or 0),
            "coverageBeforeHash": None,
            "coverageAfterHash": (
                coverage.get("contentHash") or content_hash(coverage)
                if coverage
                else None
            ),
            "conflictCount": int(merged_accounting.get("changedInsightIds") or 0),
        },
        "checkpoint": {
            "localPath": "composite_run/checkpoint.json" if composite_session else None,
            "checkpointHash": None,
            "parentHash": None,
            "outboxState": "LOCAL_ONLY",
            "remoteState": "NOT_CHECKED",
        },
        "verification": {
            "commands": ["dcm-host run-slate", "dcm-host index-build", "dcm-host checkpoint-verify"],
            "inventory": "PENDING",
            "policy": "PENDING",
            "ci": "PENDING",
        },
        "platform": {
            "workSurface": "AVAILABLE",
            "codexSurface": "AVAILABLE",
            "deepResearch": "AVAILABLE",
            "github": "PENDING_REMOTE_READBACK",
            "drive": "PENDING_REMOTE_READBACK",
            "approval": "NOT_REQUIRED",
        },
        "status": {
            "software": "IMPLEMENTED_PENDING_CI",
            "operational": "HAR_ACCOUNTING_ACCEPTED" if composite_session and all(row.get("status") == "ACCOUNTED" for row in source_records) else "EXTERNAL_BLOCKED",
            "recovery": "LOCAL_CHECKPOINT_VERIFIED" if any(
                row.get("name") == "CHECKPOINT_VERIFY" and row.get("valid") is True
                for row in phase_status
            ) else "LOCAL_CHECKPOINT_PENDING_VERIFICATION",
            "performance": "NOT_CERTIFIED",
            "predictive": "PREDICTIVE_NOT_EARNED",
            "universal": "PARTIAL",
        },
        "artifacts": artifact_hashes,
        "privacy": dict(_PRIVACY),
        "phaseStatus": phase_status,
        "autonomous": True if autonomous else False,
        "autonomousPhases": autonomous_phases,
        "autonomousPhaseOrder": list(AUTONOMOUS_PHASE_ORDER),
        "operatorContract": (autonomous_doc or {}).get("operatorContract"),
        "deferredJobs": list((autonomous_doc or {}).get("deferredJobs") or []),
        "boardHarRequired": False,
        "requiredOperatorAsks": [],
        "nextRequiredOperatorInput": "NONE",
        "contentHash": None,
    }
    if receipt_requires_board_har(receipt):
        raise RuntimeError("HAR_ONLY_CONTRACT_VIOLATION: execution receipt required a board HAR")
    receipt["contentHash"] = content_hash({k: v for k, v in receipt.items() if k != "contentHash"})
    _write_json(root / "execution_receipt.json", receipt)
    manifest = {
        "schema": SLATE_SCHEMA,
        "executionVersion": SLATE_VERSION,
        "executionId": execution_id,
        "prompt": prompt_meta,
        "cutoff": effective_cutoff,
        "cutoffFromCapture": bool(cutoff_from_capture),
        "sourceCount": len(source_records),
        "sourceRunIds": [row.get("runId") for row in source_records if row.get("runId")],
        "compositeRunId": composite_session.dest.name if composite_session else None,
        "executionReceiptHash": receipt["contentHash"],
        "artifactCount": len(artifact_hashes),
        "artifactPaths": sorted(artifact_hashes),
        "privacy": dict(_PRIVACY),
        "contentHash": None,
    }
    manifest["contentHash"] = content_hash({k: v for k, v in manifest.items() if k != "contentHash"})
    _write_json(root / "run_manifest.json", manifest)
    return {
        "schema": SLATE_SCHEMA,
        "executionId": execution_id,
        "runRoot": str(root),
        "sourceCount": len(source_records),
        "sources": source_records,
        "composite": composite_summary,
        "canonicalClaimCount": len(canonical_claims),
        "boardOfferCount": board_offer_count,
        "queueTop100Count": len((queue.get("top100") or []) if isinstance(queue, dict) else []),
        "queueTop25Count": len((queue.get("top25") or []) if isinstance(queue, dict) else []),
        "insightsOfferCount": int((read_json(root / "insights_offer_snapshots.json") or {}).get("insightsOfferCount") or 0),
        "pipelineConstitutionId": PIPELINE_CONSTITUTION_ID,
        "pipelineConstitutionValid": bool(pipeline_gate.get("valid")),
        "productionSelectionPermitted": False,
        "probabilityStatus": "NONE",
        "autonomous": bool(autonomous),
        "autonomousPhases": autonomous_phases,
        "boardHarRequired": False,
        "nextRequiredOperatorInput": "NONE",
        "executionReceipt": str(root / "execution_receipt.json"),
        "runManifest": str(root / "run_manifest.json"),
        "contentHash": manifest["contentHash"],
    }


def run_slate(
    *,
    inputs: Iterable[Path],
    run_root: Path,
    prompt: Path,
    cutoff: str | None = None,
    cutoff_from_capture: bool = False,
    workspace: Path,
    research_shadow: bool = True,
    observations: Path | None = None,
    autonomous: bool = True,
    outcomes: Path | None = None,
) -> dict[str, Any]:
    """Run the legacy producer and then apply the HAR-only closure controller."""
    ordered = internal_order(inputs)
    result = _legacy_run_slate(
        inputs=ordered,
        run_root=run_root,
        prompt=prompt,
        cutoff=cutoff,
        cutoff_from_capture=cutoff_from_capture,
        workspace=workspace,
        research_shadow=research_shadow,
        observations=observations,
        autonomous=autonomous,
        outcomes=outcomes,
    )
    return enhance_slate_result(Path(run_root), ordered, result)


__all__ = ["EXECUTION_RECEIPT_SCHEMA", "SLATE_SCHEMA", "SLATE_VERSION", "run_slate"]
