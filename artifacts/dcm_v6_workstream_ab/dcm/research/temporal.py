"""Temporal firewall for evidence. Future publication or observation fails closed."""

from __future__ import annotations

from datetime import datetime


class TemporalLeakError(RuntimeError):
    def __init__(self, value: str, cutoff: str, field: str = "observed_at"):
        super().__init__(f"TEMPORAL_LEAK: {field} {value} > cutoff {cutoff}")
        self.observed_at = value  # backwards-compatible attribute
        self.value = value
        self.cutoff = cutoff
        self.field = field


def _parse(ts: str) -> datetime:
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def assert_not_after_cutoff(value: str, cutoff: str, *, field: str = "observed_at") -> None:
    if _parse(value) > _parse(cutoff):
        raise TemporalLeakError(value, cutoff, field)


def filter_claims(claims: list[dict], cutoff: str) -> list[dict]:
    out = []
    for claim in claims:
        assert_not_after_cutoff(str(claim["observed_at"]), cutoff, field="observed_at")
        published = str(claim.get("published_at") or "").strip()
        if published:
            assert_not_after_cutoff(published, cutoff, field="published_at")
        out.append(claim)
    return out
