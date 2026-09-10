"""Bridge from run artifacts to the next optimized host research batch."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Iterable

from dcm.algorithms.selection import AlgorithmSelectionEngine
from dcm.chat.state import read_json, write_json
from dcm.research.batch import build_next_research_batch
from dcm.research.action_state import eligible_action_ids, load_action_state, save_action_state, apply_transition
from dcm.research.acquisition import build_acquisition_actions, build_acquisition_action_graph, schedule_acquisition_actions
from dcm.research.batch_store import load_batch, make_batch_envelope, seal_batch
from dcm.research.failures import load_failures
from dcm.research.provider import BundleProvider
from dcm.research.readiness import evaluate_research_os_readiness, persist_research_os_readiness, require_research_may_begin
from dcm.research.research_store import ResearchStore, hydrate_reused_claims
from dcm.research.run_lock import RunLock
from dcm.research.search_blueprint import build_search_blueprint
from dcm.contracts.hashes import content_hash
from dcm.runtime.checkpoint import load_checkpoint
from dcm.version import SOFTWARE


def _code_sha(dest: Path) -> str:
    # ``dest`` is a run-artifact directory, not the repository.  Resolve the
    # repository from the current Work/Codex process first and then from this
    # editable package.  A batch envelope must never silently record a missing
    # code identity merely because the run lives outside the checkout.
    candidates = [Path.cwd(), Path(__file__).resolve().parents[3], Path(dest)]
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=candidate, capture_output=True, text=True, check=False)
            value = (proc.stdout or "").strip()
            if proc.returncode == 0 and value:
                return value
        except OSError:
            continue
    return "WORKTREE_UNAVAILABLE"


def _har_sha(dest: Path) -> str:
    for name in ("input_manifest.json", "run_manifest.json"):
        data = read_json(dest / name) or {}
        for key in ("harSha256", "har_sha256", "sourceHash", "inputSha256"):
            if data.get(key):
                return str(data[key])
    board = read_json(dest / "board.json") or {}
    return str(board.get("harSha256") or board.get("sourceHash") or "UNKNOWN")


def _ensure_research_prerequisites(dest: Path) -> dict[str, Any]:
    """Repair the missing bridge artifacts needed before external research.

    The previous preparation path could terminate after graphs were written but
    before AcquisitionActions and ResearchOSReadiness were persisted.  Batch
    research is allowed to repair those deterministic artifacts from the
    already captured board; it is not allowed to authorize a missing graph or
    source-routing prerequisite.
    """
    requests = read_json(dest / "research_requests.json") or []
    requests = requests if isinstance(requests, list) else []
    board = read_json(dest / "board.json") or {}
    rows = board.get("rows") if isinstance(board, dict) else []
    rows = rows if isinstance(rows, list) else []
    coverage = read_json(dest / "evidence_coverage.json") or read_json(dest / "evidence" / "coverage.json") or {}
    coverage = coverage if isinstance(coverage, dict) else {}
    action_doc = read_json(dest / "acquisition_actions.json") or {}
    if not isinstance(action_doc, dict) or int(action_doc.get("actionCount") or 0) == 0 and requests:
        action_doc = build_acquisition_actions(rows, requests, coverage=coverage)
        schedule = schedule_acquisition_actions(action_doc)
        action_graph = build_acquisition_action_graph(action_doc, schedule=schedule)
        write_json(dest / "acquisition_actions.json", action_doc)
        write_json(dest / "acquisition_schedule.json", schedule)
        write_json(dest / "acquisition_action_graph.json", action_graph)
    index_meta = read_json(dest / "research_indexes_meta.json") or {}
    if not isinstance(index_meta, dict) or not index_meta.get("contentHash"):
        index_meta = {
            "schema": "pillars_dcm.research_indexes_meta.v1",
            "offerCount": len(rows),
            "requestCount": len(requests),
            "indexSource": "board.json",
            "contentHash": content_hash({"offerCount": len(rows), "requestCount": len(requests), "indexSource": "board.json"}),
        }
        write_json(dest / "research_indexes_meta.json", index_meta)
    claims = read_json(dest / "evidence" / "claims.json") or []
    reused_scopes = len({(str(c.get("semantic_scope") or ""), str(c.get("scope_id") or "")) for c in claims if isinstance(c, dict)}) if isinstance(claims, list) else 0
    readiness = evaluate_research_os_readiness(
        board_graph=read_json(dest / "board_graph.json"),
        market_demand_graph=read_json(dest / "market_demand_graph.json"),
        requirement_graph=read_json(dest / "requirement_graph.json"),
        indexes_meta=index_meta,
        reused_evidence_scopes=reused_scopes,
        acquisition_actions=action_doc,
        source_routing=read_json(dest / "source_health.json"),
    )
    persist_research_os_readiness(dest, readiness)
    return readiness


def _pending_active_batch(dest: Path) -> dict[str, Any] | None:
    """Return an uncheckpointed active batch without selecting a replacement.

    The immutable envelope protects its own path, but a mutable active pointer
    could otherwise be advanced by a second Work run after a crash.  The
    pointer may advance only after the prior batch has been represented in a
    durable research checkpoint.
    """
    pointer = read_json(dest / "active_research_batch.json") or {}
    if not isinstance(pointer, dict) or not pointer.get("batchId"):
        return None
    batch_id = str(pointer.get("batchId"))
    envelope_path = Path(str(pointer.get("envelopePath") or dest / "research_batches" / f"{batch_id}.json"))
    if not envelope_path.is_absolute():
        envelope_path = dest / envelope_path
    envelope = load_batch(envelope_path)
    if str(pointer.get("batchContentSha") or "") != str(envelope.get("batchContentSha") or ""):
        raise RuntimeError("ACTIVE_BATCH_POINTER_HASH_MISMATCH")
    checkpoint = read_json(dest / "research_checkpoint.json") or {}
    committed = bool(
        isinstance(checkpoint, dict)
        and checkpoint.get("checkpointHash")
        and str(checkpoint.get("activeBatchId") or "") == batch_id
    )
    if committed:
        return None
    compatibility = read_json(dest / "host_research_batch.json") or {}
    if not isinstance(compatibility, dict) or str(compatibility.get("batchId") or "") != batch_id:
        compatibility = {
            "schema": "pillars_dcm.host_research_batch.v1",
            "batchId": batch_id,
            "batchContentSha": envelope.get("batchContentSha"),
            "tasks": envelope.get("actions") or [],
            "selectedCount": len(envelope.get("actions") or []),
            "unresolvedCount": None,
            "eventBatchCount": None,
        }
    return {
        **compatibility,
        "batchStatus": "ACTIVE_PENDING_CHECKPOINT",
        "resumeRequired": True,
        "envelopePath": str(envelope_path),
        "batchContentSha": envelope.get("batchContentSha"),
        "parentCheckpointSha": envelope.get("parentCheckpointSha"),
    }


def next_research_batch(
    dest: Path,
    *,
    max_entities: int = 25,
    max_dependent_offers: int = 500,
    store_root: Path | None = None,
    allowed_leagues: Iterable[str] | None = None,
) -> dict[str, Any]:
    dest = Path(dest)
    # Selection, state mutation, and envelope creation are one writer-owned
    # transaction.  A second Work/Codex run receives RUN_BUSY and cannot
    # overwrite the active batch.
    with RunLock(dest, command="next-research"):
        pending = _pending_active_batch(dest)
        if pending is not None:
            return pending
        _ensure_research_prerequisites(dest)
        require_research_may_begin(dest)
        requests = read_json(dest / "research_requests.json") or []
        coverage = read_json(dest / "evidence_coverage.json") or read_json(dest / "evidence" / "coverage.json") or {}
        board = read_json(dest / "board.json") or {}
        rows = board.get("rows") if isinstance(board, dict) else []
        requests = requests if isinstance(requests, list) else []
        rows = rows if isinstance(rows, list) else []
        leagues = {str(value).upper() for value in (allowed_leagues or ()) if str(value).strip()}
        if leagues:
            def row_league(row: dict[str, Any]) -> str:
                context = row.get("context") if isinstance(row.get("context"), dict) else {}
                return str(row.get("league") or context.get("league") or "").upper()

            # A missing league is not silently assigned to the cut.  The
            # caller can widen the explicit allow-list for a later sport.
            requests = [row for row in requests if row_league(row) in leagues]
            rows = [row for row in rows if row_league(row) in leagues]
        action_doc = read_json(dest / "acquisition_actions.json") or {}
        action_rows = [row for row in (action_doc.get("actions") if isinstance(action_doc, dict) else []) if isinstance(row, dict)]
        if leagues:
            action_rows = [row for row in action_rows if str(row.get("league") or "").upper() in leagues]
        state_path = dest / "research_action_state.json"
        states = load_action_state(state_path)
        failures = load_failures(dest / "research_failures.jsonl")
        eligible = eligible_action_ids(action_rows, states=states, failures=failures, run_id=dest.name)
        excluded = {str(row.get("actionId")) for row in action_rows if str(row.get("actionId") or "") not in eligible}
        store = ResearchStore(store_root or dest / "research_store")
        batch = build_next_research_batch(
            requests,
            coverage=coverage if isinstance(coverage, dict) else {},
            store=store,
            max_entities=max_entities,
            max_dependent_offers=max_dependent_offers,
            rows=rows,
            excluded_action_ids=excluded,
        )
        reused_claims = hydrate_reused_claims(
            store,
            [
                {"scope": t.get("scope"), "scope_id": t.get("scopeId") or t.get("scope_id"), "acquire": False, "deltaClass": t.get("deltaClass")}
                for t in (batch.get("reused") or [])
            ],
        )
        if reused_claims:
            bundle = BundleProvider(dest / "evidence_bundle.jsonl")
            existing = {str(c.get("claim_hash") or "") for c in bundle.all_claims()}
            fresh = [c for c in reused_claims if str(c.get("claim_hash") or "") not in existing]
            if fresh:
                bundle.append(fresh)
            write_json(dest / "evidence" / "claims.json", bundle.all_claims())
        reused = int(batch.get("reusedCount") or 0)
        acquired = int(batch.get("unresolvedCount") or 0)
        batch["storeTelemetry"] = store.telemetry(reused=reused, acquired=acquired)
        batch["hydratedClaimCount"] = len(reused_claims)
        if leagues:
            batch["allowedLeagues"] = sorted(leagues)
        selection = AlgorithmSelectionEngine().select(
            "RESEARCH_SCHEDULE", {"consumer": "dcm.chat.research_bridge.next_research_batch"},
        )
        batch["algorithmSelection"] = selection.to_dict()

        checkpoint = {}
        try:
            research_checkpoint = dest / "research_checkpoint.json"
            checkpoint_path = research_checkpoint if research_checkpoint.is_file() else dest / "checkpoint.json"
            checkpoint = load_checkpoint(checkpoint_path) if checkpoint_path.is_file() else {}
        except (OSError, ValueError, RuntimeError):
            checkpoint = {}
        manifest_sha = content_hash({"requests": requests, "rowDigest": content_hash(rows), "coverage": coverage})
        cutoff = str((board or {}).get("forecastCutoff") or (read_json(dest / "freeze.json") or {}).get("forecastCutoff") or "")
        actions_for_envelope = [dict(task) for task in (batch.get("tasks") or []) if isinstance(task, dict)]
        blueprint = build_search_blueprint(
            actions=[row for row in action_rows if str(row.get("actionId") or "") in eligible],
            requests=requests,
            cutoff=cutoff,
            breakdown=read_json(dest / "har_breakdown.json"),
        )
        write_json(dest / "search_blueprint.json", blueprint)
        batch["searchBlueprintHash"] = blueprint.get("blueprintHash")
        envelope = make_batch_envelope(
            run_id=dest.name,
            actions=actions_for_envelope,
            manifest_sha=manifest_sha,
            har_sha256=_har_sha(dest),
            forecast_cutoff=cutoff,
            code_sha=_code_sha(dest),
            parent_checkpoint_sha=str(checkpoint.get("checkpointHash") or "") or None,
            generation=int(checkpoint.get("generation") or checkpoint.get("researchGeneration") or 0),
            budgets={"maxEntities": int(max_entities), "maxDependentOffers": int(max_dependent_offers)},
            source_policy_hash=content_hash({"sourceCatalog": (read_json(dest / "source_catalog.json") or {}).get("contentHash")}),
        )
        batch_dir = dest / "research_batches"
        sealed = seal_batch(batch_dir / f"{envelope['batchId']}.json", envelope)
        batch.update(
            {
                "batchId": sealed["batchId"],
                "batchContentSha": sealed["batchContentSha"],
                "manifestSha": sealed["manifestSha"],
                "harSha256": sealed["harSha256"],
                "forecastCutoff": sealed["forecastCutoff"],
                "codeSha": sealed["codeSha"],
                "parentCheckpointSha": sealed.get("parentCheckpointSha"),
                "envelopePath": str(batch_dir / f"{sealed['batchId']}.json"),
                "excludedActionIds": sorted(excluded),
                "stateSchema": "pillars_dcm.action_state.v1",
            }
        )
        for task in actions_for_envelope:
            aid = str(task.get("actionId") or "")
            if not aid:
                continue
            if aid not in states:
                states[aid] = {"actionId": aid, "state": "PENDING", "attempt": 0, "lastFailureId": None, "nextRetryAt": None, "updatedAt": None}
            if states[aid].get("state") in {"PENDING", "FAILED_RETRYABLE", "DEFERRED", "PARTIAL"}:
                apply_transition(states, aid, "SELECTED")
        if actions_for_envelope:
            save_action_state(state_path, states)
        # The compatibility document is atomically replaced; the immutable
        # content-addressed envelope is never replaced.
        write_json(dest / "host_research_batch.json", batch)
        pointer = {
            "schema": "pillars_dcm.active_research_batch.v1",
            "runId": dest.name,
            "batchId": sealed["batchId"],
            "batchContentSha": sealed["batchContentSha"],
            "envelopePath": str(batch_dir / f"{sealed['batchId']}.json"),
        }
        write_json(dest / "active_research_batch.json", pointer)
        return batch
