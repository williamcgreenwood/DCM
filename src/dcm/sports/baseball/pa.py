"""MLB PA / base-out conservation. SHADOW_SUPPORTED — not a production promotion."""

from __future__ import annotations

from typing import Any


PRODUCTION_STATE = "SHADOW_SUPPORTED"


def conservation(stats: dict[str, float]) -> list[dict[str, Any]]:
    h = stats["1B"] + stats["2B"] + stats["3B"] + stats["HR"]
    tb = 1 * stats["1B"] + 2 * stats["2B"] + 3 * stats["3B"] + 4 * stats["HR"]
    ab = stats["PA"] - stats["BB"] - stats["HBP"] - stats["SF"] - stats["SH"]
    checks = [
        ("H", stats["H"], h),
        ("TB", stats["TB"], tb),
        ("AB", stats["AB"], ab),
        ("H_LE_AB", stats["H"], stats["AB"] if stats["H"] <= stats["AB"] + 1e-9 else stats["H"] + 1),
        ("HR_LE_H", stats["HR"], stats["H"] if stats["HR"] <= stats["H"] + 1e-9 else stats["HR"] + 1),
        ("SO_LE_AB", stats["SO"], stats["AB"] if stats["SO"] <= stats["AB"] + 1e-9 else stats["SO"] + 1),
    ]
    out = []
    for rule, obs, exp in checks:
        passed = abs(obs - exp) < 1e-9 if rule in {"H", "TB", "AB"} else obs <= exp + 1e-9
        if rule not in {"H", "TB", "AB"}:
            passed = True if "LE" in rule and obs <= (
                stats["AB"] if "AB" in rule else stats["H"]
            ) + 1e-9 else passed
        out.append({"rule_id": rule, "passed": passed, "observed": obs, "expected": exp, "residual": obs - exp})
    # rewrite LE checks cleanly
    out = [
        {"rule_id": "H", "passed": abs(stats["H"] - h) < 1e-9, "observed": stats["H"], "expected": h},
        {"rule_id": "TB", "passed": abs(stats["TB"] - tb) < 1e-9, "observed": stats["TB"], "expected": tb},
        {"rule_id": "AB", "passed": abs(stats["AB"] - ab) < 1e-9, "observed": stats["AB"], "expected": ab},
        {"rule_id": "H_LE_AB", "passed": stats["H"] <= stats["AB"] + 1e-9, "observed": stats["H"], "expected": stats["AB"]},
        {"rule_id": "HR_LE_H", "passed": stats["HR"] <= stats["H"] + 1e-9, "observed": stats["HR"], "expected": stats["H"]},
        {"rule_id": "SO_LE_AB", "passed": stats["SO"] <= stats["AB"] + 1e-9, "observed": stats["SO"], "expected": stats["AB"]},
    ]
    return out


def validate(stats: dict[str, float]) -> None:
    failed = [c["rule_id"] for c in conservation(stats) if not c["passed"]]
    if failed:
        raise RuntimeError(f"PRIMITIVE_CONSERVATION_FAILURE: {failed}")
