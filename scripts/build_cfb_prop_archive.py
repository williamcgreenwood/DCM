#!/usr/bin/env python3
"""Create a content-addressed screenshot/OCR player-prop intake package.

The raw board packet and mutable research outputs belong in Drive. This script
creates small, reproducible local artifacts that are safe to version in Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def page_number(path: Path) -> int:
    match = re.search(r"page-(\d+)", path.stem)
    if not match:
        raise ValueError(f"Not a page OCR file: {path}")
    return int(match.group(1))


def market_families(text: str) -> list[str]:
    pairs = {
        "rush attempts": "rush_attempts",
        "rush yards": "rush_yards",
        "rush+rec": "rush_receiving_yards",
        "rec yards": "receiving_yards",
        "recs": "receptions",
        "pass attempts": "pass_attempts",
        "pass comp": "pass_completions",
        "pass yards": "pass_yards",
        "pass+rush": "pass_rush_yards",
        "fantasy score": "fantasy_score",
        "(combo)": "combo",
    }
    lower = text.lower()
    return sorted({family for marker, family in pairs.items() if marker in lower})


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--ocr-dir", type=Path, required=True)
    parser.add_argument("--subjects", type=Path, required=True,
                        help="JSONL subjects normalized after screenshot review")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--minimum-queue-seconds", type=int, default=300)
    args = parser.parse_args()

    if args.minimum_queue_seconds < 300:
        raise ValueError("Protocol requires at least a 300-second research queue.")
    if not args.pdf.exists():
        raise FileNotFoundError(args.pdf)

    pages = []
    for path in sorted(args.ocr_dir.glob("page-*.txt"), key=page_number):
        text = path.read_text(errors="replace")
        pages.append({
            "source_page": page_number(path),
            "ocr_text_sha256": sha256(path),
            "ocr_text": text,
            "market_families_detected": market_families(text),
            "extraction_status": "RAW_OCR_REVIEW_REQUIRED",
        })

    subjects = read_jsonl(args.subjects)
    for subject in subjects:
        subject.setdefault("research_status", "QUEUED")
        subject.setdefault("forecast_status", "NOT_MODELED")
        subject.setdefault(
            "reason_code",
            "NO_FORECAST_UNTIL_CURRENT_OFFER_AND_PLAYER_LINK_ARE_CONFIRMED",
        )

    manifest = {
        "run_id": args.run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "protocol": "Research, Forecasting & Evidence Archive Protocol",
        "minimum_research_queue_seconds": args.minimum_queue_seconds,
        "state": "INTAKE_COMPLETE_RESEARCH_QUEUED",
        "source": {
            "filename": args.pdf.name,
            "sha256": sha256(args.pdf),
            "pages": len(pages),
        },
        "pages": pages,
        "subjects": subjects,
        "integrity": {
            "raw_pdf_is_the_source_of_truth_for_board_availability": True,
            "no_screenshot_offer_is_treated_as_current": True,
            "missing_evidence_must_remain_missing": True,
            "forecast_requires_current_offer_plus_confirmed_entity_link": True,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    (args.output_dir / "ocr_pages.jsonl").write_text(
        "".join(json.dumps(page) + "\n" for page in pages)
    )
    (args.output_dir / "archive_receipt.json").write_text(
        json.dumps({
            "run_id": args.run_id,
            "source_sha256": manifest["source"]["sha256"],
            "page_count": len(pages),
            "subject_count": len(subjects),
            "state": manifest["state"],
        }, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
