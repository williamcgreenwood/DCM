"""CLI for appending exact Outlier Insights settlements.

The outcomes file is an operator/researcher-supplied normalized evidence map;
this command never scrapes or invents a result.  It grades the full claim
population and leaves unresolved rows visible in the ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.learning.insight_settlement import (
    append_insight_settlements,
    settle_insight_population,
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _outcomes(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("outcomes"), list):
        return [dict(row) for row in value["outcomes"] if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("outcomes"), dict):
        rows = []
        for key, row in value["outcomes"].items():
            if isinstance(row, dict):
                item = dict(row)
                item.setdefault("claimId", key)
                rows.append(item)
        return rows
    raise ValueError("OUTCOMES_MUST_BE_LIST_OR_OUTCOMES_MAP")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append exact Outlier Insights settlements")
    parser.add_argument("--claims", type=Path, required=True, help="insights_claims.jsonl")
    parser.add_argument("--outcomes", type=Path, required=True, help="normalized outcomes JSON")
    parser.add_argument("--destination", type=Path, required=True, help="run directory")
    parser.add_argument("--cutoff", required=True, help="forecast decision cutoff")
    parser.add_argument("--rule-hash", required=True, help="validated sport/market settlement rule hash")
    parser.add_argument("--recorded-at", default=None, help="record timestamp; defaults to current UTC")
    parser.add_argument("--run-id", default="", help="run identifier")
    parser.add_argument("--learning-revision", default="LR000000")
    args = parser.parse_args(argv)

    claims = _jsonl(args.claims)
    outcomes = _outcomes(args.outcomes)
    recorded_at = args.recorded_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = settle_insight_population(
        claims,
        outcomes,
        decision_cutoff=args.cutoff,
        settlement_rule_hash=args.rule_hash,
        recorded_at=recorded_at,
    )
    append_result = append_insight_settlements(
        args.destination,
        result["ledger"],
        run_id=args.run_id,
        decision_cutoff=args.cutoff,
        learning_revision=args.learning_revision,
    )
    manifest = {
        "schema": "pillars_dcm.outlier_insights_settlement_manifest.v1",
        "adapterVersion": result["adapterVersion"],
        "claimFileHash": _file_hash(args.claims),
        "outcomesFileHash": _file_hash(args.outcomes),
        "outcomeCount": len(outcomes),
        "decisionCutoff": args.cutoff,
        "recordedAt": recorded_at,
        "settlementRuleHash": args.rule_hash,
        "summary": {
            key: value for key, value in result.items()
            if key not in {"ledger", "contentHash"}
        },
        "append": append_result,
    }
    manifest["contentHash"] = content_hash(manifest)
    args.destination.mkdir(parents=True, exist_ok=True)
    (args.destination / "insight_settlement_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
