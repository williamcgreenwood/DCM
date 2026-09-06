"""ArchiveReceipt + LocalFallbackRunStore.

Drive is object storage, not the primary query engine. Remote archive
failure must not invalidate a forecast. Local fallback is always legal.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash


def build_archive_receipt(
    dest: Path,
    *,
    merkel_root: str | None = None,
    drive_status: str = "NOT_CONFIGURED",
    github_status: str = "NOT_PUSHED",
    local_status: str = "WRITTEN",
    hashes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dest = Path(dest)
    hashes = dict(hashes or {})
    body = {
        "schema": "pillars_dcm.archive_receipt.v1",
        "runDest": str(dest),
        "merkleRoot": merkel_root or hashes.get("runMerkleRoot") or hashes.get("frozenForecastHash") or hashes.get("merkleRoot") or hashes.get("freeze"),
        "localFallback": {
            "status": local_status,
            "path": str(dest),
            "promoted": local_status == "WRITTEN" and drive_status != "WRITTEN",
        },
        "drive": {
            "status": drive_status,
            "note": "Drive is object storage. Local indexes identify exact objects before any Drive fetch.",
        },
        "github": {
            "status": github_status,
            "note": "Secondary archive. Forecast does not depend on GitHub write access.",
        },
        "archiveStatus": "LOCAL_FALLBACK" if drive_status != "WRITTEN" else "DRIVE_PRIMARY",
        "remoteFailureInvalidatesForecast": False,
        "hashes": {
            "har": hashes.get("harSha256"),
            "evidence": hashes.get("evidenceHash"),
            "featureStore": hashes.get("featureStoreHash"),
            "parameterSnapshots": hashes.get("parameterSnapshotHashes"),
            "eventWorld": hashes.get("eventWorldHash"),
            "ranking": hashes.get("rankingHash"),
            "freeze": hashes.get("frozenForecastHash") or hashes.get("freezeHash") or hashes.get("freeze"),
            "merkleRoot": merkel_root or hashes.get("runMerkleRoot") or hashes.get("merkleRoot"),
        },
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


def persist_archive_receipt(dest: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "archive_receipt.json"
    body = dict(receipt)
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest / "archive-status.json").write_text(
        json.dumps({"status": body.get("archiveStatus"), "receiptHash": body.get("contentHash")}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return body


def archive_retry(dest: Path, *, drive_status: str | None = None, github_status: str | None = None) -> dict[str, Any]:
    """Retry remote archive. Local freeze is never invalidated."""
    dest = Path(dest)
    existing: dict[str, Any] = {}
    path = dest / "archive_receipt.json"
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    hashes = existing.get("hashes") if isinstance(existing.get("hashes"), dict) else {}
    receipt = build_archive_receipt(
        dest,
        merkel_root=existing.get("merkleRoot"),
        drive_status=drive_status or (existing.get("drive") or {}).get("status") or "NOT_CONFIGURED",
        github_status=github_status or (existing.get("github") or {}).get("status") or "NOT_PUSHED",
        local_status="WRITTEN",
        hashes=hashes,
    )
    receipt["retried"] = True
    persist_archive_receipt(dest, receipt)
    (dest / "archive-retry.json").write_text(
        json.dumps({"retried": True, "receiptHash": receipt.get("contentHash"), "remoteFailureInvalidatesForecast": False}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def archive_reconcile(dest: Path) -> dict[str, Any]:
    """Reconcile local freeze bytes against the receipt. Missing remote is legal."""
    dest = Path(dest)
    freeze_path = dest / "frozen_forecast.json"
    receipt_path = dest / "archive_receipt.json"
    freeze_present = freeze_path.is_file()
    receipt: dict[str, Any] = {}
    if receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            receipt = {}
    freeze_hash = None
    if freeze_present:
        try:
            freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
            freeze_hash = freeze.get("frozenForecastHash") if isinstance(freeze, dict) else None
        except (OSError, json.JSONDecodeError):
            freeze_hash = None
    declared = (receipt.get("hashes") or {}).get("freeze") if isinstance(receipt.get("hashes"), dict) else None
    body = {
        "schema": "pillars_dcm.archive_reconcile.v1",
        "freezePresent": freeze_present,
        "receiptPresent": bool(receipt),
        "freezeHash": freeze_hash,
        "receiptFreezeHash": declared,
        "hashesMatch": bool(freeze_hash) and freeze_hash == declared,
        "remoteFailureInvalidatesForecast": False,
        "localFallbackLegal": True,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "archive-reconcile.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return body


class LocalFallbackRunStore:
    """Promoted when Drive/GitHub cannot complete. Never blocks freeze."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, name: str, payload: Mapping[str, Any]) -> Path:
        path = self.root / name
        path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        return path

    def get(self, name: str) -> dict[str, Any] | None:
        path = self.root / name
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
