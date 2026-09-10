"""Deterministic price-board funnel tests.

The funnel is intentionally a structural attention allocator.  These tests
prove that it gates the board without inventing sides, collapses alternate
lines, preserves an auditable leftover list, and never turns a sort key into
an outcome probability.
"""
from __future__ import annotations

import json
from pathlib import Path

from dcm.research.funnel import build_board_funnel, build_legal_universe, write_funnel_artifacts


def _row(pid: str, *, league: str = "NFL", event: str = "E1", player: str | None = None, market: str = "pass_yds", line: float = 240.5, event_label: str = "SF @ LA", **extra: object) -> dict:
    row = {
        "projectionId": pid,
        "playerId": player or f"P-{pid}",
        "playerName": f"Player {pid}",
        "eventId": event,
        "eventLabel": event_label,
        "eventStartTime": "2026-09-10T20:35:00-04:00",
        "league": league,
        "sportFamily": "gridiron" if league in {"NFL", "CFB"} else "baseball",
        "market": market,
        "marketLabel": market,
        "line": line,
        "status": "pre_game",
        "modifier": "STANDARD",
        "boardId": "FULL_GAME",
        "combo": False,
        "allowedWagerTypes": "under_or_over",
        "offeredHigher": True,
        "offeredLower": True,
        "team": "SF" if event == "E1" else f"T-{event}",
        "opponent": "LAR" if event == "E1" else f"O-{event}",
    }
    row.update(extra)
    return row


def test_gates_fail_closed_and_collapse_alt_lines_without_guessing_sides():
    rows = [
        _row("both-a", player="A", line=240.5, isPrimary=True),
        _row("both-a-alt", player="A", line=245.5),
        # Same line split into separate higher/lower records must merge.
        _row("both-b-over", player="B", line=12.5, market="rush_yds", offeredLower=False, allowedWagerTypes="over"),
        _row("both-b-under", player="B", line=12.5, market="rush_yds", offeredHigher=False, allowedWagerTypes="under"),
        _row("cfb-over", league="CFB", event="C1", event_label="OSU @ MICH", player="C", allowedWagerTypes="over", offeredLower=False),
        _row("missing-side", player="D", allowedWagerTypes=None, offeredHigher=False, offeredLower=False),
        _row("goblin", player="E", modifier="GOBLIN"),
        _row("live", player="F", status="in_progress"),
        _row("duration", player="G", boardId="1H"),
        _row("combo", player="H", combo=True),
        _row("td", player="I", market="rush_rec_td", marketLabel="Player Touchdowns"),
        _row("named-combo", player="J", market="pra", marketLabel="Pts+Reb+Ast"),
        _row("unknown-status", player="K", status=None),
        _row("unknown-modifier", player="L", modifier=None),
        _row("missing-line", player="M", line=None),
        _row("unknown-awt", player="N", allowedWagerTypes="side_not_published"),
        _row("contradictory-awt", player="O", allowedWagerTypes="under", offeredHigher=True, offeredLower=False),
        _row("missing-projection", player="P", projectionId=""),
        _row("missing-league", player="Q", league=""),
        _row("boolean-line", player="R", line=True),
    ]

    result = build_legal_universe(rows)
    ids = {row["projectionId"] for row in result["legalRows"]}
    assert ids == {"both-a", "both-b-over", "cfb-over"}
    assert result["altLineCount"] == 1
    assert result["altLineDuplicates"][0]["projectionId"] == "both-a-alt"
    merged = next(row for row in result["legalRows"] if row["playerId"] == "B")
    assert merged["sideClass"] == "BOTH"
    # CFB exposes only Higher even if a malformed row claims a lower flag.
    cfb = next(row for row in result["legalRows"] if row["league"] == "CFB")
    assert cfb["sideClass"] == "OVER_ONLY"
    assert result["gateCounts"]["MISSING_ALLOWED_WAGER_TYPES"] == 1
    assert result["gateCounts"]["MODIFIER_GOBLIN"] == 1
    assert result["gateCounts"]["COMBO_PROP"] == 3
    assert result["gateCounts"]["STATUS_UNKNOWN"] == 1
    assert result["gateCounts"]["MODIFIER_MISSING"] == 1
    assert result["gateCounts"]["LINE_UNRESOLVED"] == 2
    assert result["gateCounts"]["UNKNOWN_ALLOWED_WAGER_TYPES"] == 1
    assert result["gateCounts"]["PROJECTION_ID_UNRESOLVED"] == 1
    assert result["gateCounts"]["LEAGUE_UNRESOLVED"] == 1
    assert result["inputRows"] == (
        len(result["legalRows"])
        + len(result["gateExclusions"])
        + result["altLineCount"]
        + result["sameLineCollapsedCount"]
    )


def test_quota_shortlist_is_deterministic_and_leaves_every_drop_visible():
    rows: list[dict] = []
    # Twelve separate two-way games provide the lower floor and game floor.
    for i in range(12):
        rows.append(_row(f"nfl-{i}", event=f"N{i}", event_label=f"N{i} @ X{i}", player=f"N{i}"))
    # CFB and MLB establish league diversity; CFB is over-only by contract.
    rows.extend(_row(f"cfb-{i}", league="CFB", event=f"C{i}", event_label=f"C{i} @ Y{i}", player=f"C{i}", allowedWagerTypes="over", offeredLower=False) for i in range(4))
    rows.extend(_row(f"mlb-{i}", league="MLB", event=f"M{i}", event_label=f"M{i} @ Z{i}", player=f"M{i}", market="h", sportFamily="baseball") for i in range(4))
    # Reserve two distinct SF@LAR players and add a third candidate to
    # exercise the per-game cap.  The NFL ceiling is exactly reached (14).
    rows.extend(
        [
            _row("sf-a", player="SF-A", event="E1", event_label="SF @ LA"),
            _row("sf-b", player="SF-B", event="E1", event_label="SF @ LA"),
            _row("sf-extra", player="SF-C", event="E1", event_label="SF @ LA"),
        ]
    )

    first = build_board_funnel(rows, min_games=8, min_leagues=3, min_two_way=12)
    second = build_board_funnel(rows, min_games=8, min_leagues=3, min_two_way=12)
    assert first["contentHash"] == second["contentHash"]
    assert [r["projectionId"] for r in first["shortlist"]["selected"]] == [r["projectionId"] for r in second["shortlist"]["selected"]]
    state = first["shortlist"]["state"]
    assert state["rows"] == 22
    assert state["distinctPlayers"] == state["rows"]
    assert state["games"] >= 8
    assert state["leagues"] >= 3
    assert state["twoWay"] >= 12
    assert state["sfLAR"] == 2
    assert first["probabilityHead"] is False
    assert first["predictiveClaim"] == "NONE"
    assert first["productionSelectionPermitted"] is False
    selected = {row["projectionId"] for row in first["shortlist"]["selected"]}
    leftovers = {row["projectionId"] for row in first["shortlist"]["leftover"] if row.get("projectionId")}
    assert selected.isdisjoint(leftovers)
    assert "sf-extra" in leftovers


def test_write_artifacts_are_local_sanitized_receipts(tmp_path: Path):
    board = {"rows": [_row("one"), _row("two", league="CFB", event="C", event_label="A @ B", allowedWagerTypes="over", offeredLower=False)]}
    (tmp_path / "board.json").write_text(json.dumps(board), encoding="utf-8")
    receipt = write_funnel_artifacts(tmp_path)
    assert receipt["artifacts"] == ["research_funnel.json", "gates.json", "leftover.json", "shortlist.json"]
    for name in receipt["artifacts"]:
        assert (tmp_path / name).is_file()
        payload = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert "contentHash" in payload or name == "research_funnel.json"
    funnel = json.loads((tmp_path / "research_funnel.json").read_text(encoding="utf-8"))
    assert funnel["predictiveClaim"] == "NONE"
    assert funnel["outcomesUsed"] is False
    assert funnel["trainingPerformed"] is False
