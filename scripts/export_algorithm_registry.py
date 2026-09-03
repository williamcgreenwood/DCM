#!/usr/bin/env python3
"""Export catalog.py to committed algorithm_registry.json and package copies.

catalog.py is the editable source of truth. CI fails if committed JSON drifts.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "artifacts" / "dcm_v6_workstream_ab"
sys.path.insert(0, str(PKG))

from dcm.algorithms.catalog import ALGORITHM_RECORDS, CONSTITUTION_VERSION  # noqa: E402
from dcm.algorithms.registry import catalog_bytes  # noqa: E402


REGISTRY_PATHS = (
    ROOT / "configs" / "algorithm_registry.json",
    PKG / "dcm" / "algorithms" / "data" / "algorithm_registry.json",
)
CONSTITUTION_SRC = ROOT / "docs" / "architecture" / "DCM_ALGORITHMIC_CONSTITUTION.md"
CONSTITUTION_DST = PKG / "dcm" / "algorithms" / "data" / "DCM_ALGORITHMIC_CONSTITUTION.md"
TRACE_PATH = ROOT / "docs" / "requirements" / "ALGORITHM_TRACE_MATRIX.md"


def _trace_markdown() -> str:
    rows = sorted(ALGORITHM_RECORDS, key=lambda r: r["algorithm_id"])
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["lifecycle"]] = counts.get(row["lifecycle"], 0) + 1
    lines = [
        "# Algorithm requirement trace matrix",
        "",
        f"Constitution version: `{CONSTITUTION_VERSION}`",
        "",
        "Generated from `dcm.algorithms.catalog`. Do not hand-edit algorithm rows.",
        "Re-run `python scripts/export_algorithm_registry.py` after catalog changes.",
        "",
        f"- Registry rows: **{len(rows)}**",
        f"- REQUIRED_CORE: **{counts.get('REQUIRED_CORE', 0)}**",
        f"- REQUIRED_CONDITIONAL: **{counts.get('REQUIRED_CONDITIONAL', 0)}**",
        f"- PERMANENT_CHALLENGER: **{counts.get('PERMANENT_CHALLENGER', 0)}**",
        "",
        "| algorithm_id | name | family | lifecycle | implementation | producer | consumer | fallback | tests | traces |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        impl = f"{row['implementation_module']}.{row['implementation_symbol']}"
        tests = ",".join(row.get("test_ids") or [])
        traces = ",".join(row.get("requirement_trace_ids") or [])
        lines.append(
            "| `{id}` | {name} | {fam} | {life} | `{impl}` | {prod} | {cons} | {fb} | {tests} | {traces} |".format(
                id=row["algorithm_id"],
                name=row["canonical_name"].replace("|", "/"),
                fam=row["algorithm_family"],
                life=row["lifecycle"],
                impl=impl,
                prod=str(row["runtime_producer"]).replace("|", "/"),
                cons=str(row["runtime_consumer"]).replace("|", "/"),
                fb=row.get("fallback_algorithm_id") or "",
                tests=tests,
                traces=traces,
            )
        )
    lines += [
        "",
        "## Requirement IDs closed by R0",
        "",
        "| ID | Statement | Status |",
        "|---|---|---|",
        "| REQ-ALG-CONST-R0 | Permanent constitution document, registry, schema, selection engine, HAR execution plan, CI gates | CLOSED in software for R0 |",
        "| REQ-ALG-SETCOVER | Weighted set-cover remains a permanent Research OS scheduling requirement | CLOSED as registered CORE primitive; live AcquisitionAction packing remains R1 |",
        "| REQ-ALG-SUBMODULAR | Submodular/lazy-greedy marginal coverage remains a permanent scheduling requirement | CLOSED as registered CORE primitive; live scheduler integration remains R1 |",
        "| REQ-ALG-FALLBACK | ChatGPT-native deterministic fallbacks exist for optional packages | CLOSED for registered conditionals/challengers |",
        "| REQ-ALG-RELEASE | Release manifests include constitution and registry hashes | CLOSED |",
        "| REQ-ALG-NO-SILENT-RETIRE | Retirement requires ADR | CLOSED as contract/CI |",
        "",
        "R0 does not close BoardGraph/RequirementGraph/AcquisitionAction live HAR research (R1).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    check = "--check" in sys.argv
    blob = catalog_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if check:
        for dest in REGISTRY_PATHS:
            if not dest.is_file():
                raise SystemExit(f"ALGORITHM_REGISTRY_MISSING:{dest}")
            if dest.read_bytes() != blob:
                raise SystemExit(f"ALGORITHM_REGISTRY_STALE:{dest}")
        if not CONSTITUTION_SRC.is_file():
            raise SystemExit("ALGORITHM_CONSTITUTION_MISSING")
        if not CONSTITUTION_DST.is_file() or CONSTITUTION_DST.read_bytes() != CONSTITUTION_SRC.read_bytes():
            raise SystemExit("ALGORITHM_CONSTITUTION_PACKAGE_COPY_STALE")
        print(f"ALGORITHM_REGISTRY_SHA256={digest}")
        print("ok")
        return 0
    for dest in REGISTRY_PATHS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    if not CONSTITUTION_SRC.is_file():
        raise SystemExit("ALGORITHM_CONSTITUTION_MISSING")
    CONSTITUTION_DST.parent.mkdir(parents=True, exist_ok=True)
    CONSTITUTION_DST.write_bytes(CONSTITUTION_SRC.read_bytes())
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.write_text(_trace_markdown(), encoding="utf-8")
    print(f"ALGORITHM_REGISTRY_SHA256={digest}")
    print(f"rows={len(ALGORITHM_RECORDS)}")
    print(f"wrote {REGISTRY_PATHS[0].relative_to(ROOT)}")
    print(f"wrote {TRACE_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
