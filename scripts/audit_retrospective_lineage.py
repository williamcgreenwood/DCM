#!/usr/bin/env python3
"""Quarantined, append-only retrospective provenance importer (not a forecast).

Use on a local original .xlsx and a machine-readable correction addendum.
No workbook rows, evidence contents, or source URLs are written to stdout or Git.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from dcm.runtime.lineage_integrity import LineageStore

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


class RetrospectiveHalt(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _col(address: str) -> int:
    letters = re.match(r"[A-Z]+", address.upper())
    if not letters:
        raise RetrospectiveHalt("INVALID_CELL_ADDRESS")
    out = 0
    for char in letters.group():
        out = out * 26 + ord(char) - 64
    return out - 1


def read_first_sheet(data: bytes, *, sheet_name: str | None = None) -> list[dict[str, str]]:
    """Read literal XLSX cells from an explicitly named sheet, or first sheet by default.

    No formula evaluation. A missing or duplicate requested sheet fails closed.
    """
    if len(data) > 20_000_000:
        raise RetrospectiveHalt("WORKBOOK_SIZE_LIMIT")
    try:
        with ZipFile(io.BytesIO(data)) as z:
            required = ["xl/workbook.xml", "xl/_rels/workbook.xml.rels"]
            for name in required:
                if z.getinfo(name).file_size > 10_000_000:
                    raise RetrospectiveHalt("WORKBOOK_XML_SIZE_LIMIT")
            book = ET.fromstring(z.read("xl/workbook.xml"))
            sheets = book.findall(f"{{{MAIN}}}sheets/{{{MAIN}}}sheet")
            if sheet_name is None:
                if not sheets:
                    raise RetrospectiveHalt("WORKSHEET_MISSING")
                sheet = sheets[0]
            else:
                if not isinstance(sheet_name, str) or not sheet_name:
                    raise RetrospectiveHalt("WORKSHEET_NAME_INVALID")
                matches = [item for item in sheets if item.get("name") == sheet_name]
                if not matches:
                    raise RetrospectiveHalt("WORKSHEET_NAME_MISSING")
                if len(matches) != 1:
                    raise RetrospectiveHalt("WORKSHEET_NAME_AMBIGUOUS")
                sheet = matches[0]
            rel_id = sheet.get(f"{{{REL}}}id")
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            target = next((r.get("Target") for r in rels.findall(f"{{{PKG_REL}}}Relationship") if r.get("Id") == rel_id), None)
            if not target:
                raise RetrospectiveHalt("WORKSHEET_RELATION_MISSING")
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            if ".." in Path(target).parts:
                raise RetrospectiveHalt("WORKSHEET_PATH_INVALID")
            if z.getinfo(target).file_size > 10_000_000:
                raise RetrospectiveHalt("WORKBOOK_XML_SIZE_LIMIT")
            strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                if z.getinfo("xl/sharedStrings.xml").file_size > 10_000_000:
                    raise RetrospectiveHalt("WORKBOOK_XML_SIZE_LIMIT")
                ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
                strings = ["".join(t.text or "" for t in si.findall(f".//{{{MAIN}}}t")) for si in ss.findall(f"{{{MAIN}}}si")]
            root = ET.fromstring(z.read(target))
            rows: list[list[str]] = []
            for row in root.findall(f".//{{{MAIN}}}sheetData/{{{MAIN}}}row"):
                values: dict[int, str] = {}
                for cell in row.findall(f"{{{MAIN}}}c"):
                    if cell.find(f"{{{MAIN}}}f") is not None:
                        raise RetrospectiveHalt("FORMULA_CELL_UNSUPPORTED")
                    typ = cell.get("t")
                    v = cell.find(f"{{{MAIN}}}v")
                    if typ == "s":
                        if v is None or not (v.text or "").isdigit() or int(v.text) >= len(strings):
                            raise RetrospectiveHalt("SHARED_STRING_INVALID")
                        value = strings[int(v.text)]
                    elif typ == "inlineStr":
                        value = "".join(t.text or "" for t in cell.findall(f".//{{{MAIN}}}t"))
                    else:
                        value = v.text if v is not None and v.text is not None else ""
                    values[_col(cell.get("r") or "")] = value
                if values:
                    row_values = [values.get(i, "") for i in range(max(values) + 1)]
                    if any(str(v).strip() for v in row_values):
                        rows.append(row_values)
    except (KeyError, BadZipFile, ET.ParseError, OSError) as exc:
        raise RetrospectiveHalt("WORKBOOK_UNREADABLE") from exc
    if not rows:
        raise RetrospectiveHalt("WORKBOOK_EMPTY")
    header = [v.strip().lstrip("\ufeff") for v in rows[0]]
    if any(not h for h in header) or len(set(header)) != len(header):
        raise RetrospectiveHalt("WORKBOOK_HEADERS_INVALID")
    records = []
    for row in rows[1:]:
        if len(row) > len(header) and any(v.strip() for v in row[len(header):]):
            raise RetrospectiveHalt("WORKBOOK_UNEXPECTED_COLUMNS")
        records.append(dict(zip(header, row + [""] * (len(header) - len(row)))))
    return records


def ingest(*, workbook: Path, addendum: Path, db: Path, run_id: str,
           expected_sha256: str, source_column: str = "SOURCE_URL", expected_rows: int = 74,
           sheet_name: str | None = None,
           row_key_columns: tuple[str, ...] | None = None) -> dict[str, object]:
    """Verify before the first write; then commit original row anchors and corrections atomically."""
    if not run_id or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256.lower()):
        raise RetrospectiveHalt("EXPECTED_HASH_REQUIRED")
    raw = workbook.read_bytes()
    actual_hash = sha256(raw)
    if actual_hash != expected_sha256.lower():
        raise RetrospectiveHalt("WORKBOOK_SHA256_MISMATCH")
    if row_key_columns is not None:
        if not isinstance(row_key_columns, (list, tuple)) or not row_key_columns or (
            any(not isinstance(k, str) or not k or k != k.strip() for k in row_key_columns)
        ) or len(set(row_key_columns)) != len(row_key_columns):
            raise RetrospectiveHalt("COMPOSITE_ROW_KEY_COLUMNS_INVALID")
        if not sheet_name:
            raise RetrospectiveHalt("COMPOSITE_WORKSHEET_NAME_REQUIRED")
    records = read_first_sheet(raw, sheet_name=sheet_name)
    if len(records) != expected_rows:
        raise RetrospectiveHalt("WORKBOOK_ROW_COUNT_MISMATCH")
    ids = ("ROW_ID", "RECORD_ID", "PROP_ID")
    id_col = next((key for key in ids if key in records[0]), None)
    if source_column not in records[0]:
        raise RetrospectiveHalt("ROW_ID_OR_SOURCE_COLUMN_MISSING")
    if row_key_columns is None and not id_col:
        raise RetrospectiveHalt("ROW_ID_OR_SOURCE_COLUMN_MISSING")
    if row_key_columns is not None and any(key not in records[0] for key in row_key_columns):
        raise RetrospectiveHalt("COMPOSITE_ROW_KEY_COLUMN_MISSING")
    rows = {}
    for row in records:
        if row_key_columns is None:
            rid = row[id_col].strip()
            if not rid or rid in rows:
                raise RetrospectiveHalt("ROW_ID_MISSING_OR_DUPLICATE")
        else:
            # Audit-row anchor ONLY. Never reuse this as a historical PROP_ID.
            columns = [[key, row[key]] for key in row_key_columns]
            if any(not value.strip() for _, value in columns):
                raise RetrospectiveHalt("COMPOSITE_ROW_KEY_VALUE_MISSING")
            rid = "AUDIT_ROW:" + digest_json({
                "kind": "retrospective_composite_row_key.v1", "columns": columns
            })
            if rid in rows:
                raise RetrospectiveHalt("COMPOSITE_ROW_KEY_DUPLICATE")
        rows[rid] = (digest_json(row), row[source_column])
    try:
        amendment = json.loads(addendum.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RetrospectiveHalt("ADDENDUM_STRUCTURED_JSON_REQUIRED") from exc
    if amendment.get("workbook_sha256") != actual_hash:
        raise RetrospectiveHalt("ADDENDUM_WORKBOOK_HASH_MISMATCH")
    if row_key_columns is not None:
        expected_scheme = (
            'AUDIT_ROW:+sha256(canonical_json({"kind":"retrospective_composite_row_key.v1",'
            '"columns":[[column_name,raw_cell_text],...]}))'
        )
        expected_contract = {
            "schema": "dcm.retrospective_source_corrections.v1",
            "run_id": run_id,
            "workbook_sheet_name": sheet_name,
            "source_column": source_column,
            "row_key_columns": list(row_key_columns),
            "row_key_scheme": expected_scheme,
            "expected_rows": expected_rows,
        }
        if any(amendment.get(key) != value for key, value in expected_contract.items()):
            raise RetrospectiveHalt("COMPOSITE_MANIFEST_CONTRACT_MISMATCH")
    corrections = amendment.get("corrections")
    if not isinstance(corrections, list):
        raise RetrospectiveHalt("CORRECTIONS_LIST_REQUIRED")
    seen = set()
    verified = []
    for c in corrections:
        cid = str(c.get("correction_id") or "")
        rid = str(c.get("target_record_id") or "")
        if not cid or cid in seen or rid not in rows:
            raise RetrospectiveHalt("CORRECTION_ID_OR_TARGET_INVALID")
        seen.add(cid)
        row_hash, original_source = rows[rid]
        if c.get("original_row_sha256") != row_hash or c.get("original_source_reference") != original_source:
            raise RetrospectiveHalt("CORRECTION_ORIGINAL_MISMATCH")
        corrected = str(c.get("corrected_source_reference") or "")
        if not corrected or corrected == original_source:
            raise RetrospectiveHalt("CORRECTION_REPLACEMENT_INVALID")
        evidence_path = Path(str(c.get("evidence_file") or ""))
        if not evidence_path.is_absolute():
            evidence_path = addendum.parent / evidence_path
        if not evidence_path.is_file() or sha256(evidence_path.read_bytes()) != c.get("evidence_sha256"):
            raise RetrospectiveHalt("CORRECTION_EVIDENCE_HASH_MISMATCH")
        if c.get("reason_code") != "SOURCE_LINEAGE_ERROR":
            raise RetrospectiveHalt("CORRECTION_REASON_UNSUPPORTED")
        flags = [c.get(k) for k in ("changes_outcome", "changes_eligibility", "changes_model_input")]
        if any(type(v) is not bool for v in flags):
            raise RetrospectiveHalt("CORRECTION_EFFECT_FLAGS_REQUIRED")
        timestamp = str(c.get("recorded_at_utc") or "")
        from datetime import datetime, timezone
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
                raise ValueError("UTC required")
        except ValueError as exc:
            raise RetrospectiveHalt("CORRECTION_TIMESTAMP_INVALID") from exc
        # A verified evidence-file hash proves bytes, not independent sports-source authority.
        payload = {"correction_id": cid, "run_id": run_id, "row_id": rid,
                   "original_row_sha256": row_hash, "original_source_reference": original_source,
                   "corrected_source_reference": corrected, "evidence_sha256": c["evidence_sha256"],
                   "reason_code": c["reason_code"], "recorded_at_utc": timestamp,
                   "changes_outcome": int(flags[0]), "changes_eligibility": int(flags[1]),
                   "changes_model_input": int(flags[2])}
        verified.append((payload, digest_json(payload)))
    store = LineageStore(db)
    try:
        with store.conn:
            for rid, (row_hash, source) in rows.items():
                existing = store.conn.execute("SELECT row_sha256,workbook_sha256,original_source_reference FROM retrospective_rows WHERE run_id=? AND row_id=?", (run_id, rid)).fetchone()
                if existing and existing != (row_hash, actual_hash, source):
                    raise RetrospectiveHalt("RETROSPECTIVE_ROW_CONFLICT")
                if not existing:
                    store.conn.execute("INSERT INTO retrospective_rows(run_id,row_id,row_sha256,workbook_sha256,original_source_reference) VALUES(?,?,?,?,?)", (run_id, rid, row_hash, actual_hash, source))
            for p, digest in verified:
                existing = store.conn.execute("SELECT content_hash FROM source_corrections WHERE correction_id=?", (p["correction_id"],)).fetchone()
                if existing and existing[0] != digest:
                    raise RetrospectiveHalt("CORRECTION_IMMUTABILITY_CONFLICT")
                if not existing:
                    store.conn.execute("INSERT INTO source_corrections(correction_id,run_id,row_id,original_row_sha256,original_source_reference,corrected_source_reference,evidence_sha256,reason_code,recorded_at_utc,changes_outcome,changes_eligibility,changes_model_input,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (*p.values(), digest))
    finally:
        store.close()
    return {"schema": "dcm.retrospective_lineage_receipt.v1", "runId": run_id,
            "workbookSha256": actual_hash, "rowsVerified": len(rows),
            "correctionsVerified": len(verified), "historicalFreezeCreated": False,
            "predictiveClaim": "NONE"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workbook", type=Path, required=True)
    ap.add_argument("--addendum", type=Path, required=True)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--source-column", default="SOURCE_URL")
    ap.add_argument("--sheet-name", help="Exact XLSX worksheet name (default: first worksheet)")
    ap.add_argument("--row-key-columns", help="Comma-separated composite retrospective audit key")
    args = ap.parse_args(argv)
    try:
        row_key_columns = None
        if args.row_key_columns is not None:
            row_key_columns = tuple(args.row_key_columns.split(","))
        receipt = ingest(workbook=args.workbook, addendum=args.addendum, db=args.db,
                         run_id=args.run_id, expected_sha256=args.expected_sha256,
                         source_column=args.source_column, sheet_name=args.sheet_name,
                         row_key_columns=row_key_columns)
    except (RetrospectiveHalt, OSError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": getattr(exc, "code", "INPUT_IO_ERROR")}), file=sys.stderr)
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
