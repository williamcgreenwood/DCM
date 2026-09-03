"""CFB HAR accounting: extract/account every offer before Goblin exclusion."""
from __future__ import annotations

from collections import Counter
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.classify import accounting_classify, research_disposition
from dcm.research.indexes import SUPPORTED_CFB_MARKETS
from dcm.sports.football.research_requirements import MARKET_REQUIREMENTS


def _is_cfb(row: dict[str, Any]) -> bool:
    return str(row.get("sportFamily") or "") == "gridiron" and str(row.get("league") or "").upper() == "CFB"


def _market(row: dict[str, Any]) -> str:
    return str(row.get("market") or "").lower()


def account_cfb_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Account every CFB offer, then classify Goblins / support / modelability gates.

    Goblins remain in raw totals. They are excluded from selection only after
    this accounting document is complete.
    """
    cfb = [r for r in rows if _is_cfb(r)]
    goblins = [r for r in cfb if r.get("modifier") == "GOBLIN"]
    non_goblins = [r for r in cfb if r.get("modifier") != "GOBLIN"]
    supported = [r for r in non_goblins if _market(r) in MARKET_REQUIREMENTS]
    unsupported = [r for r in non_goblins if _market(r) not in MARKET_REQUIREMENTS]
    classified: Counter[str] = Counter()
    disposition: Counter[str] = Counter()
    offered_side_unknown = 0
    live_or_started = 0
    for row in cfb:
        state, blocker = accounting_classify(row)
        classified[state] += 1
        if blocker == "OFFERED_SIDE_UNKNOWN":
            offered_side_unknown += 1
        if blocker in {"LIVE_OR_IN_PROGRESS_NOT_PRODUCTION", "UNKNOWN_STATUS_FAIL_CLOSED"}:
            live_or_started += 1
        _deep, cls = research_disposition(row)
        disposition[cls] += 1

    markets_raw = dict(Counter(_market(r) for r in cfb))
    markets_non_goblin = dict(Counter(_market(r) for r in non_goblins))
    events = sorted({str(r.get("eventId") or "") for r in cfb if r.get("eventId")})
    subjects = sorted({str(r.get("playerId") or "") for r in cfb if r.get("playerId")})
    teams = sorted({str(r.get("teamId") or r.get("team") or "") for r in cfb if r.get("teamId") or r.get("team")})

    body = {
        "schema": "pillars_dcm.cfb_har_accounting.v1",
        "rawCfb": len(cfb),
        "goblin": len(goblins),
        "nonGoblin": len(non_goblins),
        "supported": len(supported),
        "supportedMarketDefinitions": sorted(MARKET_REQUIREMENTS),
        "supportedNonGoblinOffers": len(supported),
        "unsupported": len(unsupported),
        "unsupportedMarkets": sorted({_market(r) for r in unsupported if _market(r)}),
        "modelablePopulationNote": "modelable is computed after evidence; this document is pre-research accounting",
        "classified": dict(classified),
        "researchDisposition": dict(disposition),
        "offeredSideUnknown": offered_side_unknown,
        "liveOrStarted": live_or_started,
        "marketsRaw": markets_raw,
        "marketsNonGoblin": markets_non_goblin,
        "uniqueEvents": len(events),
        "uniqueSubjects": len(subjects),
        "uniqueTeams": len(teams),
        "eventIds": events,
        "meaningfulTop100": len(supported) >= 100,
        "newMarketsActivatedToday": [],
        "goblinsExcludedFromSelectionAfterAccounting": True,
        "guardedLaunchMarkets": list(SUPPORTED_CFB_MARKETS),
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body
