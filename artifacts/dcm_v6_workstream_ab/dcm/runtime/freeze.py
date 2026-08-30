"""Canonical semantic forecast hashing shared by runner and postgame."""
from __future__ import annotations

from typing import Any

from dcm.contracts.hashes import content_hash

_CONTEXT_FIELDS = (
    "runId",
    "dcmVersion",
    "learningRevision",
    "schemaId",
    "schemaHash",
    "modelConfigHash",
    "calibrationStateHash",
    "harSha256",
    "forecastCutoff",
    "boardHash",
)


def forecast_hash_payload(
    context: dict[str, Any],
    population: list[dict[str, Any]],
    strict_card: list[dict[str, Any]],
    top25_ranked: list[dict[str, Any]],
) -> dict[str, Any]:
    forecasts = []
    for row in sorted(population, key=lambda x: str(x.get("projectionId") or "")):
        forecasts.append(
            {
                "projectionId": row.get("projectionId"),
                "line": row.get("line"),
                "modifier": row.get("modifier"),
                "offeredHigher": row.get("offeredHigher"),
                "offeredLower": row.get("offeredLower"),
                "state": row.get("state"),
                "blocker": row.get("blocker"),
                "grade": row.get("grade"),
                "selectedSide": row.get("direction"),
                "rawP": row.get("rawP"),
                "calibratedP": row.get("calibratedP"),
                "evidenceSafeP": row.get("evidenceSafeP"),
                "pHigher": row.get("pHigher"),
                "pLower": row.get("pLower"),
                "pPush": row.get("pPush"),
                "lowerBound": row.get("lowerBound"),
                "parameterSnapshotHash": row.get("parameterSnapshotHash"),
                "rank": row.get("rank"),
                "selectionScore": row.get("selectionScore"),
                "productionSelectable": bool(row.get("productionSelectable", False)),
            }
        )
    payload = {field: context.get(field) for field in _CONTEXT_FIELDS}
    payload["forecasts"] = forecasts
    payload["card"] = [row.get("projectionId") for row in strict_card]
    payload["ranked"] = [row.get("projectionId") for row in top25_ranked]
    return payload


def compute_forecast_hash(
    context: dict[str, Any],
    population: list[dict[str, Any]],
    strict_card: list[dict[str, Any]],
    top25_ranked: list[dict[str, Any]],
) -> str:
    return content_hash(forecast_hash_payload(context, population, strict_card, top25_ranked))
