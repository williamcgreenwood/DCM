"""Deterministic fail-closed compiler for candidate signal operators."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from dcm.signals.contracts import EXECUTABLE_STATES, LifecycleState, SignalOperatorSpec
from dcm.signals.integration_gate import BindingCatalog, SignalIntegrationGate
from dcm.signals.overlap import resolved_overlap_group, semantic_signature
from dcm.signals.registry import CompiledOperator, CompiledRegistry


class SignalCompileError(ValueError):
    pass


class SignalCompiler:
    def __init__(self, catalog: BindingCatalog | None = None):
        self.gate = SignalIntegrationGate(catalog)

    def compile(self, candidates: Iterable[SignalOperatorSpec]) -> CompiledRegistry:
        specs = sorted(tuple(candidates), key=lambda item: item.operator_id)
        by_id: dict[str, SignalOperatorSpec] = {}
        for spec in specs:
            if spec.operator_id in by_id:
                raise SignalCompileError(f"SIGNAL_OPERATOR_ID_DUPLICATE:{spec.operator_id}")
            by_id[spec.operator_id] = spec

        reasons: dict[str, list[str]] = {spec.operator_id: list(self.gate.validate(spec)) for spec in specs}
        for spec in specs:
            for dep in spec.dependencies:
                if dep not in by_id:
                    reasons[spec.operator_id].append(f"DEPENDENCY_MISSING:{dep}")

        cycle_members = self._cycle_members(by_id)
        for operator_id in cycle_members:
            reasons[operator_id].append("DEPENDENCY_CYCLE")

        signatures = {spec.operator_id: semantic_signature(spec) for spec in specs}
        signature_groups: dict[str, list[str]] = defaultdict(list)
        for operator_id, signature in signatures.items():
            signature_groups[signature].append(operator_id)
        duplicates: set[str] = set()
        for ids in signature_groups.values():
            duplicates.update(sorted(ids)[1:])

        # An executable operator may depend only on another executable,
        # validated, non-duplicate operator. Propagate dependency failure so a
        # child cannot silently run with a missing semantic prerequisite.
        invalid = {operator_id for operator_id, values in reasons.items() if values} | duplicates
        changed = True
        while changed:
            changed = False
            for spec in specs:
                if spec.operator_id in invalid or spec.lifecycle_state not in EXECUTABLE_STATES:
                    continue
                for dep in spec.dependencies:
                    if dep in invalid or (dep in by_id and by_id[dep].lifecycle_state not in EXECUTABLE_STATES):
                        reasons[spec.operator_id].append(f"DEPENDENCY_NOT_EXECUTABLE:{dep}")
                        invalid.add(spec.operator_id)
                        changed = True
                        break

        compiled: list[CompiledOperator] = []
        for spec in specs:
            item_reasons = tuple(sorted(set(reasons[spec.operator_id])))
            if spec.operator_id in duplicates:
                state = LifecycleState.REJECTED_DUPLICATE
                item_reasons = tuple(sorted({*item_reasons, "SEMANTIC_DUPLICATE"}))
            elif item_reasons:
                state = LifecycleState.REJECTED_INVALID
            else:
                state = spec.lifecycle_state
            signature = signatures[spec.operator_id]
            compiled.append(
                CompiledOperator(
                    spec=spec,
                    lifecycle_state=state,
                    semantic_signature=signature,
                    overlap_group=resolved_overlap_group(spec, signature),
                    reasons=item_reasons,
                )
            )

        executable = {
            item.spec.operator_id
            for item in compiled
            if item.lifecycle_state in EXECUTABLE_STATES
        }
        order = self._topological_order(by_id, executable)
        return CompiledRegistry.build(compiled, order)

    @staticmethod
    def _cycle_members(by_id: dict[str, SignalOperatorSpec]) -> set[str]:
        color: dict[str, int] = {key: 0 for key in by_id}
        stack: list[str] = []
        cycles: set[str] = set()

        def visit(node: str) -> None:
            color[node] = 1
            stack.append(node)
            for dep in sorted(by_id[node].dependencies):
                if dep not in by_id:
                    continue
                if color[dep] == 0:
                    visit(dep)
                elif color[dep] == 1:
                    cycles.update(stack[stack.index(dep):])
            stack.pop()
            color[node] = 2

        for key in sorted(by_id):
            if color[key] == 0:
                visit(key)
        return cycles

    @staticmethod
    def _topological_order(by_id: dict[str, SignalOperatorSpec], executable: set[str]) -> tuple[str, ...]:
        indegree = {key: 0 for key in executable}
        children: dict[str, set[str]] = defaultdict(set)
        for key in executable:
            for dep in by_id[key].dependencies:
                if dep in executable:
                    indegree[key] += 1
                    children[dep].add(key)
        ready = sorted(key for key, value in indegree.items() if value == 0)
        out: list[str] = []
        while ready:
            node = ready.pop(0)
            out.append(node)
            for child in sorted(children[node]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort()
        return tuple(out)
