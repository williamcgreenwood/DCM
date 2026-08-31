"""Team/opponent/event packets: one team researched once, reused as opponent."""
from __future__ import annotations

from pathlib import Path

from dcm.identity.resolve import build_player_index
from dcm.model.parameters import build_parameter_snapshot
from dcm.research.adapters.basketball_reference import (
    BasketballReferenceOnOffAdapter,
    BasketballReferenceTeamAdapter,
    BasketballReferenceTeamGameLogAdapter,
)
from dcm.research.claims import claim_record
from dcm.research.entity_graph import build_entity_graph
from dcm.research.entity_packets import (
    build_entity_packets,
    build_event_research_packet,
    build_opponent_research_packet,
    build_team_research_packet,
)
from dcm.research.player_offer_set import build_player_offer_sets
from dcm.research.player_packet import build_player_research_packet
from dcm.research.requests import plan_research
from dcm.research.staged import PASS_A, PASS_B, deepen_player_packet, stage_research


FIXTURES = Path(__file__).resolve().parent / "research_fixtures"
ASOF = "2026-08-30T12:00:00Z"
CUTOFF = ASOF


def _team_logs(n=12, opp="CON"):
    logs = []
    for i in range(n):
        logs.append({
            "date_game": f"2026-06-{(i % 27) + 1:02d}",
            "opp": opp if i % 4 == 0 else "NYL",
            "home": i % 2 == 0,
            "pts": 80 + (i % 12),
            "opp_pts": 78 + (i % 10),
            "fga": 68 + (i % 6),
            "fta": 18 + (i % 4),
            "tov": 13 + (i % 3),
            "oreb": 9 + (i % 3),
        })
    return logs


def _paige_rows(n=8):
    markets = ["pts", "pra", "reb", "ast", "pr", "pa", "ra", "3pm"]
    rows = []
    for i, mkt in enumerate(markets[:n]):
        rows.append({
            "projectionId": f"pp{i}",
            "playerId": "PAIGE",
            "playerName": "Paige Bueckers",
            "sportFamily": "basketball",
            "league": "WNBA",
            "team": "DAL",
            "teamId": "DAL",
            "opponent": "CON",
            "eventId": "E1",
            "eventLabel": "CON @ DAL",
            "eventStartTime": "2026-08-30T21:30:00Z",
            "market": mkt,
            "line": 10.5 + i,
            "modifier": "STANDARD",
            "offeredHigher": True,
            "offeredLower": True,
            "boardId": "FULL_GAME",
            "status": "pre_game",
        })
    rows.append({
        **{k: v for k, v in rows[0].items() if k not in {"projectionId", "playerId", "playerName", "market"}},
        "projectionId": "ari0",
        "playerId": "ARIKE",
        "playerName": "Arike Ogunbowale",
        "market": "pts",
        "line": 18.5,
    })
    return rows


def _claim(scope, scope_id, value, url="https://www.basketball-reference.com/wnba/teams/DAL/2026.html"):
    return claim_record(
        source_id="BASKETBALL_REFERENCE",
        url=url,
        published_at="2026-08-29T00:00:00Z",
        observed_at="2026-08-29T12:00:00Z",
        forecast_cutoff=CUTOFF,
        semantic_scope=scope,
        scope_id=scope_id,
        claim_type="role_pace_matchup",
        claim_value=value,
        reliability=0.8,
        freshness=0.7,
    )


def test_one_dal_packet_serves_every_dal_player_and_is_reused_as_opponent():
    rows = _paige_rows()
    sets = build_player_offer_sets(rows)
    claims = [
        _claim("TEAM", "DAL", {"team_logs": _team_logs()}),
        _claim("TEAM", "CON", {"team_logs": _team_logs(n=10, opp="DAL")}),
        _claim("EVENT", "E1", {
            "scheduled_start": "2026-08-30T21:30:00Z",
            "venue": "College Park Center",
            "environment": "indoor",
            "starters_known": True,
        }, url="https://www.wnba.com/game/E1"),
    ]
    docs = build_entity_packets(sets, claims=claims, as_of=ASOF)
    dal = next(t for t in docs["teams"] if t["teamId"] == "DAL")
    con = next(t for t in docs["teams"] if t["teamId"] == "CON")
    assert dal["gameLogCount"] >= 3
    assert dal["evidenceUsed"] is True
    assert dal["priorUsedAsResearch"] is False
    assert dal["ortg"] is not None
    assert dal["drtg"] is not None
    assert dal["pace"] is not None
    assert "PAIGE" in dal["appliesToPlayerIds"]
    assert "ARIKE" in dal["appliesToPlayerIds"]
    assert docs["teamPacketCount"] == 2
    opp_con = next(o for o in docs["opponents"] if o["teamId"] == "CON" and o["versusTeamId"] == "DAL")
    assert opp_con["reusedTeamPacketId"] == con["packetId"]
    assert opp_con["reusedTeamPacketHash"] == con["contentHash"]
    assert opp_con["h2hDominates"] is False
    ev = docs["events"][0]
    assert ev["scheduledStart"]
    assert ev["venue"] == "College Park Center"
    assert ev["evidenceUsed"] is True


def test_fixture_team_prior_is_not_research():
    packet = build_team_research_packet(
        team_id="DAL",
        league="WNBA",
        sport_family="basketball",
        claims=[_claim("TEAM", "DAL", {"pace_multiplier": 1.0, "matchup_efficiency_multiplier": 1.0, "injury_cluster": False})],
        as_of=ASOF,
    )
    assert packet["evidenceUsed"] is False
    assert packet["thin"] is True
    assert packet["priorUsedAsResearch"] is False
    assert packet["fixturePriorOnly"] is True
    assert "FIXTURE_TEAM_PRIOR" in packet["flags"]


def test_team_html_adapter_drives_ortg_drtg_pace():
    html = (FIXTURES / "br_team_dal.html").read_text(encoding="utf-8")
    recs = BasketballReferenceTeamAdapter(retrieved_at=ASOF).normalize({
        "html": html,
        "url": "https://www.basketball-reference.com/wnba/teams/DAL/2026.html",
        "retrievedAt": ASOF,
        "publishedAt": ASOF,
    })
    assert recs
    fields = recs[0]["fields"]
    assert float(fields["pace"]) == 82.4
    assert float(fields["ortg"]) == 105.4
    assert float(fields["drtg"]) == 102.1
    gamelog_html = (FIXTURES / "br_team_gamelog_dal.html").read_text(encoding="utf-8")
    packet = build_team_research_packet(
        team_id="DAL",
        league="WNBA",
        gamelog_html=gamelog_html,
        as_of=ASOF,
        source_url="https://www.basketball-reference.com/wnba/teams/DAL/2026/gamelog/",
    )
    assert packet["gameLogCount"] == 4
    assert packet["evidenceUsed"] is True
    assert packet["ortg"] is not None
    assert packet["paceMultiplier"] is not None
    assert abs(packet["paceMultiplier"] - (packet["pace"] / 80.0)) < 1e-9


def test_team_html_alone_drives_ortg_drtg_pace_not_silent_1_0():
    html = (FIXTURES / "br_team_dal.html").read_text(encoding="utf-8")
    packet = build_team_research_packet(
        team_id="DAL",
        league="WNBA",
        sport_family="basketball",
        team_html=html,
        as_of=ASOF,
        source_url="https://www.basketball-reference.com/wnba/teams/DAL/2026.html",
    )
    assert packet["evidenceUsed"] is True
    assert packet["fixturePriorOnly"] is False
    assert packet["priorUsedAsResearch"] is False
    assert abs(float(packet["pace"]) - 82.4) < 1e-9
    assert abs(float(packet["ortg"]) - 105.4) < 1e-9
    assert abs(float(packet["drtg"]) - 102.1) < 1e-9
    assert packet["parameterFields"]["ortg"] is not None


def test_onoff_adapter_and_shrinkage_caps_tiny_samples():
    html = (FIXTURES / "br_onoff_dal.html").read_text(encoding="utf-8")
    recs = BasketballReferenceOnOffAdapter(retrieved_at=ASOF).normalize({
        "html": html,
        "url": "https://www.basketball-reference.com/wnba/teams/DAL/2026/on-off/",
        "retrievedAt": ASOF,
        "publishedAt": ASOF,
    })
    assert recs[0]["fields"]["player"] == "Paige Bueckers"
    from dcm.research.lineup import shrink_lineup_effect
    tiny = shrink_lineup_effect(0.40, 12.0, max_abs=0.08)
    assert tiny["applied"] is True
    assert abs(tiny["shrunkenEffect"]) <= 0.08
    assert tiny["rawEffect"] == 0.40
    empty = shrink_lineup_effect(None, 0)
    assert empty["applied"] is False
    assert empty["reason"] == "LINEUP_SAMPLE_EMPTY"


def test_snapshot_uses_team_packet_ortg_not_silent_1_0():
    logs = _team_logs(12)
    packet = build_team_research_packet(
        team_id="DAL", league="WNBA", sport_family="basketball",
        structured_logs=logs, as_of=ASOF,
    )
    opp = build_team_research_packet(
        team_id="CON", league="WNBA", sport_family="basketball",
        structured_logs=_team_logs(12, opp="DAL"), as_of=ASOF,
    )
    row = {
        "projectionId": "p1", "sportFamily": "basketball", "league": "WNBA",
        "eventId": "E1", "teamId": "DAL", "team": "DAL", "opponent": "CON",
        "playerId": "PAIGE", "market": "pts", "boardId": "FULL_GAME", "line": 21.5, "role": "G",
    }
    claims = [
        _claim("SPORT", "basketball:WNBA", {"distribution_family": "count"}),
        _claim("EVENT", "E1", {"scheduled_start": ASOF, "venue": "CPC", "environment": "indoor", "starters_known": True}),
        _claim("TEAM", "DAL", {"pace_multiplier": 1.0, "matchup_efficiency_multiplier": 1.0}),
        _claim("PLAYER", "PAIGE", {
            "status": "ACTIVE", "role": "starter",
            "opportunity": {"support_n": 5, "minutes_mean": 32.0},
            "efficiency": {"support_n": 5},
            "role_epoch_logs": [
                {"minutes": 30, "fga": 14, "reb": 6, "ast": 4, "pts": 22},
                {"minutes": 32, "fga": 16, "reb": 5, "ast": 5, "pts": 24},
                {"minutes": 34, "fga": 15, "reb": 7, "ast": 3, "pts": 21},
            ],
        }),
        _claim("MARKET_DEFINITION", "prizepicks|WNBA|pts|FULL_GAME", {"definition_verified": True, "stat": "points"}),
        _claim("OFFER", "p1", {"offer_recorded": True, "line": 21.5, "offeredHigher": True, "offeredLower": True}),
    ]
    snap = build_parameter_snapshot(
        row, claims,
        team_packets={"DAL": packet, "CON": opp},
    )
    assert snap["teamEvidenceUsed"] is True
    assert snap["teamPriorUsedAsResearch"] is False
    assert snap["parameters"]["ortg"] is not None
    assert snap["parameters"]["drtg"] is not None
    assert snap["parameters"]["opponent_ortg"] is not None
    assert snap["parameters"]["paceFromTeamPacket"] is True
    assert snap["availabilityMixture"]["status"] == "ACTIVE"
    assert snap["availabilityMixture"]["playableBlockedByMixture"] is False


def test_entity_graph_reuses_one_team_node():
    rows = _paige_rows()
    sets = build_player_offer_sets(rows)
    docs = build_entity_packets(sets, claims=[], as_of=ASOF)
    player_packets = [
        build_player_research_packet(
            identity={"playerId": s["playerId"], "eventId": s["eventId"], "league": "WNBA"},
            structured_logs=[{"mp": 32, "pts": 20, "trb": 4, "ast": 5, "fga": 14}] * 5,
            offer_set=s, as_of=ASOF, league="WNBA",
        )
        for s in sets
    ]
    graph = build_entity_graph(
        sets,
        team_packets=docs["teams"],
        event_packets=docs["events"],
        opponent_packets=docs["opponents"],
        player_packets=player_packets,
    )
    team_nodes = [n for n in graph["nodes"] if n["type"] == "Team"]
    assert {n["teamId"] for n in team_nodes} == {"DAL", "CON"}
    reuse = [e for e in graph["edges"] if e["type"] == "reuses"]
    assert reuse
    oppose = [e for e in graph["edges"] if e["type"] == "opposes"]
    assert oppose
    assert graph["schema"] == "pillars_dcm.entity_graph.v1"


def test_staged_pass_a_everyone_pass_b_deepens_without_replacing_log():
    logs = []
    for i in range(37):
        logs.append({
            "date_game": f"2026-05-{(i % 28) + 1:02d}",
            "mp": "32:00", "pts": 20, "trb": 4, "ast": 6, "fga": 15,
            "opp": "CON" if i >= 34 else "NYL",
            "home": i % 2 == 0,
        })
    packet = build_player_research_packet(
        identity={"playerId": "PAIGE", "league": "WNBA", "opponent": "CON", "eventId": "E1"},
        structured_logs=logs, as_of=ASOF, league="WNBA",
        offer_set={"setId": "POS|PAIGE|E1", "offerCount": 12, "opponent": "CON", "offers": [{"projectionId": f"p{i}"} for i in range(12)]},
    )
    assert packet["gameLogCount"] == 37
    staged = stage_research([packet], [{"setId": "POS|PAIGE|E1", "playerId": "PAIGE", "eventId": "E1", "offerCount": 12, "opponent": "CON", "offers": [{"projectionId": f"p{i}"} for i in range(12)]}])
    assert staged["passACount"] == 1
    assert staged["passBCount"] == 1
    deep = staged["packetsPassB"][0]
    assert deep["passB"]["fullSeasonRetained"] is True
    assert deep["passB"]["fullLogCount"] == 37
    assert deep["passB"]["sameOpponent"]["doesNotReplaceFullLog"] is True
    assert deep["gameLogCount"] == 37
    overlay = deepen_player_packet(packet, {"opponent": "CON", "offerCount": 12})
    assert overlay["researchPass"] == PASS_B
    assert packet.get("researchPass") in {None, PASS_A}


def test_plan_research_fans_out_opponent_as_team():
    rows = _paige_rows(3)
    planned = plan_research(rows, CUTOFF)
    team_ids = {r["scope_id"] for r in planned["requests"] if r["scope"] == "TEAM"}
    assert "DAL" in team_ids
    assert "CON" in team_ids
    dal = next(r for r in planned["requests"] if r["scope"] == "TEAM" and r["scope_id"] == "DAL")
    assert dal["dependent_prop_count"] >= 3


def test_player_index_groups_offers_name_is_not_id():
    rows = _paige_rows()
    idx = build_player_index(rows)
    assert idx["nameIsNotId"] is True
    paige = next(p for p in idx["players"] if p["playerId"] == "PAIGE")
    assert paige["offerCount"] == 8
    assert paige["playerName"] == "Paige Bueckers"
    assert "E1" in paige["events"]
