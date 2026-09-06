"""Assemble chat_result.json from frozen run artifacts. No probability math."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dcm.chat.contracts import CHAT_RESULT_SCHEMA
from dcm.chat.state import read_json, write_json
from dcm.contracts.hashes import content_hash
from dcm.version import LEARNING_REVISION, PREDICTIVE_CLAIM, SOFTWARE


def build_report(dest: Path) -> dict[str, Any]:
    dest = Path(dest)
    freeze = read_json(dest / "freeze.json") or {}
    board = read_json(dest / "board.json") or {}
    accounting = read_json(dest / "accounting.json") or {}
    coverage = read_json(dest / "evidence_coverage.json") or read_json(dest / "evidence" / "coverage.json") or {}
    host_state = read_json(dest / "host_state.json") or {}
    ranked = read_json(dest / "top25_ranked.json") or []
    qualified = read_json(dest / "qualified.json") or read_json(dest / "production_certified.json") or []
    card = read_json(dest / "strict_card.json") or []
    directional = read_json(dest / "directional_passes.json") or []
    audit = read_json(dest / "audit" / "RUN_AUDIT.json") or read_json(dest / "audit.json") or {}
    modeled = []
    pop_path = dest / "population_full.jsonl"
    if pop_path.is_file():
        # Do not load the entire board into the chat result; counts come from freeze/accounting.
        pass
    body = {
        "schema": CHAT_RESULT_SCHEMA,
        "software": SOFTWARE,
        "learningRevision": LEARNING_REVISION,
        "predictiveClaim": PREDICTIVE_CLAIM,
        "runId": freeze.get("runId") or dest.name,
        "runState": freeze.get("runState") or host_state.get("runState"),
        "forecastCutoff": board.get("forecastCutoff") or host_state.get("forecastCutoff"),
        "boardAccounting": accounting or board.get("accounting") or {},
        "rawRows": freeze.get("rawRows") or len(board.get("rows") or []),
        "researchCoverage": {
            "complete": bool(coverage.get("complete")),
            "requested": coverage.get("requested"),
            "completeRequests": coverage.get("completeRequests"),
            "incompleteRequests": coverage.get("incompleteRequests"),
            "missingRequirementCount": coverage.get("missingRequirementCount"),
        },
        "top25Ranked": ranked if isinstance(ranked, list) else ranked.get("rows") or ranked.get("top25") or [],
        "qualified": qualified if isinstance(qualified, list) else qualified.get("rows") or [],
        "card": card if isinstance(card, list) else card.get("rows") or card.get("card") or [],
        "cardSize": freeze.get("cardSize") or freeze.get("modeledCardSize") or 0,
        "directionalPassTrap": directional if isinstance(directional, list) else [],
        "productionCertified": freeze.get("productionCertified"),
        "emptyCardReason": freeze.get("emptyCardReason"),
        "probabilityEngine": "python-dcm",
        "reliabilityIsNotProbability": True,
        "hostState": {
            "coverageEvaluated": bool(host_state.get("coverageEvaluated")),
            "forecastFrozen": bool(host_state.get("forecastFrozen")),
            "researchLoopCount": host_state.get("researchLoopCount"),
        },
        "audit": {
            "archiveIntegrityCertified": audit.get("archiveIntegrityCertified"),
            "evidenceCoverageCertified": audit.get("evidenceCoverageCertified"),
            "frozenForecastHash": audit.get("frozenForecastHash") or freeze.get("frozenForecastHash"),
        },
        "blockers": freeze.get("blockers") or [],
        "modeled": modeled,
    }
    body["contentHash"] = content_hash({k: v for k, v in body.items() if k != "contentHash"})
    write_json(dest / "chat_result.json", body)
    return body
