"""Role-conditional efficiency. Does not invent opportunity."""

from __future__ import annotations

from dcm.contracts.immutables import FrozenMap
from dcm.contracts.schemas import EfficiencyState


EFF_VERSION = "FOOTBALL_EFF_V1_2026-08-27"


def player_efficiency(rates: dict[str, float]) -> EfficiencyState:
    cleaned = {k: float(v) for k, v in rates.items()}
    return EfficiencyState(rates=FrozenMap(cleaned), definition_version=EFF_VERSION)


def apply_efficiency(opportunity: dict[str, float], rates: dict[str, float], role: str) -> dict[str, float]:
    """Map opportunity × rates to primitive outcomes. Bounds are applied here so
    a generated world starts legal; conservation still audits the ledger.
    """
    pass_att = opportunity.get("pass_att", 0.0)
    cmp_rate = min(max(rates.get("cmp_rate", 0.0), 0.0), 1.0)
    pass_cmp = min(pass_att, round(pass_att * cmp_rate)) if pass_att else 0.0
    ypa = max(rates.get("ypa", 0.0), 0.0)
    pass_yds = pass_att * ypa
    pass_td = pass_att * max(rates.get("pass_td_rate", 0.0), 0.0)
    interceptions = pass_att * max(rates.get("int_rate", 0.0), 0.0)
    sacks_taken = opportunity.get("dropbacks", 0.0) - opportunity.get("pass_att", 0.0) - opportunity.get("scramble_att", 0.0)
    sacks_taken = max(sacks_taken, 0.0)
    sack_yds = sacks_taken * max(rates.get("sack_yds_per", 0.0), 0.0)

    rush_att = opportunity.get("rush_att", 0.0)
    ypc = rates.get("ypc", 0.0)
    scramble_yds = opportunity.get("scramble_att", 0.0) * max(rates.get("scramble_ypc", ypc), 0.0)
    designed_yds = opportunity.get("designed_rush_att", 0.0) * max(ypc, 0.0)
    rush_yds = designed_yds + scramble_yds
    rush_td = rush_att * max(rates.get("rush_td_rate", 0.0), 0.0)

    targets = opportunity.get("targets", 0.0)
    catch_rate = min(max(rates.get("catch_rate", 0.0), 0.0), 1.0)
    receptions = min(targets, round(targets * catch_rate)) if targets else 0.0
    ypt = max(rates.get("ypt", 0.0), 0.0)
    rec_yds = targets * ypt
    rec_td = targets * max(rates.get("rec_td_rate", 0.0), 0.0)

    fg_att = opportunity.get("fg_att", 0.0)
    fg_made = min(fg_att, round(fg_att * min(max(rates.get("fg_rate", 0.0), 0.0), 1.0))) if fg_att else 0.0
    xp_att = opportunity.get("xp_att", 0.0)
    xp_made = min(xp_att, round(xp_att * min(max(rates.get("xp_rate", 0.0), 0.0), 1.0))) if xp_att else 0.0

    out = {
        "off_snaps": opportunity.get("off_snaps", 0.0),
        "routes": opportunity.get("routes", 0.0),
        "targets": targets,
        "dropbacks": opportunity.get("dropbacks", 0.0),
        "pass_att": pass_att,
        "designed_rush_att": opportunity.get("designed_rush_att", 0.0),
        "scramble_att": opportunity.get("scramble_att", 0.0),
        "rush_att": rush_att,
        "rz_att": opportunity.get("rz_att", 0.0),
        "pass_cmp": pass_cmp,
        "pass_yds": pass_yds,
        "pass_td": pass_td,
        "interceptions": interceptions,
        "sacks_taken": sacks_taken,
        "sack_yds": sack_yds,
        "scramble_yds": scramble_yds,
        "rush_yds": rush_yds,
        "rush_td": rush_td,
        "receptions": receptions,
        "rec_yds": rec_yds,
        "rec_td": rec_td,
        "fg_att": fg_att,
        "fg_made": fg_made,
        "xp_att": xp_att,
        "xp_made": xp_made,
        "punt_att": opportunity.get("punt_att", 0.0),
        "def_tackles": rates.get("def_tackles", 0.0) if role in {"DEF", "LB", "DL", "DB", "IDP"} else 0.0,
        "def_sacks": rates.get("def_sacks", 0.0) if role in {"DEF", "LB", "DL", "DB", "IDP"} else 0.0,
    }
    return out
