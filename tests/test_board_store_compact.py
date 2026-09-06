"""Phase 7–8: BoardStore SoA semantics + compact Feature/Parameter matrices."""
from __future__ import annotations

import time

import numpy as np

from dcm.board_store import BoardStore, board_store_matches_index_semantics
from dcm.compact import (
    CompactNumericBoard,
    feature_matrix_from_records,
    parameter_matrix_from_snapshots,
    round_trip_id_maps,
)
from dcm.research.indexes import BoardIndexes


def _rows():
    return [
        {
            "projectionId": "o1",
            "playerName": "John Smith",
            "team": "ALA",
            "teamId": "ALA",
            "market": "pass_yds",
            "sportFamily": "gridiron",
            "league": "CFB",
            "eventId": "E1",
            "playerId": "P1",
            "line": 225.5,
            "reliability": 0.7,
            "fragility": 0.2,
            "oodRisk": 0.1,
            "mean": 230.0,
            "variance": 400.0,
        },
        {
            "projectionId": "o2",
            "playerName": "Jane Doe",
            "team": "UGA",
            "teamId": "UGA",
            "market": "rush_yds",
            "sportFamily": "gridiron",
            "league": "CFB",
            "eventId": "E1",
            "playerId": "P2",
            "line": 85.5,
            "reliability": 0.6,
            "fragility": 0.3,
            "oodRisk": 0.15,
            "mean": 88.0,
            "variance": 120.0,
        },
        {
            "projectionId": "o3",
            "playerName": "Other",
            "team": "ALA",
            "teamId": "ALA",
            "market": "pass_yds",
            "sportFamily": "gridiron",
            "league": "CFB",
            "eventId": "E2",
            "playerId": "P3",
            "line": 200.0,
        },
    ]


def test_board_store_matches_board_indexes_semantics():
    rows = _rows()
    idx = BoardIndexes(rows)
    store = idx.store
    match = board_store_matches_index_semantics(
        store,
        by_event=idx.by_event,
        by_subject=idx.by_subject,
        by_affiliation=idx.by_affiliation,
        by_market=idx.by_market,
        offer_by_id=idx.offer_by_id,
    )
    assert match == {
        "offers": True,
        "by_event": True,
        "by_subject": True,
        "by_affiliation": True,
        "by_market": True,
        "no_payload_column": True,
    }
    assert store.exact_offer("o1")["projectionId"] == "o1"
    assert store.offer_ids_for_event("E1") == ["o1", "o2"]
    assert store.offer_ids_for_subject("P1") == ["o1"]
    assert store.offer_ids_for_affiliation("ALA") == ["o1", "o3"]
    assert store.offer_ids_for_market("pass_yds") == ["o1", "o3"]
    assert idx.exact_offer("o2") is store.row(store.row_id_by_offer["o2"])
    idx.close()


def test_sqlite_does_not_duplicate_full_payload():
    store = BoardStore(_rows())
    assert not store.sqlite_has_payload_column()
    cur = store.sqlite.execute("PRAGMA table_info(offers)")
    cols = [r[1] for r in cur.fetchall()]
    assert "row_id" in cols
    assert "payload" not in cols
    # Payload recoverable only via row_id → single-copy audit row.
    rid = store.sqlite.execute("SELECT row_id FROM offers WHERE offer_id=?", ("o1",)).fetchone()[0]
    assert store.row(int(rid))["playerName"] == "John Smith"
    store.close()


def test_no_full_board_scan_for_event_lookup():
    store = BoardStore(_rows())
    # Index path returns int32 posting list without scanning all rows.
    ids = store.row_ids_for_event("E1")
    assert ids.dtype == np.int32
    assert list(ids) == [0, 1]
    assert store.offer_ids_for(ids) == ["o1", "o2"]
    # Empty key does not scan.
    assert list(store.row_ids_for_event("MISSING")) == []
    store.close()


def test_id_map_round_trip():
    board = CompactNumericBoard.from_board_rows(_rows())
    rt = round_trip_id_maps(board)
    assert all(rt.values())
    audit = board.to_audit_row(0)
    assert audit["offerId"] == "o1"
    assert audit["subjectId"] == "P1"
    assert audit["eventId"] == "E1"
    assert audit["line"] == 225.5
    assert audit["reliability"] == 0.7


def test_feature_and_parameter_matrices():
    features = [
        {"entity": "P1", "featureName": "L5_pass_yds_mean", "value": 210.0},
        {"entity": "P1", "featureName": "L5_pass_att_mean", "value": 28.0},
        {"entity": "P2", "featureName": "L5_pass_yds_mean", "value": 40.0},
        {"entity": "P2", "featureName": "L5_rush_yds_mean", "value": 90.0},
        {"entity": "P2", "featureName": "skip_non_numeric", "value": "na"},
    ]
    fm = feature_matrix_from_records(features, as_of="2026-09-06T00:00:00Z")
    assert fm.shape[0] == 2
    assert "L5_pass_yds_mean" in fm.feature_names
    assert fm.values.dtype == np.float64
    audit = fm.to_audit_records()
    assert any(r["entity"] == "P1" and r["featureName"] == "L5_pass_yds_mean" and r["value"] == 210.0 for r in audit)

    snaps = [
        {"offerId": "o1", "parameters": {"pass_att_mean": 30.0, "pass_att_sd": 5.0, "minutes_mean": 0.0}},
        {"offerId": "o2", "parameters": {"rush_att_mean": 18.0, "rush_att_sd": 4.0}},
    ]
    pm = parameter_matrix_from_snapshots(snaps)
    assert pm.shape[0] == 2
    assert pm.values.dtype == np.float64
    back = pm.to_audit_snapshots()
    assert back[0]["offerId"] == "o1"
    assert back[0]["parameters"]["pass_att_mean"] == 30.0


def test_soa_microbench_smoke_path_exists():
    """Optional smoke: SoA line sum path exists and is finite (not a certification)."""
    n = 5000
    rows = [
        {
            "projectionId": f"o{i}",
            "playerId": f"P{i % 50}",
            "eventId": f"E{i % 20}",
            "teamId": f"T{i % 10}",
            "market": "pass_yds",
            "league": "CFB",
            "line": float(i % 100) + 0.5,
        }
        for i in range(n)
    ]
    board = CompactNumericBoard.from_board_rows(rows)
    t0 = time.perf_counter()
    soa_sum = board.line_sum()
    soa_ms = (time.perf_counter() - t0) * 1000.0
    # Dict scan reference (audit path) — must agree.
    dict_sum = sum(float(r["line"]) for r in rows)
    assert abs(soa_sum - dict_sum) < 1e-6
    assert soa_ms >= 0.0  # path exercised; not a host-performance claim
    assert board.n == n
