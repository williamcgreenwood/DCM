"""P7 host-native CLI/API: doctor, prepare, next-research, evidence-import, coverage, report."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dcm.chat import HostSession, doctor
from dcm.chat.cli import main as host_main
from dcm.chat.evidence_import import observation_to_claim
from dcm.research.scopes import CANONICAL_SCOPES


CUTOFF = "2026-08-29T16:00:00Z"
ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "fixtures" / "synthetic_har.json"


def test_doctor_reports_identity_and_does_not_claim_performance():
    report = doctor()
    assert report["software"]
    assert report["learningRevision"] == "LR000000"
    assert report["predictiveClaim"] == "NONE"
    assert report["probabilityEngine"] == "python-dcm"
    assert report["hostComputesProbabilities"] is False
    assert report["hostPerformanceCertified"] is False
    assert report["algorithmConstitutionVersion"] == "DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903"
    assert report["algorithmConstitution"]["sha256"]
    assert report["algorithmConstitution"]["registrySha256"]
    assert "ALGORITHM_CONSTITUTION_UNAVAILABLE" not in (report.get("blockers") or [])
    assert report["v1HashRewritten"] is False
    assert "prepare" in report["commands"]
    assert report["sourceCatalog"]["secretsInRepo"] is False
    assert report["sourceCatalog"]["sourceCount"] >= 5


def test_cli_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        host_main(["--help"])
    assert exc.value.code == 0


def test_cli_doctor(capsys):
    code = host_main(["doctor"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["probabilityEngine"] == "python-dcm"
    assert payload["learningRevision"] == "LR000000"


def test_host_session_prepare_next_research_import_coverage_report(tmp_path: Path):
    session = HostSession.prepare(
        har=None,
        run_root=tmp_path / "RUNS",
        cutoff=CUTOFF,
        workspace=tmp_path,
        synthetic=True,
    )
    dest = session.dest
    for name in (
        "host_state.json",
        "run_manifest.json",
        "board.json",
        "accounting.json",
        "subject_offer_sets.json",
        "research_population_manifest.json",
        "research_dependency_graph.json",
        "sport_plugin_contract_registry.json",
        "evidence_coverage.json",
        "research_requests.json",
        "universal_host_research_plan.json",
        "universal_research_packets.json",
        "algorithm_execution_plan.json",
        "board_graph.json",
        "market_demand_graph.json",
        "requirement_graph.json",
        "acquisition_actions.json",
    ):
        assert (dest / name).is_file(), name
    plan = json.loads((dest / "algorithm_execution_plan.json").read_text())
    assert plan["constitutionVersion"] == "DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903"
    assert plan["researchMayBegin"] is True
    assert plan["planHash"]

    reqs = json.loads((dest / "research_requests.json").read_text())
    scopes = {r["scope"] for r in reqs}
    assert scopes <= set(CANONICAL_SCOPES)
    assert "PLAYER" not in scopes
    assert "TEAM" not in scopes

    batch = session.next_research_batch(max_entities=10)
    assert batch["schema"] == "pillars_dcm.host_research_batch.v1"
    assert batch["batching"] == "celf_acquisition_action_then_event_pack"
    assert "fanout" in batch["priorityFormula"]
    assert (dest / "host_research_batch.json").is_file()
    assert batch["selectedCount"] >= 1
    assert batch.get("algorithmSelection", {}).get("selectedAlgorithmId") == "ALG-SCHED-001"
    assert "ALG-SEARCH-019" in (batch.get("algorithmIds") or []) or batch.get("algorithmSelection"); legacy_plan = __import__("dcm.research.host_plan", fromlist=["build_host_research_plan"]).build_host_research_plan([{"scope": "PLAYER", "scope_id": "P_ALIAS", "need": "status_role_logs_opportunity_efficiency", "forecast_cutoff": CUTOFF, "league": "CFB", "request_id": "REQ_ALIAS", "priority_score": 1.0, "dependent_prop_count": 1}], unique_scopes={"PLAYER": 1}); assert {task["scope"] for task in legacy_plan["tasks"]} == {"SUBJECT"}; assert legacy_plan["uniqueScopes"]["SUBJECT"] == 1

    subject = next(r for r in reqs if r["scope"] == "SUBJECT")
    obs = {
        "sourceUrl": "https://www.wnba.com/player/test",
        "retrievedAt": "2026-08-28T12:00:00Z",
        "publishedAt": "2026-08-28T00:00:00Z",
        "entityRef": {"kind": "SUBJECT", "id": subject["scope_id"]},
        "evidenceType": "HISTORICAL_PERFORMANCE",
        "sourceLabel": "WNBA_OFFICIAL",
        "data": {
            "status": "ACTIVE",
            "role": "starter",
            "game_logs": [
                {"minutes": 30, "fga": 12, "date": "2026-08-20"},
                {"minutes": 28, "fga": 11, "date": "2026-08-22"},
                {"minutes": 32, "fga": 14, "date": "2026-08-24"},
            ],
            "opportunity": {"support_n": 3},
            "efficiency": {"support_n": 3},
        },
    }
    obs_path = tmp_path / "host_observations.jsonl"
    obs_path.write_text(json.dumps(obs) + "\n", encoding="utf-8")
    imported = session.import_evidence(obs_path)
    assert imported["imported"] == 1
    assert imported["hostInventedHashes"] is False
    assert imported["rejected"] == 0
    bundle = (dest / "evidence_bundle.jsonl").read_text(encoding="utf-8")
    claim = json.loads(bundle.splitlines()[0])
    assert claim["claim_hash"]
    assert claim["source_hash"]
    assert claim["semantic_scope"] == "SUBJECT"
    assert "reliability" in claim
    # Host did not supply hashes; engine computed them.
    assert "claim_hash" not in obs
    assert "source_hash" not in obs

    cov = session.coverage()
    assert "modelingPermitted" in cov
    assert "productionSelectionPermitted" in cov
    assert cov["semanticRule"]
    state = json.loads((dest / "host_state.json").read_text())
    assert state["coverageEvaluated"] is True
    assert state["hostComputesProbabilities"] is False

    report = session.report()
    assert report["schema"] == "pillars_dcm.chat_result.v1"
    assert report["probabilityEngine"] == "python-dcm"
    assert report["reliabilityIsNotProbability"] is True
    assert (dest / "chat_result.json").is_file()
    assert report["learningRevision"] == "LR000000"
    assert report["predictiveClaim"] == "NONE"


def test_observation_rejects_secret_url():
    try:
        observation_to_claim(
            {
                "sourceUrl": "https://user:pass@example.com/x",
                "retrievedAt": "2026-08-28T12:00:00Z",
                "entityRef": {"kind": "SUBJECT", "id": "P1"},
                "data": {},
            },
            cutoff=CUTOFF,
        )
        raise AssertionError("expected secret URL to fail")
    except ValueError as exc:
        assert "CREDENTIALS" in str(exc) or "SECRET" in str(exc)


def test_cli_prepare_synthetic(tmp_path: Path, capsys):
    code = host_main([
        "prepare",
        "--synthetic",
        "--cutoff",
        CUTOFF,
        "--run-root",
        str(tmp_path / "RUNS"),
        "--workspace",
        str(tmp_path),
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    dest = Path(payload["runDest"])
    assert (dest / "host_state.json").is_file()
    assert host_main(["next-research", "--run", str(dest), "--workspace", str(tmp_path)]) == 0
    assert host_main(["coverage", "--run", str(dest), "--workspace", str(tmp_path)]) == 0
    assert host_main(["report", "--run", str(dest), "--workspace", str(tmp_path)]) == 0
