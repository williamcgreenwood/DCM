"""TemporalFirewall: observed_at must be <= forecast_cutoff. Leakage fails closed."""

from __future__ import annotations

from datetime import datetime


class TemporalLeakError(RuntimeError):
    def __init__(self, observed_at: str, cutoff: str):
        super().__init__(f"TEMPORAL_LEAK: observed_at {observed_at} > cutoff {cutoff}")
        self.observed_at = observed_at
        self.cutoff = cutoff


def _parse(ts: str) -> datetime:
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def assert_not_after_cutoff(observed_at: str, cutoff: str) -> None:
    if _parse(observed_at) > _parse(cutoff):
        raise TemporalLeakError(observed_at, cutoff)


def filter_claims(claims: list[dict], cutoff: str) -> list[dict]:
    out = []
    for c in claims:
        assert_not_after_cutoff(str(c["observed_at"]), cutoff)
        out.append(c)
    return out
