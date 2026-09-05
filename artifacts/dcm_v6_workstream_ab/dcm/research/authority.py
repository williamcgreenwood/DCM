"""SourceAuthorityRegistry: DCM derives reliability/freshness from source class + timestamps.

The host supplies source/url/timestamps/facts. DCM does not invent sources.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SOURCE_CLASSES: dict[str, dict[str, Any]] = {
    "OFFICIAL_LEAGUE": {"reliability": 0.95, "freshness_halflife_hours": 24.0},
    "OFFICIAL_PLATFORM": {"reliability": 0.90, "freshness_halflife_hours": 6.0},
    "OFFICIAL_TEAM": {"reliability": 0.85, "freshness_halflife_hours": 12.0},
    "BOX_SCORE_VENDOR": {"reliability": 0.80, "freshness_halflife_hours": 12.0},
    "BEAT_REPORTER": {"reliability": 0.55, "freshness_halflife_hours": 6.0},
    "TEST_FROZEN": {"reliability": 0.35, "freshness_halflife_hours": 8760.0},
    "FIXTURE": {"reliability": 0.20, "freshness_halflife_hours": 1.0},
    "UNKNOWN": {"reliability": 0.25, "freshness_halflife_hours": 12.0},
}


def _parse(value: str) -> datetime | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def classify_source(source_id: str, url: str = "") -> str:
    token = f"{source_id} {url}".upper()
    if token.startswith("FIXTURE") or "FIXTURE://" in token:
        return "FIXTURE"
    if "TEST_FROZEN" in token or token.startswith("TEST_"):
        return "TEST_FROZEN"
    if "PRIZEPICKS" in token:
        return "OFFICIAL_PLATFORM"
    if any(k in token for k in ("NBA.COM", "WNBA.COM", "NFL.COM", "NCAA", "LEAGUE")):
        return "OFFICIAL_LEAGUE"
    if "TEAM" in token:
        return "OFFICIAL_TEAM"
    if any(k in token for k in ("BOXSCORE", "BOX_SCORE", "STATSHEET", "BASKETBALL-REFERENCE", "BASKETBALL_REFERENCE", "SPORTS-REFERENCE")):
        return "BOX_SCORE_VENDOR"
    if any(k in token for k in ("BEAT", "REPORTER", "TWITTER", "X.COM")):
        return "BEAT_REPORTER"
    return "UNKNOWN"


def derive_quality(
    *,
    source_id: str,
    url: str = "",
    published_at: str,
    observed_at: str,
    forecast_cutoff: str,
    source_class: str | None = None,
) -> dict[str, Any]:
    klass = source_class or classify_source(source_id, url)
    spec = SOURCE_CLASSES.get(klass) or SOURCE_CLASSES["UNKNOWN"]
    reliability = float(spec["reliability"])
    half = float(spec["freshness_halflife_hours"])
    published = _parse(published_at)
    observed = _parse(observed_at)
    cutoff = _parse(forecast_cutoff)
    freshness = 0.0
    if published and cutoff:
        age_h = max(0.0, (cutoff - published).total_seconds() / 3600.0)
        freshness = 0.5 ** (age_h / half) if half > 0 else 0.0
        if observed and observed > cutoff:
            freshness = 0.0
    return {
        "source_class": klass,
        "reliability": round(reliability, 6),
        "freshness": round(min(1.0, max(0.0, freshness)), 6),
        "freshness_halflife_hours": half,
        "host_supplies": ["source_id", "url", "published_at", "observed_at", "claim_value"],
        "dcm_derives": ["reliability", "freshness", "source_class"],
    }


class SourceAuthorityRegistry:
    """Lookup table + derivation. Host never writes reliability/freshness as authority."""

    def __init__(self, extra: dict[str, dict[str, Any]] | None = None):
        self.classes = {**SOURCE_CLASSES, **(extra or {})}

    def derive(self, **kwargs: Any) -> dict[str, Any]:
        return derive_quality(**kwargs)
