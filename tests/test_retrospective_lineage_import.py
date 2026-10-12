"""Synthetic forensic fixture only; no private October 9 workbook or result labels."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile

import pytest

from scripts.audit_retrospective_lineage import RetrospectiveHalt, digest_json, ingest, read_first_sheet


def _xlsx(path: Path, n: int = 74) -> bytes:
    rows = ['<row r="1"><c r="A1" t="inlineStr"><is><t>ROW_ID</t></is></c><c r="B1" t="inlineStr"><is><t>SOURCE_URL</t></is></c></row>']
    for i in range(1, n + 1):
        rows.append(f'<row r="{i+1}"><c r="A{i+1}" t="inlineStr"><is><t>R{i:03d}</t></is></c><c r="B{i+1}" t="inlineStr"><is><t>https://example.org/old/{i}</t></is></c></row>')
    with ZipFile(path, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Rows" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + ''.join(rows) + '</sheetData></worksheet>')
    return path.read_bytes()


def _inputs(tmp_path: Path, n: int = 74):
    workbook = tmp_path / 'original.xlsx'
    raw = _xlsx(workbook, n)
    wh = hashlib.sha256(raw).hexdigest()
    row = read_first_sheet(raw)[0]
    evidence = tmp_path / 'boxscore.txt'
    evidence.write_text('Synthetic reference correction evidence only', encoding='utf-8')
    correction = {
        'correction_id': 'CORR-001', 'target_record_id': 'R001',
        'original_row_sha256': digest_json(row),
        'original_source_reference': row['SOURCE_URL'],
        'corrected_source_reference': 'https://example.org/correct/1',
        'evidence_file': evidence.name,
        'evidence_sha256': hashlib.sha256(evidence.read_bytes()).hexdigest(),
        'reason_code': 'SOURCE_LINEAGE_ERROR', 'recorded_at_utc': '2026-10-12T18:00:00Z',
        'changes_outcome': False, 'changes_eligibility': False,
        'changes_model_input': False,
    }
    addendum = tmp_path / 'correction.json'
    addendum.write_text(json.dumps({'workbook_sha256': wh, 'corrections': [correction]}))
    return workbook, addendum, wh


def test_74_row_import_and_append_only_correction(tmp_path: Path) -> None:
    workbook, addendum, wh = _inputs(tmp_path)
    db = tmp_path / 'lineage.sqlite3'
    kw = dict(workbook=workbook, addendum=addendum, db=db, run_id='RUN-SYNTHETIC', expected_sha256=wh)
    receipt = ingest(**kw)
    assert receipt['rowsVerified'] == 74
    assert receipt['correctionsVerified'] == 1
    assert receipt['historicalFreezeCreated'] is False
    assert ingest(**kw) == receipt
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM retrospective_rows').fetchone()[0] == 74
        assert conn.execute('SELECT COUNT(*) FROM source_corrections').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM freezes').fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError, match='IMMUTABLE_SOURCE_CORRECTION'):
            conn.execute("UPDATE source_corrections SET corrected_source_reference='x'")
        with pytest.raises(sqlite3.IntegrityError, match='IMMUTABLE_RETROSPECTIVE_ROW'):
            conn.execute('DELETE FROM retrospective_rows')


def test_hash_mismatch_and_wrong_population_leave_no_db(tmp_path: Path) -> None:
    workbook, addendum, wh = _inputs(tmp_path)
    db = tmp_path / 'lineage.sqlite3'
    with pytest.raises(RetrospectiveHalt, match='WORKBOOK_SHA256_MISMATCH'):
        ingest(workbook=workbook, addendum=addendum, db=db, run_id='RUN', expected_sha256='0' * 64)
    assert not db.exists()
    workbook, addendum, wh = _inputs(tmp_path, n=73)
    with pytest.raises(RetrospectiveHalt, match='WORKBOOK_ROW_COUNT_MISMATCH'):
        ingest(workbook=workbook, addendum=addendum, db=db, run_id='RUN', expected_sha256=wh)
    assert not db.exists()


def test_false_correction_evidence_rejected_before_write(tmp_path: Path) -> None:
    workbook, addendum, wh = _inputs(tmp_path)
    obj = json.loads(addendum.read_text())
    obj['corrections'][0]['evidence_sha256'] = '0' * 64
    addendum.write_text(json.dumps(obj))
    db = tmp_path / 'lineage.sqlite3'
    with pytest.raises(RetrospectiveHalt, match='CORRECTION_EVIDENCE_HASH_MISMATCH'):
        ingest(workbook=workbook, addendum=addendum, db=db, run_id='RUN', expected_sha256=wh)
    assert not db.exists()


def test_replacement_cannot_rewrite_prior_correction(tmp_path: Path) -> None:
    workbook, addendum, wh = _inputs(tmp_path)
    db = tmp_path / 'lineage.sqlite3'
    kw = dict(workbook=workbook, addendum=addendum, db=db, run_id='RUN', expected_sha256=wh)
    ingest(**kw)
    obj = json.loads(addendum.read_text())
    obj['corrections'][0]['corrected_source_reference'] = 'https://example.org/different'
    addendum.write_text(json.dumps(obj))
    with pytest.raises(RetrospectiveHalt, match='CORRECTION_IMMUTABILITY_CONFLICT'):
        ingest(**kw)
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM source_corrections').fetchone()[0] == 1


def test_freeze_member_rejects_future_offer_and_empty_evidence(tmp_path: Path) -> None:
    # Schema-level protection cannot be bypassed by a direct DB writer.
    from dcm.runtime.lineage_integrity import LineageStore
    store = LineageStore(tmp_path / 'lineage.sqlite3')
    try:
        c = store.conn
        c.execute("INSERT INTO line_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", ('L1','P1','M1','2026-10-12T20:05:00Z','2026-10-12T20:09:00Z',10.5,'HIGHER','STANDARD','FULL_GAME','PRE_GAME','src','hash1'))
        c.execute("INSERT INTO freezes VALUES(?,?,?,?,?,?,?)", ('F1','RUN','2026-10-12T20:00:00Z','MODEL','PROMPT','BOARD','hash2'))
        with pytest.raises(sqlite3.IntegrityError, match='FUTURE_OFFER_LEAKAGE'):
            c.execute("INSERT INTO freeze_members VALUES(?,?,?,?,?,?,?)", ('F1','R1','P1','L1','M1','evidence','parameters'))
        with pytest.raises(sqlite3.IntegrityError, match='MISSING_EVIDENCE_OR_MODEL'):
            c.execute("INSERT INTO freeze_members VALUES(?,?,?,?,?,?,?)", ('F1','R1','P1','L1','M1','','parameters'))
    finally:
        store.close()


def test_direct_freeze_member_rejects_stale_identity_and_unsupported_status(tmp_path: Path) -> None:
    from dcm.runtime.lineage_integrity import LineageStore
    store = LineageStore(tmp_path / 'lineage.sqlite3')
    try:
        c = store.conn
        c.execute("INSERT INTO line_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  ('L2','P2','M2','2026-10-12T19:00:00Z','2026-10-12T19:01:00Z',10.5,
                   'LOWER','STANDARD','FULL_GAME','PRE_GAME','src','hash-l2'))
        c.execute("INSERT INTO freezes VALUES(?,?,?,?,?,?,?)",
                  ('F2','RUN','2026-10-12T19:02:00Z','MODEL','PROMPT','BOARD','hash-f2'))
        with pytest.raises(sqlite3.IntegrityError, match='FREEZE_LINEAGE_OR_FRESHNESS_MISMATCH'):
            c.execute("INSERT INTO freeze_members VALUES(?,?,?,?,?,?,?)",
                      ('F2','R2','P2','L2','M2','evidence','parameters'))
        c.execute("INSERT INTO line_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  ('L3','P3','M3','2026-10-12T19:00:00Z','2026-10-12T19:04:00Z',10.5,
                   'HIGHER','STANDARD','FULL_GAME','PRE_GAME','src','hash-l3'))
        with pytest.raises(sqlite3.IntegrityError, match='FREEZE_LINEAGE_OR_FRESHNESS_MISMATCH'):
            c.execute("INSERT INTO freeze_members VALUES(?,?,?,?,?,?,?)",
                      ('F2','R3','WRONG_PROP','L3','M3','evidence','parameters'))
        c.execute("INSERT INTO line_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  ('L4','P4','M4','2026-10-12T19:00:00Z','2026-10-12T19:04:00Z',10.5,
                   'HIGHER','STANDARD','FULL_GAME','LIVE','src','hash-l4'))
        with pytest.raises(sqlite3.IntegrityError, match='FREEZE_OFFER_UNSUPPORTED'):
            c.execute("INSERT INTO freeze_members VALUES(?,?,?,?,?,?,?)",
                      ('F2','R4','P4','L4','M4','evidence','parameters'))
    finally:
        store.close()
