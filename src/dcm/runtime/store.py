"""Portable SQLite index. Append-only records keyed by identity + cutoff."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  player_id TEXT,
  event_id TEXT,
  sport TEXT,
  league TEXT,
  market TEXT,
  cutoff TEXT NOT NULL,
  run_id TEXT NOT NULL,
  lr TEXT NOT NULL,
  source_hash TEXT,
  payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_player_cutoff ON records(player_id, cutoff);
CREATE INDEX IF NOT EXISTS idx_event_cutoff ON records(event_id, cutoff);
CREATE INDEX IF NOT EXISTS idx_market ON records(sport, league, market, cutoff);
CREATE INDEX IF NOT EXISTS idx_run_lr ON records(run_id, lr);
CREATE INDEX IF NOT EXISTS idx_source ON records(source_hash);
"""


class IndexedStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.executescript(SCHEMA)

    def append(self, *, kind: str, cutoff: str, run_id: str, lr: str, payload: dict[str, Any], **keys: Any) -> None:
        self.conn.execute(
            "INSERT INTO records(kind, player_id, event_id, sport, league, market, cutoff, run_id, lr, source_hash, payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                kind,
                keys.get("player_id"),
                keys.get("event_id"),
                keys.get("sport"),
                keys.get("league"),
                keys.get("market"),
                cutoff,
                run_id,
                lr,
                keys.get("source_hash"),
                json.dumps(payload, sort_keys=True),
            ),
        )
        self.conn.commit()

    def query_player(self, player_id: str, cutoff: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT payload FROM records WHERE player_id=? AND cutoff<=? ORDER BY id",
            (player_id, cutoff),
        )
        return [json.loads(r[0]) for r in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()
