from dcm.ingest.outlier import parse_outlier_payload
from dcm.cfb.reports import cfb_top100_row
from dcm.learning.outlier_patterns import summarize_leg_segments, validate_observation
from dcm.research.funnel import build_legal_universe
from dcm.selection.preselection import assess_preselection, research_flags_from_snapshot


def test_outlier_requires_explicit_target_book_modifier_and_side():
    payload = {"props": [{"outcome": {"leagueId": "NCAAFB", "eventId": "e", "playerId": "p", "outcomeId": "o", "proposition": "Receiving Yards", "line": 21.5, "position": "UNDER", "active": True, "bookOdds": {"PRIZEPICKS": {"odds": -120, "identifier": {"bookProps": {"odds_type": "standard", "outcomeAlias": "u-21.5"}}}}}}]}
    parsed = parse_outlier_payload(payload)
    assert parsed is not None
    assert parsed[1][0]["side"] == "LESS"
    assert parsed[1][0]["modifier"] == "STANDARD"
    assert parsed[1][0]["allowedWagerTypes"] == ["LESS"]
    assert parsed[1][0]["status"] == "pre_game"


def test_outlier_never_invents_lower_when_only_higher_is_captured():
    payload = {"props": [{"outcome": {"leagueId": "NCAAFB", "eventId": "e", "playerId": "p", "outcomeId": "o", "proposition": "Receptions", "line": 1.5, "position": "OVER", "active": True, "bookOdds": {"PRIZEPICKS": {"odds": "-120", "identifier": {"bookProps": {"odds_type": "standard", "outcomeAlias": "o-1.5"}}}}}}]}
    parsed = parse_outlier_payload(payload)
    row = parsed[1][0]
    assert row["offeredHigher"] is True and row["offeredLower"] is False
    assert row["allowedWagerTypes"] == ["MORE"]


def test_outlier_side_conflict_fails_closed():
    payload = {"props": [{"outcome": {"leagueId": "NCAAFB", "eventId": "e", "playerId": "p", "outcomeId": "o", "proposition": "Receptions", "line": 1.5, "position": "UNDER", "active": True, "bookOdds": {"PRIZEPICKS": {"odds": "-120", "identifier": {"bookProps": {"odds_type": "standard", "outcomeAlias": "o-1.5"}}}}}}]}
    parsed = parse_outlier_payload(payload)
    row = parsed[1][0]
    assert row["side"] == "UNKNOWN" and row["sideConflict"] is True
    assert row["offeredHigher"] is False and row["offeredLower"] is False


def test_outlier_target_book_can_be_explicitly_changed():
    payload = {"targetBook": "DRAFTKINGS", "props": [{"outcome": {"leagueId": "NCAAFB", "eventId": "e", "playerId": "p", "outcomeId": "o", "proposition": "Receptions", "line": 1.5, "position": "OVER", "active": True, "bookOdds": {"DRAFTKINGS": {"odds": "-115", "identifier": {"bookProps": {"odds_type": "standard", "outcomeAlias": "o-1.5"}}}}}}]}
    parsed = parse_outlier_payload(payload)
    row = parsed[1][0]
    assert row["targetBook"] == "DRAFTKINGS" and row["targetBookOfferPresent"] is True


def test_outlier_does_not_assert_period_when_overtime_definition_is_absent():
    parsed = parse_outlier_payload({"props": [{"outcome": {"leagueId": "NCAAFB", "eventId": "e", "playerId": "p", "outcomeId": "o", "proposition": "Receptions", "line": 1.5, "position": "OVER", "active": True, "bookOdds": {"PRIZEPICKS": {"odds": -120, "identifier": {"bookProps": {"odds_type": "standard", "outcomeAlias": "o-1.5"}}}}}}]})
    assert parsed is not None and parsed[1][0]["period"] == "UNKNOWN"


def test_outlier_missing_target_book_fails_closed_not_standard():
    parsed = parse_outlier_payload({"props": [{"outcome": {"leagueId": "NCAAFB", "eventId": "e", "playerId": "p", "outcomeId": "o", "proposition": "Receiving Yards", "line": 21.5, "position": "UNDER"}}]})
    assert parsed is not None and parsed[1][0]["modifier"] == "OTHER"


def test_preselection_routes_close_line_to_targeted_research_and_goblin_is_terminal():
    close = assess_preselection(offered_line=50, projected_mean=51, projected_stddev=10, minimum_margin_sigma=.25, research={}, explicit_side="MORE")
    assert close.state == "RESEARCH_REQUIRED_LINE_PROXIMITY" and close.may_select is False
    goblin = assess_preselection(offered_line=50, projected_mean=70, projected_stddev=10, minimum_margin_sigma=.25, research={}, explicit_side="MORE", modifier="GOBLIN")
    assert goblin.state == "EXCLUDED_GOBLIN"


def test_preselection_needs_player_and_matchup_research_after_robust_margin():
    result = assess_preselection(offered_line=50, projected_mean=60, projected_stddev=10, minimum_margin_sigma=.25, research={}, explicit_side="MORE")
    assert result.state == "RESEARCH_REQUIRED_TARGETED" and "matchup" in result.missing_research


def test_snapshot_projection_requires_canonical_scopes_and_support():
    flags = research_flags_from_snapshot(
        {
            "status": "ACTIVE",
            "role": "WR",
            "scopes_used": ["SUBJECT", "COUNTERPARTY"],
            "evidence_hashes": ["claim"],
            "availabilityMixture": {"active": 1.0},
            "opportunity": {"support_n": 4},
            "efficiency": {"support_n": 4},
            "layers": {"counterparty": {"counterpartyId": "opp"}},
        },
        {"line": 1.5, "marketDefinitionId": "m"},
    )
    assert all(flags.values())


def test_funnel_does_not_let_missing_target_row_hide_standard_outlier_offer():
    rows = [
        {
            "projectionId": "missing", "league": "CFB", "eventId": "e", "playerId": "p", "market": "receptions",
            "line": 1.5, "modifier": "OTHER", "targetBook": "PRIZEPICKS", "targetBookOfferPresent": False,
            "status": "pre_game", "boardId": "FULL_GAME", "allowedWagerTypes": ["MORE"], "offeredHigher": True,
        },
        {
            "projectionId": "standard", "league": "CFB", "eventId": "e", "playerId": "p", "market": "receptions",
            "line": 1.5, "modifier": "STANDARD", "targetBook": "PRIZEPICKS", "targetBookOfferPresent": True,
            "status": "pre_game", "boardId": "FULL_GAME", "allowedWagerTypes": ["MORE"], "offeredHigher": True,
        },
    ]
    gate = build_legal_universe(rows)
    assert [r["projectionId"] for r in gate["legalRows"]] == ["standard"]


def test_funnel_flattens_outlier_side_lists_when_same_standard_line_has_both_outcomes():
    rows = [
        {
            "projectionId": "under", "league": "CFB", "eventId": "e", "playerId": "p", "market": "receptions",
            "line": 1.5, "modifier": "STANDARD", "targetBook": "PRIZEPICKS", "targetBookOfferPresent": True,
            "status": "pre_game", "boardId": "FULL_GAME", "allowedWagerTypes": ["LESS"], "offeredLower": True,
        },
        {
            "projectionId": "over", "league": "CFB", "eventId": "e", "playerId": "p", "market": "receptions",
            "line": 1.5, "modifier": "STANDARD", "targetBook": "PRIZEPICKS", "targetBookOfferPresent": True,
            "status": "pre_game", "boardId": "FULL_GAME", "allowedWagerTypes": ["MORE"], "offeredHigher": True,
        },
    ]
    gate = build_legal_universe(rows)
    assert len(gate["legalRows"]) == 1
    assert gate["legalRows"][0]["offeredHigher"] is True


def test_funnel_keeps_distinct_market_definitions_separate():
    rows = [
        {
            "projectionId": "m1", "league": "CFB", "eventId": "e", "playerId": "p", "market": "receptions",
            "marketDefinition": "REC_REG", "line": 1.5, "modifier": "STANDARD", "targetBook": "PRIZEPICKS",
            "targetBookOfferPresent": True, "status": "pre_game", "boardId": "FULL_GAME",
            "allowedWagerTypes": ["MORE"], "offeredHigher": True,
        },
        {
            "projectionId": "m2", "league": "CFB", "eventId": "e", "playerId": "p", "market": "receptions",
            "marketDefinition": "REC_ALT", "line": 1.5, "modifier": "STANDARD", "targetBook": "PRIZEPICKS",
            "targetBookOfferPresent": True, "status": "pre_game", "boardId": "FULL_GAME",
            "allowedWagerTypes": ["MORE"], "offeredHigher": True,
        },
    ]
    gate = build_legal_universe(rows)
    assert gate["sameLineRows"] == 2
    assert len(gate["legalRows"]) == 1
    assert gate["altLineCount"] == 1


def test_cfb_report_retains_outlier_offer_evidence_and_hold_state():
    row = cfb_top100_row(
        {
            "row": {
                "projectionId": "x", "sourceFormat": "OUTLIER", "marketDefinition": "m",
                "sourceBook": "OUTLIER_BET", "targetBook": "PRIZEPICKS",
                "targetBookOfferPresent": True, "targetBookOdds": -120,
                "targetBookDecimalOdds": 1.83, "outlierOrf": 0.8,
                "outlierOrfScore": 0.9, "outlierHitRates": {"last10": 0.7},
                "line": 1.5, "offeredHigher": True, "offeredLower": False,
                "sideConflict": False,
            },
            "modeledPlayable": False,
            "preselection": {"state": "RESEARCH_REQUIRED_TARGETED"},
            "preselectionPolicy": {"version": "OUTLIER_PRESELECTION_V1"},
            "outlierPreselectionHold": True,
        },
        rank=1,
    )
    assert row["target_book_odds"] == -120
    assert row["outlier_preselection_hold"] is True


def test_pattern_analysis_excludes_slips_from_independent_leg_rate():
    rows = [{"entryUnit": "LEG", "result": "WIN", "market": "rec_yds"}, {"entryUnit": "LEG", "result": "LOSS", "market": "rec_yds"}, {"entryUnit": "SLIP", "slipId": "x", "result": "WIN", "market": "rec_yds"}]
    summary = summarize_leg_segments(rows, by=("market",), minimum_n=2)
    assert len(summary) == 1 and summary[0].n == 2
    valid, missing = validate_observation({"observationId": "x", "decisionCutoff": "c", "projectionId": "p", "line": 1.5, "side": "MORE", "modifier": "GOBLIN", "targetBook": "PRIZEPICKS", "selected": False, "selectionState": "EXCLUDED_GOBLIN"})
    assert valid is False and "GOBLIN_SELECTION_FORBIDDEN" in missing
