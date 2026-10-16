"""Indexed SQLite audit and learning store for captured prop runs."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from dcm.chat.state import write_json
from dcm.contracts.hashes import content_hash


def _time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_captured_prop_database(
    dest: Path,
    claims: Iterable[Mapping[str, Any]],
    directional: Mapping[str, Any],
) -> dict[str, Any]:
    """Write a deterministic, indexed store joining source claims and decisions."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    cutoff = _time(directional.get("forecastCutoff"))
    decision_rows = [row for row in (directional.get("rows") or []) if isinstance(row, Mapping)]
    decisions: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in decision_rows:
        decisions.setdefault((str(row.get("claimId") or ""), str(row.get("sourceHarSha256") or "")), []).append(row)
    claim_rows = [dict(row) for row in claims if isinstance(row, Mapping)]
    claim_rows.sort(key=lambda row: (
        str(row.get("claimId") or row.get("insightId") or ""),
        str(row.get("sourceHarSha256") or ""),
        str(row.get("sourceBodyHash") or ""),
    ))

    target = dest / "captured_prop_ml.sqlite3"
    temp = dest / ".captured_prop_ml.sqlite3.tmp"
    if temp.exists():
        temp.unlink()
    connection = sqlite3.connect(temp)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
        CREATE TABLE source_claims (
            row_id INTEGER PRIMARY KEY,
            claim_id TEXT NOT NULL,
            source_har_sha256 TEXT,
            source_body_hash TEXT,
            claim_hash TEXT,
            league TEXT,
            event_id TEXT,
            event_scheduled_utc TEXT,
            target_local_event_date TEXT,
            player_id TEXT,
            player_name TEXT,
            team_id TEXT,
            market_id TEXT,
            market_outcome_id TEXT,
            market TEXT,
            period_label TEXT,
            line REAL,
            offered_direction TEXT,
            modifier_counts_json TEXT NOT NULL,
            reported_hit_rate REAL,
            reported_last_n_count INTEGER,
            reported_last_n_hit_count INTEGER,
            terminal_status TEXT,
            terminal_reason TEXT,
            lean_direction TEXT,
            p_higher REAL,
            p_lower REAL,
            p_push REAL,
            history_observation_count INTEGER,
            history_lineage_hash TEXT,
            source_snapshot_time TEXT,
            source_claim_json TEXT NOT NULL,
            UNIQUE(claim_id, source_har_sha256, source_body_hash)
        );
        CREATE TABLE history_observations (
            observation_id INTEGER PRIMARY KEY,
            claim_row_id INTEGER NOT NULL REFERENCES source_claims(row_id),
            observed_at_utc TEXT,
            event_id TEXT,
            matchup TEXT,
            value REAL,
            cutoff_safe INTEGER NOT NULL,
            raw_observation_json TEXT NOT NULL
        );
        CREATE TABLE run_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX idx_claim_target_sport_market
            ON source_claims(target_local_event_date, league, market, line);
        CREATE INDEX idx_claim_player_event
            ON source_claims(player_id, event_id, target_local_event_date);
        CREATE INDEX idx_claim_status_direction
            ON source_claims(terminal_status, lean_direction, p_higher, p_lower);
        CREATE INDEX idx_claim_source_hash
            ON source_claims(source_har_sha256, source_body_hash);
        CREATE INDEX idx_history_date_value
            ON history_observations(observed_at_utc, value);
        CREATE INDEX idx_history_event_claim
            ON history_observations(event_id, claim_row_id);
        """)
        connection.execute("BEGIN")
        inserted = 0
        history_count = 0
        for claim in claim_rows:
            claim_id = str(claim.get("claimId") or claim.get("insightId") or "")
            source_har = str(claim.get("sourceHarSha256") or "")
            source_body = str(claim.get("sourceBodyHash") or "")
            variants = decisions.get((claim_id, source_har), [])
            decision = next((row for row in variants if str(row.get("sourceBodyHash") or "") == source_body), variants[0] if variants else {})
            identity = claim.get("harIdentity") if isinstance(claim.get("harIdentity"), Mapping) else {}
            player = identity.get("player") if isinstance(identity.get("player"), Mapping) else {}
            event = claim.get("event") if isinstance(claim.get("event"), Mapping) else {}
            event_identity = identity.get("event") if isinstance(identity.get("event"), Mapping) else {}
            scheduled = event.get("scheduledTime") or event_identity.get("scheduledTime")
            local_date = decision.get("eventLocalDate")
            if local_date is None and decision.get("terminalStatus") == "OUT_OF_RUN_SCOPE":
                local_date = decision.get("eventLocalDate")
            history = claim.get("history") if isinstance(claim.get("history"), Mapping) else {}
            items = history.get("items") if isinstance(history.get("items"), list) else []
            connection.execute("""
                INSERT INTO source_claims (
                    claim_id, source_har_sha256, source_body_hash, claim_hash, league,
                    event_id, event_scheduled_utc, target_local_event_date, player_id,
                    player_name, team_id, market_id, market_outcome_id, market,
                    period_label, line, offered_direction, modifier_counts_json,
                    reported_hit_rate, reported_last_n_count, reported_last_n_hit_count,
                    terminal_status, terminal_reason, lean_direction, p_higher, p_lower,
                    p_push, history_observation_count, history_lineage_hash,
                    source_snapshot_time, source_claim_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(claim_id, source_har_sha256, source_body_hash) DO UPDATE SET
                    terminal_status=excluded.terminal_status,
                    terminal_reason=excluded.terminal_reason,
                    lean_direction=excluded.lean_direction,
                    p_higher=excluded.p_higher, p_lower=excluded.p_lower,
                    p_push=excluded.p_push,
                    history_observation_count=excluded.history_observation_count,
                    history_lineage_hash=excluded.history_lineage_hash,
                    source_claim_json=excluded.source_claim_json
            """, (
                claim_id, source_har or None, source_body or None, claim.get("claimHash"),
                str(claim.get("leagueId") or claim.get("league") or "").upper() or None,
                str(claim.get("eventId") or event.get("eventId") or event_identity.get("id") or "") or None,
                str(scheduled) if scheduled else None, local_date,
                str(claim.get("subjectId") or claim.get("playerId") or player.get("id") or "") or None,
                claim.get("subjectName") or player.get("name"),
                str(claim.get("teamId") or player.get("teamId") or "") or None,
                claim.get("marketId"), claim.get("marketOutcomeId"),
                str(claim.get("proposition") or claim.get("marketLabel") or "").upper() or None,
                claim.get("periodLabel"), _number(claim.get("line")),
                str(claim.get("direction") or "").upper() or None,
                _json(claim.get("modifierCounts") or {}), _number(claim.get("reportedHitRate")),
                int(_number(claim.get("lastNCount")) or 0),
                int(_number(claim.get("lastNHitCount")) or 0),
                decision.get("terminalStatus"), decision.get("reason"), decision.get("leanDirection"),
                _number(decision.get("pHigher")), _number(decision.get("pLower")), _number(decision.get("pPush")),
                int(decision.get("historyObservationCount") or 0), decision.get("historyLineageHash"),
                claim.get("sourceSnapshotTime"), _json(claim),
            ))
            row_id = int(connection.execute(
                "SELECT row_id FROM source_claims WHERE claim_id=? AND source_har_sha256 IS ? AND source_body_hash IS ?",
                (claim_id, source_har or None, source_body or None),
            ).fetchone()[0])
            inserted += 1
            connection.execute("DELETE FROM history_observations WHERE claim_row_id=?", (row_id,))
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                observed = _time(item.get("date"))
                value = _number(item.get("value"))
                if value is None:
                    value = _number(item.get("stat"))
                connection.execute("""
                    INSERT INTO history_observations (
                        claim_row_id, observed_at_utc, event_id, matchup, value,
                        cutoff_safe, raw_observation_json
                    ) VALUES (?,?,?,?,?,?,?)
                """, (
                    row_id,
                    observed.isoformat().replace("+00:00", "Z") if observed else None,
                    str(item.get("eventId") or "") or None,
                    str(item.get("matchup") or "") or None,
                    value,
                    int(observed is not None and cutoff is not None and observed <= cutoff),
                    _json(item),
                ))
                history_count += 1
        metadata = {
            "schema": "pillars_dcm.captured_prop_ml_database.v1",
            "forecastCutoff": directional.get("forecastCutoff"),
            "runEventDate": directional.get("runEventDate"),
            "eventTimezone": directional.get("eventTimezone"),
            "sourceClaimCount": len(claim_rows),
            "historyObservationLinkCount": history_count,
            "directionalArtifactHash": directional.get("contentHash"),
        }
        connection.executemany(
            "INSERT INTO run_metadata(key,value) VALUES (?,?)",
            [(key, _json(value)) for key, value in metadata.items()],
        )
        connection.commit()
        connection.execute("PRAGMA optimize")
    finally:
        connection.close()
    os.replace(temp, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {
        "schema": "pillars_dcm.captured_prop_ml_database_manifest.v1",
        "path": target.name,
        "sha256": digest,
        "sourceClaimCount": len(claim_rows),
        "historyObservationLinkCount": history_count,
        "uniqueSourceRowsInserted": inserted,
        "forecastCutoff": directional.get("forecastCutoff"),
        "runEventDate": directional.get("runEventDate"),
        "eventTimezone": directional.get("eventTimezone"),
        "directionalArtifactHash": directional.get("contentHash"),
        "indexes": [
            "idx_claim_target_sport_market", "idx_claim_player_event",
            "idx_claim_status_direction", "idx_claim_source_hash",
            "idx_history_date_value", "idx_history_event_claim",
        ],
    }
    manifest["contentHash"] = content_hash(manifest)
    write_json(dest / "captured_prop_ml_database_manifest.json", manifest)
    return manifest


__all__ = ["build_captured_prop_database"]
