"""P0 lineage/freeze integrity primitives.

This module is deliberately small and dependency-free. It provides the typed
append-only SQLite contract used to prove that current-offer snapshots, freeze
members, and settlements cannot silently drift after the pre-lock decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash

LINEAGE_SCHEMA_VERSION = "PILLARS_P0_LINEAGE_V1_2026-10-08"
FRESHNESS_POLICY_VERSION = "PILLARS_OFFER_FRESHNESS_V1_2026-10-08"


class LineageHalt(RuntimeError):
    """Raised when a P0 integrity invariant fails closed."""

    def __init__(self, code: str, message: str = "") -> None:
        detail = f": {message}" if message else ""
        super().__init__(f"{code}{detail}")
        self.code = code


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise LineageHalt("TIMESTAMP_REQUIRED")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise LineageHalt("TIMESTAMP_INVALID", text) from exc
    if parsed.tzinfo is None:
        raise LineageHalt("TIMESTAMP_TZ_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _iso(value: str | datetime) -> str:
    return _utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def freshness_ttl_seconds(*, retrieved_at: str | datetime, scheduled_time: str | datetime | None) -> int:
    """Return a conservative, versioned TTL based on time-to-event.

    This is an engineering safety policy, not a predictive claim. It is
    intentionally tighter near event start and can later be replaced by a
    measured market-specific policy without changing the lineage contract.
    """
    retrieved = _utc(retrieved_at)
    if scheduled_time is None or not str(scheduled_time).strip():
        return 120
    start = _utc(scheduled_time)
    seconds_to_start = max(0.0, (start - retrieved).total_seconds())
    if seconds_to_start <= 15 * 60:
        return 60
    if seconds_to_start <= 60 * 60:
        return 180
    if seconds_to_start <= 6 * 60 * 60:
        return 300
    return 900


def derive_valid_until(*, retrieved_at: str | datetime, scheduled_time: str | datetime | None) -> str:
    retrieved = _utc(retrieved_at)
    ttl = freshness_ttl_seconds(retrieved_at=retrieved, scheduled_time=scheduled_time)
    valid_until = retrieved + timedelta(seconds=ttl)
    if scheduled_time is not None and str(scheduled_time).strip():
        valid_until = min(valid_until, _utc(scheduled_time))
    return _iso(valid_until)


def offer_is_fresh(snapshot: Mapping[str, Any], *, decision_time: str | datetime) -> bool:
    valid_until = snapshot.get("validUntilUtc") or snapshot.get("valid_until_utc")
    if not valid_until:
        return False
    return _utc(decision_time) <= _utc(str(valid_until))


def line_snapshot_id(snapshot: Mapping[str, Any]) -> str:
    payload = {
        "propId": str(snapshot.get("propId") or snapshot.get("claimId") or snapshot.get("projectionId") or ""),
        "marketDefinitionId": str(snapshot.get("marketDefinitionId") or ""),
        "line": snapshot.get("line"),
        "side": str(snapshot.get("direction") or snapshot.get("side") or "").upper(),
        "modifier": str(snapshot.get("modifier") or "STANDARD").upper(),
        "period": str(snapshot.get("periodLabel") or snapshot.get("period") or "").upper(),
        "status": str(snapshot.get("eventStatus") or snapshot.get("status") or "").upper(),
        "retrievedAt": str(snapshot.get("retrievedAt") or snapshot.get("offerTimestamp") or ""),
        "sourceHash": str(snapshot.get("sourceHash") or ""),
    }
    if not payload["propId"] or payload["line"] is None or not payload["side"]:
        raise LineageHalt("LINE_SNAPSHOT_IDENTITY_INCOMPLETE")
    return "LINE:" + content_hash(payload)


def validate_line_transition(previous: Mapping[str, Any], current: Mapping[str, Any]) -> None:
    """Fail when a freeze-critical offer field changed without recomputation."""
    fields = (
        ("marketDefinitionId", "MARKET_DEFINITION_CHANGED"),
        ("line", "LINE_CHANGED"),
        ("direction", "SIDE_CHANGED"),
        ("modifier", "MODIFIER_CHANGED"),
        ("periodLabel", "PERIOD_CHANGED"),
    )
    for field, code in fields:
        left = previous.get(field)
        right = current.get(field)
        if field in {"direction", "modifier", "periodLabel"}:
            left = str(left or "").upper()
            right = str(right or "").upper()
        if left != right:
            raise LineageHalt(code, f"{left!r}->{right!r}")


def freeze_manifest_hash(
    *,
    run_id: str,
    frozen_at_utc: str,
    model_snapshot_id: str,
    prompt_hash: str,
    board_hash: str,
    members: Iterable[Mapping[str, Any]],
) -> str:
    rows = [dict(row) for row in members]
    rows.sort(
        key=lambda row: (
            str(row.get("propId") or row.get("claimId") or ""),
            str(row.get("lineSnapshotId") or ""),
        )
    )
    payload = {
        "schema": LINEAGE_SCHEMA_VERSION,
        "runId": run_id,
        "frozenAtUtc": _iso(frozen_at_utc),
        "modelSnapshotId": model_snapshot_id,
        "promptHash": prompt_hash,
        "boardHash": board_hash,
        "members": rows,
    }
    if not run_id or not model_snapshot_id or not prompt_hash or not board_hash or not rows:
        raise LineageHalt("FREEZE_MANIFEST_INCOMPLETE")
    return content_hash(payload)


LINEAGE_SQL_PATH = Path(__file__).with_name("migrations") / "p0_lineage_v1.sql"
LINEAGE_SQL = LINEAGE_SQL_PATH.read_text(encoding="utf-8")


@dataclass(frozen=True)
class FreezeMember:
    recommendation_id: str
    prop_id: str
    line_snapshot_id: str
    market_definition_id: str
    evidence_hash: str
    parameter_snapshot_hash: str

    def as_dict(self) -> dict[str, str]:
        return {
            "recommendationId": self.recommendation_id,
            "propId": self.prop_id,
            "lineSnapshotId": self.line_snapshot_id,
            "marketDefinitionId": self.market_definition_id,
            "evidenceHash": self.evidence_hash,
            "parameterSnapshotHash": self.parameter_snapshot_hash,
        }


class LineageStore:
    """Append-only P0 relational ledger used by freeze/settlement boundaries."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path) if not isinstance(path, Path) else path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(LINEAGE_SQL)

    def append_line_snapshot(self, snapshot: Mapping[str, Any]) -> str:
        sid = str(snapshot.get("lineSnapshotId") or line_snapshot_id(snapshot))
        prop_id = str(snapshot.get("propId") or snapshot.get("claimId") or snapshot.get("projectionId") or "")
        market_definition_id = str(snapshot.get("marketDefinitionId") or "")
        captured_at = _iso(str(snapshot.get("retrievedAt") or snapshot.get("offerTimestamp") or ""))
        valid_until = _iso(str(snapshot.get("validUntilUtc") or ""))
        if not prop_id or not market_definition_id:
            raise LineageHalt("LINE_SNAPSHOT_IDENTITY_INCOMPLETE")
        payload = {
            "lineSnapshotId": sid,
            "propId": prop_id,
            "marketDefinitionId": market_definition_id,
            "capturedAtUtc": captured_at,
            "validUntilUtc": valid_until,
            "line": float(snapshot["line"]),
            "side": str(snapshot.get("direction") or snapshot.get("side") or "").upper(),
            "modifier": str(snapshot.get("modifier") or "STANDARD").upper(),
            "period": str(snapshot.get("periodLabel") or snapshot.get("period") or "").upper(),
            "status": str(snapshot.get("eventStatus") or snapshot.get("status") or "PRE_GAME").upper(),
            "sourceHash": str(snapshot.get("sourceHash") or ""),
        }
        digest = content_hash(payload)
        try:
            self.conn.execute(
                "INSERT INTO line_snapshots(line_snapshot_id,prop_id,market_definition_id,captured_at_utc,valid_until_utc,line,side,modifier,period,status,source_hash,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sid,
                    prop_id,
                    market_definition_id,
                    captured_at,
                    valid_until,
                    float(snapshot["line"]),
                    payload["side"],
                    payload["modifier"],
                    payload["period"],
                    payload["status"],
                    payload["sourceHash"],
                    digest,
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            row = self.conn.execute(
                "SELECT content_hash FROM line_snapshots WHERE line_snapshot_id=?",
                (sid,),
            ).fetchone()
            if row and str(row[0]) == digest:
                return sid
            raise LineageHalt("LINE_SNAPSHOT_CONFLICT", sid) from exc
        return sid

    def freeze(
        self,
        *,
        run_id: str,
        frozen_at_utc: str,
        model_snapshot_id: str,
        prompt_hash: str,
        board_hash: str,
        members: Iterable[FreezeMember],
    ) -> str:
        frozen_at = _iso(frozen_at_utc)
        member_rows = list(members)
        if not member_rows:
            raise LineageHalt("FREEZE_MEMBERS_REQUIRED")
        for member in member_rows:
            row = self.conn.execute(
                "SELECT prop_id,market_definition_id,valid_until_utc FROM line_snapshots WHERE line_snapshot_id=?",
                (member.line_snapshot_id,),
            ).fetchone()
            if row is None:
                raise LineageHalt("FREEZE_LINE_SNAPSHOT_MISSING", member.line_snapshot_id)
            if str(row[0]) != member.prop_id or str(row[1]) != member.market_definition_id:
                raise LineageHalt("FREEZE_MEMBER_IDENTITY_MISMATCH", member.recommendation_id)
            if _utc(frozen_at) > _utc(str(row[2])):
                raise LineageHalt("OFFER_REVALIDATION_STALE", member.line_snapshot_id)
        manifest_hash = freeze_manifest_hash(
            run_id=run_id,
            frozen_at_utc=frozen_at,
            model_snapshot_id=model_snapshot_id,
            prompt_hash=prompt_hash,
            board_hash=board_hash,
            members=[member.as_dict() for member in member_rows],
        )
        freeze_id = "FREEZE:" + manifest_hash
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                "INSERT INTO freezes(freeze_id,run_id,frozen_at_utc,model_snapshot_id,prompt_hash,board_hash,manifest_hash) VALUES(?,?,?,?,?,?,?)",
                (
                    freeze_id,
                    run_id,
                    frozen_at,
                    model_snapshot_id,
                    prompt_hash,
                    board_hash,
                    manifest_hash,
                ),
            )
            self.conn.executemany(
                "INSERT INTO freeze_members(freeze_id,recommendation_id,prop_id,line_snapshot_id,market_definition_id,evidence_hash,parameter_snapshot_hash) VALUES(?,?,?,?,?,?,?)",
                [
                    (
                        freeze_id,
                        member.recommendation_id,
                        member.prop_id,
                        member.line_snapshot_id,
                        member.market_definition_id,
                        member.evidence_hash,
                        member.parameter_snapshot_hash,
                    )
                    for member in member_rows
                ],
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            row = self.conn.execute(
                "SELECT manifest_hash FROM freezes WHERE freeze_id=?",
                (freeze_id,),
            ).fetchone()
            if row and str(row[0]) == manifest_hash:
                return freeze_id
            raise LineageHalt("FREEZE_CONFLICT", freeze_id) from exc
        return freeze_id

    def settle(
        self,
        *,
        settlement_id: str,
        freeze_id: str,
        recommendation_id: str,
        prop_id: str,
        line_snapshot_id: str,
        market_definition_id: str,
        result: str,
        settled_at_utc: str,
        source_hash: str,
    ) -> None:
        result = str(result).upper()
        if result not in {"WIN", "LOSS", "PUSH", "VOID", "UNSETTLED"}:
            raise LineageHalt("SETTLEMENT_RESULT_INVALID", result)
        member = self.conn.execute(
            "SELECT prop_id,line_snapshot_id,market_definition_id FROM freeze_members WHERE freeze_id=? AND recommendation_id=?",
            (freeze_id, recommendation_id),
        ).fetchone()
        if member is None:
            raise LineageHalt("SETTLEMENT_FREEZE_MEMBER_MISSING", recommendation_id)
        if (str(member[0]), str(member[1]), str(member[2])) != (
            prop_id,
            line_snapshot_id,
            market_definition_id,
        ):
            raise LineageHalt("SETTLEMENT_LINEAGE_MISMATCH", recommendation_id)
        payload = {
            "settlementId": settlement_id,
            "freezeId": freeze_id,
            "recommendationId": recommendation_id,
            "propId": prop_id,
            "lineSnapshotId": line_snapshot_id,
            "marketDefinitionId": market_definition_id,
            "result": result,
            "settledAtUtc": _iso(settled_at_utc),
            "sourceHash": source_hash,
        }
        digest = content_hash(payload)
        self.conn.execute(
            "INSERT INTO settlements(settlement_id,freeze_id,recommendation_id,prop_id,line_snapshot_id,market_definition_id,result,settled_at_utc,source_hash,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                settlement_id,
                freeze_id,
                recommendation_id,
                prop_id,
                line_snapshot_id,
                market_definition_id,
                result,
                payload["settledAtUtc"],
                source_hash,
                digest,
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


__all__ = [
    "FRESHNESS_POLICY_VERSION",
    "FreezeMember",
    "LINEAGE_SCHEMA_VERSION",
    "LINEAGE_SQL",
    "LineageHalt",
    "LineageStore",
    "derive_valid_until",
    "freeze_manifest_hash",
    "freshness_ttl_seconds",
    "line_snapshot_id",
    "offer_is_fresh",
    "validate_line_transition",
]
