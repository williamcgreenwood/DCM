"""Freeze immutable board.json immediately after successful ingest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.ingest.wsab_bind import annotate_rows

PARSER_SCHEMA = "BOARD_JSON_V1_2026-08-28"
LEARNING_REVISION = "LR000000"
PREDICTIVE_CLAIM = "NONE"


def accounting_from_rows(rows: list[dict]) -> dict[str, int]:
    def n(pred) -> int:
        return sum(1 for r in rows if pred(r))

    return {
        "raw_projection_rows": len(rows),
        "unique_offer_rows": len({r["projectionId"] for r in rows}),
        "standard_rows": n(lambda r: r.get("modifier") == "STANDARD"),
        "goblin_rows": n(lambda r: r.get("modifier") == "GOBLIN"),
        "demon_rows": n(lambda r: r.get("modifier") == "DEMON"),
        "unknown_modifier_rows": n(lambda r: r.get("modifier") not in {"STANDARD", "GOBLIN", "DEMON"}),
        "unknown_side_rows": n(lambda r: r.get("side") == "UNKNOWN"),
        "duplicate_rows": max(0, len(rows) - len({r["projectionId"] for r in rows})),
        "removed_rows": 0,
        "unresolved_rows": n(lambda r: r.get("market") in {"unknown", ""} or r.get("league") == "UNKNOWN"),
        "wsab_bound_rows": n(lambda r: r.get("wsabMarketBound")),
        "final_model_population": n(lambda r: r.get("modifier") != "GOBLIN"),
    }


def freeze_board(ingest: dict[str, Any], *, mount: dict[str, Any], cutoff: str = "2026-08-28T00:00:00Z") -> dict[str, Any]:
    rows = annotate_rows(list(ingest.get("rows") or []))
    acc = accounting_from_rows(rows)
    unique_events = sorted({r.get("eventId") or "" for r in rows})
    payload = {
        "schemaId": PARSER_SCHEMA,
        "parserVersion": ingest.get("parserVersion"),
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "v5Mount": mount,
        "v5Decoder": ingest.get("v5Decoder", "NOT_MOUNTED"),
        "sourceAdapter": ingest.get("adapter"),
        "harSha256": ingest.get("harSha256"),
        "captureStart": ingest.get("captureStart") or "",
        "captureEnd": ingest.get("captureEnd") or "",
        "forecastCutoff": cutoff,
        "redactedSecrets": ingest.get("redactedSecrets") or 0,
        "indexStats": ingest.get("indexStats") or {},
        "warnings": ingest.get("warnings") or [],
        "rows": rows,
        "unresolvedRows": [r["projectionId"] for r in rows if r.get("market") in {"unknown", ""} or r.get("league") == "UNKNOWN"],
        "eventIds": unique_events,
        "accounting": acc,
    }
    payload["contentHash"] = content_hash({k: v for k, v in payload.items() if k not in {"contentHash"}})
    return payload


def write_board(board: dict[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(board, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    return dest
