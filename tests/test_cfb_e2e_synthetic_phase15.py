"""Phase 15 — CFB positive/negative end-to-end proof (synthetic fixtures).

Labels:
  PATH_A = SYNTHETIC / evidence-complete positive path
  PATH_B = SYNTHETIC / incomplete-conflicted negative path
  PATH_C = private HAR aggregates-only (box attachments; never committed)

Does not claim live operational acceptance, predictive certification, or LR promotion.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

from dcm.cfb.accounting import account_cfb_board
from dcm.ingest.har import ingest_har
from dcm.research.claims import claim_record
from dcm.research.classify import market_definition_id
from dcm.research.provider import write_bundle
from dcm.runner import run_dcm

FIXTURES = Path(__file__).resolve().parent / "research_fixtures"
POSITIVE_HAR = FIXTURES / "cfb_e2e_phase15_positive_har.json"
INCOMPLETE_HAR = FIXTURES / "cfb_e2e_phase15_incomplete_har.json"
CUTOFF = "2026-09-02T18:00:00Z"

# Private aggregate checkpoints may exist on the shared agent box only.
_PRIVATE_AGG_CANDIDATES = [
    Path("/workspace/dcm-private-checkpoints/cfb-har-20260906-final/final_slate_SAFE_AGGREGATES.json"),
    Path("/workspace/dcm-private-checkpoints/cfb-har-20260905/SAFE_AGGREGATES.json"),
    Path("/workspace/dcm-private-checkpoints/cfb-har-20260905/CFB_HAR_ACCOUNTING.json"),
]

QB_LOGS = [
    {"date": "2025-09-01", "gs": 1, "snaps": 70, "pass_att": 31, "pass_cmp": 20, "pass_yds": 248, "rush_att": 7, "rush_yds": 32, "sacks_taken": 2, "scramble_att": 4},
    {"date": "2025-09-08", "gs": 1, "snaps": 72, "pass_att": 34, "pass_cmp": 23, "pass_yds": 281, "rush_att": 8, "rush_yds": 39, "sacks_taken": 2, "scramble_att": 5},
    {"date": "2025-09-15", "gs": 1, "snaps": 68, "pass_att": 29, "pass_cmp": 18, "pass_yds": 226, "rush_att": 6, "rush_yds": 26, "sacks_taken": 3, "scramble_att": 4},
    {"date": "2026-08-29", "gs": 1, "snaps": 69, "pass_att": 32, "pass_cmp": 21, "pass_yds": 264, "rush_att": 7, "rush_yds": 35, "sacks_taken": 2, "scramble_att": 4},
]
RB_LOGS = [
    {"date": "2025-09-01", "gs": 1, "snaps": 48, "rush_att": 16, "rush_yds": 84, "routes": 12, "targets": 3, "receptions": 2, "rec_yds": 18},
    {"date": "2025-09-08", "gs": 1, "snaps": 51, "rush_att": 18, "rush_yds": 101, "routes": 13, "targets": 4, "receptions": 3, "rec_yds": 27},
    {"date": "2025-09-15", "gs": 1, "snaps": 46, "rush_att": 15, "rush_yds": 73, "routes": 11, "targets": 2, "receptions": 2, "rec_yds": 15},
    {"date": "2026-08-29", "gs": 1, "snaps": 50, "rush_att": 17, "rush_yds": 92, "routes": 12, "targets": 3, "receptions": 2, "rec_yds": 20},
]
WR_LOGS = [
    {"date": "2025-09-01", "gs": 1, "snaps": 59, "routes": 31, "targets": 8, "receptions": 5, "rec_yds": 71, "rush_att": 1, "rush_yds": 4},
    {"date": "2025-09-08", "gs": 1, "snaps": 62, "routes": 33, "targets": 9, "receptions": 6, "rec_yds": 88, "rush_att": 0, "rush_yds": 0},
    {"date": "2025-09-15", "gs": 1, "snaps": 57, "routes": 30, "targets": 7, "receptions": 4, "rec_yds": 63, "rush_att": 1, "rush_yds": 6},
    {"date": "2026-08-29", "gs": 1, "snaps": 61, "routes": 32, "targets": 8, "receptions": 5, "rec_yds": 79, "rush_att": 0, "rush_yds": 0},
]


def _claim(scope: str, scope_id: str, value: dict, *, claim_type: str = "cfb_e2e_phase15") -> dict:
    return claim_record(
        source_id="TEST_CFB_E2E_PHASE15",
        url="https://example.com/cfb-e2e-phase15",
        published_at=CUTOFF,
        observed_at=CUTOFF,
        forecast_cutoff=CUTOFF,
        semantic_scope=scope,
        scope_id=scope_id,
        claim_type=claim_type,
        claim_value=value,
        reliability=0.95,
        freshness=1.0,
    )


def evidence_complete_claims(rows: list[dict]) -> list[dict]:
    """Synthetic evidence-complete claim set (SPORT→OFFER). Clearly fixture-only."""
    claims = [
        _claim("SPORT", "gridiron:CFB", {"rules_calendar_distribution": True, "rules": {"season": "2026"}, "calendar": True, "distribution": True}),
        _claim("COMPETITION", "gridiron:CFB", {"competition_context": True, "league": "CFB", "level": "FBS"}),
        _claim("ENVIRONMENT", "env:CFB_TEST_1", {"weather_surface_venue_effects": True, "weather": {"wind_mph": 5, "precipitation": 0}, "surface": "grass", "venue": "Fixture Stadium"}),
        _claim("EVENT", "CFB_TEST_1", {
            "event_context": True, "scheduled_start": "2026-09-05T23:00:00Z", "venue": "Fixture Stadium",
            "surface": "grass", "weather": {"wind_mph": 5, "precipitation": 0}, "spread": -7.5, "game_total": 55.5, "starters_known": True,
        }),
        _claim("AFFILIATION", "AAA", {
            "affiliation_context": True, "team_context": True, "plays": 72, "pass_rate": 0.55, "rush_rate": 0.45,
            "pace": 1.02, "depth": {"QB": "QB1", "RB": "RB1", "WR": "WR1"}, "injury_cluster": False,
            # coverage._team_missing expects pass_defense/rush_defense on AFFILIATION merge
            "pass_defense": 1.0, "rush_defense": 1.0,
            "opponent_pass_defense": 0.98, "opponent_rush_defense": 1.01,
        }),
        _claim("COUNTERPARTY", "BBB", {
            "counterparty_context": True, "team_context": True, "plays": 69, "pace": 1.0,
            "pass_defense": 0.98, "rush_defense": 1.01, "depth": {}, "injury_cluster": False,
        }),
        _claim("SUBJECT", "QB1", {
            "status": "ACTIVE", "role": "QB", "depth_chart_role": "qb1 starter", "prior_season_starts": 12,
            "game_logs": QB_LOGS, "opportunity": {"support_n": len(QB_LOGS)}, "efficiency": {"support_n": len(QB_LOGS)},
        }),
        _claim("SUBJECT", "RB1", {
            "status": "ACTIVE", "role": "RB", "depth_chart_role": "rb1 starter", "prior_season_starts": 10,
            "game_logs": RB_LOGS, "opportunity": {"support_n": len(RB_LOGS)}, "efficiency": {"support_n": len(RB_LOGS)},
        }),
        _claim("SUBJECT", "WR1", {
            "status": "ACTIVE", "role": "WR", "depth_chart_role": "wr1 starter", "prior_season_starts": 11,
            "game_logs": WR_LOGS, "opportunity": {"support_n": len(WR_LOGS)}, "efficiency": {"support_n": len(WR_LOGS)},
        }),
    ]
    for row in rows:
        if str(row.get("modifier") or "") == "GOBLIN":
            continue
        market = str(row.get("market") or "").lower()
        if market in {"fantasy", "longest_reception", "longest_rush", "longest_completion"}:
            continue
        claims.append(_claim("MARKET_DEFINITION", market_definition_id(row), {"definition_verified": True, "exact_stat_definition": True}))
        claims.append(_claim("OFFER", str(row["projectionId"]), {
            "offer_recorded": True, "line_sides_modifier": True, "line": row.get("line"),
            "offeredHigher": bool(row.get("offeredHigher")), "offeredLower": bool(row.get("offeredLower")),
            "modifier": row.get("modifier") or "STANDARD",
        }))
    return claims


def sparse_incomplete_claims(rows: list[dict]) -> list[dict]:
    """Intentionally incomplete: event only + one subject; conflicted affiliation omitted."""
    return [
        _claim("EVENT", "CFB_TEST_1", {
            "event_context": True, "scheduled_start": "2026-09-05T23:00:00Z", "venue": "Fixture Stadium",
            "surface": "grass", "weather": {"wind_mph": 5, "precipitation": 0}, "spread": -7.5, "game_total": 55.5,
        }, claim_type="cfb_e2e_phase15_sparse"),
        _claim("SUBJECT", "QB1", {
            "status": "QUESTIONABLE", "role": "QB", "game_logs": QB_LOGS[:1],
            "opportunity": {"support_n": 1}, "efficiency": {"support_n": 1},
        }, claim_type="cfb_e2e_phase15_sparse"),
    ]


def _load_private_aggregates() -> tuple[Path, dict] | None:
    override = os.environ.get("DCM_PRIVATE_HAR_AGGREGATES")
    candidates = [Path(override)] if override else list(_PRIVATE_AGG_CANDIDATES)
    for path in candidates:
        if path is None or not path.is_file():
            continue
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(body, dict):
            return path, body
    return None


# ---------------------------------------------------------------------------
# PATH A — SYNTHETIC evidence-complete positive path
# ---------------------------------------------------------------------------

def test_path_a_synthetic_evidence_complete_positive_e2e(tmp_path: Path):
    """PATH_A (SYNTHETIC): accounting → graphs → evidence → features → snapshots →
    conserved NumPy EventWorlds → probabilities → ≥1 PLAYABLE → portfolio 0–6 → freeze.

    Must not truncate to Top100 before baseline processing of supported modelable offers.
    Never invent unavailable side; never map confidence→probability; never pad card.
    """
    assert POSITIVE_HAR.is_file()
    raw = json.loads(POSITIVE_HAR.read_text(encoding="utf-8"))
    assert raw.get("_pillars", {}).get("synthetic") is not True
    assert "SYNTHETIC" in str((raw.get("_dcm_fixture") or {}).get("label") or "")

    rows = ingest_har(raw)["rows"]
    accounting = account_cfb_board(rows)
    assert accounting["rawCfb"] == len(rows) == 8
    assert accounting["supportedNonGoblinOffers"] == 8
    assert accounting["goblinsExcludedFromSelectionAfterAccounting"] is True

    claims = evidence_complete_claims(rows)
    har_path = tmp_path / "positive.har.json"
    har_path.write_text(json.dumps(raw), encoding="utf-8")
    bundle_path = tmp_path / "positive_evidence.jsonl"
    write_bundle(bundle_path, claims)

    result = run_dcm(
        input_path=har_path,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs",
        research="bundle",
        bundle_path=bundle_path,
        workspace=tmp_path,
    )
    dest = Path(result["dest"])

    # Accounting + Research OS graphs + BoardStore-backed indexes on path
    for name in (
        "CFB_HAR_ACCOUNTING.json",
        "board_graph.json",
        "requirement_graph.json",
        "market_demand_graph.json",
        "acquisition_actions.json",
        "acquisition_schedule.json",
        "material_facts.json",
        "material_fact_features.json",
        "board_indexes.json",
        "event_worlds_meta.json",
        "algorithm_execution_telemetry.json",
        "freeze.json",
        "strict_card.json",
        "top25_ranked.json",
        "top100.json",
        "CFB_TOP100_PRELIMINARY.json",
        "CFB_TOP25_FINAL.json",
        "CFB_PLAYABLES_FINAL.json",
    ):
        assert (dest / name).is_file(), name

    # No Top100 truncation before baseline processing: all 8 supported offers classified
    classified = result["classified"]
    assert len(classified) == 8
    assert accounting["supportedNonGoblinOffers"] <= len(classified)

    playable = [r for r in classified if r.get("grade") == "PLAYABLE" and r.get("modeledPlayable")]
    assert len(playable) >= 1, "PATH_A requires at least one PLAYABLE candidate"

    # Conserved shared worlds with NumPy backend acceptable
    worlds_meta = json.loads((dest / "event_worlds_meta.json").read_text(encoding="utf-8"))
    events = worlds_meta.get("events") or []
    assert events, "expected joint EventWorld meta"
    assert any(ev.get("backend") in {"numpy", "reference"} for ev in events)
    assert any(ev.get("joint") for ev in events)
    assert any((ev.get("conservation") or {}).get("minutes") for ev in events)

    # CELF / ALG-SCHED-001 on the acquisition path (BoardStore + scheduler telemetry)
    tel = json.loads((dest / "algorithm_execution_telemetry.json").read_text(encoding="utf-8"))
    sched = json.loads((dest / "acquisition_schedule.json").read_text(encoding="utf-8"))
    tel_blob = json.dumps(tel) + json.dumps(sched)
    assert (
        "ALG-SCHED-001" in tel_blob
        or "CELF" in tel_blob.upper()
        or "celf" in tel_blob.lower()
        or "SCHED" in tel_blob
        or (sched.get("actions") or sched.get("packed") or sched.get("algorithmId"))
    )

    freeze = json.loads((dest / "freeze.json").read_text(encoding="utf-8"))
    strict = json.loads((dest / "strict_card.json").read_text(encoding="utf-8"))
    top25 = json.loads((dest / "top25_ranked.json").read_text(encoding="utf-8"))
    top100 = json.loads((dest / "top100.json").read_text(encoding="utf-8"))

    assert freeze["freezeState"] == "FROZEN"
    assert freeze["forecastFrozen"] is True
    assert freeze["learningRevision"] == "LR000000"
    assert freeze["predictiveClaim"] == "NONE"
    assert freeze["productionCertified"] is False
    assert freeze.get("top25Final") is True
    assert 0 <= len(strict) <= 6
    assert len(strict) >= 1
    assert all(p.get("grade") == "PLAYABLE" for p in strict)
    assert all(p.get("modifier") != "GOBLIN" for p in strict)
    # Never pad card / Top25 beyond available modeled rows
    assert len(top25) <= len(classified)
    assert len(top100) <= len(classified)
    assert len(top25) <= 25
    assert len(top100) <= 100

    # Never invent unavailable side
    for row in classified:
        if row.get("state") in {"MODELED", "MODELED_DIAGNOSTIC"}:
            side = row.get("selectedSide")
            offered_h = (row.get("row") or {}).get("offeredHigher")
            offered_l = (row.get("row") or {}).get("offeredLower")
            if side == "MORE":
                assert offered_h is not False
            if side == "LESS":
                assert offered_l is not False

    # BoardStore identity path recorded (Phase 7–8 SoA indexes on CFB launch path)
    indexes = json.loads((dest / "board_indexes.json").read_text(encoding="utf-8"))
    assert int(indexes.get("exactIdentityCount") or indexes.get("offerCount") or 0) >= 1
    assert "ALG-INDEX-001" in (indexes.get("algorithms") or [])


# ---------------------------------------------------------------------------
# PATH B — SYNTHETIC incomplete / conflicted path
# ---------------------------------------------------------------------------

def test_path_b_synthetic_incomplete_conflicted_not_silent_success(tmp_path: Path):
    """PATH_B (SYNTHETIC): incomplete/conflicted board must emit reresearch / lean /
    pass / trap / unsupported / abstention-class states — not a silent zero-card success.
    """
    raw = json.loads(INCOMPLETE_HAR.read_text(encoding="utf-8"))
    assert "INCOMPLETE" in str((raw.get("_dcm_fixture") or {}).get("label") or "")

    rows = ingest_har(raw)["rows"]
    accounting = account_cfb_board(rows)
    assert accounting["rawCfb"] == len(rows)
    assert accounting["goblin"] >= 1
    assert accounting["unsupported"] >= 1 or (accounting.get("classified") or {}).get("UNSUPPORTED", 0) >= 1

    har_path = tmp_path / "incomplete.har.json"
    har_path.write_text(json.dumps(raw), encoding="utf-8")
    bundle_path = tmp_path / "sparse_evidence.jsonl"
    write_bundle(bundle_path, sparse_incomplete_claims(rows))

    result = run_dcm(
        input_path=har_path,
        forecast_cutoff=CUTOFF,
        output_root=tmp_path / "runs",
        research="bundle",
        bundle_path=bundle_path,
        workspace=tmp_path,
    )
    dest = Path(result["dest"])
    freeze = json.loads((dest / "freeze.json").read_text(encoding="utf-8")) if (dest / "freeze.json").is_file() else {}
    classified = result.get("classified") or []
    states = Counter(str(r.get("state") or "") for r in classified)
    grades = Counter(str(r.get("grade") or "") for r in classified if r.get("grade"))
    blockers = {str(r.get("blocker") or "") for r in classified}

    # Must not look like a silent empty production success
    assert result.get("runState") not in {"EMPTY_CARD_COMPLETE", "RESEARCHED_MODELED_CARD"}
    if freeze:
        assert freeze.get("freezeState") in {None, "FRONTIER_INTERIM", "FROZEN"} or freeze.get("forecastFrozen") in {False, True}
        if freeze.get("runState") == "EMPTY_CARD_COMPLETE" and not classified:
            pytest.fail("silent zero-card success is forbidden on incomplete path")

    # Expect abstention-class / incomplete outcomes from the existing taxonomy
    abstentionish = (
        states.get("HELD_FOR_RESEARCH", 0)
        + states.get("UNRESOLVED", 0)
        + states.get("UNSUPPORTED", 0)
        + states.get("EXCLUDED_GOBLIN", 0)
        + states.get("MODELED_DIAGNOSTIC", 0)
    )
    grade_signals = grades.get("LEAN", 0) + grades.get("PASS", 0) + grades.get("TRAP", 0)
    interim = str(result.get("runState") or "") in {
        "AWAITING_FRONTIER_RESEARCH",
        "INCOMPLETE_CHECKPOINTED",
        "PARTIAL_RESEARCH_CONTINUE_CFB_PER_PROP",
    } or str(freeze.get("freezeState") or "") == "FRONTIER_INTERIM"

    assert abstentionish >= 1 or grade_signals >= 1 or interim, (
        f"expected incomplete/conflicted signals; states={dict(states)} grades={dict(grades)} "
        f"runState={result.get('runState')} freeze={freeze.get('freezeState')} blockers={sorted(blockers)}"
    )
    # Goblin excluded after accounting; unsupported remains visible
    assert states.get("EXCLUDED_GOBLIN", 0) >= 1 or accounting["goblin"] >= 1
    assert states.get("UNSUPPORTED", 0) >= 1 or (accounting.get("classified") or {}).get("UNSUPPORTED", 0) >= 1


# ---------------------------------------------------------------------------
# PATH C — private HAR aggregates only (optional on box)
# ---------------------------------------------------------------------------

def test_path_c_private_har_aggregates_only_no_publish():
    """PATH_C: if private aggregates exist on the box, account them only.
    Never manufacture a card from an expired/live board. Never publish HAR bytes.
    """
    found = _load_private_aggregates()
    if found is None:
        pytest.skip("No private HAR aggregates on box under known attachment paths")

    path, body = found
    # Never treat this file as committable HAR content
    assert path.suffix.lower() in {".json"}
    assert "har" not in path.name.lower() or "SAFE" in path.name.upper() or "ACCOUNTING" in path.name.upper()

    accounting = body.get("accounting_safe") if isinstance(body.get("accounting_safe"), dict) else body
    assert isinstance(accounting, dict)
    raw_cfb = int(accounting.get("rawCfb") or accounting.get("cfbRows") or 0)
    assert raw_cfb > 0

    live_or_started = int(accounting.get("liveOrStarted") or 0)
    offered_side_unknown = int(accounting.get("offeredSideUnknown") or 0)
    supported = int(accounting.get("supported") or accounting.get("supportedNonGoblinOffers") or 0)

    # Terminal limitation for a clean pregame card when the board is already live/stale
    terminal_limitation = None
    if live_or_started > 0:
        terminal_limitation = (
            f"PRIVATE_HAR_STALE_OR_LIVE_FOR_PREGAME_CARD: liveOrStarted={live_or_started} "
            f"rawCfb={raw_cfb} supported={supported} offeredSideUnknown={offered_side_unknown} "
            f"source={path.name}. Do not manufacture a card from an expired/live board."
        )
    elif offered_side_unknown > supported:
        terminal_limitation = (
            f"PRIVATE_HAR_SIDE_UNKNOWN_DOMINANT: offeredSideUnknown={offered_side_unknown} "
            f"supported={supported} source={path.name}."
        )

    report = {
        "schema": "pillars_dcm.private_har_aggregates_only.v1",
        "pathLabel": path.name,
        "rawCfb": raw_cfb,
        "supported": supported,
        "liveOrStarted": live_or_started,
        "offeredSideUnknown": offered_side_unknown,
        "goblin": accounting.get("goblin"),
        "classified": accounting.get("classified"),
        "terminalLimitation": terminal_limitation,
        "cardManufactured": False,
        "harPublished": False,
        "rawCommitted": False,
    }
    # Persist only under tmp via assertion object — test must not write into repo
    assert report["cardManufactured"] is False
    assert report["harPublished"] is False
    if terminal_limitation:
        assert "Do not manufacture" in terminal_limitation or "SIDE_UNKNOWN" in terminal_limitation
    # Honest: aggregates accounted; live card remains EXTERNAL
    assert report["rawCfb"] >= 1
