from dcm.ingest.outlier import parse_outlier_payload
from dcm.learning.outlier_patterns import summarize_leg_segments, validate_observation
from dcm.selection.preselection import assess_preselection

def test_outlier_requires_explicit_target_book_modifier_and_side():
    payload = {"props": [{"outcome": {"leagueId": "NCAAFB", "eventId": "e", "playerId": "p", "outcomeId": "o", "proposition": "Receiving Yards", "line": 21.5, "position": "UNDER", "active": True, "bookOdds": {"PRIZEPICKS": {"odds": -120, "identifier": {"bookProps": {"odds_type": "standard", "outcomeAlias": "u-21.5"}}}}}}]}
    parsed = parse_outlier_payload(payload)
    assert parsed is not None
    assert parsed[1][0]["side"] == "LESS"
    assert parsed[1][0]["modifier"] == "STANDARD"

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

def test_pattern_analysis_excludes_slips_from_independent_leg_rate():
    rows = [{"entryUnit": "LEG", "result": "WIN", "market": "rec_yds"}, {"entryUnit": "LEG", "result": "LOSS", "market": "rec_yds"}, {"entryUnit": "SLIP", "slipId": "x", "result": "WIN", "market": "rec_yds"}]
    summary = summarize_leg_segments(rows, by=("market",), minimum_n=2)
    assert len(summary) == 1 and summary[0].n == 2
    valid, missing = validate_observation({"observationId": "x", "decisionCutoff": "c", "projectionId": "p", "line": 1.5, "side": "MORE", "modifier": "GOBLIN", "targetBook": "PRIZEPICKS", "selected": False, "selectionState": "EXCLUDED_GOBLIN"})
    assert valid is False and "GOBLIN_SELECTION_FORBIDDEN" in missing