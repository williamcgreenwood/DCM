"""Shared accounting classification and pre-research disposition.

HAR → ACCOUNT EVERY PROP → IDENTITY → PRE-RESEARCH CLASSIFICATION → then
deep research is issued only for model-eligible (and opt-in shadow) rows.
"""
from __future__ import annotations

from typing import Any

from dcm.model.worlds import MARKET_FROM_STATS
from dcm.cfb.markets import ACTIVE_CFB_MARKETS
from dcm.sports.common.plugin import selection_state

SUPPORTED_FAMILIES = {"basketball", "gridiron", "baseball"}
PRODUCTION_LEAGUES = {"NBA", "WNBA", "NFL", "CFB"}
SHADOW_LEAGUES = {"MLB"}

BASKETBALL_MARKETS = {
    "pts", "reb", "ast", "pra", "pr", "pa", "ra",
    "3pm", "3pa", "tpa", "fgm", "fga", "fg_made", "fg_att",
    "2pm", "2pa", "twopm", "twopa", "fg2m",
    "ftm", "fta", "tov", "to", "oreb", "stl", "blk", "blk_stl",
    "qtrs_w_3plus_pts",
}
GRIDIRON_MARKETS = set(MARKET_FROM_STATS) | set(ACTIVE_CFB_MARKETS) | {
    "pass_yds", "rush_yds", "rec_yds", "receptions", "pass_rush_yds", "rush_rec_yds",
    "pass_att", "pass_cmp", "pass_td", "interceptions", "rush_att", "rush_td",
    "rec_td", "targets", "rush_rec_td", "pass_rush_td", "fg_made", "xp_made", "kicking_pts",
}
BASEBALL_MARKETS = {"h", "tb", "k", "hits_runs_rbi"}

SKIP_GOBLIN = "goblin"
SKIP_UNSUPPORTED_SPORT = "unsupported_sport"
SKIP_LIVE = "live_or_in_progress"
SKIP_SIDE = "side_unknown"
SKIP_MARKET = "unsupported_market"
SKIP_SHADOW = "shadow"
SKIP_UNRESOLVED = "unresolved_other"
DEEP_MODEL = "model_eligible"
DEEP_SHADOW = "shadow"

SKIP_CLASSES = (
    SKIP_GOBLIN,
    SKIP_UNSUPPORTED_SPORT,
    SKIP_LIVE,
    SKIP_SIDE,
    SKIP_MARKET,
    SKIP_SHADOW,
    SKIP_UNRESOLVED,
)


def _offered_sides_known(row: dict[str, Any]) -> bool:
    if row.get("offeredHigher") or row.get("offeredLower"):
        return True
    return False


def _is_live(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "unknown")
    return bool(row.get("isLive")) or status in {"in_progress", "suspended"}


def _unsupported_market(row: dict[str, Any]) -> bool:
    family = row.get("sportFamily") or ""
    market = row.get("market")
    if family == "basketball" and market not in BASKETBALL_MARKETS:
        return True
    if family == "gridiron" and market not in GRIDIRON_MARKETS:
        return True
    if family == "baseball" and market not in BASEBALL_MARKETS:
        return True
    return False


def accounting_classify(row: dict[str, Any]) -> tuple[str, str | None]:
    """Selection/accounting state. Goblins extracted then excluded; live stays MODELED+blocked."""
    if row.get("modifier") == "GOBLIN":
        return "EXCLUDED_GOBLIN", "GOBLIN_SELECTION_FORBIDDEN"
    if row.get("modifier") == "OTHER":
        return "UNRESOLVED", "MODIFIER_UNKNOWN"
    if row.get("side") == "UNKNOWN" and not row.get("offeredHigher") and not row.get("offeredLower"):
        return "UNRESOLVED", "OFFERED_SIDE_UNKNOWN"
    if not row.get("playerId"):
        return "UNRESOLVED", "PLAYER_ID_UNRESOLVED_NO_NAME_INFERENCE"
    if row.get("sportFamily") == "baseball" and row.get("market") == "hits_runs_rbi" and abs(float(row.get("line", 0)) - 0.5) < 1e-9:
        return "UNRESOLVED", "HALF_LINE_AVOID_BASEBALL_HRRBI_0_5"
    family = row.get("sportFamily") or ""
    cap = selection_state(family, row.get("league") or "", row.get("market") or "")
    if family not in SUPPORTED_FAMILIES or cap == "UNSUPPORTED_FAIL_CLOSED":
        return "UNSUPPORTED", "UNSUPPORTED_FAIL_CLOSED"
    if cap == "RESEARCH_ONLY":
        return "MODELED", "RESEARCH_ONLY_NOT_SELECTABLE"
    if cap == "SHADOW_SUPPORTED":
        return "MODELED", "SHADOW_SUPPORTED_NOT_SELECTABLE"
    status = str(row.get("status") or "unknown")
    if bool(row.get("isLive")) or status in {"in_progress", "suspended"}:
        return "MODELED", "LIVE_OR_IN_PROGRESS_NOT_PRODUCTION"
    if status not in {"pre_game", "unknown"}:
        return "MODELED", "UNKNOWN_STATUS_FAIL_CLOSED"
    if _unsupported_market(row):
        return "UNSUPPORTED", "UNSUPPORTED_FAIL_CLOSED"
    return "MODELED", None


def research_disposition(row: dict[str, Any], *, research_shadow: bool = False) -> tuple[bool, str]:
    """Return (deep_research?, class).

    Order matches the P0 contract:
    Goblin → unsupported sport → live → side unknown → unsupported market →
    shadow (opt-in) → model eligible.
    """
    if row.get("modifier") == "GOBLIN":
        return False, SKIP_GOBLIN

    family = str(row.get("sportFamily") or "")
    league = str(row.get("league") or "")
    cap = selection_state(family, league, str(row.get("market") or ""))

    production_or_shadow = league in PRODUCTION_LEAGUES or league in SHADOW_LEAGUES
    if family not in SUPPORTED_FAMILIES or not production_or_shadow or (
        cap == "UNSUPPORTED_FAIL_CLOSED" and league not in PRODUCTION_LEAGUES | SHADOW_LEAGUES
    ):
        return False, SKIP_UNSUPPORTED_SPORT

    if _is_live(row):
        return False, SKIP_LIVE

    if not _offered_sides_known(row):
        return False, SKIP_SIDE

    if cap == "UNSUPPORTED_FAIL_CLOSED" or _unsupported_market(row):
        return False, SKIP_MARKET

    if row.get("modifier") == "OTHER":
        return False, SKIP_UNRESOLVED
    if not row.get("playerId"):
        return False, SKIP_UNRESOLVED
    if family == "baseball" and row.get("market") == "hits_runs_rbi" and abs(float(row.get("line", 0)) - 0.5) < 1e-9:
        return False, SKIP_UNRESOLVED

    if cap == "SHADOW_SUPPORTED" or league in SHADOW_LEAGUES:
        if research_shadow:
            return True, DEEP_SHADOW
        return False, SKIP_SHADOW

    # pre_game or unknown (synthetic/legacy) is model-eligible; other statuses already live-gated
    return True, DEEP_MODEL


def classify_rows(
    rows: list[dict[str, Any]],
    *,
    research_shadow: bool = False,
) -> dict[str, Any]:
    skipped = {k: 0 for k in SKIP_CLASSES}
    skipped["model_eligible"] = 0
    skipped["shadow_researched"] = 0
    eligible: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for row in rows:
        acc_state, acc_blocker = accounting_classify(row)
        deep, klass = research_disposition(row, research_shadow=research_shadow)
        if deep:
            eligible.append(row)
            if klass == DEEP_SHADOW:
                skipped["shadow_researched"] += 1
            else:
                skipped["model_eligible"] += 1
        else:
            skipped[klass] = skipped.get(klass, 0) + 1
        records.append(
            {
                "row": row,
                "state": acc_state,
                "blocker": acc_blocker,
                "researchClass": klass,
                "deepResearch": deep,
            }
        )
    return {
        "records": records,
        "eligible": eligible,
        "skipped": skipped,
        "eligible_prop_count": len(eligible),
    }


def market_definition_id(row: dict[str, Any]) -> str:
    return "|".join(
        [
            "prizepicks",
            str(row.get("league") or ""),
            str(row.get("market") or ""),
            str(row.get("boardId") or "FULL_GAME"),
        ]
    )
