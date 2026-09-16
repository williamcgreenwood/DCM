"""Runtime source-health state. Authority is never derived from pick wins."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from dcm.contracts.hashes import content_hash
from dcm.research.source_catalog import (
    candidate_sources_for_sport,
    normalize_competition_id,
    source_health_seeds,
    sport_family_for_league,
)

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

    def __init__(
        self,
        catalog: Mapping[str, Any] | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or _now
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
                "catalogSourceId": seed.get("catalogSourceId") or source_id,
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

    def _now(self) -> datetime:
        ts = self._clock()
        if not isinstance(ts, datetime):
            raise TypeError("source-health clock must return datetime")
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

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
        ts = now or self._now()
        if row["circuitState"] == CIRCUIT_OPEN:
            until = _parse_ts(row.get("openUntil"))
            if until is not None and ts >= until:
                row["circuitState"] = CIRCUIT_HALF_OPEN
                row["retryEligible"] = True
                row["halfOpenAt"] = _iso(ts)
        return row

    def record_success(self, source_id: str, *, latency_ms: float | None = None, yield_n: int = 1, freshness: float | None = None, now: datetime | None = None) -> dict[str, Any]:
        row = self._ensure(source_id)
        now = now or self._now()
        self._refresh_circuit(row, now=now)
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

    def record_failure(self, source_id: str, *, reason: str = "unknown", now: datetime | None = None) -> dict[str, Any]:
        row = self._ensure(source_id)
        now = now or self._now()
        self._refresh_circuit(row, now=now)
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

    def fallbacks(self, source_id: str, *, now: datetime | None = None) -> list[str]:
        """Traverse fallbackSourceIds, skipping currently OPEN circuits."""
        out: list[str] = []
        now = now or self._now()
        seen = {source_id}
        queue = list(self._ensure(source_id).get("fallbackSourceIds") or [])
        while queue:
            sid = str(queue.pop(0))
            if not sid or sid in seen:
                continue
            seen.add(sid)
            row = self._ensure(sid)
            self._refresh_circuit(row, now=now)
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
        now = self._now()
        ranked: list[tuple[int, float, str]] = []
        skipped_open: list[str] = []
        half_open_used = False
        for sid, row in self._state.items():
            self._refresh_circuit(row, now=now)
            if sport and row["sports"] and str(sport).upper() not in {str(item).upper() for item in row["sports"]}:
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
            for fb in self.fallbacks(sid, now=now):
                if fb not in out:
                    # Fallbacks must still be sport-legal for the requested sport.
                    fb_row = self._ensure(fb)
                    sports = {str(item).upper() for item in (fb_row.get("sports") or [])}
                    if sport and sports and str(sport).upper() not in sports and "*" not in sports:
                        continue
                    out.append(fb)
        if not out:
            # Never dump wrong-sport sources (e.g. CFB_WEATHER for MLB). Prefer
            # wildcard / unscoped sources such as WEB_SEARCH.
            sport_u = str(sport or "").upper()
            wild: list[str] = []
            for sid, row in self._state.items():
                if row["circuitState"] == CIRCUIT_OPEN:
                    continue
                sports = {str(item).upper() for item in (row.get("sports") or [])}
                if not sports or "*" in sports or (sport_u and sport_u in sports):
                    wild.append(sid)
            out = wild or ["WEB_SEARCH"]
        # Hard rule: CFB_WEATHER is never primary for non-CFB subjects.
        sport_u = str(sport or "").upper()
        if sport_u and sport_u not in {"CFB", "NCAAFB", "CFB1H"} and out and out[0] == "CFB_WEATHER":
            out = [sid for sid in out if sid != "CFB_WEATHER"] or ["WEB_SEARCH"]
        return out

    def snapshot(self) -> dict[str, Any]:
        now = self._now()
        for row in self._state.values():
            self._refresh_circuit(row, now=now)
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
    """Restore persisted source-health counters/circuits. Missing file → universal catalog.

    Historically CFB-named; Insights/multi-sport runs require sport-correct seeds.
    """
    import json
    from pathlib import Path

    health = default_universal_source_health()
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


def default_gridiron_source_health(league: str | None = None) -> SourceHealthRegistry:
    """League-keyed gridiron router derived from the source-capability catalog.

    With no league supplied, include both production football catalogs so a
    mixed-board scheduler still chooses only sources declared for each action.
    """
    if league:
        return default_sport_source_health(league=str(league).upper(), sport_family="gridiron")
    return default_universal_source_health(["CFB", "NFL"])


def default_cfb_source_health() -> SourceHealthRegistry:
    """Backward-compatible CFB-only router."""
    return default_gridiron_source_health("CFB")


_STABLE_SOURCE_IDS = {
    "cfb_official_athletics": "CFB_OFFICIAL_GAMEBOOK",
    "college_football_reference": "CFB_SPORTS_REFERENCE",
    "open_meteo_weather": "CFB_WEATHER",
    "espn_status": "CFB_STATUS",
    "generic_web_search": "WEB_SEARCH",
    "official_nfl": "NFL_OFFICIAL",
    "pro_football_reference": "NFL_PRO_FOOTBALL_REFERENCE",
    "official_wnba": "WNBA_OFFICIAL",
    "official_nba": "NBA_OFFICIAL",
    "basketball_reference": "BASKETBALL_REFERENCE",
    "official_mlb": "MLB_OFFICIAL",
    "baseball_reference": "BASEBALL_REFERENCE",
    "official_soccer": "SOCCER_OFFICIAL",
    "outlier_offer": "OUTLIER_OFFER",
    "prizepicks_offer": "PRIZEPICKS_OFFER",
}

_AUTHORITY = {
    "cfb_official_athletics": {"EVENT": 100, "AFFILIATION": 90, "SUBJECT": 80, "COUNTERPARTY": 80},
    "college_football_reference": {"SUBJECT": 85, "AFFILIATION": 80, "EVENT": 60},
    "open_meteo_weather": {"ENVIRONMENT": 90, "EVENT": 50},
    "espn_status": {"SUBJECT": 70, "EVENT": 75, "ENVIRONMENT": 40},
    "generic_web_search": {"SUBJECT": 20, "EVENT": 20, "AFFILIATION": 20, "COUNTERPARTY": 20, "ENVIRONMENT": 20},
    "official_nfl": {"EVENT": 100, "SUBJECT": 90, "AFFILIATION": 85, "COUNTERPARTY": 85},
    "pro_football_reference": {"SUBJECT": 85, "AFFILIATION": 80, "EVENT": 65},
    "official_wnba": {"EVENT": 100, "SUBJECT": 90, "AFFILIATION": 85, "COUNTERPARTY": 85},
    "official_nba": {"EVENT": 100, "SUBJECT": 90, "AFFILIATION": 85, "COUNTERPARTY": 85},
    "basketball_reference": {"SUBJECT": 85, "AFFILIATION": 80, "COUNTERPARTY": 80, "EVENT": 60},
    "official_mlb": {"EVENT": 100, "SUBJECT": 90, "AFFILIATION": 85, "COUNTERPARTY": 85},
    "baseball_reference": {"SUBJECT": 85, "AFFILIATION": 80, "COUNTERPARTY": 80, "EVENT": 60},
    "official_soccer": {"EVENT": 100, "SUBJECT": 85, "AFFILIATION": 80, "COUNTERPARTY": 80},
}


def _seed_rows_for_competition(sport: str, competition: str) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for source in source_health_seeds(sport=sport, competition=competition):
        row = dict(source)
        catalog_id = str(row.get("sourceId") or "")
        row["catalogSourceId"] = catalog_id
        row["sourceId"] = _STABLE_SOURCE_IDS.get(catalog_id, catalog_id)
        row["authorityByClaimType"] = _AUTHORITY.get(catalog_id, row.get("authorityByClaimType") or {})
        row["sports"] = [normalize_competition_id(competition)]
        row["fallbackSourceIds"] = [
            _STABLE_SOURCE_IDS.get(str(fallback), str(fallback))
            for fallback in (row.get("fallbackSourceIds") or [])
        ]
        # CFB_WEATHER is CFB-only; never seed it for other competitions.
        if row["sourceId"] == "CFB_WEATHER" and normalize_competition_id(competition) not in {"CFB", "NCAAFB"}:
            continue
        seeds.append(row)
    if not any(str(r.get("sourceId")) == "WEB_SEARCH" for r in seeds):
        seeds.append({
            "sourceId": "WEB_SEARCH",
            "catalogSourceId": "generic_web_search",
            "adapter": "host.web_search",
            "domain": "*",
            "authorityByClaimType": _AUTHORITY["generic_web_search"],
            "sports": [normalize_competition_id(competition)] if competition else ["*"],
            "fields": ["*"],
            "cost": 3.0,
            "expectedFreshness": 0.4,
            "rateLimit": None,
            "knownFailureModes": [],
            "fallbackSourceIds": [],
        })
    return seeds


def default_sport_source_health(
    *,
    league: str | None = None,
    sport_family: str | None = None,
) -> SourceHealthRegistry:
    """Sport-correct source router derived from the capability catalog."""
    competition = normalize_competition_id(league) if league else ""
    family = sport_family_for_league(competition, fallback=sport_family) if (competition or sport_family) else ""
    if not competition and not family:
        return default_universal_source_health()
    if not family:
        family = sport_family_for_league(competition)
    seeds = _seed_rows_for_competition(family, competition or family.upper())
    return SourceHealthRegistry({"sources": seeds})


def default_universal_source_health(leagues: list[str] | None = None) -> SourceHealthRegistry:
    """Multi-league router for mixed Insights/HAR boards."""
    default_leagues = leagues or ["CFB", "NFL", "WNBA", "NBA", "MLB", "SOCCER"]
    seeds: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for league in default_leagues:
        competition = normalize_competition_id(league)
        family = sport_family_for_league(competition)
        for row in _seed_rows_for_competition(family, competition):
            key = (str(row.get("sourceId") or ""), competition)
            if key in seen:
                continue
            seen.add(key)
            seeds.append(row)
    # Deduplicate identical sourceIds by merging sports lists.
    merged: dict[str, dict[str, Any]] = {}
    for row in seeds:
        sid = str(row.get("sourceId") or "")
        if sid not in merged:
            merged[sid] = dict(row)
            merged[sid]["sports"] = list(row.get("sports") or [])
        else:
            sports = list(merged[sid].get("sports") or [])
            for token in row.get("sports") or []:
                if token not in sports:
                    sports.append(token)
            merged[sid]["sports"] = sports
    return SourceHealthRegistry({"sources": list(merged.values())})
