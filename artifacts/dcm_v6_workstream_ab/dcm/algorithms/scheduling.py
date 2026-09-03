"""Weighted coverage, lazy-greedy CELF, and deterministic batch packing."""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from dcm.algorithms.searching import submodular_lazy_greedy, weighted_set_cover


def requirement_weight(
    *,
    dependent_offer_mass: float,
    criticality: float,
    information_importance: float,
    freshness_urgency: float,
    current_uncertainty: float,
    eligibility_unlock: float,
    frontier_weight: float,
    deadline_urgency: float,
    weights: Mapping[str, float] | None = None,
) -> float:
    w = {
        "w1": 1.0,
        "w2": 1.0,
        "w3": 1.0,
        "w4": 1.0,
        "w5": 1.0,
        "w6": 1.0,
        "w7": 1.0,
        "w8": 1.0,
    }
    w.update(dict(weights or {}))

    def clip(v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    return (
        w["w1"] * max(0.0, float(dependent_offer_mass))
        + w["w2"] * clip(criticality)
        + w["w3"] * clip(information_importance)
        + w["w4"] * clip(freshness_urgency)
        + w["w5"] * clip(current_uncertainty)
        + w["w6"] * clip(eligibility_unlock)
        + w["w7"] * clip(frontier_weight)
        + w["w8"] * clip(deadline_urgency)
    )


def acquisition_cost(
    *,
    web_calls: float = 1.0,
    input_tokens: float = 0.0,
    output_tokens: float = 0.0,
    latency: float = 0.0,
    cpu: float = 0.0,
    risk: float = 0.0,
    coeffs: Mapping[str, float] | None = None,
) -> float:
    c = {"c_web": 1.0, "c_in": 0.001, "c_out": 0.002, "c_lat": 0.0, "c_cpu": 0.0, "c_risk": 0.25}
    c.update(dict(coeffs or {}))
    return (
        c["c_web"] * float(web_calls)
        + c["c_in"] * float(input_tokens) / 1000.0
        + c["c_out"] * float(output_tokens) / 1000.0
        + c["c_lat"] * float(latency)
        + c["c_cpu"] * float(cpu)
        + c["c_risk"] * float(risk)
    )


def expected_marginal_gain(
    *,
    p_success: float,
    authority_quality: float,
    novelty: float,
    uncovered_weights: Iterable[float],
) -> float:
    return max(0.0, float(p_success)) * max(0.0, float(authority_quality)) * max(0.0, float(novelty)) * sum(float(w) for w in uncovered_weights)


def utility(gain: float, cost: float, *, epsilon: float = 1e-9) -> float:
    return float(gain) / max(float(epsilon), float(cost))


@dataclass
class LazyGreedyScheduler:
    """CELF-style lazy greedy maximizer for AcquisitionAction utilities."""

    gain_fn: Callable[[str, frozenset[str]], float]
    cost_fn: Callable[[str], float]
    _heap: list[tuple[float, str, int]] = field(default_factory=list)
    _stamp: dict[str, int] = field(default_factory=dict)
    selected: list[str] = field(default_factory=list)

    def seed(self, action_ids: Sequence[str]) -> None:
        self._heap = []
        self._stamp = {aid: 0 for aid in action_ids}
        self.selected = []
        empty = frozenset()
        for aid in action_ids:
            u = utility(self.gain_fn(aid, empty), self.cost_fn(aid))
            heapq.heappush(self._heap, (-u, aid, 0))

    def next_action(self) -> str | None:
        selected_set = frozenset(self.selected)
        while self._heap:
            _neg, aid, seen = heapq.heappop(self._heap)
            if aid in selected_set:
                continue
            if seen != self._stamp.get(aid, 0):
                continue
            current = utility(self.gain_fn(aid, selected_set), self.cost_fn(aid))
            self._stamp[aid] = self._stamp.get(aid, 0) + 1
            if self._heap and current + 1e-15 < -self._heap[0][0]:
                heapq.heappush(self._heap, (-current, aid, self._stamp[aid]))
                continue
            if current <= 0:
                return None
            self.selected.append(aid)
            return aid
        return None

    def run(self, action_ids: Sequence[str], *, k: int | None = None) -> list[str]:
        self.seed(action_ids)
        while True:
            if k is not None and len(self.selected) >= k:
                break
            if self.next_action() is None:
                break
        return list(self.selected)


def greedy_value_density_pack(
    items: Sequence[str],
    value: Mapping[str, float],
    weight: Mapping[str, float],
    *,
    capacity: float,
) -> list[str]:
    ranked = sorted(items, key=lambda i: (-(float(value.get(i, 0.0)) / max(float(weight.get(i, 1.0)), 1e-12)), i))
    packed: list[str] = []
    used = 0.0
    for item in ranked:
        w = float(weight.get(item, 1.0))
        if used + w <= capacity:
            packed.append(item)
            used += w
    return packed


def first_fit_decreasing(
    items: Sequence[str],
    sizes: Mapping[str, float],
    *,
    bin_capacity: float,
    max_bins: int,
) -> list[list[str]]:
    ordered = sorted(items, key=lambda i: (-float(sizes.get(i, 1.0)), i))
    bins: list[list[str]] = []
    remaining: list[float] = []
    for item in ordered:
        size = float(sizes.get(item, 1.0))
        placed = False
        for i, left in enumerate(remaining):
            if size <= left:
                bins[i].append(item)
                remaining[i] -= size
                placed = True
                break
        if not placed:
            if len(bins) >= max_bins:
                continue
            bins.append([item])
            remaining.append(bin_capacity - size)
    return bins


def cover_actions(universe: Iterable[Any], actions: Mapping[str, Iterable[Any]], weights: Mapping[str, float] | None = None) -> list[str]:
    chosen, _ = weighted_set_cover(universe, actions, weights)
    return chosen


def lazy_submodular_select(
    items: Sequence[str],
    marginal_gain: Callable[[str, frozenset[str]], float],
    cost: Callable[[str], float],
    *,
    k: int | None = None,
    budget: float | None = None,
) -> list[str]:
    return submodular_lazy_greedy(items, marginal_gain, cost, k=k, budget=budget)
