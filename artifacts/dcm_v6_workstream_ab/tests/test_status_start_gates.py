"""P0 status/start hard gates: Bonner-shaped PLAYER_STATUS_UNCERTAIN cannot be PLAYABLE."""
from __future__ import annotations

from dcm.model.parameters import build_parameter_snapshot
from dcm.selection.card_layers import (
    EVENT_ALREADY_STARTED,
    PLAYER_NOT_ACTIVE,
    PLAYER_STATUS_UNCERTAIN,
    apply_pre_freeze_status_start_gates,
    is_modeled_playable,
    started_event_blocker,
    status_start_hard_blocker,
)
from dcm.selection.portfolio import build_card

# Freeze time from PR #9 RUN_60612c8a7bcf7df1. MIN @ ATL had already started.
BONNER_CUTOFF = "2026-08-30T19:43:12Z"
BONNER_EVENT_START = "2026-08-30T19:00:00Z"

# Slim card row as archived in PR #9 (grade PLAYABLE + modeledPlayable true was INCORRECT).
BONNER_SLIM = {
    "rank": 1,
    "sportFamily": "basketball",
    "league": "WNBA",
    "player": "DeWanna Bonner",
    "team": "ATL",
    "opponent": "MIN",
    "event": "MIN @ ATL",
    "market": "pts",
    "line": 6.5,
    "direction": "MORE",
    "modifier": "STANDARD",
    "grade": "PLAYABLE",
    "state": "MODELED",
    "blocker": "PLAYER_STATUS_UNCERTAIN",
    "productionSelectable": False,
    "modeledPlayable": True,
    "dependencyTags": ["EVENT:176427", "ROLE:ATL:questionable", "TEAM:ATL"],
    "projectionId": "14287889",
}


def _row(**overrides) -> dict:
    row = {
        "projectionId": "14287889",
        "sportFamily": "basketball",
        "league": "WNBA",
        "eventId": "176427",
        "eventLabel": "MIN @ ATL",
        "playerId": "BONNER",
        "playerName": "DeWanna Bonner",
        "teamId": "ATL",
        "team": "ATL",
        "opponent": "MIN",
        "market": "pts",
        "line": 6.5,
        "side": "MORE",
        "offeredHigher": True,
        "offeredLower": True,
        "modifier": "STANDARD",
        "boardId": "FULL_GAME",
        "productType": "PLAYER_PICKS",
        "role": "questionable",
        "eventStartTime": BONNER_EVENT_START,
        "status": "pre_game",
        "isLive": False,
    }
    row.update(overrides)
    return row


def _cand(*, grade="PLAYABLE", blocker=None, row=None, snapshot=None, tags=None, **extra) -> dict:
    r = row if row is not None else _row()
    p = {
        "grade": grade,
        "state": "MODELED",
        "blocker": blocker,
        "productionSelectable": False,
        "modeledPlayable": True,
        "selectedSide": "MORE",
        "evidenceSafeP": 0.65,
        "rank": 1,
        "row": r,
        "forecastCutoff": BONNER_CUTOFF,
        "dependencyTags": tags if tags is not None else [
            "EVENT:176427", "ROLE:ATL:questionable", "TEAM:ATL",
        ],
        "playerStatus": (snapshot or {}).get("status"),
    }
    if snapshot is not None:
        p["parameterSnapshot"] = snapshot
    p.update(extra)
    return p


def _claim(scope: str, scope_id: str, value: dict, h: str) -> dict:
    return {
        "semantic_scope": scope,
        "scope_id": scope_id,
        "claim_value": value,
        "source_id": "OFFICIAL",
        "reliability": 0.95,
        "freshness": 0.95,
        "claim_hash": h,
        "observed_at": "2026-08-30T18:00:00Z",
    }


def _active_logs() -> list[dict]:
    return [{"minutes": 28, "fga": 12, "reb": 5, "ast": 3} for _ in range(5)]


def test_bonner_status_uncertain_not_playable():
    assert BONNER_SLIM["blocker"] == PLAYER_STATUS_UNCERTAIN
    assert BONNER_SLIM["grade"] == "PLAYABLE"
    assert is_modeled_playable(BONNER_SLIM) is False
    assert status_start_hard_blocker(BONNER_SLIM) == PLAYER_STATUS_UNCERTAIN

    nested = _cand(
        blocker=PLAYER_STATUS_UNCERTAIN,
        snapshot={"status": "QUESTIONABLE", "blocker": PLAYER_STATUS_UNCERTAIN, "production_eligible": False},
    )
    assert is_modeled_playable(nested, cutoff=BONNER_CUTOFF, snapshot=nested["parameterSnapshot"]) is False
    assert build_card([nested]) == []
    # Snapshot blocker alone (accounting blocker None) still cannot be modeledPlayable.
    snap_only = _cand(
        blocker=None,
        snapshot={"status": "QUESTIONABLE", "blocker": PLAYER_STATUS_UNCERTAIN, "production_eligible": False},
        tags=["EVENT:176427", "ROLE:ATL:questionable", "TEAM:ATL"],
    )
    assert is_modeled_playable(snap_only, snapshot=snap_only["parameterSnapshot"]) is False
    assert build_card([snap_only]) == []

    logs = _active_logs()
    claims = [
        _claim("PLAYER", "BONNER", {
            "status": "QUESTIONABLE",
            "role": "questionable",
            "game_logs": logs,
            "opportunity": {"support_n": 5},
            "efficiency": {"support_n": 5},
        }, "p"),
        _claim("TEAM", "ATL", {"pace_multiplier": 1.0}, "t"),
        _claim("EVENT", "176427", {"scheduled_start": BONNER_EVENT_START}, "e"),
        _claim("MARKET_DEFINITION", "prizepicks|WNBA|pts|FULL_GAME", {"definition_verified": True}, "d"),
    ]
    snap = build_parameter_snapshot(_row(), claims)
    assert snap["blocker"] == PLAYER_STATUS_UNCERTAIN
    assert snap["production_eligible"] is False
    assert is_modeled_playable(
        {"row": _row(), "grade": "PLAYABLE", "state": "MODELED", "blocker": None},
        cutoff=BONNER_CUTOFF,
        snapshot=snap,
    ) is False


def test_started_event_not_on_card():
    row = _row(
        playerId="HILLMON",
        playerName="Naz Hillmon",
        role="starter",
        eventStartTime=BONNER_EVENT_START,
        status="pre_game",
        isLive=False,
        projectionId="14266059",
    )
    p = _cand(
        blocker=None,
        row=row,
        snapshot={"status": "ACTIVE", "blocker": None, "production_eligible": True},
        tags=["EVENT:176427", "ROLE:ATL:starter", "TEAM:ATL"],
    )
    assert started_event_blocker(row, BONNER_CUTOFF) == EVENT_ALREADY_STARTED
    assert is_modeled_playable(p, cutoff=BONNER_CUTOFF) is False
    assert build_card([p]) == []

    live = _cand(
        blocker=None,
        row=_row(status="in_progress", isLive=True, eventStartTime="2026-08-30T23:00:00Z"),
        snapshot={"status": "ACTIVE", "blocker": None},
        tags=["EVENT:176427", "ROLE:ATL:starter", "TEAM:ATL"],
    )
    assert is_modeled_playable(live, cutoff=BONNER_CUTOFF) is False
    assert build_card([live]) == []

    future = _cand(
        blocker=None,
        row=_row(eventStartTime="2026-08-30T23:00:00Z", status="pre_game", isLive=False),
        snapshot={"status": "ACTIVE", "blocker": None},
        tags=["EVENT:176427", "ROLE:ATL:starter", "TEAM:ATL"],
    )
    assert is_modeled_playable(future, cutoff=BONNER_CUTOFF) is True
    assert [c["row"]["projectionId"] for c in build_card([future])] == ["14287889"]


def test_out_player_not_playable():
    for status, blocker in (
        ("OUT", PLAYER_NOT_ACTIVE),
        ("INACTIVE", PLAYER_NOT_ACTIVE),
        ("SUSPENDED", PLAYER_NOT_ACTIVE),
    ):
        p = _cand(
            blocker=None,
            row=_row(eventStartTime="2026-08-30T23:00:00Z", role="out"),
            snapshot={"status": status, "blocker": blocker, "production_eligible": False},
            tags=["EVENT:176427", f"ROLE:ATL:{status.lower()}", "TEAM:ATL"],
        )
        assert is_modeled_playable(p, cutoff=BONNER_CUTOFF, snapshot=p["parameterSnapshot"]) is False
        assert build_card([p]) == []

    logs = _active_logs()
    claims = [
        _claim("PLAYER", "BONNER", {
            "status": "OUT",
            "role": "out",
            "game_logs": logs,
            "opportunity": {"support_n": 5},
            "efficiency": {"support_n": 5},
        }, "p"),
        _claim("TEAM", "ATL", {"pace_multiplier": 1.0}, "t"),
        _claim("EVENT", "176427", {"scheduled_start": "2026-08-30T23:00:00Z"}, "e"),
        _claim("MARKET_DEFINITION", "prizepicks|WNBA|pts|FULL_GAME", {"definition_verified": True}, "d"),
    ]
    snap = build_parameter_snapshot(_row(eventStartTime="2026-08-30T23:00:00Z"), claims)
    assert snap["blocker"] == PLAYER_NOT_ACTIVE
    assert is_modeled_playable(
        {
            "row": _row(eventStartTime="2026-08-30T23:00:00Z"),
            "grade": "PLAYABLE",
            "state": "MODELED",
            "blocker": None,
        },
        cutoff=BONNER_CUTOFF,
        snapshot=snap,
    ) is False


def test_healthy_playable_still_makes_card():
    p = _cand(
        blocker=None,
        row=_row(
            eventStartTime="2026-08-30T23:00:00Z",
            role="starter",
            playerId="OK",
            playerName="Healthy",
            projectionId="ok1",
        ),
        snapshot={"status": "ACTIVE", "blocker": None, "production_eligible": True},
        tags=["EVENT:176427", "ROLE:ATL:starter", "TEAM:ATL"],
    )
    assert is_modeled_playable(p, cutoff=BONNER_CUTOFF) is True
    card = build_card([p])
    assert len(card) == 1


def test_pre_freeze_strip_uncertain_and_started():
    nested = _cand(
        blocker=PLAYER_STATUS_UNCERTAIN,
        snapshot={"status": "QUESTIONABLE", "blocker": PLAYER_STATUS_UNCERTAIN},
    )
    started = _cand(
        blocker=None,
        row=_row(eventStartTime=BONNER_EVENT_START, role="starter"),
        snapshot={"status": "ACTIVE", "blocker": None},
        tags=["EVENT:176427", "ROLE:ATL:starter", "TEAM:ATL"],
    )
    healthy = _cand(
        blocker=None,
        row=_row(eventStartTime="2026-08-30T23:00:00Z", role="starter", projectionId="ok-healthy"),
        snapshot={"status": "ACTIVE", "blocker": None},
        tags=["EVENT:176427", "ROLE:ATL:starter", "TEAM:ATL"],
    )
    qualified = apply_pre_freeze_status_start_gates(
        [nested, started, healthy], cutoff=BONNER_CUTOFF
    )
    assert [p["row"]["projectionId"] for p in qualified] == ["ok-healthy"]
    assert nested["modeledPlayable"] is False
    assert started["modeledPlayable"] is False
