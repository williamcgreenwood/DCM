"""Portfolio controls. Unique player, event cap, composite overlap. Never pad."""

from __future__ import annotations

from typing import Any

COMPONENTS = {
    "pra": {"pts", "reb", "ast"},
    "pass_rush_yds": {"pass_yds", "rush_yds"},
    "rush_rec_yds": {"rush_yds", "rec_yds"},
    "hits_runs_rbi": {"h"},
}


def build_card(qualified: list[dict[str, Any]], *, max_size: int = 6, max_per_event: int = 2) -> list[dict[str, Any]]:
    card: list[dict[str, Any]] = []
    players: set[str] = set()
    events: dict[str, int] = {}
    markets_by_player: dict[str, set[str]] = {}
    for p in qualified:
        if len(card) >= max_size:
            break
        row = p["row"]
        if row.get("modifier") == "GOBLIN":
            continue
        pid = row["playerId"]
        if pid in players:
            continue
        ev = row["eventId"]
        if events.get(ev, 0) >= max_per_event:
            continue
        m = row["market"]
        have = markets_by_player.get(pid, set())
        overlap = COMPONENTS.get(m, set()) & have
        if overlap:
            continue
        # component vs existing composite
        blocked = False
        for existing in have:
            if m in COMPONENTS.get(existing, set()):
                blocked = True
        if blocked:
            continue
        card.append(p)
        players.add(pid)
        events[ev] = events.get(ev, 0) + 1
        markets_by_player.setdefault(pid, set()).add(m)
    return card
