"""P2 FeatureStore: cutoff-immutable window observations, not trained models."""
from __future__ import annotations

import json
from pathlib import Path

from dcm.ml.feature_store import FEATURE_FAMILIES, FeatureStore, persist_feature_store
from dcm.research.player_packet import build_player_research_packet, window_means


ASOF = "2026-08-30T12:00:00Z"


def _fixture_log():
    # Chronological; L5 is the last 5 after sort by date.
    rows = [
        {"date": "2026-06-01", "minutes": 10, "pts": 2, "reb": 1, "ast": 0, "fga": 3, "tpa": 1, "fta": 0},
        {"date": "2026-06-03", "minutes": 12, "pts": 4, "reb": 2, "ast": 1, "fga": 5, "tpa": 2, "fta": 1},
        {"date": "2026-06-05", "minutes": 20, "pts": 8, "reb": 3, "ast": 2, "fga": 7, "tpa": 3, "fta": 2},
        {"date": "2026-06-07", "minutes": 22, "pts": 10, "reb": 4, "ast": 3, "fga": 9, "tpa": 4, "fta": 2},
        {"date": "2026-06-09", "minutes": 24, "pts": 12, "reb": 5, "ast": 4, "fga": 11, "tpa": 5, "fta": 3},
        {"date": "2026-06-11", "minutes": 26, "pts": 14, "reb": 6, "ast": 5, "fga": 13, "tpa": 6, "fta": 4},
        {"date": "2026-06-13", "minutes": 28, "pts": 16, "reb": 7, "ast": 6, "fga": 15, "tpa": 7, "fta": 5},
    ]
    return rows


def test_l5_mean_matches_hand_computed_from_fixture_log():
    logs = _fixture_log()
    packet = build_player_research_packet(
        identity={"playerId": "P1", "eventId": "E1", "league": "WNBA", "sportFamily": "basketball"},
        status="ACTIVE",
        role_hints={"role": "starter"},
        structured_logs=logs,
        as_of=ASOF,
        league="WNBA",
        offer_set={"playerId": "P1", "eventId": "E1", "offerCount": 2, "opponent": "CON", "team": "DAL"},
    )
    last5 = logs[-5:]
    hand_minutes = sum(r["minutes"] for r in last5) / 5
    hand_pts = sum(r["pts"] for r in last5) / 5
    hand_reb = sum(r["reb"] for r in last5) / 5
    hand_ast = sum(r["ast"] for r in last5) / 5
    hand_fga = sum(r["fga"] for r in last5) / 5
    hand_tpa = sum(r["tpa"] for r in last5) / 5
    hand_fta = sum(r["fta"] for r in last5) / 5
    win = window_means(packet["gameLogs"], 5)
    assert abs(win["minutes_mean"] - hand_minutes) < 1e-9
    assert abs(win["pts_mean"] - hand_pts) < 1e-9
    assert abs(win["reb_mean"] - hand_reb) < 1e-9
    assert abs(win["ast_mean"] - hand_ast) < 1e-9
    assert abs(win["fga_mean"] - hand_fga) < 1e-9
    assert abs(win["tpa_mean"] - hand_tpa) < 1e-9
    assert abs(win["fta_mean"] - hand_fta) < 1e-9

    features = FeatureStore.build_from_packet(
        packet,
        {"playerId": "P1", "eventId": "E1", "opponent": "CON", "team": "DAL", "offerCount": 2},
        ASOF,
    )
    by_name = {f["featureName"]: f for f in features}
    assert abs(by_name["L5_minutes_mean"]["value"] - hand_minutes) < 1e-9
    assert abs(by_name["L5_pts_mean"]["value"] - hand_pts) < 1e-9
    assert abs(by_name["L5_reb_mean"]["value"] - hand_reb) < 1e-9
    assert abs(by_name["L5_ast_mean"]["value"] - hand_ast) < 1e-9
    assert abs(by_name["L5_fga_mean"]["value"] - hand_fga) < 1e-9
    assert abs(by_name["L5_tpa_mean"]["value"] - hand_tpa) < 1e-9
    assert abs(by_name["L5_fta_mean"]["value"] - hand_fta) < 1e-9
    rec = by_name["L5_minutes_mean"]
    assert rec["family"] in FEATURE_FAMILIES
    assert rec["cutoffImmutable"] is True
    assert rec["trainedModel"] is False
    assert rec["asOf"] == ASOF
    assert rec["featureSchemaVersion"]
    assert rec["transformationVersion"]
    assert rec["entity"] == "P1"
    assert rec["eventId"] == "E1"
    families = {f["family"] for f in features}
    assert families <= FEATURE_FAMILIES
    assert "ROLE" in families
    assert "OPPORTUNITY" in families
    assert "EFFICIENCY" in families
    assert "MATCHUP" in families
    assert "CONTEXT" in families


def test_persist_writes_jsonl_and_manifest(tmp_path: Path):
    packet = build_player_research_packet(
        identity={"playerId": "P1", "eventId": "E1", "league": "WNBA"},
        structured_logs=_fixture_log(),
        as_of=ASOF,
        league="WNBA",
    )
    man = persist_feature_store(tmp_path, [packet], [{"playerId": "P1", "eventId": "E1"}], ASOF)
    assert man["trainedModel"] is False
    assert man["observationsOnly"] is True
    assert man["mlClaim"] == "NONE"
    assert man["featureCount"] > 0
    assert man["contentHash"]
    lines = (tmp_path / "feature_store.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == man["featureCount"]
    rec = json.loads(lines[0])
    assert rec["cutoffImmutable"] is True
    assert rec["trainedModel"] is False
    dumped = json.loads((tmp_path / "feature_store_manifest.json").read_text(encoding="utf-8"))
    assert dumped["contentHash"] == man["contentHash"]
