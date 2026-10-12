"""Synthetic named-sheet/composite retrospective tests; no private historical workbook."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest

from scripts.audit_retrospective_lineage import (
    RetrospectiveHalt, digest_json, ingest, read_first_sheet,
)


SCHEME = (
    'AUDIT_ROW:+sha256(canonical_json({"kind":"retrospective_composite_row_key.v1",'
    '"columns":[[column_name,raw_cell_text],...]}))'
)
HEADERS = ("SPORT", "EVENT", "NO.", "RESULT SOURCE URL")


def _cell(address: str, value: str, *, formula: bool = False) -> str:
    if formula:
        return f'<c r="{address}"><f>1+1</f><v>2</v></c>'
    return f'<c r="{address}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def _fixture(tmp_path: Path, *, duplicate: bool = False, missing: bool = False,
             formula: bool = False) -> tuple[dict[str, object], Path, Path, str]:
    workbook = tmp_path / "synthetic.xlsx"
    evidence = tmp_path / "synthetic-evidence.md"
    evidence.write_text("Synthetic box-score correction report, not primary settlement", encoding="utf-8")
    summary = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1">' + _cell("A1", "SUMMARY ONLY") + '</row></sheetData></worksheet>'
    )
    rows = ['<row r="1">' + "".join(_cell(f"{chr(65+i)}1", h) for i, h in enumerate(HEADERS)) + '</row>']
    records: list[dict[str, str]] = []
    for i in range(74):
        sport, num = ("CFB", i + 1) if i < 31 else (
            ("WNBA", i - 30) if i < 65 else ("CFL", i - 64)
        )
        row = {"SPORT": sport, "EVENT": f"synthetic {sport} event",
               "NO.": str(num), "RESULT SOURCE URL": f"https://example.test/original/{sport}"}
        if duplicate and i == 1:
            row["NO."] = "1"
        if missing and i == 1:
            row["NO."] = ""
        records.append(row)
        r = i + 2
        rows.append('<row r="' + str(r) + '">' + "".join(
            _cell(f"{chr(65+j)}{r}", row[key], formula=(formula and i == 1 and j == 3))
            for j, key in enumerate(HEADERS)
        ) + '</row>')
    data_xml = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>' + "".join(rows) + '</sheetData></worksheet>'
    )
    with ZipFile(workbook, "w") as z:
        z.writestr("xl/workbook.xml",
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="Summary" sheetId="1" r:id="rId1"/>'
                   '<sheet name="All 74 props" sheetId="2" r:id="rId2"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId2" Target="/xl/worksheets/sheet2.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", summary)
        z.writestr("xl/worksheets/sheet2.xml", data_xml)
    digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
    manifest: dict[str, object] = {
        "schema": "dcm.retrospective_source_corrections.v1",
        "run_id": "SYNTHETIC-COMPOSITE-RUN",
        "workbook_sha256": digest,
        "workbook_sheet_name": "All 74 props",
        "source_column": "RESULT SOURCE URL",
        "row_key_columns": ["SPORT", "EVENT", "NO."],
        "row_key_scheme": SCHEME,
        "expected_rows": 74,
        "corrections": [],
    }
    for i in range(65, 74):
        row = records[i]
        anchor = "AUDIT_ROW:" + digest_json({
            "kind": "retrospective_composite_row_key.v1",
            "columns": [[key, row[key]] for key in ("SPORT", "EVENT", "NO.")],
        })
        manifest["corrections"].append({
            "correction_id": f"SYNTH-CFL-{i - 64:02d}",
            "target_record_id": anchor,
            "original_row_sha256": digest_json(row),
            "original_source_reference": row["RESULT SOURCE URL"],
            "corrected_source_reference": "https://example.test/correct/CFL",
            "evidence_file": evidence.name,
            "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            "reason_code": "SOURCE_LINEAGE_ERROR",
            "recorded_at_utc": "2026-10-12T17:53:26Z",
            "changes_outcome": False, "changes_eligibility": False,
            "changes_model_input": False,
        })
    addendum = tmp_path / "synthetic-manifest.json"
    addendum.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest, workbook, addendum, digest


def _kwargs(tmp_path: Path, workbook: Path, addendum: Path, digest: str) -> dict:
    return dict(
        workbook=workbook, addendum=addendum, db=tmp_path / "lineage.sqlite3",
        run_id="SYNTHETIC-COMPOSITE-RUN", expected_sha256=digest,
        sheet_name="All 74 props", source_column="RESULT SOURCE URL",
        row_key_columns=("SPORT", "EVENT", "NO."),
    )


def test_named_sheet_composite_nine_corrections_and_replay(tmp_path: Path) -> None:
    manifest, workbook, addendum, digest = _fixture(tmp_path)
    assert len(read_first_sheet(workbook.read_bytes())) == 0
    selected = read_first_sheet(workbook.read_bytes(), sheet_name="All 74 props")
    assert len(selected) == 74
    assert len({row["NO."] for row in selected}) < 74
    args = _kwargs(tmp_path, workbook, addendum, digest)
    first = ingest(**args)
    assert first == {
        "schema": "dcm.retrospective_lineage_receipt.v1",
        "runId": "SYNTHETIC-COMPOSITE-RUN",
        "workbookSha256": digest,
        "rowsVerified": 74,
        "correctionsVerified": 9,
        "historicalFreezeCreated": False,
        "predictiveClaim": "NONE",
    }
    assert ingest(**args) == first
    assert hashlib.sha256(workbook.read_bytes()).hexdigest() == digest
    with sqlite3.connect(args["db"]) as conn:
        anchors = conn.execute("SELECT row_id FROM retrospective_rows").fetchall()
        assert len(anchors) == 74
        assert all(rid.startswith("AUDIT_ROW:") for (rid,) in anchors)
        assert conn.execute("SELECT COUNT(*) FROM source_corrections").fetchone()[0] == 9
        assert conn.execute("SELECT COUNT(*) FROM freezes").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_SOURCE_CORRECTION"):
            conn.execute("UPDATE source_corrections SET corrected_source_reference='tampered'")
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_RETROSPECTIVE_ROW"):
            conn.execute("DELETE FROM retrospective_rows")


@pytest.mark.parametrize("error,change", [
    ("COMPOSITE_ROW_KEY_DUPLICATE", "duplicate"),
    ("COMPOSITE_ROW_KEY_VALUE_MISSING", "missing"),
    ("FORMULA_CELL_UNSUPPORTED", "formula"),
])
def test_composite_key_and_formula_fail_closed(tmp_path: Path, error: str, change: str) -> None:
    _, workbook, addendum, digest = _fixture(tmp_path, **{change: True})
    with pytest.raises(RetrospectiveHalt, match=error):
        ingest(**_kwargs(tmp_path, workbook, addendum, digest))
    assert not (tmp_path / "lineage.sqlite3").exists()


def test_missing_named_sheet_fails_closed(tmp_path: Path) -> None:
    _, workbook, addendum, digest = _fixture(tmp_path)
    args = _kwargs(tmp_path, workbook, addendum, digest)
    args["sheet_name"] = "NOT PRESENT"
    with pytest.raises(RetrospectiveHalt, match="WORKSHEET_NAME_MISSING"):
        ingest(**args)
    assert not args["db"].exists()


def test_manifest_contract_mismatch_and_evidence_tamper(tmp_path: Path) -> None:
    manifest, workbook, addendum, digest = _fixture(tmp_path)
    args = _kwargs(tmp_path, workbook, addendum, digest)
    manifest["row_key_columns"] = ["NO."]
    addendum.write_text(json.dumps(manifest))
    with pytest.raises(RetrospectiveHalt, match="COMPOSITE_MANIFEST_CONTRACT_MISMATCH"):
        ingest(**args)
    assert not args["db"].exists()
    manifest["row_key_columns"] = ["SPORT", "EVENT", "NO."]
    addendum.write_text(json.dumps(manifest))
    (tmp_path / "synthetic-evidence.md").write_text("changed evidence")
    with pytest.raises(RetrospectiveHalt, match="CORRECTION_EVIDENCE_HASH_MISMATCH"):
        ingest(**args)
    assert not args["db"].exists()


def test_ninth_correction_hash_tamper_is_atomic(tmp_path: Path) -> None:
    manifest, workbook, addendum, digest = _fixture(tmp_path)
    manifest["corrections"][-1]["original_row_sha256"] = "0" * 64
    addendum.write_text(json.dumps(manifest))
    args = _kwargs(tmp_path, workbook, addendum, digest)
    with pytest.raises(RetrospectiveHalt, match="CORRECTION_ORIGINAL_MISMATCH"):
        ingest(**args)
    assert not args["db"].exists()


def test_expected_hash_precedes_sheet_parse(tmp_path: Path) -> None:
    _, workbook, addendum, digest = _fixture(tmp_path)
    args = _kwargs(tmp_path, workbook, addendum, digest)
    args["expected_sha256"] = "0" * 64
    with pytest.raises(RetrospectiveHalt, match="WORKBOOK_SHA256_MISMATCH"):
        ingest(**args)
    assert not args["db"].exists()
