"""Deterministic, privacy-aware routing for DCM artifacts.

Drive is a durable object store; it is not a search engine or a place to
upload an entire run directory.  This module produces a stable folder/object
route that a host connector can execute after validating folder IDs and
reading the uploaded object back.  It deliberately has no Drive API
dependency, which keeps the Python engine runnable in ChatGPT Work mode and
in a clean offline installation.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from dcm.contracts.hashes import content_hash


STORAGE_ROUTE_SCHEMA = "pillars_dcm.storage_route.v1"
STORAGE_REGISTRY_SCHEMA = "pillars_dcm.drive_folder_registry.v1"
SAFE_SUMMARY = "SAFE_SUMMARY"
LOCAL_ONLY = "LOCAL_ONLY"
REMOTE_REQUIRED = "REMOTE_REQUIRED"

# The key names are stable API.  Folder IDs are environment-specific and are
# supplied by the host in a separate registry; code never guesses them.
DRIVE_HIERARCHY: dict[str, tuple[str, ...]] = {
    "00_control": ("00_control",),
    "01_inputs": ("01_inputs",),
    "02_research": ("02_research", "{sport}", "{period}"),
    "03_features": ("03_features", "{sport}", "{period}"),
    "04_models": ("04_models", "{sport}", "{period}"),
    "05_runs": ("05_runs", "{sport}", "{period}", "{run_id}"),
    "06_settlements": ("06_settlements", "{sport}", "{period}"),
    "07_learning": ("07_learning", "{sport}", "{period}"),
    "08_reports": ("08_reports", "{sport}", "{period}"),
    "09_engineering": ("09_engineering", "{period}", "{run_id}"),
}

_FOLDER_BY_PREFIX = {
    "input_": "01_inputs",
    "har_": "01_inputs",
    "research": "02_research",
    "evidence": "02_research",
    "material_fact": "02_research",
    "feature": "03_features",
    "parameter": "03_features",
    "signal": "03_features",
    "model": "04_models",
    "event_world": "04_models",
    "top": "05_runs",
    "full_population": "05_runs",
    "population": "05_runs",
    "freeze": "05_runs",
    "frozen_": "05_runs",
    "checkpoint": "09_engineering",
    "run_": "09_engineering",
    "performance": "09_engineering",
    "algorithm": "09_engineering",
    "audit": "09_engineering",
    "archive": "09_engineering",
    "storage_": "09_engineering",
    "settlement": "06_settlements",
    "learning": "07_learning",
    "report": "08_reports",
}

_FORBIDDEN_NAME = re.compile(
    r"(?i)(\.har$|\.sqlite(?:3)?$|cookie|authorization|bearer|token|secret|password|credential|api[-_]?key)"
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _slug(value: Any, *, fallback: str = "unknown") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    text = text.strip("._-")[:96]
    return text or fallback


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_filename(filename: Any) -> str:
    name = Path(str(filename or "")).name
    if not name or name in {".", ".."} or _FORBIDDEN_NAME.search(name):
        raise ValueError("STORAGE_OBJECT_FORBIDDEN_PRIVACY_CLASS")
    return _slug(name, fallback="artifact")


@dataclass(frozen=True)
class FolderRegistry:
    """Validated environment-specific Drive folder IDs.

    ``folders`` maps hierarchy keys to IDs.  IDs are opaque and never
    fabricated.  The registry is safe to persist because it contains no
    credentials or artifact contents.
    """

    root_id: str | None
    folders: dict[str, str]
    names: dict[str, str]
    schema: str = STORAGE_REGISTRY_SCHEMA

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "FolderRegistry":
        value = value if isinstance(value, Mapping) else {}
        if value and value.get("schema") not in {None, STORAGE_REGISTRY_SCHEMA}:
            raise ValueError("DRIVE_FOLDER_REGISTRY_SCHEMA_UNSUPPORTED")
        raw = value.get("folders") if isinstance(value.get("folders"), Mapping) else {}
        folders: dict[str, str] = {}
        names: dict[str, str] = {}
        seen_ids: set[str] = set()
        for key, raw_item in raw.items():
            if isinstance(raw_item, Mapping):
                folder_id = str(raw_item.get("id") or "")
                name = str(raw_item.get("name") or key)
            else:
                folder_id = str(raw_item or "")
                name = str(key)
            if not folder_id:
                continue
            if not _SAFE_ID.fullmatch(folder_id):
                raise ValueError(f"DRIVE_FOLDER_ID_INVALID:{key}")
            if folder_id in seen_ids:
                raise ValueError("DRIVE_FOLDER_ID_DUPLICATE")
            seen_ids.add(folder_id)
            folders[str(key)] = folder_id
            names[str(key)] = name
        root_id = str(value.get("rootId") or "") or None
        if root_id and not _SAFE_ID.fullmatch(root_id):
            raise ValueError("DRIVE_ROOT_ID_INVALID")
        return cls(root_id=root_id, folders=folders, names=names)

    def validate(self, *, required: Iterable[str] = ()) -> list[str]:
        errors: list[str] = []
        for key in required:
            if key not in DRIVE_HIERARCHY:
                errors.append(f"UNKNOWN_FOLDER_KEY:{key}")
            elif not self.folders.get(key):
                errors.append(f"FOLDER_ID_MISSING:{key}")
        return errors

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": self.schema,
            "rootIdConfigured": bool(self.root_id),
            "folderKeys": sorted(self.folders),
            "folderCount": len(self.folders),
            "requiredKeys": sorted(DRIVE_HIERARCHY),
            "missingKeys": self.validate(required=DRIVE_HIERARCHY),
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body


@dataclass(frozen=True)
class StorageRoute:
    artifact: str
    folder_key: str
    relative_path: str
    storage_class: str
    object_hash: str | None
    schema: str | None
    remote_folder_id: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact": self.artifact,
            "folderKey": self.folder_key,
            "relativePath": self.relative_path,
            "storageClass": self.storage_class,
            "objectHash": self.object_hash,
            "schema": self.schema,
            "remoteFolderId": self.remote_folder_id,
            "status": self.status,
        }


class StorageRouter:
    """Build and persist deterministic local/Drive routes for one run."""

    def __init__(self, run_root: Path, *, registry: FolderRegistry | None = None) -> None:
        self.run_root = Path(run_root)
        self.registry = registry or FolderRegistry(root_id=None, folders={}, names={})

    @staticmethod
    def folder_for(filename: str) -> str:
        lower = filename.lower()
        for prefix, folder in _FOLDER_BY_PREFIX.items():
            if lower.startswith(prefix):
                return folder
        return "09_engineering"

    def route(
        self,
        *,
        filename: str,
        sport: str = "CFB",
        period: str = "current",
        run_id: str = "run",
        folder_key: str | None = None,
        object_hash: str | None = None,
        schema: str | None = None,
        storage_class: str = SAFE_SUMMARY,
    ) -> StorageRoute:
        name = _safe_filename(filename)
        key = folder_key or self.folder_for(name)
        if key not in DRIVE_HIERARCHY:
            raise ValueError(f"STORAGE_FOLDER_KEY_UNKNOWN:{key}")
        parts = [
            part.format(sport=_slug(sport, fallback="unknown"), period=_slug(period), run_id=_slug(run_id))
            for part in DRIVE_HIERARCHY[key]
        ]
        relative = "/".join([*parts, name])
        folder_id = self.registry.folders.get(key)
        status = "REMOTE_READY" if folder_id else "LOCAL_ROUTE_ONLY"
        return StorageRoute(name, key, relative, storage_class, object_hash, schema, folder_id, status)

    def stage_bytes(self, route: StorageRoute, data: bytes) -> dict[str, Any]:
        """Stage an immutable safe object and return its verified manifest."""
        if route.storage_class != SAFE_SUMMARY:
            raise ValueError("STORAGE_STAGE_REQUIRES_SAFE_SUMMARY")
        digest = _sha256_bytes(data)
        if route.object_hash and route.object_hash != digest:
            raise ValueError("STORAGE_OBJECT_HASH_MISMATCH")
        path = self.run_root / "storage" / route.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_bytes()
            if existing != data:
                raise RuntimeError("STORAGE_IMMUTABLE_OBJECT_CONFLICT")
        else:
            tmp = path.with_suffix(path.suffix + ".tmp")
            with tmp.open("wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(path)
        body: dict[str, Any] = {
            "schema": "pillars_dcm.storage_object_manifest.v1",
            "artifact": route.artifact,
            "relativePath": route.relative_path,
            "objectHash": digest,
            "sizeBytes": len(data),
            "artifactSchema": route.schema,
            "storageClass": route.storage_class,
            "remoteFolderId": route.remote_folder_id,
            "rawBytes": False,
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        return body

    def persist_run_route(
        self,
        *,
        run_id: str,
        sport: str = "CFB",
        period: str = "current",
        artifact_paths: Iterable[Path] = (),
    ) -> dict[str, Any]:
        routes: list[dict[str, Any]] = []
        blocked: list[dict[str, str]] = []
        for raw_path in sorted((Path(p) for p in artifact_paths), key=lambda p: str(p)):
            if not raw_path.is_file():
                continue
            name = raw_path.name
            if _FORBIDDEN_NAME.search(name):
                blocked.append({"artifact": name, "reason": "PRIVACY_OR_QUERY_STORE_LOCAL_ONLY"})
                continue
            try:
                digest = _sha256_bytes(raw_path.read_bytes())
            except OSError:
                blocked.append({"artifact": name, "reason": "READ_FAILED_LOCAL_ONLY"})
                continue
            route = self.route(
                filename=name,
                sport=sport,
                period=period,
                run_id=run_id,
                object_hash=digest,
                schema="json_or_jsonl_safe_projection",
            )
            routes.append(route.to_dict())
        body: dict[str, Any] = {
            "schema": STORAGE_ROUTE_SCHEMA,
            "runId": str(run_id),
            "sport": _slug(sport),
            "period": _slug(period),
            "drive": self.registry.snapshot(),
            "routes": routes,
            "blockedLocalOnly": blocked,
            "remoteUploadPolicy": "HOST_CONNECTOR_ONLY_AFTER_EXACT_READBACK",
            "queryPolicy": "LOCAL_INDEX_BEFORE_REMOTE_FETCH",
            "rawArtifactsUploaded": False,
        }
        body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
        self.run_root.mkdir(parents=True, exist_ok=True)
        (self.run_root / "storage_route.json").write_text(
            json.dumps(body, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        return body


__all__ = [
    "DRIVE_HIERARCHY",
    "FolderRegistry",
    "LOCAL_ONLY",
    "REMOTE_REQUIRED",
    "SAFE_SUMMARY",
    "STORAGE_REGISTRY_SCHEMA",
    "STORAGE_ROUTE_SCHEMA",
    "StorageRoute",
    "StorageRouter",
]
