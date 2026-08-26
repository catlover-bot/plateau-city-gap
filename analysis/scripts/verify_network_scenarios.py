"""Independently verify network scenario routes, impacts and one-site optima."""

from __future__ import annotations

import heapq
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real"
RESULT = OUTPUT / "maizuru_network_scenarios.json"
VERIFICATION = OUTPUT / "maizuru_network_scenario_verification.json"


def _adjacency(
    nodes: pd.DataFrame, edges: pd.DataFrame
) -> tuple[list[str], dict[str, int], list[list[tuple[int, float]]]]:
    node_ids = sorted(nodes.node_id.astype(str))
    index = {node_id: position for position, node_id in enumerate(node_ids)}
    graph: list[list[tuple[int, float]]] = [[] for _ in node_ids]
    for row in edges.itertuples(index=False):
        source = index[str(row.source_node_id)]
        target = index[str(row.target_node_id)]
        graph[source].append((target, float(row.length_m)))
        graph[target].append((source, float(row.length_m)))
    return node_ids, index, graph


def _multi_source(graph: list[list[tuple[int, float]]], sources: list[int]) -> np.ndarray:
    distance = np.full(len(graph), np.inf)
    queue = []
    for source in sorted(set(sources)):
        distance[source] = 0.0
        heapq.heappush(queue, (0.0, source))
    while queue:
        current, node = heapq.heappop(queue)
        if current > distance[node] + 1e-9:
            continue
        for neighbor, weight in graph[node]:
            proposed = current + weight
            if proposed < distance[neighbor] - 1e-9:
                distance[neighbor] = proposed
                heapq.heappush(queue, (proposed, neighbor))
    return distance


def _single_target(graph: list[list[tuple[int, float]]], source: int, target: int) -> float:
    distance = {source: 0.0}
    queue = [(0.0, source)]
    while queue:
        current, node = heapq.heappop(queue)
        if node == target:
            return current
        if current > distance[node] + 1e-9:
            continue
        for neighbor, weight in graph[node]:
            proposed = current + weight
            if proposed < distance.get(neighbor, math.inf) - 1e-9:
                distance[neighbor] = proposed
                heapq.heappush(queue, (proposed, neighbor))
    return math.inf


def _write(value: dict[str, Any]) -> None:
    VERIFICATION.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def verify() -> dict[str, Any]:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    nodes = pd.read_parquet(OUTPUT / "maizuru_road_graph_nodes.parquet")
    edges = pd.read_parquet(OUTPUT / "maizuru_road_graph_edges.parquet")
    network = pd.read_parquet(OUTPUT / "maizuru_building_network_accessibility.parquet")
    demographics = pd.read_parquet(OUTPUT / "maizuru_building_demographics.parquet")
    gains = pd.read_parquet(OUTPUT / "maizuru_network_scenario_candidate_gains.parquet")
    candidates = pd.read_csv(OUTPUT / "maizuru_scenario_candidate_context.csv")
    _node_ids, node_index, graph = _adjacency(nodes, edges)

    building_demographics = demographics.groupby("gml_id", as_index=False).agg(
        estimated_elderly_population=("estimated_elderly_population", "sum")
    )
    buildings = network.merge(building_demographics, on="gml_id", how="left", validate="one_to_one")
    finite = buildings.network_to_transport_from_node_m.notna()
    worst_count = max(1, math.ceil(int(finite.sum()) * 0.1))
    worst_ids = set(
        buildings.loc[finite]
        .sort_values(
            ["nearest_network_transport_distance_m", "gml_id"],
            ascending=[False, True],
        )
        .head(worst_count)
        .gml_id
    )
    buildings["worst_served"] = buildings.gml_id.isin(worst_ids)

    robust_meshes = {
        str(row["mesh_code"])
        for row in json.loads((OUTPUT / "maizuru_robustness.json").read_text())["top_candidates"][
            :20
        ]
    }
    robust_fragments = demographics.loc[demographics.mesh_code.astype(str).isin(robust_meshes)]
    robust_by_building = (
        robust_fragments.groupby("gml_id", as_index=False)
        .estimated_elderly_population.sum()
        .rename(columns={"estimated_elderly_population": "robust_elderly_population"})
    )
    buildings = buildings.merge(robust_by_building, on="gml_id", how="left")
    buildings["robust_elderly_population"] = buildings.robust_elderly_population.fillna(0.0)

    impact_residuals = []
    spacing_failures = []
    context_failures = []
    candidate_coordinates = candidates.set_index("candidate_id")[["candidate_x", "candidate_y"]]
    for mode_plans in report["plans"].values():
        for plan in mode_plans.values():
            site_nodes = [node_index[site["node_id"]] for site in plan["sites"]]
            site_distance = _multi_source(graph, site_nodes)
            building_node_indices = buildings.node_id.map(node_index).to_numpy(int)
            graph_distance = site_distance[building_node_indices]
            baseline = buildings.network_to_transport_from_node_m.to_numpy(float)
            reduction = np.where(
                np.isfinite(baseline), np.maximum(baseline - graph_distance, 0.0), 0.0
            )
            improved = reduction > 1e-9
            directly_computed = {
                "improved_building_count": int(improved.sum()),
                "newly_network_connected_building_count": int(
                    ((~np.isfinite(baseline)) & np.isfinite(graph_distance)).sum()
                ),
                "total_building_distance_reduction_m": float(reduction.sum()),
                "elderly_weighted_distance_reduction_person_m": float(
                    np.dot(
                        reduction,
                        buildings.estimated_elderly_population.to_numpy(float),
                    )
                ),
                "worst_decile_mean_reduction_m": float(
                    reduction[buildings.worst_served.to_numpy(bool)].mean()
                ),
            }
            published = plan["impact"]
            impact_residuals.append(
                {
                    "plan_id": plan["plan_id"],
                    "improved_building_count": abs(
                        directly_computed["improved_building_count"]
                        - published["improved_building_count"]
                    ),
                    "newly_network_connected_building_count": abs(
                        directly_computed["newly_network_connected_building_count"]
                        - published["newly_network_connected_building_count"]
                    ),
                    "total_building_distance_reduction_m": abs(
                        directly_computed["total_building_distance_reduction_m"]
                        - published["total_building_distance_reduction_m"]
                    ),
                    "elderly_weighted_distance_reduction_person_m": abs(
                        directly_computed["elderly_weighted_distance_reduction_person_m"]
                        - published["elderly_weighted_distance_reduction_person_m"]
                    ),
                    "worst_decile_mean_reduction_m": abs(
                        directly_computed["worst_decile_mean_reduction_m"]
                        - published["worst_decile_mean_reduction_m"]
                    ),
                }
            )
            site_ids = [site["candidate_id"] for site in plan["sites"]]
            positions = candidate_coordinates.loc[site_ids].to_numpy(float)
            for left in range(len(positions)):
                for right in range(left + 1, len(positions)):
                    if np.linalg.norm(positions[left] - positions[right]) < 1_500 - 1e-9:
                        spacing_failures.append(
                            {"plan_id": plan["plan_id"], "left": left, "right": right}
                        )
            for site in plan["sites"]:
                if site["hazard_overlap"] and site["hazard_review_status"] != (
                    "additional_confirmation_required"
                ):
                    context_failures.append(plan["plan_id"])
                if site["siting_feasibility"] != "not_determined":
                    context_failures.append(plan["plan_id"])

    demand_weights = (
        buildings.loc[finite]
        .groupby("node_id", as_index=False)
        .agg(
            building_count=("gml_id", "nunique"),
            elderly_population=("estimated_elderly_population", "sum"),
            worst_served_building_count=("worst_served", "sum"),
            robust_elderly_population=("robust_elderly_population", "sum"),
        )
        .set_index("node_id")
    )
    one_site_optimality = {}
    weight_by_mode = {
        "overall": "building_count",
        "elderly": "elderly_population",
        "worst_served": "worst_served_building_count",
        "robust": "robust_elderly_population",
    }
    gain_with_weights = gains.merge(
        demand_weights,
        left_on="demand_node_id",
        right_index=True,
        validate="many_to_one",
    )
    for mode, column in weight_by_mode.items():
        objective = (
            gain_with_weights.assign(
                weighted=gain_with_weights.distance_reduction_m * gain_with_weights[column]
            )
            .groupby("candidate_id")
            .weighted.sum()
        )
        selected = report["plans"][mode]["1"]["sites"][0]["candidate_id"]
        best_value = float(objective.max())
        one_site_optimality[mode] = {
            "selected_candidate_id": selected,
            "selected_value": float(objective.get(selected, 0.0)),
            "maximum_value": best_value,
            "residual": abs(float(objective.get(selected, 0.0)) - best_value),
        }

    all_candidate_ids = sorted(candidates.candidate_id.astype(str).unique())
    objective_tables = {
        mode: (
            gain_with_weights.assign(
                weighted=gain_with_weights.distance_reduction_m * gain_with_weights[column]
            )
            .groupby("candidate_id")
            .weighted.sum()
            .reindex(all_candidate_ids, fill_value=0.0)
        )
        for mode, column in weight_by_mode.items()
    }
    objective_maxima = {mode: float(values.max()) for mode, values in objective_tables.items()}

    def lexicographically_better(
        key: tuple[float, ...], reference: tuple[float, ...] | None
    ) -> bool:
        if reference is None:
            return True
        for value, other in zip(key, reference, strict=True):
            if value > other + 1e-9:
                return True
            if value < other - 1e-9:
                return False
        return False

    balanced_best = ""
    balanced_best_key: tuple[float, ...] | None = None
    for candidate_id in all_candidate_ids:
        normalized = sorted(
            float(objective_tables[mode][candidate_id]) / objective_maxima[mode]
            if objective_maxima[mode] > 1e-9
            else 1.0
            for mode in weight_by_mode
        )
        key = (*normalized, float(objective_tables["overall"][candidate_id]))
        if lexicographically_better(key, balanced_best_key):
            balanced_best = candidate_id
            balanced_best_key = key
    balanced_selected = report["plans"]["balanced"]["1"]["sites"][0]["candidate_id"]
    balanced_optimality = {
        "selected_candidate_id": balanced_selected,
        "independently_selected_candidate_id": balanced_best,
        "selected_key": [
            round(value, 12)
            for value in (balanced_best_key if balanced_selected == balanced_best else ())
        ],
    }

    node_components = nodes.set_index("node_id").component_id.astype(str)
    unreachable_component_weights = (
        buildings.loc[~finite]
        .assign(component_id=lambda frame: frame.node_id.map(node_components))
        .groupby("component_id")
        .gml_id.nunique()
        .astype(float)
        .to_dict()
    )
    surface_nodes = nodes.set_index("surface_id").node_id.astype(str)
    candidate_components = pd.Series(
        {
            candidate_id: str(
                node_components[
                    surface_nodes[
                        f"{candidate_id.rsplit('-', 1)[0]}:{candidate_id.rsplit('-', 1)[1]}"
                    ]
                ]
            )
            for candidate_id in all_candidate_ids
        }
    )
    reachability_best = ""
    reachability_best_key: tuple[float, ...] | None = None
    for candidate_id in all_candidate_ids:
        component = candidate_components[candidate_id]
        overall = float(objective_tables["overall"][candidate_id])
        key = (float(unreachable_component_weights.get(component, 0.0)), overall, overall)
        if lexicographically_better(key, reachability_best_key):
            reachability_best = candidate_id
            reachability_best_key = key
    reachability_selected = report["plans"]["reachability"]["1"]["sites"][0]["candidate_id"]
    reachability_optimality = {
        "selected_candidate_id": reachability_selected,
        "independently_selected_candidate_id": reachability_best,
        "selected_key": [
            round(value, 12)
            for value in (
                reachability_best_key if reachability_selected == reachability_best else ()
            )
        ],
    }

    gain_sample = gains.iloc[np.unique(np.linspace(0, len(gains) - 1, 200, dtype=int))]
    candidate_node = {
        site["candidate_id"]: site["node_id"]
        for plans in report["plans"].values()
        for plan in plans.values()
        for site in plan["sites"]
    }
    surface_lookup = nodes.set_index("surface_id").node_id.astype(str)
    gain_distance_residuals = []
    for row in gain_sample.itertuples(index=False):
        candidate_node_id = candidate_node.get(str(row.candidate_id))
        if candidate_node_id is None:
            base, surface = str(row.candidate_id).rsplit("-", 1)
            candidate_node_id = surface_lookup[f"{base}:{surface}"]
        computed = _single_target(
            graph,
            node_index[str(row.demand_node_id)],
            node_index[str(candidate_node_id)],
        )
        gain_distance_residuals.append(abs(computed - float(row.network_distance_m)))

    required_flags = {
        "hazard_attention",
        "planning_attention",
        "landuse_attention",
        "network_component_attention",
        "long_connector_attention",
        "terrain_attention",
    }
    flag_failures = []
    evidence_failures = []
    maximum_evidence_distance_residual = 0.0
    edge_lookup = edges.set_index("edge_id")
    node_gml = nodes.set_index("node_id").gml_id.astype(str)
    for mode_plans in report["plans"].values():
        for plan in mode_plans.values():
            plan_candidate_ids = {site["candidate_id"] for site in plan["sites"]}
            for site in plan["sites"]:
                flags = site.get("feasibility_flags", {})
                if not required_flags.issubset(flags) or flags.get("interpretation") != (
                    "review prompts only; no flag is an automatic policy decision"
                ):
                    flag_failures.append(
                        {"plan_id": plan["plan_id"], "candidate_id": site["candidate_id"]}
                    )

            evidence = plan.get("representative_evidence")
            if not evidence:
                evidence_failures.append(
                    {"plan_id": plan["plan_id"], "reason": "missing representative evidence"}
                )
                continue
            after = evidence["after"]
            route_nodes = [str(value) for value in after["road_node_sequence"]]
            route_edges = [str(value) for value in after["road_edge_sequence"]]
            if len(route_nodes) != len(route_edges) + 1:
                evidence_failures.append(
                    {"plan_id": plan["plan_id"], "reason": "route sequence lengths"}
                )
                continue
            if (
                not route_nodes
                or route_nodes[0] != evidence["snap_node_id"]
                or route_nodes[-1] != after["virtual_scenario_node_id"]
                or after["virtual_scenario_candidate_id"] not in plan_candidate_ids
            ):
                evidence_failures.append({"plan_id": plan["plan_id"], "reason": "route endpoints"})
            route_length = 0.0
            for index, edge_id in enumerate(route_edges):
                if edge_id not in edge_lookup.index:
                    evidence_failures.append(
                        {"plan_id": plan["plan_id"], "reason": f"unknown edge {edge_id}"}
                    )
                    continue
                edge = edge_lookup.loc[edge_id]
                expected = {route_nodes[index], route_nodes[index + 1]}
                actual = {str(edge.source_node_id), str(edge.target_node_id)}
                if expected != actual:
                    evidence_failures.append(
                        {"plan_id": plan["plan_id"], "reason": f"edge endpoints {edge_id}"}
                    )
                route_length += float(edge.length_m)
            graph_residual = abs(route_length - float(after["graph_distance_from_snap_node_m"]))
            total_residual = abs(
                float(evidence["origin_to_node_connector_m"])
                + float(after["graph_distance_from_snap_node_m"])
                - float(after["network_distance_m"])
            )
            maximum_evidence_distance_residual = max(
                maximum_evidence_distance_residual, graph_residual, total_residual
            )
            computed_road_ids = list(dict.fromkeys(node_gml.loc[route_nodes].tolist()))
            if computed_road_ids != after["plateau_road_gml_ids"]:
                evidence_failures.append(
                    {"plan_id": plan["plan_id"], "reason": "PLATEAU road GML sequence"}
                )
            demographic_source = evidence.get("estimated_demographic_source", {})
            if not evidence.get("building_gml_id") or not {
                "source_population_year",
                "allocation_method",
                "population_resolution",
                "privacy",
            }.issubset(demographic_source):
                evidence_failures.append(
                    {"plan_id": plan["plan_id"], "reason": "demographic provenance"}
                )

    maximum_metric_residual = max(
        (value for row in impact_residuals for key, value in row.items() if key != "plan_id"),
        default=0.0,
    )
    checks = {
        "all_30_plan_impacts_recompute": maximum_metric_residual < 5e-4,
        "all_one_site_linear_objectives_are_exact": all(
            row["residual"] < 1e-6 for row in one_site_optimality.values()
        ),
        "one_site_balanced_max_min_is_exact": balanced_selected == balanced_best,
        "one_site_reachability_lexicographic_is_exact": (
            reachability_selected == reachability_best
        ),
        "sampled_gain_network_distances_recompute": max(gain_distance_residuals, default=0.0)
        < 1e-8,
        "minimum_site_separation_holds": not spacing_failures,
        "hazard_context_never_determines_feasibility": not context_failures,
        "six_review_only_feasibility_flags_are_present": not flag_failures,
        "representative_evidence_routes_recompute": (
            not evidence_failures and maximum_evidence_distance_residual < 2e-3
        ),
        "claim_boundary_is_explicit": (
            report["network"]["pedestrian_network"] is False
            and report["candidate_set"]["land_availability_confirmed"] is False
        ),
        "pareto_comparison_has_no_recommendation": all(
            item["interpretation"] == "trade-off comparison; no single plan is labelled recommended"
            for item in report["alternatives_by_site_count"].values()
        ),
    }
    verification = {
        "schema_version": "1.0.0",
        "verification_method": "independent adjacency and Dijkstra implementation",
        "passed": all(checks.values()),
        "checks": checks,
        "evidence": {
            "plan_count": len(impact_residuals),
            "maximum_published_metric_residual": maximum_metric_residual,
            "one_site_optimality": one_site_optimality,
            "balanced_one_site_optimality": balanced_optimality,
            "reachability_one_site_optimality": reachability_optimality,
            "gain_pair_sample_count": len(gain_sample),
            "maximum_gain_distance_residual_m": max(gain_distance_residuals, default=0.0),
            "spacing_failures": spacing_failures,
            "context_failures": context_failures,
            "flag_failures": flag_failures,
            "evidence_failures": evidence_failures,
            "maximum_evidence_distance_residual_m": maximum_evidence_distance_residual,
        },
    }
    _write(verification)
    return verification


def main() -> None:
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
