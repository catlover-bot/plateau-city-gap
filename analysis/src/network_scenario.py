"""Sparse, deterministic facility-location primitives for a road graph."""

from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CandidateGainMatrix:
    candidate_ids: tuple[str, ...]
    demand_node_ids: tuple[str, ...]
    candidate_index: np.ndarray
    demand_index: np.ndarray
    network_distance_m: np.ndarray
    distance_reduction_m: np.ndarray
    candidate_offsets: np.ndarray

    def candidate_slice(self, candidate: int) -> slice:
        return slice(self.candidate_offsets[candidate], self.candidate_offsets[candidate + 1])


def _graph_arrays(
    nodes: pd.DataFrame, edges: pd.DataFrame
) -> tuple[list[str], dict[str, int], list[list[tuple[int, float]]]]:
    node_ids = sorted(nodes.node_id.astype(str))
    node_index = {node_id: index for index, node_id in enumerate(node_ids)}
    adjacency: list[list[tuple[int, float]]] = [[] for _ in node_ids]
    for row in edges.itertuples(index=False):
        source = node_index[str(row.source_node_id)]
        target = node_index[str(row.target_node_id)]
        weight = float(row.length_m)
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("Every scenario graph edge must have a positive finite length")
        adjacency[source].append((target, weight))
        adjacency[target].append((source, weight))
    for neighbors in adjacency:
        neighbors.sort()
    return node_ids, node_index, adjacency


def build_candidate_gain_matrix(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    candidates: pd.DataFrame,
    demand_nodes: pd.DataFrame,
) -> CandidateGainMatrix:
    """Compute only candidate reductions inside each demand node's baseline radius."""

    required_candidates = {"candidate_id", "node_id"}
    required_demand = {"node_id", "baseline_graph_distance_m"}
    if missing := required_candidates - set(candidates.columns):
        raise ValueError(f"Candidate columns missing: {sorted(missing)}")
    if missing := required_demand - set(demand_nodes.columns):
        raise ValueError(f"Demand columns missing: {sorted(missing)}")

    node_ids, node_index, adjacency = _graph_arrays(nodes, edges)
    ordered_candidates = candidates.sort_values("candidate_id").reset_index(drop=True)
    if not ordered_candidates.candidate_id.is_unique:
        raise ValueError("candidate_id must be unique")
    candidate_ids = tuple(ordered_candidates.candidate_id.astype(str))
    candidate_at_node = np.full(len(node_ids), -1, dtype=np.int32)
    for candidate, node_id in enumerate(ordered_candidates.node_id.astype(str)):
        graph_node = node_index.get(node_id)
        if graph_node is None:
            raise ValueError(f"Candidate references unknown node {node_id}")
        if candidate_at_node[graph_node] >= 0:
            raise ValueError(f"Multiple candidates reference node {node_id}")
        candidate_at_node[graph_node] = candidate

    ordered_demand = demand_nodes.sort_values("node_id").reset_index(drop=True)
    if not ordered_demand.node_id.is_unique:
        raise ValueError("Demand node_id must be unique")
    demand_ids = tuple(ordered_demand.node_id.astype(str))
    gain_candidate: list[int] = []
    gain_demand: list[int] = []
    gain_distance: list[float] = []
    gain_reduction: list[float] = []

    for demand, row in enumerate(ordered_demand.itertuples(index=False)):
        cutoff = float(row.baseline_graph_distance_m)
        if not math.isfinite(cutoff) or cutoff <= 0:
            continue
        source = node_index.get(str(row.node_id))
        if source is None:
            raise ValueError(f"Demand references unknown node {row.node_id}")
        distances = {source: 0.0}
        queue = [(0.0, source)]
        while queue:
            distance, node = heapq.heappop(queue)
            if distance > distances[node] + 1e-9:
                continue
            candidate = int(candidate_at_node[node])
            if candidate >= 0 and distance < cutoff - 1e-9:
                gain_candidate.append(candidate)
                gain_demand.append(demand)
                gain_distance.append(distance)
                gain_reduction.append(cutoff - distance)
            for neighbor, weight in adjacency[node]:
                proposed = distance + weight
                if proposed >= cutoff - 1e-9:
                    continue
                if proposed < distances.get(neighbor, math.inf) - 1e-9:
                    distances[neighbor] = proposed
                    heapq.heappush(queue, (proposed, neighbor))

    candidate_array = np.asarray(gain_candidate, dtype=np.int32)
    demand_array = np.asarray(gain_demand, dtype=np.int32)
    distance_array = np.asarray(gain_distance, dtype=np.float64)
    reduction_array = np.asarray(gain_reduction, dtype=np.float64)
    order = np.lexsort((demand_array, candidate_array))
    candidate_array = candidate_array[order]
    demand_array = demand_array[order]
    distance_array = distance_array[order]
    reduction_array = reduction_array[order]
    counts = np.bincount(candidate_array, minlength=len(candidate_ids))
    offsets = np.concatenate(([0], np.cumsum(counts))).astype(np.int64)
    return CandidateGainMatrix(
        candidate_ids=candidate_ids,
        demand_node_ids=demand_ids,
        candidate_index=candidate_array,
        demand_index=demand_array,
        network_distance_m=distance_array,
        distance_reduction_m=reduction_array,
        candidate_offsets=offsets,
    )


def evaluate_selected(
    matrix: CandidateGainMatrix, selected: list[int]
) -> tuple[np.ndarray, np.ndarray]:
    """Return best distance reduction and assigned selected candidate per demand node."""

    best = np.zeros(len(matrix.demand_node_ids), dtype=float)
    assigned = np.full(len(matrix.demand_node_ids), -1, dtype=np.int32)
    for candidate in selected:
        section = matrix.candidate_slice(candidate)
        demands = matrix.demand_index[section]
        reductions = matrix.distance_reduction_m[section]
        improved = reductions > best[demands] + 1e-9
        if np.any(improved):
            best[demands[improved]] = reductions[improved]
            assigned[demands[improved]] = candidate
    return best, assigned


def greedy_select(
    matrix: CandidateGainMatrix,
    weights: np.ndarray,
    overall_weights: np.ndarray,
    candidate_x: np.ndarray,
    candidate_y: np.ndarray,
    *,
    max_sites: int,
    minimum_separation_m: float,
    candidate_components: np.ndarray | None = None,
    unreachable_component_weights: dict[str, float] | None = None,
) -> tuple[list[int], list[dict[str, Any]]]:
    """Select an arbitrary N by deterministic forward greedy marginal gain.

    A one-site prefix is exact for the supplied linear objective over the candidate
    set. Longer prefixes are greedy approximations. If unreachable component
    weights are supplied, newly reachable demand is the first lexicographic
    objective and distance reduction is only a tie-breaker.
    """

    if max_sites < 1:
        raise ValueError("max_sites must be positive")
    demand_count = len(matrix.demand_node_ids)
    weights = np.asarray(weights, dtype=float)
    overall_weights = np.asarray(overall_weights, dtype=float)
    if len(weights) != demand_count or len(overall_weights) != demand_count:
        raise ValueError("Objective weight arrays must align to demand nodes")
    candidate_x = np.asarray(candidate_x, dtype=float)
    candidate_y = np.asarray(candidate_y, dtype=float)
    if len(candidate_x) != len(matrix.candidate_ids) or len(candidate_y) != len(
        matrix.candidate_ids
    ):
        raise ValueError("Candidate coordinates must align to matrix candidate order")

    current = np.zeros(demand_count, dtype=float)
    available = np.ones(len(matrix.candidate_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, Any]] = []
    covered_unreachable_components: set[str] = set()
    unreachable_component_weights = unreachable_component_weights or {}

    def better(key: tuple[float, ...], reference: tuple[float, ...] | None) -> bool:
        if reference is None:
            return True
        for value, other in zip(key, reference, strict=True):
            if value > other + 1e-9:
                return True
            if value < other - 1e-9:
                return False
        return False

    for step in range(max_sites):
        step_started = time.perf_counter()
        best_candidate = -1
        best_key: tuple[float, ...] | None = None
        best_primary = 0.0
        best_overall = 0.0
        best_reachability = 0.0
        for candidate in np.flatnonzero(available):
            section = matrix.candidate_slice(int(candidate))
            demands = matrix.demand_index[section]
            marginal = np.maximum(matrix.distance_reduction_m[section] - current[demands], 0.0)
            primary = float(np.dot(marginal, weights[demands]))
            overall = float(np.dot(marginal, overall_weights[demands]))
            reachability = 0.0
            if candidate_components is not None:
                component = str(candidate_components[candidate])
                if component not in covered_unreachable_components:
                    reachability = float(unreachable_component_weights.get(component, 0.0))
            key = (reachability, primary, overall)
            if better(key, best_key):
                best_candidate = int(candidate)
                best_key = key
                best_primary = primary
                best_overall = overall
                best_reachability = reachability
        if best_candidate < 0 or best_key is None:
            break
        # When every remaining marginal is zero there is no evidence-backed site to add.
        if max(best_key) <= 1e-9:
            break
        selected.append(best_candidate)
        section = matrix.candidate_slice(best_candidate)
        demands = matrix.demand_index[section]
        current[demands] = np.maximum(current[demands], matrix.distance_reduction_m[section])
        if candidate_components is not None:
            covered_unreachable_components.add(str(candidate_components[best_candidate]))
        squared = (candidate_x - candidate_x[best_candidate]) ** 2 + (
            candidate_y - candidate_y[best_candidate]
        ) ** 2
        available[squared < minimum_separation_m**2 - 1e-9] = False
        available[selected] = False
        trace.append(
            {
                "step": step + 1,
                "candidate_index": best_candidate,
                "candidate_id": matrix.candidate_ids[best_candidate],
                "marginal_objective": best_primary,
                "marginal_overall_building_distance_m": best_overall,
                "newly_reachable_weight": best_reachability,
                "stage_runtime_seconds": round(time.perf_counter() - step_started, 6),
            }
        )
    return selected, trace


def balanced_greedy_select(
    matrix: CandidateGainMatrix,
    objective_weights: dict[str, np.ndarray],
    overall_weights: np.ndarray,
    candidate_x: np.ndarray,
    candidate_y: np.ndarray,
    *,
    max_sites: int,
    minimum_separation_m: float,
) -> tuple[list[int], list[dict[str, Any]]]:
    """Maximize the worst normalized marginal objective, without a weighted sum.

    At every greedy stage each candidate's marginal gain is calculated separately
    for every objective and normalized by that objective's best available gain.
    Candidates are compared lexicographically by their sorted normalized gains
    (worst first), then by overall building gain. This is a max-min compromise,
    not a claim that unlike municipal objectives form one cardinal score.
    """

    if max_sites < 1:
        raise ValueError("max_sites must be positive")
    names = tuple(objective_weights)
    if len(names) < 2:
        raise ValueError("Balanced selection requires at least two objectives")
    weight_arrays = {name: np.asarray(objective_weights[name], dtype=float) for name in names}
    demand_count = len(matrix.demand_node_ids)
    if any(len(weights) != demand_count for weights in weight_arrays.values()):
        raise ValueError("Balanced objective weights must align to demand nodes")
    overall_weights = np.asarray(overall_weights, dtype=float)
    candidate_x = np.asarray(candidate_x, dtype=float)
    candidate_y = np.asarray(candidate_y, dtype=float)
    current = np.zeros(demand_count, dtype=float)
    available = np.ones(len(matrix.candidate_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, Any]] = []

    for step in range(max_sites):
        step_started = time.perf_counter()
        available_candidates = np.flatnonzero(available)
        if not len(available_candidates):
            break
        marginal_by_candidate: dict[int, dict[str, float]] = {}
        maxima = {name: 0.0 for name in names}
        for candidate in available_candidates:
            section = matrix.candidate_slice(int(candidate))
            demands = matrix.demand_index[section]
            marginal = np.maximum(matrix.distance_reduction_m[section] - current[demands], 0.0)
            values = {
                name: float(np.dot(marginal, weights[demands]))
                for name, weights in weight_arrays.items()
            }
            marginal_by_candidate[int(candidate)] = values
            for name, value in values.items():
                maxima[name] = max(maxima[name], value)

        best_candidate = -1
        best_key: tuple[float, ...] | None = None
        best_values: dict[str, float] = {}
        for candidate in available_candidates:
            candidate = int(candidate)
            values = marginal_by_candidate[candidate]
            normalized = sorted(
                values[name] / maxima[name] if maxima[name] > 1e-9 else 1.0 for name in names
            )
            section = matrix.candidate_slice(candidate)
            demands = matrix.demand_index[section]
            marginal = np.maximum(matrix.distance_reduction_m[section] - current[demands], 0.0)
            overall = float(np.dot(marginal, overall_weights[demands]))
            key = (*normalized, overall)
            if best_key is None:
                better = True
            else:
                better = False
                for value, reference in zip(key, best_key, strict=True):
                    if value > reference + 1e-9:
                        better = True
                        break
                    if value < reference - 1e-9:
                        break
            if better:
                best_candidate = candidate
                best_key = key
                best_values = values
        if best_candidate < 0 or best_key is None or max(best_values.values()) <= 1e-9:
            break
        selected.append(best_candidate)
        section = matrix.candidate_slice(best_candidate)
        demands = matrix.demand_index[section]
        current[demands] = np.maximum(current[demands], matrix.distance_reduction_m[section])
        squared = (candidate_x - candidate_x[best_candidate]) ** 2 + (
            candidate_y - candidate_y[best_candidate]
        ) ** 2
        available[squared < minimum_separation_m**2 - 1e-9] = False
        available[selected] = False
        trace.append(
            {
                "step": step + 1,
                "candidate_index": best_candidate,
                "candidate_id": matrix.candidate_ids[best_candidate],
                "marginal_objectives": best_values,
                "normalized_maximin_vector": list(best_key[:-1]),
                "marginal_overall_building_distance_m": best_key[-1],
                "stage_runtime_seconds": round(time.perf_counter() - step_started, 6),
            }
        )
    return selected, trace
