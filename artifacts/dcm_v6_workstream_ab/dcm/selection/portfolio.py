"""Portfolio constraints, dependency exposure, and simulated failure correlation. Never pad."""
from __future__ import annotations

from collections import Counter
from math import sqrt
from typing import Any

COMPONENTS = {
    "pra": {"pts", "reb", "ast"}, "pr": {"pts", "reb"}, "pa": {"pts", "ast"}, "ra": {"reb", "ast"},
    "pass_rush_yds": {"pass_yds", "rush_yds"}, "rush_rec_yds": {"rush_yds", "rec_yds"},
    "hits_runs_rbi": {"h"},
}
HARD_TAG_PREFIXES = ("INJURY:", "QBUNIT:")


def _tags(p: dict[str, Any]) -> set[str]:
    return set(str(x) for x in (p.get("dependencyTags") or []))


def _composite_conflict(existing_markets: set[str], market: str) -> bool:
    if COMPONENTS.get(market, set()) & existing_markets:
        return True
    return any(market in COMPONENTS.get(existing, set()) for existing in existing_markets)


def _selection_correlation(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    """Pearson correlation of aligned simulated pick outcomes.

    Private outcome bytes encode loss=0, push=1, win=2. Mapping to 0/0.5/1
    keeps pushes neutral and preserves selected-side direction.
    """
    xa = a.get("_selectionOutcomes")
    xb = b.get("_selectionOutcomes")
    if not isinstance(xa, (bytes, bytearray)) or not isinstance(xb, (bytes, bytearray)):
        return None
    n = min(len(xa), len(xb))
    if n < 16:
        return None
    av = [xa[i] / 2.0 for i in range(n)]
    bv = [xb[i] / 2.0 for i in range(n)]
    ma = sum(av) / n
    mb = sum(bv) / n
    va = sum((x - ma) ** 2 for x in av)
    vb = sum((x - mb) ** 2 for x in bv)
    if va <= 1e-12 or vb <= 1e-12:
        return None
    cov = sum((av[i] - ma) * (bv[i] - mb) for i in range(n))
    return cov / sqrt(va * vb)


def build_card(
    qualified: list[dict[str, Any]],
    *,
    max_size: int = 6,
    max_per_event: int = 2,
    max_per_team: int = 2,
    max_shared_dependency: int = 2,
    max_selection_correlation: float = 0.55,
) -> list[dict[str, Any]]:
    card: list[dict[str, Any]] = []
    players: set[str] = set()
    events: Counter[str] = Counter()
    teams: Counter[str] = Counter()
    dependency_counts: Counter[str] = Counter()
    markets_by_player: dict[str, set[str]] = {}

    for p in qualified:
        if len(card) >= max_size:
            break
        row = p["row"]
        if row.get("modifier") == "GOBLIN" or p.get("grade") != "PLAYABLE":
            continue

        pid = str(row["playerId"])
        ev = str(row["eventId"])
        team = str(row.get("teamId") or row.get("team") or "")
        if pid in players or events[ev] >= max_per_event or (team and teams[team] >= max_per_team):
            continue

        market = str(row["market"])
        have = markets_by_player.get(pid, set())
        if _composite_conflict(have, market):
            continue

        tags = _tags(p)
        if any(dependency_counts[t] >= 1 for t in tags if t.startswith(HARD_TAG_PREFIXES)):
            continue
        if any(
            dependency_counts[t] >= max_shared_dependency
            for t in tags
            if not t.startswith("EVENT:") and not t.startswith("TEAM:")
        ):
            continue

        correlated = False
        for existing in card:
            corr = _selection_correlation(existing, p)
            if corr is not None and corr >= max_selection_correlation:
                correlated = True
                break
        if correlated:
            continue

        card.append(p)
        players.add(pid)
        events[ev] += 1
        if team:
            teams[team] += 1
        for tag in tags:
            dependency_counts[tag] += 1
        markets_by_player.setdefault(pid, set()).add(market)

    return card


def exposure_report(card: list[dict[str, Any]]) -> dict[str, Any]:
    events = Counter(str(p["row"].get("eventId")) for p in card)
    teams = Counter(str(p["row"].get("teamId") or p["row"].get("team") or "") for p in card)
    deps = Counter(tag for p in card for tag in _tags(p))
    correlations = []
    for i, a in enumerate(card):
        for b in card[i + 1:]:
            corr = _selection_correlation(a, b)
            if corr is not None:
                correlations.append({
                    "a": str(a["row"].get("projectionId")),
                    "b": str(b["row"].get("projectionId")),
                    "selectionCorrelation": corr,
                })
    correlations.sort(key=lambda x: abs(float(x["selectionCorrelation"])), reverse=True)
    return {
        "players": len({p["row"]["playerId"] for p in card}),
        "events": dict(events),
        "teams": dict(teams),
        "shared_dependencies": {k: v for k, v in deps.items() if v > 1},
        "pairwiseSelectionCorrelations": correlations,
        "maxPositiveSelectionCorrelation": max(
            (float(x["selectionCorrelation"]) for x in correlations),
            default=None,
        ),
    }
