"""Content-addressed DAG with true changed-node → descendant invalidation.

Development runtime — not host-certified.

Permanent graph structures:
- parent links on each node
- reverse adjacency (children_map)
- conceptual lineage indexes (claim→fact→feature→parameter→worlds→offer outcomes→portfolio)

``invalidate(changed_node_ids)`` walks *actual* children only (deterministic BFS).
``invalidate_types`` / ``invalidate_for_delta`` remain explicit legacy helpers for
coarse delta-class wipes when seed IDs are unavailable.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable

from dcm.contracts.hashes import content_hash

STATES = (
    "PENDING",
    "RUNNING",
    "COMPLETE_VERIFIED",
    "BLOCKED",
    "INVALIDATED",
    "FAILED_RETRYABLE",
    "FAILED_TERMINAL",
)

LINE_DEPENDENT = {"MARKET_LINE", "LINE_SURFACE", "GRADE", "RANK", "PORTFOLIO", "FREEZE"}
LINE_SEED_TYPES = frozenset({"MARKET_LINE", "LINE_SURFACE"})
RESEARCH_STABLE = {
    "PLAYER_HISTORY",
    "SUBJECT_HISTORY",
    "TEAM_RESEARCH",
    "AFFILIATION_RESEARCH",
    "EVENT_RESEARCH",
    "SPORT_RULES",
}
ROLE_LINEAGE_TYPES = frozenset(
    {
        "ROLE",
        "PARTICIPATION",
        "OPPORTUNITY",
        "EFFICIENCY",
        "PARAMETER",
        "PARAMETER_SNAPSHOT",
        "EVENT_WORLDS",
        "GRADE",
        "RANK",
        "PORTFOLIO",
        "FREEZE",
    }
)
ENVIRONMENT_LINEAGE_TYPES = frozenset(
    {
        "ENVIRONMENT",
        "WEATHER",
        "EVENT_WORLDS",
        "GRADE",
        "RANK",
        "PORTFOLIO",
        "FREEZE",
    }
)

# Conceptual parent-type → child-types for permanent run DAG indexes.
LINEAGE_CHILD_TYPES: dict[str, tuple[str, ...]] = {
    "EVIDENCE_CLAIM": ("FACT", "MATERIAL_FACT"),
    "CLAIM": ("FACT", "MATERIAL_FACT"),
    "FACT": ("FEATURE",),
    "MATERIAL_FACT": ("FEATURE",),
    "FEATURE": ("PARAMETER", "PARAMETER_SNAPSHOT"),
    "ROLE": ("PARTICIPATION", "OPPORTUNITY", "PARAMETER", "PARAMETER_SNAPSHOT"),
    "PARTICIPATION": ("OPPORTUNITY", "PARAMETER", "PARAMETER_SNAPSHOT"),
    "OPPORTUNITY": ("PARAMETER", "PARAMETER_SNAPSHOT"),
    "EFFICIENCY": ("PARAMETER", "PARAMETER_SNAPSHOT"),
    "PARAMETER": ("EVENT_WORLDS", "GRADE"),
    "PARAMETER_SNAPSHOT": ("EVENT_WORLDS", "GRADE"),
    "EVENT_WORLDS": ("GRADE", "RANK", "OFFER_OUTCOME"),
    "MARKET_LINE": ("LINE_SURFACE", "GRADE"),
    "LINE_SURFACE": ("GRADE",),
    "GRADE": ("RANK", "FRONTIER", "PORTFOLIO"),
    "RANK": ("FRONTIER", "PORTFOLIO"),
    "FRONTIER": ("PORTFOLIO",),
    "PORTFOLIO": ("FREEZE",),
    "ENVIRONMENT": ("EVENT_WORLDS",),
    "WEATHER": ("EVENT_WORLDS", "ENVIRONMENT"),
}

DELTA_INVALIDATION = {
    "APPEND_MISSING_HISTORY": (
        "FEATURE", "ROLE", "PARTICIPATION", "OPPORTUNITY", "EFFICIENCY",
        "PARAMETER", "EVENT_WORLDS", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
    "REFRESH_CURRENT_CONTEXT": (
        "AVAILABILITY", "OPPORTUNITY", "EVENT_WORLDS", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
    "NEW_OPPONENT_REQUIRED": (
        "COUNTERPARTY", "MATCHUP", "EVENT_WORLDS", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
    "TEAM_CHANGED": (
        "ROLE", "PARTICIPATION", "OPPORTUNITY", "EFFICIENCY", "PARAMETER",
        "EVENT_WORLDS", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
    "ROLE_EPOCH_CHANGED": (
        "ROLE", "PARTICIPATION", "OPPORTUNITY", "EFFICIENCY", "PARAMETER",
        "EVENT_WORLDS", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
    "DEFINITION_CHANGED": (
        "MARKET_LINE", "LINE_SURFACE", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
    "REPLACE_INVALIDATED": (
        "FEATURE", "ROLE", "PARTICIPATION", "OPPORTUNITY", "EFFICIENCY",
        "PARAMETER", "EVENT_WORLDS", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
    "CONTRADICTED_REVERIFY": (
        "FEATURE", "PARAMETER", "EVENT_WORLDS", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
    "REFRESH_STALE": (
        "FEATURE", "PARAMETER", "EVENT_WORLDS", "GRADE", "RANK", "PORTFOLIO", "FREEZE",
    ),
}

CANONICAL_DAG_ARTIFACTS = (
    "runtime_dag.json",
    "dag.json",
    "source_aware_import_dag.json",
)


class DagFrozenError(RuntimeError):
    """Raised when invalidate attempts backward mutation after FREEZE is verified."""

    def __init__(self, message: str = "DAG_FROZEN_NO_BACKWARD_MUTATION") -> None:
        super().__init__(message)


def node_key(
    node_type: str,
    identity: str,
    cutoff: str,
    source_versions: dict[str, str],
    config_hash: str,
    schema_version: str,
    parent_hashes: Iterable[str],
) -> str:
    return content_hash(
        {
            "NodeType": node_type,
            "CanonicalIdentity": identity,
            "ForecastCutoff": cutoff,
            "SourceVersionSet": source_versions,
            "ConfigHash": config_hash,
            "SchemaVersion": schema_version,
            "ParentHashes": list(parent_hashes),
        }
    )


@dataclass
class DagNode:
    key: str
    node_type: str
    identity: str
    state: str = "PENDING"
    artifact_hash: str | None = None
    error: str | None = None
    parents: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "nodeType": self.node_type,
            "identity": self.identity,
            "state": self.state,
            "artifactHash": self.artifact_hash,
            "error": self.error,
            "parents": list(self.parents),
        }


@dataclass
class Dag:
    cutoff: str
    config_hash: str
    schema_version: str
    source_versions: dict[str, str]
    nodes: dict[str, DagNode] = field(default_factory=dict)
    # Explicit freeze latch (also inferred from COMPLETE_VERIFIED FREEZE nodes).
    frozen: bool = False

    def add(self, node_type: str, identity: str, parents: Iterable[str] = ()) -> DagNode:
        parents = tuple(parents)
        key = node_key(
            node_type,
            identity,
            self.cutoff,
            self.source_versions,
            self.config_hash,
            self.schema_version,
            parents,
        )
        existing = self.nodes.get(key)
        if existing is not None:
            return existing
        node = DagNode(key=key, node_type=node_type, identity=identity, parents=parents)
        self.nodes[key] = node
        return node

    def complete(self, key: str, artifact_hash: str) -> None:
        n = self.nodes[key]
        n.state = "COMPLETE_VERIFIED"
        n.artifact_hash = artifact_hash

    def block(self, key: str, error: str) -> None:
        n = self.nodes[key]
        n.state = "BLOCKED"
        n.error = error

    def fail(self, key: str, error: str, *, retryable: bool = False) -> None:
        n = self.nodes[key]
        n.state = "FAILED_RETRYABLE" if retryable else "FAILED_TERMINAL"
        n.error = error

    def is_frozen(self) -> bool:
        """True only after an explicit freeze latch (``mark_freeze`` / snapshot).

        A COMPLETE FREEZE *node* alone does not seal the DAG — line/role deltas
        must still be able to invalidate that node during an active run. Once
        ``frozen=True``, all invalidate paths raise DagFrozenError (no backward
        forecast mutation).
        """
        return bool(self.frozen)

    def children_map(self) -> dict[str, list[str]]:
        """Reverse adjacency: parent key → child keys (sorted for determinism)."""
        children: dict[str, list[str]] = {}
        for n in self.nodes.values():
            for parent in n.parents:
                children.setdefault(parent, []).append(n.key)
        for parent, kids in children.items():
            kids.sort()
        return children

    def reverse_adjacency_indexes(self) -> dict[str, Any]:
        """Permanent conceptual indexes used by run invalidation / audit.

        Returns parent→children plus type-scoped reverse maps for the lineage
        chain (claim→fact→feature→parameter→worlds→grade/rank→portfolio).
        """
        children = self.children_map()
        by_type: dict[str, list[str]] = {}
        by_identity: dict[str, list[str]] = {}
        for n in self.nodes.values():
            by_type.setdefault(n.node_type, []).append(n.key)
            by_identity.setdefault(n.identity, []).append(n.key)
        for bucket in by_type.values():
            bucket.sort()
        for bucket in by_identity.values():
            bucket.sort()
        type_edges: dict[str, list[str]] = {}
        for parent_key, child_keys in children.items():
            parent = self.nodes.get(parent_key)
            if parent is None:
                continue
            for child_key in child_keys:
                child = self.nodes.get(child_key)
                if child is None:
                    continue
                edge = f"{parent.node_type}->{child.node_type}"
                type_edges.setdefault(edge, []).append(f"{parent_key}>{child_key}")
        for edge_keys in type_edges.values():
            edge_keys.sort()
        return {
            "children": children,
            "byType": by_type,
            "byIdentity": by_identity,
            "typeEdges": type_edges,
            "lineageChildTypes": {k: list(v) for k, v in LINEAGE_CHILD_TYPES.items()},
        }

    def nodes_of_type(self, *types: str) -> list[DagNode]:
        wanted = {str(t) for t in types}
        return sorted(
            (n for n in self.nodes.values() if n.node_type in wanted),
            key=lambda n: (n.node_type, n.identity, n.key),
        )

    def find_by_identity(self, identity: str, *types: str) -> list[DagNode]:
        wanted = {str(t) for t in types} if types else None
        out = []
        for n in self.nodes.values():
            if n.identity != identity:
                continue
            if wanted is not None and n.node_type not in wanted:
                continue
            out.append(n)
        out.sort(key=lambda n: (n.node_type, n.key))
        return out

    def _assert_not_frozen(self) -> None:
        if self.is_frozen():
            raise DagFrozenError()

    def invalidate(
        self,
        changed_node_ids: Iterable[str],
        *,
        include_roots: bool = True,
        protect_types: Iterable[str] | None = None,
    ) -> list[str]:
        """Deterministic BFS invalidation of actual children only.

        Unrelated PARAMETER / EVENT_WORLDS / GRADE nodes outside the touched
        lineages are never wiped. Research-stable types may be listed in
        ``protect_types`` (default: RESEARCH_STABLE) and are skipped even if
        incorrectly linked as descendants.
        """
        self._assert_not_frozen()
        roots = [str(x) for x in changed_node_ids if x and str(x) in self.nodes]
        if not roots:
            return []
        protect = {str(t) for t in (protect_types if protect_types is not None else RESEARCH_STABLE)}
        children = self.children_map()
        ordered: list[str] = []
        seen: set[str] = set()
        queue: deque[str] = deque(sorted(set(roots)))
        while queue:
            key = queue.popleft()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
            for child in children.get(key, ()):
                if child not in seen:
                    queue.append(child)
        root_set = set(roots)
        hit: list[str] = []
        for key in ordered:
            if not include_roots and key in root_set:
                continue
            n = self.nodes[key]
            if n.node_type in protect and key not in root_set:
                continue
            n.state = "INVALIDATED"
            n.artifact_hash = None
            hit.append(key)
        return hit

    def invalidate_descendants(
        self, node_ids: Iterable[str], *, include_roots: bool = True
    ) -> list[str]:
        """Alias for ``invalidate`` — ID-scoped transitive children only."""
        return self.invalidate(node_ids, include_roots=include_roots)

    def invalidate_line_descendants(self) -> list[str]:
        """Line change: invalidate MARKET_LINE/LINE_SURFACE seeds and *their* descendants.

        Historical player/subject/team research (RESEARCH_STABLE) is never wiped.
        Unrelated GRADE/RANK/PORTFOLIO nodes outside the line lineage survive —
        unlike the legacy type-scoped wipe.
        """
        seeds = [n.key for n in self.nodes_of_type(*LINE_SEED_TYPES)]
        return self.invalidate(seeds, include_roots=True, protect_types=RESEARCH_STABLE)

    def invalidate_types(self, types: Iterable[str]) -> list[str]:
        """Legacy / coarse helper: wipe every node whose type is in ``types``.

        Prefer ``invalidate(changed_node_ids)`` on the live CFB path. Retained for
        delta-class callers that lack seed IDs.
        """
        self._assert_not_frozen()
        wanted = {str(t) for t in types}
        hit = []
        for n in sorted(self.nodes.values(), key=lambda x: x.key):
            if n.node_type in wanted:
                if n.node_type in RESEARCH_STABLE:
                    continue
                n.state = "INVALIDATED"
                n.artifact_hash = None
                hit.append(n.key)
        return hit

    def invalidate_for_delta(self, delta_class: str) -> list[str]:
        """Legacy coarse delta-class wipe via ``invalidate_types``.

        Subject/affiliation historical research is never invalidated by a line
        change. When seed node IDs are known, call ``invalidate`` / role /
        environment helpers instead.
        """
        if str(delta_class) == "REUSE_VALID":
            return []
        types = DELTA_INVALIDATION.get(str(delta_class), LINE_DEPENDENT)
        return self.invalidate_types(types)

    def invalidate_role_lineage(self, role_node_ids: Iterable[str]) -> list[str]:
        """Role/epoch change: only the given role nodes and their actual descendants."""
        return self.invalidate(role_node_ids, include_roots=True, protect_types=RESEARCH_STABLE)

    def invalidate_environment_lineage(self, env_or_weather_ids: Iterable[str]) -> list[str]:
        """Weather/environment change: only relevant env/weather nodes + descendants."""
        return self.invalidate(env_or_weather_ids, include_roots=True, protect_types=RESEARCH_STABLE)

    def ensure_offer_lineage(
        self,
        *,
        claim_keys: Iterable[str],
        offer_id: str,
        event_id: str,
        fact_id: str | None = None,
        feature_id: str | None = None,
    ) -> DagNode:
        """Install permanent claim→fact→feature→parameter→worlds→grade→rank chain.

        Returns the PARAMETER node for the offer (invalidation seed).
        """
        oid = str(offer_id)
        eid = str(event_id or oid)
        parents = [str(k) for k in claim_keys if k]
        fact = self.add("FACT", fact_id or f"fact:{oid}", parents=parents)
        if fact.state == "PENDING" and fact.artifact_hash is None:
            self.complete(fact.key, f"fact:{oid}")
        feature = self.add("FEATURE", feature_id or f"feature:{oid}", parents=[fact.key])
        if feature.state == "PENDING" and feature.artifact_hash is None:
            self.complete(feature.key, f"feature:{oid}")
        param = self.add("PARAMETER", oid, parents=[feature.key])
        if param.state == "PENDING" and param.artifact_hash is None:
            self.complete(param.key, f"param:{oid}")
        worlds = self.add("EVENT_WORLDS", eid, parents=[param.key])
        if worlds.state == "PENDING" and worlds.artifact_hash is None:
            self.complete(worlds.key, f"worlds:{eid}")
        grade_n = self.add("GRADE", oid, parents=[param.key, worlds.key])
        if grade_n.state == "PENDING" and grade_n.artifact_hash is None:
            self.complete(grade_n.key, f"grade:{oid}")
        rank_n = self.add("RANK", oid, parents=[grade_n.key])
        if rank_n.state == "PENDING" and rank_n.artifact_hash is None:
            self.complete(rank_n.key, f"rank:{oid}")
        return param

    def ensure_portfolio_link(self, *, grade_or_rank_keys: Iterable[str], portfolio_id: str = "board") -> DagNode:
        parents = [str(k) for k in grade_or_rank_keys if k]
        port = self.add("PORTFOLIO", portfolio_id, parents=parents)
        if port.state == "PENDING" and port.artifact_hash is None:
            self.complete(port.key, f"portfolio:{portfolio_id}")
        return port

    def mark_freeze(self, *, portfolio_key: str | None = None, freeze_id: str = "board") -> DagNode:
        parents = (portfolio_key,) if portfolio_key else ()
        freeze = self.add("FREEZE", freeze_id, parents=parents)
        self.complete(freeze.key, f"freeze:{freeze_id}")
        self.frozen = True
        return freeze

    @classmethod
    def from_snapshot(cls, snap: dict[str, Any]) -> "Dag":
        """Reload a previously persisted DAG snapshot (nodes + parent links)."""
        dag = cls(
            cutoff=str(snap.get("cutoff") or ""),
            config_hash=str(snap.get("configHash") or ""),
            schema_version=str(snap.get("schemaVersion") or ""),
            source_versions={str(k): str(v) for k, v in dict(snap.get("sourceVersions") or {}).items()},
            frozen=bool(snap.get("frozen")),
        )
        for raw in snap.get("nodes") or []:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("key") or "")
            if not key:
                continue
            node = DagNode(
                key=key,
                node_type=str(raw.get("nodeType") or ""),
                identity=str(raw.get("identity") or ""),
                state=str(raw.get("state") or "PENDING"),
                artifact_hash=raw.get("artifactHash"),
                error=raw.get("error"),
                parents=tuple(str(p) for p in (raw.get("parents") or ())),
            )
            dag.nodes[key] = node
        return dag

    def preserved_research_nodes(self) -> list[str]:
        return [n.key for n in self.nodes.values() if n.node_type in RESEARCH_STABLE]

    def reused(self) -> int:
        return sum(1 for n in self.nodes.values() if n.state == "COMPLETE_VERIFIED")

    def pending(self) -> list[str]:
        return [k for k, n in self.nodes.items() if n.state in {"PENDING", "INVALIDATED"}]

    def snapshot(self) -> dict[str, Any]:
        indexes = self.reverse_adjacency_indexes()
        return {
            "cutoff": self.cutoff,
            "configHash": self.config_hash,
            "schemaVersion": self.schema_version,
            "sourceVersions": self.source_versions,
            "frozen": self.is_frozen(),
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "completed": [n.key for n in self.nodes.values() if n.state == "COMPLETE_VERIFIED"],
            "pending": self.pending(),
            "invalidated": [n.key for n in self.nodes.values() if n.state == "INVALIDATED"],
            "children": indexes["children"],
            "indexes": {
                "byType": indexes["byType"],
                "byIdentity": indexes["byIdentity"],
                "typeEdges": indexes["typeEdges"],
            },
        }
