PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS line_snapshots (
    line_snapshot_id TEXT PRIMARY KEY,
    prop_id TEXT NOT NULL,
    market_definition_id TEXT NOT NULL,
    captured_at_utc TEXT NOT NULL,
    valid_until_utc TEXT NOT NULL,
    line REAL NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('HIGHER','LOWER')),
    modifier TEXT NOT NULL,
    period TEXT NOT NULL,
    status TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_line_snapshots_prop_time
    ON line_snapshots(prop_id, captured_at_utc DESC);

CREATE TABLE IF NOT EXISTS freezes (
    freeze_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    frozen_at_utc TEXT NOT NULL,
    model_snapshot_id TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    board_hash TEXT NOT NULL,
    manifest_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS freeze_members (
    freeze_id TEXT NOT NULL,
    recommendation_id TEXT NOT NULL,
    prop_id TEXT NOT NULL,
    line_snapshot_id TEXT NOT NULL,
    market_definition_id TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    parameter_snapshot_hash TEXT NOT NULL,
    PRIMARY KEY(freeze_id, recommendation_id),
    FOREIGN KEY(freeze_id) REFERENCES freezes(freeze_id),
    FOREIGN KEY(line_snapshot_id) REFERENCES line_snapshots(line_snapshot_id)
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id TEXT PRIMARY KEY,
    freeze_id TEXT NOT NULL,
    recommendation_id TEXT NOT NULL,
    prop_id TEXT NOT NULL,
    line_snapshot_id TEXT NOT NULL,
    market_definition_id TEXT NOT NULL,
    result TEXT NOT NULL CHECK(result IN ('WIN','LOSS','PUSH','VOID','UNSETTLED')),
    settled_at_utc TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    FOREIGN KEY(freeze_id, recommendation_id)
        REFERENCES freeze_members(freeze_id, recommendation_id),
    FOREIGN KEY(line_snapshot_id) REFERENCES line_snapshots(line_snapshot_id)
);

CREATE TRIGGER IF NOT EXISTS line_snapshots_no_update
BEFORE UPDATE ON line_snapshots BEGIN
    SELECT RAISE(ABORT, 'PILLARS_P0_IMMUTABLE_LINE_SNAPSHOT');
END;
CREATE TRIGGER IF NOT EXISTS line_snapshots_no_delete
BEFORE DELETE ON line_snapshots BEGIN
    SELECT RAISE(ABORT, 'PILLARS_P0_IMMUTABLE_LINE_SNAPSHOT');
END;
CREATE TRIGGER IF NOT EXISTS freezes_no_update
BEFORE UPDATE ON freezes BEGIN
    SELECT RAISE(ABORT, 'PILLARS_P0_IMMUTABLE_FREEZE');
END;
CREATE TRIGGER IF NOT EXISTS freezes_no_delete
BEFORE DELETE ON freezes BEGIN
    SELECT RAISE(ABORT, 'PILLARS_P0_IMMUTABLE_FREEZE');
END;
CREATE TRIGGER IF NOT EXISTS freeze_members_no_update
BEFORE UPDATE ON freeze_members BEGIN
    SELECT RAISE(ABORT, 'PILLARS_P0_IMMUTABLE_FREEZE_MEMBER');
END;
CREATE TRIGGER IF NOT EXISTS freeze_members_no_delete
BEFORE DELETE ON freeze_members BEGIN
    SELECT RAISE(ABORT, 'PILLARS_P0_IMMUTABLE_FREEZE_MEMBER');
END;
CREATE TRIGGER IF NOT EXISTS settlements_no_update
BEFORE UPDATE ON settlements BEGIN
    SELECT RAISE(ABORT, 'PILLARS_P0_IMMUTABLE_SETTLEMENT');
END;
CREATE TRIGGER IF NOT EXISTS settlements_no_delete
BEFORE DELETE ON settlements BEGIN
    SELECT RAISE(ABORT, 'PILLARS_P0_IMMUTABLE_SETTLEMENT');
END;
