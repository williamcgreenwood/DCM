"""Rights-aware append-only algorithm/method discovery records.

Records are stored under the caller's canonical ResearchStore root. A source is
not authorized for ingestion or training merely because it is recorded here.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qsl
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash

DISCOVERY_SCHEMA = "pillars_dcm.research_discovery.v1"
RIGHTS_STATES = frozenset({
    "DISCOVERY_ONLY", "RIGHTS_REVIEW_REQUIRED", "AUTHORIZED_RESEARCH",
    "AUTHORIZED_TRAINING", "PROHIBITED",
})
LIFECYCLE_STATES = frozenset({
    "CANDIDATE", "REVIEWED", "EXPERIMENTAL", "ADOPTED", "REJECTED",
    "DEFERRED", "RIGHTS_BLOCKED",
})
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _validate_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "candidateId", "title", "hypothesis", "sourceId", "sourceAuthority", "sourceUrl",
        "sourceContentSha256", "rightsState", "license", "rightsEvidence", "requiredData", "expectedBenefit", "possibleHarm",
        "experimentEvidence", "metricEvidence", "testReferences", "downstreamConsumer",
    )
    missing = [key for key in required if key not in candidate]
    if missing:
        raise ValueError("DISCOVERY_REQUIRED_FIELDS_MISSING:" + ",".join(missing))
    out = dict(candidate)
    if not str(out["candidateId"]).strip() or not str(out["title"]).strip():
        raise ValueError("DISCOVERY_ID_OR_TITLE_EMPTY")
    parsed_url = urlparse(str(out["sourceUrl"]))
    if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.username or parsed_url.password:
        raise ValueError("DISCOVERY_SOURCE_URL_MUST_USE_HTTPS")
    restricted_query_keys = {"key", "api_key", "token", "access_token", "auth", "signature", "sig"}
    if any(key.lower() in restricted_query_keys for key, _value in parse_qsl(parsed_url.query, keep_blank_values=True)):
        raise ValueError("DISCOVERY_SOURCE_URL_MUST_NOT_CONTAIN_CREDENTIALS")
    if not _SHA256.fullmatch(str(out["sourceContentSha256"])):
        raise ValueError("DISCOVERY_SOURCE_SHA256_INVALID")
    if out["rightsState"] not in RIGHTS_STATES:
        raise ValueError("DISCOVERY_RIGHTS_STATE_INVALID")
    if not isinstance(out["rightsEvidence"], dict):
        raise ValueError("DISCOVERY_RIGHTS_EVIDENCE_INVALID")
    if out["rightsState"] in {"AUTHORIZED_RESEARCH", "AUTHORIZED_TRAINING"}:
        evidence = out["rightsEvidence"]
        if not all(evidence.get(key) for key in ("reviewer", "reviewedAt", "evidenceUrl", "permittedUses")):
            raise ValueError("DISCOVERY_AUTHORIZATION_EVIDENCE_INCOMPLETE")
        permitted = set(evidence.get("permittedUses") or [])
        required_use = "training" if out["rightsState"] == "AUTHORIZED_TRAINING" else "research"
        if required_use not in permitted:
            raise ValueError("DISCOVERY_AUTHORIZATION_SCOPE_MISMATCH")
    if out.get("lifecycle", "CANDIDATE") not in LIFECYCLE_STATES:
        raise ValueError("DISCOVERY_LIFECYCLE_INVALID")
    for key in ("requiredData", "experimentEvidence", "metricEvidence", "testReferences"):
        if not isinstance(out[key], list):
            raise ValueError(f"DISCOVERY_FIELD_MUST_BE_LIST:{key}")
    if out.get("lifecycle") == "ADOPTED":
        if out["rightsState"] not in {"AUTHORIZED_RESEARCH", "AUTHORIZED_TRAINING"}:
            raise ValueError("DISCOVERY_ADOPTION_RIGHTS_NOT_AUTHORIZED")
        if not out["experimentEvidence"] or not out["metricEvidence"] or not out["testReferences"] or not out["downstreamConsumer"]:
            raise ValueError("DISCOVERY_ADOPTION_EVIDENCE_INCOMPLETE")
    return out


def append_discovery_event(store: Any, candidate: Mapping[str, Any], *, event_type: str = "UPSERT_CANDIDATE") -> dict[str, Any]:
    """Append an immutable discovery snapshot under an existing ResearchStore.

    The event ID is content-addressed for retry idempotency. Lifecycle changes
    create new snapshots; prior events remain available for audit/replay.
    """
    if event_type not in {"UPSERT_CANDIDATE", "LIFECYCLE_DECISION", "EXPERIMENT_RECORDED", "RIGHTS_REVIEW"}:
        raise ValueError("DISCOVERY_EVENT_TYPE_INVALID")
    body = _validate_candidate(candidate)
    event = {
        "schema": DISCOVERY_SCHEMA,
        "eventType": event_type,
        "candidate": body,
        "rightsState": body["rightsState"],
        "lifecycle": body.get("lifecycle", "CANDIDATE"),
    }
    event["contentHash"] = content_hash(event)
    path = store.indexes / "discovery_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Idempotent replay; index rows are immutable and old decisions are retained.
    if path.is_file():
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    prior = __import__("json").loads(line)
                    prior_hash = content_hash({k: v for k, v in prior.items() if k != "contentHash"})
                    if prior.get("contentHash") != prior_hash:
                        raise ValueError("DISCOVERY_EVENT_HASH_MISMATCH")
                    if prior.get("contentHash") == event["contentHash"]:
                        return event
    import json
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n")
    return event


def discovery_events(store: Any, *, candidate_id: str | None = None) -> list[dict[str, Any]]:
    """Read and integrity-check discovery history from a ResearchStore."""
    import json
    path = store.indexes / "discovery_events.jsonl"
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            expected = content_hash({k: v for k, v in row.items() if k != "contentHash"})
            if row.get("contentHash") != expected:
                raise ValueError("DISCOVERY_EVENT_HASH_MISMATCH")
            if candidate_id is None or row.get("candidate", {}).get("candidateId") == candidate_id:
                rows.append(row)
    return rows
