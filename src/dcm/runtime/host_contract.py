"""Typed host execution and terminal-board accounting contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from dcm.contracts.hashes import content_hash


@dataclass(frozen=True)
class HostReceipt:
    schema: str
    run_id: str
    state: str
    raw_rows: int
    terminal_rows: int
    accounting_hash: str
    research_required: bool

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def build_terminal_accounting(
    rows: list[dict[str, Any]],
    classify: Callable[[dict[str, Any]], tuple[str, str | None]],
    *,
    run_id: str,
    research_required: bool = True,
) -> tuple[dict[str, Any], HostReceipt]:
    """Classify every row exactly once and emit a deterministic receipt."""
    records: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in rows:
        state, blocker = classify(row)
        rec = {
            "projectionId": str(row.get("projectionId") or ""),
            "state": str(state),
            "blocker": blocker,
            "terminal": True,
        }
        records.append(rec)
        counts[rec["state"]] = counts.get(rec["state"], 0) + 1
    records.sort(key=lambda r: r["projectionId"])
    body = {"schema": "pillars_dcm.terminal_accounting.v1", "records": records, "counts": counts}
    body["contentHash"] = content_hash(body)
    receipt = HostReceipt(
        schema="pillars_dcm.host_execution_receipt.v1",
        run_id=str(run_id),
        state="ACCOUNTED" if len(records) == len(rows) else "INCOMPLETE",
        raw_rows=len(rows),
        terminal_rows=sum(1 for r in records if r["terminal"]),
        accounting_hash=body["contentHash"],
        research_required=bool(research_required),
    )
    return body, receipt
