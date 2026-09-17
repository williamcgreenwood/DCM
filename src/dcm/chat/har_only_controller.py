"""HAR-only capture authority, bitemporal reconciliation, and slate closure."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from dcm.chat.state import read_json
from dcm.contracts.hashes import content_hash
from dcm.runtime.run_director import RunDirector


PRIVACY = {
    "rawHarPersisted": False,
    "rawBodiesPersisted": False,
    "rawHeadersPersisted": False,
    "rawUrlsPersisted": False,
    "rawArtifactsCommitted": False,
    "rawArtifactsUploaded": False,
    "freeFormInsightTextPersisted": False,
}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _har_times(path: Path) -> tuple[str, str]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "", ""
    entries = ((payload.get("log") or {}).get("entries") or []) if isinstance(payload, dict) else []
    values: list[datetime] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("startedDateTime") or "")
        if not raw:
            continue
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        values.append(value if value.tzinfo else value.replace(tzinfo=timezone.utc))
    if not values:
        return "", ""
    values.sort()
    return tuple(value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") for value in (values[0], values[-1]))


def _sport(name: str) -> str:
    upper = str(name).upper()
    for token in ("NCAAFB", "SOCCER", "WNBA", "NFL", "CFB", "NBA", "MLB", "NHL"):
        if re.search(rf"(?:^|[^A-Z]){token}(?:[^A-Z]|$)", upper):
            return token
    return "UNKNOWN"


def internal_order(inputs: Iterable[Path]) -> list[Path]:
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
    unique.sort(key=lambda path: (_har_times(path)[0] or "9999-12-31T23:59:59Z", path.name, _sha(path)))
    return unique


def _event_id(claim: Mapping[str, Any]) -> str:
    event = claim.get("event") if isinstance(claim.get("event"), Mapping) else {}
    return str(claim.get("eventId") or event.get("eventId") or event.get("id") or "")


def _subject_id(claim: Mapping[str, Any]) -> str:
    player = claim.get("player") if isinstance(claim.get("player"), Mapping) else {}
    return str(claim.get("subjectId") or claim.get("playerId") or claim.get("teamId") or player.get("id") or "")


def _status(claim: Mapping[str, Any]) -> str:
    event = claim.get("event") if isinstance(claim.get("event"), Mapping) else {}
    return str(claim.get("eventStatus") or event.get("status") or "").strip().upper().replace(" ", "_")


def _key(claim: Mapping[str, Any]) -> str:
    values = (
        str(claim.get("leagueId") or claim.get("league") or "").upper(),
        _event_id(claim),
        _subject_id(claim),
        str(claim.get("marketId") or "").upper(),
        str(claim.get("proposition") or claim.get("marketType") or "").upper(),
        str(claim.get("periodLabel") or "").upper(),
        str(claim.get("modifier") or "").upper(),
    )
    return "|".join(values) if any(values) else "UNRESOLVED|" + str(claim.get("insightId") or claim.get("claimId") or "UNKNOWN")


def _projection(claim: Mapping[str, Any], capture: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonicalClaimKey": _key(claim),
        "claimId": claim.get("claimId"),
        "claimHash": claim.get("claimHash"),
        "insightId": claim.get("insightId"),
        "league": claim.get("leagueId") or claim.get("league"),
        "eventId": _event_id(claim),
        "subjectId": _subject_id(claim),
        "marketId": claim.get("marketId"),
        "proposition": claim.get("proposition") or claim.get("marketType"),
        "periodLabel": claim.get("periodLabel"),
        "modifier": claim.get("modifier"),
        "line": claim.get("line"),
        "side": claim.get("direction") or claim.get("side"),
        "eventStatus": _status(claim),
        "evidenceHash": claim.get("sourceBodyHash") or claim.get("claimHash"),
        "sourceHarSha256": claim.get("sourceHarSha256") or capture.get("sha256"),
        "captureStart": capture.get("captureStart"),
        "captureEnd": capture.get("captureEnd"),
    }


def _change(old: Mapping[str, Any], new: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {
        "canonicalClaimKey": new.get("canonicalClaimKey") or old.get("canonicalClaimKey"),
        "old": old.get(field),
        "new": new.get(field),
        "oldClaimId": old.get("claimId"),
        "newClaimId": new.get("claimId"),
        "oldClaimHash": old.get("claimHash"),
        "newClaimHash": new.get("claimHash"),
        "oldCaptureStart": old.get("captureStart"),
        "newCaptureStart": new.get("captureStart"),
    }


def build_capture_diff(
    captures: Iterable[Mapping[str, Any]],
    claim_lists: Iterable[Iterable[Mapping[str, Any]]] = (),
) -> dict[str, Any]:
    rows = [dict(row) for row in captures if isinstance(row, Mapping)]
    lists = list(claim_lists)
    records: list[dict[str, Any]] = []
    for index, capture in enumerate(rows):
        records.append({
            "capture": capture,
            "claims": [dict(row) for row in (lists[index] if index < len(lists) else []) if isinstance(row, Mapping)],
        })
    records.sort(key=lambda row: (
        str(row["capture"].get("captureStart") or "9999-12-31T23:59:59Z"),
        str(row["capture"].get("sha256") or ""),
        str(row["capture"].get("filename") or ""),
    ))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record["capture"].get("sportHint") or "UNKNOWN").upper(), []).append(record)

    bitemporal: dict[str, dict[str, Any]] = {}
    exact: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        capture = record["capture"]
        for claim in record["claims"]:
            key = _key(claim)
            identity = "BITEMPORAL:" + content_hash(key)[:24]
            row = bitemporal.setdefault(identity, {
                "bitemporalClaimId": identity,
                "canonicalClaimKey": key,
                "firstSeen": None,
                "lastSeen": None,
                "captureCount": 0,
                "captureSha256s": [],
                "snapshots": [],
            })
            start = str(capture.get("captureStart") or "") or None
            if start and (row["firstSeen"] is None or start < row["firstSeen"]):
                row["firstSeen"] = start
            if start and (row["lastSeen"] is None or start > row["lastSeen"]):
                row["lastSeen"] = start
            sha = str(capture.get("sha256") or claim.get("sourceHarSha256") or "")
            if sha and sha not in row["captureSha256s"]:
                row["captureSha256s"].append(sha)
                row["captureCount"] += 1
            projection = _projection(claim, capture)
            sig = (sha, str(projection.get("claimHash") or projection.get("claimId") or ""))
            if sig not in {
                (str(item.get("sourceHarSha256") or ""), str(item.get("claimHash") or item.get("claimId") or ""))
                for item in row["snapshots"]
            }:
                row["snapshots"].append(projection)
            claim_hash = str(claim.get("claimHash") or claim.get("claimId") or "")
            if claim_hash:
                exact.setdefault(claim_hash, []).append({
                    "sha256": sha,
                    "claimId": claim.get("claimId"),
                    "captureStart": start,
                })
    for row in bitemporal.values():
        row["captureSha256s"] = sorted(row["captureSha256s"])
        row["snapshots"] = sorted(row["snapshots"], key=lambda item: (str(item.get("captureStart") or ""), str(item.get("claimId") or "")))

    duplicates: list[dict[str, Any]] = []
    by_sha: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_sha.setdefault(str(record["capture"].get("sha256") or ""), []).append(record)
    for sha, values in by_sha.items():
        if sha and len(values) > 1:
            duplicates.append({
                "relationship": "DUPLICATE_CAPTURE_BYTES",
                "sha256": sha,
                "filenames": sorted(str(value["capture"].get("filename") or "") for value in values),
                "captureIds": sorted(str(value["capture"].get("captureId") or "") for value in values),
            })
    duplicates.extend({
        "relationship": "EXACT_CLAIM_DUPLICATE",
        "claimHash": key,
        "occurrences": sorted(values, key=lambda value: (str(value.get("captureStart") or ""), str(value.get("sha256") or ""))),
    } for key, values in exact.items() if len({str(value.get("sha256") or "") for value in values}) > 1)

    supersessions: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for sport, values in sorted(grouped.items()):
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value in values:
            sha = str(value["capture"].get("sha256") or "")
            if sha in seen:
                continue
            seen.add(sha)
            unique.append(value)
        for old_record, new_record in zip(unique, unique[1:]):
            old_capture, new_capture = old_record["capture"], new_record["capture"]
            old_map = {_key(row): _projection(row, old_capture) for row in old_record["claims"]}
            new_map = {_key(row): _projection(row, new_capture) for row in new_record["claims"]}
            common = sorted(set(old_map) & set(new_map))
            line_changes = [_change(old_map[key], new_map[key], "line") for key in common if old_map[key].get("line") != new_map[key].get("line")]
            side_changes = [_change(old_map[key], new_map[key], "side") for key in common if old_map[key].get("side") != new_map[key].get("side")]
            status_changes = [_change(old_map[key], new_map[key], "eventStatus") for key in common if old_map[key].get("eventStatus") != new_map[key].get("eventStatus")]
            evidence_changes = [_change(old_map[key], new_map[key], "evidenceHash") for key in common if old_map[key].get("evidenceHash") != new_map[key].get("evidenceHash")]
            for key in common:
                if old_map[key].get("claimHash") != new_map[key].get("claimHash") or old_map[key].get("line") != new_map[key].get("line") or old_map[key].get("side") != new_map[key].get("side"):
                    supersessions.append({
                        "canonicalClaimKey": key,
                        "supersededClaimId": old_map[key].get("claimId"),
                        "supersedingClaimId": new_map[key].get("claimId"),
                        "supersededAt": old_map[key].get("captureStart"),
                        "supersedingAt": new_map[key].get("captureStart"),
                        "reason": "LATER_BITEMPORAL_SNAPSHOT",
                    })
            later_research = [row for row in new_map.values() if row.get("line") is not None and str(row.get("side") or "").upper() in {"HIGHER", "LOWER"}]
            board_count = int(new_capture.get("boardOfferCount") or 0)
            pairs.append({
                "sport": sport,
                "earlier": {key: old_capture.get(key) for key in ("captureId", "sha256", "captureStart")},
                "later": {key: new_capture.get(key) for key in ("captureId", "sha256", "captureStart")},
                "added": [new_map[key] for key in sorted(set(new_map) - set(old_map))],
                "removed": [old_map[key] for key in sorted(set(old_map) - set(new_map))],
                "lineChanges": line_changes,
                "sideChanges": side_changes,
                "eventStatusChanges": status_changes,
                "evidenceChanges": evidence_changes,
                "laterResearchUsable": bool(later_research),
                "laterResearchClaimCount": len(later_research),
                "laterOfferSnapshotUsable": board_count > 0,
                "laterProductionForecastUsable": False,
                "laterForecastBlocker": "OFFER_REVALIDATION_UNAVAILABLE" if board_count <= 0 else "MODEL_AND_EVIDENCE_GATES_NOT_EARNED",
            })

    body = {
        "schema": "pillars_dcm.capture_diff.v1",
        "temporalOrdering": "HAR_INTERNAL_STARTED_DATETIME",
        "filenameTimestampUsedForOrdering": False,
        "captureCount": len(records),
        "uniqueCaptureCount": len({str(row["capture"].get("sha256") or "") for row in records if row["capture"].get("sha256")}),
        "duplicateFileCount": sum(len(row.get("filenames") or []) - 1 for row in duplicates if row.get("relationship") == "DUPLICATE_CAPTURE_BYTES"),
        "timelines": [
            {
                "sport": sport,
                "captures": [
                    {key: value["capture"].get(key) for key in ("captureId", "sha256", "filename", "captureStart", "captureEnd", "claimCount")}
                    for value in values
                ],
            }
            for sport, values in sorted(grouped.items())
        ],
        "pairs": pairs,
        "bitemporalClaimCount": len(bitemporal),
        "bitemporalClaims": sorted(bitemporal.values(), key=lambda row: str(row.get("canonicalClaimKey") or "")),
        "duplicateRelationships": duplicates,
        "supersessionRelationships": sorted(supersessions, key=lambda row: (str(row.get("canonicalClaimKey") or ""), str(row.get("supersedingAt") or ""))),
        "privacy": dict(PRIVACY),
    }
    body["contentHash"] = content_hash(body)
    return body


def _read_claims(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _root_action(action: Mapping[str, Any], root: Path, composite: Path | None) -> dict[str, Any]:
    body = dict(action)
    body["operatorInputRequired"] = False
    body["noBoardHarAsk"] = True
    body["boardHarRequired"] = False
    if composite is not None:
        prefix = f"composite_run/{composite.name}"
        body["executionRunPath"] = prefix
        for key in ("packetPath", "responsePath"):
            value = str(body.get(key) or "")
            if value and not value.startswith("composite_run/") and not value.startswith(prefix + "/"):
                body[key] = f"{prefix}/{value}"
    body["contentHash"] = content_hash({key: value for key, value in body.items() if key != "contentHash"})
    return body


def _capability_matrix(claims: list[dict[str, Any]], board_count: int, autonomous: Mapping[str, Any], coverage: Mapping[str, Any], composite: Path | None) -> dict[str, Any]:
    phases = {str(row.get("name")): row for row in (autonomous.get("phases") or []) if isinstance(row, Mapping)}
    research = str((phases.get("RESEARCH") or {}).get("status") or "NOT_EXECUTED")
    settle = str((phases.get("SETTLE") or {}).get("status") or "NOT_EXECUTED")
    train = str((phases.get("TRAIN") or {}).get("status") or "NOT_EXECUTED")
    playables = str((phases.get("PLAYABLES") or {}).get("status") or "NOT_EXECUTED")
    complete = bool(coverage.get("complete"))
    names = [
        ("HAR", "dcm.ingest.har", "slate", "COMPLETE" if composite else "FAILED"),
        ("PER_FILE_ACCOUNTING", "dcm.runtime.input_boundary", "har_census.json", "COMPLETE" if composite else "PARTIAL"),
        ("EXTRACTION", "dcm.ingest.har", "insights_claims.jsonl", "COMPLETE" if claims else "NO_CLAIMS"),
        ("NORMALIZATION", "dcm.ingest.insights", "canonical_claims.jsonl", "COMPLETE" if claims else "NOT_EXECUTED"),
        ("IDENTITY_RESOLUTION", "dcm.ingest.insights", "insights_host_bridge.json", "COMPLETE" if claims else "NOT_EXECUTED"),
        ("EVENT_SCHEDULE_RESOLUTION", "dcm.research.insight_bridge", "insights_host_bridge.json", "COMPLETE" if claims else "NOT_EXECUTED"),
        ("MARKET_SEMANTICS", "dcm.research.insight_bridge", "insights_offer_snapshots.json", "RESEARCH_ONLY_CAPTURED" if claims else "NOT_EXECUTED"),
        ("OFFER_SNAPSHOT_INSIGHT_CLAIM", "dcm.research.insight_bridge", "insights_offer_snapshots.json", "COMPLETE_INSIGHTS_RESEARCH_ONLY" if claims else "NO_INSIGHTS_OFFERS"),
        ("INDEX_ARCHIVE", "dcm.chat.session.index_build", "search_index_receipt.json", "COMPLETE" if composite else "NOT_EXECUTED"),
        ("RESEARCH_PRIORITIZATION", "dcm.research.queue", "research_queue_top100.json", "COMPLETE" if claims else "NOT_EXECUTED"),
        ("RESEARCH_PACKET", "dcm.research.batch_store", "research_batches/*.json", "COMPLETE" if composite else "NOT_EXECUTED"),
        ("CHATGPT_RESEARCH_EXECUTION", "dcm.runtime.run_director", "next_action.json", "AWAITING_CHATGPT" if research == "AWAITING_HOST_OBSERVATIONS" else research),
        ("EVIDENCE_VALIDATION_IMPORT", "dcm.chat.session", "evidence_bundle.jsonl", "COMPLETE" if complete else "AVAILABLE_NOT_EXECUTED"),
        ("COVERAGE", "dcm.research.coverage", "evidence_coverage.json", "COMPLETE" if complete else "INCOMPLETE"),
        ("EVENTWORLD_FEATURES", "dcm.model.event_world_joint", "feature_snapshot.json", "COMPLETE" if complete else "BLOCKED_COVERAGE_INCOMPLETE"),
        ("SETTLEMENT", "dcm.learning.insight_settlement", "settlement_queue.json", settle),
        ("TRAINING_CALIBRATION", "dcm.learning.walkforward", "model_report.json", train),
        ("RANKING", "dcm.model.ranking", "top25.json", "READY_AFTER_MODEL" if train in {"SHADOW_EVALUATED", "CERTIFIED"} else "BLOCKED_MODEL"),
        ("SELECTION", "dcm.selection.card_layers", "playables.json", playables),
        ("FROZEN_PREDICTIONS", "dcm.runtime.freeze", "freeze.json", "COMPLETE" if playables == "SELECTED" else "NOT_EARNED"),
        ("AUTHORITATIVE_SETTLEMENT", "dcm.learning.postgame", "settlement.json", "READY" if settle == "SETTLED" else "DEFERRED_UNTIL_FINAL"),
        ("POSTGAME_LEARNING", "dcm.learning.registry", "CALIBRATION_STATE.json", "SHADOW_ONLY" if settle == "SETTLED" else "DEFERRED_UNTIL_SETTLEMENT"),
    ]
    blockers = []
    if board_count <= 0:
        blockers.append("OFFER_REVALIDATION_UNAVAILABLE")
    if not complete:
        blockers.append("EVIDENCE_COVERAGE_INCOMPLETE")
    if not (autonomous.get("model") or {}).get("modelPathAttempted"):
        blockers.append("MODEL_PATH_NOT_EXECUTED")
    blockers.append("PRODUCTION_ROOT_NOT_CERTIFIED")
    payload = {
        "schema": "pillars_dcm.capability_matrix.v1",
        "producerConsumerOrder": [row[0] for row in names],
        "stages": [
            {"stage": stage, "producer": producer, "consumer": consumer, "status": status, "claimCount": len(claims) if stage in {"EXTRACTION", "NORMALIZATION", "IDENTITY_RESOLUTION", "EVENT_SCHEDULE_RESOLUTION"} else None}
            for stage, producer, consumer, status in names
        ],
        "blockers": sorted(set(blockers)),
        "boardOfferCount": board_count,
        "insightsClaimCount": len(claims),
        "operatorInputRequired": False,
        "boardHarRequired": False,
        "predictiveClaim": "NONE",
    }
    payload["contentHash"] = content_hash(payload)
    return payload


def _closure_state(claims: list[dict[str, Any]], queue: Mapping[str, Any], coverage: Mapping[str, Any], autonomous: Mapping[str, Any], sources: list[Mapping[str, Any]], board_count: int, capture: Mapping[str, Any]) -> dict[str, Any]:
    phases = {str(row.get("name")): row for row in (autonomous.get("phases") or []) if isinstance(row, Mapping)}
    research = str((phases.get("RESEARCH") or {}).get("status") or "")
    settle = str((phases.get("SETTLE") or {}).get("status") or "")
    train = str((phases.get("TRAIN") or {}).get("status") or "")
    playable = phases.get("PLAYABLES") or {}
    selected = str(playable.get("status") or "") in {"SELECTED", "ABSTAINED_GATES_NOT_MET"}
    predictive = bool((autonomous.get("model") or {}).get("predictiveCertified"))
    root_certified = bool((autonomous.get("model") or {}).get("productionRootCertified"))
    blockers = set()
    if board_count <= 0:
        blockers.add("OFFER_REVALIDATION_UNAVAILABLE")
    if not coverage.get("complete"):
        blockers.add("EVIDENCE_COVERAGE_INCOMPLETE")
    if settle != "SETTLED":
        blockers.add("AUTHORITATIVE_OUTCOMES_PENDING")
    if not predictive:
        blockers.add("MODEL_NOT_CERTIFIED")
    if not root_certified:
        blockers.add("PRODUCTION_ROOT_NOT_CERTIFIED")
    body = {
        "schema": "pillars_dcm.closure_state.v1",
        "ENGINEERING_CLOSED": True,
        "HAR_ACCOUNTING_CLOSED": bool(sources) and all(row.get("status") == "ACCOUNTED" for row in sources),
        "INSIGHTS_CLOSED": bool(claims) and bool(queue),
        "RESEARCH_CLOSED": research in {"IMPORTED", "COMPLETE_NO_FURTHER_BATCH"} and bool(coverage.get("complete")),
        "SETTLEMENT_CLOSED": settle == "SETTLED",
        "MODEL_CLOSED": train in {"SHADOW_EVALUATED", "CERTIFIED"},
        "CURRENT_SLATE_SELECTION_CLOSED": selected,
        "DURABILITY_CLOSED": True,
        "PREDICTIVE_CERTIFIED": predictive,
        "PRODUCTION_ROOT_CERTIFIED": root_certified,
        "validAbstention": selected and str(playable.get("status") or "") != "SELECTED" and bool(playable.get("reason") or "OFFER_REVALIDATION_UNAVAILABLE"),
        "operatorInputRequired": False,
        "boardHarRequired": False,
        "captureAuthorityStatus": capture.get("status"),
        "playables": {"status": playable.get("status"), "count": int(playable.get("count") or 0), "reason": playable.get("reason")},
        "blockers": sorted(blockers),
        "explanation": "Insights line+side capture is valid research evidence. A zero board-offer count only means no exact /projections rows were observed; it never requests another HAR. Production playables remain zero until offer revalidation, evidence, settlement, calibration, and production-root gates are independently earned.",
    }
    body["contentHash"] = content_hash(body)
    return body


def enhance_slate_result(root: Path, inputs: Iterable[Path], result: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(root)
    census = read_json(root / "har_census.json") or {}
    raw_sources = [dict(row) for row in (census.get("sources") or []) if isinstance(row, Mapping)]
    metadata = {path.name: {"path": path, "sha256": _sha(path), "captureStart": _har_times(path)[0], "captureEnd": _har_times(path)[1], "sportHint": _sport(path.name)} for path in internal_order(inputs)}
    for row in raw_sources:
        info = metadata.get(str(row.get("filename") or ""))
        if info is None:
            info = next((value for value in metadata.values() if value["sha256"] == row.get("sha256")), None)
        if info is not None:
            row.update({
                "captureStart": info["captureStart"],
                "captureEnd": info["captureEnd"],
                "sportHint": row.get("sportHint") or info["sportHint"],
                "captureTimeAuthority": "HAR_INTERNAL_STARTED_DATETIME",
                "filenameTimestampUsedForOrdering": False,
            })
    raw_sources.sort(key=lambda row: (str(row.get("captureStart") or "9999-12-31T23:59:59Z"), str(row.get("sha256") or ""), str(row.get("filename") or "")))
    for index, row in enumerate(raw_sources, 1):
        row["processingOrder"] = index
    claims_by_source: list[list[dict[str, Any]]] = []
    for row in raw_sources:
        run_id = str(row.get("runId") or "")
        claims_by_source.append(_read_claims(root / "source_runs" / run_id / "insights_claims.jsonl"))
    unique_hashes = sorted({str(row.get("sha256") or "") for row in raw_sources if row.get("sha256")})
    canonical_claims = _read_claims(root / "composite_run" / str((read_json(root / "run_manifest.json") or {}).get("compositeRunId") or "") / "insights_claims.jsonl")
    if not canonical_claims:
        canonical_claims = _read_claims(root / "canonical_claims.jsonl")
    board = read_json(root / "composite_run" / str((read_json(root / "run_manifest.json") or {}).get("compositeRunId") or "") / "board.json") or {}
    board_count = len(board.get("rows") or []) if isinstance(board, dict) else int(result.get("boardOfferCount") or 0)
    queue = read_json(root / "composite_run" / str((read_json(root / "run_manifest.json") or {}).get("compositeRunId") or "") / "insights_research_queue.json") or {}
    coverage = read_json(root / "composite_run" / str((read_json(root / "run_manifest.json") or {}).get("compositeRunId") or "") / "evidence_coverage.json") or {}
    if not canonical_claims:
        canonical_claims = [dict(row) for row in (queue.get("top100") or []) if isinstance(row, Mapping)]
    diff = build_capture_diff(raw_sources, claims_by_source)
    _write(root / "har_census.json", {**census, "sourceCount": len(raw_sources), "sources": raw_sources, "union": {**(census.get("union") or {}), "sourceHarSha256s": unique_hashes, "canonicalClaimCount": len(canonical_claims), "boardOfferCount": board_count}, "contentHash": None})
    census = read_json(root / "har_census.json") or {}
    census["contentHash"] = content_hash({key: value for key, value in census.items() if key != "contentHash"})
    _write(root / "har_census.json", census)
    capture_authority = {
        "schema": "pillars_dcm.capture_authority.v1",
        "mode": "USER_SUPPLIED_CAPTURE",
        "status": "ACCEPTED" if raw_sources else "NOT_AVAILABLE",
        "authority": "USER_SUPPLIED" if raw_sources else "NONE",
        "accepted": bool(raw_sources),
        "sourceCount": len(raw_sources),
        "harCount": len(raw_sources),
        "sourceHarSha256s": unique_hashes,
        "freshnessPolicy": "OPERATOR_CONTROLLED",
        "replacementCaptureRequired": False,
        "replacementCaptureReason": None,
        "temporalPolicy": "LATEST_AS_OF_FORECAST_CUTOFF",
        "downstreamPolicy": "CONTINUE_RESEARCH_SETTLEMENT_MODEL_AND_CERTIFICATION_DIAGNOSTICS_UNTIL_OWN_GATES_TERMINATE",
        "note": "The supplied capture is accepted for this run. The operator decides when to rerun; this does not waive exact offer, authoritative settlement, calibration, or root gates.",
    }
    capture_authority["captureGateStatus"] = "PASS" if capture_authority["accepted"] else "FAIL_NO_AUTHORIZED_CAPTURE"
    capture_authority["contentHash"] = content_hash(capture_authority)
    _write(root / "capture_authority.json", capture_authority)
    _write(root / "capture_diff.json", diff)
    _write(root / "bitemporal_claims.json", {"schema": "pillars_dcm.bitemporal_claims.v1", "temporalOrdering": "HAR_INTERNAL_STARTED_DATETIME", "claims": diff.get("bitemporalClaims") or [], "count": diff.get("bitemporalClaimCount") or 0, "duplicateRelationships": diff.get("duplicateRelationships") or [], "supersessionRelationships": diff.get("supersessionRelationships") or [], "privacy": dict(PRIVACY), "contentHash": None})
    bitemporal = read_json(root / "bitemporal_claims.json") or {}
    bitemporal["contentHash"] = content_hash(bitemporal)
    _write(root / "bitemporal_claims.json", bitemporal)

    top25_path = root / "top25.json"
    top25 = read_json(top25_path) or {}
    rows = [dict(row) for row in (top25.get("rows") or []) if isinstance(row, Mapping)]
    insight_count = len([row for row in canonical_claims if row.get("line") is not None and str(row.get("direction") or "").upper() in {"HIGHER", "LOWER"}])
    for row in rows:
        # Only reclassify the Insights-only branch. A board-backed row must
        # remain available to the real model/ranking/selection consumers.
        if board_count <= 0 or row.get("offerBacking") == "INSIGHTS_OFFER_BACKED":
            row["offerBacking"] = "INSIGHTS_OFFER_BACKED"
            row["candidateClass"] = "RESEARCH_CANDIDATE"
            row["probability"] = None
            row["productionEligible"] = False
    if rows:
        top25.update({"status": "RESEARCH_ONLY", "rows": rows, "boardOfferCount": board_count, "insightsOfferCount": insight_count, "productionSelectionPermitted": False, "probabilityStatus": "NONE", "boardHarRequired": False})
        top25["contentHash"] = content_hash({key: value for key, value in top25.items() if key != "contentHash"})
        _write(root / "top25.json", top25)
    playables = read_json(root / "playables.json") or {}
    if board_count <= 0:
        playables.update({
            "count": 0,
            "ABSTAINED": True,
            "rows": [],
            "reason": "OFFER_REVALIDATION_UNAVAILABLE",
            "productionSelectionPermitted": False,
            "predictiveClaim": "NONE",
        })
    else:
        # Preserve a real selector's result. If it has not run, expose the
        # typed model/root gate instead of manufacturing a second zero path.
        playables.setdefault("count", len(playables.get("rows") or []))
        playables.setdefault("rows", [])
        playables.setdefault("reason", "PRODUCTION_MODEL_GATES_NOT_MET")
        playables["ABSTAINED"] = not bool(playables.get("rows"))
        playables["productionSelectionPermitted"] = bool(playables.get("productionSelectionPermitted"))
        playables.setdefault("predictiveClaim", "NONE")
    playables.update({"boardOfferCount": board_count, "insightsTop25Count": len(rows), "boardHarRequired": False})
    playables["contentHash"] = content_hash({key: value for key, value in playables.items() if key != "contentHash"})
    _write(root / "playables.json", playables)
    selection_permitted = bool(playables.get("productionSelectionPermitted"))
    feature = read_json(root / "feature_snapshot.json") or {}
    feature.update({"boardOfferCount": board_count, "insightsOfferCount": insight_count, "probabilityStatus": "NONE" if not selection_permitted else feature.get("probabilityStatus") or "AVAILABLE", "productionSelectionPermitted": selection_permitted, "reasonCodes": (["INSIGHTS_OFFER_BACKED_RESEARCH_ONLY", "OFFER_REVALIDATION_UNAVAILABLE"] if insight_count and board_count <= 0 else ["INSIGHTS_LINE_SIDE_MISSING", "OFFER_REVALIDATION_UNAVAILABLE"] if board_count <= 0 else ["PRODUCTION_MODEL_GATES_NOT_MET"] if not selection_permitted else []), "boardHarRequired": False})
    feature["contentHash"] = content_hash({key: value for key, value in feature.items() if key != "contentHash"})
    _write(root / "feature_snapshot.json", feature)

    manifest = read_json(root / "run_manifest.json") or {}
    composite_id = str(manifest.get("compositeRunId") or "")
    composite = root / "composite_run" / composite_id if composite_id else None
    action: dict[str, Any] = {}
    if composite is not None and composite.is_dir():
        try:
            action = dict(RunDirector(composite).status().get("nextAction") or {})
        except Exception:
            action = {}
    if not action:
        action = {"schema": "pillars_dcm.autonomous_next_action.v1", "type": "CHATGPT_RESEARCH_RESPONSE" if queue else "NONE", "owner": "CHATGPT" if queue else "DCM", "status": "READY" if queue else "TERMINAL", "operatorInputRequired": False, "noBoardHarAsk": True, "boardHarRequired": False, "nextCommand": "autonomous-resume"}
    action = _root_action(action, root, composite)
    _write(root / "next_action.json", action)
    autonomous = read_json(root / "autonomous_closure.json") or {}
    phases = [row for row in (autonomous.get("phases") or []) if isinstance(row, Mapping)]
    research_phase = next((row for row in phases if row.get("name") == "RESEARCH"), {})
    receipt = read_json(root / "execution_receipt.json") or {}
    receipt["nextAction"] = action
    receipt["boardHarRequired"] = False
    receipt["requiredOperatorAsks"] = []
    receipt["nextRequiredOperatorInput"] = "NONE"
    receipt.setdefault("research", {})["batchId"] = action.get("batchId")
    receipt["research"]["actions"] = {**(receipt.get("research", {}).get("actions") or {}), "pending": [] if research_phase.get("status") in {"IMPORTED", "COMPLETE_NO_FURTHER_BATCH"} else ["CHATGPT_RESEARCH_EXECUTION"]}
    receipt.setdefault("status", {})["universal"] = "COMPLETE_MIXED_SPORT_ROUTING" if composite else "PARTIAL"
    receipt["captureAuthority"] = capture_authority
    receipt["captureDiffPath"] = "capture_diff.json"
    receipt["bitemporalClaimsPath"] = "bitemporal_claims.json"
    receipt["capabilityMatrixPath"] = "capability_matrix.json"
    receipt["closureStatePath"] = "closure_state.json"
    receipt["contentHash"] = content_hash({key: value for key, value in receipt.items() if key != "contentHash"})
    _write(root / "execution_receipt.json", receipt)
    autonomous["nextAction"] = action
    _write(root / "autonomous_closure.json", autonomous)
    matrix = _capability_matrix(canonical_claims, board_count, autonomous, coverage if isinstance(coverage, Mapping) else {}, composite)
    _write(root / "capability_matrix.json", matrix)
    closure = _closure_state(canonical_claims, queue, coverage if isinstance(coverage, Mapping) else {}, autonomous, raw_sources, board_count, capture_authority)
    _write(root / "closure_state.json", closure)
    output = dict(result)
    model_state = autonomous.get("model") if isinstance(autonomous.get("model"), Mapping) else {}
    output.update({"sourceCount": len(raw_sources), "sources": raw_sources, "canonicalClaimCount": len(canonical_claims), "boardOfferCount": board_count, "insightsOfferCount": insight_count, "productionSelectionPermitted": selection_permitted, "probabilityStatus": "NONE" if not selection_permitted else "AVAILABLE", "modelPathAttempted": bool(model_state.get("modelPathAttempted")), "autonomous": True, "nextAction": action, "captureAuthority": capture_authority, "closureState": closure, "captureDiff": str(root / "capture_diff.json")})
    output["contentHash"] = content_hash({key: value for key, value in output.items() if key != "contentHash"})
    return output


__all__ = ["PRIVACY", "build_capture_diff", "enhance_slate_result", "internal_order"]
