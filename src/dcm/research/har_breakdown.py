"""Whole-HAR H0–H7 decomposition for the DCM research planner.

This is a structural analyzer, not a replay client.  It reads a supplied HAR,
derives safe topology and demand fingerprints, and writes a receipt that can
be used to reproduce the same batch plan.  Raw HAR data remains private to the
process and is never included in the receipt.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from dcm.algorithms.grouping import connected_components, tarjan_scc
from dcm.algorithms.searching import minhash_jaccard
from dcm.contracts.hashes import content_hash
from dcm.ingest.har import ingest_har
from dcm.research.har_records import build_record_units


BREAKDOWN_SCHEMA = "pillars_dcm.har_breakdown.v1"
RECEIPT_SCHEMA = "pillars_dcm.har_breakdown_receipt.v1"


class HarLimitError(ValueError):
    code = "HAR_LIMIT_EXCEEDED"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_parse_har(
    path: Path,
    *,
    max_bytes: int = 512_000_000,
    max_entries: int = 100_000,
    max_json_depth: int = 80,
) -> dict[str, Any]:
    """Read and validate a HAR without executing or persisting its content."""
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) > int(max_bytes):
        raise HarLimitError(f"{HarLimitError.code}:bytes")
    digest = _sha256(raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"HAR_JSON_INVALID:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("log"), dict):
        raise ValueError("HAR_LOG_REQUIRED")
    entries = parsed["log"].get("entries")
    if not isinstance(entries, list):
        raise ValueError("HAR_ENTRIES_REQUIRED")
    if len(entries) > int(max_entries):
        raise HarLimitError(f"{HarLimitError.code}:entries")
    depth = 0
    stack: list[tuple[Any, int]] = [(parsed, 1)]
    while stack:
        node, current = stack.pop()
        depth = max(depth, current)
        if depth > int(max_json_depth):
            raise HarLimitError(f"{HarLimitError.code}:nesting")
        if isinstance(node, dict):
            stack.extend((child, current + 1) for child in node.values())
        elif isinstance(node, list):
            stack.extend((child, current + 1) for child in node[:1000])
    version = str(parsed["log"].get("version") or "")
    if version and version not in {"1.2", "1.1"}:
        raise ValueError(f"HAR_VERSION_UNSUPPORTED:{version}")
    return {"object": parsed, "rawBytes": raw, "harSha256": digest, "entryCount": len(entries), "maxDepth": depth}


def _route_digest(entry: Mapping[str, Any]) -> str:
    request = entry.get("request") if isinstance(entry.get("request"), Mapping) else {}
    url = str(request.get("url") or "")
    parts = urlsplit(url)
    return content_hash({"method": str(request.get("method") or "GET").upper(), "scheme": parts.scheme, "host": parts.netloc, "path": parts.path})


def _capture_summary(parsed: Mapping[str, Any]) -> dict[str, Any]:
    entries = parsed.get("log", {}).get("entries", [])
    methods: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    routes: Counter[str] = Counter()
    starts: list[str] = []
    request_bodies = response_bodies = 0
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        req = entry.get("request") if isinstance(entry.get("request"), Mapping) else {}
        res = entry.get("response") if isinstance(entry.get("response"), Mapping) else {}
        methods[str(req.get("method") or "GET").upper()] += 1
        statuses[str(int(res.get("status") or 0))] += 1
        routes[_route_digest(entry)] += 1
        if entry.get("startedDateTime"):
            starts.append(str(entry["startedDateTime"]))
        post = req.get("postData") if isinstance(req.get("postData"), Mapping) else {}
        content = res.get("content") if isinstance(res.get("content"), Mapping) else {}
        if post.get("text") not in (None, ""):
            request_bodies += 1
        if content.get("text") not in (None, ""):
            response_bodies += 1
    return {
        "entryCount": len(entries),
        "methodCounts": dict(sorted(methods.items())),
        "statusCounts": dict(sorted(statuses.items())),
        "routeDigestCounts": dict(sorted(routes.items())),
        "requestBodyCount": request_bodies,
        "responseBodyCount": response_bodies,
        "captureStart": min(starts) if starts else None,
        "captureEnd": max(starts) if starts else None,
        "routeFamilyDigest": content_hash(sorted(routes.items())),
    }


def _relationships(units: list[dict[str, Any]]) -> dict[str, Any]:
    edges: set[tuple[str, str]] = set()
    by_entry: dict[int, list[str]] = defaultdict(list)
    by_identifier: dict[str, list[str]] = defaultdict(list)
    for unit in units:
        uid = str(unit["unitId"])
        by_entry[int(unit.get("entryOrdinal") or 0)].append(uid)
        for identifier in unit.get("identifierDigests") or []:
            by_identifier[str(identifier)].append(uid)
    for group in by_entry.values():
        group = sorted(set(group))
        for left, right in zip(group, group[1:]):
            edges.add((left, right))
    for group in by_identifier.values():
        group = sorted(set(group))
        if group:
            first = group[0]
            edges.update((first, other) for other in group[1:])
    node_ids = sorted({str(unit["unitId"]) for unit in units})
    components = connected_components(sorted(edges), nodes=node_ids)
    adjacency: dict[str, list[str]] = {node: [] for node in node_ids}
    for left, right in sorted(edges):
        adjacency[left].append(right)
        adjacency[right].append(left)
    if len(adjacency) <= 800:
        try:
            sccs = tarjan_scc(adjacency) if adjacency else []
            scc_algorithm = "TARJAN_RECURSIVE"
        except RecursionError:
            sccs = []
            scc_algorithm = "KOSARAJU_ITERATIVE_FALLBACK"
    else:
        sccs = []
        scc_algorithm = "KOSARAJU_ITERATIVE_FALLBACK"
    if not sccs and adjacency:
        # The repository Tarjan implementation is intentionally compact and
        # recursive.  Large HARs can form a long chain, so use an iterative
        # Kosaraju pass as the deterministic stack-safe fallback.
        reverse: dict[str, list[str]] = {node: [] for node in adjacency}
        for left, successors in adjacency.items():
            for right in successors:
                reverse.setdefault(right, []).append(left)
        visited: set[str] = set()
        order: list[str] = []
        for start in sorted(adjacency):
            if start in visited:
                continue
            stack: list[tuple[str, bool]] = [(start, False)]
            while stack:
                node, expanded = stack.pop()
                if expanded:
                    order.append(node)
                    continue
                if node in visited:
                    continue
                visited.add(node)
                stack.append((node, True))
                for nxt in reversed(sorted(set(adjacency.get(node, [])))):
                    if nxt not in visited:
                        stack.append((nxt, False))
        visited.clear()
        sccs = []
        for start in reversed(order):
            if start in visited:
                continue
            component: list[str] = []
            stack = [start]
            visited.add(start)
            while stack:
                node = stack.pop()
                component.append(node)
                for nxt in sorted(set(reverse.get(node, []))):
                    if nxt not in visited:
                        visited.add(nxt)
                        stack.append(nxt)
            sccs.append(sorted(component))
    clusters = []
    units_by_id = {str(unit["unitId"]): unit for unit in units}
    for component in components:
        families = Counter(str(units_by_id[uid].get("family") or "unknown") for uid in component if uid in units_by_id)
        clusters.append({"clusterDigest": content_hash(sorted(component)), "size": len(component), "familyCounts": dict(sorted(families.items()))})
    clusters.sort(key=lambda row: (-int(row["size"]), str(row["clusterDigest"])))
    return {
        "edgeCount": len(edges),
        "edgeDigest": content_hash(sorted(edges)),
        "nodeCount": len(node_ids),
        "connectedComponentCount": len(components),
        "sccCount": len(sccs),
        "sccAlgorithm": scc_algorithm,
        "fanoutClusters": clusters[:2000],
        "inference": "same-entry and shared-identifier topology; no semantic entity identity is asserted",
    }


def _demand_summary(board: Mapping[str, Any] | None, requests: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    request_rows = [dict(row) for row in (requests or []) if isinstance(row, Mapping)]
    by_action: dict[str, dict[str, Any]] = {}
    missing: Counter[str] = Counter()
    for req in request_rows:
        scope = str(req.get("scope") or "").upper()
        sid = str(req.get("scope_id") or req.get("scopeId") or "")
        action_digest = content_hash({"scope": scope, "scopeId": sid})
        record = by_action.setdefault(action_digest, {"actionDigest": action_digest, "scope": scope, "dependentOfferCount": 0, "requestCount": 0})
        record["dependentOfferCount"] += int(req.get("dependent_prop_count") or req.get("dependentOfferCount") or 0)
        record["requestCount"] += 1
        for field in req.get("knownMissing") or req.get("requiredFields") or []:
            missing[str(field)] += 1
    rows = board.get("rows") if isinstance(board, Mapping) else []
    offer_count = len(rows) if isinstance(rows, list) else 0
    action_rows = sorted(by_action.values(), key=lambda row: (str(row.get("scope")), str(row.get("actionDigest"))))
    return {
        "requestCount": len(request_rows),
        "actionCandidateCount": len(action_rows),
        "offerRowCount": offer_count,
        "actions": action_rows,
        "missingFieldCounts": dict(sorted(missing.items())),
        "fanoutDigest": content_hash(action_rows),
    }


def _canonical_record_summary(canonical: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize adapter-normalized records without persisting their values.

    JSON:API responses often wrap offer attributes in generic ``data`` objects,
    so shape-only extraction can correctly report many ``unknown`` raw units
    even though the trusted adapter has normalized thousands of board offers.
    Keep both views: raw topology for drift detection and canonical reference
    counts for the search planner.  Identifiers are counted and hashed only.
    """
    rows = [row for row in (canonical.get("rows") or []) if isinstance(row, Mapping)]

    def unique_digest(field: str) -> dict[str, Any]:
        values = {str(row.get(field)) for row in rows if row.get(field) not in (None, "")}
        return {"count": len(values), "digest": content_hash(sorted(values))}

    offer_rows = [row for row in rows if row.get("projectionId") not in (None, "")]
    return {
        "adapterRecordCount": len(rows),
        "canonicalOfferRowCount": len(offer_rows),
        "canonicalOfferId": unique_digest("projectionId"),
        "referencedEventId": unique_digest("eventId"),
        "referencedParticipantId": unique_digest("playerId"),
        "referencedTeamId": unique_digest("teamId"),
        "referencedMarket": unique_digest("market"),
        "normalizationNote": "counts and digests are derived in memory; canonical values are not persisted by the structural receipt",
    }


def build_har_breakdown(
    path: Path,
    *,
    run_id: str | None = None,
    prior: Mapping[str, Any] | None = None,
    board: Mapping[str, Any] | None = None,
    requests: list[Mapping[str, Any]] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    parsed_info = safe_parse_har(Path(path))
    parsed = parsed_info["object"]
    raw = parsed_info["rawBytes"]
    har_sha = str(parsed_info["harSha256"])
    canonical = ingest_har(parsed, raw_bytes=raw)
    record_doc = build_record_units(parsed)
    units = list(record_doc.get("units") or [])
    capture = _capture_summary(parsed)
    # Reuse the established adapter counts but do not copy body-bearing rows.
    canonical_stats = dict(canonical.get("indexStats") or {})
    schema_counts = dict(record_doc.get("schemaCounts") or {})
    family_counts = dict(record_doc.get("familyCounts") or {})
    drift = {
        "priorHarSha256": (prior or {}).get("har_sha256") or (prior or {}).get("harSha256"),
        "sameInput": bool(prior and str((prior or {}).get("har_sha256") or (prior or {}).get("harSha256") or "") == har_sha),
        "newSchemaFingerprints": sorted(set(schema_counts) - set((prior or {}).get("schema_fingerprints") or (prior or {}).get("schemaFingerprints") or {})),
        "routeFamilyChanged": bool(prior and (prior.get("capture") or {}).get("routeFamilyDigest") not in {None, capture["routeFamilyDigest"]}),
    }
    body: dict[str, Any] = {
        "schema": BREAKDOWN_SCHEMA,
        "schema_version": 1,
        "run_id": str(run_id or "") or None,
        "har_sha256": har_sha,
        "privacy": {
            "rawHarPersisted": False,
            "rawBodiesPersisted": False,
            "rawHeadersPersisted": False,
            "rawUrlsPersisted": False,
            "valuesPersisted": False,
            "identifierRepresentation": "sha256_digest_only",
            "secretHeaderCount": int(canonical.get("redactedSecrets") or 0),
        },
        "capture": {
            **capture,
            "canonicalAdapter": canonical.get("adapter"),
            "canonicalParserVersion": canonical.get("parserVersion"),
            "canonicalIndexStats": canonical_stats,
        },
        "schema_fingerprints": schema_counts,
        "record_families": {key: int(family_counts.get(key) or 0) for key in ("event", "matchup", "offer", "market", "participant", "team_or_side", "source_assertion", "unknown")},
        "canonical_record_summary": _canonical_record_summary(canonical),
        "relationships": _relationships(units),
        "research_demand": _demand_summary(board, requests),
        "drift": drift,
        "algorithmIds": ["ALG-INDEX-001", "ALG-INDEX-014", "ALG-GROUP-006", "ALG-SEARCH-013", "ALG-SEARCH-014", "ALG-SEARCH-015"],
        "recordDigest": record_doc.get("recordDigest"),
        "warnings": sorted({str(x) for x in (canonical.get("warnings") or [])}),
    }
    body["content_hash"] = content_hash({k: v for k, v in body.items() if k != "content_hash"})
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "runId": body["run_id"],
        "harSha256": har_sha,
        "breakdownHash": body["content_hash"],
        "recordCount": len(units),
        "entryCount": capture["entryCount"],
        "privacy": body["privacy"],
        "algorithmIds": body["algorithmIds"],
        "reproducible": True,
    }
    receipt["contentHash"] = content_hash(receipt)
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(body, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        output_path.with_name("har_breakdown_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return {"breakdown": body, "receipt": receipt}


__all__ = ["BREAKDOWN_SCHEMA", "HarLimitError", "RECEIPT_SCHEMA", "build_har_breakdown", "safe_parse_har"]
