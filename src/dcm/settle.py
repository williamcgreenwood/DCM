"""CLI: settle the full modeled population of an immutable DCM run.

python -m dcm.settle --dest RUNS/<id> --outcomes outcomes.json
python -m dcm.settle --dest RUNS/<id> --outcomes outcomes.json --card-only
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dcm.learning.postgame import settle_run


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Settle a frozen DCM run against synthetic/official outcome maps. Does not invent outcomes."
    )
    p.add_argument("--dest", "--run", dest="dest", type=Path, required=True, help="Existing run directory")
    p.add_argument("--outcomes", type=Path, required=True, help="Outcome map JSON (projectionId -> result)")
    p.add_argument(
        "--card-only",
        action="store_true",
        help="Settle only the 0-6 strict_card subset instead of the full modeled population.",
    )
    args = p.parse_args(argv)
    result = settle_run(args.dest, args.outcomes, card_only=bool(args.card_only))
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
