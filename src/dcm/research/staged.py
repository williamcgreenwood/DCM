"""Staged research: Pass A foundational vs Pass B serious-candidate deepening.

Pass A: every eligible player/team/event gets a valid baseline packet.
Pass B: high-value / grade-border / rank-unstable / thin-support candidates
receive same-opponent windows, home/road splits, lineup/on-off, and late
status confirmation. Pass B never replaces the full log.
"""
from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.lineup import build_lineup_effects
from dcm.research.player_packet import window_means


PASS_A = "FOUNDATIONAL"
PASS_B = "SERIOUS_CANDIDATE_DEEPENING"
BORDER_GRADES = frozenset({"PLAYABLE", "LEAN"})


def _f_home(row: dict[str, Any]) -> bool | None:
    if "home" in row:
        return bool(row.get("home"))
    loc = str(row.get("location") or row.get("game_location") or "").lower()
    if loc in {"home", "h"}:
        return True
    if loc in {"away", "road", "@", "a"}:
        return False
    return None


def _same_opponent(logs: list[dict[str, Any]], opponent: str) -> list[dict[str, Any]]:
    want = str(opponent or "").strip().upper()
    if not want:
        return []
    out = []
    for row in logs:
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        label = str(row.get("opponent") or row.get("opp") or raw.get("opp_id") or raw.get("opp") or "").upper()
        if want and want in label:
            out.append(row)
    return out


def pass_b_needed(
    packet: dict[str, Any],
    offer_set: dict[str, Any] | None = None,
    *,
    grade: str | None = None,
    rank: int | None = None,
) -> bool:
    """Deepen when the candidate is serious, thin, or near a decision boundary."""
    if str(grade or "").upper() in BORDER_GRADES:
        return True
    if rank is not None and rank <= 30:
        return True
    n = int(packet.get("gameLogCount") or 0)
    if 0 < n < 8:
        return True
    offers = int((offer_set or {}).get("offerCount") or len((offer_set or {}).get("offers") or packet.get("appliesToProjectionIds") or []))
    if offers >= 6:
        return True
    if packet.get("thin"):
        return False
    return False


def deepen_player_packet(
    packet: dict[str, Any],
    offer_set: dict[str, Any] | None = None,
    *,
    lineup_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a Pass-B overlay. Does not mutate Pass A or replace the full log."""
    logs = [r for r in (packet.get("gameLogs") or []) if isinstance(r, dict)]
    ident = packet.get("identity") if isinstance(packet.get("identity"), dict) else {}
    opponent = str((offer_set or {}).get("opponent") or ident.get("opponent") or "")
    same = _same_opponent(logs, opponent)
    home_logs = [r for r in logs if _f_home(r) is True]
    road_logs = [r for r in logs if _f_home(r) is False]
    lineup = build_lineup_effects(lineup_rows or [])
    overlay = {
        "pass": PASS_B,
        "sameOpponent": {
            "opponent": opponent,
            "nAvailable": len(same),
            "window": window_means(same, max(len(same), 1)) if same else None,
            "doesNotReplaceFullLog": True,
            "shrinkTowardSeason": True,
        },
        "home": window_means(home_logs, max(len(home_logs), 1)) if home_logs else None,
        "road": window_means(road_logs, max(len(road_logs), 1)) if road_logs else None,
        "lineupOnOff": lineup,
        "fullSeasonRetained": True,
        "fullLogCount": len(logs),
    }
    overlay["contentHash"] = content_hash(overlay)
    out = dict(packet)
    out["passB"] = overlay
    out["researchPass"] = PASS_B
    return out


def stage_research(
    packets: list[dict[str, Any]],
    offer_sets: list[dict[str, Any]] | None = None,
    *,
    grades: dict[str, str] | None = None,
    ranks: dict[str, int] | None = None,
) -> dict[str, Any]:
    sets = {str(s.get("setId") or ""): s for s in (offer_sets or [])}
    by_player_event = {(str(s.get("playerId") or ""), str(s.get("eventId") or "")): s for s in (offer_sets or [])}
    pass_a: list[dict[str, Any]] = []
    pass_b: list[dict[str, Any]] = []
    for packet in packets or []:
        ident = packet.get("identity") if isinstance(packet.get("identity"), dict) else {}
        offer = sets.get(str(packet.get("offerSetId") or "")) or by_player_event.get(
            (str(ident.get("playerId") or ""), str(ident.get("eventId") or ""))
        )
        tagged = dict(packet)
        tagged.setdefault("researchPass", PASS_A)
        pass_a.append(tagged)
        key = str(ident.get("playerId") or "")
        grade = (grades or {}).get(key)
        rank = (ranks or {}).get(key)
        if pass_b_needed(packet, offer, grade=grade, rank=rank):
            pass_b.append(deepen_player_packet(packet, offer))
    body = {
        "schema": "pillars_dcm.staged_research.v1",
        "passA": PASS_A,
        "passB": PASS_B,
        "passACount": len(pass_a),
        "passBCount": len(pass_b),
        "passAPlayerIds": [
            str((p.get("identity") or {}).get("playerId") or "") for p in pass_a
        ],
        "passBPlayerIds": [
            str((p.get("identity") or {}).get("playerId") or "") for p in pass_b
        ],
        "packetsPassB": pass_b,
        "rule": "Pass A is universal baseline. Pass B deepens serious candidates without replacing the full log.",
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash" and k != "packetsPassB"})
    return body
