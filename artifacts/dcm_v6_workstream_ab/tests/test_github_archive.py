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
    scan_for_secrets,
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
    frozen_forecast_hash: str | None = "freezehash",
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
        "frozenForecastHash": frozen_forecast_hash,
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
    hashes_payload = {"boardHash": "boardhash", "harSha256": "abc123"}
    if frozen_forecast_hash:
        hashes_payload["frozenForecastHash"] = frozen_forecast_hash
    _write_json(dest / "hashes.json", hashes_payload)
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
            "observed_at": "2026-08-28T16:00:00Z",
            "published_at": "2026-08-28T16:00:00Z",
        }
    )
    dest = _fake_dest(tmp_path / "RUN_COMPLETE", claims=claims, synthetic=False, evidence_mode="PRODUCTION")
    ev = evaluate_pick_evidence(_slim_pick(), claims, _requests())
    assert ev["coverage"]["complete"] is True
    assert ev["hallucinationRisk"] is False
    assert "claim-player-1" in ev["coveringClaimHashes"]
    assert ev["urls"]

    audit = build_run_audit(dest)
    assert audit["modelRunCertified"] is True
    assert audit["selectionCertified"] is True
    assert audit["evidenceCoverageCertified"] is True
    assert audit["locksCertified"] is True
    assert audit["hallucinationRisk"] is False
    assert audit["predictiveValidationEarned"] is False
    assert audit["productionRootCertified"] is False
    assert audit["hashCertifiedPythonFreeze"] is True
    assert locks_certified(audit) is True


def test_fixture_evidence_mode_on_live_har_fails_gate():
    audit = {
        "runState": "COMPLETE_FROZEN",
        "completedStages": ["RESEARCH", "MODEL", "RANK", "FREEZE"],
        "softwareE2eComplete": True,
        "synthetic": False,
        "evidenceMode": "fixture",
        "cardSize": 0,
        "claimCount": 3,
        "picks": [],
        "hallucinationRisk": False,
        "frozenForecastHash": "freezehash",
        "learningRevision": "LR000000",
        "predictiveClaim": "NONE",
    }
    assert locks_certified(audit) is False
    from dcm.runtime.github_archive import compute_certification
    flags = compute_certification(audit, research_ran=True)
    assert flags["modelRunCertified"] is False
    assert flags["locksCertified"] is False


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
    assert "## Card" in text
    assert "## Failures" in text
    assert "modelRunCertified" in text
    assert (dest / "audit" / "pick_evidence.json").is_file()
    assert (dest / "audit" / "archive_manifest.json").is_file()


def test_push_to_github_commits_without_network(tmp_path: Path, monkeypatch):
    dest = _fake_dest(
        tmp_path / "RUN_GIT",
        claims=[_player_claim(), _event_claim(), _market_claim()],
        evidence_mode="PRODUCTION",
    )
    build_run_audit(dest)
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "noconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(home / "nosystem"))
    for key in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "GIT_AUTHOR_DATE",
        "GIT_COMMITTER_DATE",
    ):
        monkeypatch.delenv(key, raising=False)
    env = os.environ.copy()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, env=env)
    (repo / "audit").mkdir()
    (repo / "audit" / "README.md").write_text("# audit\n", encoding="utf-8")
    subprocess.run(["git", "add", "audit/README.md"], cwd=repo, check=True, capture_output=True, env=env)
    init_commit = subprocess.run(
        ["git", "-c", "user.name=init", "-c", "user.email=init@example.com", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
        env=env,
        text=True,
    )
    assert init_commit.returncode == 0, init_commit.stderr
    pack = materialize_github_pack(dest, repo)
    append_index(repo, {"runId": dest.name, "path": f"audit/runs/{dest.name}"})
    result = push_to_github(repo, dest.name, push=False)
    assert result.get("error") is None, result
    assert result["pushed"] is False
    assert result["commit"]
    assert result["path"] == f"audit/runs/{dest.name}"
    assert pack.is_dir()
    log = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=repo, capture_output=True, text=True, check=True, env=env)
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

def test_manual_research_card_is_not_model_run_certified(tmp_path: Path):
    claims = [
        _player_claim(),
        _event_claim(),
        _market_claim(),
        {
            "semantic_scope": "OFFER",
            "scope_id": PROJ_ID,
            "claim_value": {"offer_recorded": True},
            "claim_hash": "claim-offer-1",
            "url": "https://api.prizepicks.com/projections",
            "observed_at": "2026-08-28T16:00:00Z",
            "published_at": "2026-08-28T16:00:00Z",
        },
    ]
    dest = _fake_dest(
        tmp_path / "RUN_MANUAL",
        claims=claims,
        run_state="MANUAL_RESEARCH_CARD",
        evidence_mode="manual_research",
        software_e2e=False,
        frozen_forecast_hash=None,
        stages=["RESEARCH"],
    )
    audit = build_run_audit(dest)
    assert audit["evidenceCoverageCertified"] is True
    assert audit["modelRunCertified"] is False
    assert audit["selectionCertified"] is False
    assert audit["hashCertifiedPythonFreeze"] is False
    assert audit["locksCertified"] is False
    assert locks_certified(audit) is False


def test_set_cookie_dest_file_is_not_copied(tmp_path: Path):
    dest = _fake_dest(
        tmp_path / "RUN_SECRET",
        claims=[_player_claim(), _event_claim(), _market_claim()],
        evidence_mode="PRODUCTION",
    )
    leak = dest / "MODEL_CONFIG.json"
    leak.write_text('{"headers": "Set-Cookie: session=abc123"}\n', encoding="utf-8")
    assert scan_for_secrets(leak)
    build_run_audit(dest)
    repo = tmp_path / "repo"
    repo.mkdir()
    pack = materialize_github_pack(dest, repo)
    names = {p.name for p in pack.iterdir()}
    assert "MODEL_CONFIG.json" not in names
    assert not any("Set-Cookie" in p.read_text(encoding="utf-8", errors="ignore") for p in pack.iterdir() if p.is_file())


def test_researched_modeled_card_is_python_freeze_certified(tmp_path: Path):
    """Three-layer modeled card is a Python freeze even while production root stays closed."""
    claims = [
        _player_claim(),
        _event_claim(),
        _market_claim(),
        {
            "semantic_scope": "OFFER",
            "scope_id": PROJ_ID,
            "claim_value": {"offer_recorded": True},
            "claim_hash": "claim-offer-1",
            "url": "https://api.prizepicks.com/projections",
            "observed_at": "2026-08-28T16:00:00Z",
            "published_at": "2026-08-28T16:00:00Z",
        },
    ]
    dest = _fake_dest(
        tmp_path / "RUN_MODELED_CARD",
        claims=claims,
        run_state="RESEARCHED_MODELED_CARD",
        evidence_mode="PRODUCTION",
        synthetic=False,
        software_e2e=True,
        frozen_forecast_hash="python-freeze-hash",
        stages=["RESEARCH", "MODEL", "RANK", "PORTFOLIO", "FREEZE"],
    )
    audit = build_run_audit(dest)
    assert audit["modelRunCertified"] is True
    assert audit["hashCertifiedPythonFreeze"] is True
    assert audit["productionRootCertified"] is False
    assert audit["predictiveValidationEarned"] is False


def test_locks_certified_is_derived_alias_not_primary():
    """locksCertified is a retired derived alias, never a primary cert flag."""
    from dcm.runtime.github_archive import compute_certification

    flags = compute_certification(
        {
            "runState": "COMPLETE_FROZEN",
            "completedStages": ["RESEARCH", "MODEL", "RANK", "FREEZE"],
            "softwareE2eComplete": True,
            "synthetic": False,
            "evidenceMode": "PRODUCTION",
            "cardSize": 0,
            "claimCount": 3,
            "frozenForecastHash": "abc",
            "learningRevision": "LR000000",
            "predictiveClaim": "NONE",
            "picks": [],
        },
        research_ran=True,
    )
    assert flags["locksCertified"] == (
        bool(flags["modelRunCertified"])
        and bool(flags["selectionCertified"])
        and bool(flags["evidenceCoverageCertified"])
    )
    # Alias stays false unless all three primary flags are true.
    incomplete = compute_certification(
        {
            "runState": "COMPLETE_FROZEN",
            "completedStages": ["RESEARCH", "MODEL", "RANK", "FREEZE"],
            "softwareE2eComplete": True,
            "synthetic": False,
            "evidenceMode": "fixture",
            "cardSize": 1,
            "claimCount": 3,
            "frozenForecastHash": "abc",
            "learningRevision": "LR000000",
            "predictiveClaim": "NONE",
            "picks": [{"coverage": {"complete": False}}],
        },
        research_ran=True,
    )
    assert incomplete["modelRunCertified"] is False
    assert incomplete["locksCertified"] is False


def test_archive_copies_explanations_graph_and_feature_store_when_present(tmp_path: Path):
    dest = _fake_dest(
        tmp_path / "RUN_EXPLAIN",
        claims=[_player_claim(), _event_claim(), _market_claim()],
        evidence_mode="PRODUCTION",
    )
    (dest / "prop_explanations.jsonl").write_text(
        json.dumps({"projectionId": PROJ_ID, "drivers": []}) + "\n", encoding="utf-8"
    )
    (dest / "evidence_graph.json").write_text(json.dumps({"nodes": [], "edges": [], "contentHash": "g"}) + "\n", encoding="utf-8")
    (dest / "feature_store_manifest.json").write_text(json.dumps({"contentHash": "f", "n": 1}) + "\n", encoding="utf-8")
    (dest / "feature_store.jsonl").write_text("{}\n", encoding="utf-8")
    build_run_audit(dest)
    repo = tmp_path / "repo"
    repo.mkdir()
    pack = materialize_github_pack(dest, repo)
    names = {p.name for p in pack.iterdir()}
    assert "prop_explanations.jsonl" in names
    assert "evidence_graph.json" in names
    assert "feature_store_manifest.json" in names
    assert "feature_store.jsonl" in names
    assert not list(pack.rglob("*.har"))


def test_cookie_header_dest_file_is_not_copied(tmp_path: Path):
    dest = _fake_dest(
        tmp_path / "RUN_COOKIE",
        claims=[_player_claim(), _event_claim(), _market_claim()],
        evidence_mode="PRODUCTION",
    )
    leak = dest / "hashes.json"
    original = leak.read_text(encoding="utf-8")
    leak.write_text('{"Cookie": "session=abc123; Path=/"}\n', encoding="utf-8")
    assert scan_for_secrets(leak)
    # Restore a clean hashes.json so the pack still has hashes, and leak via another pack file.
    leak.write_text(original, encoding="utf-8")
    cookie_file = dest / "MODEL_CONFIG.json"
    cookie_file.write_text('{"Cookie": "session=abc123"}\n', encoding="utf-8")
    assert scan_for_secrets(cookie_file)
    build_run_audit(dest)
    repo = tmp_path / "repo"
    repo.mkdir()
    pack = materialize_github_pack(dest, repo)
    names = {p.name for p in pack.iterdir()}
    assert "MODEL_CONFIG.json" not in names
    for path in pack.iterdir():
        if path.is_file():
            body = path.read_text(encoding="utf-8", errors="ignore")
            assert "Cookie" not in body
            assert "Set-Cookie" not in body
