"""Content-addressed DAG. Development runtime — not host-certified."""

from __future__ import annotations

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
RESEARCH_STABLE = {
    "PLAYER_HISTORY",
    "SUBJECT_HISTORY",
    "TEAM_RESEARCH",
    "AFFILIATION_RESEARCH",
    "EVENT_RESEARCH",
    "SPORT_RULES",
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

    def invalidate_line_descendants(self) -> list[str]:
        """A line change invalidates market/grade/rank/portfolio/freeze, not research."""
        return self.invalidate_types(LINE_DEPENDENT)

    def invalidate_types(self, types: Iterable[str]) -> list[str]:
        wanted = {str(t) for t in types}
        hit = []
        for n in self.nodes.values():
            if n.node_type in wanted:
                n.state = "INVALIDATED"
                n.artifact_hash = None
                hit.append(n.key)
        return hit

    def children_map(self) -> dict[str, list[str]]:
        """Reverse adjacency: parent key → child keys."""
        children: dict[str, list[str]] = {}
        for n in self.nodes.values():
            for parent in n.parents:
                children.setdefault(parent, []).append(n.key)
        return children

    def invalidate_descendants(self, node_ids: Iterable[str], *, include_roots: bool = True) -> list[str]:
        """Invalidate transitive children of specific node keys via reverse adjacency.

        Unlike invalidate_types, this only touches the lineage of the given IDs —
        unrelated PARAMETER / EVENT_WORLDS / GRADE nodes remain untouched.
        """
        roots = [str(x) for x in node_ids if x and str(x) in self.nodes]
        if not roots:
            return []
        children = self.children_map()
        ordered: list[str] = []
        seen: set[str] = set()
        stack = list(roots)
        while stack:
            key = stack.pop()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
            for child in children.get(key, ()):
                if child not in seen:
                    stack.append(child)
        root_set = set(roots)
        hit: list[str] = []
        for key in ordered:
            if not include_roots and key in root_set:
                continue
            n = self.nodes[key]
            n.state = "INVALIDATED"
            n.artifact_hash = None
            hit.append(key)
        return hit

    def invalidate_for_delta(self, delta_class: str) -> list[str]:
        """Invalidate only downstream nodes that depend on this evidence class.

        Subject/affiliation historical research is never invalidated by a line change.
        """
        if str(delta_class) == "REUSE_VALID":
            return []
        types = DELTA_INVALIDATION.get(str(delta_class), LINE_DEPENDENT)
        return self.invalidate_types(types)

    @classmethod
    def from_snapshot(cls, snap: dict[str, Any]) -> "Dag":
        """Reload a previously persisted DAG snapshot (nodes + parent links)."""
        dag = cls(
            cutoff=str(snap.get("cutoff") or ""),
            config_hash=str(snap.get("configHash") or ""),
            schema_version=str(snap.get("schemaVersion") or ""),
            source_versions={str(k): str(v) for k, v in dict(snap.get("sourceVersions") or {}).items()},
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
        return {
            "cutoff": self.cutoff,
            "configHash": self.config_hash,
            "schemaVersion": self.schema_version,
            "sourceVersions": self.source_versions,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "completed": [n.key for n in self.nodes.values() if n.state == "COMPLETE_VERIFIED"],
            "pending": self.pending(),
            "invalidated": [n.key for n in self.nodes.values() if n.state == "INVALIDATED"],
        }
