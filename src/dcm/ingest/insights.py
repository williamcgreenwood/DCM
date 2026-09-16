"""Typed adapter for Outlier ``/insights`` responses.

The Insights endpoint is a historical signal surface, not a market-board
projection feed.  This module converts only the documented semantic fields
into bounded, content-addressed records.  It deliberately does not copy the
response body, free-form text, cookies, headers, or opaque book identifiers.

The adapter is accounting-first: every row receives a disposition, while
production eligibility remains a later decision owned by the sport and market
contracts.  ``hitRate`` and ``lastN`` are retained as historical features;
they are never emitted as a forecast probability.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from dcm.contracts.hashes import content_hash


INSIGHTS_ADAPTER_VERSION = "OUTLIER_INSIGHTS_ADAPTER_V1_2026-09-14"
PAGINATION_ABSENT = "ABSENT"
PAGINATION_TERMINAL_NULL = "TERMINAL_NULL"
PAGINATION_NONEMPTY = "NONEMPTY"
PAGINATION_MALFORMED = "MALFORMED"
PAGINATION_INCOMPLETE = "INCOMPLETE"
_PAGINATION_COMPLETE_STATES = {PAGINATION_ABSENT, PAGINATION_TERMINAL_NULL}

_HIGHER = {"OVER", "HIGHER", "MORE", "ABOVE"}
_LOWER = {"UNDER", "LOWER", "LESS", "BELOW"}
_HOME = {"HOME"}
_AWAY = {"AWAY"}
_MODIFIERS = {"STANDARD", "GOBLIN", "DEMON", "UNKNOWN"}


def pagination_state(payload: dict[str, Any]) -> str:
    """Return an explicit pagination state without treating malformed data as complete."""
    if not isinstance(payload, dict):
        return PAGINATION_MALFORMED
    marker = payload.get("pagination")
    if marker is not None:
        if not isinstance(marker, dict):
            return PAGINATION_MALFORMED
        if marker.get("complete") is False:
            return PAGINATION_INCOMPLETE
    if "nextPageToken" not in payload:
        return PAGINATION_ABSENT
    token = payload.get("nextPageToken")
    if token is None or str(token).strip() == "":
        return PAGINATION_TERMINAL_NULL
    if not isinstance(token, str):
        return PAGINATION_MALFORMED
    return PAGINATION_NONEMPTY


def _text(value: Any, *, limit: int = 256) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _bool_list(value: Any) -> list[bool]:
    if not isinstance(value, list):
        return []
    return [bool(item) for item in value if isinstance(item, (bool, int, float))]


def _direction(row: dict[str, Any]) -> tuple[str, str]:
    """Classify Higher/Lower separately from team Home/Away outcomes."""
    position = _text(row.get("position")).upper()
    label = _text(row.get("outcomeLabel")).upper()
    position_direction = (
        "HIGHER" if position in _HIGHER else
        "LOWER" if position in _LOWER else
        "HOME" if position in _HOME else
        "AWAY" if position in _AWAY else
        "UNKNOWN"
    )
    label_direction = (
        "HIGHER" if label in _HIGHER else
        "LOWER" if label in _LOWER else
        "HOME" if label in _HOME else
        "AWAY" if label in _AWAY else
        "UNKNOWN"
    )
    if position_direction != "UNKNOWN" and label_direction != "UNKNOWN" and position_direction != label_direction:
        return "CONFLICT", "POSITION_OUTCOME_CONFLICT"
    direction = position_direction if position_direction != "UNKNOWN" else label_direction
    if direction in {"HIGHER", "LOWER"}:
        return direction, "HIGHER_LOWER"
    if direction in {"HOME", "AWAY"}:
        return direction, "TEAM_SIDE"
    return "UNKNOWN", "UNRESOLVED"


def _event_summary(row: dict[str, Any]) -> dict[str, Any]:
    event = row.get("event") if isinstance(row.get("event"), dict) else {}
    home = event.get("home") if isinstance(event.get("home"), dict) else {}
    away = event.get("away") if isinstance(event.get("away"), dict) else {}
    return {
        "eventId": _text(row.get("eventId") or event.get("eventId"), limit=128),
        "scheduledTime": _text(event.get("scheduledTime"), limit=64),
        "status": _text(event.get("status") or row.get("eventStatus") or event.get("gameStatus"), limit=48),
        "timezone": _text(event.get("timezone"), limit=64),
        "week": _text(event.get("week"), limit=32),
        "year": _text(event.get("year"), limit=16),
        "neutralSite": bool(event.get("neutralSite")) if "neutralSite" in event else None,
        "home": {
            "teamId": _text(home.get("teamId"), limit=128),
            "name": _text(home.get("name"), limit=128),
            "alias": _text(home.get("alias"), limit=32),
        },
        "away": {
            "teamId": _text(away.get("teamId"), limit=128),
            "name": _text(away.get("name"), limit=128),
            "alias": _text(away.get("alias"), limit=32),
        },
    }


def _history_summary(row: dict[str, Any]) -> dict[str, Any]:
    source = row.get("playerData") or row.get("teamData")
    source = source if isinstance(source, dict) else {}
    items = source.get("items") if isinstance(source.get("items"), list) else []
    history: list[dict[str, Any]] = []
    for item in items[:100]:
        if not isinstance(item, dict):
            continue
        history.append(
            {
                "date": _text(item.get("date"), limit=64),
                "eventId": _text(item.get("eventId"), limit=128),
                "matchup": _text(item.get("matchup"), limit=64),
                "stat": _number(item.get("stat")),
                "value": _number(item.get("value")),
            }
        )
    record: dict[str, Any] = {"items": history}
    team_record = source.get("teamRecord")
    if isinstance(team_record, dict):
        record["teamRecord"] = {
            "wins": _number(team_record.get("wins")),
            "losses": _number(team_record.get("losses")),
            "ties": _number(team_record.get("ties")),
        }
    return record


def _subject_name(row: dict[str, Any]) -> str:
    for key in ("playerName", "teamName", "subjectName", "name"):
        value = _text(row.get(key), limit=128)
        if value:
            return value
    for key in ("player", "team", "subject"):
        nested = row.get(key)
        if isinstance(nested, dict):
            for name_key in ("name", "displayName", "display_name", "fullName"):
                value = _text(nested.get(name_key), limit=128)
                if value:
                    return value
    return ""


def _book_summary(row: dict[str, Any]) -> tuple[list[dict[str, Any]], Counter[str]]:
    book_odds = row.get("bookOdds") if isinstance(row.get("bookOdds"), dict) else {}
    listed_books = row.get("books") if isinstance(row.get("books"), list) else []
    names = sorted({_text(name, limit=64).upper() for name in listed_books if _text(name)})
    if not names:
        names = sorted(_text(name, limit=64).upper() for name in book_odds if _text(name))
    counts: Counter[str] = Counter()
    out: list[dict[str, Any]] = []
    for name in names:
        detail = book_odds.get(name) if isinstance(book_odds.get(name), dict) else {}
        props = detail.get("identifier", {}).get("bookProps") if isinstance(detail.get("identifier"), dict) else {}
        props = props if isinstance(props, dict) else {}
        modifier = _text(props.get("odds_type") or props.get("oddsType") or "UNKNOWN", limit=32).upper()
        if modifier not in _MODIFIERS:
            modifier = "UNKNOWN"
        counts[modifier] += 1
        out.append(
            {
                "book": name,
                "odds": _text(detail.get("odds"), limit=32),
                "decimal": _number(detail.get("decimal")),
                "modifier": modifier,
                "hasBookIdentity": bool(detail.get("identifier")),
            }
        )
    return out, counts


def _split_summary(row: dict[str, Any]) -> list[dict[str, Any]]:
    splits = row.get("splits") if isinstance(row.get("splits"), list) else []
    out: list[dict[str, Any]] = []
    for split in splits[:16]:
        if not isinstance(split, dict):
            continue
        item: dict[str, Any] = {"splitType": _text(split.get("splitType"), limit=32).upper() or "NONE"}
        matchup = split.get("matchupStat")
        if isinstance(matchup, dict):
            item["matchupStat"] = {
                "games": _number(matchup.get("games")),
                "hits": _number(matchup.get("hits")),
                "hitRate": _number(matchup.get("hitRate")),
            }
        out.append(item)
    return out


def _disposition(
    *,
    subject_type: str,
    market_type: str,
    direction_class: str,
    insight_id: str,
    player_id: str,
    team_id: str,
    line: float | int | None,
) -> str:
    if not insight_id:
        return "MISSING_INSIGHT_ID"
    if line is None:
        return "MISSING_LINE"
    if subject_type == "PLAYER" and market_type == "PLAYER_PROP":
        if not player_id:
            return "MISSING_PLAYER_ID"
        if direction_class != "HIGHER_LOWER":
            return "UNRESOLVED_PLAYER_DIRECTION"
        return "PLAYER_PROP_CANDIDATE"
    if subject_type == "TEAM" or market_type == "GAMELINE":
        if not team_id:
            return "MISSING_TEAM_ID"
        if direction_class != "TEAM_SIDE":
            return "UNRESOLVED_TEAM_DIRECTION"
        return "TEAM_MARKET_ACCOUNTED"
    return "UNSUPPORTED_INSIGHT_MARKET"


def canonical_insight_record(
    row: dict[str, Any],
    *,
    source_har_sha256: str,
    source_body_hash: str,
    source_snapshot_time: str = "",
    request_scope: str = "",
    entry_ordinal: int = 0,
    row_ordinal: int = 0,
    page_number: int = 1,
    page_state: str = PAGINATION_ABSENT,
) -> dict[str, Any]:
    """Build one bounded immutable record without retaining the source body."""
    row = row if isinstance(row, dict) else {}
    insight_id = _text(row.get("insightId"), limit=128)
    subject_type = _text(row.get("subjectType"), limit=32).upper()
    market_type = _text(row.get("marketType"), limit=64).upper()
    player_id = _text(row.get("playerId"), limit=128)
    team_id = _text(row.get("teamId"), limit=128)
    line = _number(row.get("line"))
    direction, direction_class = _direction(row)
    books, modifier_counts = _book_summary(row)
    last_n = _bool_list(row.get("lastN"))
    hit_count = sum(1 for value in last_n if value)
    reported_hit_rate = _number(row.get("hitRate"))
    disposition = _disposition(
        subject_type=subject_type,
        market_type=market_type,
        direction_class=direction_class,
        insight_id=insight_id,
        player_id=player_id,
        team_id=team_id,
        line=line,
    )
    record: dict[str, Any] = {
        "schema": "pillars_dcm.outlier_insight_claim.v1",
        "adapterVersion": INSIGHTS_ADAPTER_VERSION,
        "claimId": f"INSIGHT:{insight_id}:{source_body_hash}" if insight_id else "",
        "insightId": insight_id,
        "sourceHarSha256": _text(source_har_sha256, limit=128),
        "sourceBodyHash": _text(source_body_hash, limit=128),
        "sourceSnapshotTime": _text(source_snapshot_time, limit=64),
        "requestScope": _text(request_scope, limit=128),
        "entryOrdinal": int(entry_ordinal),
        "rowOrdinal": int(row_ordinal),
        "pageNumber": int(page_number),
        "paginationState": page_state,
        "paginationComplete": page_state in _PAGINATION_COMPLETE_STATES,
        "subjectType": subject_type,
        "subjectId": player_id if subject_type == "PLAYER" else team_id,
        "subjectName": _subject_name(row),
        "playerId": player_id,
        "teamId": team_id,
        "leagueId": _text(row.get("leagueId"), limit=64),
        "competitionId": _text(row.get("competitionId"), limit=128),
        "event": _event_summary(row),
        "marketId": _text(row.get("marketId"), limit=128),
        "marketOutcomeId": _text(row.get("marketOutcomeId"), limit=128),
        "marketType": market_type,
        "marketActive": bool(row.get("marketActive")) if "marketActive" in row else None,
        "marketLabel": _text(row.get("marketLabel"), limit=128),
        "proposition": _text(row.get("proposition"), limit=128).upper(),
        "propLabel": _text(row.get("propLabel"), limit=128),
        "periodLabel": _text(row.get("periodLabel"), limit=64),
        "includeOvertime": bool(row.get("includeOvertime")) if "includeOvertime" in row else None,
        "line": line,
        "lineLabel": _text(row.get("lineLabel"), limit=128),
        "direction": direction,
        "directionClass": direction_class,
        "lastN": last_n,
        "lastNCount": len(last_n),
        "lastNHitCount": hit_count,
        "reportedHitRate": reported_hit_rate,
        "historicalSignalOnly": True,
        "books": books,
        "observedBookOffers": [
            {
                "book": item["book"], "odds": item["odds"], "decimal": item["decimal"],
                "side": direction, "line": line, "modifier": item["modifier"],
                "periodLabel": _text(row.get("periodLabel"), limit=64),
                "captureTime": _text(source_snapshot_time, limit=64),
                "state": "OBSERVED_INSIGHT_NOT_CURRENT_BOARD",
            }
            for item in books
        ],
        "bookCount": len(books),
        "modifierCounts": dict(sorted(modifier_counts.items())),
        "splits": _split_summary(row),
        "history": _history_summary(row),
        "playerPosition": _text(row.get("playerPosition"), limit=32),
        "relevancy": _number(row.get("relevancy")),
        "disposition": disposition,
        "productionEligible": False,
        "marketDefinitionState": "CAPTURED_UNRESOLVED",
        "settlementState": "UNSETTLED",
    }
    record["claimHash"] = content_hash(record)
    return record


def summarize_insight_claims(
    claims: list[dict[str, Any]],
    *,
    page_state: str,
    source_har_sha256: str,
    source_body_hash: str,
    item_count: int,
) -> dict[str, Any]:
    dispositions = Counter(str(row.get("disposition") or "UNKNOWN") for row in claims)
    directions = Counter(str(row.get("direction") or "UNKNOWN") for row in claims)
    subjects = Counter(str(row.get("subjectType") or "UNKNOWN") for row in claims)
    return {
        "schema": "pillars_dcm.outlier_insight_accounting.v1",
        "adapterVersion": INSIGHTS_ADAPTER_VERSION,
        "sourceHarSha256": source_har_sha256,
        "sourceBodyHash": source_body_hash,
        "itemCount": int(item_count),
        "typedClaimCount": len(claims),
        "uniqueInsightIds": len({str(row.get("insightId") or "") for row in claims if row.get("insightId")}),
        "paginationState": page_state,
        "paginationComplete": page_state in _PAGINATION_COMPLETE_STATES,
        "dispositions": dict(sorted(dispositions.items())),
        "subjects": dict(sorted(subjects.items())),
        "directions": dict(sorted(directions.items())),
        "contentHash": content_hash(
            {
                "sourceHarSha256": source_har_sha256,
                "sourceBodyHash": source_body_hash,
                "itemCount": item_count,
                "typedClaimCount": len(claims),
                "dispositions": dict(sorted(dispositions.items())),
                "paginationState": page_state,
            }
        ),
    }


def parse_insights_payload(
    payload: dict[str, Any],
    *,
    source_har_sha256: str,
    source_body_hash: str,
    source_snapshot_time: str = "",
    request_scope: str = "",
    entry_ordinal: int = 0,
    page_number: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse one response page; malformed and unconsumed pages fail closed."""
    payload = payload if isinstance(payload, dict) else {}
    rows = payload.get("insights") if isinstance(payload.get("insights"), list) else []
    state = pagination_state(payload)
    if "insights" in payload and not isinstance(payload.get("insights"), list):
        state = PAGINATION_MALFORMED
    claims = [
        canonical_insight_record(
            row,
            source_har_sha256=source_har_sha256,
            source_body_hash=source_body_hash,
            source_snapshot_time=source_snapshot_time,
            request_scope=request_scope,
            entry_ordinal=entry_ordinal,
            row_ordinal=index,
            page_number=page_number,
            page_state=state,
        )
        for index, row in enumerate(rows)
    ]
    return claims, summarize_insight_claims(
        claims,
        page_state=state,
        source_har_sha256=source_har_sha256,
        source_body_hash=source_body_hash,
        item_count=len(rows),
    )


def merge_insight_claims(claim_lists: list[list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deduplicate exact snapshots while preserving changed snapshots and conflicts."""
    by_key: dict[str, dict[str, Any]] = {}
    by_insight: dict[str, set[str]] = {}
    exact_duplicates = 0
    for claims in claim_lists:
        for claim in claims:
            key = str(claim.get("claimId") or claim.get("claimHash") or content_hash(claim))
            if key in by_key:
                exact_duplicates += 1
            by_key.setdefault(key, claim)
            insight_id = str(claim.get("insightId") or "")
            if insight_id:
                by_insight.setdefault(insight_id, set()).add(key)
    merged = [by_key[key] for key in sorted(by_key)]
    conflicts = sum(1 for keys in by_insight.values() if len(keys) > 1)
    return merged, {
        "schema": "pillars_dcm.outlier_insight_composite_accounting.v1",
        "typedClaimCount": len(merged),
        "uniqueInsightIds": len(by_insight),
        "exactDuplicateSnapshotsRemoved": exact_duplicates,
        "changedInsightIds": conflicts,
        "paginationComplete": all(
            bool(claim.get("paginationComplete")) for claim in merged
        ),
        "contentHash": content_hash(merged),
    }
