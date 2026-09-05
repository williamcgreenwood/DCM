"""Posterior-aware ranking without conflating probability and quality."""
from __future__ import annotations

import hashlib
import random
from typing import Any

from dcm.algorithms.sorting import heap_topk, timsort


def selection_score(p: dict[str, Any]) -> float:
    safe = float(p.get("evidenceSafeP") or 0.5)
    lb = float(p.get("lowerBound") or 0.0)
    reliability = float(p.get("reliability") or 0.0)
    quality = float(p.get("dataQuality") or 0.0)
    fragility = float(p.get("fragility") or 1.0)
    ood = float(p.get("oodRisk") or 1.0)
    false_sign = float(p.get("falseSignRisk") or 0.5)
    return (
        (safe - 0.5) * 0.46 + (lb - 0.5) * 0.24 + reliability * 0.10 + quality * 0.08
        - fragility * 0.05 - ood * 0.04 - false_sign * 0.03
    )


def frontier_slice(ranked: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """Partial Top-K without requiring a second full-board sort."""
    return heap_topk(
        ranked,
        k,
        key=lambda p: (float(p.get("selectionScore") or -999), str((p.get("row") or {}).get("projectionId") or "")),
    )


def rank_candidates(candidates: list[dict[str, Any]], *, top_k: int = 25, draws: int = 256, seed: str = "DCM_RANK") -> list[dict[str, Any]]:
    for p in candidates:
        p["selectionScore"] = selection_score(p)
    ranked = timsort(
        candidates,
        key=lambda p: (float(p.get("selectionScore") or -999), str(p["row"].get("projectionId"))),
        reverse=True,
    )
    if not ranked:
        return ranked
    hit = {str(p["row"]["projectionId"]): 0 for p in ranked}
    base_seed = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    rng = random.Random(base_seed)
    samples = max(32, draws)
    for _ in range(samples):
        sampled = []
        for p in ranked:
            sd = 0.015 + float(p.get("epistemicUncertainty") or 0.2) * 0.10 + float(p.get("volatility") or 0.5) * 0.02
            sampled.append((rng.gauss(float(p["selectionScore"]), sd), p))
        top = heap_topk(
            sampled,
            min(top_k, len(sampled)),
            key=lambda item: (item[0], str(item[1]["row"].get("projectionId"))),
        )
        for _, p in top:
            hit[str(p["row"]["projectionId"])] += 1
    max_score = max(float(p["selectionScore"]) for p in ranked)
    for i, p in enumerate(ranked, 1):
        pid = str(p["row"]["projectionId"])
        p["rank"] = i
        p["topKInclusionP"] = hit[pid] / samples
        p["posteriorRegret"] = max(0.0, max_score - float(p["selectionScore"]))
        p["rankStability"] = p["topKInclusionP"] if i <= top_k else 1.0 - p["topKInclusionP"]
    return ranked
