"""Safe, machine-readable runtime and CI diagnostics.

Diagnostics identify the failing contract and recovery command while removing
secrets, bearer tokens, raw URLs, and private capture values.  The receipt is
intended for CI artifacts and Drive hand-offs, not as a replacement for a
developer's local traceback.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import traceback
from pathlib import Path
from typing import Any, Mapping

from dcm.contracts.hashes import content_hash


DIAGNOSTICS_SCHEMA = "pillars_dcm.runtime_diagnostics.v1"
_SECRET_KEY = re.compile(r"(token|secret|password|authorization|cookie|api[_-]?key|credential|private[_-]?key)", re.I)
_URL = re.compile(r"https?://[^\s\"']+", re.I)
_INLINE_SECRET = re.compile(r"(?i)\b(?:bearer\s+|token\s*[=:]\s*|secret\s*[=:]\s*|api[_-]?key\s*[=:]\s*)([^\s,;]+)")


def _safe(value: Any, *, key: str = "") -> Any:
    if _SECRET_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): _safe(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v, key=key) for v in value[:1000]]
    if isinstance(value, tuple):
        return [_safe(v, key=key) for v in value[:1000]]
    if isinstance(value, str):
        cleaned = _URL.sub("[URL_REDACTED]", value)
        cleaned = _INLINE_SECRET.sub("[SECRET_REDACTED]", cleaned)
        return cleaned[:1000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:1000]


def _exception_info(exc: BaseException | None) -> dict[str, Any]:
    if exc is None:
        return {"type": None, "message": None, "tracebackDigest": None, "location": None}
    trace = traceback.format_exc()
    lines = [line.strip() for line in trace.splitlines() if line.strip()]
    location = next((line for line in reversed(lines) if line.startswith("File ")), None)
    return {
        "type": type(exc).__name__,
        "message": _safe(str(exc)),
        "tracebackDigest": hashlib.sha256(trace.encode("utf-8", "replace")).hexdigest(),
        "location": _safe(location),
    }


def build_diagnostics(*, command: str, exit_code: int = 0, failure_code: str | None = None, exc: BaseException | None = None, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    env = os.environ
    body: dict[str, Any] = {
        "schema": DIAGNOSTICS_SCHEMA,
        "command": str(command),
        "exitCode": int(exit_code),
        "failureCode": str(failure_code or "") or None,
        "exception": _exception_info(exc),
        "workflow": {
            "ci": bool(env.get("CI")),
            "workflow": env.get("GITHUB_WORKFLOW"),
            "runId": env.get("GITHUB_RUN_ID"),
            "runAttempt": env.get("GITHUB_RUN_ATTEMPT"),
            "job": env.get("GITHUB_JOB"),
            "step": env.get("GITHUB_STEP_SUMMARY") is not None,
            "event": env.get("GITHUB_EVENT_NAME"),
            "ref": env.get("GITHUB_REF"),
            "sha": env.get("GITHUB_SHA"),
        },
        "affectedIds": _safe((context or {}).get("affectedIds") or []),
        "artifactHashes": _safe((context or {}).get("artifactHashes") or {}),
        "recoveryCommand": _safe((context or {}).get("recoveryCommand") or "dcm-host doctor --format json"),
        "context": _safe(dict(context or {})),
        "privacy": {"rawHar": False, "rawUrls": False, "secrets": False, "tracebackBody": False},
    }
    body["contentHash"] = content_hash(body)
    return body


def write_diagnostics(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = _safe(dict(payload))
    safe["contentHash"] = content_hash({k: v for k, v in safe.items() if k != "contentHash"})
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(safe, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    temp.replace(path)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("## DCM diagnostics\n\n")
            handle.write(f"- command: `{safe.get('command')}`\n")
            handle.write(f"- failure code: `{safe.get('failureCode') or 'none'}`\n")
            handle.write(f"- receipt hash: `{safe.get('contentHash')}`\n")
    return safe


__all__ = ["DIAGNOSTICS_SCHEMA", "build_diagnostics", "write_diagnostics"]
