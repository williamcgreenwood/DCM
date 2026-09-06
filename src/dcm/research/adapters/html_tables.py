"""Stdlib HTML table extractor for Basketball-Reference-style pages.

Uses data-stat attributes when present (B-R), else header text. Unwraps
HTML comments that wrap tables (B-R advanced/split tables).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL | re.IGNORECASE)


def unwrap_commented_tables(html: str) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1) or ""
        if "<table" in inner.lower():
            return inner
        return match.group(0)

    return _COMMENT.sub(repl, html or "")


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict[str, Any]] = []
        self._in_table = False
        self._in_thead = False
        self._in_tbody = False
        self._in_tr = False
        self._in_cell = False
        self._cell_tag = ""
        self._cell_text: list[str] = []
        self._cell_attrs: dict[str, str] = {}
        self._row_cells: list[dict[str, str]] = []
        self._row_class = ""
        self._section = ""
        self._headers: list[dict[str, str]] = []
        self._rows: list[list[dict[str, str]]] = []
        self._table_id = ""
        self._table_class = ""
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        if tag == "table":
            if not self._in_table:
                self._in_table = True
                self._depth = 1
                self._table_id = ad.get("id") or ""
                self._table_class = ad.get("class") or ""
                self._headers = []
                self._rows = []
                self._in_thead = False
                self._in_tbody = False
            else:
                self._depth += 1
            return
        if not self._in_table:
            return
        if tag == "thead":
            self._in_thead = True
            self._section = "thead"
        elif tag == "tbody":
            self._in_tbody = True
            self._section = "tbody"
        elif tag == "tr":
            self._in_tr = True
            self._row_cells = []
            self._row_class = ad.get("class") or ""
        elif tag in {"th", "td"} and self._in_tr:
            self._in_cell = True
            self._cell_tag = tag
            self._cell_text = []
            self._cell_attrs = ad

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            self._depth -= 1
            if self._depth <= 0:
                self.tables.append(
                    {
                        "id": self._table_id,
                        "class": self._table_class,
                        "headers": list(self._headers),
                        "rows": list(self._rows),
                    }
                )
                self._in_table = False
                self._table_id = ""
                self._headers = []
                self._rows = []
            return
        if not self._in_table:
            return
        if tag in {"th", "td"} and self._in_cell:
            text = re.sub(r"\s+", " ", "".join(self._cell_text)).strip()
            cell = {
                "tag": self._cell_tag,
                "text": text,
                "stat": (self._cell_attrs.get("data-stat") or "").strip(),
                "class": self._cell_attrs.get("class") or "",
            }
            self._row_cells.append(cell)
            self._in_cell = False
            self._cell_text = []
        elif tag == "tr" and self._in_tr:
            classes = set(self._row_class.lower().split())
            is_header_row = (
                self._in_thead
                or (not self._in_tbody and any(c["tag"] == "th" for c in self._row_cells))
                or "thead" in classes
            )
            if is_header_row:
                # Keep the most complete header row.
                if len(self._row_cells) >= len(self._headers):
                    self._headers = list(self._row_cells)
            elif "thead" not in classes and self._row_cells:
                self._rows.append(list(self._row_cells))
            self._in_tr = False
            self._row_cells = []
        elif tag == "thead":
            self._in_thead = False
            if self._section == "thead":
                self._section = ""
        elif tag == "tbody":
            self._in_tbody = False
            if self._section == "tbody":
                self._section = ""

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)


def extract_tables(html: str) -> list[dict[str, Any]]:
    parser = _TableParser()
    parser.feed(unwrap_commented_tables(html or ""))
    parser.close()
    return parser.tables


def table_rows_as_dicts(table: dict[str, Any]) -> list[dict[str, Any]]:
    headers = table.get("headers") or []
    keys: list[str] = []
    for i, cell in enumerate(headers):
        stat = str(cell.get("stat") or "").strip()
        text = str(cell.get("text") or "").strip()
        key = stat or text or f"col_{i}"
        keys.append(key)
    out: list[dict[str, Any]] = []
    for row in table.get("rows") or []:
        rec: dict[str, Any] = {}
        for i, cell in enumerate(row):
            key = str(cell.get("stat") or "").strip()
            if not key:
                key = keys[i] if i < len(keys) else f"col_{i}"
            rec[key] = cell.get("text")
        if any(str(v).strip() for v in rec.values() if v is not None):
            out.append(rec)
    return out
