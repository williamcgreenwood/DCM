"""Helpers for source-aware host observation execution.

Internal helpers extracted so MCP push_files can ship full content under size limits.
Public API remains ``dcm.research.observation_execute``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dcm.chat.state import read_json
from dcm.contracts.hashes import content_hash
from dcm.model.grade import grade as grade_of
from dcm.model.parameters import build_parameter_snapshot
from dcm.model.uncertainty import probability_bundle
from dcm.research.indexes import BoardIndexes
from dcm.research.material_facts import facts_to_features, resolve_material_facts
from dcm.research.scopes import canonical_scope
from dcm.runtime.dag import Dag

_SCOPE_KIND_BLOCKLIST = {
    "EVENT",
    "SUBJECT",
    "AFFILIATION",
    "COUNTERPARTY",
    "PLAYER",
    "TEAM",
    "ENVIRONMENT",
    "COMPETITION",
    "SPORT",
    "OFFER",
    "MARKET",
    "MARKET_DEFINITION",
}


def _build_counterparty_index(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """One-shot opponent → offer ids map (BoardIndexes has no by_counterparty)."""
    out: dict[str, list[str]] = {}
    for row in rows:
        oid = str(row.get("projectionId") or "")
        if not oid:
            continue
        cp = str(row.get("opponentId") or row.get("opponent") or "")
        if cp:
            out.setdefault(cp, []).append(oid)
    return out


def _derive_sport(
    board: dict[str, Any],
    host_state: dict[str, Any],
    rows: list[dict[str, Any]],
) -> str:
    """Sport / league family for ResearchStore — never a semantic_scope kind."""
    for src in (board, host_state):
        if not isinstance(src, dict):
            continue
        for key in ("sport", "league", "sportFamily"):
            val = str(src.get(key) or "").strip()
            if val and canonical_scope(val) not in _SCOPE_KIND_BLOCKLIST and val.upper() not in _SCOPE_KIND_BLOCKLIST:
                return val
    for row in rows:
        league = str(row.get("league") or "").strip()
        if league and league.upper() not in _SCOPE_KIND_BLOCKLIST:
            return league
        family = str(row.get("sportFamily") or "").strip()
        if family and family.upper() not in _SCOPE_KIND_BLOCKLIST:
            return family
    return "CFB"


def _affected_rows(
    *,
    indexes: BoardIndexes,
    by_counterparty: dict[str, list[str]],
    action: dict[str, Any] | None,
    claim: dict[str, Any],
) -> list[dict[str, Any]]:
    """Resolve dependent offers via BoardIndexes — no O(N) board scans."""
    offer_ids = [str(x) for x in ((action or {}).get("offerIds") or []) if x]
    hit: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(oid: str) -> None:
        if not oid or oid in seen:
            return
        row = indexes.exact_offer(oid, downstream_used=True)
        if row is not None:
            seen.add(oid)
            hit.append(row)

    if offer_ids:
        for oid in offer_ids:
            _add(oid)
        return hit

    scope = canonical_scope(str(claim.get("semantic_scope") or ""))
    scope_id = str(claim.get("scope_id") or "")
    if not scope_id:
        return hit
    if scope == "EVENT":
        for oid in indexes.by_event.get(scope_id) or ():
            _add(str(oid))
    elif scope == "AFFILIATION":
        for oid in indexes.by_affiliation.get(scope_id) or ():
            _add(str(oid))
    elif scope == "SUBJECT":
        for oid in indexes.by_subject.get(scope_id) or ():
            _add(str(oid))
    elif scope == "COUNTERPARTY":
        for oid in by_counterparty.get(scope_id) or ():
            _add(str(oid))
    return hit


def _snapshot_ablation(
    rows: list[dict[str, Any]],
    claims_before: list[dict[str, Any]],
    claims_after: list[dict[str, Any]],
) -> dict[str, Any]:
    before_hashes: dict[str, str] = {}
    after_hashes: dict[str, str] = {}
    changed: list[str] = []
    for row in rows:
        oid = str(row.get("projectionId") or "")
        if not oid:
            continue
        b = build_parameter_snapshot(row, claims_before)
        a = build_parameter_snapshot(row, claims_after)
        before_hashes[oid] = str(b.get("parameter_snapshot_hash") or "")
        after_hashes[oid] = str(a.get("parameter_snapshot_hash") or "")
        if before_hashes[oid] != after_hashes[oid]:
            changed.append(oid)
    return {
        "offerCount": len(before_hashes),
        "changedOfferCount": len(changed),
        "changedOfferIds": changed[:50],
        "parameterConsumerChanged": bool(changed),
        "beforeHashes": {k: before_hashes[k] for k in list(before_hashes)[:8]},
        "afterHashes": {k: after_hashes[k] for k in list(after_hashes)[:8]},
    }


def _consumer_ablation(
    rows: list[dict[str, Any]],
    claims_before: list[dict[str, Any]],
    claims_after: list[dict[str, Any]],
    *,
    cutoff: str,
) -> dict[str, Any]:
    """MaterialFact / feature + probability/grade helper hash changes.

    Proves a consumer beyond ParameterSnapshot. Full EventWorld wiring is out of
    scope for this repair; this path uses resolve_material_facts → facts_to_features
    and probability_bundle + grade on snapshot-derived support.
    """
    mf_before = resolve_material_facts(claims_before, cutoff=cutoff)
    mf_after = resolve_material_facts(claims_after, cutoff=cutoff)
    feat_before = facts_to_features(mf_before, cutoff=cutoff)
    feat_after = facts_to_features(mf_after, cutoff=cutoff)
    feature_hash_before = content_hash({"features": feat_before, "material": mf_before.get("contentHash")})
    feature_hash_after = content_hash({"features": feat_after, "material": mf_after.get("contentHash")})

    grade_before: dict[str, str] = {}
    grade_after: dict[str, str] = {}
    prob_before: dict[str, str] = {}
    prob_after: dict[str, str] = {}
    changed_grade: list[str] = []
    changed_prob: list[str] = []

    def _stub_consumer(row: dict[str, Any], claims: list[dict[str, Any]]) -> tuple[str, str, str]:
        snap = build_parameter_snapshot(row, claims)
        support = int(snap.get("minimum_model_support") or 0)
        if support <= 0:
            opp = snap.get("opportunity") if isinstance(snap.get("opportunity"), dict) else {}
            eff = snap.get("efficiency") if isinstance(snap.get("efficiency"), dict) else {}
            support = int(opp.get("support_n") or 0) + int(eff.get("support_n") or 0)
        data_quality = float(snap.get("data_quality") or 0.0)
        ood = float(snap.get("ood_risk") or 0.0)
        # Deterministic stub: scopes_used and evidence shift selected_p slightly.
        scopes = list(snap.get("scopes_used") or [])
        raw_p = 0.50 + 0.02 * min(5, len(scopes)) + 0.01 * min(5, len(snap.get("evidence_hashes") or []))
        raw_p = max(0.05, min(0.95, raw_p))
        bundle = probability_bundle(
            raw_selected_p=raw_p,
            n_worlds=max(8, support * 2 or 8),
            support_n=max(0, support),
            data_quality=max(0.05, data_quality) if data_quality else 0.35,
            ood_risk=ood,
            volatility=0.2,
            synthetic=bool(snap.get("synthetic")),
        )
        g = grade_of(
            selected_p=float(bundle["evidence_safe_probability"]),
            lower_bound=float(bundle["lower_bound"]),
            demon=False,
            fragility=0.2,
        )
        return (
            str(snap.get("parameter_snapshot_hash") or ""),
            content_hash(bundle),
            g,
        )

    for row in rows:
        oid = str(row.get("projectionId") or "")
        if not oid:
            continue
        _sb, pb, gb = _stub_consumer(row, claims_before)
        _sa, pa, ga = _stub_consumer(row, claims_after)
        prob_before[oid] = pb
        prob_after[oid] = pa
        grade_before[oid] = gb
        grade_after[oid] = ga
        if pb != pa:
            changed_prob.append(oid)
        if gb != ga:
            changed_grade.append(oid)

    return {
        "proven": [
            "ParameterSnapshot.hash",
            "MaterialFactResolution + facts_to_features contentHash",
            "probability_bundle + grade helper (snapshot-derived stub; not full EventWorld)",
        ],
        "notProven": [
            "full EventWorld set resimulation",
            "runner-grade shared-world probability path",
        ],
        "materialFactHashBefore": str(mf_before.get("contentHash") or ""),
        "materialFactHashAfter": str(mf_after.get("contentHash") or ""),
        "featureHashBefore": feature_hash_before,
        "featureHashAfter": feature_hash_after,
        "materialOrFeatureChanged": feature_hash_before != feature_hash_after
        or str(mf_before.get("contentHash") or "") != str(mf_after.get("contentHash") or ""),
        "featureCountBefore": len(feat_before),
        "featureCountAfter": len(feat_after),
        "probabilityHashChangedOfferCount": len(changed_prob),
        "gradeChangedOfferCount": len(changed_grade),
        "changedProbabilityOfferIds": changed_prob[:50],
        "changedGradeOfferIds": changed_grade[:50],
        "consumerChanged": (
            feature_hash_before != feature_hash_after
            or str(mf_before.get("contentHash") or "") != str(mf_after.get("contentHash") or "")
            or bool(changed_prob)
            or bool(changed_grade)
        ),
    }


def _load_existing_dag(dest: Path, *, cutoff: str) -> Dag | None:
    """Prefer canonical run DAG artifacts over throwaway mini-DAGs."""
    from dcm.runtime.dag import CANONICAL_DAG_ARTIFACTS

    for name in CANONICAL_DAG_ARTIFACTS:
        path = dest / name
        if not path.is_file():
            continue
        snap = read_json(path) or {}
        if isinstance(snap, dict) and (snap.get("nodes") or snap.get("cutoff")):
            dag = Dag.from_snapshot(snap)
            if not dag.cutoff:
                dag.cutoff = cutoff
            return dag
    return None


def _persist_run_dag(dest: Path, dag: Dag) -> None:
    """Write canonical runtime_dag.json plus source-aware alias used by tests."""
    from dcm.chat.state import write_json

    snap = dag.snapshot()
    write_json(dest / "runtime_dag.json", snap)
    write_json(dest / "source_aware_import_dag.json", snap)


def _ensure_offer_lineage(
    dag: Dag,
    *,
    claim_nodes: list[Any],
    row: dict[str, Any],
) -> Any:
    """Permanent claim→fact→feature→parameter→worlds→grade→rank for one offer."""
    oid = str(row.get("projectionId") or "")
    eid = str(row.get("eventId") or oid)
    return dag.ensure_offer_lineage(
        claim_keys=[c.key for c in claim_nodes],
        offer_id=oid,
        event_id=eid,
    )
