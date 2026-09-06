"""CFB guarded-execution eligibility for pure and mixed slates."""
from __future__ import annotations


def _cfb_execution(rows: list[dict]) -> bool:
    cfb_row_count = sum(
        1
        for r in rows
        if str(r.get("sportFamily") or "") == "gridiron"
        and str(r.get("league") or "").upper() in {"CFB", "CFB1H"}
    )
    leagues = {
        str(r.get("league") or "").upper()
        for r in rows
        if str(r.get("league") or "").strip()
    }
    return cfb_row_count > 0 and (
        cfb_row_count >= 1000
        or leagues <= {"CFB", "CFB1H"}
        or cfb_row_count >= max(100, (len(rows) + 1) // 2)
    )


def test_pure_cfb1h_board_enables_cfb_execution():
    rows = [{"sportFamily": "gridiron", "league": "CFB"} for _ in range(40)]
    rows += [{"sportFamily": "gridiron", "league": "CFB1H"} for _ in range(10)]
    assert _cfb_execution(rows) is True


def test_cfb_dominant_mixed_slate_enables_cfb_execution():
    rows = [{"sportFamily": "gridiron", "league": "CFB"} for _ in range(600)]
    rows += [{"sportFamily": "gridiron", "league": "CFL"} for _ in range(20)]
    rows += [{"sportFamily": "soccer", "league": "EPL1H"} for _ in range(4)]
    assert _cfb_execution(rows) is True


def test_cfl_only_does_not_enable_cfb_execution():
    rows = [{"sportFamily": "gridiron", "league": "CFL"} for _ in range(200)]
    assert _cfb_execution(rows) is False
