"""Time-aware city states and conservative incremental recomputation planning."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from backend.citygap_platform.ingestion.differential import FeatureChange

StateType = Literal["observed", "future", "scenario"]
StateLifecycle = Literal["draft", "validated", "current", "superseded", "archived"]


@dataclass(frozen=True, slots=True)
class UrbanStateDefinition:
    city_code: str
    state_key: str
    effective_date: date
    state_type: StateType
    plateau_version: str
    population_version: str | None = None
    facility_version: str | None = None
    transport_version: str | None = None
    network_version: str | None = None
    base_state_key: str | None = None
    source_verified: bool = False
    fixed_service_assumption: bool = False

    def __post_init__(self) -> None:
        if len(self.city_code) != 5 or not self.city_code.isdigit():
            raise ValueError("Urban state requires a five-digit municipality code")
        if not self.state_key.strip() or not self.plateau_version.strip():
            raise ValueError("Urban state requires explicit state and PLATEAU versions")
        if self.state_type != "observed" and not self.base_state_key:
            raise ValueError("Future/scenario urban states require a base observed state")
        if self.state_type == "future" and not self.population_version:
            raise ValueError("Future urban state requires an official population version")


class DependencyGraph:
    """Small deterministic DAG used to identify downstream recomputation products."""

    def __init__(self, edges: Iterable[tuple[str, str]]) -> None:
        downstream: dict[str, set[str]] = defaultdict(set)
        indegree: dict[str, int] = defaultdict(int)
        for source, target in edges:
            if source == target or target in downstream[source]:
                raise ValueError("Dependency graph edges must be unique and non-reflexive")
            downstream[source].add(target)
            indegree[target] += 1
            indegree.setdefault(source, 0)
        queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for target in sorted(downstream[node]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if visited != len(indegree):
            raise ValueError("Dependency graph must be acyclic")
        self._downstream = {key: frozenset(value) for key, value in downstream.items()}

    def impacted_products(self, changed_inputs: Iterable[str]) -> tuple[str, ...]:
        pending = deque(sorted(set(changed_inputs)))
        impacted: set[str] = set()
        while pending:
            source = pending.popleft()
            for target in sorted(self._downstream.get(source, ())):
                if target not in impacted:
                    impacted.add(target)
                    pending.append(target)
        return tuple(sorted(impacted))


DEFAULT_DEPENDENCY_GRAPH = DependencyGraph(
    (
        ("Building", "building_demographics"),
        ("building_demographics", "mesh_metrics"),
        ("mesh_metrics", "city_gap"),
        ("Road", "road_graph"),
        ("road_graph", "network_accessibility"),
        ("network_accessibility", "city_gap"),
        ("network_accessibility", "scenario_results"),
        ("Facility", "network_accessibility"),
        ("Population", "building_demographics"),
        ("LandUse", "spatial_context"),
        ("UrbanPlanning", "spatial_context"),
        ("Hazard", "spatial_context"),
        ("spatial_context", "scenario_results"),
        ("city_gap", "scenario_results"),
        ("scenario_results", "evidence"),
    )
)


@dataclass(frozen=True, slots=True)
class FeatureScope:
    mesh_codes: tuple[str, ...] = ()
    network_component_ids: tuple[str, ...] = ()
    network_region_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecomputeScope:
    analysis_type: str
    scope_type: Literal["building", "mesh", "network_component", "network_region", "city"]
    scope_key: str
    rationale: str


def plan_incremental_recomputation(
    changes: Iterable[FeatureChange],
    feature_scopes: Mapping[str, FeatureScope],
) -> tuple[RecomputeScope, ...]:
    """Return bounded scopes, falling back to city scope when locality is not proven."""

    result: set[RecomputeScope] = set()
    for change in changes:
        if change.change_type == "unchanged":
            continue
        scope = feature_scopes.get(change.gml_id, FeatureScope())
        impacted = DEFAULT_DEPENDENCY_GRAPH.impacted_products((change.feature_type,))
        if change.feature_type == "Building":
            result.add(
                RecomputeScope(
                    "building_demographics",
                    "building",
                    change.gml_id,
                    "changed building identity/geometry/important attributes",
                )
            )
            for mesh_code in scope.mesh_codes:
                result.add(
                    RecomputeScope(
                        "mesh_metrics",
                        "mesh",
                        mesh_code,
                        "mesh intersects a changed building",
                    )
                )
        elif change.feature_type == "Road" and scope.network_component_ids:
            for component_id in scope.network_component_ids:
                for analysis in ("road_graph", "network_accessibility", "scenario_results"):
                    result.add(
                        RecomputeScope(
                            analysis,
                            "network_component",
                            component_id,
                            "road change is bounded to a known graph component",
                        )
                    )
        elif change.feature_type == "Facility" and scope.network_region_ids:
            for region_id in scope.network_region_ids:
                result.add(
                    RecomputeScope(
                        "network_accessibility",
                        "network_region",
                        region_id,
                        "facility change is bounded by a proven network search region",
                    )
                )
        else:
            for analysis in impacted:
                result.add(
                    RecomputeScope(
                        analysis,
                        "city",
                        "all",
                        "local correctness boundary unavailable; conservative full-city scope",
                    )
                )
    return tuple(sorted(result, key=lambda row: (row.analysis_type, row.scope_type, row.scope_key)))


def canonical_result_hash(rows: Iterable[Mapping[str, Any]]) -> str:
    ordered = sorted(
        (dict(row) for row in rows),
        key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, default=str),
    )
    payload = json.dumps(
        ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def incremental_matches_full(
    incremental_rows: Iterable[Mapping[str, Any]], full_rebuild_rows: Iterable[Mapping[str, Any]]
) -> bool:
    return canonical_result_hash(incremental_rows) == canonical_result_hash(full_rebuild_rows)
