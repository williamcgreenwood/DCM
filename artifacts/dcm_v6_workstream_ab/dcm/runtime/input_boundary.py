"""Sensitive-ingress accounting for HAR and other user-supplied inputs.

The raw bytes are accepted only at the local parser boundary.  This module
returns a summary that is safe to place in manifests, logs, checkpoints, or
remote audit stores: it contains hashes, counts, and marker *names*, never
header values, URLs with query values, response bodies, or raw bytes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash


INPUT_BOUNDARY_SCHEMA = "pillars_dcm.input_security_boundary.v1"
_SENSITIVE_HEADER_NAMES = {
    "authorization": "AUTHORIZATION",
    "cookie": "COOKIE",
    "set-cookie": "SET_COOKIE",
    "x-csrf-token": "CSRF_TOKEN",
    "x-xsrf-token": "CSRF_TOKEN",
    "proxy-authorization": "PROXY_AUTHORIZATION",
}
_SENSITIVE_MARKER_RE = re.compile(
    r"(?i)(set-cookie|authorization|bearer|csrf|session[-_ ]?token|api[-_ ]?key|password)"
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _header_marker(name: Any) -> str | None:
    token = str(name or "").strip().lower()
    if token in _SENSITIVE_HEADER_NAMES:
        return _SENSITIVE_HEADER_NAMES[token]
    if any(part in token for part in ("token", "secret", "password", "api-key", "apikey")):
        return "SENSITIVE_HEADER_NAME"
    return None


def _iter_headers(value: Any) -> Iterable[str]:
    if not isinstance(value, list):
        return ()
    return (
        marker
        for item in value
        if isinstance(item, Mapping)
        for marker in (_header_marker(item.get("name")),)
        if marker
    )


def _har_shape(raw: bytes) -> tuple[int, set[str], bool]:
    """Inspect only structure/marker classes; never return sensitive values."""
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 0, set(), bool(_SENSITIVE_MARKER_RE.search(raw.decode("utf-8", "ignore")))
    log = payload.get("log") if isinstance(payload, Mapping) else None
    entries = log.get("entries") if isinstance(log, Mapping) else None
    if not isinstance(entries, list):
        return 0, set(), bool(_SENSITIVE_MARKER_RE.search(raw.decode("utf-8", "ignore")))
    markers: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        request = entry.get("request") if isinstance(entry.get("request"), Mapping) else {}
        response = entry.get("response") if isinstance(entry.get("response"), Mapping) else {}
        markers.update(_iter_headers(request.get("headers")))
        markers.update(_iter_headers(request.get("queryString")))
        markers.update(_iter_headers(response.get("headers")))
    text = raw.decode("utf-8", "ignore")
    return len(entries), markers, bool(_SENSITIVE_MARKER_RE.search(text))


def inspect_input_boundary(path: Path, *, raw_bytes: bytes | None = None) -> dict[str, Any]:
    """Return a redacted, content-addressed input summary.

    ``raw_bytes`` lets the parser avoid a second read.  It is intentionally
    never retained in the returned object.
    """
    path = Path(path)
    raw = bytes(raw_bytes) if raw_bytes is not None else path.read_bytes()
    entries, header_markers, content_marker = _har_shape(raw)
    kind = "HAR" if path.suffix.lower() == ".har" or entries else "JSON"
    body: dict[str, Any] = {
        "schema": INPUT_BOUNDARY_SCHEMA,
        "name": path.name,
        "kind": kind,
        "sizeBytes": len(raw),
        "sha256": _sha256(raw),
        "quarantine": {
            "state": "LOCAL_QUARANTINED",
            "rawBytesNeverEmitted": True,
            "rawPathNeverRecorded": True,
            "replayAllowed": False,
        },
        "redaction": {
            "required": bool(header_markers or content_marker),
            "downstreamState": "SAFE_SUMMARY_ONLY",
            "sensitiveHeaderClasses": sorted(header_markers),
            "sensitiveContentMarkersPresent": bool(content_marker),
            "valuesOmitted": True,
        },
        "safeProjection": {
            "harEntryCount": entries,
            "rawArtifactCommitted": False,
            "rawArtifactUploaded": False,
        },
    }
    body["contentHash"] = content_hash(body)
    return body


def build_input_boundary_manifest(
    records: Iterable[Mapping[str, Any]],
    *,
    run_id: str,
    har_sha256: str,
) -> dict[str, Any]:
    safe_records = [dict(record) for record in records if isinstance(record, Mapping)]
    body: dict[str, Any] = {
        "schema": INPUT_BOUNDARY_SCHEMA,
        "runId": str(run_id),
        "harSha256": str(har_sha256),
        "records": safe_records,
        "rawArtifactsCommitted": False,
        "rawArtifactsUploaded": False,
        "rawArtifactsLogged": False,
        "rawBytesNeverEmitted": True,
        "rawPathNeverRecorded": True,
        "replayAllowed": False,
        "safeSummaryOnly": True,
    }
    body["contentHash"] = content_hash(body)
    return body


def persist_input_boundary_manifest(dest: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payload = dict(manifest)
    (dest / "input_security_boundary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return payload


__all__ = [
    "INPUT_BOUNDARY_SCHEMA",
    "build_input_boundary_manifest",
    "inspect_input_boundary",
    "persist_input_boundary_manifest",
]
