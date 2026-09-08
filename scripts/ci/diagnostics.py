#!/usr/bin/env python3
"""Emit a sanitized GitHub Actions failure receipt."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dcm.runtime.diagnostics import build_diagnostics, write_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--command", default=os.environ.get("DCM_DIAGNOSTIC_COMMAND", "github-actions"))
    parser.add_argument("--failure-code", default=os.environ.get("DCM_FAILURE_CODE"))
    parser.add_argument("--exit-code", type=int, default=int(os.environ.get("DCM_EXIT_CODE", "1")))
    args = parser.parse_args()
    payload = build_diagnostics(
        command=args.command,
        exit_code=args.exit_code,
        failure_code=args.failure_code,
        context={"recoveryCommand": "python -m dcm.chat doctor --format json", "branch": os.environ.get("GITHUB_REF_NAME")},
    )
    result = write_diagnostics(args.out, payload)
    print(json.dumps({"path": str(args.out), "contentHash": result["contentHash"], "failureCode": result.get("failureCode")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
