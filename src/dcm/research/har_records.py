"""Privacy-preserving record extraction from a HAR response topology.

The extractor profiles the entire HAR, including routes that are not admitted
to the production board.  It never emits a URL, header value, cookie, request
body, response body, player name, or token; all such values are used only for
in-memory classification and are represented by content digests in receipts.
"""
from __future__ import annotations

import base64
import json
import re
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from dcm.algorithms.searching import minhash_signature, simhash
from dcm.contracts.hashes import content_hash


RECORD_FAMILIES = ("offer", "event", "matchup", "market", "participant", "team_or_side", "source_assertion", "unknown")
_ID_KEYS = ("id", "uid", "uuid", "eventid", "event_id", "playerid", "player_id", "teamid", "team_id", "projectionid", "projection_id", "marketid", "market_id")
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def type_class(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "other"


def schema_paths(value: Any, *, max_depth: int = 6, max_paths: int = 2048) -> list[dict[str, Any]]:
    """Return bounded shape-only paths, not values."""
    out: list[dict[str, Any]] = []

    def walk(node: Any, path: tuple[str, ...], depth: int) -> None:
        if len(out) >= max_paths:
            return
        out.append({"path": ".".join(path) or "$", "type": type_class(node), "depth": depth})
        if depth >= max_depth:
            return
        if isinstance(node, dict):
            for key in sorted((str(k) for k in node), key=str)[:256]:
                walk(node.get(key), path + (key,), depth + 1)
        elif isinstance(node, list):
            # One representative shape is sufficient; cardinality is recorded
            # separately so repeated records cannot inflate the schema index.
            if node:
                walk(node[0], path + ("[]",), depth + 1)

    walk(value, (), 0)
    return out


def schema_fingerprint(value: Any) -> str:
    paths = schema_paths(value)
    return content_hash(paths)


def _keys(value: Mapping[str, Any]) -> set[str]:
    return {str(k).replace("-", "_").replace(" ", "_").lower() for k in value}


def record_family(value: Mapping[str, Any]) -> str:
    keys = _keys(value)
    text = " ".join(sorted(keys))
    if keys & {"projection", "projectionid", "projection_id", "offer", "line", "odds", "over_under", "overunder"}:
        return "offer"
    if keys & {"matchup", "fixture", "event", "eventid", "event_id", "game", "gameid", "game_id", "scheduled_start", "start_time"}:
        if keys & {"home", "away", "home_team", "away_team", "competitor", "competitors", "sides"}:
            return "matchup"
        return "event"
    if keys & {"player", "playerid", "player_id", "athlete", "athleteid", "athlete_id", "person", "roster", "position"}:
        return "participant"
    if keys & {"team", "teamid", "team_id", "home_team", "away_team", "opponent", "side", "competitor"}:
        return "team_or_side"
    if keys & {"market", "marketid", "market_id", "stat", "stat_type", "prop_type", "line", "over", "under"}:
        return "market"
    if keys & {"source", "source_id", "sourceurl", "source_url", "citation", "publishedat", "published_at", "updatedat", "updated_at"}:
        return "source_assertion"
    # A conservative token rule catches provider-specific names without
    # treating arbitrary objects as players or offers.
    if "market" in text or "prop" in text:
        return "market"
    return "unknown"


def _identifier_digests(value: Mapping[str, Any]) -> list[str]:
    result = []
    for key, raw in value.items():
        norm = str(key).replace("-", "_").replace(" ", "_").lower()
        if norm in _ID_KEYS or norm.endswith("_id") or norm.endswith("id"):
            if raw not in (None, "", [], {}):
                result.append(content_hash({"key": norm, "value": str(raw)}))
    return sorted(set(result))


def _decode_body(entry: Mapping[str, Any], *, max_body_bytes: int = 8_000_000) -> Any:
    response = entry.get("response") if isinstance(entry.get("response"), Mapping) else {}
    content = response.get("content") if isinstance(response.get("content"), Mapping) else {}
    text = content.get("text")
    if not isinstance(text, str) or len(text.encode("utf-8", "ignore")) > max_body_bytes:
        return None
    if content.get("encoding") == "base64":
        try:
            text = base64.b64decode(text, validate=False).decode("utf-8", "replace")
        except (ValueError, UnicodeError):
            return None
    if not text.strip() or not str(content.get("mimeType") or "").lower().find("json") >= 0:
        # Providers occasionally omit MIME types.  Only attempt JSON for text
        # that looks like an object/array; HTML remains unparsed.
        if text.lstrip()[:1] not in "[{":
            return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _walk_records(value: Any, *, max_depth: int = 7, max_records: int = 5000) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []

    def walk(node: Any, depth: int) -> None:
        if len(out) >= max_records or depth > max_depth:
            return
        if isinstance(node, dict):
            if node:
                out.append(node)
            for key in sorted(node, key=str):
                child = node[key]
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(node, list):
            for child in node:
                walk(child, depth + 1)

    walk(value, 0)
    return out


def _route_digest(entry: Mapping[str, Any]) -> str:
    request = entry.get("request") if isinstance(entry.get("request"), Mapping) else {}
    url = str(request.get("url") or "")
    parts = urlsplit(url)
    # Host/path are never returned; the digest permits route drift comparison.
    return content_hash({"method": str(request.get("method") or "GET").upper(), "scheme": parts.scheme, "host": parts.netloc, "path": parts.path})


def build_record_units(har: Mapping[str, Any], *, max_entries: int = 10000, max_records_per_entry: int = 5000) -> dict[str, Any]:
    entries = ((har.get("log") or {}).get("entries") or []) if isinstance(har.get("log"), Mapping) else []
    units: list[dict[str, Any]] = []
    schema_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    for entry_index, entry in enumerate(entries[:max_entries]):
        if not isinstance(entry, Mapping):
            continue
        route = _route_digest(entry)
        route_counts[route] += 1
        decoded = _decode_body(entry)
        if decoded is None:
            continue
        for ordinal, record in enumerate(_walk_records(decoded, max_records=max_records_per_entry)):
            family = record_family(record)
            shape = schema_fingerprint(record)
            tokens = sorted(set(_TOKEN_RE.findall(" ".join(str(k) for k in record.keys()).lower())))
            record_digest = content_hash(record)
            unit_identity = {"entry": entry_index, "ordinal": ordinal, "digest": record_digest}
            unit = {
                "unitId": f"RU_{content_hash(unit_identity)[:24]}",
                "entryOrdinal": entry_index,
                "recordOrdinal": ordinal,
                "routeDigest": route,
                "family": family,
                "recordDigest": record_digest,
                "identifierDigests": _identifier_digests(record),
                "schemaFingerprint": shape,
                "tokenSignature": {
                    "minhash": list(minhash_signature(tokens)),
                    "simhash": str(simhash(tokens)),
                },
                "fieldCount": len(record),
            }
            units.append(unit)
            schema_counts[shape] += 1
            family_counts[family] += 1
    units.sort(key=lambda row: str(row["unitId"]))
    return {
        "units": units,
        "familyCounts": dict(sorted(family_counts.items())),
        "schemaCounts": dict(sorted(schema_counts.items())),
        "routeCounts": dict(sorted(route_counts.items())),
        "recordCount": len(units),
        "recordDigest": content_hash(units),
    }


__all__ = ["RECORD_FAMILIES", "build_record_units", "record_family", "schema_fingerprint", "schema_paths", "type_class"]
