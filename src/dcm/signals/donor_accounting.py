"""Complete, non-activating disposition accounting for donor candidates."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_DISPOSITIONS = frozenset({
    "PORT_NATIVE", "MERGE_WITH_EXISTING", "REINTERPRET", "PORT_AS_DIAGNOSTIC",
    "PORT_AS_EVIDENCE", "PORT_FUTURE_ONLY", "REFERENCE_ONLY", "DEFER_SPORT_PLUGIN",
    "GENERALIZE", "GENERALIZE_HOST_NEUTRAL", "REIMPLEMENT_CORE_IDEAS", "REJECT",
    "REJECT_CONFLICT", "REJECT_INVALID", "REJECT_DUPLICATE", "REJECT_IF_FORCING",
    "REJECT_AS_PROBABILITY_TRANSFORM", "REJECT_NAME_AND_IMPL",
})


@dataclass(frozen=True)
class DonorAccountingReport:
    component_count: int
    disposition_counts: dict[str, int]
    exact_archive_state: str
    active_count: int
    complete: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "pillars_dcm.p380x_donor_accounting.v1",
            "componentCount": self.component_count,
            "dispositionCounts": dict(sorted(self.disposition_counts.items())),
            "exactArchiveState": self.exact_archive_state,
            "activeCount": self.active_count,
            "complete": self.complete,
            "runtimeImportable": False,
        }


def audit_donor_matrix(path: Path, *, expected_count: int = 58, exact_archives_available: bool = False) -> DonorAccountingReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = payload.get("components") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise ValueError("DONOR_COMPONENTS_REQUIRED")
    ids: set[str] = set()
    counts: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("DONOR_COMPONENT_INVALID")
        donor_id = str(entry.get("id") or "")
        if not donor_id or donor_id in ids:
            raise ValueError(f"DONOR_ID_INVALID_OR_DUPLICATE:{donor_id}")
        ids.add(donor_id)
        disposition = str(entry.get("disposition") or "")
        if disposition not in ALLOWED_DISPOSITIONS:
            raise ValueError(f"DONOR_DISPOSITION_INVALID:{donor_id}:{disposition}")
        if entry.get("active") is True:
            raise ValueError(f"DONOR_MATRIX_CANNOT_SELF_ACTIVATE:{donor_id}")
        counts[disposition] = counts.get(disposition, 0) + 1
    if len(entries) != expected_count:
        raise ValueError(f"DONOR_ACCOUNTING_COUNT_MISMATCH:expected={expected_count}:actual={len(entries)}")
    return DonorAccountingReport(
        component_count=len(entries),
        disposition_counts=counts,
        exact_archive_state="QUARANTINED_HASHED" if exact_archives_available else "EXACT_ARCHIVE_BYTES_UNAVAILABLE",
        active_count=0,
        complete=True,
    )
