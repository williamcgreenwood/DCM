"""Insights consumer stages: research Top-100 through production freeze.

The initial Insights queue is useful before a model exists.  This module keeps
that research frontier separate from a production frontier and connects the
latter to the existing DCM ranking and portfolio constraints.  No probability
is derived from an Insights hit rate.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from dcm.chat.state import read_json, write_json
from dcm.contracts.hashes import content_hash
from dcm.model.ranking import rank_candidates
from dcm.research.insight_bridge import insights_offer_snapshots
from dcm.research.offer_revalidation import UNAVAILABLE, load_current_offers
from dcm.selection.portfolio import build_card


TOP100_SCHEMA = "pillars_dcm.production_top100.v1"
SELECTION_SCHEMA = "pillars_dcm.insights_selection_state.v1"
EVENT_WORLD_SCHEMA = "pillars_dcm.insights_event_worlds.v1"


def _text(value: Any, limit: int = 256) -> str:
    return str(value or "").strip()[:limit]


def _number(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value != value or abs(value) == float("inf"):
        return None
    return value


def _request_ids(row: Mapping[str, Any], requests: Iterable[Mapping[str, Any]]) -> list[str]:
    claim_id = _text(row.get("claimId"), 512)
    event_id = _text(row.get("eventId"), 256)
    subject_id = _text(row.get("subjectId") or row.get("playerId"), 256)
    matched: list[str] = []
    for request in requests:
        request_id = _text(request.get("request_id") or request.get("requestId"), 256)
        claim_ids = {_text(value, 512) for value in (request.get("dependent_claim_ids") or request.get("insightClaimIds") or []) if _text(value, 512)}
        if claim_id and claim_id in claim_ids:
            matched.append(request_id)
            continue
        if event_id and _text(request.get("eventId"), 256) != event_id:
            continue
        scope = _text(request.get("scope"), 64).upper()
        scope_id = _text(request.get("scope_id") or request.get("scopeId"), 256)
        if scope == "EVENT" and scope_id == event_id:
            matched.append(request_id)
        elif scope in {"SUBJECT", "PLAYER"} and scope_id == subject_id:
            matched.append(request_id)
    return sorted({value for value in matched if value})


def _coverage_map(coverage: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("requestId") or row.get("request_id"), 256): dict(row)
        for row in ((coverage or {}).get("requests") or [])
        if isinstance(row, Mapping) and _text(row.get("requestId") or row.get("request_id"), 256)
    }


def build_top100_artifact(
    queue: Mapping[str, Any] | None,
    *,
    requests: Iterable[Mapping[str, Any]] = (),
    coverage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn the deterministic research queue into an auditable Top-100 stage."""
    queue = queue if isinstance(queue, Mapping) else {}
    request_rows = [row for row in requests if isinstance(row, Mapping)]
    coverage_by_id = _coverage_map(coverage)
    source_rows = [row for row in (queue.get("top100") or []) if isinstance(row, Mapping)]
    rows: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    for index, raw in enumerate(source_rows[:100], 1):
        row = dict(raw)
        req_ids = _request_ids(row, request_rows)
        req_cov = [coverage_by_id.get(request_id) or {} for request_id in req_ids]
        complete = bool(req_cov) and all(bool(item.get("complete")) for item in req_cov)
        if complete:
            state = "COMPLETE"
        elif req_cov:
            state = "INCOMPLETE"
            blocker_counts["EVIDENCE_COVERAGE_INCOMPLETE"] += 1
        else:
            state = "BLOCKED_NO_RESEARCH_REQUEST"
            blocker_counts["EVIDENCE_REQUEST_MISSING"] += 1
        for blocker in row.get("blockers") or []:
            blocker_counts[_text(blocker, 128)] += 1
        row.update({
            "top100Rank": index,
            "stage": "TOP100_RESEARCH_PRIORITY",
            "researchRequirementIds": req_ids,
            "researchStatus": state,
            "coverageComplete": complete,
            "researchPriorityScore": _number(row.get("attentionScore")),
            "researchPriorityScoreType": "NOT_A_PROBABILITY",
            "productionEligible": False,
            "probability": None,
            "selectionState": "AWAITING_RESEARCH" if state != "COMPLETE" else "AWAITING_MODEL",
        })
        rows.append(row)
    complete_count = sum(row.get("researchStatus") == "COMPLETE" for row in rows)
    payload = {
        "schema": TOP100_SCHEMA,
        "stage": "TOP100",
        "status": "READY_FOR_MODEL" if complete_count else "RESEARCH_IN_PROGRESS",
        "researchOnly": True,
        "productionEligible": False,
        "researchCompleteCount": int(complete_count),
        "candidateCount": len(rows),
        "requestedCount": int((coverage or {}).get("requested") or len(request_rows)),
        "rows": rows,
        "productionTop100": [],
        "productionTop100Count": 0,
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "selectionGate": "NOT_EVALUATED_UNTIL_MODEL_AND_CURRENT_OFFER",
        "boardHarRequired": False,
        "note": (
            "Top 100 is the deterministic research frontier. It is not a list "
            "of probabilities and does not convert reported Insights hit rate "
            "into a forecast. Production Top 100 is populated only by the "
            "downstream model/current-offer consumer."
        ),
    }
    payload["contentHash"] = content_hash(payload)
    return payload


def build_event_worlds(
    claims: Iterable[Mapping[str, Any]],
    *,
    coverage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a safe shared event context index for Insights descendants."""
    worlds: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        identity = claim.get("harIdentity") if isinstance(claim.get("harIdentity"), Mapping) else {}
        event = identity.get("event") if isinstance(identity.get("event"), Mapping) else {}
        nested_event = claim.get("event") if isinstance(claim.get("event"), Mapping) else {}
        home = event.get("home") if isinstance(event.get("home"), Mapping) else {}
        away = event.get("away") if isinstance(event.get("away"), Mapping) else {}
        event_id = _text(event.get("id") or nested_event.get("eventId") or claim.get("eventId"), 256)
        if not event_id:
            continue
        world = worlds.setdefault(event_id, {
            "eventId": event_id,
            "league": _text(claim.get("leagueId"), 64).upper() or None,
            "scheduledStart": _text(event.get("scheduledTime") or nested_event.get("scheduledTime") or claim.get("scheduledTime"), 64) or None,
            "eventStatus": _text(event.get("status") or nested_event.get("status") or claim.get("eventStatus"), 64) or None,
            "homeTeamId": _text(home.get("id"), 256) or None,
            "awayTeamId": _text(away.get("id"), 256) or None,
            "claimIds": [],
            "sourceHarSha256s": [],
            "evidenceComplete": False,
            "featureState": "CAPTURE_CONTEXT_ONLY",
            "conservationState": "NOT_EVALUATED",
            "researchOnly": True,
        })
        claim_id = _text(claim.get("claimId"), 512)
        if claim_id and claim_id not in world["claimIds"]:
            world["claimIds"].append(claim_id)
        source_hash = _text(claim.get("sourceHarSha256"), 128)
        if source_hash and source_hash not in world["sourceHarSha256s"]:
            world["sourceHarSha256s"].append(source_hash)
    complete = bool((coverage or {}).get("complete"))
    for world in worlds.values():
        world["evidenceComplete"] = complete
        world["featureState"] = "READY_FOR_FEATURES" if complete else "AWAITING_TYPED_EVIDENCE"
        world["claimIds"].sort()
        world["sourceHarSha256s"].sort()
    payload = {
        "schema": EVENT_WORLD_SCHEMA,
        "worldCount": len(worlds),
        "worlds": sorted(worlds.values(), key=lambda row: str(row.get("eventId") or "")),
        "sharedContextLaw": "One event world is reused by every dependent Insights candidate; no independent prop simulation is performed here.",
        "researchOnly": True,
        "productionSelectionPermitted": False,
    }
    payload["contentHash"] = content_hash(payload)
    return payload


def _prediction_rows(model_result: Mapping[str, Any] | None, dest: Path | None) -> dict[str, dict[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    if isinstance(model_result, Mapping):
        for key in ("predictions", "candidatePredictions", "rows"):
            value = model_result.get(key)
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, Mapping))
    if dest is not None:
        external = read_json(Path(dest) / "model_predictions.json") or {}
        if isinstance(external, Mapping) and isinstance(external.get("rows"), list):
            rows.extend(row for row in external["rows"] if isinstance(row, Mapping))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        nested = row.get("row") if isinstance(row.get("row"), Mapping) else {}
        key = _text(row.get("claimId") or row.get("projectionId") or nested.get("projectionId"), 512)
        if key:
            out[key] = dict(row)
    return out


def _model_is_promoted(model: Mapping[str, Any]) -> bool:
    status = _text(model.get("status"), 64).upper()
    registry = _text(model.get("registryState") or model.get("modelState"), 64).upper()
    return bool(
        model.get("predictiveCertified")
        and model.get("productionRootCertified")
        and status in {"CERTIFIED", "PRODUCTION_CERTIFIED", "PROMOTED"}
        and registry not in {"", "SHADOW", "UNTRAINED", "RESEARCH_PROTOTYPE", "QUARANTINED"}
    )


def _future(snapshot: Mapping[str, Any]) -> bool:
    status = _text(snapshot.get("eventStatus") or snapshot.get("status"), 64).upper().replace(" ", "_")
    if status in {"FINAL", "FINALIZED", "CLOSED", "SETTLED", "LIVE", "IN_PROGRESS", "SUSPENDED"}:
        return False
    start = _text(snapshot.get("scheduledTime") or snapshot.get("eventStartTime"), 64)
    if not start:
        return True
    try:
        parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        return True
    parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc) > datetime.now(timezone.utc)


def _candidate_row(snapshot: Mapping[str, Any], prediction: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(snapshot)
    row["projectionId"] = _text(snapshot.get("projectionId") or snapshot.get("claimId"), 512)
    row["market"] = _text(snapshot.get("market") or snapshot.get("proposition"), 128).lower()
    row["modifier"] = _text(snapshot.get("modifier") or "STANDARD", 64).upper()
    row["direction"] = _text(snapshot.get("direction") or snapshot.get("side"), 32).upper()
    row["playerId"] = _text(snapshot.get("playerId") or snapshot.get("subjectId"), 256)
    row["eventId"] = _text(snapshot.get("eventId"), 256)
    row["teamId"] = _text(snapshot.get("teamId"), 256)
    row.update({key: value for key, value in prediction.items() if key not in {"row", "claimId", "projectionId"}})
    return row


def evaluate_insight_selection(
    *,
    dest: Path | None,
    claims: Iterable[Mapping[str, Any]],
    queue: Mapping[str, Any] | None,
    coverage: Mapping[str, Any] | None,
    model_result: Mapping[str, Any] | None,
    board_offer_count: int = 0,
) -> dict[str, Any]:
    """Consume Insights snapshots through ranking, gates, constraints, freeze."""
    dest = Path(dest) if dest is not None else None
    claim_rows = [dict(row) for row in claims if isinstance(row, Mapping)]
    snapshot_doc = insights_offer_snapshots(claim_rows)
    snapshots = [dict(row) for row in (snapshot_doc.get("snapshots") or []) if isinstance(row, Mapping)]
    # The research queue is the funnel boundary.  Do not silently model all
    # thousands of captured claims after the Top-100 has been selected.
    queue = queue if isinstance(queue, Mapping) else {}
    frontier_rows = [row for row in (queue.get("top100") or []) if isinstance(row, Mapping)]
    frontier_ids = {_text(row.get("claimId"), 512) for row in frontier_rows if _text(row.get("claimId"), 512)}
    if frontier_ids:
        snapshots = [row for row in snapshots if _text(row.get("claimId"), 512) in frontier_ids]
    current_offers = load_current_offers(dest) if dest is not None else {}
    requests = read_json(dest / "research_requests.json") if dest is not None else []
    request_rows = [row for row in (requests or []) if isinstance(row, Mapping)]
    coverage_by_id = _coverage_map(coverage)
    model = dict(model_result) if isinstance(model_result, Mapping) else {}
    predictions = _prediction_rows(model, dest)
    root_certified = bool(model.get("productionRootCertified"))
    promoted = _model_is_promoted({**model, "productionRootCertified": root_certified})
    ranked_inputs: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    for snapshot in snapshots:
        claim_id = _text(snapshot.get("claimId") or snapshot.get("projectionId"), 512)
        prediction = predictions.get(claim_id) or {}
        req_ids = _request_ids(snapshot, request_rows)
        req_cov = [coverage_by_id.get(request_id) or {} for request_id in req_ids]
        blockers: list[str] = []
        offer = current_offers.get(claim_id)
        if not offer:
            blockers.append(UNAVAILABLE)
        elif offer.get("state") != "VALID":
            blockers.append("OFFER_REVALIDATION_INVALID")
        if not req_cov or not all(bool(row.get("complete")) for row in req_cov):
            blockers.append("EVIDENCE_COVERAGE_INCOMPLETE")
        # Revalidation can carry a fresher status/time than the original
        # Insights capture.  Evaluate the merged view so a post-capture live or
        # final event cannot enter production merely because the old snapshot
        # still said pre_game.
        future_view = {**snapshot, **(offer or {})}
        if not _future(future_view):
            blockers.append("EVENT_NOT_FUTURE")
        if not prediction:
            blockers.append("MODEL_PROBABILITY_UNAVAILABLE")
        if not promoted:
            blockers.append("MODEL_NOT_CERTIFIED")
        if _text(model.get("predictiveClaim") or "NONE", 64).upper() == "NONE":
            blockers.append("PREDICTIVE_CLAIM_NONE")
        if not root_certified:
            blockers.append("PRODUCTION_ROOT_NOT_CERTIFIED")
        if offer and not offer.get("marketDefinitionId"):
            blockers.append("UNSUPPORTED_MARKET_DEFINITION")
        if offer and not offer.get("settlementRuleHash"):
            blockers.append("SETTLEMENT_RULE_UNKNOWN")

        candidate: dict[str, Any] = {
            "row": _candidate_row(snapshot, prediction),
            "claimId": claim_id,
            "offerRevalidation": dict(offer) if offer else None,
            "researchRequirementIds": req_ids,
            "researchCoverageComplete": bool(req_cov) and all(bool(row.get("complete")) for row in req_cov),
            "blockers": sorted(set(blockers)),
            "productionEligible": False,
            "predictiveClaim": _text(model.get("predictiveClaim") or "NONE", 64),
            "modelState": _text(model.get("registryState") or model.get("status") or "UNTRAINED", 64),
        }
        for blocker in candidate["blockers"]:
            blocker_counts[blocker] += 1
        p = _number(
            prediction.get("evidenceSafeP")
            or prediction.get("calibratedP")
            or prediction.get("selectedP")
            or prediction.get("rawP")
        )
        if p is not None:
            candidate.update({
                "evidenceSafeP": p,
                "calibratedP": _number(prediction.get("calibratedP")),
                "rawP": _number(prediction.get("rawP") or prediction.get("selectedP")),
                "lowerBound": _number(prediction.get("lowerBound") or prediction.get("lowerBoundP")) or 0.0,
                "reliability": _number(prediction.get("reliability")) or 0.0,
                "dataQuality": _number(prediction.get("dataQuality")) or 0.0,
                "fragility": _number(prediction.get("fragility")) or 1.0,
                "oodRisk": _number(prediction.get("oodRisk")) or 1.0,
                "falseSignRisk": _number(prediction.get("falseSignRisk")) or 0.5,
                "epistemicUncertainty": _number(prediction.get("epistemicUncertainty")) or 0.5,
                "volatility": _number(prediction.get("volatility")) or 0.5,
                "grade": "PLAYABLE",
                "state": "MODELED",
                "parameterSnapshot": dict(prediction.get("parameterSnapshot") or {}),
            })
            candidate["parameterSnapshot"].setdefault("status", "ACTIVE")
            candidate["forecastCutoff"] = prediction.get("forecastCutoff")
            # Only candidates that have already passed every gate can enter
            # the production ranking. Blocked model rows remain diagnostics.
            if not candidate["blockers"]:
                ranked_inputs.append(candidate)
        diagnostics.append(candidate)

    ranked: list[dict[str, Any]] = []
    if ranked_inputs:
        ranked = rank_candidates(
            ranked_inputs,
            top_k=100,
            seed=content_hash([row.get("claimId") for row in ranked_inputs])[:32],
        )
    production_top100 = ranked[:100]
    # Reuse the canonical portfolio constraint implementation for the Top-25
    # frontier with a larger cap; the six-leg card is applied below.
    production_top25 = build_card(production_top100, max_size=25) if production_top100 else []
    playables = build_card(production_top25, max_size=6) if production_top25 else []
    for index, row in enumerate(production_top25, 1):
        row["productionEligible"] = True
        row["selectionState"] = "FROZEN_TOP25"
        row["top25Rank"] = index
    for row in playables:
        row["selectionState"] = "PLAYABLE"

    if playables:
        playables_doc = {
            "name": "PLAYABLES",
            "status": "SELECTED",
            "count": len(playables),
            "rows": playables,
            "productionSelectionPermitted": True,
            "reason": None,
            "boardHarRequired": False,
        }
    else:
        reason = UNAVAILABLE if not current_offers else (
            sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if blocker_counts else "NO_QUALIFIED_CANDIDATES"
        )
        playables_doc = {
            "name": "PLAYABLES",
            "status": "ABSTAINED_GATES_NOT_MET",
            "count": 0,
            "rows": [],
            "productionSelectionPermitted": False,
            "reason": reason,
            "boardHarRequired": False,
        }

    freeze_doc: dict[str, Any] = {
        "schema": "pillars_dcm.insights_frozen_predictions.v1",
        "status": "NOT_EARNED",
        "freezeId": None,
        "rows": [],
        "productionTop25Count": len(production_top25),
        "reason": playables_doc.get("reason") or "NO_PLAYABLES",
        "boardHarRequired": False,
    }
    if production_top25 and playables:
        frozen_rows = [
            {
                "projectionId": (row.get("row") or {}).get("projectionId"),
                "claimId": row.get("claimId"),
                "line": (row.get("row") or {}).get("line"),
                "direction": (row.get("row") or {}).get("direction"),
                "evidenceSafeP": row.get("evidenceSafeP"),
                "calibratedP": row.get("calibratedP"),
                "selectionScore": row.get("selectionScore"),
                "rank": row.get("rank"),
            }
            for row in production_top25
        ]
        freeze_hash = content_hash(frozen_rows)
        freeze_doc.update({
            "status": "FROZEN",
            "freezeId": "INSIGHT_FREEZE:" + freeze_hash,
            "rows": frozen_rows,
            "frozenPredictionHash": freeze_hash,
            "reason": None,
        })

    top100 = build_top100_artifact(queue, requests=request_rows, coverage=coverage)
    top100.update({
        "status": "READY_FOR_TOP25_GATES" if production_top100 else top100.get("status"),
        "researchOnly": not bool(production_top100),
        "productionEligible": bool(production_top100),
        "productionTop100": production_top100,
        "productionTop100Count": len(production_top100),
        "selectionGate": "TOP25_AND_FREEZE_EVALUATED" if production_top100 else top100.get("selectionGate"),
        "blockerCounts": dict(sorted(blocker_counts.items())),
    })
    top100["contentHash"] = content_hash({key: value for key, value in top100.items() if key != "contentHash"})

    selection = {
        "schema": SELECTION_SCHEMA,
        "status": "SELECTED" if production_top25 else "ABSTAINED",
        "modelPathAttempted": bool(model.get("modelPathAttempted")) or bool(predictions),
        "candidateCount": len(diagnostics),
        "rankedCount": len(ranked),
        "productionTop100Count": len(production_top100),
        "productionTop25Count": len(production_top25),
        "playableCount": len(playables),
        "productionSelectionPermitted": bool(production_top25),
        "candidateDiagnostics": diagnostics,
        "ranked": ranked,
        "productionTop100": production_top100,
        "productionTop25": production_top25,
        "playables": playables_doc,
        "freeze": freeze_doc,
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "boardOfferCount": int(board_offer_count),
        "insightsOfferCount": len(snapshots),
        "currentOfferRevalidationCount": len(current_offers),
        "noBoardHarAsk": True,
    }
    selection["contentHash"] = content_hash(selection)
    return {
        "top100": top100,
        "eventWorld": build_event_worlds(claim_rows, coverage=coverage),
        "selection": selection,
        "freeze": freeze_doc,
    }


def refresh_insight_pipeline_files(
    dest: Path,
    *,
    claims: Iterable[Mapping[str, Any]],
    queue: Mapping[str, Any] | None,
    coverage: Mapping[str, Any] | None,
    model_result: Mapping[str, Any] | None,
    board_offer_count: int = 0,
) -> dict[str, Any]:
    """Persist the inner consumer artifacts and return the full state."""
    dest = Path(dest)
    claim_rows = [dict(row) for row in claims if isinstance(row, Mapping)]
    # Materialize the no-offer state on the first run as a typed, durable
    # blocker.  This prevents downstream consumers from interpreting a missing
    # file as a missing HAR and gives ChatGPT a stable place to append
    # revalidation observations later.
    current_offer_path = dest / "current_offer_snapshots.json"
    if not current_offer_path.is_file():
        from dcm.research.offer_revalidation import import_offer_revalidations

        board = read_json(dest / "board.json") or {}
        state = read_json(dest / "host_state.json") or {}
        cutoff = str(
            (state.get("forecastCutoff") if isinstance(state, Mapping) else "")
            or (board.get("forecastCutoff") if isinstance(board, Mapping) else "")
            or ""
        ) or None
        import_offer_revalidations(
            dest,
            [],
            snapshots=insights_offer_snapshots(claim_rows).get("snapshots") or [],
            cutoff=cutoff,
        )
    state = evaluate_insight_selection(
        dest=dest,
        claims=claim_rows,
        queue=queue,
        coverage=coverage,
        model_result=model_result,
        board_offer_count=board_offer_count,
    )
    write_json(dest / "insight_event_worlds.json", state["eventWorld"])
    write_json(dest / "production_top100.json", state["top100"])
    write_json(dest / "insight_selection.json", state["selection"])
    write_json(dest / "insights_frozen_predictions.json", state["freeze"])
    return state


__all__ = [
    "EVENT_WORLD_SCHEMA",
    "SELECTION_SCHEMA",
    "TOP100_SCHEMA",
    "build_event_worlds",
    "build_top100_artifact",
    "evaluate_insight_selection",
    "refresh_insight_pipeline_files",
]
