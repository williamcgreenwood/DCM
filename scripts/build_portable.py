#!/usr/bin/env python3
"""Wrapper: python scripts/build_portable.py -> python -m dcm.release"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "artifacts" / "dcm_v6_workstream_ab"))

from dcm.release import main

if __name__ == "__main__":
    raise SystemExit(main())
