"""Runtime source-health state. Authority is never derived from pick wins."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash

CIRCUIT_CLOSED = "CLOSED"
CIRCUIT_OPEN = "OPEN"
CIRCUIT_HALF_OPEN = "HALF_OPEN"
FAILURE_THRESHOLD = 3
OPEN_COOLDOWN = timedelta(seconds=300)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime | None = None) -> str:
    return (ts or _now()).isoformat()


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class SourceHealthRegistry:
    """Claim-specific source routing with circuit breakers and bounded fallbacks."""

    def __init__(self, catalog: Mapping[str, Any] | None = None) -> None:
        self._state: dict[str, dict[str, Any]] = {}
        sources = []
        if isinstance(catalog, Mapping):
            raw = catalog.get("sources") or catalog.get("adapters") or []
            if isinstance(raw, Mapping):
                sources = [{"sourceId": k, **(v if isinstance(v, dict) else {})} for k, v in raw.items()]
            elif isinstance(raw, list):
                sources = [s for s in raw if isinstance(s, dict)]
        for src in sources:
            sid = str(src.get("sourceId") or src.get("id") or src.get("adapter") or "")
            if sid:
                self._ensure(sid, src)

    def _ensure(self, source_id: str, seed: Mapping[str, Any] | None = None) -> dict[str, Any]:
        row = self._state.get(source_id)
        if row is None:
            seed = dict(seed or {})
            row = {
                "sourceId": source_id,
                "domain": seed.get("domain") or "",
                "adapter": seed.get("adapter") or source_id,
                "authorityByClaimType": dict(seed.get("authorityByClaimType") or {}),
                "sports": list(seed.get("sports") or ["CFB"]),
                "fields": list(seed.get("fields") or []),
                "cost": float(seed.get("estimated_cost") or seed.get("cost") or 1.0),
                "expectedFreshness": float(seed.get("expectedFreshness") or 0.5),
                "observedFreshness": None,
                "lastSuccess": None,
                "lastFailure": None,
                "lastSuccessAt": None,
                "lastFailureAt": None,
                "openedAt": None,
                "openUntil": None,
                "halfOpenAt": None,
                "consecutiveFailures": 0,
                "successes": 0,
                "failures": 0,
                "latencyMs": [],
                "yield": 0,
                "rateLimit": seed.get("rateLimit"),
                "knownFailureModes": list(seed.get("knownFailureModes") or []),
                "circuitState": CIRCUIT_CLOSED,
                "retryEligible": True,
                "fallbackSourceIds": list(seed.get("fallbackSourceIds") or []),
                "historicalSuccessProbability": seed.get("historicalSuccessProbability"),
            }
            if seed.get("successes") is not None:
                row["successes"] = int(seed.get("successes") or 0)
            if seed.get("failures") is not None:
                row["failures"] = int(seed.get("failures") or 0)
            if seed.get("consecutiveFailures") is not None:
                row["consecutiveFailures"] = int(seed.get("consecutiveFailures") or 0)
            if seed.get("circuitState"):
                row["circuitState"] = str(seed.get("circuitState"))
            if seed.get("yield") is not None:
                row["yield"] = int(seed.get("yield") or 0)
            if seed.get("latencyMs"):
                row["latencyMs"] = list(seed.get("latencyMs") or [])
            for k in ("lastSuccess", "lastFailure", "lastSuccessAt", "lastFailureAt", "openedAt", "openUntil", "halfOpenAt", "observedFreshness"):
                if seed.get(k) is not None:
                    row[k] = seed.get(k)
            self._state[source_id] = row
            self._set_success_probability(row)
        return row

    def _set_success_probability(self, row: dict[str, Any]) -> None:
        total = int(row.get("successes") or 0) + int(row.get("failures") or 0)
        if total <= 0:
            row["historicalSuccessProbability"] = None
        else:
            row["historicalSuccessProbability"] = int(row["successes"]) / total

    def success_probability(self, source_id: str) -> float | None:
        row = self._state.get(source_id)
        if row is None:
            return None
        self._set_success_probability(row)
        val = row.get("historicalSuccessProbability")
        return None if val is None else float(val)

    def _refresh_circuit(self, row: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        ts = now or _now()
        if row["circuitState"] == CIRCUIT_OPEN:
            until = _parse_ts(row.get("openUntil"))
            if until is not None and ts >= until:
                row["circuitState"] = CIRCUIT_HALF_OPEN
                row["retryEligible"] = True
                row["halfOpenAt"] = _iso(ts)
        return row

    def record_success(self, source_id: str, *, latency_ms: float | None = None, yield_n: int = 1, freshness: float | None = None) -> dict[str, Any]:
        row = self._ensure(source_id)
        self._refresh_circuit(row)
        now = _now()
        row["successes"] += 1
        row["consecutiveFailures"] = 0
        row["lastSuccess"] = "ok"
        row["lastSuccessAt"] = _iso(now)
        row["yield"] += int(yield_n)
        if latency_ms is not None:
            row["latencyMs"] = (list(row["latencyMs"]) + [float(latency_ms)])[-32:]
        if freshness is not None:
            row["observedFreshness"] = float(freshness)
        row["circuitState"] = CIRCUIT_CLOSED
        row["retryEligible"] = True
        row["openUntil"] = None
        row["openedAt"] = None
        row["halfOpenAt"] = None
        self._set_success_probability(row)
        return row

    def record_failure(self, source_id: str, *, reason: str = "unknown") -> dict[str, Any]:
        row = self._ensure(source_id)
        self._refresh_circuit(row)
        now = _now()
        row["failures"] += 1
        row["consecutiveFailures"] += 1
        row["lastFailure"] = reason
        row["lastFailureAt"] = _iso(now)
        self._set_success_probability(row)
        if row["circuitState"] == CIRCUIT_HALF_OPEN or row["consecutiveFailures"] >= FAILURE_THRESHOLD:
            row["circuitState"] = CIRCUIT_OPEN
            row["retryEligible"] = False
            row["openedAt"] = _iso(now)
            row["openUntil"] = _iso(now + OPEN_COOLDOWN)
            row["halfOpenAt"] = None
        return row

    def fallbacks(self, source_id: str) -> list[str]:
        """Traverse fallbackSourceIds, skipping currently OPEN circuits."""
        out: list[str] = []
        seen = {source_id}
        queue = list(self._ensure(source_id).get("fallbackSourceIds") or [])
        while queue:
            sid = str(queue.pop(0))
            if not sid or sid in seen:
                continue
            seen.add(sid)
            row = self._ensure(sid)
            self._refresh_circuit(row)
            if row["circuitState"] == CIRCUIT_OPEN:
                queue.extend(row.get("fallbackSourceIds") or [])
                continue
            out.append(sid)
        return out

    def route(self, *, claim_type: str, sport: str = "CFB") -> list[str]:
        """Prefer official/structured, then stats, then reporting, search last.

        OPEN circuits are skipped and replaced by live fallbacks.
        HALF_OPEN circuits are eligible for a single trial request.
        """
        now = _now()
        ranked: list[tuple[int, float, str]] = []
        skipped_open: list[str] = []
        half_open_used = False
        for sid, row in self._state.items():
            self._refresh_circuit(row, now=now)
            if sport and row["sports"] and sport not in row["sports"] and "CFB" not in row["sports"]:
                continue
            if row["circuitState"] == CIRCUIT_OPEN:
                skipped_open.append(sid)
                continue
            if row["circuitState"] == CIRCUIT_HALF_OPEN:
                if half_open_used:
                    continue
                half_open_used = True
            auth = int((row["authorityByClaimType"] or {}).get(claim_type) or 50)
            ranked.append((-auth, row["cost"], sid))
        ranked.sort()
        out = [sid for _a, _c, sid in ranked]
        for sid in skipped_open:
            for fb in self.fallbacks(sid):
                if fb not in out:
                    out.append(fb)
        if not out:
            out = [sid for sid, row in self._state.items() if row["circuitState"] != CIRCUIT_OPEN]
        return out

    def snapshot(self) -> dict[str, Any]:
        for row in self._state.values():
            self._refresh_circuit(row)
        open_all = bool(self._state) and all(r["circuitState"] == CIRCUIT_OPEN for r in self._state.values())
        body = {
            "schema": "pillars_dcm.source_health.v1",
            "sources": [self._state[k] for k in sorted(self._state)],
            "valid": not open_all,
            "blockers": ["circuitOpenAll"] if open_all else [],
            "circuits": {k: v["circuitState"] for k, v in self._state.items()},
            "note": "Source factual authority is never derived from whether prior prop picks won.",
        }
        body["contentHash"] = content_hash({
            "schema": body["schema"],
            "sourceIds": sorted(self._state),
            "circuits": body["circuits"],
        })
        return body

    def load_snapshot(self, body: Mapping[str, Any] | None) -> None:
        """Overlay persisted counters/circuits onto the live catalog. Never invent 0.85."""
        if not isinstance(body, Mapping):
            return
        sources = body.get("sources") or []
        if isinstance(sources, Mapping):
            sources = [{"sourceId": k, **(v if isinstance(v, dict) else {})} for k, v in sources.items()]
        for src in sources:
            if not isinstance(src, Mapping):
                continue
            sid = str(src.get("sourceId") or src.get("id") or "")
            if not sid:
                continue
            if sid in self._state:
                row = self._state[sid]
                for k, v in src.items():
                    if k == "sourceId":
                        continue
                    row[k] = v
                self._set_success_probability(row)
            else:
                self._ensure(sid, src)


def persist_cfb_source_health(health: SourceHealthRegistry, dest) -> dict[str, Any]:
    """Write the live source-health snapshot so later research passes restore it."""
    import json
    from pathlib import Path

    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    snap = health.snapshot()
    (dest / "source_health.json").write_text(
        json.dumps(snap, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return snap


def load_cfb_source_health(path=None) -> SourceHealthRegistry:
    """Restore persisted source-health counters/circuits. Missing file → default catalog."""
    import json
    from pathlib import Path

    health = default_cfb_source_health()
    if path is None:
        return health
    p = Path(path)
    if p.is_dir():
        p = p / "source_health.json"
    if not p.is_file():
        return health
    try:
        body = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return health
    health.load_snapshot(body if isinstance(body, Mapping) else {})
    return health


def default_cfb_source_health() -> SourceHealthRegistry:
    """CFB catalog. Never routes college football through a pro-football adapter."""
    return SourceHealthRegistry({
        "sources": [
            {
                "sourceId": "CFB_OFFICIAL_GAMEBOOK",
                "adapter": "official_league",
                "domain": "official",
                "authorityByClaimType": {"EVENT": 100, "AFFILIATION": 90, "SUBJECT": 80},
                "sports": ["CFB"],
                "cost": 1.0,
                "fallbackSourceIds": ["CFB_SPORTS_REFERENCE", "WEB_SEARCH"],
            },
            {
                "sourceId": "CFB_SPORTS_REFERENCE",
                "adapter": "college_football_reference",
                "domain": "sports-reference.com",
                "authorityByClaimType": {"SUBJECT": 85, "AFFILIATION": 80, "EVENT": 60},
                "sports": ["CFB"],
                "cost": 1.2,
                "fallbackSourceIds": ["CFB_STATUS", "WEB_SEARCH"],
            },
            {
                "sourceId": "CFB_STATUS",
                "adapter": "espn_status",
                "domain": "espn.com",
                "authorityByClaimType": {"SUBJECT": 70, "EVENT": 75, "ENVIRONMENT": 60},
                "sports": ["CFB"],
                "cost": 0.8,
                "fallbackSourceIds": ["WEB_SEARCH"],
            },
            {
                "sourceId": "WEB_SEARCH",
                "adapter": "host_web",
                "authorityByClaimType": {"SUBJECT": 20, "EVENT": 20},
                "sports": ["CFB"],
                "cost": 5.0,
                "fallbackSourceIds": [],
            },
        ]
    })
