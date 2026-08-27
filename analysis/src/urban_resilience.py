"""Deterministic network disruption, continuity, criticality and redundancy analysis.

The graph may be the current experimental PLATEAU road-surface adjacency model. None
of these functions relabels it as a validated pedestrian network. Hazard overlap is
converted into closures only through an explicit counterfactual assumption.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

ServiceCategory = Literal[
    "medical", "emergency", "evacuation", "administrative", "transport_hub"
]


@dataclass(frozen=True, slots=True)
class NetworkEdge:
    edge_id: str
    source: str
    target: str
    length_m: float

    def __post_init__(self) -> None:
        if not self.edge_id or not self.source or not self.target or self.source == self.target:
            raise ValueError("Network edge requires distinct source/target identifiers")
        if not math.isfinite(self.length_m) or self.length_m <= 0:
            raise ValueError("Network edge length must be finite and positive")


@dataclass(frozen=True, slots=True)
class BuildingDemand:
    building_id: str
    node_id: str
    connector_m: float
    estimated_population: float
    estimated_elderly_population: float
    baseline_distances_m: Mapping[ServiceCategory, float | None]

    def __post_init__(self) -> None:
        values = (
            self.connector_m,
            self.estimated_population,
            self.estimated_elderly_population,
        )
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Building demand values must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class HazardClosureAssumption:
    hazard_dataset_version: str
    hazard_type: str
    hazard_classes: tuple[str, ...]
    rule: Literal["overlap_edges_unavailable"]
    assumption_source: str
    explicitly_confirmed: bool

    def __post_init__(self) -> None:
        if not self.explicitly_confirmed:
            raise ValueError("Hazard closure requires an explicit counterfactual assumption")
        if not all(
            (
                self.hazard_dataset_version.strip(),
                self.hazard_type.strip(),
                self.hazard_classes,
                self.assumption_source.strip(),
            )
        ):
            raise ValueError("Hazard assumption provenance and classes are required")

    @property
    def limitation(self) -> str:
        return "This is a counterfactual stress test, not a prediction of road passability."

    def canonical_payload(self) -> dict[str, object]:
        return {
            "hazard_dataset_version": self.hazard_dataset_version,
            "hazard_type": self.hazard_type,
            "hazard_classes": sorted(self.hazard_classes),
            "rule": self.rule,
            "assumption_source": self.assumption_source,
            "explicitly_confirmed": self.explicitly_confirmed,
            "limitation": self.limitation,
        }


@dataclass(frozen=True, slots=True)
class ServiceChange:
    facility_id: str
    category: ServiceCategory
    action: Literal["open", "close", "relocate", "temporary_unavailable"]
    user_supplied: bool
    from_node_id: str | None = None
    to_node_id: str | None = None
    connector_m: float = 0.0

    def __post_init__(self) -> None:
        if not self.user_supplied:
            raise ValueError("Service changes are user-input scenarios only")
        if self.action in {"open", "relocate"} and not self.to_node_id:
            raise ValueError("Opening/relocating a service requires a destination node")
        if self.action in {"close", "temporary_unavailable", "relocate"} and not self.from_node_id:
            raise ValueError("Closing/relocating a service requires the existing node")
        if not math.isfinite(self.connector_m) or self.connector_m < 0:
            raise ValueError("Service connector must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class PathResult:
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    distance_m: float


@dataclass(frozen=True, slots=True)
class CriticalityCandidate:
    edge_id: str
    source: str
    target: str
    component_id: int
    isolated_node_count: int
    affected_buildings: int
    affected_estimated_elderly_population: float
    service_reachability_change: Mapping[str, int]
    algorithm: str = "tarjan_bridge_subtree_demand_v1"


@dataclass(frozen=True, slots=True)
class StressTestResult:
    closed_edge_count: int
    baseline_component_count: int
    scenario_component_count: int
    largest_component_nodes: int
    component_fragmentation_increase: int
    service_metrics: Mapping[str, Mapping[str, float | int]]


def _adjacency(
    edges: Iterable[NetworkEdge], closed_edge_ids: frozenset[str] = frozenset()
) -> tuple[dict[str, list[tuple[str, float, str]]], dict[str, NetworkEdge]]:
    adjacency: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
    by_id: dict[str, NetworkEdge] = {}
    for edge in edges:
        if edge.edge_id in by_id:
            raise ValueError(f"Duplicate network edge id: {edge.edge_id}")
        by_id[edge.edge_id] = edge
        adjacency.setdefault(edge.source, [])
        adjacency.setdefault(edge.target, [])
        if edge.edge_id not in closed_edge_ids:
            adjacency[edge.source].append((edge.target, edge.length_m, edge.edge_id))
            adjacency[edge.target].append((edge.source, edge.length_m, edge.edge_id))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda row: (row[0], row[2]))
    return dict(adjacency), by_id


def multi_source_distances(
    edges: Iterable[NetworkEdge],
    seeds: Mapping[str, float],
    closed_edge_ids: frozenset[str] = frozenset(),
) -> dict[str, float]:
    adjacency, _ = _adjacency(edges, closed_edge_ids)
    distances = {node_id: math.inf for node_id in adjacency}
    queue: list[tuple[float, str]] = []
    for node_id, initial_distance in sorted(seeds.items()):
        if node_id not in adjacency:
            continue
        if not math.isfinite(initial_distance) or initial_distance < 0:
            raise ValueError("Service seed distances must be finite and non-negative")
        if initial_distance < distances[node_id]:
            distances[node_id] = initial_distance
            heapq.heappush(queue, (initial_distance, node_id))
    while queue:
        distance, node_id = heapq.heappop(queue)
        if distance != distances[node_id]:
            continue
        for neighbor, edge_length, _edge_id in adjacency[node_id]:
            candidate = distance + edge_length
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    return distances


def _component_summary(
    edges: Iterable[NetworkEdge], closed_edge_ids: frozenset[str]
) -> tuple[int, int, dict[str, int]]:
    adjacency, _ = _adjacency(edges, closed_edge_ids)
    component_by_node: dict[str, int] = {}
    sizes: list[int] = []
    for start in sorted(adjacency):
        if start in component_by_node:
            continue
        component_id = len(sizes)
        pending = [start]
        component_by_node[start] = component_id
        size = 0
        while pending:
            node_id = pending.pop()
            size += 1
            for neighbor, _weight, _edge_id in adjacency[node_id]:
                if neighbor not in component_by_node:
                    component_by_node[neighbor] = component_id
                    pending.append(neighbor)
        sizes.append(size)
    return len(sizes), max(sizes, default=0), component_by_node


def apply_service_changes(
    seeds: Mapping[ServiceCategory, Mapping[str, float]], changes: Iterable[ServiceChange]
) -> dict[ServiceCategory, dict[str, float]]:
    result = {category: dict(rows) for category, rows in seeds.items()}
    for change in changes:
        category_seeds = result.setdefault(change.category, {})
        if change.action in {"close", "temporary_unavailable", "relocate"}:
            category_seeds.pop(change.from_node_id or "", None)
        if change.action in {"open", "relocate"}:
            category_seeds[change.to_node_id or ""] = change.connector_m
    return result


def run_network_stress_test(
    edges: Iterable[NetworkEdge],
    buildings: Iterable[BuildingDemand],
    service_seeds: Mapping[ServiceCategory, Mapping[str, float]],
    closed_edge_ids: frozenset[str],
) -> StressTestResult:
    edge_rows = tuple(edges)
    building_rows = tuple(buildings)
    known_edges = {edge.edge_id for edge in edge_rows}
    unknown = closed_edge_ids - known_edges
    if unknown:
        raise ValueError(f"Stress test references unknown edges: {sorted(unknown)[:3]}")
    baseline_components, _baseline_largest, _ = _component_summary(edge_rows, frozenset())
    scenario_components, scenario_largest, _ = _component_summary(edge_rows, closed_edge_ids)
    service_metrics: dict[str, dict[str, float | int]] = {}
    for category, seeds in sorted(service_seeds.items()):
        scenario_distances = multi_source_distances(edge_rows, seeds, closed_edge_ids)
        baseline_reachable = 0
        scenario_reachable = 0
        newly_disconnected = 0
        disconnected_population = 0.0
        disconnected_elderly = 0.0
        increases: list[float] = []
        for building in building_rows:
            baseline = building.baseline_distances_m.get(category)
            before_reachable = baseline is not None and math.isfinite(baseline)
            after_node = scenario_distances.get(building.node_id, math.inf)
            after = after_node + building.connector_m
            after_reachable = math.isfinite(after)
            baseline_reachable += int(before_reachable)
            scenario_reachable += int(after_reachable)
            if before_reachable and not after_reachable:
                newly_disconnected += 1
                disconnected_population += building.estimated_population
                disconnected_elderly += building.estimated_elderly_population
            elif before_reachable and after_reachable and baseline is not None:
                increases.append(max(0.0, after - baseline))
        service_metrics[category] = {
            "baseline_reachable_buildings": baseline_reachable,
            "scenario_reachable_buildings": scenario_reachable,
            "newly_unreachable_buildings": newly_disconnected,
            "estimated_population_disconnected": disconnected_population,
            "estimated_elderly_population_disconnected": disconnected_elderly,
            "mean_network_distance_increase_m": (
                sum(increases) / len(increases) if increases else 0.0
            ),
            "maximum_network_distance_increase_m": max(increases, default=0.0),
            "critical_facility_seed_count": len(seeds),
        }
    return StressTestResult(
        closed_edge_count=len(closed_edge_ids),
        baseline_component_count=baseline_components,
        scenario_component_count=scenario_components,
        largest_component_nodes=scenario_largest,
        component_fragmentation_increase=scenario_components - baseline_components,
        service_metrics=service_metrics,
    )


def network_criticality_candidates(
    edges: Iterable[NetworkEdge],
    buildings: Iterable[BuildingDemand],
    service_seeds: Mapping[ServiceCategory, Mapping[str, float]],
) -> tuple[CriticalityCandidate, ...]:
    """Find bridge candidates and aggregate demand without edges × full-city routing."""

    edge_rows = tuple(edges)
    building_rows = tuple(buildings)
    adjacency, by_id = _adjacency(edge_rows)
    demand_count: dict[str, int] = defaultdict(int)
    elderly: dict[str, float] = defaultdict(float)
    for building in building_rows:
        demand_count[building.node_id] += 1
        elderly[building.node_id] += building.estimated_elderly_population
    categories = tuple(sorted(service_seeds))
    seed_count: dict[str, dict[str, int]] = {
        category: defaultdict(int) for category in categories
    }
    for category, seeds in service_seeds.items():
        for node_id in seeds:
            seed_count[category][node_id] += 1

    component_by_node: dict[str, int] = {}
    component_nodes: dict[int, list[str]] = {}
    for start in sorted(adjacency):
        if start in component_by_node:
            continue
        component_id = len(component_nodes)
        pending = [start]
        component_by_node[start] = component_id
        nodes: list[str] = []
        while pending:
            node = pending.pop()
            nodes.append(node)
            for neighbor, _weight, _edge_id in adjacency[node]:
                if neighbor not in component_by_node:
                    component_by_node[neighbor] = component_id
                    pending.append(neighbor)
        component_nodes[component_id] = nodes

    component_totals: dict[int, dict[str, object]] = {}
    for component_id, nodes in component_nodes.items():
        component_totals[component_id] = {
            "nodes": len(nodes),
            "buildings": sum(demand_count[node] for node in nodes),
            "elderly": sum(elderly[node] for node in nodes),
            "seeds": {
                category: sum(seed_count[category][node] for node in nodes)
                for category in categories
            },
        }

    timer = 0
    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    subtree_nodes: dict[str, int] = {}
    subtree_buildings: dict[str, int] = {}
    subtree_elderly: dict[str, float] = {}
    subtree_seeds: dict[str, dict[str, int]] = {}
    candidates: list[CriticalityCandidate] = []

    def initialize(node: str) -> None:
        nonlocal timer
        discovery[node] = timer
        low[node] = timer
        timer += 1
        subtree_nodes[node] = 1
        subtree_buildings[node] = demand_count[node]
        subtree_elderly[node] = elderly[node]
        subtree_seeds[node] = {
            category: seed_count[category][node] for category in categories
        }

    def record_bridge(child: str, edge_id: str, component_id: int) -> None:
        total = component_totals[component_id]
        side_buildings = subtree_buildings[child]
        other_buildings = int(total["buildings"]) - side_buildings
        side_elderly = subtree_elderly[child]
        other_elderly = float(total["elderly"]) - side_elderly
        service_change: dict[str, int] = {}
        affected_counts: list[int] = []
        affected_elderly: list[float] = []
        total_seeds = total["seeds"]
        assert isinstance(total_seeds, dict)
        for category in categories:
            side_seed_count = subtree_seeds[child][category]
            other_seed_count = int(total_seeds[category]) - side_seed_count
            affected = 0
            elderly_affected = 0.0
            if side_seed_count == 0 < other_seed_count:
                affected = side_buildings
                elderly_affected = side_elderly
            elif other_seed_count == 0 < side_seed_count:
                affected = other_buildings
                elderly_affected = other_elderly
            service_change[category] = affected
            affected_counts.append(affected)
            affected_elderly.append(elderly_affected)
        isolated_nodes = min(subtree_nodes[child], int(total["nodes"]) - subtree_nodes[child])
        bridge = by_id[edge_id]
        candidates.append(
            CriticalityCandidate(
                edge_id=edge_id,
                source=bridge.source,
                target=bridge.target,
                component_id=component_id,
                isolated_node_count=isolated_nodes,
                affected_buildings=max(affected_counts, default=0),
                affected_estimated_elderly_population=max(affected_elderly, default=0.0),
                service_reachability_change=service_change,
            )
        )

    # Iterative Tarjan DFS avoids Python recursion depth and C-stack limits on the
    # 50k+ node Fujisawa graph. Stack rows are node, parent node/edge, next neighbor.
    for start in sorted(adjacency):
        if start in discovery:
            continue
        component_id = component_by_node[start]
        initialize(start)
        stack: list[tuple[str, str | None, str | None, int]] = [(start, None, None, 0)]
        while stack:
            node, parent, parent_edge_id, next_index = stack[-1]
            if next_index < len(adjacency[node]):
                neighbor, _weight, edge_id = adjacency[node][next_index]
                stack[-1] = (node, parent, parent_edge_id, next_index + 1)
                if edge_id == parent_edge_id:
                    continue
                if neighbor not in discovery:
                    initialize(neighbor)
                    stack.append((neighbor, node, edge_id, 0))
                else:
                    low[node] = min(low[node], discovery[neighbor])
                continue
            stack.pop()
            if parent is None or parent_edge_id is None:
                continue
            subtree_nodes[parent] += subtree_nodes[node]
            subtree_buildings[parent] += subtree_buildings[node]
            subtree_elderly[parent] += subtree_elderly[node]
            for category in categories:
                subtree_seeds[parent][category] += subtree_seeds[node][category]
            low[parent] = min(low[parent], low[node])
            if low[node] > discovery[parent]:
                record_bridge(node, parent_edge_id, component_id)
    return tuple(
        sorted(
            candidates,
            key=lambda row: (
                -row.affected_buildings,
                -row.affected_estimated_elderly_population,
                -row.isolated_node_count,
                row.edge_id,
            ),
        )
    )


def _shortest_path(
    adjacency: Mapping[str, list[tuple[str, float, str]]],
    source: str,
    target: str,
    banned_edge_ids: frozenset[str] = frozenset(),
    banned_node_ids: frozenset[str] = frozenset(),
) -> PathResult | None:
    if source in banned_node_ids or target in banned_node_ids:
        return None
    distances = {source: 0.0}
    previous: dict[str, tuple[str, str]] = {}
    queue = [(0.0, source)]
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == target:
            break
        for neighbor, weight, edge_id in adjacency.get(node, []):
            if edge_id in banned_edge_ids or neighbor in banned_node_ids:
                continue
            candidate = distance + weight
            if candidate < distances.get(neighbor, math.inf):
                distances[neighbor] = candidate
                previous[neighbor] = (node, edge_id)
                heapq.heappush(queue, (candidate, neighbor))
    if target not in distances:
        return None
    nodes = [target]
    edge_ids: list[str] = []
    while nodes[-1] != source:
        parent, edge_id = previous[nodes[-1]]
        nodes.append(parent)
        edge_ids.append(edge_id)
    nodes.reverse()
    edge_ids.reverse()
    return PathResult(tuple(nodes), tuple(edge_ids), distances[target])


def k_shortest_paths(
    edges: Iterable[NetworkEdge], source: str, target: str, k: int = 2
) -> tuple[PathResult, ...]:
    """Yen-style loopless paths for selected origin/destination pairs only."""

    if k < 1 or k > 10:
        raise ValueError("k must be between 1 and 10")
    adjacency, by_id = _adjacency(edges)
    first = _shortest_path(adjacency, source, target)
    if first is None:
        return ()
    accepted = [first]
    candidate_heap: list[tuple[float, tuple[str, ...], tuple[str, ...]]] = []
    candidate_keys: set[tuple[str, ...]] = set()
    for path_index in range(1, k):
        previous_path = accepted[path_index - 1]
        for spur_index in range(len(previous_path.node_ids) - 1):
            root_nodes = previous_path.node_ids[: spur_index + 1]
            root_edges = previous_path.edge_ids[:spur_index]
            banned_edges = {
                path.edge_ids[spur_index]
                for path in accepted
                if len(path.node_ids) > spur_index
                and path.node_ids[: spur_index + 1] == root_nodes
            }
            spur = _shortest_path(
                adjacency,
                root_nodes[-1],
                target,
                frozenset(banned_edges),
                frozenset(root_nodes[:-1]),
            )
            if spur is None:
                continue
            combined_nodes = root_nodes[:-1] + spur.node_ids
            combined_edges = root_edges + spur.edge_ids
            if combined_edges in candidate_keys:
                continue
            root_distance = sum(by_id[edge_id].length_m for edge_id in root_edges)
            distance = root_distance + spur.distance_m
            heapq.heappush(candidate_heap, (distance, combined_nodes, combined_edges))
            candidate_keys.add(combined_edges)
        if not candidate_heap:
            break
        distance, nodes, edge_ids = heapq.heappop(candidate_heap)
        accepted.append(PathResult(nodes, edge_ids, distance))
    return tuple(accepted)


def verify_bridge_by_removal(edges: Iterable[NetworkEdge], edge_id: str) -> bool:
    """Independent selected-case verifier using component recount after one removal."""

    rows = tuple(edges)
    if edge_id not in {edge.edge_id for edge in rows}:
        raise ValueError("Unknown edge")
    before, _largest, _mapping = _component_summary(rows, frozenset())
    after, _largest, _mapping = _component_summary(rows, frozenset({edge_id}))
    return after == before + 1


def stress_test_cache_key(
    city_code: str,
    urban_state_id: str,
    network_version: str,
    assumption_payload: Mapping[str, object],
    algorithm_version: str,
) -> str:
    payload = json.dumps(
        {
            "city": city_code,
            "urban_state": urban_state_id,
            "network_version": network_version,
            "assumption": assumption_payload,
            "algorithm_version": algorithm_version,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()
