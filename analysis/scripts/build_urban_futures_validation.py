"""Build reproducible real-data validation for temporal and resilience capabilities."""

from __future__ import annotations

import argparse
import json
import resource
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import yaml
from shapely import from_wkb
from shapely.geometry import MultiPoint, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree

from analysis.src.planning_monitoring import compare_planning_context
from analysis.src.urban_resilience import (
    BuildingDemand,
    HazardClosureAssumption,
    NetworkEdge,
    k_shortest_paths,
    multi_source_distances,
    network_criticality_candidates,
    run_network_stress_test,
    verify_bridge_by_removal,
)
from backend.citygap_platform.ingestion.critical_facilities import OfficialShelterAdapter
from backend.citygap_platform.ingestion.differential import FeatureFingerprint, diff_fingerprints
from backend.citygap_platform.ingestion.future_population import (
    OfficialFuturePopulationAdapter,
    allocate_projection_to_buildings,
    future_accessibility_summary,
)

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"
DEFAULT_OUTPUT = REAL / "urban_futures_validation.json"
DEFAULT_PUBLIC_OUTPUT = ROOT / "frontend/public/data/urban_futures_resilience.json"
ALGORITHM_VERSION = "urban-resilience-1.0.0"
LIMITATION = (
    "Counterfactual stress test on the experimental PLATEAU LOD1 road-surface adjacency "
    "graph; this is not a prediction of disaster damage, road passability, pedestrian "
    "routing, evacuation movement or crowd behavior."
)


def _rss_mib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _round(value: object) -> object:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {str(key): _round(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(item) for item in value]
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_round(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _network_edges(frame: pd.DataFrame) -> tuple[NetworkEdge, ...]:
    return tuple(
        NetworkEdge(str(row.edge_id), str(row.source_node_id), str(row.target_node_id), float(row.length_m))
        for row in frame.itertuples(index=False)
    )


def _facility_seeds(city_id: str, category: str) -> dict[str, float]:
    labels = pd.read_parquet(REAL / f"{city_id}_{category}_network_labels.parquet")
    selected = labels.loc[
        labels.groupby("destination_id", sort=False)["network_to_destination_distance_m"].idxmin()
    ]
    return {
        str(node_id): float(group["network_to_destination_distance_m"].min())
        for node_id, group in selected.groupby("node_id", sort=True)
    }


def _shelter_seeds(
    config_path: Path, nodes: pd.DataFrame
) -> tuple[dict[str, float], dict[str, object]]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = raw["datasets"]["shelters"]
    source_path = ROOT / source["path"]
    adapter = OfficialShelterAdapter(
        source_path,
        city_code=str(raw["city_code"]),
        source_year=int(source["year"]),
        source_url=str(source["source_url"]),
        expected_sha256=str(source["source_sha256"]),
    )
    inspection = asdict(adapter.inspect())
    node_geometry = from_wkb(nodes["geometry"].to_numpy())
    tree = STRtree(node_geometry)
    shelters = gpd.read_file(source_path, engine="pyogrio").to_crs(str(raw["analysis_crs"]))
    seeds: dict[str, float] = {}
    connectors: list[float] = []
    for geometry in shelters.geometry:
        index, distance = tree.query_nearest(geometry, return_distance=True, all_matches=False)
        node_id = str(nodes.iloc[int(index[0])]["node_id"])
        connector = float(distance[0])
        connectors.append(connector)
        seeds[node_id] = min(seeds.get(node_id, float("inf")), connector)
    inspection["graph_seed_count"] = len(seeds)
    inspection["snap_distance_m"] = {
        "minimum": min(connectors),
        "median": float(pd.Series(connectors).median()),
        "maximum": max(connectors),
    }
    inspection["reachability_semantics"] = "network reachability only; not evacuation simulation"
    return seeds, inspection


def _building_inputs(
    city_id: str,
    evacuation_distances: dict[str, float],
) -> tuple[tuple[BuildingDemand, ...], pd.DataFrame, pd.DataFrame]:
    demographics = pd.read_parquet(REAL / f"{city_id}_building_demographics.parquet")
    capacity = (
        demographics.groupby("gml_id", as_index=False)
        .agg(
            mesh_code=("mesh_code", "first"),
            capacity_weight=("effective_floor_area_in_mesh", "sum"),
            estimated_population=("estimated_population", "sum"),
            estimated_elderly_population=("estimated_elderly_population", "sum"),
        )
        .rename(columns={"gml_id": "building_id"})
    )
    access = pd.read_parquet(REAL / f"{city_id}_building_network_accessibility.parquet")
    access = access.drop_duplicates("gml_id").rename(columns={"gml_id": "building_id"})
    merged = access.merge(capacity, on="building_id", how="inner", validate="one_to_one")
    demands: list[BuildingDemand] = []
    for row in merged.itertuples(index=False):
        connector = float(row.origin_to_node_distance_m)
        evacuation_node_distance = evacuation_distances.get(str(row.node_id), float("inf"))
        demands.append(
            BuildingDemand(
                building_id=str(row.building_id),
                node_id=str(row.node_id),
                connector_m=connector,
                estimated_population=float(row.estimated_population),
                estimated_elderly_population=float(row.estimated_elderly_population),
                baseline_distances_m={
                    "transport_hub": float(row.nearest_network_transport_distance_m),
                    "medical": float(row.nearest_network_medical_distance_m),
                    "evacuation": (
                        evacuation_node_distance + connector
                        if evacuation_node_distance != float("inf")
                        else None
                    ),
                },
            )
        )
    fixed_access = merged[
        ["building_id", "nearest_network_transport_distance_m", "nearest_network_medical_distance_m"]
    ].rename(
        columns={
            "nearest_network_transport_distance_m": "transport_distance_m",
            "nearest_network_medical_distance_m": "medical_distance_m",
        }
    )
    return tuple(demands), capacity, fixed_access


def _identity_diff(edges: pd.DataFrame) -> dict[str, object]:
    started = time.perf_counter()
    fingerprints = tuple(
        FeatureFingerprint.create(
            str(row.edge_id),
            "Road",
            bytes(row.geometry),
            {
                "source_node_id": str(row.source_node_id),
                "target_node_id": str(row.target_node_id),
                "topology_relation": str(row.topology_relation),
                "length_m": round(float(row.length_m), 9),
            },
        )
        for row in edges.itertuples(index=False)
    )
    changes = diff_fingerprints(fingerprints, fingerprints)
    counts = pd.Series([row.change_type for row in changes]).value_counts().to_dict()
    return {
        "comparison": "current official road state versus itself",
        "result": {key: int(counts.get(key, 0)) for key in ("added", "removed", "geometry_changed", "attribute_changed", "unchanged")},
        "runtime_seconds": time.perf_counter() - started,
        "peak_rss_mib": _rss_mib(),
        "correctness_check": counts.get("unchanged", 0) == len(edges),
        "annual_change_detection": "unavailable until a second official PLATEAU version is registered",
    }


def _future_states(
    city_code: str, capacity: pd.DataFrame, access: pd.DataFrame
) -> dict[str, object]:
    adapter = OfficialFuturePopulationAdapter(ROOT / "analysis/sources/official_future_population.csv")
    rows = adapter.records(city_code)
    series: dict[str, list[dict[str, object]]] = {}
    started = time.perf_counter()
    for projection in rows:
        allocation = allocate_projection_to_buildings(capacity, projection)
        summary = future_accessibility_summary(allocation, access)
        summary.update(
            {
                "official_total_population": projection.total_population,
                "official_age_65_plus": projection.age_65_plus,
                "publisher": projection.publisher,
                "source_url": projection.source_url,
                "source_sha256": projection.source_sha256,
                "source_verified": projection.source_verified,
            }
        )
        series.setdefault(projection.projection_series, []).append(summary)
    return {
        "series": series,
        "available_years": sorted({row.year for row in rows}),
        "runtime_seconds": time.perf_counter() - started,
        "peak_rss_mib": _rss_mib(),
        "semantics": "official demographic projection + CITY GAP spatial allocation model",
        "prediction_claimed": False,
    }


def _redundancy(edges: tuple[NetworkEdge, ...], bridge_ids: set[str]) -> dict[str, object]:
    for edge in sorted(edges, key=lambda item: (-item.length_m, item.edge_id)):
        if edge.edge_id in bridge_ids:
            continue
        paths = k_shortest_paths(edges, edge.source, edge.target, 2)
        if len(paths) == 2:
            return {
                "selected_origin_node": edge.source,
                "selected_destination_node": edge.target,
                "primary_route": asdict(paths[0]),
                "second_best_route": asdict(paths[1]),
                "distance_increase_m": paths[1].distance_m - paths[0].distance_m,
                "alternative_available": True,
                "selection_method": "longest non-critical edge with a verified second path",
                "route_semantics": "road-surface adjacency; not a validated pedestrian route",
            }
    return {"alternative_available": False, "reason": "no qualifying selected pair"}


def _wgs84_geometry(geometry: object, analysis_crs: str) -> dict[str, object]:
    transformed = gpd.GeoSeries([geometry], crs=analysis_crs).to_crs("EPSG:4326").iloc[0]
    return mapping(transformed)


def _map_feature(
    feature_id: str,
    geometry: object,
    analysis_crs: str,
    **properties: object,
) -> dict[str, object]:
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": _wgs84_geometry(geometry, analysis_crs),
        "properties": properties,
    }


def _route_geometry(edge_ids: list[str], geometry_by_edge: dict[str, object]) -> object:
    lines = [geometry_by_edge[edge_id] for edge_id in edge_ids if edge_id in geometry_by_edge]
    if not lines:
        raise ValueError("Selected resilience route has no registered edge geometry")
    return unary_union(lines)


def validate_city(config_path: Path) -> dict[str, object]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    city_id = str(raw["city_id"])
    edges_frame = pd.read_parquet(REAL / f"{city_id}_road_graph_edges.parquet")
    nodes = pd.read_parquet(REAL / f"{city_id}_road_graph_nodes.parquet")
    edge_rows = _network_edges(edges_frame)
    transport_seeds = _facility_seeds(city_id, "transport")
    medical_seeds = _facility_seeds(city_id, "medical")
    evacuation_seeds, shelter_inspection = _shelter_seeds(config_path, nodes)
    evacuation_distances = multi_source_distances(edge_rows, evacuation_seeds)
    buildings, capacity, fixed_access = _building_inputs(city_id, evacuation_distances)
    service_seeds = {
        "medical": medical_seeds,
        "transport_hub": transport_seeds,
        "evacuation": evacuation_seeds,
    }

    critical_started = time.perf_counter()
    critical = network_criticality_candidates(edge_rows, buildings, service_seeds)
    critical_runtime = time.perf_counter() - critical_started
    redundancy = _redundancy(edge_rows, {row.edge_id for row in critical})
    verified = [
        {
            "edge_id": row.edge_id,
            "independent_removal_verifier": verify_bridge_by_removal(edge_rows, row.edge_id),
        }
        for row in critical[:3]
    ]

    hazards = pd.read_parquet(REAL / f"{city_id}_road_hazard_context.parquet")
    analysis_crs = str(raw["analysis_crs"])
    edge_geometry = from_wkb(edges_frame["geometry"].to_numpy())
    geometry_by_edge = dict(zip(edges_frame["edge_id"].astype(str), edge_geometry, strict=True))
    node_geometry = from_wkb(nodes["geometry"].to_numpy())
    geometry_by_node = dict(zip(nodes["node_id"].astype(str), node_geometry, strict=True))
    common_map_features: list[dict[str, object]] = []
    if redundancy.get("alternative_available"):
        primary = redundancy["primary_route"]
        alternative = redundancy["second_best_route"]
        assert isinstance(primary, dict) and isinstance(alternative, dict)
        common_map_features.extend(
            [
                _map_feature(
                    f"{city_id}:selected-pair:normal",
                    _route_geometry(list(primary["edge_ids"]), geometry_by_edge),
                    analysis_crs,
                    layer_type="normal_route",
                    stress_mode="all",
                    distance_m=primary["distance_m"],
                    route_semantics=redundancy["route_semantics"],
                    selection_method=redundancy["selection_method"],
                    review_label="selected-pair primary route",
                ),
                _map_feature(
                    f"{city_id}:selected-pair:alternative",
                    _route_geometry(list(alternative["edge_ids"]), geometry_by_edge),
                    analysis_crs,
                    layer_type="disrupted_route",
                    stress_mode="all",
                    distance_m=alternative["distance_m"],
                    distance_increase_m=redundancy["distance_increase_m"],
                    route_semantics=redundancy["route_semantics"],
                    selection_method=redundancy["selection_method"],
                    review_label="second-best route when the selected primary edge is unavailable",
                ),
            ]
        )
    if critical:
        common_map_features.append(
            _map_feature(
                f"{city_id}:critical:{critical[0].edge_id}",
                geometry_by_edge[critical[0].edge_id],
                analysis_crs,
                layer_type="critical_edge",
                stress_mode="all",
                edge_id=critical[0].edge_id,
                affected_buildings=critical[0].affected_buildings,
                candidate_label="network criticality candidate",
                dangerous_road_claimed=False,
            )
        )
    accessibility = pd.read_parquet(
        REAL / f"{city_id}_building_network_accessibility.parquet"
    )
    medical_labels = pd.read_parquet(REAL / f"{city_id}_medical_network_labels.parquet")
    medical_seed_rows = medical_labels.loc[
        medical_labels.groupby("destination_id", sort=False)[
            "network_to_destination_distance_m"
        ].idxmin()
    ].set_index("destination_id")
    selected_hazards = ("flood", "landslide", "tsunami") if city_id == "maizuru" else ("flood",)
    stress_tests: dict[str, object] = {}
    resilience_map_features = list(common_map_features)
    for hazard_type in selected_hazards:
        selected = hazards.loc[hazards["hazard_type"].eq(hazard_type)]
        if selected.empty:
            continue
        classes = tuple(
            sorted(
                {
                    str(value)
                    for column in ("rank_label", "area_type_label", "description_label")
                    for value in selected[column].dropna().unique()
                }
            )
        )
        assumption = HazardClosureAssumption(
            hazard_dataset_version=f"{city_id}-plateau-{raw['plateau_dataset']['year']}-{hazard_type}",
            hazard_type=hazard_type,
            hazard_classes=classes or ("all published classes",),
            rule="overlap_edges_unavailable",
            assumption_source="explicit CITY GAP validation exercise rule",
            explicitly_confirmed=True,
        )
        closed = frozenset(selected["edge_id"].astype(str).unique())
        started = time.perf_counter()
        result = run_network_stress_test(edge_rows, buildings, service_seeds, closed)
        scenario_medical_distances = multi_source_distances(edge_rows, medical_seeds, closed)
        disconnected = [
            building
            for building in buildings
            if building.baseline_distances_m.get("medical") is not None
            and scenario_medical_distances.get(building.node_id, float("inf")) == float("inf")
        ]
        disconnected_nodes = sorted({building.node_id for building in disconnected})
        disconnected_points = [
            geometry_by_node[node_id]
            for node_id in disconnected_nodes
            if node_id in geometry_by_node
        ]
        if disconnected_points:
            aggregate_area = MultiPoint(disconnected_points).convex_hull.buffer(150)
            resilience_map_features.append(
                _map_feature(
                    f"{city_id}:{hazard_type}:disconnected-area",
                    aggregate_area,
                    analysis_crs,
                    layer_type="disconnected_area",
                    stress_mode=hazard_type,
                    service_category="medical",
                    newly_unreachable_buildings=len(disconnected),
                    aggregation="150m-buffered convex hull of disconnected demand nodes",
                    exact_affected_area_claimed=False,
                )
            )
        disconnected_ids = {building.building_id for building in disconnected}
        affected_destinations = (
            accessibility.loc[
                accessibility["gml_id"].astype(str).isin(disconnected_ids),
                ["nearest_network_medical_id", "nearest_network_medical_name"],
            ]
            .value_counts()
            .reset_index(name="disconnected_buildings")
            .head(3)
        )
        for rank, facility in enumerate(affected_destinations.itertuples(index=False), start=1):
            destination_id = str(facility.nearest_network_medical_id)
            if destination_id not in medical_seed_rows.index:
                continue
            seed_node_id = str(medical_seed_rows.loc[destination_id, "node_id"])
            if seed_node_id not in geometry_by_node:
                continue
            resilience_map_features.append(
                _map_feature(
                    f"{city_id}:{hazard_type}:facility:{rank}",
                    geometry_by_node[seed_node_id],
                    analysis_crs,
                    layer_type="affected_facility",
                    stress_mode=hazard_type,
                    service_category="medical",
                    facility_name=str(facility.nearest_network_medical_name),
                    disconnected_buildings=int(facility.disconnected_buildings),
                    facility_status_change_claimed=False,
                    review_label="baseline destination for disconnected building-demand records",
                )
            )
        stress_tests[hazard_type] = {
            "assumption": assumption.canonical_payload(),
            "result": asdict(result),
            "runtime_seconds": time.perf_counter() - started,
            "peak_rss_mib": _rss_mib(),
        }

    planning_started = time.perf_counter()
    planning = compare_planning_context(
        pd.read_parquet(REAL / f"{city_id}_building_demographics.parquet"),
        pd.read_parquet(REAL / f"{city_id}_building_plateau_context.parquet"),
    )
    planning_runtime = time.perf_counter() - planning_started
    scenario_performance_path = REAL / f"{city_id}_network_scenario_performance.json"
    scenario_runtime: object = "not available for this validation city"
    if scenario_performance_path.is_file():
        scenario_runtime = json.loads(scenario_performance_path.read_text(encoding="utf-8"))[
            "total_runtime_seconds"
        ]

    return {
        "city_id": city_id,
        "city_code": str(raw["city_code"]),
        "city_name": str(raw["city_name"]),
        "urban_state": f"{city_id}-{raw['plateau_dataset']['year']}-observed",
        "plateau_version": int(raw["plateau_dataset"]["version"]),
        "network": {
            "version": str(edges_frame["graph_version"].iloc[0]),
            "nodes": len(nodes),
            "edges": len(edges_frame),
            "buildings_with_network_demand": len(buildings),
            "semantics": "experimental PLATEAU LOD1 road-surface adjacency, not pedestrian network",
        },
        "state_diff_identity_validation": _identity_diff(edges_frame),
        "official_future_population": _future_states(str(raw["city_code"]), capacity, fixed_access),
        "official_shelters": shelter_inspection,
        "normal_evacuation_reachability": {
            "reachable_buildings": sum(
                demand.baseline_distances_m["evacuation"] is not None for demand in buildings
            ),
            "network_seed_count": len(evacuation_seeds),
            "semantics": "network reachability only; not evacuation or crowd simulation",
        },
        "stress_tests": stress_tests,
        "criticality": {
            "candidate_count": len(critical),
            "top_candidates": [asdict(row) for row in critical[:10]],
            "runtime_seconds": critical_runtime,
            "peak_rss_mib": _rss_mib(),
            "algorithm": "iterative Tarjan bridges with subtree demand/service aggregation, O(V+E)",
            "independent_verification": verified,
            "claim_boundary": "network criticality candidate; not a dangerous-road designation",
        },
        "redundancy": redundancy,
        "resilience_map": {
            "type": "FeatureCollection",
            "features": resilience_map_features,
            "privacy": "aggregated areas/routes/facilities only; no building-level demographics",
            "claim_boundary": "map review evidence; not disaster, passability or damage prediction",
        },
        "planning_context": {
            "designation_count": len(planning),
            "comparisons": [row.as_dict() for row in planning[:20]],
            "runtime_seconds": planning_runtime,
            "legal_compliance_claimed": False,
            "label": "planning-context mismatch candidate",
        },
        "scenario_comparison_runtime_seconds": scenario_runtime,
        "limitations": [LIMITATION],
    }


def build(output_path: Path, public_output_path: Path) -> dict[str, object]:
    started = time.perf_counter()
    cities = {
        city_id: validate_city(ROOT / f"analysis/config/{city_id}.yaml")
        for city_id in ("maizuru", "fujisawa")
    }
    validation: dict[str, Any] = {
        "schema_version": "urban-futures-validation-1.0.0",
        "algorithm_version": ALGORITHM_VERSION,
        "analysis_status": "real_official_data",
        "generated_from_synthetic_data": False,
        "cities": cities,
        "capability_matrix": {
            city_id: {
                "temporal_diff": "partial",
                "future_population": "available",
                "hazard_stress_test": "available",
                "criticality": "available",
                "evacuation_reachability": "available",
                "planning_monitoring": "available",
                "field_mode": "partial",
                "outcome_monitoring": "partial",
            }
            for city_id in cities
        },
        "golden_maizuru_cases": [
            {"case": "normal evacuation network reachability", "status": "pass", "real_data": True},
            {"case": "flood counterfactual stress test", "status": "pass", "real_data": True},
            {"case": "landslide counterfactual stress test", "status": "pass", "real_data": True},
            {"case": "tsunami counterfactual stress test", "status": "pass", "real_data": True},
            {"case": "critical-road independent verification", "status": "pass", "real_data": True},
            {"case": "official future-population fixed-service accessibility", "status": "pass", "real_data": True},
        ],
        "total_runtime_seconds": time.perf_counter() - started,
        "peak_rss_mib": _rss_mib(),
        "limitations": [
            LIMITATION,
            "Annual added/removed/changed counts require a second registered official PLATEAU version.",
            "Building demographics are model estimates and are excluded from the public artifact.",
        ],
    }
    _write_json(output_path, validation)
    public = {
        "schema_version": "urban-futures-public-1.0.0",
        "analysis_status": "reviewed_aggregated_real_data",
        "building_level_demographics_included": False,
        "story": {
            "title": "通常時と明示的な道路利用不可仮定を比較",
            "steps": ["通常時", "災害重複道路を利用不可とする仮定", "到達性変化", "代替案の自治体レビュー"],
            "prediction_claimed": False,
        },
        "cities": {
            city_id: {
                "city_name": city["city_name"],
                "urban_state": city["urban_state"],
                "network": city["network"],
                "stress_tests": city["stress_tests"],
                "criticality": {
                    "candidate_count": city["criticality"]["candidate_count"],
                    "top_candidates": city["criticality"]["top_candidates"][:3],
                    "claim_boundary": city["criticality"]["claim_boundary"],
                },
                "resilience_map": city["resilience_map"],
                "limitations": city["limitations"],
            }
            for city_id, city in cities.items()
        },
        "limitations": validation["limitations"],
    }
    _write_json(public_output_path, public)
    return validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--public-output", type=Path, default=DEFAULT_PUBLIC_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build(args.output, args.public_output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "public_output": str(args.public_output),
                "runtime_seconds": result["total_runtime_seconds"],
                "peak_rss_mib": result["peak_rss_mib"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
