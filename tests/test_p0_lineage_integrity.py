from __future__ import annotations

import sqlite3

import pytest

from dcm.runtime.lineage_integrity import (
    FreezeMember,
    LineageHalt,
    LineageStore,
    derive_valid_until,
    freshness_ttl_seconds,
    validate_line_transition,
)


def _snapshot(*, line: float = 24.5, retrieved: str = "2026-10-08T20:00:00Z") -> dict:
    scheduled = "2026-10-08T20:30:00Z"
    return {
        "claimId": "PROP-WNBA-NYL-ATL-CANADA-PRA",
        "projectionId": "projection-1",
        "marketDefinitionId": "WNBA_PRA_FULL_GAME_V1",
        "line": line,
        "direction": "HIGHER",
        "modifier": "STANDARD",
        "periodLabel": "FULL_GAME",
        "eventStatus": "PRE_GAME",
        "retrievedAt": retrieved,
        "scheduledTime": scheduled,
        "validUntilUtc": derive_valid_until(
            retrieved_at=retrieved,
            scheduled_time=scheduled,
        ),
        "sourceHash": "source-hash-1",
    }


def test_adaptive_freshness_policy_tightens_near_start() -> None:
    assert freshness_ttl_seconds(
        retrieved_at="2026-10-08T20:00:00Z",
        scheduled_time="2026-10-08T20:10:00Z",
    ) == 60
    assert freshness_ttl_seconds(
        retrieved_at="2026-10-08T20:00:00Z",
        scheduled_time="2026-10-08T20:30:00Z",
    ) == 180
    assert freshness_ttl_seconds(
        retrieved_at="2026-10-08T20:00:00Z",
        scheduled_time="2026-10-08T23:00:00Z",
    ) == 300
    assert freshness_ttl_seconds(
        retrieved_at="2026-10-08T20:00:00Z",
        scheduled_time="2026-10-09T12:00:00Z",
    ) == 900


def test_line_snapshots_are_append_only_and_line_drift_fails_closed(tmp_path) -> None:
    store = LineageStore(tmp_path / "lineage.sqlite3")
    snapshot = _snapshot()
    line_snapshot_id = store.append_line_snapshot(snapshot)

    with pytest.raises(
        sqlite3.IntegrityError,
        match="PILLARS_P0_IMMUTABLE_LINE_SNAPSHOT",
    ):
        store.conn.execute(
            "UPDATE line_snapshots SET line=25.5 WHERE line_snapshot_id=?",
            (line_snapshot_id,),
        )

    changed = {**snapshot, "line": 25.5}
    with pytest.raises(LineageHalt, match="LINE_CHANGED"):
        validate_line_transition(snapshot, changed)
    store.close()


def test_freeze_requires_exact_fresh_member_and_settlement_rejoins_it(tmp_path) -> None:
    store = LineageStore(tmp_path / "lineage.sqlite3")
    snapshot = _snapshot()
    line_snapshot_id = store.append_line_snapshot(snapshot)
    member = FreezeMember(
        recommendation_id="REC-001",
        prop_id=snapshot["claimId"],
        line_snapshot_id=line_snapshot_id,
        market_definition_id=snapshot["marketDefinitionId"],
        evidence_hash="evidence-hash",
        parameter_snapshot_hash="parameter-hash",
    )
    freeze_id = store.freeze(
        run_id="RUN-001",
        frozen_at_utc="2026-10-08T20:02:00Z",
        model_snapshot_id="MODEL-SNAPSHOT-001",
        prompt_hash="prompt-hash",
        board_hash="board-hash",
        members=[member],
    )
    assert freeze_id.startswith("FREEZE:")

    store.settle(
        settlement_id="SET-001",
        freeze_id=freeze_id,
        recommendation_id="REC-001",
        prop_id=snapshot["claimId"],
        line_snapshot_id=line_snapshot_id,
        market_definition_id=snapshot["marketDefinitionId"],
        result="WIN",
        settled_at_utc="2026-10-09T03:00:00Z",
        source_hash="official-result-hash",
    )

    with pytest.raises(LineageHalt, match="SETTLEMENT_LINEAGE_MISMATCH"):
        store.settle(
            settlement_id="SET-002",
            freeze_id=freeze_id,
            recommendation_id="REC-001",
            prop_id=snapshot["claimId"],
            line_snapshot_id="LINE:wrong",
            market_definition_id=snapshot["marketDefinitionId"],
            result="WIN",
            settled_at_utc="2026-10-09T03:00:00Z",
            source_hash="official-result-hash",
        )
    store.close()


def test_stale_offer_cannot_freeze(tmp_path) -> None:
    store = LineageStore(tmp_path / "lineage.sqlite3")
    snapshot = _snapshot(retrieved="2026-10-08T20:00:00Z")
    line_snapshot_id = store.append_line_snapshot(snapshot)
    member = FreezeMember(
        recommendation_id="REC-STALE",
        prop_id=snapshot["claimId"],
        line_snapshot_id=line_snapshot_id,
        market_definition_id=snapshot["marketDefinitionId"],
        evidence_hash="evidence-hash",
        parameter_snapshot_hash="parameter-hash",
    )
    with pytest.raises(LineageHalt, match="OFFER_REVALIDATION_STALE"):
        store.freeze(
            run_id="RUN-STALE",
            frozen_at_utc="2026-10-08T20:10:00Z",
            model_snapshot_id="MODEL-SNAPSHOT-001",
            prompt_hash="prompt-hash",
            board_hash="board-hash",
            members=[member],
        )
    store.close()
