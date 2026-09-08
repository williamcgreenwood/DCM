"""Machine-readable Work/Codex response envelopes and batch binding."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash
from dcm.research.batch_store import load_batch
from dcm.research.failures import EXCLUSION_SCOPES, FAILURE_CODES


RESPONSE_SCHEMA = "pillars_dcm.research_response.v1"


class ResponseEnvelopeError(ValueError):
    code = "RESEARCH_RESPONSE_INVALID"


def _rows(value: Any, *, field: str) -> list[dict[str, Any]]:
    rows = value.get(field) if isinstance(value, Mapping) else None
    if rows is None:
        return []
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:{field}_MUST_BE_OBJECT_LIST")
    return [dict(row) for row in rows]


def load_response(path: Path) -> dict[str, Any]:
    """Parse either the Work response object or legacy JSONL observations.

    The parser returns observations and failures separately while retaining
    only safe envelope metadata in its result.  Source URLs and claim values
    remain in memory for the canonical importer and are not echoed by this
    control-plane object.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        parsed: Any = []
    else:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            observations: list[dict[str, Any]] = []
            for number, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:JSONL_LINE_{number}") from exc
                if not isinstance(row, Mapping):
                    raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:JSONL_ROW_{number}_MUST_BE_OBJECT")
                observations.append(dict(row))
            parsed = observations

    metadata: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    if isinstance(parsed, Mapping) and ("observations" in parsed or "failures" in parsed or parsed.get("schema") == RESPONSE_SCHEMA):
        if parsed.get("schema") not in (None, RESPONSE_SCHEMA):
            raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:SCHEMA")
        observations = _rows(parsed, field="observations")
        failures = _rows(parsed, field="failures")
        for key in ("runId", "batchId", "batchContentSha", "checkpointSha", "searchBlueprintHash"):
            if parsed.get(key) not in (None, ""):
                metadata[key] = str(parsed[key])
        metadata["schema"] = str(parsed.get("schema") or RESPONSE_SCHEMA)
    elif isinstance(parsed, list):
        if any(not isinstance(row, Mapping) for row in parsed):
            raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:OBSERVATION_LIST")
        observations = [dict(row) for row in parsed]
    elif isinstance(parsed, Mapping):
        observations = [dict(parsed)]
    else:
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:ROOT")

    body = {
        "schema": metadata.get("schema"),
        "runId": metadata.get("runId"),
        "batchId": metadata.get("batchId"),
        "batchContentSha": metadata.get("batchContentSha"),
        "checkpointSha": metadata.get("checkpointSha"),
        "searchBlueprintHash": metadata.get("searchBlueprintHash"),
        "observations": observations,
        "failures": failures,
    }
    body["responseHash"] = content_hash(body)
    body["observationCount"] = len(observations)
    body["failureCount"] = len(failures)
    return body


def _active_envelope(run_dir: Path) -> dict[str, Any] | None:
    pointer_path = Path(run_dir) / "active_research_batch.json"
    if not pointer_path.is_file():
        return None
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if not isinstance(pointer, Mapping) or not pointer.get("batchId"):
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:ACTIVE_POINTER")
    batch_id = str(pointer["batchId"])
    envelope_path = Path(str(pointer.get("envelopePath") or Path(run_dir) / "research_batches" / f"{batch_id}.json"))
    if not envelope_path.is_absolute():
        envelope_path = Path(run_dir) / envelope_path
    envelope = load_batch(envelope_path)
    if str(pointer.get("batchContentSha") or "") != str(envelope.get("batchContentSha") or ""):
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:ACTIVE_POINTER_HASH")
    if str(pointer.get("searchBlueprintHash") or "") != str(envelope.get("searchBlueprintHash") or ""):
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:ACTIVE_POINTER_BLUEPRINT")
    return envelope


def validate_response_binding(response: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    """Fail closed when an explicit response envelope targets another batch."""
    response = dict(response)
    envelope = _active_envelope(Path(run_dir))
    strict = response.get("schema") == RESPONSE_SCHEMA
    explicit = strict or any(response.get(key) not in (None, "") for key in ("runId", "batchId", "batchContentSha", "checkpointSha", "searchBlueprintHash"))
    if strict:
        for key in ("runId", "batchId", "batchContentSha", "checkpointSha", "searchBlueprintHash"):
            if response.get(key) in (None, ""):
                raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:{key.upper()}_REQUIRED")
    if explicit:
        if envelope is None:
            raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:NO_ACTIVE_BATCH")
        if response.get("runId") not in (None, "", str(run_dir.name)):
            raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:RUN_MISMATCH")
        if str(response.get("batchId") or "") != str(envelope.get("batchId") or ""):
            raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:BATCH_MISMATCH")
        if response.get("batchContentSha") not in (None, "", str(envelope.get("batchContentSha") or "")):
            raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:BATCH_CONTENT_MISMATCH")
        if response.get("searchBlueprintHash") not in (None, "", str(envelope.get("searchBlueprintHash") or "")):
            raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:BLUEPRINT_MISMATCH")
        if strict and str(response.get("checkpointSha") or "") != str(envelope.get("parentCheckpointSha") or ""):
            raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:CHECKPOINT_MISMATCH")
    observation_mismatches: list[str] = []
    for index, observation in enumerate(response.get("observations") or []):
        if not isinstance(observation, Mapping):
            observation_mismatches.append(str(index))
            continue
        if observation.get("runId") not in (None, "", str(run_dir.name)):
            observation_mismatches.append(f"{index}:run")
        if envelope is not None and observation.get("batchId") not in (None, "", str(envelope.get("batchId") or "")):
            observation_mismatches.append(f"{index}:batch")
        if envelope is not None and observation.get("batchContentSha") not in (None, "", str(envelope.get("batchContentSha") or "")):
            observation_mismatches.append(f"{index}:content")
        if envelope is not None and observation.get("searchBlueprintHash") not in (None, "", str(envelope.get("searchBlueprintHash") or "")):
            observation_mismatches.append(f"{index}:blueprint")
    if observation_mismatches:
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:OBSERVATION_BINDING:{','.join(observation_mismatches[:20])}")
    response["bindingStatus"] = "BOUND" if explicit else "LEGACY_UNBOUND_COMPATIBILITY"
    response["boundBatchId"] = str(envelope.get("batchId")) if envelope else None
    return response


def validate_failure_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    action_id = str(row.get("actionId") or row.get("action_id") or "")
    code = str(row.get("code") or "").upper()
    scope = str(row.get("exclusionScope") or row.get("exclusion_scope") or "ATTEMPT_ONLY").upper()
    if not action_id:
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:FAILURE_ACTION_ID")
    if code not in FAILURE_CODES:
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:FAILURE_CODE:{code}")
    if scope not in EXCLUSION_SCOPES:
        raise ResponseEnvelopeError(f"{ResponseEnvelopeError.code}:FAILURE_SCOPE:{scope}")
    return {
        "actionId": action_id,
        "requestId": str(row.get("requestId") or row.get("request_id") or "") or None,
        "sourceId": str(row.get("sourceId") or row.get("source_id") or "") or None,
        "code": code,
        "retryable": bool(row.get("retryable")),
        "exclusionScope": scope,
        "missingFields": [str(value) for value in (row.get("missingFields") or row.get("missing_fields") or []) if str(value)],
        "sourceAttempts": [dict(value) for value in (row.get("sourceAttempts") or []) if isinstance(value, Mapping)],
        "safeReason": str(row.get("safeReason") or row.get("reason") or "")[:240] or None,
        "failureKey": str(row.get("failureKey") or row.get("failure_key") or "") or None,
    }


__all__ = ["RESPONSE_SCHEMA", "ResponseEnvelopeError", "load_response", "validate_failure_payload", "validate_response_binding"]
