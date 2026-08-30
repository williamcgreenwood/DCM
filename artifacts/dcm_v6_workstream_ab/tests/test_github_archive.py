"""Fast unit tests for GitHub-verifiable run audit archive. No live network, no git push."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from dcm.runtime.github_archive import (
    build_run_audit,
    evaluate_pick_evidence,
    locks_certified,
    materialize_github_pack,
    pick_to_requests,
    push_to_github,
    append_index,
)


PLAYER_ID = "P1"
EVENT_ID = "E1"
DEF_ID = "prizepicks|NBA|pts|FULL_GAME"
PROJ_ID = "proj-1"


def _player_claim(**overrides) -> dict:
    value = {
        "status": "ACTIVE",
        "role": "starter",
        "game_logs": [{"minutes": 30}, {"minutes": 32}, {"minutes": 34}],
        "opportunity": {"support_n": 3, "minutes_mean": 32.0},
        "efficiency": {"support_n": 3},
    }
    value.update(overrides)
    return {
        "semantic_scope": "PLAYER",
        "scope_id": PLAYER_ID,
        "claim_value": value,
        "claim_hash": "claim-player-1",
        "url": "https://stats.nba.com/player/P1",
        "observed_at": "2026-08-28T16:00:00Z",
        "published_at": "2026-08-28T16:00:00Z",
    }


def _event_claim() -> dict:
    return {
        "semantic_scope": "EVENT",
        "scope_id": EVENT_ID,
        "claim_value": {
            "starters_known": True,
            "scheduled_start": "2026-08-29T23:00:00Z",
            "environment": "indoor",
            "event_context": "pre_game",
        },
        "claim_hash": "claim-event-1",
        "url": "https://cdn.nba.com/static/json/liveData/scoreboard.json",
        "observed_at": "2026-08-28T16:00:00Z",
        "published_at": "2026-08-28T16:00:00Z",
    }


def _market_claim() -> dict:
    return {
        "semantic_scope": "MARKET_DEFINITION",
        "scope_id": DEF_ID,
        "claim_value": {"definition_verified": True},
        "claim_hash": "claim-market-1",
        "url": "https://api.prizepicks.com/projections",
        "observed_at": "2026-08-28T16:00:00Z",
        "published_at": "2026-08-28T16:00:00Z",
    }


def _requests() -> list[dict]:
    return [
        {
            "request_id": "REQ_P",
            "scope": "PLAYER",
            "scope_id": PLAYER_ID,
            "need": "status_role_logs_opportunity_efficiency",
            "name": "Player One",
            "league": "NBA",
        },
        {
            "request_id": "REQ_E",
            "scope": "EVENT",
            "scope_id": EVENT_ID,
            "need": "start_venue_starters_environment",
            "label": "A @ B",
            "league": "NBA",
            "sportFamily": "basketball",
        },
        {
            "request_id": "REQ_M",
            "scope": "MARKET_DEFINITION",
            "scope_id": DEF_ID,
            "need": "exact_stat_definition",
            "market": "pts",
            "league": "NBA",
            "boardId": "FULL_GAME",
        },
        {
            "request_id": "REQ_O",
            "scope": "OFFER",
            "scope_id": PROJ_ID,
            "need": "line_sides_modifier",
            "market": "pts",
            "line": 20.5,
            "playerId": PLAYER_ID,
            "definition_id": DEF_ID,
        },
    ]


def _slim_pick() -> dict:
    return {
        "projectionId": PROJ_ID,
        "player": "Player One",
        "playerId": PLAYER_ID,
        "event": "A @ B",
        "eventId": EVENT_ID,
        "market": "pts",
        "line": 20.5,
        "direction": "MORE",
        "league": "NBA",
        "sportFamily": "basketball",
    }


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _fake_dest(
    dest: Path,
    *,
    claims: list[dict],
    card: list[dict] | None = None,
    run_state: str = "COMPLETE_FROZEN",
    evidence_mode: str = "PRODUCTION",
    synthetic: bool = False,
    card_size: int | None = None,
    software_e2e: bool = True,
    stages: list[str] | None = None,
) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    pick = _slim_pick()
    card = list(card) if card is not None else [pick]
    if card_size is None:
        card_size = len(card)
    freeze = {
        "runId": dest.name,
        "dcmVersion": "6.0.0+WSAB.E2E.PRODUCTION_PIPELINE.LR000000",
        "learningRevision": "LR000000",
        "predictiveClaim": "NONE",
        "runState": run_state,
        "forecastCutoff": "2026-08-29T00:00:00Z",
        "harSha256": "abc123",
        "boardHash": "boardhash",
        "frozenForecastHash": "freezehash",
        "researchComplete": True,
        "productionResearchComplete": evidence_mode == "PRODUCTION",
        "evidenceMode": evidence_mode,
        "researchRequested": 4,
        "playable": card_size,
        "cardSize": card_size,
        "softwareE2eComplete": software_e2e,
        "synthetic": synthetic,
    }
    _write_json(dest / "frozen_forecast.json", freeze)
    _write_json(dest / "freeze.json", freeze)
    _write_json(
        dest / "checkpoint.json",
        {
            "runId": dest.name,
            "forecastCutoff": "2026-08-29T00:00:00Z",
            "completedStages": stages or ["BOARD_FREEZE", "RESEARCH", "MODEL", "RANK", "PORTFOLIO", "FREEZE"],
        },
    )
    _write_json(dest / "strict_card.json", card)
    _write_json(dest / "research_requests.json", _requests())
    _write_jsonl(dest / "evidence_bundle.jsonl", claims)
    _write_json(dest / "hashes.json", {"boardHash": "boardhash", "harSha256": "abc123", "frozenForecastHash": "freezehash"})
    _write_json(dest / "input_manifest.json", {"harSha256": "abc123", "synthetic": synthetic})
    _write_json(dest / "accounting.json", {"playable": card_size, "cardSize": card_size})
    _write_json(dest / "board.json", {"contentHash": "boardhash", "rows": [{"projectionId": PROJ_ID}], "forecastCutoff": "2026-08-29T00:00:00Z", "accounting": {"raw_projection_rows": 1}})
    return dest


def test_pick_to_requests_matches_slim_fields():
    pick = {
        "projectionId": PROJ_ID,
        "player": "Player One",
        "event": "A @ B",
        "market": "pts",
        "league": "NBA",
    }
    matched = pick_to_requests(pick, _requests())
    scopes = {r["scope"] for r in matched}
    assert "PLAYER" in scopes
    assert "EVENT" in scopes
    assert "MARKET_DEFINITION" in scopes
    assert "OFFER" in scopes


def test_lock_without_player_claims_is_not_certified(tmp_path: Path):
    dest = _fake_dest(tmp_path / "RUN_NO_PLAYER", claims=[_event_claim(), _market_claim()])
    pick = _slim_pick()
    ev = evaluate_pick_evidence(pick, [_event_claim(), _market_claim()], _requests())
    assert ev["hallucinationRisk"] is True
    assert ev["coverage"]["complete"] is False
    assert "PLAYER_STATUS" in ev["coverage"]["missing"] or "EVIDENCE_CLAIM" in ev["coverage"]["missing"]

    audit = build_run_audit(dest)
    assert audit["hallucinationRisk"] is True
    assert audit["locksCertified"] is False
    assert locks_certified(audit) is False


def test_complete_player_event_market_definition_is_certified(tmp_path: Path):
    claims = [_player_claim(), _event_claim(), _market_claim()]
    # OFFER is matched from slim projectionId; cover it so the lock trio+offer is complete.
    claims.append(
        {
            "semantic_scope": "OFFER",
            "scope_id": PROJ_ID,
            "claim_value": {"offer_recorded": True},
            "claim_hash": "claim-offer-1",
            "url": "https://api.prizepicks.com/projections",
        }
    )
    dest = _fake_dest(tmp_path / "RUN_COMPLETE", claims=claims, synthetic=False, evidence_mode="PRODUCTION")
    ev = evaluate_pick_evidence(_slim_pick(), claims, _requests())
    assert ev["coverage"]["complete"] is True
    assert ev["hallucinationRisk"] is False
    assert "claim-player-1" in ev["coveringClaimHashes"]
    assert ev["urls"]

    audit = build_run_audit(dest)
    assert audit["locksCertified"] is True
    assert audit["hallucinationRisk"] is False
    assert locks_certified(audit) is True


def test_fixture_evidence_mode_on_live_har_fails_gate():
    audit = {
        "runState": "COMPLETE_FROZEN",
        "completedStages": ["RESEARCH", "FREEZE"],
        "softwareE2eComplete": True,
        "synthetic": False,
        "evidenceMode": "fixture",
        "cardSize": 0,
        "claimCount": 3,
        "picks": [],
        "hallucinationRisk": False,
    }
    assert locks_certified(audit) is False


def test_empty_card_can_certify_when_research_ran(tmp_path: Path):
    dest = _fake_dest(
        tmp_path / "RUN_EMPTY",
        claims=[_player_claim(), _event_claim(), _market_claim()],
        card=[],
        card_size=0,
        run_state="EMPTY_CARD_COMPLETE",
        evidence_mode="PRODUCTION",
        synthetic=False,
    )
    audit = build_run_audit(dest)
    assert audit["cardSize"] == 0
    assert audit["hallucinationRisk"] is False
    assert audit["locksCertified"] is True


def test_card_with_incomplete_evidence_is_not_certified(tmp_path: Path):
    dest = _fake_dest(
        tmp_path / "RUN_INCOMPLETE_LOCK",
        claims=[_player_claim(status="", game_logs=[])],
        evidence_mode="PRODUCTION",
        synthetic=False,
    )
    audit = build_run_audit(dest)
    assert audit["cardSize"] > 0
    assert audit["locksCertified"] is False
    assert audit["hallucinationRisk"] is True


def test_materialize_github_pack_never_copies_har_or_sqlite(tmp_path: Path):
    dest = _fake_dest(
        tmp_path / "RUN_PACK",
        claims=[_player_claim(), _event_claim(), _market_claim()],
        evidence_mode="PRODUCTION",
    )
    (dest / "capture.har").write_text("NOT_A_REAL_HAR", encoding="utf-8")
    (dest / "index.sqlite").write_bytes(b"sqlite")
    (dest / "population_full.jsonl").write_text("{}\n", encoding="utf-8")
    (dest / "full_population.jsonl").write_text("{}\n", encoding="utf-8")
    (dest / "worlds").mkdir()
    (dest / "worlds" / "w0.json").write_text("{}", encoding="utf-8")
    (dest / "session_cookie.json").write_text("{}", encoding="utf-8")
    build_run_audit(dest)
    repo = tmp_path / "repo"
    repo.mkdir()
    pack = materialize_github_pack(dest, repo)
    names = {p.name for p in pack.iterdir()}
    assert "capture.har" not in names
    assert "index.sqlite" not in names
    assert "population_full.jsonl" not in names
    assert "full_population.jsonl" not in names
    assert "session_cookie.json" not in names
    assert "worlds" not in names
    assert not list(pack.rglob("*.har"))
    assert not list(pack.rglob("*.sqlite"))
    assert (pack / "RUN_AUDIT.md").is_file()
    assert (pack / "pick_evidence.json").is_file()
    assert (pack / "archive_manifest.json").is_file()
    assert (pack / "hashes.json").is_file()
    assert (pack / "strict_card.json").is_file()
    assert (pack / "evidence_bundle.jsonl").is_file()


def test_build_run_audit_writes_run_audit_md(tmp_path: Path):
    dest = _fake_dest(tmp_path / "RUN_MD", claims=[_player_claim(), _event_claim(), _market_claim()])
    audit = build_run_audit(dest)
    md = dest / "audit" / "RUN_AUDIT.md"
    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    assert f"# DCM run {audit['runId']}" in text
    assert "learningRevision" in text
    assert "LR000000" in text
    assert "NONE" in text
    assert "## Locks" in text
    assert "## Failures" in text
    assert (dest / "audit" / "pick_evidence.json").is_file()
    assert (dest / "audit" / "archive_manifest.json").is_file()


def test_push_to_github_commits_without_network(tmp_path: Path):
    dest = _fake_dest(
        tmp_path / "RUN_GIT",
        claims=[_player_claim(), _event_claim(), _market_claim()],
        evidence_mode="PRODUCTION",
    )
    build_run_audit(dest)
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "williamcgreenwood",
            "GIT_AUTHOR_EMAIL": "311696354+williamcgreenwood@users.noreply.github.com",
            "GIT_COMMITTER_NAME": "williamcgreenwood",
            "GIT_COMMITTER_EMAIL": "311696354+williamcgreenwood@users.noreply.github.com",
        }
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, env=env)
    (repo / "audit").mkdir()
    (repo / "audit" / "README.md").write_text("# audit\n", encoding="utf-8")
    subprocess.run(["git", "add", "audit/README.md"], cwd=repo, check=True, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, env=env)
    pack = materialize_github_pack(dest, repo)
    append_index(repo, {"runId": dest.name, "path": f"audit/runs/{dest.name}"})
    result = push_to_github(repo, dest.name, push=False)
    assert result.get("error") is None, result
    assert result["pushed"] is False
    assert result["commit"]
    assert result["path"] == f"audit/runs/{dest.name}"
    assert pack.is_dir()
    log = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=repo, capture_output=True, text=True, check=True)
    assert dest.name in log.stdout


def test_gitignore_still_ignores_har_under_audit_runs():
    repo = Path(__file__).resolve().parents[3]
    gitignore = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "!audit/" in gitignore
    assert "!audit/runs/**" in gitignore
    allow_idx = gitignore.find("!audit/")
    # Global *.har (not dcm_v6/INBOX/*.har) must follow the audit allowlist.
    har_idx = gitignore.find("\n*.har\n", allow_idx)
    assert allow_idx != -1 and har_idx != -1
    assert allow_idx < har_idx
    check = subprocess.run(
        ["git", "check-ignore", "-v", "audit/runs/RUN_X/capture.har"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert "*.har" in check.stdout
