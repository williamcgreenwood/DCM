"""Capture authority and operator-controlled freshness policy.

A user-supplied HAR is an accepted source of platform facts for the run. This
module deliberately does not infer freshness from filenames or demand a
replacement capture. Downstream offer/model/root gates remain independent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

CAPTURE_AUTHORITY_SCHEMA = "pillars_dcm.capture_authority.v1"
USER_SUPPLIED_CAPTURE = "USER_SUPPLIED_CAPTURE"
SYNTHETIC_CAPTURE = "SYNTHETIC_FIXTURE"
OPERATOR_CONTROLLED_FRESHNESS = "OPERATOR_CONTROLLED"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_capture_authority(
    source_paths: Iterable[Path] = (),
    *,
    synthetic: bool = False,
    accepted: bool | None = None,
    source_count: int | None = None,
    source_hashes: Iterable[str] = (),
) -> dict[str, Any]:
    paths = [Path(value) for value in source_paths]
    hashes = sorted({str(value) for value in source_hashes if str(value)})
    if not hashes:
        hashes = sorted({_sha256(path) for path in paths if path.is_file()})
    count = int(source_count if source_count is not None else len(paths))
    is_accepted = bool(accepted if accepted is not None else (bool(paths) or bool(hashes)))
    mode = SYNTHETIC_CAPTURE if synthetic else USER_SUPPLIED_CAPTURE
    body: dict[str, Any] = {
        "schema": CAPTURE_AUTHORITY_SCHEMA,
        "mode": mode,
        "authority": "SYSTEM_FIXTURE" if synthetic else "USER_SUPPLIED",
        "status": "TEST_ONLY" if synthetic else "ACCEPTED" if is_accepted else "NOT_AVAILABLE",
        "accepted": is_accepted,
        "sourceCount": count,
        "harCount": count,
        "sourceHarSha256s": hashes,
        "freshnessPolicy": OPERATOR_CONTROLLED_FRESHNESS,
        "replacementCaptureRequired": False,
        "replacementCaptureReason": None,
        "temporalPolicy": "LATEST_AS_OF_FORECAST_CUTOFF",
        "selectionTemporalPolicy": "USE_VERIFIED_CAPTURE_METADATA_NOT_FILENAME",
        "downstreamPolicy": (
            "CONTINUE_RESEARCH_SETTLEMENT_TRAINING_CALIBRATION_SELECTION_AND_DIAGNOSTICS"
        ),
        "operatorInputRequired": False,
        "boardHarRequired": False,
        "note": (
            "The supplied capture is accepted for this run. The operator decides "
            "when a newer capture is wanted; no hidden freshness gate asks for one."
        ),
    }
    body["captureGateStatus"] = "PASS" if is_accepted else "FAIL_NO_AUTHORIZED_CAPTURE"
    body["contentHash"] = _content_hash(body)
    return body


def capture_gate_status(authority: Mapping[str, Any] | None) -> str:
    if not isinstance(authority, Mapping):
        return "FAIL_NO_AUTHORITY_RECORD"
    if authority.get("status") == "ACCEPTED" and authority.get("accepted") is True:
        return "PASS"
    if authority.get("status") == "TEST_ONLY":
        return "TEST_ONLY"
    return str(authority.get("captureGateStatus") or "FAIL_NO_AUTHORIZED_CAPTURE")


def _content_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "CAPTURE_AUTHORITY_SCHEMA",
    "OPERATOR_CONTROLLED_FRESHNESS",
    "SYNTHETIC_CAPTURE",
    "USER_SUPPLIED_CAPTURE",
    "build_capture_authority",
    "capture_gate_status",
]
