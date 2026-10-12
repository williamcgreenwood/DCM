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

-- Forensic retrospective row anchors and append-only source corrections.
-- These records never manufacture a historical model, recommendation, or freeze.
CREATE TABLE IF NOT EXISTS retrospective_rows (
    run_id TEXT NOT NULL,
    row_id TEXT NOT NULL,
    row_sha256 TEXT NOT NULL,
    workbook_sha256 TEXT NOT NULL,
    original_source_reference TEXT NOT NULL,
    PRIMARY KEY (run_id, row_id)
);
CREATE TABLE IF NOT EXISTS source_corrections (
    correction_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    row_id TEXT NOT NULL,
    original_row_sha256 TEXT NOT NULL,
    original_source_reference TEXT NOT NULL,
    corrected_source_reference TEXT NOT NULL,
    evidence_sha256 TEXT NOT NULL,
    reason_code TEXT NOT NULL CHECK (reason_code='SOURCE_LINEAGE_ERROR'),
    recorded_at_utc TEXT NOT NULL,
    changes_outcome INTEGER NOT NULL CHECK (changes_outcome IN (0,1)),
    changes_eligibility INTEGER NOT NULL CHECK (changes_eligibility IN (0,1)),
    changes_model_input INTEGER NOT NULL CHECK (changes_model_input IN (0,1)),
    content_hash TEXT NOT NULL UNIQUE,
    FOREIGN KEY (run_id,row_id) REFERENCES retrospective_rows(run_id,row_id)
);
CREATE TRIGGER IF NOT EXISTS retrospective_rows_no_update
BEFORE UPDATE ON retrospective_rows BEGIN SELECT RAISE(ABORT,'PILLARS_P0_IMMUTABLE_RETROSPECTIVE_ROW'); END;
CREATE TRIGGER IF NOT EXISTS retrospective_rows_no_delete
BEFORE DELETE ON retrospective_rows BEGIN SELECT RAISE(ABORT,'PILLARS_P0_IMMUTABLE_RETROSPECTIVE_ROW'); END;
CREATE TRIGGER IF NOT EXISTS source_corrections_no_update
BEFORE UPDATE ON source_corrections BEGIN SELECT RAISE(ABORT,'PILLARS_P0_IMMUTABLE_SOURCE_CORRECTION'); END;
CREATE TRIGGER IF NOT EXISTS source_corrections_no_delete
BEFORE DELETE ON source_corrections BEGIN SELECT RAISE(ABORT,'PILLARS_P0_IMMUTABLE_SOURCE_CORRECTION'); END;
CREATE TRIGGER IF NOT EXISTS source_corrections_match_original
BEFORE INSERT ON source_corrections BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM retrospective_rows r WHERE r.run_id=NEW.run_id AND r.row_id=NEW.row_id
        AND r.row_sha256=NEW.original_row_sha256
        AND r.original_source_reference=NEW.original_source_reference
    ) THEN RAISE(ABORT,'PILLARS_P0_CORRECTION_ORIGINAL_MISMATCH') END;
END;

-- Protect the observed-time and eligibility boundary even from direct SQL writers.
CREATE TRIGGER IF NOT EXISTS freeze_members_point_in_time_gate
BEFORE INSERT ON freeze_members BEGIN
    SELECT CASE WHEN length(trim(NEW.evidence_hash))=0 OR length(trim(NEW.parameter_snapshot_hash))=0
        THEN RAISE(ABORT,'PILLARS_P0_FREEZE_MISSING_EVIDENCE_OR_MODEL') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM line_snapshots l JOIN freezes f ON f.freeze_id=NEW.freeze_id
        WHERE l.line_snapshot_id=NEW.line_snapshot_id AND l.captured_at_utc>f.frozen_at_utc
    ) THEN RAISE(ABORT,'PILLARS_P0_FUTURE_OFFER_LEAKAGE') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM line_snapshots l JOIN freezes f ON f.freeze_id=NEW.freeze_id
        WHERE l.line_snapshot_id=NEW.line_snapshot_id
        AND (l.valid_until_utc<f.frozen_at_utc OR l.prop_id!=NEW.prop_id
             OR l.market_definition_id!=NEW.market_definition_id)
    ) THEN RAISE(ABORT,'PILLARS_P0_FREEZE_LINEAGE_OR_FRESHNESS_MISMATCH') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM line_snapshots l WHERE l.line_snapshot_id=NEW.line_snapshot_id
        AND (l.status NOT IN ('PRE_GAME','PREGAME') OR length(trim(l.source_hash))=0)
    ) THEN RAISE(ABORT,'PILLARS_P0_FREEZE_OFFER_UNSUPPORTED') END;
END;
