"""Runtime source-health state. Authority is never derived from pick wins."""
from __future__ import annotations

from typing import Any, Mapping

from dcm.contracts.hashes import content_hash

CIRCUIT_CLOSED = "CLOSED"
CIRCUIT_OPEN = "OPEN"
CIRCUIT_HALF_OPEN = "HALF_OPEN"
FAILURE_THRESHOLD = 3


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
                "historicalSuccessProbability": 1.0,
            }
            self._state[source_id] = row
        return row

    def record_success(self, source_id: str, *, latency_ms: float | None = None, yield_n: int = 1, freshness: float | None = None) -> dict[str, Any]:
        row = self._ensure(source_id)
        row["successes"] += 1
        row["consecutiveFailures"] = 0
        row["lastSuccess"] = "ok"
        row["yield"] += int(yield_n)
        if latency_ms is not None:
            row["latencyMs"] = (list(row["latencyMs"]) + [float(latency_ms)])[-32:]
        if freshness is not None:
            row["observedFreshness"] = float(freshness)
        row["circuitState"] = CIRCUIT_CLOSED
        row["retryEligible"] = True
        total = row["successes"] + row["failures"]
        row["historicalSuccessProbability"] = row["successes"] / total if total else 1.0
        return row

    def record_failure(self, source_id: str, *, reason: str = "unknown") -> dict[str, Any]:
        row = self._ensure(source_id)
        row["failures"] += 1
        row["consecutiveFailures"] += 1
        row["lastFailure"] = reason
        total = row["successes"] + row["failures"]
        row["historicalSuccessProbability"] = row["successes"] / total if total else 0.0
        if row["consecutiveFailures"] >= FAILURE_THRESHOLD:
            row["circuitState"] = CIRCUIT_OPEN
            row["retryEligible"] = False
        return row

    def route(self, *, claim_type: str, sport: str = "CFB") -> list[str]:
        """Prefer official/structured, then stats, then reporting, search last.

        Open circuits are skipped; their fallbacks are appended.
        """
        ranked: list[tuple[int, float, str]] = []
        for sid, row in self._state.items():
            if sport and row["sports"] and sport not in row["sports"] and "CFB" not in row["sports"]:
                continue
            if row["circuitState"] == CIRCUIT_OPEN:
                continue
            auth = int((row["authorityByClaimType"] or {}).get(claim_type) or 50)
            ranked.append((-auth, row["cost"], sid))
        ranked.sort()
        out = [sid for _a, _c, sid in ranked]
        if not out:
            out = [sid for sid, row in self._state.items() if row["circuitState"] != CIRCUIT_OPEN]
        return out

    def snapshot(self) -> dict[str, Any]:
        open_all = bool(self._state) and all(r["circuitState"] == CIRCUIT_OPEN for r in self._state.values())
        body = {
            "schema": "pillars_dcm.source_health.v1",
            "sources": [self._state[k] for k in sorted(self._state)],
            "valid": not open_all,
            "blockers": ["circuitOpenAll"] if open_all else [],
            "note": "Source factual authority is never derived from whether prior prop picks won.",
        }
        body["contentHash"] = content_hash({
            "schema": body["schema"],
            "sourceIds": sorted(self._state),
            "circuits": {k: v["circuitState"] for k, v in self._state.items()},
        })
        return body


def default_cfb_source_health() -> SourceHealthRegistry:
    return SourceHealthRegistry({
        "sources": [
            {
                "sourceId": "CFB_OFFICIAL_GAMEBOOK",
                "adapter": "official_league",
                "authorityByClaimType": {"EVENT": 100, "AFFILIATION": 90, "SUBJECT": 80},
                "sports": ["CFB"],
                "cost": 1.0,
                "fallbackSourceIds": ["CFB_PFR", "WEB_SEARCH"],
            },
            {
                "sourceId": "CFB_PFR",
                "adapter": "pro_football_reference",
                "authorityByClaimType": {"SUBJECT": 85, "AFFILIATION": 80},
                "sports": ["CFB"],
                "cost": 1.2,
                "fallbackSourceIds": ["WEB_SEARCH"],
            },
            {
                "sourceId": "CFB_STATUS",
                "adapter": "espn_status",
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
