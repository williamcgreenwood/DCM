"""CLI: settle an immutable DCM run against official postgame outcomes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dcm.learning.postgame import settle_run


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", "--dest", dest="run", type=Path, required=True)
    p.add_argument("--outcomes", type=Path, required=True)
    p.add_argument("--card-only", action="store_true")
    args = p.parse_args(argv)
    result = settle_run(args.run, args.outcomes, card_only=bool(args.card_only))
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
