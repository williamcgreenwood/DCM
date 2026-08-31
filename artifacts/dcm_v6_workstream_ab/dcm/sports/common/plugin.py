"""Universal sport plugin contract plus exact league/market capability gates."""
from __future__ import annotations

from dataclasses import dataclass

PRODUCTION = "PRODUCTION_SUPPORTED"
SHADOW = "SHADOW_SUPPORTED"
RESEARCH = "RESEARCH_ONLY"
UNSUPPORTED = "UNSUPPORTED_FAIL_CLOSED"


@dataclass(frozen=True)
class SportPluginManifest:
    sport_family_id: str
    plugin_version: str
    leagues: tuple[str, ...]
    path_unit: str
    opportunity_units: tuple[str, ...]
    production_state: str
    known_unsupported: tuple[str, ...] = ()
    test_ids: tuple[str, ...] = ()


REGISTRY: dict[str, SportPluginManifest] = {}
CAPABILITIES: dict[tuple[str, str, str], str] = {}


def register(m: SportPluginManifest) -> None:
    REGISTRY[m.sport_family_id] = m


def lookup(family: str) -> SportPluginManifest | None:
    return REGISTRY.get(family)


def _cap(family: str, league: str, markets: tuple[str, ...], state: str) -> None:
    for market in markets:
        CAPABILITIES[(family, league, market)] = state


_cap("basketball", "NBA", ("pts", "reb", "ast", "pra", "pr", "pa", "ra", "3pm", "3pa", "tpa", "fgm", "fga", "fg_made", "fg_att", "2pm", "2pa", "twopm", "twopa", "fg2m", "ftm", "fta", "tov", "to", "oreb", "stl", "blk", "blk_stl", "qtrs_w_3plus_pts"), PRODUCTION)
_cap("basketball", "WNBA", ("pts", "reb", "ast", "pra", "pr", "pa", "ra", "3pm", "3pa", "tpa", "fgm", "fga", "fg_made", "fg_att", "2pm", "2pa", "twopm", "twopa", "fg2m", "ftm", "fta", "tov", "to", "oreb", "stl", "blk", "blk_stl", "qtrs_w_3plus_pts"), PRODUCTION)
_cap("gridiron", "NFL", ("pass_yds", "rush_yds", "rec_yds", "receptions", "pass_rush_yds", "rush_rec_yds"), PRODUCTION)
_cap("gridiron", "CFB", ("pass_yds", "rush_yds", "rec_yds", "receptions", "pass_rush_yds", "rush_rec_yds"), PRODUCTION)
_cap("gridiron", "NFLP", ("pass_yds", "rush_yds", "rec_yds", "receptions"), RESEARCH)
_cap("gridiron", "CFL", ("pass_yds", "rush_yds", "rec_yds", "receptions", "pass_rush_yds", "rush_rec_yds"), UNSUPPORTED)
_cap("baseball", "MLB", ("h", "tb", "k", "hits_runs_rbi"), SHADOW)
_cap("baseball", "NPB", ("h", "tb", "k", "hits_runs_rbi"), UNSUPPORTED)
_cap("baseball", "KBO", ("h", "tb", "k", "hits_runs_rbi"), UNSUPPORTED)
_cap("combat", "UFC", ("sig_strikes", "takedowns", "fight_time"), RESEARCH)


def selection_state(family: str, league: str, market: str) -> str:
    return CAPABILITIES.get((family, league, market), UNSUPPORTED)


register(SportPluginManifest("gridiron", "1.2.0", ("NFL", "CFB", "NFLP", "CFL", "UFL"), "play/snap/route/target/dropback", ("snaps", "routes", "targets", "dropbacks", "carries"), PRODUCTION, known_unsupported=("CFL_REBOOT", "NFLP_PRESEASON", "DEF_TACKLES_PLAYABLE", "KICKING_PLAYABLE"), test_ids=("WSAB_BASELINE_46", "gridiron_p7_e2e"),))
register(SportPluginManifest("basketball", "1.1.0", ("NBA", "WNBA"), "possession/stint/minute", ("minutes", "possessions"), PRODUCTION, test_ids=("basketball_minimal_e2e",)))
register(SportPluginManifest("baseball", "0.2.0", ("MLB", "NPB"), "PA/pitch/base-out", ("PA", "BF"), SHADOW))
register(SportPluginManifest("combat", "0.1.0", ("UFC", "BOXING"), "fight_second/round", ("fight_seconds",), RESEARCH, known_unsupported=("BOXING_AS_UFC",)))
for fam, unit, leagues in (
    ("soccer", "minute/action", ("EPL", "MLS", "UEFA")), ("hockey", "shift/TOI", ("NHL",)),
    ("racket", "point/game/set", ("ATP", "WTA")), ("cricket", "ball/over/innings", ("T20", "ODI", "TEST")),
    ("golf", "hole/stroke", ("PGA", "LPGA")), ("esports", "title+patch+map", ("CS2", "LOL", "VAL")),
    ("lacrosse", "possession", ("PLL", "NLL")), ("handball", "possession", ("HBL",)),
    ("australian_rules", "disposal", ("AFL",)), ("rugby", "phase/ruck", ("RU", "RL")),
    ("volleyball", "rally", ("INDOOR", "BEACH")), ("motorsport", "lap", ("F1", "NASCAR")),
):
    register(SportPluginManifest(fam, "0.0.0", leagues, unit, (unit,), UNSUPPORTED))
