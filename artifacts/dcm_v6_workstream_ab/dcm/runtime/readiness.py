"""Production/readiness gate reporting without conflating validation classes."""
from __future__ import annotations

from typing import Any


def build_readiness(
    *,
    mount: dict[str, Any],
    schema: dict[str, Any],
    research: dict[str, Any],
    board: dict[str, Any],
    conservation_failures: int,
    software_e2e_complete: bool,
    host_performance_certified: bool,
    learning_revision: str,
    predictive_claim: str,
) -> dict[str, Any]:
    rows = list(board.get("rows") or [])
    offered_unknown = sum(
        not bool(row.get("offeredHigher")) and not bool(row.get("offeredLower"))
        for row in rows
        if row.get("modifier") != "GOBLIN"
    )
    gates = [
        {
            "id": "SOFTWARE_E2E",
            "passed": bool(software_e2e_complete),
            "class": "ENGINEERING",
            "state": "PASS" if software_e2e_complete else "FAIL",
        },
        {
            "id": "CANONICAL_V541",
            "passed": mount.get("state") == "HASH_VERIFIED_EXTRACTED",
            "class": "EXTERNAL_ARTIFACT",
            "state": str(mount.get("state") or "ABSENT"),
        },
        {
            "id": "PHASE_BC_SCHEMA",
            "passed": bool(schema.get("productionEligible")) and schema.get("state") == "HASH_VERIFIED",
            "class": "EXTERNAL_ARTIFACT",
            "state": str(schema.get("state") or "ABSENT"),
        },
        {
            "id": "PRODUCTION_RESEARCH",
            "passed": bool(research.get("production_ready")),
            "class": "RUNTIME_EVIDENCE",
            "state": str(research.get("evidence_mode") or "INCOMPLETE"),
        },
        {
            "id": "OFFERED_SIDE_INTEGRITY",
            "passed": offered_unknown == 0,
            "class": "BOARD_INTEGRITY",
            "state": "PASS" if offered_unknown == 0 else "UNRESOLVED",
            "count": offered_unknown,
        },
        {
            "id": "PRIMITIVE_CONSERVATION",
            "passed": int(conservation_failures) == 0,
            "class": "MODEL_INTEGRITY",
            "state": "PASS" if int(conservation_failures) == 0 else "FAIL",
            "count": int(conservation_failures),
        },
        {
            "id": "HOST_PERFORMANCE_CERTIFICATION",
            "passed": bool(host_performance_certified),
            "class": "MEASURED_CERTIFICATION",
            "state": "PASS" if host_performance_certified else "NOT_CERTIFIED",
        },
        {
            "id": "CHRONOLOGICAL_PREDICTIVE_VALIDATION",
            "passed": learning_revision != "LR000000" and predictive_claim != "NONE",
            "class": "FUTURE_VALIDATION",
            "state": (
                "PROMOTED"
                if learning_revision != "LR000000" and predictive_claim != "NONE"
                else "UNEARNED"
            ),
        },
    ]

    by_id = {gate["id"]: gate for gate in gates}
    selection_gate_ids = (
        "SOFTWARE_E2E",
        "CANONICAL_V541",
        "PHASE_BC_SCHEMA",
        "PRODUCTION_RESEARCH",
        "PRIMITIVE_CONSERVATION",
    )
    system_cert_ids = selection_gate_ids + ("HOST_PERFORMANCE_CERTIFICATION",)
    return {
        "productionSelectionReady": all(by_id[g]["passed"] for g in selection_gate_ids),
        "systemCertified": all(by_id[g]["passed"] for g in system_cert_ids),
        "predictiveValidationEarned": by_id["CHRONOLOGICAL_PREDICTIVE_VALIDATION"]["passed"],
        "gates": gates,
        "blocking": [gate for gate in gates if not gate["passed"]],
        "note": (
            "Production selection readiness, host certification, and predictive "
            "validation are distinct contracts and must never be conflated. "
            "productionSelectionReady does not gate ranked Top 25 or the modeled "
            "strict card; it only certifies the production-certified layer."
        ),
    }
