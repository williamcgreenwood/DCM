"""Cutoff-immutable FeatureStore: observations for later ML, not trained models.

Windows L3/L5/L10/L15/L20/season are derived from the FULL log. Last-5 never
replaces the season. Persist as jsonl + manifest with a content hash.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dcm.contracts.hashes import content_hash
from dcm.research.player_packet import WINDOW_SIZES, window_means
from dcm.research.role_epoch import RoleEpochBuilder

FEATURE_SCHEMA_VERSION = "dcm.feature_store.v1-20260830"
TRANSFORMATION_VERSION = "dcm.features.windows.v1-20260830"
FEATURE_FAMILIES = frozenset({"ROLE", "OPPORTUNITY", "EFFICIENCY", "MATCHUP", "CONTEXT"})
WINDOW_STATS = ("minutes", "pts", "reb", "ast", "fga", "tpa", "fta")


def _s(value: Any) -> str:
    return "" if value is None else str(value)


def feature_record(
    *,
    entity: str,
    event_id: str,
    feature_name: str,
    value: Any,
    as_of: str,
    source_hashes: list[str],
    family: str,
    transformation_version: str = TRANSFORMATION_VERSION,
    feature_schema_version: str = FEATURE_SCHEMA_VERSION,
) -> dict[str, Any]:
    if family not in FEATURE_FAMILIES:
        raise ValueError(f"unknown feature family: {family}")
    return {
        "entity": entity,
        "eventId": event_id,
        "featureName": feature_name,
        "value": value,
        "asOf": as_of,
        "sourceHashes": list(source_hashes),
        "transformationVersion": transformation_version,
        "featureSchemaVersion": feature_schema_version,
        "family": family,
        "cutoffImmutable": True,
        "trainedModel": False,
    }


def _identity(packet: dict[str, Any], offer_set: dict[str, Any] | None) -> tuple[str, str]:
    ident = packet.get("identity") if isinstance(packet.get("identity"), dict) else {}
    offer = offer_set if isinstance(offer_set, dict) else {}
    entity = _s(ident.get("playerId") or offer.get("playerId") or packet.get("playerId"))
    event_id = _s(ident.get("eventId") or offer.get("eventId") or packet.get("eventId"))
    return entity, event_id


def _logs_from_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    logs = packet.get("gameLogs") or packet.get("game_logs") or []
    return [r for r in logs if isinstance(r, dict)] if isinstance(logs, list) else []


class FeatureStore:
    """Build cutoff-immutable feature records from a PlayerResearchPacket."""

    feature_schema_version = FEATURE_SCHEMA_VERSION
    transformation_version = TRANSFORMATION_VERSION

    @classmethod
    def build_from_packet(
        cls,
        packet: dict[str, Any],
        offer_set: dict[str, Any] | None,
        cutoff: str,
    ) -> list[dict[str, Any]]:
        packet = packet if isinstance(packet, dict) else {}
        offer = offer_set if isinstance(offer_set, dict) else {}
        entity, event_id = _identity(packet, offer)
        as_of = _s(cutoff or packet.get("asOf") or "")
        source_hashes = [str(h) for h in (packet.get("sourceHashes") or []) if h]
        if packet.get("contentHash"):
            source_hashes.append(str(packet["contentHash"]))
        source_hashes = sorted(set(source_hashes))
        logs = _logs_from_packet(packet)
        features: list[dict[str, Any]] = []

        def add(name: str, value: Any, family: str) -> None:
            features.append(
                feature_record(
                    entity=entity,
                    event_id=event_id,
                    feature_name=name,
                    value=value,
                    as_of=as_of,
                    source_hashes=source_hashes,
                    family=family,
                )
            )

        packet_windows = packet.get("windows") if isinstance(packet.get("windows"), dict) else {}
        for n in WINDOW_SIZES:
            key = f"L{n}"
            stats = packet_windows.get(key) if isinstance(packet_windows.get(key), dict) else None
            computed = window_means(logs, n)
            merged = dict(computed)
            if stats:
                merged.update({k: v for k, v in stats.items() if v is not None})
            family_map = {
                "minutes": "OPPORTUNITY",
                "fga": "OPPORTUNITY",
                "tpa": "OPPORTUNITY",
                "fta": "OPPORTUNITY",
                "pts": "EFFICIENCY",
                "reb": "EFFICIENCY",
                "ast": "EFFICIENCY",
            }
            for stat in WINDOW_STATS:
                value = merged.get(f"{stat}_mean")
                add(f"{key}_{stat}_mean", value, family_map[stat])
            add(f"{key}_support_n", merged.get("support_n"), "OPPORTUNITY")
            add(f"{key}_nAvailable", merged.get("nAvailable"), "CONTEXT")

        season = window_means(logs, max(len(logs), 1) if logs else 1)
        if logs:
            season = window_means(logs, len(logs))
        else:
            season = {f"{s}_mean": None for s in WINDOW_STATS}
            season["support_n"] = 0
            season["nAvailable"] = 0
        for stat in WINDOW_STATS:
            fam = "OPPORTUNITY" if stat in {"minutes", "fga", "tpa", "fta"} else "EFFICIENCY"
            add(f"season_{stat}_mean", season.get(f"{stat}_mean"), fam)
        add("season_support_n", season.get("support_n") if logs else 0, "OPPORTUNITY")
        add("gameLogCount", packet.get("gameLogCount") if packet.get("gameLogCount") is not None else len(logs), "CONTEXT")
        add("evidenceUsed", bool(packet.get("evidenceUsed")), "CONTEXT")

        role_hints = packet.get("roleHints") if isinstance(packet.get("roleHints"), dict) else {}
        claim_value = {
            "game_logs": logs,
            "role": role_hints.get("role") or packet.get("status"),
            "league": (packet.get("identity") or {}).get("league") if isinstance(packet.get("identity"), dict) else None,
        }
        built = RoleEpochBuilder().build(
            claim_value,
            today_context={"role": role_hints.get("role"), "league": claim_value.get("league")},
        )
        add("role_support_n", built.get("support_n"), "ROLE")
        add("role_prior_weight", (built.get("shrinkage") or {}).get("priorWeight"), "ROLE")
        add("role_role_weight", (built.get("shrinkage") or {}).get("roleWeight"), "ROLE")
        add("role_season_weight", (built.get("shrinkage") or {}).get("seasonWeight"), "ROLE")
        selected = built.get("selected_epoch") or {}
        add("role_selected_label", selected.get("label"), "ROLE")
        add("role_selected_n", selected.get("n"), "ROLE")
        add("role_epoch_count", len(built.get("epochs") or []), "ROLE")
        add("role_invented", False, "ROLE")

        add("opponent", offer.get("opponent") or (packet.get("identity") or {}).get("opponent"), "MATCHUP")
        add("team", offer.get("team") or (packet.get("identity") or {}).get("team"), "MATCHUP")
        add("league", offer.get("league") or (packet.get("identity") or {}).get("league"), "CONTEXT")
        add("eventStartTime", offer.get("eventStartTime") or (packet.get("identity") or {}).get("eventStartTime"), "CONTEXT")
        add("status", packet.get("status"), "CONTEXT")
        add("offerCount", offer.get("offerCount") or len(offer.get("offers") or []), "CONTEXT")
        return features


def persist_feature_store(
    dest: Path,
    packets: list[dict[str, Any]],
    offer_sets: list[dict[str, Any]] | None = None,
    cutoff: str = "",
) -> dict[str, Any]:
    """Write feature_store.jsonl + feature_store_manifest.json. Observations only."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    sets = [s for s in (offer_sets or []) if isinstance(s, dict)]
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    by_set_id: dict[str, dict[str, Any]] = {}
    for offer in sets:
        by_key[(str(offer.get("playerId") or ""), str(offer.get("eventId") or ""))] = offer
        if offer.get("setId"):
            by_set_id[str(offer["setId"])] = offer

    features: list[dict[str, Any]] = []
    for packet in packets or []:
        if not isinstance(packet, dict):
            continue
        ident = packet.get("identity") if isinstance(packet.get("identity"), dict) else {}
        offer = by_set_id.get(str(packet.get("offerSetId") or "")) or by_key.get(
            (str(ident.get("playerId") or ""), str(ident.get("eventId") or ""))
        ) or {}
        features.extend(FeatureStore.build_from_packet(packet, offer, cutoff))

    jsonl_path = dest / "feature_store.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for rec in features:
            handle.write(json.dumps(rec, sort_keys=True, ensure_ascii=True) + "\n")

    entities = sorted({str(r.get("entity") or "") for r in features if r.get("entity")})
    families = sorted({str(r.get("family") or "") for r in features if r.get("family")})
    manifest_body = {
        "schema": "pillars_dcm.feature_store_manifest.v1",
        "featureSchemaVersion": FEATURE_SCHEMA_VERSION,
        "transformationVersion": TRANSFORMATION_VERSION,
        "featureCount": len(features),
        "entityCount": len(entities),
        "packetCount": len([p for p in (packets or []) if isinstance(p, dict)]),
        "families": families,
        "asOf": cutoff,
        "trainedModel": False,
        "observationsOnly": True,
        "mlClaim": "NONE",
        "cutoffImmutable": True,
    }
    manifest_body["contentHash"] = content_hash({**manifest_body, "features": features})
    (dest / "feature_store_manifest.json").write_text(
        json.dumps(manifest_body, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest_body
