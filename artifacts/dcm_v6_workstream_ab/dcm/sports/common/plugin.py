"""Universal sport plugin contract. Families register; unknown sports fail closed."""

from __future__ import annotations

from dataclasses import dataclass, field


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


def register(m: SportPluginManifest) -> None:
    REGISTRY[m.sport_family_id] = m


def lookup(family: str) -> SportPluginManifest | None:
    return REGISTRY.get(family)


def selection_state(family: str, league: str, market: str) -> str:
    m = REGISTRY.get(family)
    if m is None:
        return UNSUPPORTED
    if league not in m.leagues:
        return UNSUPPORTED
    if market in m.known_unsupported:
        return UNSUPPORTED
    return m.production_state


register(SportPluginManifest(
    "gridiron", "1.0.0", ("NFL", "CFB", "NFLP", "CFL", "UFL"),
    "play/snap/route/target/dropback",
    ("snaps", "routes", "targets", "dropbacks", "carries"),
    PRODUCTION,
    known_unsupported=("CFL_REBOOT",),
    test_ids=("WSAB_BASELINE_46",),
))
register(SportPluginManifest(
    "basketball", "1.0.0", ("NBA", "WNBA", "NCAAM", "NCAAW", "GLEAGUE"),
    "possession/stint/minute",
    ("minutes",),
    PRODUCTION,
    test_ids=("basketball_minimal_e2e",),
))
register(SportPluginManifest(
    "baseball", "0.1.0", ("MLB", "NPB", "KBO", "CPBL", "LMB"),
    "PA/pitch/base-out",
    ("PA", "BF"),
    SHADOW,
))
register(SportPluginManifest(
    "combat", "0.1.0", ("UFC", "BOXING"),
    "fight_second/round",
    ("fight_seconds",),
    RESEARCH,
    known_unsupported=("BOXING_AS_UFC",),
))
for fam, unit, leagues in (
    ("soccer", "minute/action", ("EPL", "MLS", "UEFA")),
    ("hockey", "shift/TOI", ("NHL",)),
    ("racket", "point/game/set", ("ATP", "WTA")),
    ("cricket", "ball/over/innings", ("T20", "ODI", "TEST")),
    ("golf", "hole/stroke", ("PGA", "LPGA")),
    ("esports", "title+patch+map", ("CS2", "LOL", "VAL")),
    ("lacrosse", "possession", ("PLL", "NLL")),
    ("handball", "possession", ("HBL",)),
    ("australian_rules", "disposal", ("AFL",)),
    ("rugby", "phase/ruck", ("RU", "RL")),
    ("volleyball", "rally", ("INDOOR", "BEACH")),
    ("motorsport", "lap", ("F1", "NASCAR")),
):
    register(SportPluginManifest(fam, "0.0.0", leagues, unit, (unit,), UNSUPPORTED))
