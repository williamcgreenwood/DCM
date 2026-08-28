"""HAR ingest spine: chunk-hash, sanitize, allowlist, latest-as-of, emit rows.

This is the v6 development adapter. It is NOT a hash-verified v5.4.1 decoder.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from dcm.ingest.outlier import parse_outlier_payload
from dcm.ingest.prizepicks import parse_prizepicks_payload
from dcm.ingest.sanitize import count_secrets, redact_headers, url_allowlisted, url_denied

PARSER_VERSION = "HAR_ADAPTER_V6_DEV_2026-08-28"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


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
    if not isinstance(text, str) or not text:
        return None
    enc = str(content.get("encoding") or "").lower()
    if enc == "base64":
        try:
            return base64.b64decode(text).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return None
    return text


def _index_har(obj: dict) -> tuple[list[dict], dict[str, int], list[str]]:
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
    }
    seen_body: dict[str, str] = {}
    indexed: list[dict] = []
    for ent in entries:
        if not isinstance(ent, dict):
            continue
        req = ent.get("request") if isinstance(ent.get("request"), dict) else {}
        res = ent.get("response") if isinstance(ent.get("response"), dict) else {}
        url = str(req.get("url") or "")
        method = str(req.get("method") or "GET").upper()
        started = str(ent.get("startedDateTime") or "")
        _, n_req = redact_headers(req.get("headers"))
        _, n_res = redact_headers(res.get("headers"))
        stats["secret_headers"] += n_req + n_res
        if url_denied(url):
            stats["denied_endpoints"] += 1
            continue
        if not url_allowlisted(url):
            continue
        stats["allowlisted_endpoints"] += 1
        status = int(res.get("status") or 0)
        if status < 200 or status >= 300:
            continue
        content = res.get("content") if isinstance(res.get("content"), dict) else {}
        body = _decode_content(content)
        if not body:
            continue
        stats["decoded_bodies"] += 1
        body_hash = sha256_text(body)
        if body_hash in seen_body:
            stats["duplicate_bodies"] += 1
        seen_body[body_hash] = started
        indexed.append({
            "url": url.split("?")[0],
            "method": method,
            "startedDateTime": started,
            "status": status,
            "bodyHash": body_hash,
            "body": body,
        })
    indexed.sort(key=lambda e: e["startedDateTime"])
    latest: dict[tuple[str, str], dict] = {}
    for e in indexed:
        latest[(e["method"], e["url"])] = e
    if not latest and entries:
        warnings.append("NO_ALLOWLISTED_MARKET_ENDPOINT")
    return list(latest.values()), stats, warnings


def _parse_payload(obj: Any) -> tuple[str, list[dict]] | None:
    pp = parse_prizepicks_payload(obj)
    if pp:
        return pp
    out = parse_outlier_payload(obj)
    if out:
        return out
    return None


def _merge_rows(batches: list[tuple[str, list[dict]]]) -> tuple[str, list[dict], int]:
    by_id: dict[str, dict] = {}
    adapter = "UNKNOWN"
    dup = 0
    for name, rows in batches:
        adapter = name
        for row in rows:
            pid = row["projectionId"]
            if pid in by_id:
                dup += 1
            by_id[pid] = row
    return adapter, list(by_id.values()), dup


def ingest_har(raw: Any, *, raw_bytes: bytes | None = None) -> dict[str, Any]:
    obj, text = _as_object(raw)
    har_sha256 = sha256_bytes(raw_bytes) if raw_bytes is not None else sha256_text(text)
    redacted = count_secrets(obj) if obj is not None else count_secrets(text)
    warnings: list[str] = []
    if redacted:
        warnings.append("Secrets detected in capture; redacted from persistence. Never replay HAR.")

    synthetic = isinstance(obj, dict) and isinstance(obj.get("_pillars"), dict) and obj["_pillars"].get("kind") == "SYNTHETIC_HAR"
    index_stats = {
        "raw_entries": 0,
        "denied_endpoints": 0,
        "allowlisted_endpoints": 0,
        "decoded_bodies": 0,
        "duplicate_bodies": 0,
        "secret_headers": 0,
    }
    capture_start = ""
    capture_end = ""
    batches: list[tuple[str, list[dict]]] = []
    parser = PARSER_VERSION
    adapter = "UNKNOWN"

    if isinstance(obj, dict) and isinstance(obj.get("log"), dict):
        indexed, index_stats, w = _index_har(obj)
        warnings.extend(w)
        times = [e["startedDateTime"] for e in indexed if e.get("startedDateTime")]
        capture_start = min(times) if times else ""
        capture_end = max(times) if times else ""
        for e in indexed:
            try:
                payload = json.loads(e["body"])
            except json.JSONDecodeError:
                warnings.append(f"NON_JSON_BODY:{e['url']}")
                continue
            parsed = _parse_payload(payload)
            if parsed:
                batches.append(parsed)
    elif obj is not None:
        parsed = _parse_payload(obj)
        if parsed:
            batches.append(parsed)

    if batches:
        adapter, rows, dup = _merge_rows(batches)
        index_stats["duplicate_projection_ids"] = dup
    else:
        rows = []
        warnings.append("UNKNOWN_HAR_SHAPE")

    if synthetic:
        adapter = "SYNTHETIC"
        parser = "HAR_SYNTHETIC_V1"

    if adapter == "UNKNOWN":
        parser = "HAR_UNKNOWN"

    redacted += index_stats.get("secret_headers", 0)

    return {
        "adapter": adapter,
        "parserVersion": parser,
        "harSha256": har_sha256,
        "rows": rows,
        "redactedSecrets": redacted,
        "warnings": warnings,
        "indexStats": index_stats,
        "captureStart": capture_start,
        "captureEnd": capture_end,
        "synthetic": synthetic,
        "v5Decoder": "NOT_MOUNTED",
    }
