"""Fail-closed preselection gate for fragile lines and incomplete research."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

REQUIRED_RESEARCH = frozenset({"player_role", "availability", "recent_usage", "matchup", "current_line"})

@dataclass(frozen=True)
class PreselectionDecision:
    state: str
    reason: str
    directional_margin_sigma: float | None
    missing_research: tuple[str, ...]
    @property
    def may_select(self) -> bool:
        return self.state == "ADVANCE_TO_DIRECTIONAL_GATE"
    def as_dict(self) -> dict[str, Any]:
        return {"state": self.state, "reason": self.reason, "directionalMarginSigma": self.directional_margin_sigma, "missingResearch": list(self.missing_research), "maySelect": self.may_select}

def _missing_research(research: Mapping[str, Any] | None) -> tuple[str, ...]:
    research = research or {}
    return tuple(sorted(key for key in REQUIRED_RESEARCH if research.get(key) is not True))

def assess_preselection(*, offered_line: Any, projected_mean: Any, projected_stddev: Any, minimum_margin_sigma: Any, research: Mapping[str, Any] | None, modifier: Any = "STANDARD", target_book_offer_present: bool = True, explicit_side: Any = "UNKNOWN") -> PreselectionDecision:
    """Require versioned market policy, target offer, and focused research."""
    if str(modifier or "").upper() == "GOBLIN":
        return PreselectionDecision("EXCLUDED_GOBLIN", "GOBLIN_SELECTION_FORBIDDEN", None, ())
    if str(modifier or "").upper() != "STANDARD":
        return PreselectionDecision("BLOCKED_MODIFIER", "TARGET_MODIFIER_NOT_STANDARD", None, ())
    if not target_book_offer_present:
        return PreselectionDecision("BLOCKED_TARGET_OFFER", "TARGET_BOOK_OFFER_MISSING", None, ())
    side = str(explicit_side or "").upper()
    if side not in {"MORE", "LESS"}:
        return PreselectionDecision("BLOCKED_SIDE", "EXPLICIT_TARGET_SIDE_REQUIRED", None, ())
    missing = _missing_research(research)
    try:
        line, mean, stddev, required = map(float, (offered_line, projected_mean, projected_stddev, minimum_margin_sigma))
    except (TypeError, ValueError):
        return PreselectionDecision("RESEARCH_REQUIRED_LINE_PROXIMITY", "MODEL_DISTRIBUTION_OR_POLICY_MISSING", None, missing)
    if not all(isfinite(v) for v in (line, mean, stddev, required)) or stddev <= 0 or required < 0:
        return PreselectionDecision("RESEARCH_REQUIRED_LINE_PROXIMITY", "MODEL_DISTRIBUTION_OR_POLICY_INVALID", None, missing)
    margin = (mean - line) / stddev
    directional = margin if side == "MORE" else -margin
    if directional < required:
        return PreselectionDecision("RESEARCH_REQUIRED_LINE_PROXIMITY", "DIRECTIONAL_EDGE_INSIDE_CALIBRATED_UNCERTAINTY_BAND", directional, missing)
    if missing:
        return PreselectionDecision("RESEARCH_REQUIRED_TARGETED", "PLAYER_AND_MATCHUP_RESEARCH_INCOMPLETE", directional, missing)
    return PreselectionDecision("ADVANCE_TO_DIRECTIONAL_GATE", "ROBUST_MARGIN_AND_TARGETED_RESEARCH_COMPLETE", directional, ())