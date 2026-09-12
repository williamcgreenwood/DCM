"""Fail-closed preselection gate for fragile lines and incomplete research."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from dcm.exclusions import permanent_subject_exclusion

REQUIRED_RESEARCH = frozenset({"player_role", "availability", "recent_usage", "matchup", "current_line"})
OUTLIER_PRESELECTION_POLICY_VERSION = "OUTLIER_PRESELECTION_V1"
OUTLIER_MINIMUM_MARGIN_SIGMA = 0.25


def _support_n(value: Any) -> int:
    """Coerce evidence support counts without allowing malformed captures to raise."""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


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
        return {"state": self.state, "reason": self.reason, "directionalMarginSigma": self.directional_margin_sigma,
                "missingResearch": list(self.missing_research), "maySelect": self.may_select}


def _missing_research(research: Mapping[str, Any] | None) -> tuple[str, ...]:
    research = research or {}
    return tuple(sorted(key for key in REQUIRED_RESEARCH if research.get(key) is not True))


def research_flags_from_snapshot(snapshot: Mapping[str, Any] | None, row: Mapping[str, Any] | None = None) -> dict[str, bool]:
    """Project canonical evidence state into the small preselection contract.

    These flags do not assert source authority; ResearchStore and coverage do
    that. They only keep a close Outlier line from reaching directional
    selection before the required player, availability, usage, matchup, and
    current-offer fields are present in the model snapshot.
    """
    snap = snapshot if isinstance(snapshot, Mapping) else {}
    source_row = row if isinstance(row, Mapping) else {}
    raw_scopes = snap.get("scopes_used") or []
    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]
    scopes = {str(value).upper() for value in raw_scopes if value}
    status = str(snap.get("status") or "").upper()
    role = str(snap.get("role") or "").upper()
    opp = snap.get("opportunity") if isinstance(snap.get("opportunity"), Mapping) else {}
    eff = snap.get("efficiency") if isinstance(snap.get("efficiency"), Mapping) else {}
    layers = snap.get("layers") if isinstance(snap.get("layers"), Mapping) else {}
    counterparty = layers.get("counterparty") if isinstance(layers.get("counterparty"), Mapping) else {}
    current_line = source_row.get("line") not in (None, "") and bool(
        source_row.get("marketDefinition") or source_row.get("marketDefinitionId") or source_row.get("market")
    )
    return {
        "player_role": role not in {"", "UNKNOWN", "NONE"} and ("SUBJECT" in scopes or bool(snap.get("role_epoch"))),
        "availability": status in {"ACTIVE", "AVAILABLE", "PROBABLE", "EXPECTED_ACTIVE"}
        and bool(snap.get("availabilityMixture"))
        and ("SUBJECT" in scopes or "EVENT" in scopes),
        "recent_usage": min(_support_n(opp.get("support_n")), _support_n(eff.get("support_n"))) >= 3
        and ("SUBJECT" in scopes or bool(snap.get("evidence_hashes"))),
        "matchup": bool(counterparty.get("counterpartyId") or source_row.get("opponentId") or source_row.get("opponent"))
        and ("COUNTERPARTY" in scopes or "EVENT" in scopes),
        "current_line": bool(current_line),
    }


def assess_preselection(*, offered_line: Any, projected_mean: Any, projected_stddev: Any,
                        minimum_margin_sigma: Any, research: Mapping[str, Any] | None,
                        modifier: Any = "STANDARD", target_book_offer_present: bool = True,
                        explicit_side: Any = "UNKNOWN",
                        subject: Mapping[str, Any] | None = None) -> PreselectionDecision:
    """Apply safety order before direction/portfolio selection.

    ``minimum_margin_sigma`` is supplied by a versioned market-specific policy;
    requiring it prevents an arbitrary global yards/receptions cutoff.
    """
    if str(modifier or "").upper() == "GOBLIN":
        return PreselectionDecision("EXCLUDED_GOBLIN", "GOBLIN_SELECTION_FORBIDDEN", None, ())
    if (excluded := permanent_subject_exclusion(subject)):
        return PreselectionDecision("EXCLUDED_SUBJECT", excluded, None, ())
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
