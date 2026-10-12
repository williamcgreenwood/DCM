"""Fail-closed canonical runner -> P0 LineageStore.freeze bridge.

Only current, independently revalidated, production-authorized CFB offers may
be frozen here. The runner's diagnostic frozen_forecast.json is NOT this ledger.
Missing market/prop identity, offer freshness, evidence or model provenance
blocks publication rather than generating surrogate IDs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from dcm.cfb.markets import canonicalize_cfb_market, contract_for
from dcm.contracts.hashes import content_hash
from dcm.runtime.lineage_integrity import (
    FreezeMember, LineageHalt, LineageStore, line_snapshot_id,
)

_HEX = re.compile(r"^[0-9a-f]{64}$")


def _utc(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise LineageHalt("PRODUCTION_FREEZE_TIME_INVALID") from exc
    if parsed.tzinfo is None:
        raise LineageHalt("PRODUCTION_FREEZE_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _hash(value: Any, code: str) -> str:
    text = str(value or "")
    if not _HEX.fullmatch(text):
        raise LineageHalt(code)
    return text



def bind_verified_runner_cfb_card(
    card: Sequence[Mapping[str, Any]],
    *,
    current_offers: Mapping[str, Mapping[str, Any]],
    parameter_snapshot_hashes: Sequence[str],
    feature_store_hash: str,
    evidence_graph_hash: str,
) -> list[dict[str, Any]]:
    """Bind modeled survivors to capture-origin IDs without manufacturing lineage."""
    _hash(feature_store_hash, "PRODUCTION_FREEZE_FEATURE_STORE_REQUIRED")
    _hash(evidence_graph_hash, "PRODUCTION_FREEZE_EVIDENCE_GRAPH_REQUIRED")
    known_parameters = set(parameter_snapshot_hashes)
    if not known_parameters or any(not _HEX.fullmatch(str(h)) for h in known_parameters):
        raise LineageHalt("PRODUCTION_FREEZE_PARAMETER_INDEX_INVALID")
    prepared: list[dict[str, Any]] = []
    for candidate in card:
        row = candidate.get("row")
        if not isinstance(row, Mapping):
            raise LineageHalt("PRODUCTION_FREEZE_ROW_MISSING")
        projection_id = str(row.get("projectionId") or "")
        offer = current_offers.get(projection_id) if projection_id else None
        if not isinstance(offer, Mapping):
            raise LineageHalt("OFFER_REVALIDATION_UNAVAILABLE")
        if offer.get("productionSelectionPermitted") is not True:
            raise LineageHalt("PRODUCTION_FREEZE_OFFER_NOT_AUTHORIZED")
        if (str(row.get("league") or "").upper() != "CFB"
            or str(row.get("eventId") or "") != str(offer.get("eventId") or "")
            or str(row.get("playerId") or "") != str(offer.get("subjectId") or "")
            or canonicalize_cfb_market(str(row.get("market") or "")) !=
                str(offer.get("proposition") or "").lower()):
            raise LineageHalt("PRODUCTION_FREEZE_CAPTURE_ROW_MISMATCH")
        try:
            if (not isfinite(float(row["line"])) or
                float(row["line"]) != float(offer["line"])):
                raise LineageHalt("PRODUCTION_FREEZE_LINE_CHANGED")
        except (KeyError, ValueError, TypeError) as exc:
            raise LineageHalt("PRODUCTION_FREEZE_LINE_MISSING") from exc
        side = str(candidate.get("selectedSide") or "").upper()
        side = {"MORE": "HIGHER", "LESS": "LOWER"}.get(side, side)
        if side not in {"HIGHER", "LOWER"} or side != str(offer.get("direction") or ""):
            raise LineageHalt("PRODUCTION_FREEZE_DIRECTION_MISMATCH")
        if row.get("status") not in {"pre_game", "PRE_GAME", "pregame", "PREGAME"}:
            raise LineageHalt("PRODUCTION_FREEZE_EVENT_NOT_PREGAME")
        for key in ("propId", "marketDefinitionId", "settlementRuleHash", "periodLabel", "modifier"):
            verified = str(offer.get(key) or "")
            if not verified:
                raise LineageHalt("PRODUCTION_FREEZE_CAPTURE_FIELD_MISSING")
            existing = str(row.get(key) or "")
            if existing and existing.upper() != verified.upper():
                raise LineageHalt("PRODUCTION_FREEZE_CANONICAL_CONFLICT")
        parameter_hash = str(candidate.get("parameterSnapshotHash") or "")
        if parameter_hash not in known_parameters:
            raise LineageHalt("PRODUCTION_FREEZE_PARAMETER_NOT_IN_RUN")
        snapshot = candidate.get("parameterSnapshot")
        if not isinstance(snapshot, Mapping) or snapshot.get("parameter_snapshot_hash") != parameter_hash:
            raise LineageHalt("PRODUCTION_FREEZE_PARAMETER_SNAPSHOT_UNBOUND")
        evidence = candidate.get("evidenceHashes")
        if not isinstance(evidence, (tuple, list)) or not evidence:
            raise LineageHalt("PRODUCTION_FREEZE_EVIDENCE_REQUIRED")
        if sorted(evidence) != sorted(snapshot.get("evidence_hashes") or []):
            raise LineageHalt("PRODUCTION_FREEZE_EVIDENCE_SNAPSHOT_CONFLICT")
        try:
            calibrated = float(candidate["calibratedP"])
        except (KeyError, ValueError, TypeError) as exc:
            raise LineageHalt("PRODUCTION_FREEZE_CALIBRATION_REQUIRED") from exc
        if not isfinite(calibrated) or not 0 <= calibrated <= 1:
            raise LineageHalt("PRODUCTION_FREEZE_CALIBRATION_INVALID")
        bound_row = dict(row)
        for key in ("propId", "marketDefinitionId", "settlementRuleHash", "periodLabel", "modifier"):
            bound_row[key] = offer[key]
        # Capture-authorized observed side, never inferred availability.
        observed_key = "offeredHigher" if side == "HIGHER" else "offeredLower"
        if row.get(observed_key) is False:
            raise LineageHalt("PRODUCTION_FREEZE_SIDE_NOT_OFFERED")
        bound_row[observed_key] = True
        bound = dict(candidate)
        bound["row"] = bound_row
        bound["selectedSide"] = side
        bound["featureStoreHash"] = feature_store_hash
        bound["evidenceGraphHash"] = evidence_graph_hash
        prepared.append(bound)
    return prepared


def freeze_supported_cfb_card(
    *,
    dest: Path,
    run_id: str,
    frozen_at_utc: str,
    board_hash: str,
    prompt_hash: str,
    model_snapshot_id: str,
    card: Sequence[Mapping[str, Any]],
    current_offers: Mapping[str, Mapping[str, Any]],
    root_accepted: bool,
) -> dict[str, Any]:
    """Persist an actual P0 freeze only when every current CFB dependency passes."""
    if not root_accepted:
        raise LineageHalt("PRODUCTION_ROOT_NOT_ACCEPTED")
    if not run_id or not model_snapshot_id:
        raise LineageHalt("PRODUCTION_FREEZE_MODEL_ID_REQUIRED")
    _hash(board_hash, "PRODUCTION_FREEZE_BOARD_HASH_REQUIRED")
    _hash(prompt_hash, "PRODUCTION_FREEZE_PROMPT_HASH_REQUIRED")
    decision_time = _utc(frozen_at_utc)
    if not card or len(card) > 6:
        raise LineageHalt("PRODUCTION_FREEZE_CARD_SIZE_INVALID")
    if not isinstance(current_offers, Mapping):
        raise LineageHalt("PRODUCTION_FREEZE_OFFERS_UNAVAILABLE")
    validated: list[tuple[dict[str, Any], FreezeMember]] = []
    seen: set[str] = set()
    for selected in card:
        row = selected.get("row")
        if not isinstance(row, Mapping):
            raise LineageHalt("PRODUCTION_FREEZE_ROW_MISSING")
        if str(row.get("league") or "").upper() != "CFB":
            raise LineageHalt("PRODUCTION_FREEZE_SPORT_UNSUPPORTED")
        market = canonicalize_cfb_market(str(row.get("market") or ""))
        if market is None or contract_for(market) is None:
            raise LineageHalt("PRODUCTION_FREEZE_MARKET_UNSUPPORTED")
        projection_id = str(row.get("projectionId") or "")
        if not projection_id or projection_id in seen:
            raise LineageHalt("PRODUCTION_FREEZE_PROJECTION_ID_INVALID")
        seen.add(projection_id)
        offer = current_offers.get(projection_id)
        if not isinstance(offer, Mapping):
            raise LineageHalt("OFFER_REVALIDATION_UNAVAILABLE")
        if offer.get("state") != "VALID" or offer.get("offerBacking") != "CURRENT_OFFER_REVALIDATED":
            raise LineageHalt("PRODUCTION_FREEZE_OFFER_NOT_VERIFIED")
        if offer.get("productionSelectionPermitted") is not True:
            raise LineageHalt("PRODUCTION_FREEZE_OFFER_NOT_AUTHORIZED")
        prop_id = str(row.get("propId") or "")
        market_id = str(row.get("marketDefinitionId") or "")
        if not prop_id or not market_id or prop_id != str(offer.get("propId") or "") or market_id != str(offer.get("marketDefinitionId") or ""):
            raise LineageHalt("PRODUCTION_FREEZE_CANONICAL_IDENTITY_REQUIRED")
        if str(row.get("eventId") or "") != str(offer.get("eventId") or "") or str(row.get("playerId") or "") != str(offer.get("subjectId") or ""):
            raise LineageHalt("PRODUCTION_FREEZE_EVENT_SUBJECT_MISMATCH")
        if str(offer.get("proposition") or "").lower() != market:
            raise LineageHalt("PRODUCTION_FREEZE_MARKET_MISMATCH")
        period = str(row.get("periodLabel") or row.get("boardId") or "").upper()
        if not period or period != str(offer.get("periodLabel") or "").upper():
            raise LineageHalt("PRODUCTION_FREEZE_PERIOD_MISMATCH")
        modifier = str(row.get("modifier") or "STANDARD").upper()
        if modifier != str(offer.get("modifier") or "").upper():
            raise LineageHalt("PRODUCTION_FREEZE_MODIFIER_MISMATCH")
        direction = str(selected.get("selectedSide") or "").upper()
        if direction not in {"HIGHER", "LOWER"} or direction != str(offer.get("direction") or "").upper():
            raise LineageHalt("PRODUCTION_FREEZE_DIRECTION_MISMATCH")
        if row.get("offeredHigher") is not True and direction == "HIGHER":
            raise LineageHalt("PRODUCTION_FREEZE_SIDE_NOT_OFFERED")
        if row.get("offeredLower") is not True and direction == "LOWER":
            raise LineageHalt("PRODUCTION_FREEZE_SIDE_NOT_OFFERED")
        try:
            line = float(row["line"])
            current_line = float(offer["line"])
        except (ValueError, TypeError, KeyError) as exc:
            raise LineageHalt("PRODUCTION_FREEZE_LINE_MISSING") from exc
        if not isfinite(line) or not isfinite(current_line) or abs(line - current_line) > 1e-12:
            raise LineageHalt("PRODUCTION_FREEZE_LINE_CHANGED")
        if str(row.get("settlementRuleHash") or "") != str(offer.get("settlementRuleHash") or "") or not offer.get("settlementRuleHash"):
            raise LineageHalt("PRODUCTION_FREEZE_SETTLEMENT_RULE_MISSING")
        if str(row.get("status") or "").upper() not in {"PRE_GAME", "PREGAME"} or str(offer.get("eventStatus") or "").upper() not in {"PRE_GAME", "PREGAME"}:
            raise LineageHalt("PRODUCTION_FREEZE_EVENT_NOT_PREGAME")
        if not offer.get("scheduledTime") or _utc(offer["scheduledTime"]) <= decision_time:
            raise LineageHalt("PRODUCTION_FREEZE_EVENT_STARTED")
        if _utc(offer.get("retrievedAt")) > decision_time or _utc(offer.get("validUntilUtc")) < decision_time:
            raise LineageHalt("OFFER_REVALIDATION_STALE")
        _hash(offer.get("sourceHash"), "PRODUCTION_FREEZE_OFFER_SOURCE_HASH_REQUIRED")
        snapshot_id = str(offer.get("lineSnapshotId") or "")
        if not snapshot_id or snapshot_id != line_snapshot_id(offer):
            raise LineageHalt("PRODUCTION_FREEZE_LINE_SNAPSHOT_ID_MISMATCH")
        parameter_hash = _hash(selected.get("parameterSnapshotHash"), "PRODUCTION_FREEZE_MODEL_HASH_REQUIRED")
        evidence_hashes = selected.get("evidenceHashes")
        if not isinstance(evidence_hashes, (tuple, list)) or not evidence_hashes:
            raise LineageHalt("PRODUCTION_FREEZE_EVIDENCE_REQUIRED")
        for evidence_hash in evidence_hashes:
            _hash(evidence_hash, "PRODUCTION_FREEZE_EVIDENCE_HASH_INVALID")
        try:
            probability = float(selected["evidenceSafeP"])
        except (ValueError, TypeError, KeyError) as exc:
            raise LineageHalt("PRODUCTION_FREEZE_PROBABILITY_REQUIRED") from exc
        if not isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise LineageHalt("PRODUCTION_FREEZE_PROBABILITY_INVALID")
        if (selected.get("grade") != "PLAYABLE" or selected.get("blocker")
            or selected.get("productionSelectable") is not True
            or selected.get("survivorStateAccepted") is not True):
            raise LineageHalt("PRODUCTION_FREEZE_CANDIDATE_NOT_CERTIFIED")
        recommendation_id = "REC:" + content_hash({
            "runId": run_id, "propId": prop_id, "lineSnapshotId": snapshot_id,
            "marketDefinitionId": market_id, "side": direction,
            "parameterSnapshotHash": parameter_hash,
            "evidenceHashes": sorted(evidence_hashes),
        })
        member = FreezeMember(
            recommendation_id=recommendation_id, prop_id=prop_id,
            line_snapshot_id=snapshot_id, market_definition_id=market_id,
            evidence_hash=content_hash(sorted(evidence_hashes)),
            parameter_snapshot_hash=parameter_hash,
        )
        validated.append((dict(offer), member))
    store = LineageStore(Path(dest) / "lineage.sqlite3")
    try:
        for offer, member in validated:
            sid = store.append_line_snapshot(offer)
            if sid != member.line_snapshot_id:
                raise LineageHalt("PRODUCTION_FREEZE_LINE_SNAPSHOT_DRIFT")
        freeze_id = store.freeze(
            run_id=run_id, frozen_at_utc=frozen_at_utc,
            model_snapshot_id=model_snapshot_id,
            prompt_hash=prompt_hash, board_hash=board_hash,
            members=[member for _, member in validated],
        )
    finally:
        store.close()
    return {
        "schema": "dcm.production_lineage_freeze_receipt.v1",
        "state": "FROZEN", "freezeId": freeze_id,
        "memberCount": len(validated), "runId": run_id,
        "modelSnapshotId": model_snapshot_id,
        "productionLineageFrozen": True, "predictiveClaim": "NONE",
    }
