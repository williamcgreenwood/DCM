#!/usr/bin/env python3
"""Run one CI gate and emit a sanitized diagnostic receipt on failure."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcm.runtime.diagnostics import build_diagnostics, write_diagnostics  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, default=ROOT)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    completed = subprocess.run(command, cwd=args.cwd, text=True, capture_output=True, check=False)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode == 0:
        return 0
    output = (completed.stdout + "\n" + completed.stderr).strip()
    payload = build_diagnostics(
        command=args.name,
        exit_code=completed.returncode,
        failure_code=f"CI_GATE_{args.name.upper().replace('-', '_')}",
        context={
            "argv": command,
            "outputTail": output[-4000:],
            "recoveryCommand": "python -m dcm.chat doctor --format json",
            "branch": os.environ.get("GITHUB_REF_NAME"),
        },
    )
    result = write_diagnostics(args.out, payload)
    print(
        f"DCM_GATE_FAILURE name={args.name} exitCode={completed.returncode} "
        f"diagnostics={args.out} contentHash={result['contentHash']}",
        file=sys.stderr,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
