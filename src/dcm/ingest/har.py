"""HAR ingest spine: sanitize, classify request-scope attempts, preserve chronology.

The v6 adapter is intentionally fail-closed. It records only sanitized request
scope identities and decoded market payloads; auth/session material is never
persisted and HAR replay is not supported.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from dcm.ingest.composite import reconcile_scope_attempts
from dcm.ingest.outlier import parse_outlier_payload
from dcm.ingest.prizepicks import parse_prizepicks_payload
from dcm.ingest.sanitize import count_secrets, redact_headers, url_allowlisted, url_denied

PARSER_VERSION = "HAR_ADAPTER_V6_SCOPE_STATE_2026-08-29"

_VOLATILE_QUERY_KEYS = {
    "token", "access_token", "refresh_token", "auth", "authorization",
    "session", "session_id", "sid", "csrf", "csrf_token", "xsrf",
    "device", "device_id", "request_id", "requestid", "trace_id", "traceid",
    "nonce", "timestamp", "ts", "cache_bust", "cachebuster", "cb", "_",
    "visitor_id", "tracking_id",
}
_MARKET_PATH_TOKENS = ("projection", "market", "prop", "offer", "line")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def _is_volatile_query_key(key: str) -> bool:
    lowered = key.strip().lower()
    return lowered in _VOLATILE_QUERY_KEYS or lowered.startswith("utm_")


def canonical_request_scope(url: str, method: str = "GET") -> str:
    """Hash only response-population-defining request semantics.

    Query values are used only inside the hash and are never persisted.
    Volatile auth/session/tracking/cache-buster keys are excluded.
    """
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        host = f"{host}:{port}"
    path = quote(unquote(parsed.path or "/"), safe="/:@-._~")
    pairs = sorted(
        (str(k), str(v))
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_volatile_query_key(str(k))
    )
    payload = json.dumps(
        {
            "method": str(method or "GET").upper(),
            "scheme": scheme,
            "host": host,
            "path": path,
            "query": pairs,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return sha256_text(payload)


def _scope_path(url: str) -> str:
    return urlsplit(url).path or "/"


def _market_endpoint(url: str) -> bool:
    path = _scope_path(url).lower()
    return any(token in path for token in _MARKET_PATH_TOKENS)


def _as_object(raw: Any) -> tuple[Any, str]:
    if isinstance(raw, (bytes, bytearray)):
        text = bytes(raw).decode("utf-8", errors="replace")
        try:
            return json.loads(text), text
        except json.JSONDecodeError:
            return None, text
    if isinstance(raw, str):
        try:
            return json.loads(raw), raw
        except json.JSONDecodeError:
            return None, raw
    try:
        text = json.dumps(raw, ensure_ascii=True, separators=(",", ":"))
    except TypeError:
        text = str(raw)
    return raw, text


def _decode_content(content: dict) -> str | None:
    text = content.get("text")
    if not isinstance(text, str):
        return None
    enc = str(content.get("encoding") or "").lower()
    if enc == "base64":
        try:
            return base64.b64decode(text).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return None
    return text


def _attempt(
    *,
    scope: str,
    path: str,
    method: str,
    started: str,
    status: int,
    state: str,
    ordinal: int,
    source_hash: str,
    response_hash: str = "",
    rows: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "requestScope": scope,
        "scopePath": path,
        "method": method,
        "startedDateTime": started,
        "status": status,
        "state": state,
        "entryOrdinal": ordinal,
        "sourceHarSha256": source_hash,
        "responseHash": response_hash,
        "rows": rows or [],
    }


def _index_har(
    obj: dict,
    *,
    source_hash: str,
) -> tuple[list[dict], list[dict], dict[str, int], list[str]]:
    log = obj.get("log") if isinstance(obj.get("log"), dict) else {}
    entries = log.get("entries") if isinstance(log.get("entries"), list) else []
    warnings: list[str] = []
    stats = {
        "raw_entries": len(entries),
        "denied_endpoints": 0,
        "allowlisted_endpoints": 0,
        "decoded_bodies": 0,
        "duplicate_bodies": 0,
        "secret_headers": 0,
        "http_failures": 0,
        "decode_failures": 0,
        "schema_failures": 0,
        "verified_empty_responses": 0,
        "successful_nonempty_responses": 0,
    }
    seen_body: set[tuple[str, str]] = set()
    indexed: list[dict] = []
    attempts: list[dict] = []

    for ordinal, ent in enumerate(entries):
        if not isinstance(ent, dict):
            continue
        req = ent.get("request") if isinstance(ent.get("request"), dict) else {}
        res = ent.get("response") if isinstance(ent.get("response"), dict) else {}
        url = str(req.get("url") or "")
        method = str(req.get("method") or "GET").upper()
        started = str(ent.get("startedDateTime") or "")
        scope = canonical_request_scope(url, method)
        path = _scope_path(url)
        _, n_req = redact_headers(req.get("headers"))
        _, n_res = redact_headers(res.get("headers"))
        stats["secret_headers"] += n_req + n_res

        if url_denied(url):
            stats["denied_endpoints"] += 1
            attempts.append(
                _attempt(
                    scope=scope, path=path, method=method, started=started,
                    status=int(res.get("status") or 0), state="DENIED_SECURITY_SCOPE",
                    ordinal=ordinal, source_hash=source_hash,
                )
            )
            continue
        if not url_allowlisted(url) or not _market_endpoint(url):
            continue

        stats["allowlisted_endpoints"] += 1
        status = int(res.get("status") or 0)
        if status < 200 or status >= 300:
            stats["http_failures"] += 1
            attempts.append(
                _attempt(
                    scope=scope, path=path, method=method, started=started,
                    status=status, state="HTTP_FAILURE", ordinal=ordinal, source_hash=source_hash,
                )
            )
            continue

        content = res.get("content") if isinstance(res.get("content"), dict) else {}
        body = _decode_content(content)
        if body is None:
            stats["decode_failures"] += 1
            attempts.append(
                _attempt(
                    scope=scope, path=path, method=method, started=started,
                    status=status, state="DECODE_FAILURE", ordinal=ordinal, source_hash=source_hash,
                )
            )
            continue

        stats["decoded_bodies"] += 1
        body_hash = sha256_text(body)
        pair = (scope, body_hash)
        if pair in seen_body:
            stats["duplicate_bodies"] += 1
        seen_body.add(pair)
        indexed.append(
            {
                "requestScope": scope,
                "scopePath": path,
                "method": method,
                "startedDateTime": started,
                "status": status,
                "bodyHash": body_hash,
                "body": body,
                "entryOrdinal": ordinal,
            }
        )

    indexed.sort(
        key=lambda e: (
            e["startedDateTime"], e["method"], e["requestScope"],
            e["bodyHash"], e["entryOrdinal"],
        )
    )
    if not indexed and entries and not attempts:
        warnings.append("NO_ALLOWLISTED_MARKET_ENDPOINT")
    return indexed, attempts, stats, warnings


def _parse_payload(obj: Any) -> tuple[str, list[dict]] | None:
    pp = parse_prizepicks_payload(obj)
    if pp:
        return pp
    out = parse_outlier_payload(obj)
    if out:
        return out
    return None


def _verified_empty_payload(obj: Any, scope_path: str) -> bool:
    """An empty response clears a scope only when the market collection is explicit."""
    if not isinstance(obj, dict) or not _market_endpoint(scope_path):
        return False
    if "data" in obj and isinstance(obj.get("data"), list) and len(obj["data"]) == 0:
        return True
    for key in ("projections", "markets", "props", "offers", "lines"):
        if key in obj and isinstance(obj.get(key), list) and len(obj[key]) == 0:
            return True
    return False


def ingest_har(raw: Any, *, raw_bytes: bytes | None = None) -> dict[str, Any]:
    """Parse a HAR and retain every sanitized request-scope attempt."""
    obj, text = _as_object(raw)
    har_sha256 = sha256_bytes(raw_bytes) if raw_bytes is not None else sha256_text(text)
    redacted = count_secrets(obj) if obj is not None else count_secrets(text)
    warnings: list[str] = []
    if redacted:
        warnings.append("Secrets detected in capture; redacted from persistence. Never replay HAR.")

    synthetic = (
        isinstance(obj, dict)
        and isinstance(obj.get("_pillars"), dict)
        and obj["_pillars"].get("kind") == "SYNTHETIC_HAR"
    )
    index_stats = {
        "raw_entries": 0, "denied_endpoints": 0, "allowlisted_endpoints": 0,
        "decoded_bodies": 0, "duplicate_bodies": 0, "secret_headers": 0,
        "http_failures": 0, "decode_failures": 0, "schema_failures": 0,
        "verified_empty_responses": 0, "successful_nonempty_responses": 0,
    }
    capture_start = capture_end = ""
    parser = PARSER_VERSION
    adapter = "UNKNOWN"
    histories: dict[str, list[dict]] = {}
    timeline: list[dict] = []
    scope_attempts: list[dict[str, Any]] = []

    if isinstance(obj, dict) and isinstance(obj.get("log"), dict):
        indexed, initial_attempts, index_stats, w = _index_har(obj, source_hash=har_sha256)
        warnings.extend(w)
        scope_attempts.extend(initial_attempts)
        all_times = [
            str((e or {}).get("startedDateTime") or "")
            for e in (obj.get("log", {}).get("entries") or [])
            if isinstance(e, dict) and e.get("startedDateTime")
        ]
        capture_start = min(all_times) if all_times else ""
        capture_end = max(all_times) if all_times else ""

        for e in indexed:
            try:
                payload = json.loads(e["body"])
            except json.JSONDecodeError:
                index_stats["decode_failures"] += 1
                scope_attempts.append(
                    _attempt(
                        scope=e["requestScope"], path=e["scopePath"], method=e["method"],
                        started=e["startedDateTime"], status=e["status"], state="DECODE_FAILURE",
                        ordinal=e["entryOrdinal"], source_hash=har_sha256,
                        response_hash=e["bodyHash"],
                    )
                )
                continue

            parsed = _parse_payload(payload)
            if parsed:
                adapter_name, batch = parsed
                adapter = adapter_name
                tagged: list[dict] = []
                for row in batch:
                    rec = dict(row)
                    rec["sourceSnapshotTime"] = e["startedDateTime"]
                    rec["sourceBodyHash"] = e["bodyHash"]
                    rec["requestScope"] = e["requestScope"]
                    tagged.append(rec)
                    pid = str(rec["projectionId"])
                    hist = histories.setdefault(pid, [])
                    prior = hist[-1] if hist else None
                    states = ["ADDED"] if prior is None else []
                    if prior is not None:
                        if prior.get("line") != rec.get("line"):
                            states.append("LINE_CHANGED")
                        if prior.get("modifier") != rec.get("modifier"):
                            states.append("MODIFIER_CHANGED")
                        if (prior.get("offeredHigher"), prior.get("offeredLower")) != (
                            rec.get("offeredHigher"), rec.get("offeredLower")
                        ):
                            states.append("SIDE_CHANGED")
                        if prior.get("status") != rec.get("status"):
                            states.append("STATUS_CHANGED")
                        if not states:
                            states = ["UNCHANGED"]
                    timeline.append(
                        {
                            "projectionId": pid,
                            "snapshotTime": e["startedDateTime"],
                            "states": states,
                            "previousLine": prior.get("line") if prior else None,
                            "currentLine": rec.get("line"),
                            "bodyHash": e["bodyHash"],
                            "requestScope": e["requestScope"],
                        }
                    )
                    hist.append(rec)
                index_stats["successful_nonempty_responses"] += 1
                scope_attempts.append(
                    _attempt(
                        scope=e["requestScope"], path=e["scopePath"], method=e["method"],
                        started=e["startedDateTime"], status=e["status"],
                        state="SUCCESS_NONEMPTY", ordinal=e["entryOrdinal"],
                        source_hash=har_sha256, response_hash=e["bodyHash"], rows=tagged,
                    )
                )
            elif _verified_empty_payload(payload, e["scopePath"]):
                index_stats["verified_empty_responses"] += 1
                scope_attempts.append(
                    _attempt(
                        scope=e["requestScope"], path=e["scopePath"], method=e["method"],
                        started=e["startedDateTime"], status=e["status"],
                        state="SUCCESS_EMPTY_VERIFIED", ordinal=e["entryOrdinal"],
                        source_hash=har_sha256, response_hash=e["bodyHash"], rows=[],
                    )
                )
            else:
                index_stats["schema_failures"] += 1
                scope_attempts.append(
                    _attempt(
                        scope=e["requestScope"], path=e["scopePath"], method=e["method"],
                        started=e["startedDateTime"], status=e["status"],
                        state="SCHEMA_FAILURE", ordinal=e["entryOrdinal"],
                        source_hash=har_sha256, response_hash=e["bodyHash"],
                    )
                )

    elif obj is not None:
        parsed = _parse_payload(obj)
        if parsed:
            adapter, batch = parsed
            tagged = []
            for row in batch:
                rec = dict(row)
                rec["sourceSnapshotTime"] = ""
                rec["sourceBodyHash"] = har_sha256
                rec["requestScope"] = "DIRECT"
                tagged.append(rec)
                histories.setdefault(str(rec["projectionId"]), []).append(rec)
            scope_attempts.append(
                _attempt(
                    scope="DIRECT", path="DIRECT", method="DIRECT", started="", status=200,
                    state="SUCCESS_NONEMPTY", ordinal=0, source_hash=har_sha256,
                    response_hash=har_sha256, rows=tagged,
                )
            )

    reconciled = reconcile_scope_attempts(scope_attempts)
    rows = reconciled["rows"]
    for hist in histories.values():
        hist.sort(
            key=lambda r: (
                str(r.get("sourceSnapshotTime") or ""),
                str(r.get("sourceUpdatedAt") or ""),
                str(r.get("sourceBodyHash") or ""),
            )
        )

    index_stats["projection_snapshot_rows"] = sum(len(v) for v in histories.values())
    index_stats["unique_projection_ids"] = len(rows)
    index_stats["lineage_transitions"] = len(timeline)
    index_stats["request_scope_attempts"] = len(scope_attempts)
    index_stats["selected_request_scopes"] = len(reconciled["scopeState"])
    index_stats["failed_refreshes_retained"] = len(reconciled["failedRefreshes"])

    if not rows and not any(a["state"] == "SUCCESS_EMPTY_VERIFIED" for a in scope_attempts):
        warnings.append("UNKNOWN_HAR_SHAPE")
    missing_sides = sum(not r.get("offeredHigher") and not r.get("offeredLower") for r in rows)
    if missing_sides:
        warnings.append(f"{missing_sides} offers have no verified offered side and fail closed")
    if synthetic:
        adapter = "SYNTHETIC"
        parser = "HAR_SYNTHETIC_V2"
    if adapter == "UNKNOWN" and rows:
        parser = PARSER_VERSION
    elif adapter == "UNKNOWN" and not scope_attempts:
        parser = "HAR_UNKNOWN"

    redacted += index_stats.get("secret_headers", 0)
    return {
        "adapter": adapter,
        "parserVersion": parser,
        "harSha256": har_sha256,
        "rows": rows,
        "rowHistory": histories,
        "scopeAttempts": scope_attempts,
        "scopeState": reconciled["scopeState"],
        "failedRefreshes": reconciled["failedRefreshes"],
        "reconciliationHash": reconciled["reconciliationHash"],
        "timeline": timeline,
        "redactedSecrets": redacted,
        "warnings": warnings,
        "indexStats": index_stats,
        "captureStart": capture_start,
        "captureEnd": capture_end,
        "synthetic": synthetic,
        "v5Decoder": "NOT_MOUNTED",
    }
