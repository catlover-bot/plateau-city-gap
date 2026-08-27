"""Build real-data hazard, criticality and future-allocation sensitivity evidence."""

from __future__ import annotations

import argparse
import json
import math
import resource
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from shapely.geometry import mapping

from analysis.scripts.build_urban_futures_validation import (
    REAL,
    _building_inputs,
    _facility_seeds,
    _network_edges,
    _shelter_seeds,
)
from analysis.src.model_validation import read_osm_overpass_reference
from analysis.src.sensitivity_validation import (
    criticality_robustness,
    hazard_assumption_edge_sets,
)
from analysis.src.urban_resilience import (
    BuildingDemand,
    multi_source_distances,
    network_criticality_candidates,
    run_network_stress_test,
)
from backend.citygap_platform.ingestion.future_population import (
    OfficialFuturePopulationAdapter,
    allocate_projection_to_buildings,
    future_accessibility_summary,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REAL / "validation/sensitivity_validation.json"
PUBLIC_OUTPUT = ROOT / "frontend/public/data/validation/sensitivity_validation.json"
CRITICAL_MAP = ROOT / "frontend/public/data/validation/criticality_map_audit.geojson"
ALGORITHM_VERSION = "citygap-assumption-sensitivity-v1.0.0"
OSM = {
    "maizuru": (
        ROOT / "data/raw/osm_reference/maizuru-20260827-overpass.json",
        "1308277a253ca2cc4fb7b8d5883a78b7430be66a385210307092f0ee6401d71e",
    ),
    "fujisawa": (
        ROOT / "data/raw/osm_reference/fujisawa-20260827-overpass.json",
        "1e5b637e583ca340cc1d29d5a382b4f594b5e42b68db7b6ddf873cd94031f9e2",
    ),
}


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) or not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _bridge_edge_ids(adjacency: dict[str, list[tuple[str, float, str]]]) -> set[str]:
    """Iterative topology-only Tarjan bridge set for the OSM reference graph."""

    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    timer = 0
    bridges: set[str] = set()
    for start in sorted(adjacency):
        if start in discovery:
            continue
        discovery[start] = low[start] = timer
        timer += 1
        stack: list[tuple[str, str | None, str | None, int]] = [(start, None, None, 0)]
        while stack:
            node, parent, parent_edge, index = stack[-1]
            if index < len(adjacency[node]):
                neighbor, _length, edge_id = adjacency[node][index]
                stack[-1] = (node, parent, parent_edge, index + 1)
                if edge_id == parent_edge:
                    continue
                if neighbor not in discovery:
                    discovery[neighbor] = low[neighbor] = timer
                    timer += 1
                    stack.append((neighbor, node, edge_id, 0))
                else:
                    low[node] = min(low[node], discovery[neighbor])
                continue
            stack.pop()
            if parent is not None and parent_edge is not None:
                low[parent] = min(low[parent], low[node])
                if low[node] > discovery[parent]:
                    bridges.add(parent_edge)
    return bridges


def _critical_models(
    edges_frame: pd.DataFrame,
    nodes: pd.DataFrame,
    buildings: tuple[BuildingDemand, ...],
    service_seeds: dict[str, dict[str, float]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    edge_rows = _network_edges(edges_frame)
    largest_nodes = set(
        nodes.loc[nodes["component_id"].eq("component_0001"), "node_id"].astype(str)
    )
    strict_edges = tuple(
        edge for edge, relation in zip(edge_rows, edges_frame["topology_relation"], strict=True)
        if relation != "tolerance_bridge"
    )
    definitions = {
        "M1_baseline_tolerance_0_05m": (edge_rows, buildings),
        "M2_tolerance_0m_remove_bridge_edges": (strict_edges, buildings),
        "M3_largest_component_demand_only": (
            edge_rows,
            tuple(row for row in buildings if row.node_id in largest_nodes),
        ),
        "M4_origin_snap_max_50m": (
            edge_rows,
            tuple(row for row in buildings if row.connector_m <= 50),
        ),
        "M5_origin_snap_max_100m": (
            edge_rows,
            tuple(row for row in buildings if row.connector_m <= 100),
        ),
    }
    models: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, Any] = {}
    for model, (model_edges, model_buildings) in definitions.items():
        started = time.perf_counter()
        candidates = network_criticality_candidates(model_edges, model_buildings, service_seeds)
        models[model] = [asdict(row) for row in candidates]
        metadata[model] = {
            "edge_count": len(model_edges),
            "building_demand_count": len(model_buildings),
            "candidate_count": len(candidates),
            "runtime_seconds": time.perf_counter() - started,
        }
    return models, metadata


def _osm_reference_correspondence(
    city: str,
    analysis_crs: str,
    candidates: list[dict[str, Any]],
    edge_geometry: gpd.GeoDataFrame,
) -> dict[str, Any]:
    source, digest = OSM[city]
    started = time.perf_counter()
    graph = read_osm_overpass_reference(
        source,
        analysis_crs=analysis_crs,
        retrieval_date="2026-08-27",
        extract_source="pinned Overpass reference extract",
        source_sha256=digest,
    )
    reference_bridges = _bridge_edge_ids(graph.adjacency)
    reference_geometry = graph.edges.loc[
        graph.edges["edge_id"].isin(reference_bridges), ["edge_id", "geometry"]
    ].rename(columns={"edge_id": "reference_edge_id"})
    candidate_ids = [row["edge_id"] for row in candidates]
    source_geometry = edge_geometry.loc[
        edge_geometry["edge_id"].isin(candidate_ids), ["edge_id", "geometry"]
    ]
    if source_geometry.empty or reference_geometry.empty:
        correspondence_count = 0
        distance_summary = None
    else:
        nearest = gpd.sjoin_nearest(
            source_geometry,
            reference_geometry,
            how="left",
            max_distance=25,
            distance_col="distance_m",
        ).sort_values(["edge_id", "distance_m", "reference_edge_id"]).drop_duplicates("edge_id")
        matched = nearest["reference_edge_id"].notna()
        correspondence_count = int(matched.sum())
        distance_summary = {
            "median_m": float(nearest.loc[matched, "distance_m"].median()) if matched.any() else None,
            "p90_m": float(nearest.loc[matched, "distance_m"].quantile(0.90)) if matched.any() else None,
        }
    return {
        "reference_network": "openstreetmap_pinned_reference_network",
        "reference_semantics": "reference_network_not_ground_truth",
        "direct_edge_identity_comparable": False,
        "spatial_correspondence_rule": "primary edge within 25m of an OSM topology bridge candidate",
        "primary_candidate_count": len(candidates),
        "reference_topology_bridge_count": len(reference_bridges),
        "spatial_correspondence_count": correspondence_count,
        "spatial_correspondence_fraction": correspondence_count / max(len(candidates), 1),
        "distance_summary": distance_summary,
        "runtime_seconds": time.perf_counter() - started,
        "limitations": [
            "Nearby topology candidates are not the same edge identity or proof of correctness.",
            "OSM completeness and topology semantics differ from PLATEAU road surfaces.",
        ],
    }


def _future_sensitivity(
    city: str,
    city_code: str,
    capacity: pd.DataFrame,
    fixed_access: pd.DataFrame,
) -> dict[str, Any]:
    adapter = OfficialFuturePopulationAdapter(ROOT / "analysis/sources/official_future_population.csv")
    records = adapter.records(city_code)
    by_series: dict[str, dict[int, Any]] = {}
    for record in records:
        by_series.setdefault(record.projection_series, {})[record.year] = record
    comparison_year = 2040 if any(record.year == 2040 for record in records) else records[-1].year
    primary_record = next(record for record in records if record.year == comparison_year)
    demographics = pd.read_parquet(REAL / f"{city}_building_demographics.parquet")
    footprint_capacity = (
        demographics.groupby("gml_id", as_index=False)
        .agg(
            mesh_code=("mesh_code", "first"),
            capacity_weight=("building_geometry_footprint_area_m2", "max"),
        )
        .rename(columns={"gml_id": "building_id"})
    )
    strict = allocate_projection_to_buildings(capacity, primary_record)
    footprint = allocate_projection_to_buildings(footprint_capacity, primary_record)
    strict_summary = future_accessibility_summary(strict, fixed_access)
    footprint_summary = future_accessibility_summary(footprint, fixed_access)
    source_summary = json.loads(
        (REAL / f"{city}_building_demographics_summary.json").read_text(encoding="utf-8")
    )["sensitivity"]
    fallback_count = int(
        (~demographics["allocation_weight_source"].eq("total_floor_area")).sum()
    )
    variants = {
        "strict_residential_floor_area": {
            "status": "available",
            "qualifying_records": len(demographics),
            "future_burden": strict_summary,
        },
        "residential_plus_mixed": {
            "status": "available_with_limitation",
            "qualifying_records": int(source_summary["residential_plus_mixed"]["records"]),
            "current_population_conservation": source_summary["residential_plus_mixed"],
            "future_burden": "NOT_AVAILABLE: added mixed-use buildings were not persisted with network accessibility; no burden was fabricated",
        },
        "strict_residential_footprint_area": {
            "status": "available",
            "qualifying_buildings": len(footprint_capacity),
            "future_burden": footprint_summary,
        },
        "mesh_fallback_handling": {
            "status": "available",
            "fallback_record_count": fallback_count,
            "rule": "equal-weight fallback only for a mesh with zero qualifying positive capacity",
            "observed_effect": "no_effect_no_fallback_records" if fallback_count == 0 else "see sensitivity output",
            "future_burden": strict_summary if fallback_count == 0 else "NOT_AVAILABLE",
        },
    }
    official_series_comparison: list[dict[str, Any]] = []
    series_names = sorted(by_series)
    if len(series_names) >= 2:
        common_years = sorted(set(by_series[series_names[0]]) & set(by_series[series_names[1]]))
        for year in common_years:
            scenarios = []
            for label, series_name in zip(("official_scenario_A", "official_scenario_B"), series_names[:2], strict=True):
                projection = by_series[series_name][year]
                allocation = allocate_projection_to_buildings(capacity, projection)
                scenarios.append(
                    {
                        "label": label,
                        "projection_series": series_name,
                        "publisher": projection.publisher,
                        "official_total_population": projection.total_population,
                        "official_age_65_plus": projection.age_65_plus,
                        "accessibility_burden": future_accessibility_summary(allocation, fixed_access),
                    }
                )
            official_series_comparison.append(
                {"year": year, "scenarios": scenarios, "best_projection_selected": False}
            )
    return {
        "comparison_year": comparison_year,
        "allocation_variants": variants,
        "official_series_same_year_comparison": official_series_comparison,
        "best_projection_selected": False,
        "semantics": "official scenarios under a fixed-service allocation model; not building-level predictions",
    }


def validate_city(city: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.perf_counter()
    config = yaml.safe_load((ROOT / f"analysis/config/{city}.yaml").read_text(encoding="utf-8"))
    analysis_crs = str(config["analysis_crs"])
    edges_frame = gpd.read_parquet(REAL / f"{city}_road_graph_edges.parquet")
    nodes = pd.read_parquet(REAL / f"{city}_road_graph_nodes.parquet")
    edge_rows = _network_edges(edges_frame)
    transport_seeds = _facility_seeds(city, "transport")
    medical_seeds = _facility_seeds(city, "medical")
    shelter_seeds, shelter_inspection = _shelter_seeds(
        ROOT / f"analysis/config/{city}.yaml", nodes
    )
    evacuation_distances = multi_source_distances(edge_rows, shelter_seeds)
    buildings, capacity, fixed_access = _building_inputs(city, evacuation_distances)
    service_seeds = {
        "medical": medical_seeds,
        "transport_hub": transport_seeds,
        "evacuation": shelter_seeds,
    }
    critical_models, critical_metadata = _critical_models(
        edges_frame, nodes, buildings, service_seeds
    )
    robust = criticality_robustness(critical_models)
    baseline_candidates = critical_models["M1_baseline_tolerance_0_05m"]
    reference_comparison = _osm_reference_correspondence(
        city, analysis_crs, baseline_candidates, edges_frame
    )

    critical_ids = {item["edge_id"] for item in baseline_candidates}
    hazards = pd.read_parquet(REAL / f"{city}_road_hazard_context.parquet")
    sensitivity_matrix: list[dict[str, Any]] = []
    stable_findings: dict[str, Any] = {}
    capacity_by_building = capacity.set_index("building_id")
    for hazard_type in sorted(hazards["hazard_type"].dropna().unique()):
        hazard_rows = hazards.loc[hazards["hazard_type"].eq(hazard_type)].copy()
        rule_sets = hazard_assumption_edge_sets(
            hazard_rows, edges_frame, nodes, critical_ids
        )
        disconnected_by_model: dict[str, set[str]] = {}
        for rule_key, rule in rule_sets.items():
            closed = rule["closed_edges"]
            result = run_network_stress_test(edge_rows, buildings, service_seeds, closed)
            medical_distances = multi_source_distances(edge_rows, medical_seeds, closed)
            disconnected = {
                building.building_id
                for building in buildings
                if building.baseline_distances_m.get("medical") is not None
                and not math.isfinite(medical_distances.get(building.node_id, math.inf))
            }
            disconnected_by_model[rule_key] = disconnected
            metrics = asdict(result)
            sensitivity_matrix.append(
                {
                    "city_id": city,
                    "hazard_type": hazard_type,
                    "assumption": rule_key,
                    "rule": rule["rule"],
                    "validated_parameter_range": rule["validated_parameter_range"],
                    "affected_edges": len(closed),
                    "disconnected_buildings": metrics["service_metrics"]["medical"]["newly_unreachable_buildings"],
                    "estimated_elderly_affected": metrics["service_metrics"]["medical"]["estimated_elderly_population_disconnected"],
                    "medical_reachability": metrics["service_metrics"]["medical"]["scenario_reachable_buildings"],
                    "shelter_reachability": metrics["service_metrics"]["evacuation"]["scenario_reachable_buildings"],
                    "component_fragmentation": metrics["component_fragmentation_increase"],
                    "probability_claimed": False,
                }
            )
        occurrence = Counter(
            building_id for values in disconnected_by_model.values() for building_id in values
        )
        stable_ids = {key for key, value in occurrence.items() if value >= 3}
        unstable_ids = {key for key, value in occurrence.items() if value == 1}
        stable_capacity = capacity_by_building.reindex(sorted(stable_ids)).dropna(how="all")
        stable_mesh = (
            stable_capacity.groupby("mesh_code", as_index=False)
            .agg(
                affected_buildings=("estimated_population", "size"),
                estimated_elderly_affected=("estimated_elderly_population", "sum"),
            )
            .sort_values(["affected_buildings", "mesh_code"], ascending=[False, True])
            .head(20)
        )
        stable_findings[hazard_type] = {
            "assumption_stable_impact_candidate_buildings": len(stable_ids),
            "single_assumption_only_buildings": len(unstable_ids),
            "stability_rule": "medical disconnection repeated in at least 3 of 5 bounded closure models",
            "probability_or_risk_claimed": False,
            "top_aggregate_mesh_candidates": stable_mesh.to_dict("records"),
        }

    audit_features: list[dict[str, Any]] = []
    geometry_by_edge = edges_frame.set_index("edge_id").geometry
    for item in [row for row in robust if row["edge_id"] in geometry_by_edge.index][:30]:
        geometry = gpd.GeoSeries([geometry_by_edge.loc[item["edge_id"]]], crs=analysis_crs).to_crs("EPSG:4326").iloc[0]
        center = geometry.centroid
        audit_features.append(
            {
                "type": "Feature",
                "properties": {
                    **item,
                    "city_id": city,
                    "candidate_label": "network criticality candidate",
                    "review_status": "not_reviewed",
                    "automatic_correctness_claimed": False,
                    "dangerous_road_claimed": False,
                    "web_map_context": f"https://www.openstreetmap.org/?mlat={center.y:.6f}&mlon={center.x:.6f}#map=19/{center.y:.6f}/{center.x:.6f}",
                },
                "geometry": mapping(geometry),
            }
        )
    future = _future_sensitivity(city, str(config["city_code"]), capacity, fixed_access)
    return (
        {
            "city_id": city,
            "city_name": config["city_name"],
            "network_version": str(edges_frame["graph_version"].iloc[0]),
            "hazard_assumption_matrix": sensitivity_matrix,
            "stress_test_findings": stable_findings,
            "criticality_sensitivity": {
                "models": critical_metadata,
                "robust_candidate_count": len(robust),
                "robust_candidates": robust[:100],
                "network_source_comparison": {
                    "official_plateau": "NOT_AVAILABLE",
                    "osm_reference": reference_comparison,
                },
                "magic_score_used": False,
            },
            "criticality_map_audit_count": len(audit_features),
            "future_population_sensitivity": future,
            "shelter_source": shelter_inspection,
            "validation_status": "internally_verified",
            "municipal_review": "not_reviewed",
            "field_validation": "awaiting_field_validation",
            "runtime_seconds": time.perf_counter() - started,
            "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "limitations": [
                "Sensitivity models are counterfactual assumptions, not hazard probabilities or passability forecasts.",
                "Criticality robustness is model-dependence evidence, not a dangerous-road designation.",
                "Building and elderly values are model estimates; public outputs contain aggregates only.",
            ],
        },
        audit_features,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", choices=["maizuru", "fujisawa", "all"], default="all")
    args = parser.parse_args()
    selected = ("maizuru", "fujisawa") if args.city == "all" else (args.city,)
    cities: dict[str, Any] = {}
    features: list[dict[str, Any]] = []
    started = time.perf_counter()
    for city in selected:
        result, city_features = validate_city(city)
        cities[city] = result
        features.extend(city_features)
    payload = {
        "schema_version": "sensitivity-validation-v1.0.0",
        "algorithm_version": ALGORITHM_VERSION,
        "cities": cities,
        "confidence_percentage_used": False,
        "total_runtime_seconds": time.perf_counter() - started,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(_json_value(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    PUBLIC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_OUTPUT.write_text(json.dumps(_json_value(payload), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    CRITICAL_MAP.write_text(
        json.dumps(_json_value({"type": "FeatureCollection", "features": features}), ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "cities": {key: {"hazard_models": len(value["hazard_assumption_matrix"]), "critical_models": value["criticality_sensitivity"]["models"]} for key, value in cities.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
