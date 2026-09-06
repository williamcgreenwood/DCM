from __future__ import annotations

import json

from dcm.ingest.board import rows_as_of
from dcm.ingest.composite import compose_ingests
from dcm.ingest.har import canonical_request_scope, ingest_har


def _row(pid: str, line: float = 10.5) -> dict:
    return {
        "projectionId": pid,
        "sportFamily": "basketball",
        "league": "NBA",
        "eventId": "E1",
        "eventLabel": "AAA @ BBB",
        "playerId": f"P_{pid}",
        "playerName": f"Player {pid}",
        "teamId": "AAA",
        "team": "AAA",
        "opponent": "BBB",
        "market": "pts",
        "marketLabel": "Points",
        "line": line,
        "side": "MORE",
        "offeredHigher": True,
        "offeredLower": True,
        "modifier": "STANDARD",
        "boardId": "FULL_GAME",
        "productType": "PLAYER_PICKS",
        "role": "G",
    }


def _har(
    *,
    url: str,
    at: str,
    rows: list[dict] | None = None,
    status: int = 200,
    body: dict | None = None,
) -> dict:
    if body is None and status >= 200 and status < 300:
        body = {"data": rows if rows is not None else []}
    content = {}
    if body is not None:
        content = {"mimeType": "application/json", "text": json.dumps(body)}
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "test", "version": "1"},
            "entries": [
                {
                    "startedDateTime": at,
                    "request": {"method": "GET", "url": url, "headers": []},
                    "response": {"status": status, "headers": [], "content": content},
                }
            ],
        }
    }


def _ing(har: dict) -> dict:
    raw = json.dumps(har, sort_keys=True).encode()
    return ingest_har(raw, raw_bytes=raw)


def test_request_scope_normalizes_query_order_and_volatile_values():
    a = canonical_request_scope(
        "https://api.prizepicks.com/projections?page=2&league=NBA&token=AAA"
    )
    b = canonical_request_scope(
        "https://API.PRIZEPICKS.COM/projections?token=BBB&league=NBA&page=2"
    )
    c = canonical_request_scope(
        "https://api.prizepicks.com/projections?league=NBA&page=3&token=CCC"
    )
    assert a == b
    assert a != c


def test_complementary_hars_union_and_reverse_input_order_is_invariant():
    a = _ing(
        _har(
            url="https://api.prizepicks.com/projections?page=1",
            at="2026-08-28T10:00:00Z",
            rows=[_row("p1")],
        )
    )
    b = _ing(
        _har(
            url="https://api.prizepicks.com/projections?page=2",
            at="2026-08-28T11:00:00Z",
            rows=[_row("p2")],
        )
    )
    ab = compose_ingests([a, b])
    ba = compose_ingests([b, a])
    assert {r["projectionId"] for r in ab["rows"]} == {"p1", "p2"}
    assert ab["harSha256"] == ba["harSha256"]
    assert ab["reconciliationHash"] == ba["reconciliationHash"]
    assert ab["rows"] == ba["rows"]


def test_scope_not_recaptured_retains_prior_valid_state():
    a = _ing(
        _har(
            url="https://api.prizepicks.com/projections?page=1",
            at="2026-08-28T10:00:00Z",
            rows=[_row("p1")],
        )
    )
    b = _ing(
        _har(
            url="https://api.prizepicks.com/projections?page=2",
            at="2026-08-28T11:00:00Z",
            rows=[_row("p2")],
        )
    )
    out = compose_ingests([a, b])
    retained = [
        x for x in out["timeline"]
        if x["projectionId"] == "p1" and "SCOPE_NOT_RECAPTURED_RETAINED" in x["states"]
    ]
    assert retained
    assert {r["projectionId"] for r in out["rows"]} == {"p1", "p2"}


def test_successful_verified_empty_identical_scope_clears_prior_state():
    url = "https://api.prizepicks.com/projections?page=1"
    a = _ing(_har(url=url, at="2026-08-28T10:00:00Z", rows=[_row("p1")]))
    b = _ing(_har(url=url, at="2026-08-28T11:00:00Z", rows=[]))
    out = compose_ingests([a, b])
    assert out["rows"] == []
    assert any(
        x["projectionId"] == "p1" and "REMOVED_BY_IDENTICAL_SCOPE_REFRESH" in x["states"]
        for x in out["timeline"]
    )


def test_failed_identical_scope_refresh_retains_prior_valid_state():
    url = "https://api.prizepicks.com/projections?page=1"
    a = _ing(_har(url=url, at="2026-08-28T10:00:00Z", rows=[_row("p1")]))
    b = _ing(_har(url=url, at="2026-08-28T11:00:00Z", status=503, body=None))
    out = compose_ingests([a, b])
    assert [r["projectionId"] for r in out["rows"]] == ["p1"]
    assert out["failedRefreshes"]
    assert out["failedRefreshes"][-1]["state"] == "HTTP_FAILURE"
    assert any(
        x["projectionId"] == "p1" and "FAILED_REFRESH_PRIOR_RETAINED" in x["states"]
        for x in out["timeline"]
    )


def test_asof_scope_state_uses_last_success_before_cutoff():
    url = "https://api.prizepicks.com/projections?page=1"
    a = _ing(_har(url=url, at="2026-08-28T10:00:00Z", rows=[_row("p1", 10.5)]))
    b = _ing(_har(url=url, at="2026-08-28T12:00:00Z", rows=[_row("p1", 12.5)]))
    out = compose_ingests([a, b])
    rows, stats = rows_as_of(out, "2026-08-28T11:00:00Z")
    assert len(rows) == 1
    assert rows[0]["line"] == 10.5
    assert stats["post_cutoff_snapshots_excluded"] == 1


def test_successful_empty_after_cutoff_does_not_clear_pre_cutoff_board():
    url = "https://api.prizepicks.com/projections?page=1"
    a = _ing(_har(url=url, at="2026-08-28T10:00:00Z", rows=[_row("p1")]))
    b = _ing(_har(url=url, at="2026-08-28T12:00:00Z", rows=[]))
    out = compose_ingests([a, b])
    rows, _ = rows_as_of(out, "2026-08-28T11:00:00Z")
    assert [r["projectionId"] for r in rows] == ["p1"]
