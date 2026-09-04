"""HostSession: ChatGPT/Grok-native orchestration over the canonical runner.

This module never computes probabilities. It prepares, schedules research,
imports host observations, evaluates coverage, and delegates forecast/settle
to dcm.runner / dcm.settle.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from dcm.algorithms.constitution import ALGORITHM_CONSTITUTION_VERSION, constitution_identity
from dcm.chat.archive import archive_run, audit_run
from dcm.chat.contracts import REQUIRED_PREPARE_ARTIFACTS
from dcm.chat.evidence_import import import_observations
from dcm.chat.report import build_report
from dcm.chat.research_bridge import next_research_batch
from dcm.chat.state import default_host_state, read_json, utc_now, write_json
from dcm.research.coverage import coverage_report
from dcm.research.source_catalog import catalog_summary, load_source_catalog
from dcm.runner import run_dcm, DEFAULT_WORKSPACE
from dcm.runtime.mount_v541 import mount_default
from dcm.sports.common.plugin import REGISTRY as SPORT_REGISTRY
from dcm.version import EXPECTED_V1_HASH, LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE


def _git_commit() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    sha = (proc.stdout or "").strip()
    return sha if proc.returncode == 0 and sha else None


def doctor(*, release_manifest: Path | None = None, workspace: Path | None = None) -> dict[str, Any]:
    workspace = Path(workspace) if workspace is not None else DEFAULT_WORKSPACE
    mount = mount_default(workspace)
    catalog = catalog_summary()
    plugins = sorted(SPORT_REGISTRY.keys())
    release = {}
    if release_manifest and Path(release_manifest).is_file():
        try:
            release = json.loads(Path(release_manifest).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            release = {"error": "RELEASE_MANIFEST_UNREADABLE"}
    blockers: list[str] = []
    if mount.get("state") != "HASH_VERIFIED_EXTRACTED":
        blockers.append("PRODUCTION_ROOT_NOT_MOUNTED")
    if PREDICTIVE_CLAIM != "NONE":
        blockers.append("PREDICTIVE_CLAIM_UNEXPECTED")
    try:
        constitution = constitution_identity()
    except Exception as exc:  # doctor must still report identity
        constitution = {"error": str(exc)}
        blockers.append("ALGORITHM_CONSTITUTION_UNAVAILABLE")
    return {
        "schema": "pillars_dcm.host_doctor.v1",
        "software": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "algorithmConstitutionVersion": ALGORITHM_CONSTITUTION_VERSION,
        "algorithmConstitution": constitution,
        "gitCommit": _git_commit(),
        "expectedV1Hash": EXPECTED_V1_HASH,
        "v1HashRewritten": False,
        "probabilityEngine": "python-dcm",
        "hostComputesProbabilities": False,
        "sportPlugins": plugins,
        "sourceCatalog": catalog,
        "sourceCatalogHash": load_source_catalog().get("contentHash"),
        "mountState": mount.get("state"),
        "cacheStatus": "process_local_research_cache",
        "hostPerformanceCertified": False,
        "productionRootCertified": False,
        "blockers": blockers,
        "releaseManifest": release or None,
        "commands": [
            "doctor", "prepare", "next-research", "evidence-import", "coverage",
            "forecast", "report", "resume", "audit", "archive", "settle", "cfb-launch",
        ],
    }


class HostSession:
    """One run directory, one Python probability engine."""

    def __init__(self, dest: Path, *, workspace: Path | None = None):
        self.dest = Path(dest)
        self.workspace = Path(workspace) if workspace is not None else DEFAULT_WORKSPACE

    @classmethod
    def open(cls, run: Path, *, workspace: Path | None = None) -> "HostSession":
        dest = Path(run)
        if not dest.is_dir():
            raise FileNotFoundError(f"HOST_RUN_NOT_FOUND:{dest}")
        return cls(dest, workspace=workspace)

    @classmethod
    def prepare(
        cls,
        *,
        har: Path | None = None,
        run_root: Path,
        cutoff: str | None = None,
        cutoff_from_capture: bool = False,
        workspace: Path | None = None,
        synthetic: bool = False,
        research_shadow: bool = False,
        input_paths: list[Path] | None = None,
    ) -> "HostSession":
        if not synthetic and har is None and not input_paths:
            raise FileNotFoundError("HAR missing. Pass har= or input_paths= or synthetic=True.")
        result = run_dcm(
            input_path=har,
            input_paths=input_paths,
            forecast_cutoff=cutoff,
            output_root=Path(run_root),
            synthetic=synthetic,
            research="file",
            workspace=Path(workspace) if workspace is not None else DEFAULT_WORKSPACE,
            account_only=True,
            research_shadow=research_shadow,
            cutoff_from_capture=bool(cutoff_from_capture),
        )
        dest = Path(result["dest"])
        session = cls(dest, workspace=workspace)
        session._write_prepare_artifacts(result)
        return session

    def _host_state(self) -> dict[str, Any]:
        return read_json(self.dest / "host_state.json") or {}

    def _save_host_state(self, **updates: Any) -> dict[str, Any]:
        state = self._host_state() or default_host_state(self.dest)
        state.update(updates)
        state["updatedAt"] = utc_now()
        from dcm.contracts.hashes import content_hash
        state["contentHash"] = content_hash({k: v for k, v in state.items() if k != "contentHash"})
        write_json(self.dest / "host_state.json", state)
        return state

    def _write_prepare_artifacts(self, result: dict[str, Any]) -> None:
        board = read_json(self.dest / "board.json") or {}
        requests = read_json(self.dest / "research_requests.json") or []
        claims = read_json(self.dest / "evidence" / "claims.json") or []
        coverage = coverage_report(requests if isinstance(requests, list) else [], claims if isinstance(claims, list) else [])
        write_json(self.dest / "evidence_coverage.json", coverage)
        freeze = read_json(self.dest / "freeze.json") or {}
        manifest = {
            "schema": "pillars_dcm.run_manifest.v1",
            "runId": result.get("run_id") or freeze.get("runId") or self.dest.name,
            "runDest": str(self.dest),
            "runState": result.get("runState") or freeze.get("runState"),
            "accountOnly": True,
            "forecastCutoff": board.get("forecastCutoff"),
            "software": SOFTWARE,
            "learningRevision": LEARNING_REVISION,
            "predictiveClaim": PREDICTIVE_CLAIM,
            "probabilityEngine": "python-dcm",
            "checkpoint": str(self.dest / "checkpoint.json"),
        }
        write_json(self.dest / "run_manifest.json", manifest)
        self._save_host_state(
            **default_host_state(
                self.dest,
                extra={
                    "runId": manifest["runId"],
                    "forecastCutoff": manifest["forecastCutoff"],
                    "runState": manifest["runState"],
                    "lastCommand": "prepare",
                    "accountOnly": True,
                    "preparedArtifacts": [name for name in REQUIRED_PREPARE_ARTIFACTS if (self.dest / name).is_file()],
                },
            )
        )

    def next_research_batch(self, *, max_entities: int = 25, max_dependent_offers: int = 500) -> dict[str, Any]:
        batch = next_research_batch(
            self.dest,
            max_entities=max_entities,
            max_dependent_offers=max_dependent_offers,
            store_root=self.workspace / "dcm_v6" / "research_store",
        )
        state = self._host_state()
        self._save_host_state(
            lastCommand="next-research",
            researchLoopCount=int(state.get("researchLoopCount") or 0) + 1,
        )
        return batch

    def import_evidence(self, observations: Path) -> dict[str, Any]:
        result = import_observations(
            self.dest,
            Path(observations),
            store_root=self.workspace / "dcm_v6" / "research_store",
        )
        self._save_host_state(lastCommand="evidence-import", lastImport=result.get("imported"))
        return result

    def coverage(self) -> dict[str, Any]:
        requests = read_json(self.dest / "research_requests.json") or []
        claims = read_json(self.dest / "evidence" / "claims.json") or []
        if not claims:
            bundle = self.dest / "evidence_bundle.jsonl"
            if bundle.is_file():
                from dcm.research.provider import BundleProvider
                claims = BundleProvider(bundle).all_claims()
        coverage = coverage_report(requests if isinstance(requests, list) else [], claims if isinstance(claims, list) else [])
        batch = next_research_batch(
            self.dest,
            store_root=self.workspace / "dcm_v6" / "research_store",
        )
        modeling_permitted = bool(coverage.get("complete")) or bool(coverage.get("completeRequests"))
        mount = mount_default(self.workspace)
        production_selection_permitted = bool(coverage.get("complete")) and mount.get("state") == "HASH_VERIFIED_EXTRACTED"
        payload = {
            **coverage,
            "modelingPermitted": modeling_permitted,
            "productionSelectionPermitted": production_selection_permitted,
            "nextRecommendedBatch": {
                "selectedCount": batch.get("selectedCount"),
                "unresolvedCount": batch.get("unresolvedCount"),
                "eventBatchCount": batch.get("eventBatchCount"),
            },
            "semanticRule": "Coverage means required SportResearchSchema fields exist, not merely that a request returned something.",
        }
        write_json(self.dest / "evidence_coverage.json", payload)
        self._save_host_state(
            lastCommand="coverage",
            coverageEvaluated=True,
            modelingPermitted=modeling_permitted,
            productionSelectionPermitted=production_selection_permitted,
        )
        return payload

    def forecast(self, *, research: str = "bundle") -> dict[str, Any]:
        state = self._host_state()
        if not state.get("coverageEvaluated"):
            self.coverage()
        # Hydrate still-valid persistent claims into the run bundle before resume.
        next_research_batch(
            self.dest,
            store_root=self.workspace / "dcm_v6" / "research_store",
        )
        ck = self.dest / "checkpoint.json"
        if not ck.is_file():
            raise FileNotFoundError("CHECKPOINT_MISSING")
        bundle = self.dest / "evidence_bundle.jsonl"
        mode = research
        if mode == "bundle" and not bundle.is_file():
            mode = "fixture"
        result = run_dcm(
            input_path=None,
            forecast_cutoff=None,
            output_root=self.dest.parent,
            resume=ck,
            research=mode,
            bundle_path=bundle if mode == "bundle" else None,
            workspace=self.workspace,
            account_only=False,
        )
        self._save_host_state(
            lastCommand="forecast",
            forecastFrozen=True,
            runState=result.get("runState"),
            accountOnly=False,
        )
        return result

    def report(self, *, fmt: str = "json") -> dict[str, Any]:
        body = build_report(self.dest)
        self._save_host_state(lastCommand="report")
        if fmt != "json":
            body = {**body, "requestedFormat": fmt}
        return body

    def resume(self) -> dict[str, Any]:
        ck = self.dest / "checkpoint.json"
        if not ck.is_file():
            raise FileNotFoundError("CHECKPOINT_MISSING")
        result = run_dcm(
            input_path=None,
            forecast_cutoff=None,
            output_root=self.dest.parent,
            resume=ck,
            workspace=self.workspace,
            research="bundle" if (self.dest / "evidence_bundle.jsonl").is_file() else "file",
            bundle_path=self.dest / "evidence_bundle.jsonl",
        )
        self._save_host_state(lastCommand="resume", runState=result.get("runState"))
        return result

    def audit(self) -> dict[str, Any]:
        result = audit_run(self.dest)
        self._save_host_state(lastCommand="audit")
        return result

    def archive(self, *, format: str = "github-pack", repo_root: Path | None = None) -> dict[str, Any]:
        result = archive_run(self.dest, repo_root=repo_root or self.workspace, format=format)
        self._save_host_state(lastCommand="archive")
        return result

    def settle(self, outcomes: Path, *, card_only: bool = False) -> dict[str, Any]:
        from dcm.learning.postgame import settle_run
        result = settle_run(self.dest, Path(outcomes), card_only=card_only)
        self._save_host_state(lastCommand="settle")
        return result


def cfb_launch(
    *,
    har: Path,
    run_root: Path,
    cutoff: str | None = None,
    cutoff_from_capture: bool = False,
    research: str = "file",
    bundle_path: Path | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Guarded CFB vertical slice. Fixture/bundle can freeze; file research returns the host loop."""
    workspace = Path(workspace) if workspace is not None else DEFAULT_WORKSPACE
    if research in {"fixture", "bundle"}:
        result = run_dcm(
            input_path=Path(har),
            forecast_cutoff=cutoff,
            output_root=Path(run_root),
            research=research,
            bundle_path=bundle_path,
            workspace=workspace,
            cutoff_from_capture=bool(cutoff_from_capture),
        )
        dest = Path(result["dest"])
        return {
            "schema": "pillars_dcm.cfb_launch.v1",
            "runId": result.get("run_id"),
            "dest": str(dest),
            "runState": result.get("runState"),
            "mode": research,
            "artifacts": {
                "accounting": str(dest / "CFB_HAR_ACCOUNTING.json"),
                "algorithmPlan": str(dest / "algorithm_execution_plan.json"),
                "boardGraph": str(dest / "board_graph.json"),
                "requirementGraph": str(dest / "requirement_graph.json"),
                "acquisitionActions": str(dest / "acquisition_actions.json"),
                "top100": str(dest / "CFB_TOP100_PRELIMINARY.json"),
                "top25": str(dest / "CFB_TOP25_FINAL.json"),
                "playables": str(dest / "CFB_PLAYABLES_FINAL.json"),
                "telemetry": str(dest / "algorithm_execution_telemetry.json"),
                "freeze": str(dest / "freeze.json"),
            },
            "hostComputesProbabilities": False,
            "learningRevision": LEARNING_REVISION,
            "predictiveClaim": PREDICTIVE_CLAIM,
            "next": "none" if result.get("runState") not in {"INCOMPLETE_CHECKPOINTED"} else "execute host_research_plan / next-research, evidence-import, coverage, forecast",
        }
    session = HostSession.prepare(
        har=Path(har),
        run_root=Path(run_root),
        cutoff=cutoff,
        cutoff_from_capture=bool(cutoff_from_capture),
        workspace=workspace,
    )
    batch = session.next_research_batch()
    return {
        "schema": "pillars_dcm.cfb_launch.v1",
        "runId": session.dest.name,
        "dest": str(session.dest),
        "mode": "file",
        "runState": "AWAITING_HOST_RESEARCH",
        "nextResearch": {
            "selectedCount": batch.get("selectedCount"),
            "unresolvedCount": batch.get("unresolvedCount"),
            "liveSelector": batch.get("liveSelector"),
            "batchPath": str(session.dest / "host_research_batch.json"),
        },
        "hostWorkflow": [
            "python -m dcm.chat next-research --run <run>",
            "host web research by EVENT/TEAM before PLAYER (do not one-search-per-prop)",
            "python -m dcm.chat evidence-import --run <run> --input host_observations.jsonl",
            "python -m dcm.chat coverage --run <run>",
            "repeat until per-prop modelable flags are explicit",
            "python -m dcm.chat forecast --run <run> --research bundle",
            "python -m dcm.chat report --run <run>",
        ],
        "hostComputesProbabilities": False,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
    }

