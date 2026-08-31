"""Versioned basketball market derivation: identities, fail-closed unknown, no fuzzy match."""
from __future__ import annotations

import pytest

from dcm.model.market_derive import UnknownMarketError, derive_market
from dcm.model.worlds import as_primitive_ledger, sample_basketball, value_from_stats


def test_pra_always_pts_plus_reb_plus_ast_on_ledger():
    rng = __import__("random").Random(11)
    for _ in range(64):
        w = sample_basketball(rng, 32.0)
        ledger = as_primitive_ledger(w)
        pra = derive_market(ledger, "pra")
        assert pra == ledger["pts"] + ledger["reb"] + ledger["ast"]
        assert pra == value_from_stats("pra", w)
        # Even if a precomputed pra field is corrupted, derivation uses primitives.
        w["pra"] = 9999.0
        assert derive_market(w, "PRA") == w["pts"] + w["reb"] + w["ast"]


def test_two_pa_two_pm_identities():
    rng = __import__("random").Random(12)
    for _ in range(48):
        w = sample_basketball(rng, 30.0)
        ledger = as_primitive_ledger(w)
        assert ledger["twopa"] == ledger["fga"] - ledger["three_pa"]
        assert ledger["twopm"] == ledger["fgm"] - ledger["three_pm"]
        assert derive_market(ledger, "2PA") == ledger["twopa"]
        assert derive_market(ledger, "2PM") == ledger["twopm"]
        assert derive_market(ledger, "3PTA") == ledger["tpa"]
        assert derive_market(ledger, "3PTM") == ledger["tpm"]
        assert derive_market(ledger, "FGM") == ledger["fgm"]
        assert derive_market(ledger, "FGA") == ledger["fga"]
        assert derive_market(ledger, "Pts+Rebs") == ledger["pts"] + ledger["reb"]
        assert derive_market(ledger, "Pts+Asts") == ledger["pts"] + ledger["ast"]
        assert derive_market(ledger, "Rebs+Asts") == ledger["reb"] + ledger["ast"]
        assert derive_market(ledger, "Blks+Stls") == ledger["blk"] + ledger["stl"]
        assert derive_market(ledger, "Turnovers") == ledger["tov"]
        assert derive_market(ledger, "OREB") == ledger["oreb"]
        assert derive_market(ledger, "Steals") == ledger["stl"]
        assert derive_market(ledger, "FTM") == ledger["ftm"]
        assert derive_market(ledger, "FTA") == ledger["fta"]


def test_unknown_market_fails_closed_no_fuzzy():
    rng = __import__("random").Random(3)
    w = sample_basketball(rng, 28.0)
    with pytest.raises(UnknownMarketError) as ei:
        derive_market(w, "pointz")
    assert ei.value.blocker == "UNVERIFIED_MARKET_DEFINITION"
    with pytest.raises(UnknownMarketError):
        derive_market(w, "pts_almost")
    with pytest.raises(UnknownMarketError):
        value_from_stats("unknown_stat", w)


def test_fantasy_score_fails_closed_without_registered_definition():
    rng = __import__("random").Random(4)
    w = sample_basketball(rng, 28.0)
    with pytest.raises(UnknownMarketError) as ei:
        derive_market(w, "fantasy")
    assert ei.value.blocker == "UNVERIFIED_MARKET_DEFINITION"


def test_ledger_contains_required_primitive_keys():
    rng = __import__("random").Random(5)
    w = sample_basketball(rng, 33.0)
    ledger = as_primitive_ledger(w)
    for key in (
        "minutes", "fgm", "fga", "tpm", "three_pm", "tpa", "three_pa",
        "twopm", "twopa", "ftm", "fta", "oreb", "dreb", "reb", "ast",
        "stl", "blk", "tov", "pf", "pts",
    ):
        assert key in ledger
    # reb-only heuristic
    slim = {"minutes": 30, "fgm": 5, "fga": 12, "tpm": 1, "tpa": 4, "twopm": 4, "twopa": 8,
            "ftm": 2, "fta": 2, "reb": 7, "ast": 3, "stl": 1, "blk": 0, "tov": 2, "pts": 13}
    filled = as_primitive_ledger(slim)
    assert filled["reb"] == filled["oreb"] + filled["dreb"]
