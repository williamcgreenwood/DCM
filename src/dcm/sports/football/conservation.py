"""Football conservation rules. Only physically true identities are enforced."""

from __future__ import annotations

from dcm.contracts.schemas import ConservationRule, InvariantResult, PrimitiveStatLedger
from dcm.sports.football.registry import CFB_LEAGUE, NFL_LEAGUE, NFLP_LEAGUE, SPORT


RULE_VERSION = "FOOTBALL_CONSERVATION_V1_2026-08-27"
TOL = 1e-9


def _rule(rule_id: str, league: str, rule_type: str, expression: str, scope: str) -> ConservationRule:
    return ConservationRule(
        rule_id=rule_id,
        sport=SPORT,
        league=league,
        rule_type=rule_type,
        expression=expression,
        tolerance=TOL,
        rule_version=RULE_VERSION,
        scope=scope,
    )


def football_conservation_rules(*leagues: str) -> tuple[ConservationRule, ...]:
    if not leagues:
        leagues = (NFL_LEAGUE, CFB_LEAGUE, NFLP_LEAGUE)
    rows = []
    for league in leagues:
        rows.extend([
            _rule(f"{league}_RUSH_ATT_SPLIT", league, "COMPONENT_IDENTITY",
                  "rush_att = designed_rush_att + scramble_att", "PLAYER_AND_TEAM"),
            _rule(f"{league}_DROPBACKS", league, "COMPONENT_IDENTITY",
                  "dropbacks = pass_att + sacks_taken + scramble_att", "PLAYER_AND_TEAM"),
            _rule(f"{league}_TEAM_PLAYS", league, "SUM_EQUALS",
                  "team_off_plays = team_pass_att + team_rush_att + team_sacks_taken", "TEAM"),
            _rule(f"{league}_CMP_LE_ATT", league, "BOUND",
                  "pass_cmp <= pass_att", "PLAYER"),
            _rule(f"{league}_REC_LE_TGT", league, "BOUND",
                  "receptions <= targets", "PLAYER"),
            _rule(f"{league}_TGT_LE_ROUTES", league, "BOUND",
                  "targets <= routes when routes present", "PLAYER"),
            _rule(f"{league}_FG_MADE_LE_ATT", league, "BOUND",
                  "fg_made <= fg_att", "PLAYER"),
            _rule(f"{league}_XP_MADE_LE_ATT", league, "BOUND",
                  "xp_made <= xp_att", "PLAYER"),
            _rule(f"{league}_TEAM_TARGETS", league, "RESOURCE_ALLOCATION",
                  "sum(player.targets) = team_targets", "TEAM"),
            _rule(f"{league}_TEAM_REC_YDS", league, "SUM_EQUALS",
                  "sum(player.rec_yds) = team_rec_yds", "TEAM"),
            _rule(f"{league}_PASS_REC_RECONCILE", league, "SUM_EQUALS",
                  "team_pass_yds = team_rec_yds under NO_LATERAL definition", "TEAM"),
            _rule(f"{league}_NO_SNAP_EQ_PLAYS", league, "LOGICAL",
                  "sum(player.off_snaps) is NOT required to equal team_off_plays", "TEAM"),
        ])
    return tuple(rows)


def _get(values: dict[str, float], key: str, default: float = 0.0) -> float:
    return float(values.get(key, default))


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol + 1e-9


def evaluate_football_conservation(ledger: PrimitiveStatLedger) -> tuple[InvariantResult, ...]:
    results: list[InvariantResult] = []
    players = {e.entity_id for e in ledger.entries if e.entity_type == "PLAYER"}
    teams = {e.team_id for e in ledger.entries if e.entity_type == "TEAM"}

    for player_id in players:
        v = ledger.values_for(player_id)
        rush_att = _get(v, "rush_att")
        rush_split = _get(v, "designed_rush_att") + _get(v, "scramble_att")
        results.append(InvariantResult(
            rule_id="RUSH_ATT_SPLIT",
            passed=_close(rush_att, rush_split),
            observed=rush_att,
            expected=rush_split,
            residual=rush_att - rush_split,
            message=f"{player_id} rush_att identity",
        ))
        dropbacks = _get(v, "dropbacks")
        drop_expected = _get(v, "pass_att") + _get(v, "sacks_taken") + _get(v, "scramble_att")
        results.append(InvariantResult(
            rule_id="DROPBACKS",
            passed=_close(dropbacks, drop_expected),
            observed=dropbacks,
            expected=drop_expected,
            residual=dropbacks - drop_expected,
            message=f"{player_id} dropback identity",
        ))
        cmp_, att = _get(v, "pass_cmp"), _get(v, "pass_att")
        results.append(InvariantResult(
            rule_id="CMP_LE_ATT",
            passed=cmp_ <= att + TOL,
            observed=cmp_,
            expected=att,
            residual=max(0.0, cmp_ - att),
            message=f"{player_id} completions bound",
        ))
        rec, tgt = _get(v, "receptions"), _get(v, "targets")
        results.append(InvariantResult(
            rule_id="REC_LE_TGT",
            passed=rec <= tgt + TOL,
            observed=rec,
            expected=tgt,
            residual=max(0.0, rec - tgt),
            message=f"{player_id} receptions bound",
        ))
        routes = v.get("routes")
        if routes is not None:
            results.append(InvariantResult(
                rule_id="TGT_LE_ROUTES",
                passed=tgt <= float(routes) + TOL,
                observed=tgt,
                expected=float(routes),
                residual=max(0.0, tgt - float(routes)),
                message=f"{player_id} targets vs routes",
            ))
        results.append(InvariantResult(
            rule_id="FG_MADE_LE_ATT",
            passed=_get(v, "fg_made") <= _get(v, "fg_att") + TOL,
            observed=_get(v, "fg_made"),
            expected=_get(v, "fg_att"),
            residual=max(0.0, _get(v, "fg_made") - _get(v, "fg_att")),
            message=f"{player_id} FG bound",
        ))
        results.append(InvariantResult(
            rule_id="XP_MADE_LE_ATT",
            passed=_get(v, "xp_made") <= _get(v, "xp_att") + TOL,
            observed=_get(v, "xp_made"),
            expected=_get(v, "xp_att"),
            residual=max(0.0, _get(v, "xp_made") - _get(v, "xp_att")),
            message=f"{player_id} XP bound",
        ))

    for team_id in teams:
        tv = ledger.team_values(team_id)
        plays = _get(tv, "team_off_plays")
        plays_expected = _get(tv, "team_pass_att") + _get(tv, "team_rush_att") + _get(tv, "team_sacks_taken")
        results.append(InvariantResult(
            rule_id="TEAM_PLAYS",
            passed=_close(plays, plays_expected),
            observed=plays,
            expected=plays_expected,
            residual=plays - plays_expected,
            message=f"{team_id} play identity",
        ))
        player_ids = {e.entity_id for e in ledger.entries if e.entity_type == "PLAYER" and e.team_id == team_id}
        sum_tgt = sum(_get(ledger.values_for(p), "targets") for p in player_ids)
        results.append(InvariantResult(
            rule_id="TEAM_TARGETS",
            passed=_close(sum_tgt, _get(tv, "team_targets")),
            observed=sum_tgt,
            expected=_get(tv, "team_targets"),
            residual=sum_tgt - _get(tv, "team_targets"),
            message=f"{team_id} target allocation",
        ))
        sum_rec_yds = sum(_get(ledger.values_for(p), "rec_yds") for p in player_ids)
        results.append(InvariantResult(
            rule_id="TEAM_REC_YDS",
            passed=_close(sum_rec_yds, _get(tv, "team_rec_yds")),
            observed=sum_rec_yds,
            expected=_get(tv, "team_rec_yds"),
            residual=sum_rec_yds - _get(tv, "team_rec_yds"),
            message=f"{team_id} receiving yards sum",
        ))
        results.append(InvariantResult(
            rule_id="PASS_REC_RECONCILE",
            passed=_close(_get(tv, "team_pass_yds"), _get(tv, "team_rec_yds")),
            observed=_get(tv, "team_pass_yds"),
            expected=_get(tv, "team_rec_yds"),
            residual=_get(tv, "team_pass_yds") - _get(tv, "team_rec_yds"),
            message=f"{team_id} pass/rec yards under NO_LATERAL",
        ))
        # Explicit non-identity: snap occupancy is not a play count.
        snap_sum = sum(_get(ledger.values_for(p), "off_snaps") for p in player_ids)
        results.append(InvariantResult(
            rule_id="NO_SNAP_EQ_PLAYS",
            passed=True,
            observed=snap_sum,
            expected=plays,
            residual=snap_sum - plays,
            message=f"{team_id} snap occupancy ({snap_sum}) is allowed to differ from plays ({plays})",
        ))

    return tuple(results)


def conservation_passed(results: tuple[InvariantResult, ...]) -> bool:
    return all(r.passed for r in results)
