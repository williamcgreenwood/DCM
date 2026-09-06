"""Content-addressed persistent research store with delta classification.

Historical evidence is append-oriented. Volatile current context is refreshed.
Prediction outcomes never decide whether research is reused.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.scopes import canonical_scope

STORE_SCHEMA = "pillars_dcm.research_store.v1"
OUTCOME_SCHEMA = "pillars_dcm.forecast_outcome_memory.v1"

DELTA_CLASSES = (
    "REUSE_VALID",
    "REFRESH_STALE",
    "APPEND_MISSING_HISTORY",
    "REFRESH_CURRENT_CONTEXT",
    "NEW_OPPONENT_REQUIRED",
    "ROLE_EPOCH_CHANGED",
    "TEAM_CHANGED",
    "DEFINITION_CHANGED",
    "CONTRADICTED_REVERIFY",
    "REPLACE_INVALIDATED",
    "NEW_ENTITY_FULL_RESEARCH",
    "RESEARCH_NEW",
    "NOT_APPLICABLE",
)

VOLATILE_TYPES = frozenset({
    "status",
    "availability",
    "lineup",
    "weather",
    "injury",
    "starters",
    "CURRENT_STATUS",
    "CURRENT_CONTEXT",
})
HISTORICAL_TYPES = frozenset({
    "HISTORICAL_PERFORMANCE",
    "game_logs",
    "team_logs",
    "season_stats",
    "role_epoch_logs",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _asof_day(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return "unknown"


def game_identity(log: dict[str, Any]) -> str:
    """Stable sport-agnostic identity for one completed event log row."""
    event = str(log.get("eventId") or log.get("event_id") or log.get("gameId") or "")
    if event:
        return f"event:{event}"
    date = str(log.get("date") or log.get("game_date") or log.get("gameDate") or "")[:10]
    opp = str(log.get("opponent") or log.get("opp") or log.get("counterpartyId") or "")
    if date:
        return f"date:{date}:opp:{opp}"
    return "hash:" + content_hash({k: log[k] for k in sorted(log) if k != "raw"})[:16]


def extract_game_logs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if "claim" in payload and isinstance(payload.get("claim"), dict):
            return extract_game_logs(payload["claim"])
        value = payload.get("claim_value") if isinstance(payload.get("claim_value"), dict) else payload
        logs = value.get("game_logs") or value.get("gameLogs") or value.get("role_epoch_logs") or []
        return [r for r in logs if isinstance(r, dict)] if isinstance(logs, list) else []
    return []



def preserve_historical_support_fields(
    target: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    """Copy already-observed historical support into a claim_value that omits it.

    Never invents logs — only preserves non-empty fields already stored on a
    prior claim_value (game_logs, priorSeason_*, opportunity/efficiency support).
    Destination keys win when already populated.
    """
    if not isinstance(target, dict):
        target = {}
    if not isinstance(source, dict):
        return dict(target)
    out = dict(target)

    if not extract_game_logs(out):
        logs = extract_game_logs(source)
        if logs:
            if "game_logs" in source or "gameLogs" not in source:
                out["game_logs"] = list(logs)
            else:
                out["gameLogs"] = list(logs)
        role_logs = source.get("role_epoch_logs")
        if isinstance(role_logs, list) and role_logs and not out.get("role_epoch_logs"):
            out["role_epoch_logs"] = list(role_logs)

    for key, value in source.items():
        key_s = str(key)
        if not (key_s.startswith("priorSeason") or key_s.startswith("game_logs_sample")):
            continue
        if key in out and out.get(key) not in (None, "", [], {}):
            continue
        if value in (None, "", [], {}):
            continue
        out[key] = value

    for key in ("opportunity", "efficiency"):
        src = source.get(key)
        if not isinstance(src, dict) or not src:
            continue
        dst = out.get(key)
        if not isinstance(dst, dict) or not dst:
            out[key] = dict(src)
            continue
        merged = dict(src)
        merged.update({k: v for k, v in dst.items() if v not in (None, "", [], {})})
        for sk, sv in src.items():
            if sk not in merged or merged.get(sk) in (None, "", [], {}):
                merged[sk] = sv
        out[key] = merged

    return out


def enrich_claim_value_from_prior_records(
    claim: dict[str, Any],
    store: "ResearchStore",
    *,
    scope: str,
    scope_id: str,
) -> dict[str, Any]:
    """Return a shallow-copied claim whose claim_value keeps prior historical support."""
    if not isinstance(claim, dict):
        return claim
    out = dict(claim)
    value = out.get("claim_value") if isinstance(out.get("claim_value"), dict) else {}
    value = dict(value)
    needs_logs = not extract_game_logs(value)
    needs_prior_season = not any(str(k).startswith("priorSeason") for k in value)
    needs_support = not (
        isinstance(value.get("opportunity"), dict) and value.get("opportunity")
    ) and not (
        isinstance(value.get("efficiency"), dict) and value.get("efficiency")
    )
    if not (needs_logs or needs_prior_season or needs_support):
        return out

    records = store.records_for(scope, scope_id) if store is not None else []
    # Newest-first so we prefer the most recent prior blob that still carries history.
    for rec in reversed(list(records or [])):
        if not isinstance(rec, dict):
            continue
        prior_claim = rec.get("claim") if isinstance(rec.get("claim"), dict) else None
        if not isinstance(prior_claim, dict):
            continue
        prior_hash = str(prior_claim.get("claim_hash") or rec.get("contentHash") or "")
        self_hash = str(out.get("claim_hash") or "")
        if prior_hash and self_hash and prior_hash == self_hash:
            continue
        prior_value = prior_claim.get("claim_value") if isinstance(prior_claim.get("claim_value"), dict) else {}
        if not prior_value:
            continue
        if not extract_game_logs(prior_value) and not any(
            str(k).startswith("priorSeason") for k in prior_value
        ) and not (
            isinstance(prior_value.get("opportunity"), dict) and prior_value.get("opportunity")
        ) and not (
            isinstance(prior_value.get("efficiency"), dict) and prior_value.get("efficiency")
        ):
            continue
        value = preserve_historical_support_fields(value, prior_value)
        needs_logs = not extract_game_logs(value)
        if not needs_logs:
            # Logs are the critical regression; stop once restored.
            break

    out["claim_value"] = value
    return out


def merge_game_logs(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Append-only merge. First identity wins; history is never silently replaced."""
    seen: dict[str, dict[str, Any]] = {}
    out: list[dict[str, Any]] = []
    appended: list[dict[str, Any]] = []
    for log in list(existing or []) + list(incoming or []):
        if not isinstance(log, dict):
            continue
        key = game_identity(log)
        if key in seen:
            continue
        seen[key] = log
        out.append(log)
        if existing and log in incoming and key not in {game_identity(x) for x in existing if isinstance(x, dict)}:
            appended.append(log)
    if existing:
        existing_keys = {game_identity(x) for x in existing if isinstance(x, dict)}
        appended = [log for log in incoming or [] if isinstance(log, dict) and game_identity(log) not in existing_keys]
    return out, appended


def last_verified_event(logs: list[dict[str, Any]]) -> dict[str, Any] | None:
    dated: list[tuple[str, dict[str, Any]]] = []
    for log in logs:
        ident = game_identity(log)
        date = str(log.get("date") or log.get("game_date") or log.get("gameDate") or "")[:10]
        dated.append((date or ident, log))
    if not dated:
        return None
    dated.sort(key=lambda kv: kv[0])
    last = dated[-1][1]
    return {"identity": game_identity(last), "date": dated[-1][0], "log": last}


def history_gap(
    prior_logs: list[dict[str, Any]],
    *,
    required_history_count: int = 3,
    incoming_logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    known = merge_game_logs(prior_logs, incoming_logs or [])[0] if incoming_logs else list(prior_logs or [])
    last = last_verified_event(known)
    return {
        "knownHistoryCount": len(known),
        "requiredHistoryCount": int(required_history_count),
        "lastVerified": last,
        "missingCount": max(0, int(required_history_count) - len(known)),
        "gap": len(known) < int(required_history_count),
    }


class ResearchStore:
    """Filesystem content-addressed store. Git never receives raw HARs/HTML dumps."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.blobs = self.root / "blobs"
        self.indexes = self.root / "indexes"
        self.outcomes = self.root / "outcomes"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.indexes.mkdir(parents=True, exist_ok=True)
        self.outcomes.mkdir(parents=True, exist_ok=True)
        self._index_path = self.indexes / "records.jsonl"
        self._latest_path = self.indexes / "latest.json"
        self._by_entity_path = self.indexes / "by_entity.json"
        self._by_source_path = self.indexes / "by_source.json"
        self._by_asof_path = self.indexes / "by_asof.json"

    def _append_index(self, rec: dict[str, Any]) -> None:
        with self._index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n")

    def _load_index(self) -> list[dict[str, Any]]:
        if not self._index_path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with self._index_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if isinstance(rec, dict):
                    out.append(rec)
        return out

    def _latest(self) -> dict[str, Any]:
        if not self._latest_path.is_file():
            return {}
        try:
            data = json.loads(self._latest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _set_latest(self, key: str, pointer: dict[str, Any]) -> None:
        latest = self._latest()
        latest[key] = pointer
        self._latest_path.write_text(json.dumps(latest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _load_map(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _index_push(self, path: Path, key: str, digest: str) -> None:
        data = self._load_map(path)
        bucket = data.setdefault(key, [])
        if digest not in bucket:
            bucket.append(digest)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def put_claim(
        self,
        claim: dict[str, Any],
        *,
        sport: str = "",
        entity_kind: str | None = None,
        as_of: str = "",
    ) -> dict[str, Any]:
        kind = canonical_scope(entity_kind or str(claim.get("semantic_scope") or ""))
        entity_id = str(claim.get("scope_id") or "")
        asof = as_of or str(claim.get("forecast_cutoff") or claim.get("observed_at") or "")
        # Volatile status/context claims must not hide already-stored historical logs.
        claim = dict(claim)
        value = claim.get("claim_value") if isinstance(claim.get("claim_value"), dict) else None
        if isinstance(value, dict) and entity_id and not extract_game_logs(value):
            prior_blob = self.latest_blob(kind, entity_id)
            prior_claim = (prior_blob or {}).get("claim") if isinstance(prior_blob, dict) else None
            prior_value = (
                prior_claim.get("claim_value")
                if isinstance(prior_claim, dict) and isinstance(prior_claim.get("claim_value"), dict)
                else {}
            )
            if prior_value:
                claim["claim_value"] = preserve_historical_support_fields(dict(value), prior_value)
        payload = {
            "schema": STORE_SCHEMA,
            "sport": sport,
            "entityKind": kind,
            "entityId": entity_id,
            "asOf": asof,
            "claim": claim,
        }
        digest = content_hash(payload)
        blob = self.blobs / f"{digest}.json"
        if not blob.is_file():
            blob.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pointer = {
            "contentHash": digest,
            "sport": sport,
            "entityKind": kind,
            "entityId": entity_id,
            "asOf": asof,
            "asOfDate": _asof_day(asof),
            "sourceId": str(claim.get("source_id") or ""),
            "claimType": str(claim.get("claim_type") or ""),
            "claimHash": str(claim.get("claim_hash") or ""),
            "observedAt": str(claim.get("observed_at") or ""),
            "freshness": claim.get("freshness"),
            "reliability": claim.get("reliability"),
            "storedAt": _utc_now(),
            "path": str(blob.relative_to(self.root)),
        }
        value = claim.get("claim_value") if isinstance(claim.get("claim_value"), dict) else {}
        if value.get("affiliationId") or value.get("teamId"):
            pointer["affiliationId"] = str(value.get("affiliationId") or value.get("teamId") or "")
        if value.get("opponentId") or value.get("counterpartyId"):
            pointer["opponentId"] = str(value.get("opponentId") or value.get("counterpartyId") or "")
        if value.get("role_epoch_id") or value.get("roleEpochId"):
            pointer["roleEpochId"] = str(value.get("role_epoch_id") or value.get("roleEpochId") or "")
        pointer["historyCount"] = len(extract_game_logs(claim))
        self._append_index(pointer)
        self._set_latest(f"{kind}:{entity_id}", pointer)
        self._index_push(self._by_entity_path, f"{kind}:{entity_id}", digest)
        if pointer.get("sourceId"):
            self._index_push(self._by_source_path, str(pointer["sourceId"]), digest)
        self._index_push(self._by_asof_path, pointer["asOfDate"], digest)
        return pointer

    def put_game_logs(
        self,
        *,
        entity_kind: str,
        entity_id: str,
        logs: list[dict[str, Any]],
        sport: str = "",
        as_of: str = "",
        base_claim: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prior_blob = self.latest_blob(entity_kind, entity_id)
        prior_logs = extract_game_logs(prior_blob) if prior_blob else []
        merged, appended = merge_game_logs(prior_logs, logs)
        claim = dict(base_claim or {})
        value = dict(claim.get("claim_value") or {})
        value["game_logs"] = merged
        value["appendedGameCount"] = len(appended)
        value["lastVerified"] = last_verified_event(merged)
        claim["claim_value"] = value
        claim.setdefault("semantic_scope", canonical_scope(entity_kind))
        claim.setdefault("scope_id", entity_id)
        claim.setdefault("claim_type", "HISTORICAL_PERFORMANCE")
        pointer = self.put_claim(claim, sport=sport, entity_kind=entity_kind, as_of=as_of)
        pointer["appendedGameCount"] = len(appended)
        pointer["knownHistoryCount"] = len(merged)
        return pointer

    def get(self, content_hash_value: str) -> dict[str, Any] | None:
        blob = self.blobs / f"{content_hash_value}.json"
        if not blob.is_file():
            return None
        data = json.loads(blob.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None

    def latest_for(self, kind: str, entity_id: str) -> dict[str, Any] | None:
        pointer = self._latest().get(f"{canonical_scope(kind)}:{entity_id}")
        return pointer if isinstance(pointer, dict) else None

    def latest_blob(self, kind: str, entity_id: str) -> dict[str, Any] | None:
        pointer = self.latest_for(kind, entity_id)
        if not pointer:
            return None
        return self.get(str(pointer.get("contentHash") or ""))

    def prior_fields(self, kind: str, entity_id: str) -> dict[str, Any] | None:
        """Hydrate classify_delta `prior` from the stored blob, not the pointer."""
        pointer = self.latest_for(kind, entity_id)
        if not pointer:
            return None
        blob = self.get(str(pointer.get("contentHash") or ""))
        claim = (blob or {}).get("claim") if isinstance(blob, dict) else None
        value = claim.get("claim_value") if isinstance(claim, dict) and isinstance(claim.get("claim_value"), dict) else {}
        prior = dict(pointer)
        if isinstance(claim, dict):
            prior["freshness"] = claim.get("freshness", prior.get("freshness"))
            prior["reliability"] = claim.get("reliability", prior.get("reliability"))
            prior["claim_type"] = claim.get("claim_type") or prior.get("claimType")
            prior["claimHash"] = claim.get("claim_hash") or prior.get("claimHash")
            prior["invalidated"] = claim.get("invalidated") or value.get("invalidated")
        prior["affiliationId"] = str(
            value.get("affiliationId") or value.get("teamId") or pointer.get("affiliationId") or ""
        )
        prior["opponentId"] = str(
            value.get("opponentId") or value.get("counterpartyId") or pointer.get("opponentId") or ""
        )
        prior["roleEpochId"] = str(
            value.get("role_epoch_id") or value.get("roleEpochId")
            or (value.get("role_epoch") or {}).get("label")
            or pointer.get("roleEpochId")
            or ""
        )
        prior["definitionId"] = str(value.get("definitionId") or value.get("marketDefinitionId") or "")
        prior["historyCount"] = len(extract_game_logs(claim or {}))
        prior["gameLogs"] = extract_game_logs(claim or {})
        prior["contradicted"] = bool(claim.get("conflicts") if isinstance(claim, dict) else False)
        return prior

    def records_for(self, kind: str, entity_id: str) -> list[dict[str, Any]]:
        kind_c = canonical_scope(kind)
        mapped = self._load_map(self._by_entity_path).get(f"{kind_c}:{entity_id}") or []
        if mapped:
            out = []
            for digest in mapped:
                blob = self.get(str(digest))
                if blob:
                    out.append(blob)
            return out
        return [
            rec
            for rec in self._load_index()
            if str(rec.get("entityKind") or "") == kind_c and str(rec.get("entityId") or "") == str(entity_id)
        ]

    def put_outcome(self, outcome: dict[str, Any]) -> dict[str, Any]:
        """Store settlement memory separately from research validity."""
        payload = {
            "schema": OUTCOME_SCHEMA,
            "researchReuseDecidedByOutcome": False,
            "futureOnlyLearning": True,
            "outcome": outcome,
        }
        digest = content_hash(payload)
        path = self.outcomes / f"{digest}.json"
        if not path.is_file():
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pointer = {
            "contentHash": digest,
            "projectionId": str(outcome.get("projectionId") or ""),
            "result": str(outcome.get("settlement") or outcome.get("result") or ""),
            "frozenForecastHash": str(outcome.get("frozenForecastHash") or ""),
            "doesNotDecideResearchReuse": True,
        }
        with (self.indexes / "outcomes.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(pointer, sort_keys=True, separators=(",", ":")) + "\n")
        return pointer

    def telemetry(self, *, reused: int = 0, appended: int = 0, refreshed: int = 0, acquired: int = 0) -> dict[str, Any]:
        records = self._load_index()
        blobs = list(self.blobs.glob("*.json"))
        total = max(1, int(reused) + int(acquired) + int(refreshed))
        return {
            "schema": STORE_SCHEMA,
            "recordCount": len(records),
            "blobCount": len(blobs),
            "entityCount": len(self._latest()),
            "root": str(self.root),
            "persistentRecordsReused": int(reused),
            "newRecordsAcquired": int(acquired),
            "staleRecordsRefreshed": int(refreshed),
            "missingGamesAppended": int(appended),
            "webRequestsAvoided": int(reused),
            "cacheHitRate": round(int(reused) / total, 4) if (reused or acquired or refreshed) else None,
            "hostPerformanceCertified": False,
        }


def classify_delta(
    *,
    request: dict[str, Any],
    prior: dict[str, Any] | None,
    current_affiliation: str = "",
    current_opponent: str = "",
    current_role_epoch: str = "",
    current_definition: str = "",
    known_history_count: int | None = None,
    required_history_count: int = 3,
) -> dict[str, Any]:
    """Deterministic gap analysis before the host is asked to research.

    Prediction HIT/MISS is never an input. Outcomes live in a separate store.
    """
    scope = canonical_scope(str(request.get("scope") or ""))
    if scope in {"MARKET_DEFINITION", "OFFER", "SPORT", "COMPETITION"} and prior is None:
        klass = "RESEARCH_NEW" if scope in {"SPORT", "COMPETITION"} else "REFRESH_CURRENT_CONTEXT"
        return {"deltaClass": klass, "reason": "NO_PRIOR_RECORD", "acquire": True}

    if prior is None:
        return {
            "deltaClass": "NEW_ENTITY_FULL_RESEARCH",
            "reason": "NO_PRIOR_RECORD",
            "acquire": True,
        }

    if str(prior.get("invalidated") or "") or str(prior.get("deltaClass") or "") == "REPLACE_INVALIDATED":
        return {"deltaClass": "REPLACE_INVALIDATED", "reason": "PRIOR_INVALIDATED", "acquire": True}

    if prior.get("contradicted") or prior.get("conflicts"):
        return {"deltaClass": "CONTRADICTED_REVERIFY", "reason": "PRIOR_CONFLICTS", "acquire": True}

    prior_def = str(prior.get("definitionId") or "")
    if current_definition and prior_def and current_definition != prior_def:
        return {"deltaClass": "DEFINITION_CHANGED", "reason": "MARKET_DEFINITION_CHANGED", "acquire": True}

    prior_epoch = str(prior.get("roleEpochId") or "")
    if current_role_epoch and prior_epoch and current_role_epoch != prior_epoch:
        return {"deltaClass": "ROLE_EPOCH_CHANGED", "reason": "ROLE_EPOCH_CHANGED", "acquire": True}

    prior_aff = str(prior.get("affiliationId") or prior.get("teamId") or "")
    if current_affiliation and prior_aff and current_affiliation != prior_aff:
        return {"deltaClass": "TEAM_CHANGED", "reason": "AFFILIATION_CHANGED", "acquire": True}

    prior_opp = str(prior.get("opponentId") or prior.get("counterpartyId") or "")
    if current_opponent and prior_opp and current_opponent != prior_opp:
        return {"deltaClass": "NEW_OPPONENT_REQUIRED", "reason": "COUNTERPARTY_CHANGED", "acquire": True}

    history_n = known_history_count
    if history_n is None and prior.get("historyCount") is not None:
        try:
            history_n = int(prior.get("historyCount"))
        except (TypeError, ValueError):
            history_n = None
    if (
        scope in {"SUBJECT", "AFFILIATION", "COUNTERPARTY", "PLAYER", "TEAM"}
        and history_n is not None
        and history_n < required_history_count
    ):
        last = last_verified_event(prior.get("gameLogs") or [])
        return {
            "deltaClass": "APPEND_MISSING_HISTORY",
            "reason": "HISTORY_GAP",
            "acquire": True,
            "knownHistoryCount": history_n,
            "requiredHistoryCount": required_history_count,
            "lastVerified": last,
        }

    claim_type = str(request.get("need") or request.get("claim_type") or "").strip()
    claim_u = claim_type.upper()
    if claim_u in {v.upper() for v in VOLATILE_TYPES} or claim_u in {
        "STATUS",
        "AVAILABILITY",
        "LINEUP",
        "WEATHER",
        "INJURY",
        "STARTERS",
        "CURRENT_STATUS",
        "CURRENT_CONTEXT",
    }:
        return {"deltaClass": "REFRESH_CURRENT_CONTEXT", "reason": "VOLATILE_FIELD", "acquire": True}

    freshness = prior.get("freshness")
    try:
        fresh_f = float(freshness) if freshness is not None else 1.0
    except (TypeError, ValueError):
        fresh_f = 1.0
    if fresh_f < 0.35:
        return {"deltaClass": "REFRESH_STALE", "reason": "FRESHNESS_BELOW_THRESHOLD", "acquire": True}

    return {"deltaClass": "REUSE_VALID", "reason": "PRIOR_STILL_VALID", "acquire": False}


def classify_requests(
    requests: list[dict[str, Any]],
    store: ResearchStore | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for req in requests:
        if not isinstance(req, dict):
            continue
        prior = None
        if store is not None:
            prior = store.prior_fields(str(req.get("scope") or ""), str(req.get("scope_id") or ""))
        extra = req.get("context") if isinstance(req.get("context"), dict) else {}
        required = int(req.get("requiredHistoryCount") or extra.get("requiredHistoryCount") or 3)
        delta = classify_delta(
            request=req,
            prior=prior,
            current_affiliation=str(
                req.get("affiliationId") or extra.get("affiliationId") or extra.get("teamId") or ""
            ),
            current_opponent=str(req.get("opponentId") or extra.get("opponentId") or extra.get("opponent") or ""),
            current_role_epoch=str(req.get("roleEpochId") or extra.get("roleEpochId") or ""),
            current_definition=str(req.get("definitionId") or extra.get("definitionId") or ""),
            known_history_count=None if prior is None else prior.get("historyCount"),
            required_history_count=required,
        )
        rec = dict(req)
        rec["deltaClass"] = delta["deltaClass"]
        rec["deltaReason"] = delta["reason"]
        rec["acquire"] = bool(delta["acquire"])
        if "lastVerified" in delta:
            rec["lastVerified"] = delta["lastVerified"]
        if "knownHistoryCount" in delta:
            rec["knownHistoryCount"] = delta["knownHistoryCount"]
        rec["priorContentHash"] = (prior or {}).get("contentHash")
        out.append(rec)
    return out



def merge_latest_store_claims(
    claims: list[dict[str, Any]],
    store: "ResearchStore",
    *,
    scopes: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Merge ResearchStore latest blobs into a forecast claim list.

    evidence-import persists host observations into the store and appends the
    run bundle, but forecast ``collect`` + ``write_bundle`` can rewrite the
    bundle without those store updates. Re-attach latest store claims by
    ``(semantic_scope, scope_id)`` so consumers see plays/pace/status/logs.
    """
    out = list(claims or [])
    seen = {str(c.get("claim_hash") or "") for c in out if c.get("claim_hash")}
    scope_keys: set[tuple[str, str]] = set()
    for scope, scope_id in scopes or []:
        if scope and scope_id:
            scope_keys.add((str(scope), str(scope_id)))
    for claim in out:
        scope = str(claim.get("semantic_scope") or claim.get("scope") or "")
        scope_id = str(claim.get("scope_id") or claim.get("scopeId") or "")
        if scope and scope_id:
            scope_keys.add((scope, scope_id))
    # Also walk store latest pointer index when available.
    latest = getattr(store, "_latest", None)
    pointer_map = latest() if callable(latest) else {}
    if isinstance(pointer_map, dict):
        for key in pointer_map:
            if ":" not in str(key):
                continue
            kind, entity_id = str(key).split(":", 1)
            if kind and entity_id:
                scope_keys.add((kind, entity_id))
    for scope, scope_id in sorted(scope_keys):
        blob = store.latest_blob(scope, scope_id)
        claim = (blob or {}).get("claim") if isinstance(blob, dict) else None
        if not isinstance(claim, dict):
            continue
        claim = enrich_claim_value_from_prior_records(claim, store, scope=scope, scope_id=scope_id)
        digest = str(claim.get("claim_hash") or (blob or {}).get("contentHash") or "")
        if digest and digest in seen:
            continue
        if digest:
            seen.add(digest)
        out.append(claim)
    return out



def hydrate_reused_claims(
    store: ResearchStore,
    classified: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pull still-valid stored claims so forecast does not research from zero."""
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in classified:
        if rec.get("acquire"):
            continue
        scope = str(rec.get("scope") or "")
        scope_id = str(rec.get("scope_id") or "")
        blob = store.latest_blob(scope, scope_id)
        claim = (blob or {}).get("claim") if isinstance(blob, dict) else None
        if not isinstance(claim, dict):
            continue
        claim = enrich_claim_value_from_prior_records(claim, store, scope=scope, scope_id=scope_id)
        digest = str(claim.get("claim_hash") or (blob or {}).get("contentHash") or "")
        if digest and digest in seen:
            continue
        if digest:
            seen.add(digest)
        claims.append(claim)
    return claims
