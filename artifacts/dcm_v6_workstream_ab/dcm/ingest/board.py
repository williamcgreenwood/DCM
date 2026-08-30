"""As-of immutable board freeze."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.ingest.composite import reconcile_scope_attempts
from dcm.ingest.wsab_bind import annotate_rows

PARSER_SCHEMA = "BOARD_JSON_V2_ASOF_2026-08-28"
LEARNING_REVISION = "LR000000"
PREDICTIVE_CLAIM = "NONE"


def _time(value: Any) -> datetime | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except ValueError:
        return None


def rows_as_of(ingest: dict[str, Any], cutoff: str) -> tuple[list[dict], dict[str, int]]:
    cut = _time(cutoff)
    if cut is None:
        raise ValueError("FORECAST_CUTOFF_INVALID")

    # New scope-state captures are authoritative because they can represent a
    # successful empty refresh. Projection-only history cannot express a
    # deletion and would incorrectly resurrect rows after such a refresh.
    attempts = ingest.get("scopeAttempts")
    if isinstance(attempts, list) and attempts:
        reconciled = reconcile_scope_attempts(attempts, cutoff=cutoff)
        stats = reconciled["stats"]
        return list(reconciled["rows"]), {
            "post_cutoff_snapshots_excluded": int(stats["post_cutoff_attempts_excluded"]),
            "post_cutoff_updates_excluded": int(stats["post_cutoff_updates_excluded"]),
            "failed_refreshes_retained": int(stats["failed_refreshes_retained"]),
            "selected_request_scopes": int(stats["selected_scope_count"]),
        }

    history = ingest.get("rowHistory") if isinstance(ingest.get("rowHistory"), dict) else {}
    if not history:
        return list(ingest.get("rows") or []), {"post_cutoff_snapshots_excluded": 0, "post_cutoff_updates_excluded": 0}
    selected: list[dict] = []
    post_snap = post_update = 0
    for hist in history.values():
        candidates = []
        for row in hist if isinstance(hist, list) else []:
            snap = _time(row.get("sourceSnapshotTime"))
            updated = _time(row.get("sourceUpdatedAt"))
            if snap is not None and snap > cut:
                post_snap += 1
                continue
            if updated is not None and updated > cut:
                post_update += 1
                continue
            candidates.append(row)
        if candidates:
            candidates.sort(key=lambda r: (
                _time(r.get("sourceUpdatedAt")) or _time(r.get("sourceSnapshotTime")) or datetime.min.replace(tzinfo=timezone.utc),
                str(r.get("sourceBodyHash") or ""),
            ))
            selected.append(dict(candidates[-1]))
    selected.sort(key=lambda r: str(r.get("projectionId")))
    return selected, {"post_cutoff_snapshots_excluded": post_snap, "post_cutoff_updates_excluded": post_update}


def accounting_from_rows(rows: list[dict], *, asof: dict[str, int] | None = None) -> dict[str, int]:
    def n(pred) -> int:
        return sum(1 for r in rows if pred(r))
    by_league: dict[str, int] = {}
    by_sport: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_odds: dict[str, int] = {}
    for r in rows:
        lg = str(r.get("league") or "UNKNOWN")
        by_league[lg] = by_league.get(lg, 0) + 1
        fam = str(r.get("sportFamily") or "unknown")
        by_sport[fam] = by_sport.get(fam, 0) + 1
        st = str(r.get("status") or "unknown")
        by_status[st] = by_status.get(st, 0) + 1
        md = str(r.get("modifier") or "OTHER")
        by_odds[md] = by_odds.get(md, 0) + 1
    out = {
        "raw_projection_rows": len(rows),
        "unique_offer_rows": len({r["projectionId"] for r in rows}),
        "standard_rows": n(lambda r: r.get("modifier") == "STANDARD"),
        "goblin_rows": n(lambda r: r.get("modifier") == "GOBLIN"),
        "demon_rows": n(lambda r: r.get("modifier") == "DEMON"),
        "unknown_modifier_rows": n(lambda r: r.get("modifier") not in {"STANDARD", "GOBLIN", "DEMON"}),
        "unknown_side_rows": n(lambda r: not r.get("offeredHigher") and not r.get("offeredLower")),
        "offered_higher_only": n(lambda r: r.get("offeredHigher") and not r.get("offeredLower")),
        "offered_lower_only": n(lambda r: r.get("offeredLower") and not r.get("offeredHigher")),
        "offered_both_sides": n(lambda r: r.get("offeredHigher") and r.get("offeredLower")),
        "missing_sides_fail_closed": n(lambda r: not r.get("offeredHigher") and not r.get("offeredLower")),
        "raw_missing_wager_types": n(lambda r: r.get("allowedWagerTypes") in (None, "", "missing")),
        "raw_over_wager_types": n(lambda r: str(r.get("allowedWagerTypes") or "").lower() == "over"),
        "raw_under_or_over_wager_types": n(lambda r: str(r.get("allowedWagerTypes") or "").lower() in {"under_or_over", "over_or_under"}),
        "pre_game_rows": n(lambda r: r.get("status") == "pre_game"),
        "in_progress_rows": n(lambda r: r.get("status") == "in_progress"),
        "suspended_rows": n(lambda r: r.get("status") == "suspended"),
        "live_rows": n(lambda r: bool(r.get("isLive"))),
        "combo_rows": n(lambda r: bool(r.get("combo"))),
        "events": len({r.get("eventId") for r in rows if r.get("eventId")}),
        "players": len({r.get("playerId") for r in rows if r.get("playerId")}),
        "duplicate_rows": max(0, len(rows) - len({r["projectionId"] for r in rows})),
        "removed_rows": 0,
        "unresolved_rows": n(lambda r: r.get("market") in {"unknown", ""} or r.get("league") == "UNKNOWN"),
        "wsab_bound_rows": n(lambda r: r.get("wsabMarketBound")),
        "final_model_population": n(lambda r: r.get("modifier") != "GOBLIN"),
        "by_league": by_league,
        "by_sport": by_sport,
        "by_status": by_status,
        "by_modifier": by_odds,
    }
    out.update(asof or {})
    return out


def freeze_board(
    ingest: dict[str, Any],
    *,
    mount: dict[str, Any],
    cutoff: str | None = None,
    asof_policy: str = "strict",
) -> dict[str, Any]:
    """Freeze the board.

    asof_policy:
      - strict: drop snapshots/updates after cutoff (unit tests / replay).
      - account_capture: account every unique captured projection; cutoff is
        recorded for evidence and production gating. A live HAR captured after
        the evidence cutoff still must be fully accounted.
    """
    resolved_cutoff = cutoff or str(ingest.get("captureEnd") or "9999-12-31T23:59:59Z")
    if asof_policy == "account_capture":
        attempts = ingest.get("scopeAttempts")
        if isinstance(attempts, list) and attempts:
            reconciled = reconcile_scope_attempts(attempts, cutoff=None)
            selected = list(reconciled["rows"])
            asof = {
                "post_cutoff_snapshots_excluded": 0,
                "post_cutoff_updates_excluded": 0,
                "failed_refreshes_retained": int((reconciled.get("stats") or {}).get("failed_refreshes_retained") or 0),
                "selected_request_scopes": int((reconciled.get("stats") or {}).get("selected_scope_count") or 0),
                "accounted_including_post_cutoff": True,
            }
            if cutoff:
                _, skipped = rows_as_of(ingest, cutoff)
                asof["would_exclude_under_strict_asof"] = int(skipped.get("post_cutoff_snapshots_excluded") or 0) + int(
                    skipped.get("post_cutoff_updates_excluded") or 0
                )
        else:
            selected, asof = list(ingest.get("rows") or []), {"accounted_including_post_cutoff": True}
    else:
        selected, asof = rows_as_of(ingest, resolved_cutoff)
    rows = annotate_rows(selected)
    payload = {
        "schemaId": PARSER_SCHEMA,
        "parserVersion": ingest.get("parserVersion"),
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "v5Mount": mount,
        "v5Decoder": ingest.get("v5Decoder", "NOT_MOUNTED"),
        "sourceAdapter": ingest.get("adapter"),
        "harSha256": ingest.get("harSha256"),
        "captureStart": ingest.get("captureStart") or "",
        "captureEnd": ingest.get("captureEnd") or "",
        "forecastCutoff": resolved_cutoff,
        "redactedSecrets": ingest.get("redactedSecrets") or 0,
        "indexStats": ingest.get("indexStats") or {},
        "warnings": ingest.get("warnings") or [],
        "timeline": ingest.get("timeline") or [],
        "rows": rows,
        "unresolvedRows": [
            r["projectionId"] for r in rows
            if r.get("market") in {"unknown", ""} or r.get("league") == "UNKNOWN"
            or (not r.get("offeredHigher") and not r.get("offeredLower"))
        ],
        "eventIds": sorted({r.get("eventId") or "" for r in rows}),
        "accounting": accounting_from_rows(rows, asof=asof),
    }
    payload["contentHash"] = content_hash(payload)
    return payload


def write_board(board: dict[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(board, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    return dest
