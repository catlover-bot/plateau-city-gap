"""Build N-site, road-network-aware municipal scenario alternatives."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - unavailable on Windows.
    resource = None  # type: ignore[assignment]

import numpy as np
import pandas as pd
from shapely import from_wkb

from analysis.scripts.build_decision_studio_assets import _candidate_pool
from analysis.src.network_scenario import (
    CandidateGainMatrix,
    balanced_greedy_select,
    build_candidate_gain_matrix,
    evaluate_selected,
    greedy_select,
)
from analysis.src.plateau_road_network import reconstruct_route

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real"
NODES = OUTPUT / "maizuru_road_graph_nodes.parquet"
TERRAIN_NODES = OUTPUT / "maizuru_road_graph_nodes_terrain.parquet"
TERRAIN_EDGES = OUTPUT / "maizuru_road_graph_edges_terrain.parquet"
EDGES = OUTPUT / "maizuru_road_graph_edges.parquet"
BUILDING_NETWORK = OUTPUT / "maizuru_building_network_accessibility.parquet"
BUILDING_DEMOGRAPHICS = OUTPUT / "maizuru_building_demographics.parquet"
CANDIDATE_CONTEXT = OUTPUT / "maizuru_scenario_candidate_context.csv"
ROBUSTNESS = OUTPUT / "maizuru_robustness.json"
TRANSPORT_LABELS = OUTPUT / "maizuru_transport_network_labels.parquet"
GAINS = OUTPUT / "maizuru_network_scenario_candidate_gains.parquet"
RESULT = OUTPUT / "maizuru_network_scenarios.json"
SUMMARY = OUTPUT / "maizuru_network_scenario_summary.csv"
PERFORMANCE = OUTPUT / "maizuru_network_scenario_performance.json"
WEB_RESULT = ROOT / "frontend/public/data/network_scenario_story.json"
MINIMUM_SEPARATION_M = 1_500.0
LONG_CONNECTOR_ATTENTION_M = 50.0
TERRAIN_GRADE_ATTENTION_PERCENT = 10.0


def _peak_rss_kib() -> int | None:
    """Return the OS-reported process peak, or null when the OS exposes no equivalent."""

    if resource is None:
        return None
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


ALGORITHM_VERSION = "network-scenario-1.0.0"

MODE_DEFINITIONS = {
    "overall": {
        "label": "建物全体の改善",
        "objective": "maximize sum of network-distance reduction across reachable buildings",
        "weight": "building_count",
    },
    "elderly": {
        "label": "高齢者加重の改善",
        "objective": "maximize elderly-estimate-weighted network-distance reduction",
        "weight": "elderly_population",
    },
    "worst_served": {
        "label": "取り残し重視",
        "objective": "maximize reduction for buildings in the worst baseline network-distance decile",
        "weight": "worst_served_building_count",
    },
    "robust": {
        "label": "頑健候補重視",
        "objective": "maximize elderly-weighted reduction in Robust Top 20 meshes",
        "weight": "robust_elderly_population",
    },
    "balanced": {
        "label": "バランス案",
        "objective": (
            "greedy max-min compromise across separately normalized overall, elderly, "
            "worst-served and robust marginal objectives; no weighted composite score"
        ),
        "weight": None,
    },
    "reachability": {
        "label": "未到達component重視",
        "objective": (
            "lexicographically maximize newly network-connected buildings, then overall "
            "building distance reduction"
        ),
        "weight": "building_count",
        "supplemental_diagnostic": True,
    },
}


def _generated_at() -> str:
    epoch = os.getenv("SOURCE_DATE_EPOCH")
    value = (
        datetime.fromtimestamp(int(epoch), tz=timezone.utc) if epoch else datetime.now(timezone.utc)
    )
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    options: dict[str, Any] = {"ensure_ascii": False}
    if compact:
        options["separators"] = (",", ":")
    else:
        options["indent"] = 2
    path.write_text(json.dumps(value, **options) + "\n", encoding="utf-8")


def _public_story(report: dict[str, Any]) -> dict[str, Any]:
    """Keep the public demo to two reviewed story alternatives, not the platform corpus."""

    stories = []
    for story_id, mode in (("scenario_a", "overall"), ("scenario_b", "worst_served")):
        plan = {
            key: value for key, value in report["plans"][mode]["3"].items() if key != "mesh_results"
        }
        stories.append({"story_id": story_id, **plan})
    return {
        "schema_version": report["schema_version"],
        "generated_at": report["generated_at"],
        "city": report["city"],
        "source": "selected static subset of maizuru_network_scenarios.json",
        "scenario_story": stories,
        "context_policy": report["context_policy"],
        "limitations": report["limitations"],
    }


def _clean(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    set[str],
]:
    nodes = pd.read_parquet(NODES)
    terrain_nodes = pd.read_parquet(TERRAIN_NODES)[
        ["node_id", "elevation_m", "terrain_source_member", "terrain_source_member_crc32"]
    ]
    nodes = nodes.merge(terrain_nodes, on="node_id", how="left", validate="one_to_one")
    node_geometry = from_wkb(nodes.geometry.to_numpy())
    nodes["graph_x"] = np.asarray([geometry.x for geometry in node_geometry])
    nodes["graph_y"] = np.asarray([geometry.y for geometry in node_geometry])
    terrain_edges = pd.read_parquet(TERRAIN_EDGES)
    incident_grade = pd.concat(
        [
            terrain_edges[["source_node_id", "absolute_grade_percent"]].rename(
                columns={"source_node_id": "node_id"}
            ),
            terrain_edges[["target_node_id", "absolute_grade_percent"]].rename(
                columns={"target_node_id": "node_id"}
            ),
        ],
        ignore_index=True,
    )
    maximum_incident_grade = (
        incident_grade.groupby("node_id", as_index=False)
        .absolute_grade_percent.max()
        .rename(columns={"absolute_grade_percent": "maximum_incident_grade_percent"})
    )
    nodes = nodes.merge(maximum_incident_grade, on="node_id", how="left", validate="one_to_one")
    edges = pd.read_parquet(EDGES)
    network = pd.read_parquet(BUILDING_NETWORK)
    demographics = pd.read_parquet(BUILDING_DEMOGRAPHICS)
    context = pd.read_csv(CANDIDATE_CONTEXT)
    pool, _ = _candidate_pool()
    pool = pool.rename(columns={"road_id": "candidate_id"})
    candidates = context.merge(
        pool[["candidate_id", "road_name", "existing_transport_distance_m"]],
        on="candidate_id",
        how="left",
        validate="one_to_one",
    )
    surface_parts = candidates.candidate_id.astype(str).str.rsplit("-", n=1, expand=True)
    if surface_parts.shape[1] != 2 or not surface_parts[1].str.fullmatch(r"\d+").all():
        raise ValueError("Candidate IDs must end with the explicit road surface index")
    candidates["surface_id"] = surface_parts[0] + ":" + surface_parts[1]
    candidates = candidates.merge(
        nodes[
            [
                "surface_id",
                "gml_id",
                "node_id",
                "component_id",
                "name",
                "source_member",
                "source_member_crc32",
                "graph_x",
                "graph_y",
                "maximum_incident_grade_percent",
                "elevation_m",
                "terrain_source_member",
                "terrain_source_member_crc32",
            ]
        ].rename(columns={"gml_id": "road_gml_id", "name": "plateau_road_name"}),
        on="surface_id",
        how="left",
        validate="one_to_one",
    )
    if candidates.node_id.isna().any():
        raise ValueError("Every screened scenario candidate must map to a graph node")
    candidates["candidate_to_graph_connector_m"] = np.hypot(
        candidates.candidate_x - candidates.graph_x,
        candidates.candidate_y - candidates.graph_y,
    )
    largest_component = str(nodes.component_id.value_counts().index[0])
    candidates["is_largest_network_component"] = candidates.component_id.astype(str).eq(
        largest_component
    )
    robustness = json.loads(ROBUSTNESS.read_text(encoding="utf-8"))
    robust_meshes = {str(row["mesh_code"]) for row in robustness["top_candidates"][:20]}
    return nodes, edges, network, demographics, candidates, pool, robust_meshes


def _demand_tables(
    nodes: pd.DataFrame,
    network: pd.DataFrame,
    demographics: pd.DataFrame,
    robust_meshes: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, float]]:
    building_network = network.merge(
        demographics.groupby("gml_id", as_index=False).agg(
            estimated_population=("estimated_population", "sum"),
            estimated_elderly_population=("estimated_elderly_population", "sum"),
        ),
        on="gml_id",
        how="left",
        validate="one_to_one",
    )
    finite = building_network.nearest_network_transport_distance_m.notna()
    worst_count = max(1, math.ceil(int(finite.sum()) * 0.1))
    worst_ids = set(
        building_network.loc[finite]
        .sort_values(
            ["nearest_network_transport_distance_m", "gml_id"],
            ascending=[False, True],
        )
        .head(worst_count)
        .gml_id
    )
    building_network["worst_served"] = building_network.gml_id.isin(worst_ids)

    fragments = demographics.merge(
        network[
            [
                "gml_id",
                "node_id",
                "origin_to_node_distance_m",
                "network_to_transport_from_node_m",
                "nearest_network_transport_distance_m",
            ]
        ],
        on="gml_id",
        validate="many_to_one",
    )
    fragments["robust_mesh"] = fragments.mesh_code.astype(str).isin(robust_meshes)
    building_weights = building_network[
        [
            "gml_id",
            "node_id",
            "estimated_population",
            "estimated_elderly_population",
            "worst_served",
            "network_to_transport_from_node_m",
        ]
    ].copy()
    building_weights["worst_served_building_count"] = building_weights.worst_served.astype(int)
    robust_elderly = (
        fragments.loc[fragments.robust_mesh]
        .groupby("node_id", as_index=False)
        .estimated_elderly_population.sum()
        .rename(columns={"estimated_elderly_population": "robust_elderly_population"})
    )
    demand = (
        building_weights.groupby("node_id", as_index=False)
        .agg(
            baseline_graph_distance_m=("network_to_transport_from_node_m", "first"),
            building_count=("gml_id", "nunique"),
            population=("estimated_population", "sum"),
            elderly_population=("estimated_elderly_population", "sum"),
            worst_served_building_count=("worst_served_building_count", "sum"),
        )
        .merge(robust_elderly, on="node_id", how="left")
    )
    demand["robust_elderly_population"] = demand.robust_elderly_population.fillna(0.0)
    finite_demand = demand.loc[demand.baseline_graph_distance_m.notna()].copy()

    node_components = nodes.set_index("node_id").component_id.astype(str)
    unreachable = building_network.loc[
        building_network.network_to_transport_from_node_m.isna()
    ].copy()
    unreachable["component_id"] = unreachable.node_id.map(node_components)
    unreachable_weights = (
        unreachable.groupby("component_id").gml_id.nunique().astype(float).to_dict()
    )
    return finite_demand, building_network, fragments, unreachable_weights


def _gain_frame(matrix: CandidateGainMatrix) -> pd.DataFrame:
    candidate_ids = np.asarray(matrix.candidate_ids, dtype=object)
    demand_ids = np.asarray(matrix.demand_node_ids, dtype=object)
    return pd.DataFrame(
        {
            "candidate_id": candidate_ids[matrix.candidate_index],
            "demand_node_id": demand_ids[matrix.demand_index],
            "network_distance_m": matrix.network_distance_m,
            "distance_reduction_m": matrix.distance_reduction_m,
        }
    )


def _mesh_results(
    fragments: pd.DataFrame,
    demand_reduction: dict[str, float],
) -> dict[str, dict[str, Any]]:
    work = fragments.loc[fragments.nearest_network_transport_distance_m.notna()].copy()
    work["distance_reduction_m"] = work.node_id.map(demand_reduction).fillna(0.0)
    work["after_network_distance_m"] = (
        work.nearest_network_transport_distance_m - work.distance_reduction_m
    )
    results: dict[str, dict[str, Any]] = {}
    for mesh_code, group in work.groupby(work.mesh_code.astype(str)):
        population = group.estimated_population.to_numpy(float)
        weight_total = float(population.sum())
        weights = population if weight_total > 0 else np.ones(len(group), dtype=float)
        baseline = float(
            np.average(group.nearest_network_transport_distance_m.to_numpy(float), weights=weights)
        )
        after = float(np.average(group.after_network_distance_m.to_numpy(float), weights=weights))
        improved = group.distance_reduction_m.gt(1e-9)
        results[str(mesh_code)] = {
            "baseline_population_weighted_network_distance_m": round(baseline, 3),
            "after_population_weighted_network_distance_m": round(after, 3),
            "population_weighted_reduction_m": round(baseline - after, 3),
            "improved_building_fragment_count": int(improved.sum()),
            "affected_estimated_elderly_population": round(
                float(group.loc[improved, "estimated_elderly_population"].sum()), 6
            ),
        }
    return results


def _impact(
    demand: pd.DataFrame,
    reduction: np.ndarray,
    fragments: pd.DataFrame,
    robust_meshes: set[str],
    newly_reachable_buildings: int,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    indexed = demand.sort_values("node_id").reset_index(drop=True)
    if tuple(indexed.node_id.astype(str)) == ():
        raise ValueError("No finite network demand")
    improved = reduction > 1e-9
    building_count = indexed.building_count.to_numpy(float)
    elderly = indexed.elderly_population.to_numpy(float)
    worst = indexed.worst_served_building_count.to_numpy(float)
    robust = indexed.robust_elderly_population.to_numpy(float)
    total_building_reduction = float(np.dot(reduction, building_count))
    mesh_results = _mesh_results(fragments, dict(zip(indexed.node_id, reduction, strict=True)))
    robust_improved = sum(
        mesh_results.get(mesh, {}).get("population_weighted_reduction_m", 0) > 0
        for mesh in robust_meshes
    )
    improved_buildings = int(building_count[improved].sum())
    impact = {
        "affected_graph_node_count": int(improved.sum()),
        "improved_building_count": improved_buildings,
        "newly_network_connected_building_count": newly_reachable_buildings,
        "total_building_distance_reduction_m": round(total_building_reduction, 3),
        "mean_reduction_all_reachable_buildings_m": round(
            total_building_reduction / building_count.sum(), 3
        ),
        "mean_reduction_improved_buildings_m": round(
            total_building_reduction / improved_buildings if improved_buildings else 0.0, 3
        ),
        "affected_estimated_elderly_population": round(float(elderly[improved].sum()), 6),
        "elderly_weighted_distance_reduction_person_m": round(float(np.dot(reduction, elderly)), 3),
        "elderly_weighted_mean_reduction_m": round(
            float(np.dot(reduction, elderly)) / elderly.sum() if elderly.sum() else 0.0,
            3,
        ),
        "worst_decile_mean_reduction_m": round(
            float(np.dot(reduction, worst)) / worst.sum() if worst.sum() else 0.0,
            3,
        ),
        "robust_top20_elderly_weighted_reduction_person_m": round(
            float(np.dot(reduction, robust)), 3
        ),
        "robust_top20_improved_mesh_count": int(robust_improved),
        "improved_mesh_count": sum(
            row["population_weighted_reduction_m"] > 0 for row in mesh_results.values()
        ),
    }
    return impact, mesh_results


def _site_record(candidate: pd.Series, order: int) -> dict[str, Any]:
    connector = float(candidate.candidate_to_graph_connector_m)
    maximum_grade = float(candidate.maximum_incident_grade_percent)
    planning_count = int(candidate.planning_feature_count)
    landuse_count = int(candidate.landuse_feature_count)
    hazard_overlap = bool(candidate.hazard_overlap)
    return {
        "site_order": order,
        "candidate_id": str(candidate.candidate_id),
        "node_id": str(candidate.node_id),
        "road_gml_id": str(candidate.road_gml_id),
        "road_surface_id": str(candidate.surface_id),
        "road_name": _clean(candidate.road_name) or _clean(candidate.plateau_road_name),
        "longitude": round(float(candidate.longitude), 9),
        "latitude": round(float(candidate.latitude), 9),
        "existing_transport_distance_m": round(float(candidate.existing_transport_distance_m), 3),
        "landuse_context": _clean(candidate.landuse_labels),
        "planning_context": _clean(candidate.planning_labels),
        "landuse_feature_count": landuse_count,
        "planning_feature_count": planning_count,
        "hazard_context": _clean(candidate.hazard_labels),
        "hazard_overlap": hazard_overlap,
        "hazard_review_status": str(candidate.hazard_review_status),
        "siting_feasibility": "not_determined",
        "component_id": str(candidate.component_id),
        "road_source": {
            "source_member": str(candidate.source_member),
            "source_member_crc32": str(candidate.source_member_crc32),
        },
        "candidate_to_graph_connector_m": round(connector, 9),
        "terrain": {
            "elevation_m": round(float(candidate.elevation_m), 3),
            "source_member": str(candidate.terrain_source_member),
            "source_member_crc32": str(candidate.terrain_source_member_crc32),
            "routing_penalty_applied": False,
            "maximum_incident_endpoint_grade_percent": round(maximum_grade, 3),
        },
        "feasibility_flags": {
            "hazard_attention": hazard_overlap,
            "planning_attention": planning_count > 0,
            "landuse_attention": True,
            "network_component_attention": not bool(candidate.is_largest_network_component),
            "long_connector_attention": connector > LONG_CONNECTOR_ATTENTION_M,
            "terrain_attention": (
                not math.isfinite(maximum_grade) or maximum_grade > TERRAIN_GRADE_ATTENTION_PERCENT
            ),
            "interpretation": "review prompts only; no flag is an automatic policy decision",
        },
    }


def _route_adjacency(edges: pd.DataFrame) -> dict[str, list[tuple[str, float, str]]]:
    adjacency: dict[str, list[tuple[str, float, str]]] = {}
    for row in edges.itertuples(index=False):
        source = str(row.source_node_id)
        target = str(row.target_node_id)
        edge_id = str(row.edge_id)
        weight = float(row.length_m)
        adjacency.setdefault(source, []).append((target, weight, edge_id))
        adjacency.setdefault(target, []).append((source, weight, edge_id))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[2]))
    return adjacency


def _shortest_route(
    adjacency: dict[str, list[tuple[str, float, str]]], source: str, target: str
) -> tuple[float, list[str], list[str]]:
    distance = {source: 0.0}
    predecessor: dict[str, tuple[str, str]] = {}
    queue = [(0.0, source)]
    while queue:
        current, node = heapq.heappop(queue)
        if current > distance[node] + 1e-9:
            continue
        if node == target:
            nodes = [target]
            edges = []
            while nodes[-1] != source:
                previous, edge_id = predecessor[nodes[-1]]
                edges.append(edge_id)
                nodes.append(previous)
            return current, list(reversed(nodes)), list(reversed(edges))
        for neighbor, weight, edge_id in adjacency.get(node, []):
            proposed = current + weight
            current_predecessor = predecessor.get(neighbor)
            candidate_predecessor = (node, edge_id)
            if proposed < distance.get(neighbor, math.inf) - 1e-9 or (
                abs(proposed - distance.get(neighbor, math.inf)) <= 1e-9
                and (current_predecessor is None or candidate_predecessor < current_predecessor)
            ):
                distance[neighbor] = proposed
                predecessor[neighbor] = candidate_predecessor
                heapq.heappush(queue, (proposed, neighbor))
    return math.inf, [], []


def _representative_evidence(
    building_network: pd.DataFrame,
    demographics: pd.DataFrame,
    matrix: CandidateGainMatrix,
    reduction: np.ndarray,
    assigned: np.ndarray,
    selected: list[int],
    ordered_candidates: pd.DataFrame,
    route_adjacency: dict[str, list[tuple[str, float, str]]],
    nodes: pd.DataFrame,
    terrain_edges: pd.DataFrame,
    transport_labels: pd.DataFrame,
) -> dict[str, Any] | None:
    reduction_by_node = dict(zip(matrix.demand_node_ids, reduction, strict=True))
    assignment_by_node = dict(zip(matrix.demand_node_ids, assigned, strict=True))
    work = building_network.copy()
    work["scenario_reduction_m"] = work.node_id.map(reduction_by_node).fillna(0.0)
    work["assigned_candidate_index"] = work.node_id.map(assignment_by_node).fillna(-1).astype(int)
    finite_improved = work.loc[work.scenario_reduction_m.gt(1e-9)].sort_values(
        ["scenario_reduction_m", "gml_id"], ascending=[False, True]
    )
    if len(finite_improved):
        building = finite_improved.iloc[0]
        candidate_index = int(building.assigned_candidate_index)
        before_distance = float(building.nearest_network_transport_distance_m)
        before_nodes, before_edges = reconstruct_route(transport_labels, str(building.node_id))
    else:
        selected_components = set(ordered_candidates.iloc[selected].component_id.astype(str))
        node_component = nodes.set_index("node_id").component_id.astype(str)
        unreachable = work.loc[
            work.network_to_transport_from_node_m.isna()
            & work.node_id.map(node_component).astype(str).isin(selected_components)
        ].sort_values("gml_id")
        if not len(unreachable):
            return None
        building = unreachable.iloc[0]
        same_component = [
            candidate
            for candidate in selected
            if str(ordered_candidates.iloc[candidate].component_id)
            == str(node_component[str(building.node_id)])
        ]
        routes = [
            (
                *_shortest_route(
                    route_adjacency,
                    str(building.node_id),
                    str(ordered_candidates.iloc[candidate].node_id),
                ),
                candidate,
            )
            for candidate in same_component
        ]
        _, _, _, candidate_index = min(routes, key=lambda item: (item[0], item[3]))
        before_distance = None
        before_nodes, before_edges = [], []

    candidate = ordered_candidates.iloc[candidate_index]
    after_graph_distance, after_nodes, after_edges = _shortest_route(
        route_adjacency, str(building.node_id), str(candidate.node_id)
    )
    if not math.isfinite(after_graph_distance):
        raise ValueError("Selected evidence route is not graph reachable")
    node_lookup = nodes.set_index("node_id")
    road_gml_ids = list(dict.fromkeys(node_lookup.loc[after_nodes, "gml_id"].astype(str).tolist()))
    elevation = node_lookup.elevation_m.astype(float)
    route_elevations = [float(elevation[node]) for node in after_nodes]
    deltas = np.diff(route_elevations)
    terrain_lookup = terrain_edges.set_index("edge_id")
    maximum_grade = max(
        (float(terrain_lookup.loc[edge, "absolute_grade_percent"]) for edge in after_edges),
        default=0.0,
    )
    demographic = (
        demographics.loc[demographics.gml_id.eq(building.gml_id)].sort_values("mesh_code").iloc[0]
    )
    return {
        "building_gml_id": str(building.gml_id),
        "estimated_demographic_source": {
            "source_population_year": int(demographic.source_population_year),
            "allocation_method": str(demographic.allocation_method),
            "population_resolution": str(demographic.population_resolution),
            "privacy": "model source only; no per-building person estimate is exported",
        },
        "origin_representative_point": {
            "longitude": round(float(demographic.longitude), 9),
            "latitude": round(float(demographic.latitude), 9),
            "method": str(building.snap_method),
        },
        "snap_node_id": str(building.node_id),
        "origin_to_node_connector_m": round(float(building.origin_to_node_distance_m), 3),
        "before": {
            "network_distance_m": (
                round(before_distance, 3) if before_distance is not None else None
            ),
            "destination_id": _clean(building.nearest_network_transport_id),
            "destination_name": _clean(building.nearest_network_transport_name),
            "road_edge_sequence": before_edges,
            "road_node_sequence": before_nodes,
        },
        "after": {
            "network_distance_m": round(
                float(building.origin_to_node_distance_m) + after_graph_distance, 3
            ),
            "graph_distance_from_snap_node_m": round(after_graph_distance, 3),
            "virtual_scenario_candidate_id": str(candidate.candidate_id),
            "virtual_scenario_node_id": str(candidate.node_id),
            "road_edge_sequence": after_edges,
            "road_node_sequence": after_nodes,
            "plateau_road_gml_ids": road_gml_ids,
            "terrain": {
                "ascent_m": round(float(np.maximum(deltas, 0).sum()), 3),
                "descent_m": round(float(np.maximum(-deltas, 0).sum()), 3),
                "maximum_observed_endpoint_grade_percent": round(maximum_grade, 3),
                "routing_penalty_applied": False,
            },
        },
        "route_semantics": "road_surface_adjacency_not_validated_pedestrian",
    }


def _pareto(plans: list[dict[str, Any]]) -> list[str]:
    metrics = np.asarray(
        [
            [
                plan["impact"]["mean_reduction_all_reachable_buildings_m"],
                plan["impact"]["elderly_weighted_mean_reduction_m"],
                plan["impact"]["worst_decile_mean_reduction_m"],
                plan["impact"]["robust_top20_improved_mesh_count"],
                plan["impact"]["newly_network_connected_building_count"],
            ]
            for plan in plans
        ],
        dtype=float,
    )
    keep = []
    for index in range(len(plans)):
        dominated = any(
            other != index
            and np.all(metrics[other] >= metrics[index] - 1e-9)
            and np.any(metrics[other] > metrics[index] + 1e-9)
            for other in range(len(plans))
        )
        if not dominated:
            keep.append(plans[index]["plan_id"])
    return keep


def build(*, max_sites: int = 5) -> dict[str, Any]:
    started = time.perf_counter()
    timings: dict[str, float] = {}
    if not 1 <= max_sites <= 20:
        raise ValueError("max_sites must be between 1 and 20")
    for path in (
        NODES,
        TERRAIN_NODES,
        TERRAIN_EDGES,
        EDGES,
        BUILDING_NETWORK,
        BUILDING_DEMOGRAPHICS,
        CANDIDATE_CONTEXT,
        TRANSPORT_LABELS,
    ):
        if not path.exists():
            raise FileNotFoundError(path)
    stage_started = time.perf_counter()
    nodes, edges, network, demographics, candidates, _, robust_meshes = _inputs()
    timings["candidate_and_input_generation_seconds"] = round(
        time.perf_counter() - stage_started, 6
    )
    stage_started = time.perf_counter()
    demand, building_network, fragments, unreachable_weights = _demand_tables(
        nodes, network, demographics, robust_meshes
    )
    timings["demand_preparation_seconds"] = round(time.perf_counter() - stage_started, 6)
    candidate_input = candidates[["candidate_id", "node_id"]]
    stage_started = time.perf_counter()
    matrix = build_candidate_gain_matrix(nodes, edges, candidate_input, demand)
    _gain_frame(matrix).to_parquet(GAINS, index=False)
    timings["sparse_matrix_seconds"] = round(time.perf_counter() - stage_started, 6)

    ordered_candidates = candidates.sort_values("candidate_id").reset_index(drop=True)
    ordered_demand = demand.sort_values("node_id").reset_index(drop=True)
    terrain_edges = pd.read_parquet(TERRAIN_EDGES)
    transport_labels = pd.read_parquet(TRANSPORT_LABELS)
    route_adjacency = _route_adjacency(edges)
    node_components = nodes.set_index("node_id").component_id.astype(str)
    candidate_components = ordered_candidates.component_id.astype(str).to_numpy()
    unreachable_buildings = building_network.loc[
        building_network.network_to_transport_from_node_m.isna()
    ].copy()
    unreachable_buildings["component_id"] = unreachable_buildings.node_id.map(node_components)

    plans_by_mode: dict[str, dict[str, Any]] = {}
    diminishing_returns: dict[str, list[dict[str, Any]]] = {}
    summary_rows = []
    for mode, definition in MODE_DEFINITIONS.items():
        mode_started = time.perf_counter()
        overall_weights = ordered_demand.building_count.to_numpy(float)
        if mode == "balanced":
            selected, trace = balanced_greedy_select(
                matrix,
                {
                    name: ordered_demand[column].to_numpy(float)
                    for name, column in (
                        ("overall", "building_count"),
                        ("elderly", "elderly_population"),
                        ("worst_served", "worst_served_building_count"),
                        ("robust", "robust_elderly_population"),
                    )
                },
                overall_weights,
                ordered_candidates.candidate_x.to_numpy(float),
                ordered_candidates.candidate_y.to_numpy(float),
                max_sites=max_sites,
                minimum_separation_m=MINIMUM_SEPARATION_M,
            )
        else:
            weights = ordered_demand[str(definition["weight"])].to_numpy(float)
            reachability_mode = mode == "reachability"
            selected, trace = greedy_select(
                matrix,
                weights,
                overall_weights,
                ordered_candidates.candidate_x.to_numpy(float),
                ordered_candidates.candidate_y.to_numpy(float),
                max_sites=max_sites,
                minimum_separation_m=MINIMUM_SEPARATION_M,
                candidate_components=candidate_components if reachability_mode else None,
                unreachable_component_weights=(unreachable_weights if reachability_mode else None),
            )
        mode_plans: dict[str, Any] = {}
        mode_diminishing = [
            {
                "site_count": 0,
                "total_building_distance_reduction_m": 0.0,
                "affected_building_count": 0,
                "affected_estimated_elderly_population": 0.0,
                "worst_decile_mean_reduction_m": 0.0,
                "marginal_total_building_distance_reduction_m": 0.0,
                "marginal_affected_building_count": 0,
                "marginal_affected_estimated_elderly_population": 0.0,
                "marginal_worst_decile_mean_reduction_m": 0.0,
                "newly_network_connected_building_count": 0,
                "marginal_newly_network_connected_building_count": 0,
            }
        ]
        previous_impact = mode_diminishing[0]
        for site_count in range(1, len(selected) + 1):
            prefix = selected[:site_count]
            reduction, assigned = evaluate_selected(matrix, prefix)
            selected_components = set(candidate_components[prefix])
            newly_reachable = int(
                unreachable_buildings.component_id.astype(str).isin(selected_components).sum()
            )
            impact, mesh_results = _impact(
                ordered_demand, reduction, fragments, robust_meshes, newly_reachable
            )
            selected_ids = [matrix.candidate_ids[index] for index in prefix]
            sites = [
                _site_record(
                    ordered_candidates.loc[
                        ordered_candidates.candidate_id.astype(str).eq(candidate_id)
                    ].iloc[0],
                    order,
                )
                for order, candidate_id in enumerate(selected_ids, start=1)
            ]
            plan = {
                "plan_id": f"network-{mode}-{site_count}",
                "mode": mode,
                "label": definition["label"],
                "site_count": site_count,
                "objective": definition["objective"],
                "exactness": (
                    "deterministic forward-greedy approximation; not a global N-site optimum"
                    if site_count > 1
                    else (
                        "exact max-min lexicographic result over the screened candidate set"
                        if mode == "balanced"
                        else (
                            "exact lexicographic result over the screened candidate set"
                            if mode == "reachability"
                            else "exact over the screened candidate set for this one-site linear objective"
                        )
                    )
                ),
                "sites": sites,
                "impact": impact,
                "mesh_results": mesh_results,
                "assigned_demand_node_count": int((assigned >= 0).sum()),
                "selection_trace": trace[:site_count],
            }
            plan["representative_evidence"] = _representative_evidence(
                building_network,
                demographics,
                matrix,
                reduction,
                assigned,
                prefix,
                ordered_candidates,
                route_adjacency,
                nodes,
                terrain_edges,
                transport_labels,
            )
            marginal = {
                "site_count": site_count,
                "total_building_distance_reduction_m": impact[
                    "total_building_distance_reduction_m"
                ],
                "affected_building_count": impact["improved_building_count"],
                "affected_estimated_elderly_population": impact[
                    "affected_estimated_elderly_population"
                ],
                "worst_decile_mean_reduction_m": impact["worst_decile_mean_reduction_m"],
                "marginal_total_building_distance_reduction_m": round(
                    impact["total_building_distance_reduction_m"]
                    - previous_impact["total_building_distance_reduction_m"],
                    3,
                ),
                "marginal_affected_building_count": (
                    impact["improved_building_count"] - previous_impact["affected_building_count"]
                ),
                "marginal_affected_estimated_elderly_population": round(
                    impact["affected_estimated_elderly_population"]
                    - previous_impact["affected_estimated_elderly_population"],
                    6,
                ),
                "marginal_worst_decile_mean_reduction_m": round(
                    impact["worst_decile_mean_reduction_m"]
                    - previous_impact["worst_decile_mean_reduction_m"],
                    3,
                ),
                "newly_network_connected_building_count": impact[
                    "newly_network_connected_building_count"
                ],
                "marginal_newly_network_connected_building_count": (
                    impact["newly_network_connected_building_count"]
                    - previous_impact["newly_network_connected_building_count"]
                ),
            }
            plan["marginal_from_previous_site"] = marginal
            mode_diminishing.append(marginal)
            previous_impact = marginal
            mode_plans[str(site_count)] = plan
            summary_rows.append(
                {
                    "plan_id": plan["plan_id"],
                    "mode": mode,
                    "site_count": site_count,
                    **impact,
                    **{
                        key: value for key, value in marginal.items() if key.startswith("marginal_")
                    },
                    "candidate_ids": "|".join(selected_ids),
                }
            )
        plans_by_mode[mode] = mode_plans
        diminishing_returns[mode] = mode_diminishing
        timings[f"optimizer_{mode}_seconds"] = round(time.perf_counter() - mode_started, 6)

    alternatives_by_site_count = {}
    for site_count in range(1, max_sites + 1):
        alternatives = [
            plans[str(site_count)] for plans in plans_by_mode.values() if str(site_count) in plans
        ]
        alternatives_by_site_count[str(site_count)] = {
            "plan_ids": [plan["plan_id"] for plan in alternatives],
            "pareto_plan_ids": _pareto(alternatives),
            "interpretation": "trade-off comparison; no single plan is labelled recommended",
        }

    report = {
        "schema_version": "1.0.0",
        "generated_at": _generated_at(),
        "algorithm_version": ALGORITHM_VERSION,
        "city": {"city_id": "26202", "name": "舞鶴市"},
        "network": {
            "graph_version": str(nodes.graph_version.iloc[0]),
            "graph_method": str(nodes.graph_method.iloc[0]),
            "network_type": "experimental_road_surface_adjacency",
            "pedestrian_network": False,
            "route_semantics": str(network.route_semantics.iloc[0]),
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
        "candidate_set": {
            "count": len(ordered_candidates),
            "source": "PLATEAU LOD1 road-surface representatives screened against existing transport",
            "existing_transport_exclusion_m": 150.0,
            "minimum_site_separation_m": MINIMUM_SEPARATION_M,
            "land_availability_confirmed": False,
        },
        "demand": {
            "strict_residential_buildings": int(building_network.gml_id.nunique()),
            "finite_baseline_buildings": int(
                building_network.network_to_transport_from_node_m.notna().sum()
            ),
            "baseline_unreachable_buildings": int(
                building_network.network_to_transport_from_node_m.isna().sum()
            ),
            "finite_demand_nodes": len(ordered_demand),
            "robust_top20_meshes_with_building_network_coverage": int(
                fragments.loc[fragments.robust_mesh, "mesh_code"].astype(str).nunique()
            ),
            "baseline_unreachable_buildings_in_components_with_screened_candidates": int(
                building_network.loc[
                    building_network.network_to_transport_from_node_m.isna()
                    & building_network.node_id.map(node_components)
                    .astype(str)
                    .isin(set(candidate_components))
                ].shape[0]
            ),
            "population_resolution": "500m census allocated model estimate; not resident records",
        },
        "sparse_gain_matrix": {
            "improving_candidate_demand_pairs": len(matrix.distance_reduction_m),
            "dense_candidate_demand_pair_count": len(matrix.candidate_ids)
            * len(matrix.demand_node_ids),
            "avoided_zero_gain_pair_count": len(matrix.candidate_ids) * len(matrix.demand_node_ids)
            - len(matrix.distance_reduction_m),
            "cutoff": "each demand node's finite baseline graph distance to public transport",
        },
        "objectives": MODE_DEFINITIONS,
        "plans": plans_by_mode,
        "diminishing_returns": diminishing_returns,
        "alternatives_by_site_count": alternatives_by_site_count,
        "context_policy": {
            "hazard": "displayed as additional_confirmation_required, never automatic rejection",
            "planning": "displayed from actual PLATEAU overlaps, not used as a guessed constraint",
            "landuse": "displayed from actual official codelist labels; availability remains unconfirmed",
            "attention_flags": {
                "long_connector_threshold_m": LONG_CONNECTOR_ATTENTION_M,
                "terrain_incident_grade_threshold_percent": TERRAIN_GRADE_ATTENTION_PERCENT,
                "effect": "review prompt only; never automatic rejection or approval",
            },
        },
        "provenance": {
            "road_nodes_sha256": _sha256(NODES),
            "road_terrain_nodes_sha256": _sha256(TERRAIN_NODES),
            "road_terrain_edges_sha256": _sha256(TERRAIN_EDGES),
            "road_edges_sha256": _sha256(EDGES),
            "building_network_sha256": _sha256(BUILDING_NETWORK),
            "building_demographics_sha256": _sha256(BUILDING_DEMOGRAPHICS),
            "candidate_context_sha256": _sha256(CANDIDATE_CONTEXT),
            "robustness_sha256": _sha256(ROBUSTNESS),
            "transport_network_labels_sha256": _sha256(TRANSPORT_LABELS),
        },
        "limitations": [
            "The graph represents LOD1 road-surface adjacency, not a validated pedestrian network.",
            "Candidate points do not confirm land ownership, constructability, service operation or cost.",
            "Each one-site result is exact for its stated linear, max-min or lexicographic objective over the screened set; N>1 is greedy.",
            "Terrain observations are kept separate and are not a hidden routing penalty.",
            "Hazard and planning overlaps require municipal review and do not determine feasibility.",
        ],
        "performance": {
            "timings": timings,
            "peak_rss_kib": _peak_rss_kib(),
        },
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }
    pd.DataFrame(summary_rows).to_csv(SUMMARY, index=False)
    _write_json(RESULT, report)
    _write_json(WEB_RESULT, _public_story(report), compact=True)
    performance = {
        "schema_version": "1.0.0",
        "algorithm_version": ALGORITHM_VERSION,
        "timings_seconds": timings,
        "stage_runtime_by_objective_and_site_count": {
            mode: {
                str(row["step"]): row["stage_runtime_seconds"]
                for row in plans[str(max(plans, key=int))]["selection_trace"]
            }
            for mode, plans in plans_by_mode.items()
        },
        "total_runtime_seconds": round(time.perf_counter() - started, 6),
        "peak_rss_kib": _peak_rss_kib(),
        "sparse_improvement_pair_count": len(matrix.distance_reduction_m),
        "dense_candidate_demand_pair_count": len(matrix.candidate_ids)
        * len(matrix.demand_node_ids),
        "avoided_zero_gain_pair_count": len(matrix.candidate_ids) * len(matrix.demand_node_ids)
        - len(matrix.distance_reduction_m),
        "artifact_sizes_bytes": {
            path.name: path.stat().st_size for path in (GAINS, SUMMARY, RESULT, WEB_RESULT)
        },
    }
    _write_json(PERFORMANCE, performance)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-sites", type=int, default=5)
    arguments = parser.parse_args()
    report = build(max_sites=arguments.max_sites)
    print(
        json.dumps(
            {
                "output": str(RESULT.relative_to(ROOT)),
                "plan_count": sum(len(plans) for plans in report["plans"].values()),
                "objective_modes": list(report["plans"]),
                "maximum_site_count": arguments.max_sites,
                "runtime_seconds": report["runtime_seconds"],
                "peak_rss_kib": report["performance"]["peak_rss_kib"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
