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
            "scopeHash": sha256_text(f"{method}:{url}"),
            "method": method,
            "startedDateTime": started,
            "status": status,
            "bodyHash": body_hash,
            "body": body,
        })
    indexed.sort(key=lambda e: (e["startedDateTime"], e["method"], e["url"], e["bodyHash"]))
    if not indexed and entries:
        warnings.append("NO_ALLOWLISTED_MARKET_ENDPOINT")
    return indexed, stats, warnings


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
    """Parse every allowlisted snapshot and preserve per-projection history."""
    obj, text = _as_object(raw)
    har_sha256 = sha256_bytes(raw_bytes) if raw_bytes is not None else sha256_text(text)
    redacted = count_secrets(obj) if obj is not None else count_secrets(text)
    warnings: list[str] = []
    if redacted:
        warnings.append("Secrets detected in capture; redacted from persistence. Never replay HAR.")

    synthetic = isinstance(obj, dict) and isinstance(obj.get("_pillars"), dict) and obj["_pillars"].get("kind") == "SYNTHETIC_HAR"
    index_stats = {"raw_entries": 0, "denied_endpoints": 0, "allowlisted_endpoints": 0, "decoded_bodies": 0, "duplicate_bodies": 0, "secret_headers": 0}
    capture_start = capture_end = ""
    parser = PARSER_VERSION
    adapter = "UNKNOWN"
    histories: dict[str, list[dict]] = {}
    timeline: list[dict] = []

    def add_rows(rows: list[dict], *, snapshot: str, body_hash: str, scope: str) -> None:
        for row in rows:
            rec = dict(row)
            rec["sourceSnapshotTime"] = snapshot
            rec["sourceBodyHash"] = body_hash
            rec["requestScope"] = scope
            pid = str(rec["projectionId"])
            hist = histories.setdefault(pid, [])
            prior = hist[-1] if hist else None
            states = ["ADDED"] if prior is None else []
            if prior is not None:
                if prior.get("line") != rec.get("line"): states.append("LINE_CHANGED")
                if prior.get("modifier") != rec.get("modifier"): states.append("MODIFIER_CHANGED")
                if (prior.get("offeredHigher"), prior.get("offeredLower")) != (rec.get("offeredHigher"), rec.get("offeredLower")): states.append("SIDE_CHANGED")
                if prior.get("status") != rec.get("status"): states.append("STATUS_CHANGED")
                if not states: states = ["UNCHANGED"]
            timeline.append({"projectionId": pid, "snapshotTime": snapshot, "states": states,
                             "previousLine": prior.get("line") if prior else None, "currentLine": rec.get("line"),
                             "bodyHash": body_hash, "requestScope": scope})
            hist.append(rec)

    if isinstance(obj, dict) and isinstance(obj.get("log"), dict):
        indexed, index_stats, w = _index_har(obj)
        warnings.extend(w)
        times = [e["startedDateTime"] for e in indexed if e.get("startedDateTime")]
        capture_start = min(times) if times else ""
        capture_end = max(times) if times else ""
        last_hash_by_scope: dict[tuple[str, str], str] = {}
        for e in indexed:
            scope_key = (e["method"], e.get("scopeHash") or e["url"])
            if last_hash_by_scope.get(scope_key) == e["bodyHash"]:
                continue
            last_hash_by_scope[scope_key] = e["bodyHash"]
            try:
                payload = json.loads(e["body"])
            except json.JSONDecodeError:
                warnings.append(f"NON_JSON_BODY:{e['url']}")
                continue
            parsed = _parse_payload(payload)
            if parsed:
                adapter, batch = parsed
                add_rows(batch, snapshot=e["startedDateTime"], body_hash=e["bodyHash"], scope=str(e.get("scopeHash") or e["url"]))
    elif obj is not None:
        parsed = _parse_payload(obj)
        if parsed:
            adapter, batch = parsed
            add_rows(batch, snapshot="", body_hash=har_sha256, scope="DIRECT")

    rows = []
    for hist in histories.values():
        hist.sort(key=lambda r: (str(r.get("sourceSnapshotTime") or ""), str(r.get("sourceUpdatedAt") or ""), str(r.get("sourceBodyHash") or "")))
        rows.append(hist[-1])
    rows.sort(key=lambda r: str(r.get("projectionId")))
    index_stats["projection_snapshot_rows"] = sum(len(v) for v in histories.values())
    index_stats["unique_projection_ids"] = len(histories)
    index_stats["lineage_transitions"] = len(timeline)
    if not rows:
        warnings.append("UNKNOWN_HAR_SHAPE")
    missing_sides = sum(not r.get("offeredHigher") and not r.get("offeredLower") for r in rows)
    if missing_sides:
        warnings.append(f"{missing_sides} offers have no verified offered side and fail closed")
    if synthetic:
        adapter = "SYNTHETIC"
        parser = "HAR_SYNTHETIC_V2"
    if adapter == "UNKNOWN":
        parser = "HAR_UNKNOWN"
    redacted += index_stats.get("secret_headers", 0)
    return {"adapter": adapter, "parserVersion": parser, "harSha256": har_sha256,
            "rows": rows, "rowHistory": histories, "timeline": timeline,
            "redactedSecrets": redacted, "warnings": warnings, "indexStats": index_stats,
            "captureStart": capture_start, "captureEnd": capture_end,
            "synthetic": synthetic, "v5Decoder": "NOT_MOUNTED"}
