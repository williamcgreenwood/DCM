"""SourceAdapter protocol and canonical adapter records.

Adapters own website/HTML/table parsing. Model code (parameters.py) consumes
normalized records and never parses host pages inline.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlsplit

from dcm.contracts.hashes import content_hash
from dcm.research.authority import classify_source


ADAPTER_RECORD_KEYS = (
    "url",
    "hostname",
    "retrievedAt",
    "publishedAt",
    "raw",
    "sourceClass",
    "adapterId",
    "adapterVersion",
    "contentHash",
    "fields",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def live_fetch_enabled(flag: bool | None = None) -> bool:
    if flag is True:
        return True
    if flag is False:
        return False
    return str(os.environ.get("DCM_LIVE_FETCH") or "").strip().lower() in {"1", "true", "yes", "on"}


def hostname_of(url: str) -> str:
    return str(urlsplit(str(url) or "").hostname or "")


def adapter_record(
    *,
    url: str,
    raw: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
    retrieved_at: str | None = None,
    published_at: str | None = None,
    source_class: str | None = None,
    adapter_id: str,
    adapter_version: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retrieved = retrieved_at or utc_now()
    published = published_at or retrieved
    klass = source_class or classify_source(adapter_id, url)
    body: dict[str, Any] = {
        "url": str(url or ""),
        "hostname": hostname_of(url),
        "retrievedAt": retrieved,
        "publishedAt": published,
        "raw": dict(raw or {}),
        "sourceClass": klass,
        "adapterId": adapter_id,
        "adapterVersion": adapter_version,
        "fields": dict(fields or {}),
    }
    if extra:
        for key, value in extra.items():
            if key not in body:
                body[key] = value
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    return body


class SourceAdapter(Protocol):
    """Fetch/normalize boundary. CI uses fixtures; live fetch is opt-in."""

    adapter_id: str
    adapter_version: str
    source_class: str

    def fetch(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Return a SourceDocument-shaped dict (url, text/html, timestamps)."""
        ...

    def normalize(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        """Return adapter records with provenance + content hash."""
        ...


def fetch_normalize(adapter: SourceAdapter, spec: dict[str, Any]) -> list[dict[str, Any]]:
    return adapter.normalize(adapter.fetch(spec))
