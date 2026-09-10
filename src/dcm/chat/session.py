"""HostSession: ChatGPT/Grok-native orchestration over the canonical runner.

This module never computes probabilities. It prepares, schedules research,
imports host observations, evaluates coverage, and delegates forecast/settle
to dcm.runner / dcm.settle.
"""
from __future__ import annotations

import json
import hashlib
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
from dcm.research.coverage_incremental import incremental_coverage_report
from dcm.research.failures import append_failure, failure_record, load_failures
from dcm.research.action_state import apply_failure, apply_transition, load_action_state, save_action_state, TERMINAL_STATES
from dcm.research.batch_store import verify_checkpoint, write_checkpoint_cas
from dcm.research.har_breakdown import build_har_breakdown
from dcm.research.search_blueprint import build_search_blueprint
from dcm.research.search_engine import SearchEngine
from dcm.research.run_lock import RunLock
from dcm.research.observation_typed import _load_observations, _match_action, _match_request, observation_to_typed_claim
from dcm.research.response import load_response, validate_failure_payload, validate_response_binding
from dcm.contracts.hashes import content_hash
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


def doctor(*, release_manifest: Path | None = None, workspace: Path | None = None, run: Path | None = None) -> dict[str, Any]:
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
    run_state = None
    if run is not None:
        run_path = Path(run)
        run_state = {
            "path": str(run_path),
            "exists": run_path.is_dir(),
            "activeBatch": read_json(run_path / "active_research_batch.json") if run_path.is_dir() else None,
            "researchCheckpoint": read_json(run_path / "research_checkpoint.json") if run_path.is_dir() else None,
            "failureCount": len(load_failures(run_path / "research_failures.jsonl")) if run_path.is_dir() and (run_path / "research_failures.jsonl").is_file() else 0,
        }
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
        "cacheStatus": "run_root_sqlite_research_cache_with_integrity_fallback",
        "hostPerformanceCertified": False,
        "productionRootCertified": False,
        "blockers": blockers,
        "releaseManifest": release or None,
        "run": run_state,
        "commands": [
            "doctor", "prepare", "next-research", "research-batch", "research-validate", "research-failure",
            "evidence-import", "coverage", "har-breakdown", "index-build", "search-blueprint", "checkpoint-verify",
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

    def next_research_batch(self, *, max_entities: int = 25, max_dependent_offers: int = 500,
                            allowed_leagues: tuple[str, ...] | None = None) -> dict[str, Any]:
        batch = next_research_batch(
            self.dest,
            max_entities=max_entities,
            max_dependent_offers=max_dependent_offers,
            store_root=self.workspace / "dcm_v6" / "research_store",
            allowed_leagues=allowed_leagues,
        )
        state = self._host_state()
        self._save_host_state(
            lastCommand="next-research",
            researchLoopCount=int(state.get("researchLoopCount") or 0) + 1,
        )
        return batch

    def research_batch(self, *, max_entities: int = 25, max_dependent_offers: int = 500,
                       allowed_leagues: tuple[str, ...] | None = None) -> dict[str, Any]:
        """Canonical durable batch command; next-research remains compatible."""
        return self.next_research_batch(max_entities=max_entities, max_dependent_offers=max_dependent_offers,
                                        allowed_leagues=allowed_leagues)

    def har_breakdown(self, har: Path, *, prior: Path | None = None) -> dict[str, Any]:
        with RunLock(self.dest, command="har-breakdown"):
            board = read_json(self.dest / "board.json") or {}
            requests = read_json(self.dest / "research_requests.json") or []
            prior_body = read_json(prior) if prior else read_json(self.dest / "har_breakdown.json")
            result = build_har_breakdown(
                Path(har), run_id=self.dest.name, prior=prior_body if isinstance(prior_body, dict) else None,
                board=board if isinstance(board, dict) else None,
                requests=requests if isinstance(requests, list) else None,
                output_path=self.dest / "har_breakdown.json",
            )
            self._save_host_state(lastCommand="har-breakdown", harSha256=result["receipt"].get("harSha256"))
            return result["receipt"]

    def index_build(self) -> dict[str, Any]:
        with RunLock(self.dest, command="index-build"):
            claims = read_json(self.dest / "evidence" / "claims.json") or []
            board = read_json(self.dest / "board.json") or {}
            rows = board.get("rows") if isinstance(board, dict) else []
            docs = [dict(row, _kind="claim") for row in claims if isinstance(row, dict)]
            docs.extend(dict(row, _kind="board") for row in (rows if isinstance(rows, list) else []) if isinstance(row, dict))
            engine = SearchEngine(docs)
            receipt = {**engine.index_receipt, "documentKinds": {"claims": len(claims) if isinstance(claims, list) else 0, "board": len(rows) if isinstance(rows, list) else 0}}
            receipt["contentHash"] = content_hash(receipt)
            write_json(self.dest / "search_index_receipt.json", receipt)
            self._save_host_state(lastCommand="index-build", searchIndexHash=receipt.get("indexHash"))
            return receipt

    def search_blueprint(self) -> dict[str, Any]:
        """Compile the sport-neutral public-search fan-out plan for this run."""
        with RunLock(self.dest, command="search-blueprint"):
            actions_doc = read_json(self.dest / "acquisition_actions.json") or {}
            actions = actions_doc.get("actions") if isinstance(actions_doc, dict) else []
            requests = read_json(self.dest / "research_requests.json") or []
            board = read_json(self.dest / "board.json") or {}
            freeze = read_json(self.dest / "freeze.json") or {}
            cutoff = str((self._host_state() or {}).get("forecastCutoff") or freeze.get("forecastCutoff") or (board if isinstance(board, dict) else {}).get("forecastCutoff") or "")
            blueprint = build_search_blueprint(
                actions=[row for row in (actions or []) if isinstance(row, dict)],
                requests=requests if isinstance(requests, list) else [],
                cutoff=cutoff,
                breakdown=read_json(self.dest / "har_breakdown.json"),
            )
            write_json(self.dest / "search_blueprint.json", blueprint)
            self._save_host_state(lastCommand="search-blueprint", searchBlueprintHash=blueprint.get("blueprintHash"))
            return blueprint

    def research_validate(self, observations: Path) -> dict[str, Any]:
        response = validate_response_binding(load_response(Path(observations)), self.dest)
        requests = read_json(self.dest / "research_requests.json") or []
        action_doc = read_json(self.dest / "acquisition_actions.json") or {}
        actions = action_doc.get("actions") if isinstance(action_doc, dict) else []
        actions = [row for row in actions if isinstance(row, dict)]
        freeze = read_json(self.dest / "freeze.json") or {}
        board = read_json(self.dest / "board.json") or {}
        state = self._host_state()
        cutoff = str(state.get("forecastCutoff") or freeze.get("forecastCutoff") or board.get("forecastCutoff") or "")
        if not cutoff:
            raise ValueError("FORECAST_CUTOFF_REQUIRED")
        valid: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for index, obs in enumerate(response.get("observations") or []):
            try:
                req = _match_request(obs, requests if isinstance(requests, list) else [])
                action = _match_action(obs, actions, request=req)
                claim = observation_to_typed_claim(obs, cutoff=cutoff, request=req, action=action)
                valid.append({"index": index, "actionId": claim.get("action_id"), "scope": claim.get("semantic_scope"), "scopeId": claim.get("scope_id"), "claimHash": claim.get("claim_hash"), "sourceHash": claim.get("source_hash"), "fieldNames": sorted((claim.get("claim_value") or {}).keys()) if isinstance(claim.get("claim_value"), dict) else []})
            except (ValueError, TypeError, KeyError) as exc:
                rejected.append({"index": index, "code": "SCHEMA_INVALID", "error": str(exc)[:240]})
        result = {
            "schema": "pillars_dcm.research_validation.v1",
            "cutoff": cutoff,
            "input": str(Path(observations).name),
            "validCount": len(valid),
            "rejectedCount": len(rejected),
            "valid": valid,
            "rejected": rejected,
            "hostComputedHashes": True,
            "responseHash": response.get("responseHash"),
            "bindingStatus": response.get("bindingStatus"),
            "failureCount": int(response.get("failureCount") or 0),
        }
        result["contentHash"] = content_hash(result)
        write_json(self.dest / "research_validation.json", result)
        return result

    def import_evidence(self, observations: Path, *, select_next: bool = True) -> dict[str, Any]:
        response = validate_response_binding(load_response(Path(observations)), self.dest)
        with RunLock(self.dest, command="evidence-import"):
            active = read_json(self.dest / "active_research_batch.json") or {}
            bound_batch_id = str(response.get("batchId") or active.get("batchId") or "UNBOUND")
            response_failure_errors: list[dict[str, Any]] = []
            response_failures = response.get("failures") or []
            states = load_action_state(self.dest / "research_action_state.json")
            failure_path = self.dest / "research_failures.jsonl"
            for index, raw_failure in enumerate(response_failures):
                try:
                    failure = validate_failure_payload(raw_failure)
                    failure_key = failure.get("failureKey") or content_hash({
                        "responseHash": response.get("responseHash"),
                        "index": index,
                        "actionId": failure.get("actionId"),
                        "requestId": failure.get("requestId"),
                        "sourceId": failure.get("sourceId"),
                        "code": failure.get("code"),
                        "missingFields": failure.get("missingFields"),
                    })
                    apply_failure(
                        states,
                        run_id=self.dest.name,
                        batch_id=bound_batch_id,
                        action_id=str(failure["actionId"]),
                        request_id=failure.get("requestId"),
                        source_id=failure.get("sourceId"),
                        code=str(failure["code"]),
                        retryable=bool(failure.get("retryable")),
                        exclusion_scope=str(failure.get("exclusionScope") or "ATTEMPT_ONLY"),
                        failure_path=failure_path,
                        missing_fields=failure.get("missingFields") or [],
                        source_attempts=failure.get("sourceAttempts") or [],
                        safe_reason=failure.get("safeReason"),
                        failure_key=failure_key,
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    response_failure_errors.append({"index": index, "code": "SCHEMA_INVALID", "error": str(exc)[:240]})
            if states:
                save_action_state(self.dest / "research_action_state.json", states)
            result = import_observations(
                self.dest,
                Path(observations),
                store_root=self.workspace / "dcm_v6" / "research_store",
                refresh_frontier=select_next,
            )
            state_path = self.dest / "research_action_state.json"
            states = load_action_state(state_path)
            actions_doc = read_json(self.dest / "acquisition_actions.json") or {}
            action_by_id = {str(row.get("actionId")): row for row in (actions_doc.get("actions") or []) if isinstance(row, dict)}
            coverage = read_json(self.dest / "evidence_coverage.json") or {}
            coverage_by_id = {str(row.get("requestId") or ""): row for row in (coverage.get("requests") or []) if isinstance(row, dict)}
            for fanout in result.get("fanouts") or []:
                aid = str(fanout.get("actionId") or "")
                if not aid:
                    continue
                row = dict(states.get(aid) or {"actionId": aid, "state": "PENDING", "attempt": 0})
                current = str(row.get("state") or "PENDING")
                if current == "PENDING":
                    apply_transition(states, aid, "SELECTED")
                    current = "SELECTED"
                if current == "SELECTED":
                    apply_transition(states, aid, "IN_FLIGHT")
                    current = "IN_FLIGHT"
                if current == "IN_FLIGHT":
                    apply_transition(states, aid, "IMPORTING")
                    current = "IMPORTING"
                req_ids = [str(x) for x in (action_by_id.get(aid) or {}).get("requirementIds") or []]
                complete = bool(req_ids) and all(bool((coverage_by_id.get(rid) or {}).get("complete")) for rid in req_ids)
                target = "SUCCEEDED" if complete else "PARTIAL"
                if current != target:
                    apply_transition(states, aid, target)
            if states:
                save_action_state(state_path, states)
            # Source-aware import already emits canonical changed claim refs.
            # Preserve them; only derive the legacy shape when an older
            # importer returned stored pointers instead.
            changed_refs = result.get("changedClaimRefs") or []
            if not changed_refs:
                changed_refs = [
                    {
                        "semantic_scope": str(row.get("entityKind") or row.get("semantic_scope") or ""),
                        "scope_id": str(row.get("entityId") or row.get("scope_id") or ""),
                        "claim_hash": str(row.get("claimHash") or row.get("claim_hash") or ""),
                    }
                    for row in (result.get("stored") or [])
                    if isinstance(row, dict)
                ]
            result["changedClaimRefs"] = changed_refs
            write_json(self.dest / "last_import_claim_refs.json", result["changedClaimRefs"])
            self._persist_research_checkpoint(active_batch_id=(read_json(self.dest / "active_research_batch.json") or {}).get("batchId"))
            self._save_host_state(lastCommand="evidence-import", lastImport=result.get("imported"))
            result["responseHash"] = response.get("responseHash")
            result["bindingStatus"] = response.get("bindingStatus")
            result["responseFailureCount"] = len(response_failures)
            result["responseFailureErrors"] = response_failure_errors
        # Create/seal the next immutable envelope after the current batch is
        # checkpointed.  This is the repeatable hand-off to the next Work run.
        if select_next:
            next_batch = self.next_research_batch()
            result["nextBatchId"] = next_batch.get("batchId")
        return result

    def coverage(self, *, incremental: bool = False, verify_full: bool = False, select_next: bool = True) -> dict[str, Any]:
        requests = read_json(self.dest / "research_requests.json") or []
        claims = read_json(self.dest / "evidence" / "claims.json") or []
        if not claims:
            bundle = self.dest / "evidence_bundle.jsonl"
            if bundle.is_file():
                from dcm.research.provider import BundleProvider
                claims = BundleProvider(bundle).all_claims()
        request_rows = requests if isinstance(requests, list) else []
        claim_rows = claims if isinstance(claims, list) else []
        if incremental:
            prior = read_json(self.dest / "evidence_coverage.json") or {}
            changed = read_json(self.dest / "last_import_claim_refs.json") or claim_rows
            coverage = incremental_coverage_report(request_rows, claim_rows, prior=prior if isinstance(prior, dict) else None, changed_claims=changed if isinstance(changed, list) else None, verify_full=verify_full)
        else:
            coverage = coverage_report(request_rows, claim_rows)
        batch = None
        if select_next:
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
            "semanticRule": "Coverage means required SportResearchSchema fields exist, not merely that a request returned something.",
        }
        if batch is not None:
            payload["nextRecommendedBatch"] = {
                "selectedCount": batch.get("selectedCount"),
                "unresolvedCount": batch.get("unresolvedCount"),
                "eventBatchCount": batch.get("eventBatchCount"),
            }
        write_json(self.dest / "evidence_coverage.json", payload)
        self._save_host_state(
            lastCommand="coverage",
            coverageEvaluated=True,
            modelingPermitted=modeling_permitted,
            productionSelectionPermitted=production_selection_permitted,
        )
        return payload

    def record_research_failure(self, *, action_id: str, code: str, retryable: bool, request_id: str | None = None, source_id: str | None = None, batch_id: str | None = None, exclusion_scope: str = "ATTEMPT_ONLY", safe_reason: str | None = None) -> dict[str, Any]:
        with RunLock(self.dest, command="research-failure"):
            active = read_json(self.dest / "active_research_batch.json") or {}
            batch_id = str(batch_id or active.get("batchId") or "UNBOUND")
            path = self.dest / "research_failures.jsonl"
            states = load_action_state(self.dest / "research_action_state.json")
            row, failure = apply_failure(states, run_id=self.dest.name, batch_id=batch_id, action_id=action_id, request_id=request_id, source_id=source_id, code=code, retryable=retryable, exclusion_scope=exclusion_scope, failure_path=path, safe_reason=safe_reason)
            save_action_state(self.dest / "research_action_state.json", states)
            self._persist_research_checkpoint(active_batch_id=batch_id)
            return {"schema": "pillars_dcm.research_failure_result.v1", "action": row, "failure": failure}

    def checkpoint_verify(self) -> dict[str, Any]:
        results = {}
        research = self.dest / "research_checkpoint.json"
        canonical = self.dest / "checkpoint.json"
        if research.is_file():
            results["research"] = verify_checkpoint(research)
        if canonical.is_file():
            results["canonical"] = {"path": str(canonical), "valid": bool(__import__("dcm.runtime.checkpoint", fromlist=["load_checkpoint"]).load_checkpoint(canonical))}
        return {"schema": "pillars_dcm.checkpoint_verification.v1", "results": results, "valid": all(row.get("valid", False) for row in results.values()) if results else False}

    def _persist_research_checkpoint(self, *, active_batch_id: str | None = None) -> dict[str, Any]:
        path = self.dest / "research_checkpoint.json"
        current = read_json(path) or {}
        expected = str(current.get("checkpointHash") or "") or None
        states = load_action_state(self.dest / "research_action_state.json")
        terminal = TERMINAL_STATES
        artifacts: dict[str, str] = {}
        for name in ("active_research_batch.json", "research_action_state.json", "research_failures.jsonl", "evidence_coverage.json", "last_import_claim_refs.json"):
            file = self.dest / name
            if file.is_file():
                artifacts[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        coverage = read_json(self.dest / "evidence_coverage.json") or {}
        result = write_checkpoint_cas(
            path,
            expected_parent_sha=expected,
            run_id=self.dest.name,
            generation=int(current.get("generation") or 0) + 1,
            active_batch_id=active_batch_id,
            artifacts=artifacts,
            completed_action_ids=[aid for aid, row in states.items() if row.get("state") == "SUCCEEDED"],
            pending_action_ids=[aid for aid, row in states.items() if row.get("state") not in terminal],
            failed_action_ids=[aid for aid, row in states.items() if str(row.get("state") or "").startswith(("FAILED_", "BLOCKED_"))],
            coverage_sha=content_hash(coverage),
        )
        return result

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
