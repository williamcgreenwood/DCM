"""One-arrow supervisor for the ChatGPT/Grok research hand-off.

The director is deliberately a small control plane.  It never fetches the
web, computes probabilities, or holds a writer lease while waiting for a
response.  A sealed packet is an external boundary: the state is persisted as
``AWAITING_RESPONSE`` and the lock is released before the next invocation.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from dcm.chat.session import HostSession
from dcm.chat.state import read_json, write_json
from dcm.contracts.hashes import content_hash
from dcm.research.batch_store import load_batch
from dcm.research.run_lock import RunLock


DIRECTOR_SCHEMA = "pillars_dcm.run_director.v1"
STATE_FILE = "run_director.json"
PHASES = (
    "READ_CHECKPOINT",
    "READ_MANIFEST",
    "SELECT_OR_RESUME_BATCH",
    "AWAITING_RESPONSE",
    "VALIDATE",
    "IMPORT",
    "COVERAGE",
    "CHECKPOINT_CAS",
    "TERMINAL",
)


class DirectorStateError(RuntimeError):
    """The durable director state cannot safely advance."""


class RunDirector:
    """Persisted one-transition-at-a-time research supervisor."""

    def __init__(self, run: Path, *, workspace: Path | None = None,
                 max_entities: int = 8, max_dependent_offers: int = 250) -> None:
        self.run = Path(run)
        self.workspace = Path(workspace) if workspace is not None else None
        self.max_entities = min(8, max(4, int(max_entities)))
        self.max_dependent_offers = min(250, max(1, int(max_dependent_offers)))

    @property
    def state_path(self) -> Path:
        return self.run / STATE_FILE

    def _load(self) -> dict[str, Any]:
        raw = read_json(self.state_path)
        if not raw:
            return {
                "schema": DIRECTOR_SCHEMA, "runId": self.run.name,
                "phase": "READ_CHECKPOINT", "transition": 0,
                "batchId": None, "batchContentSha": None,
                "responsePath": None, "lastError": None,
            }
        if raw.get("schema") != DIRECTOR_SCHEMA or raw.get("runId") != self.run.name:
            raise DirectorStateError("DIRECTOR_STATE_IDENTITY_MISMATCH")
        if raw.get("phase") not in PHASES:
            raise DirectorStateError("DIRECTOR_PHASE_INVALID")
        return dict(raw)

    def _save(self, state: dict[str, Any]) -> dict[str, Any]:
        body = dict(state)
        body["schema"] = DIRECTOR_SCHEMA
        body["runId"] = self.run.name
        body["transition"] = int(body.get("transition") or 0) + 1
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        write_json(self.state_path, body)
        return body

    def _lease_status(self) -> dict[str, Any]:
        path = self.run / "run_lock.sqlite3"
        if not path.is_file():
            return {"held": False}
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.2)
            row = db.execute("SELECT fence, lease_until, command, metadata_json FROM writer_lease WHERE run_id=?", (self.run.name,)).fetchone()
            db.close()
        except sqlite3.Error:
            return {"held": None, "state": "UNREADABLE"}
        if row is None:
            return {"held": False}
        metadata = {}
        try:
            metadata = json.loads(str(row[3] or "{}"))
        except json.JSONDecodeError:
            pass
        return {
            "held": float(row[1]) > __import__("time").time(),
            "fence": int(row[0]), "leaseUntil": float(row[1]),
            "command": str(row[2]),
            "released": bool(metadata.get("released")),
        }

    def status(self) -> dict[str, Any]:
        state = self._load()
        return {
            "schema": "pillars_dcm.run_director_status.v1",
            "runId": self.run.name,
            "phase": state["phase"],
            "transition": state.get("transition", 0),
            "batchId": state.get("batchId"),
            "batchContentSha": state.get("batchContentSha"),
            "responsePath": state.get("responsePath"),
            "nextCommand": self._next_command(state),
            "lock": self._lease_status(),
            "lastError": state.get("lastError"),
        }

    def _next_command(self, state: dict[str, Any]) -> str:
        phase = state["phase"]
        if phase == "READ_CHECKPOINT": return "director-step"
        if phase == "READ_MANIFEST": return "director-step"
        if phase == "SELECT_OR_RESUME_BATCH": return "director-step"
        if phase == "AWAITING_RESPONSE": return "place response at the sealed responsePath"
        if phase == "VALIDATE": return "director-step"
        if phase == "IMPORT": return "director-step"
        if phase == "COVERAGE": return "director-step"
        if phase == "CHECKPOINT_CAS": return "director-step"
        return "none"

    def _response_path(self, state: dict[str, Any]) -> Path | None:
        value = state.get("responsePath")
        if value:
            path = Path(str(value))
            return path if path.is_absolute() else self.run / path
        batch_id = state.get("batchId")
        if not batch_id:
            return None
        for candidate in (self.run / "responses" / f"{batch_id}.response.json",
                          self.run / "outbox" / f"{batch_id}.response.json",
                          self.run / "outbox" / f"{batch_id}.json"):
            if candidate.is_file():
                return candidate
        return self.run / "responses" / f"{batch_id}.response.json"

    @staticmethod
    def _batch_counts(batch: dict[str, Any]) -> tuple[int, int]:
        """Return bounded action/entity and dependent-offer counts.

        Older sealed envelopes did not persist a top-level dependent count.
        Recompute it from the immutable action rows instead of silently
        treating the missing value as zero.
        """
        actions = [row for row in (batch.get("actions") or []) if isinstance(row, dict)]
        selected = int(batch.get("selectedCount") or len(actions))
        raw_dependent = batch.get("dependentOfferCount")
        if raw_dependent is None:
            raw_dependent = batch.get("dependentOffers")
        if raw_dependent is None:
            raw_dependent = sum(
                int(row.get("dependentOfferCount") or row.get("dependentPropCount") or 0)
                for row in actions
            )
        return selected, int(raw_dependent or 0)

    def _checkpoint_batch(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Load the checkpoint and its active immutable envelope, if any."""
        checkpoint = read_json(self.run / "research_checkpoint.json") or {}
        if not isinstance(checkpoint, dict):
            return {}, {}
        batch_id = str(checkpoint.get("activeBatchId") or "")
        if not batch_id:
            return checkpoint, {}
        path = self.run / "research_batches" / f"{batch_id}.json"
        if not path.is_file():
            raise DirectorStateError("CHECKPOINT_ACTIVE_BATCH_MISSING")
        try:
            return checkpoint, load_batch(path)
        except (OSError, ValueError, TypeError) as exc:
            raise DirectorStateError("CHECKPOINT_ACTIVE_BATCH_INVALID") from exc

    def _reconcile_pointer(self, pointer: dict[str, Any], batch: dict[str, Any], *, checkpoint: dict[str, Any]) -> None:
        """Move only the mutable pointer back to the checkpoint authority.

        A previous side-effectful importer could publish a newer pointer before
        the checkpoint CAS completed.  The immutable envelopes remain intact;
        this repair makes the checkpoint-authoritative packet resumable and
        leaves an auditable, sanitized reconciliation receipt.
        """
        old_id = str(pointer.get("batchId") or "")
        new_id = str(batch.get("batchId") or "")
        if not old_id or not new_id or old_id == new_id:
            return
        pointer_path = self.run / "active_research_batch.json"
        receipt_path = self.run / "run_director_reconciliation.json"
        receipt = {
            "schema": "pillars_dcm.run_director.reconciliation.v1",
            "runId": self.run.name,
            "reason": "POINTER_AHEAD_OF_CHECKPOINT",
            "checkpointHash": checkpoint.get("checkpointHash"),
            "authoritativeBatchId": new_id,
            "authoritativeBatchContentSha": batch.get("batchContentSha"),
            "authoritativeEnvelope": f"research_batches/{new_id}.json",
            "supersededPointerBatchId": old_id,
            "supersededPointerBatchContentSha": pointer.get("batchContentSha"),
            "supersededEnvelope": f"research_batches/{old_id}.json",
            "immutableEnvelopesPreserved": True,
            "productionSelectionChanged": False,
            "predictiveClaim": "NONE",
        }
        with RunLock(self.run, command="director-reconcile") as lock:
            write_json(pointer_path, {
                "schema": "pillars_dcm.active_research_batch.v1",
                "runId": self.run.name,
                "batchId": new_id,
                "batchContentSha": batch.get("batchContentSha"),
                "envelopePath": f"research_batches/{new_id}.json",
            })
            write_json(receipt_path, receipt)
            lock.assert_fence()

    def step(self) -> dict[str, Any]:
        state = self._load()
        phase = state["phase"]
        if phase == "TERMINAL":
            return self.status()
        session = HostSession.open(self.run, workspace=self.workspace)

        if phase == "READ_CHECKPOINT":
            result = session.checkpoint_verify()
            if not result.get("valid"):
                raise DirectorStateError("CHECKPOINT_INVALID")
            state["phase"] = "READ_MANIFEST"
            state["lastError"] = None
            return self._save(state)

        if phase == "READ_MANIFEST":
            manifest = read_json(self.run / "run_manifest.json")
            if not isinstance(manifest, dict) or str(manifest.get("runId") or self.run.name) != self.run.name:
                raise DirectorStateError("MANIFEST_IDENTITY_MISMATCH")
            state["phase"] = "SELECT_OR_RESUME_BATCH"
            return self._save(state)

        if phase == "SELECT_OR_RESUME_BATCH":
            pointer = read_json(self.run / "active_research_batch.json") or {}
            checkpoint, checkpoint_batch = self._checkpoint_batch()
            pointer_id = str(pointer.get("batchId") or "")
            checkpoint_id = str(checkpoint.get("activeBatchId") or "")
            if pointer_id and checkpoint_id and pointer_id != checkpoint_id:
                # The checkpoint is the authority.  A pointer that moved
                # ahead of it is a recoverable legacy side effect, not a new
                # batch to execute.
                if not checkpoint_batch:
                    raise DirectorStateError("ACTIVE_BATCH_DIVERGENCE")
                self._reconcile_pointer(pointer, checkpoint_batch, checkpoint=checkpoint)
                pointer = read_json(self.run / "active_research_batch.json") or {}

            # Once the pointer's batch is already represented by the research
            # checkpoint, selection must create/resume the *next* packet.  A
            # director invocation must never wait on a completed batch again.
            if pointer.get("batchId") and str(pointer.get("batchId")) == checkpoint_id:
                batch = session.next_research_batch(
                    max_entities=self.max_entities,
                    max_dependent_offers=self.max_dependent_offers,
                )
            elif pointer.get("batchId"):
                batch_id = str(pointer["batchId"])
                envelope = Path(str(pointer.get("envelopePath") or self.run / "research_batches" / f"{batch_id}.json"))
                if not envelope.is_absolute():
                    envelope = self.run / envelope
                batch = load_batch(envelope)
            else:
                batch = session.next_research_batch(
                    max_entities=self.max_entities,
                    max_dependent_offers=self.max_dependent_offers,
                )
            selected, dependent = self._batch_counts(batch)
            if selected > self.max_entities or dependent > self.max_dependent_offers:
                raise DirectorStateError("BATCH_CAP_EXCEEDED")
            state.update({"batchId": batch.get("batchId"), "batchContentSha": batch.get("batchContentSha"),
                          "responsePath": str(self.run / "responses" / f"{batch.get('batchId')}.response.json"),
                          "phase": "AWAITING_RESPONSE" if selected else "TERMINAL"})
            return self._save(state)

        if phase == "AWAITING_RESPONSE":
            path = self._response_path(state)
            if path is None or not path.is_file():
                # This is a durable wait state, not a failed command and not a
                # writer lease.  The caller can poll status without mutation.
                return self.status() | {"waiting": True}
            state["responsePath"] = str(path)
            state["phase"] = "VALIDATE"
            return self._save(state)

        response = self._response_path(state)
        if response is None or not response.is_file():
            state["phase"] = "AWAITING_RESPONSE"
            return self._save(state)

        if phase == "VALIDATE":
            result = session.research_validate(response)
            if int(result.get("validCount") or 0) == 0 and int(result.get("failureCount") or 0) == 0:
                return self.status() | {"waiting": True, "validation": "EMPTY_RESPONSE"}
            state["phase"] = "IMPORT"
            return self._save(state)

        if phase == "IMPORT":
            result = session.import_evidence(response, select_next=False)
            state["phase"] = "COVERAGE"
            state["lastImport"] = {"imported": int(result.get("imported") or 0),
                                    "responseFailureCount": int(result.get("responseFailureCount") or 0)}
            return self._save(state)

        if phase == "COVERAGE":
            with RunLock(self.run, command="director-coverage") as lock:
                result = session.coverage(incremental=True, verify_full=True, select_next=False)
                lock.assert_fence()
            state["coverageHash"] = content_hash(result)
            state["phase"] = "CHECKPOINT_CAS"
            return self._save(state)

        if phase == "CHECKPOINT_CAS":
            with RunLock(self.run, command="director-checkpoint") as lock:
                checkpoint = session._persist_research_checkpoint(active_batch_id=state.get("batchId"))
                lock.assert_fence()
            state["checkpointHash"] = checkpoint.get("checkpointHash")
            state["phase"] = "SELECT_OR_RESUME_BATCH"
            state["responsePath"] = None
            return self._save(state)

        raise DirectorStateError(f"DIRECTOR_PHASE_UNHANDLED:{phase}")

    def run_until_awaiting(self) -> dict[str, Any]:
        while True:
            result = self.step()
            phase = result.get("phase")
            if phase in {"AWAITING_RESPONSE", "TERMINAL"} or result.get("waiting"):
                status = self.status()
                status.update({key: value for key, value in result.items() if key not in status})
                return status


__all__ = ["DIRECTOR_SCHEMA", "DirectorStateError", "RunDirector"]
