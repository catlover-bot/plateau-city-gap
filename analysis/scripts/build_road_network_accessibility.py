"""Build real PLATEAU road-surface graph and building-origin network accessibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

import analysis.scripts.build_building_demographics as demographic_builder
from analysis.scripts.build_building_demographics import (
    ARCHIVE,
    ARCHIVE_SHA256,
    BORDER,
    DEEP_DIVE_MESH,
    _facilities,
)
from analysis.src.building_demographics import weighted_statistics
from analysis.src.network_verification import verify_shortest_path_certificate
from analysis.src.plateau_road_network import (
    ANALYSIS_CRS,
    EXPERIMENTAL_GRAPH_METHOD,
    build_surface_adjacency_graph,
    multi_source_shortest_paths,
    read_road_surfaces,
    reconstruct_route,
    snap_points_to_surfaces,
)
from analysis.src.spatial import boundary_from_plateau

ROOT = Path(__file__).resolve().parents[2]
BUILDING_PARQUET = ROOT / "analysis/outputs/real/maizuru_building_demographics.parquet"
BUILDING_SUMMARY = ROOT / "analysis/outputs/real/maizuru_building_demographics_summary.json"
BUILDING_DETAIL = ROOT / "analysis/outputs/real/maizuru_plateau_detail_meshes.csv"
NODE_PARQUET = ROOT / "analysis/outputs/real/maizuru_road_graph_nodes.parquet"
EDGE_PARQUET = ROOT / "analysis/outputs/real/maizuru_road_graph_edges.parquet"
ACCESS_PARQUET = ROOT / "analysis/outputs/real/maizuru_building_network_accessibility.parquet"
TRANSPORT_LABELS_PARQUET = (
    ROOT / "analysis/outputs/real/maizuru_transport_network_labels.parquet"
)
MEDICAL_LABELS_PARQUET = ROOT / "analysis/outputs/real/maizuru_medical_network_labels.parquet"
MESH_OUTPUT = ROOT / "analysis/outputs/real/maizuru_network_accessibility_meshes.csv"
SUMMARY_OUTPUT = ROOT / "analysis/outputs/real/maizuru_road_network_summary.json"
EVIDENCE_OUTPUT = ROOT / "analysis/outputs/real/maizuru_network_deep_dive_evidence.json"

TOPOLOGY_TOLERANCE_M = 0.05
OFFICIAL_GENERATOR_URL = (
    "https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator"
)
OFFICIAL_GENERATOR_REVIEWED_COMMIT = "5f8d7662a01f58761c98bade02fd065884679b42"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_value(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _software_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"commit": commit, "worktree_dirty": dirty}


def _graph_version() -> tuple[str, str]:
    config = {
        "method": EXPERIMENTAL_GRAPH_METHOD,
        "archive_sha256": ARCHIVE_SHA256,
        "analysis_crs": ANALYSIS_CRS,
        "topology_tolerance_m": TOPOLOGY_TOLERANCE_M,
    }
    serialized = json.dumps(config, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    return f"exp-{digest[:16]}", digest


def _origins(buildings: pd.DataFrame) -> gpd.GeoDataFrame:
    unique = buildings.sort_values(["gml_id", "mesh_code"]).drop_duplicates("gml_id")
    return gpd.GeoDataFrame(
        unique[["gml_id"]].reset_index(drop=True),
        geometry=gpd.points_from_xy(unique["longitude"], unique["latitude"]),
        crs="EPSG:4326",
    ).to_crs(ANALYSIS_CRS)


def _facility_points(
    facilities: dict[str, gpd.GeoDataFrame], key: str
) -> gpd.GeoDataFrame:
    source = facilities[key].to_crs(ANALYSIS_CRS).reset_index(drop=True).copy()
    if key == "transport":
        source["facility_type"] = source["type"].astype(str)
    else:
        source["facility_type"] = "medical"
    source["facility_name"] = source["name"].astype(str)
    source["facility_id"] = [
        f"{facility_type}::{index:04d}::{name}"
        for index, (facility_type, name) in enumerate(
            zip(source["facility_type"], source["facility_name"], strict=True)
        )
    ]
    return gpd.GeoDataFrame(
        source[["facility_id", "facility_name", "facility_type", "geometry"]],
        geometry="geometry",
        crs=ANALYSIS_CRS,
    )


def _network_access(
    building_snap: pd.DataFrame,
    routing: pd.DataFrame,
    *,
    prefix: str,
) -> pd.DataFrame:
    renamed = routing.rename(
        columns={
            "network_to_destination_distance_m": f"network_to_{prefix}_from_node_m",
            "destination_id": f"nearest_network_{prefix}_id",
            "destination_name": f"nearest_network_{prefix}_name",
            "predecessor_node_id": f"{prefix}_predecessor_node_id",
            "predecessor_edge_id": f"{prefix}_predecessor_edge_id",
        }
    )
    result = building_snap.merge(renamed, on="node_id", how="left", validate="many_to_one")
    result[f"nearest_network_{prefix}_distance_m"] = (
        result["origin_to_node_distance_m"]
        + result[f"network_to_{prefix}_from_node_m"]
    )
    return result


def _mesh_metrics(
    demographics: pd.DataFrame,
    access: pd.DataFrame,
    euclidean_detail: pd.DataFrame,
) -> pd.DataFrame:
    detailed = demographics.merge(access, on="gml_id", how="left", validate="many_to_one")
    rows: list[dict[str, Any]] = []
    for mesh_code, group in detailed.groupby("mesh_code", sort=True):
        transport = weighted_statistics(
            group["nearest_network_transport_distance_m"],
            group["estimated_elderly_population"],
        )
        medical = weighted_statistics(
            group["nearest_network_medical_distance_m"],
            group["estimated_elderly_population"],
        )
        total_weight = float(group["estimated_elderly_population"].sum())
        transport_weight = float(
            group.loc[
                group["nearest_network_transport_distance_m"].notna(),
                "estimated_elderly_population",
            ].sum()
        )
        medical_weight = float(
            group.loc[
                group["nearest_network_medical_distance_m"].notna(),
                "estimated_elderly_population",
            ].sum()
        )
        rows.append(
            {
                "mesh_code": mesh_code,
                "network_transport_weighted_mean_distance_m": transport["mean"],
                "network_transport_weighted_median_distance_m": transport["median"],
                "network_transport_weighted_p90_distance_m": transport["p90"],
                "network_medical_weighted_mean_distance_m": medical["mean"],
                "network_medical_weighted_median_distance_m": medical["median"],
                "network_medical_weighted_p90_distance_m": medical["p90"],
                "transport_elderly_weight_coverage": (
                    transport_weight / total_weight if total_weight > 0 else np.nan
                ),
                "medical_elderly_weight_coverage": (
                    medical_weight / total_weight if total_weight > 0 else np.nan
                ),
                "network_reachable_buildings_transport": int(
                    group.loc[group["nearest_network_transport_distance_m"].notna(), "gml_id"].nunique()
                ),
                "network_reachable_buildings_medical": int(
                    group.loc[group["nearest_network_medical_distance_m"].notna(), "gml_id"].nunique()
                ),
            }
        )
    result = pd.DataFrame(rows).merge(
        euclidean_detail,
        on="mesh_code",
        how="left",
        validate="one_to_one",
    )
    result["network_minus_building_euclidean_transport_m"] = (
        result["network_transport_weighted_mean_distance_m"]
        - result["weighted_mean_transport_distance"]
    )
    result["network_minus_building_euclidean_medical_m"] = (
        result["network_medical_weighted_mean_distance_m"]
        - result["weighted_mean_medical_distance"]
    )
    result["network_transport_detour_ratio"] = (
        result["network_transport_weighted_mean_distance_m"]
        / result["weighted_mean_transport_distance"]
    )
    result["network_medical_detour_ratio"] = (
        result["network_medical_weighted_mean_distance_m"]
        / result["weighted_mean_medical_distance"]
    )
    result["network_metric_status"] = "available"
    full_coverage = result[
        ["transport_elderly_weight_coverage", "medical_elderly_weight_coverage"]
    ].min(axis=1)
    result.loc[full_coverage.lt(1 - 1e-12), "network_metric_status"] = "partial"
    result.loc[full_coverage.le(0), "network_metric_status"] = "unavailable"
    return result


def _evidence(
    demographics: pd.DataFrame,
    access: pd.DataFrame,
    nodes: gpd.GeoDataFrame,
    transport_routing: pd.DataFrame,
    medical_routing: pd.DataFrame,
    graph_version: str,
) -> dict[str, Any]:
    deep = demographics.loc[demographics["mesh_code"].eq(DEEP_DIVE_MESH)].copy()
    target = deep.sort_values(
        ["estimated_elderly_population", "gml_id"], ascending=[False, True]
    ).iloc[0]
    snapped = access.set_index("gml_id").loc[target["gml_id"]]
    node_id = str(snapped["node_id"])
    node_lookup = nodes.set_index("node_id")

    def route(routing: pd.DataFrame, prefix: str) -> dict[str, Any]:
        route_nodes, route_edges = reconstruct_route(routing, node_id)
        road_ids = [str(node_lookup.loc[value, "gml_id"]) for value in route_nodes]
        return {
            "destination_id": snapped[f"nearest_network_{prefix}_id"],
            "destination_name": snapped[f"nearest_network_{prefix}_name"],
            "distance_m": snapped[f"nearest_network_{prefix}_distance_m"],
            "road_graph_node_count": len(route_nodes),
            "road_graph_edge_count": len(route_edges),
            "road_gml_ids": list(dict.fromkeys(road_ids)),
            "route_node_ids": route_nodes,
            "route_edge_ids": route_edges,
        }

    return {
        "interpretation": (
            "Experimental PLATEAU LOD1 road-surface adjacency path; not a validated pedestrian "
            "network or walking route."
        ),
        "graph_version": graph_version,
        "building": {
            "gml_id": target["gml_id"],
            "mesh_code": target["mesh_code"],
            "estimated_population": target["estimated_population"],
            "estimated_elderly_population": target["estimated_elderly_population"],
            "population_source_year": target["source_population_year"],
            "origin_method": target["origin_method"],
        },
        "snap": {
            "road_surface_id": snapped["surface_id"],
            "road_graph_node_id": node_id,
            "road_surface_distance_m": snapped["road_surface_distance_m"],
            "origin_to_graph_node_distance_m": snapped["origin_to_node_distance_m"],
            "method": snapped["snap_method"],
        },
        "transport": route(transport_routing, "transport"),
        "medical": route(medical_routing, "medical"),
        "algorithm": "deterministic undirected multi-source Dijkstra",
        "distance_component": "edge length plus origin and destination node connectors",
    }


def main() -> None:
    global ACCESS_PARQUET, ANALYSIS_CRS, ARCHIVE, ARCHIVE_SHA256, BORDER, BUILDING_DETAIL
    global BUILDING_PARQUET, BUILDING_SUMMARY, DEEP_DIVE_MESH, EDGE_PARQUET
    global EVIDENCE_OUTPUT, MEDICAL_LABELS_PARQUET, MESH_OUTPUT, NODE_PARQUET
    global SUMMARY_OUTPUT, TRANSPORT_LABELS_PARQUET

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--city-id", default="26202")
    parser.add_argument("--city-name", default="舞鶴市")
    parser.add_argument("--building-parquet", type=Path, default=BUILDING_PARQUET)
    parser.add_argument("--building-summary", type=Path, default=BUILDING_SUMMARY)
    parser.add_argument("--building-detail", type=Path, default=BUILDING_DETAIL)
    parser.add_argument("--border", type=Path, default=BORDER)
    parser.add_argument("--stations", type=Path, default=demographic_builder.STATIONS)
    parser.add_argument("--bus-stops", type=Path, default=demographic_builder.BUS_STOPS)
    parser.add_argument("--medical", type=Path, default=demographic_builder.MEDICAL)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis/outputs/real")
    parser.add_argument("--output-prefix", default="maizuru")
    parser.add_argument("--analysis-crs", default=ANALYSIS_CRS)
    parser.add_argument("--archive-sha256")
    parser.add_argument("--expected-road-count", type=int, default=15_684)
    parser.add_argument("--deep-dive-mesh", default=DEEP_DIVE_MESH)
    args = parser.parse_args()

    ARCHIVE = args.archive
    BORDER = args.border
    BUILDING_PARQUET = args.building_parquet
    BUILDING_SUMMARY = args.building_summary
    BUILDING_DETAIL = args.building_detail
    ANALYSIS_CRS = args.analysis_crs
    DEEP_DIVE_MESH = args.deep_dive_mesh
    prefix = args.output_prefix
    output = args.output_dir
    NODE_PARQUET = output / f"{prefix}_road_graph_nodes.parquet"
    EDGE_PARQUET = output / f"{prefix}_road_graph_edges.parquet"
    ACCESS_PARQUET = output / f"{prefix}_building_network_accessibility.parquet"
    TRANSPORT_LABELS_PARQUET = output / f"{prefix}_transport_network_labels.parquet"
    MEDICAL_LABELS_PARQUET = output / f"{prefix}_medical_network_labels.parquet"
    MESH_OUTPUT = output / f"{prefix}_network_accessibility_meshes.csv"
    SUMMARY_OUTPUT = output / f"{prefix}_road_network_summary.json"
    EVIDENCE_OUTPUT = output / f"{prefix}_network_deep_dive_evidence.json"
    output.mkdir(parents=True, exist_ok=True)

    demographic_builder.ARCHIVE = ARCHIVE
    demographic_builder.BORDER = BORDER
    demographic_builder.STATIONS = args.stations
    demographic_builder.BUS_STOPS = args.bus_stops
    demographic_builder.MEDICAL = args.medical
    demographic_builder.ANALYSIS_CRS = ANALYSIS_CRS

    started_total = time.perf_counter()
    timings: dict[str, float] = {}
    building_summary = json.loads(BUILDING_SUMMARY.read_text(encoding="utf-8"))
    ARCHIVE_SHA256 = args.archive_sha256 or building_summary["provenance"][
        "dataset_archive_sha256"
    ]
    if _sha256(ARCHIVE) != ARCHIVE_SHA256:
        raise ValueError("PLATEAU archive hash does not match the audited dataset")
    if not BUILDING_PARQUET.exists():
        raise FileNotFoundError(
            f"Run analysis.scripts.build_building_demographics first: {BUILDING_PARQUET}"
        )
    demographics = pd.read_parquet(BUILDING_PARQUET)
    euclidean_detail = pd.read_csv(BUILDING_DETAIL, dtype={"mesh_code": str})

    started = time.perf_counter()
    road_surfaces = read_road_surfaces(ARCHIVE).to_crs(ANALYSIS_CRS)
    timings["road_parse_seconds"] = time.perf_counter() - started
    if len(road_surfaces) != args.expected_road_count:
        raise ValueError(
            f"Expected {args.expected_road_count:,} real LOD1 road surfaces, "
            f"got {len(road_surfaces):,}"
        )

    started = time.perf_counter()
    nodes, edges, graph_report = build_surface_adjacency_graph(
        road_surfaces, tolerance_m=TOPOLOGY_TOLERANCE_M
    )
    graph_version, config_hash = _graph_version()
    nodes["graph_version"] = graph_version
    edges["graph_version"] = graph_version
    timings["graph_build_seconds"] = time.perf_counter() - started
    nodes.to_parquet(NODE_PARQUET, index=False)
    edges.to_parquet(EDGE_PARQUET, index=False)

    started = time.perf_counter()
    origins = _origins(demographics)
    building_snap = snap_points_to_surfaces(
        origins, road_surfaces, nodes, id_column="gml_id"
    )
    boundary = boundary_from_plateau(
        gpd.read_file(BORDER).to_crs("EPSG:4326"),
        city_code=args.city_id,
        city_name=args.city_name,
    )
    facilities = _facilities(boundary)
    transport = _facility_points(facilities, "transport")
    medical = _facility_points(facilities, "medical")
    transport_snap = snap_points_to_surfaces(
        transport, road_surfaces, nodes, id_column="facility_id"
    ).merge(
        pd.DataFrame(transport.drop(columns="geometry")),
        on="facility_id",
        how="left",
        validate="one_to_one",
    )
    medical_snap = snap_points_to_surfaces(
        medical, road_surfaces, nodes, id_column="facility_id"
    ).merge(
        pd.DataFrame(medical.drop(columns="geometry")),
        on="facility_id",
        how="left",
        validate="one_to_one",
    )
    timings["snap_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    transport_routing = multi_source_shortest_paths(
        nodes,
        edges,
        transport_snap,
        destination_id_column="facility_id",
        destination_name_column="facility_name",
    )
    medical_routing = multi_source_shortest_paths(
        nodes,
        edges,
        medical_snap,
        destination_id_column="facility_id",
        destination_name_column="facility_name",
    )
    transport_routing.to_parquet(TRANSPORT_LABELS_PARQUET, index=False)
    medical_routing.to_parquet(MEDICAL_LABELS_PARQUET, index=False)
    audit_samples = (
        demographics.sort_values(
            ["estimated_elderly_population", "gml_id"], ascending=[False, True]
        )
        .drop_duplicates("gml_id")
        .loc[:, ["gml_id", "estimated_elderly_population"]]
        .merge(
            building_snap[["gml_id", "node_id", "origin_to_node_distance_m"]],
            on="gml_id",
            how="left",
            validate="one_to_one",
        )
        .drop_duplicates("node_id")
        .head(5)
    )
    audit_node_ids = audit_samples["node_id"].astype(str).tolist()
    transport_certificate = verify_shortest_path_certificate(
        edges,
        transport_snap,
        transport_routing,
        destination_id_column="facility_id",
        destination_name_column="facility_name",
        sample_node_ids=audit_node_ids,
    )
    medical_certificate = verify_shortest_path_certificate(
        edges,
        medical_snap,
        medical_routing,
        destination_id_column="facility_id",
        destination_name_column="facility_name",
        sample_node_ids=audit_node_ids,
    )
    if not transport_certificate["certified"] or not medical_certificate["certified"]:
        raise ValueError("Independent shortest-path certificate failed")
    transport_access = _network_access(building_snap, transport_routing, prefix="transport")
    medical_columns = [
        "gml_id",
        "network_to_medical_from_node_m",
        "nearest_network_medical_id",
        "nearest_network_medical_name",
        "medical_predecessor_node_id",
        "medical_predecessor_edge_id",
        "nearest_network_medical_distance_m",
    ]
    medical_access = _network_access(building_snap, medical_routing, prefix="medical")
    access = transport_access.merge(
        medical_access[medical_columns], on="gml_id", how="left", validate="one_to_one"
    )
    access["graph_version"] = graph_version
    access["graph_method"] = EXPERIMENTAL_GRAPH_METHOD
    access["route_semantics"] = "road_surface_adjacency_not_validated_pedestrian"
    access.to_parquet(ACCESS_PARQUET, index=False)
    timings["routing_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    mesh_metrics = _mesh_metrics(demographics, access, euclidean_detail)
    mesh_metrics.to_csv(MESH_OUTPUT, index=False)
    evidence = _evidence(
        demographics,
        access,
        nodes,
        transport_routing,
        medical_routing,
        graph_version,
    )
    evidence["provenance"] = {
        "plateau_archive_sha256": ARCHIVE_SHA256,
        "building_demographics_summary_sha256": _sha256(BUILDING_SUMMARY),
        "graph_config_hash": config_hash,
        "analysis_crs": ANALYSIS_CRS,
    }
    _write_json(EVIDENCE_OUTPUT, evidence)
    timings["aggregation_seconds"] = time.perf_counter() - started

    unique_euclidean = demographics.sort_values(["gml_id", "mesh_code"]).drop_duplicates("gml_id")
    comparison = access.merge(
        unique_euclidean[
            [
                "gml_id",
                "nearest_public_transport_distance_m",
                "nearest_medical_distance_m",
            ]
        ],
        on="gml_id",
        how="left",
        validate="one_to_one",
    )
    transport_violation = comparison["nearest_network_transport_distance_m"].lt(
        comparison["nearest_public_transport_distance_m"] - 1e-6
    )
    medical_violation = comparison["nearest_network_medical_distance_m"].lt(
        comparison["nearest_medical_distance_m"] - 1e-6
    )
    if transport_violation.any() or medical_violation.any():
        raise ValueError("Network path is shorter than straight-line facility distance")

    timings["total_seconds"] = time.perf_counter() - started_total
    report = {
        "schema_version": 1,
        "graph": {**graph_report, "graph_version": graph_version},
        "official_generator_boundary": {
            "repository": OFFICIAL_GENERATOR_URL,
            "reviewed_commit": OFFICIAL_GENERATOR_REVIEWED_COMMIT,
            "execution_status": "not_run_windows_gui_unavailable",
            "adapter_implemented": True,
            "experimental_graph_claimed_as_official": False,
        },
        "coverage": {
            "strict_demographic_buildings": int(demographics["gml_id"].nunique()),
            "transport_reachable_buildings": int(
                access["nearest_network_transport_distance_m"].notna().sum()
            ),
            "medical_reachable_buildings": int(
                access["nearest_network_medical_distance_m"].notna().sum()
            ),
            "building_to_surface_snap_m": {
                "median": building_snap["road_surface_distance_m"].median(),
                "p90": building_snap["road_surface_distance_m"].quantile(0.9),
                "p95": building_snap["road_surface_distance_m"].quantile(0.95),
                "maximum": building_snap["road_surface_distance_m"].max(),
            },
            "building_to_graph_node_connector_m": {
                "median": building_snap["origin_to_node_distance_m"].median(),
                "p90": building_snap["origin_to_node_distance_m"].quantile(0.9),
                "p95": building_snap["origin_to_node_distance_m"].quantile(0.95),
                "maximum": building_snap["origin_to_node_distance_m"].max(),
            },
            "mesh_status_counts": mesh_metrics["network_metric_status"].value_counts().to_dict(),
        },
        "facilities": {
            "transport": len(transport),
            "medical": len(medical),
            "policy": "city_baseline_including_uncertain_medical",
        },
        "validation": {
            "positive_edge_lengths": bool(edges["length_m"].gt(0).all()),
            "referential_integrity": True,
            "network_below_euclidean_transport_records": int(transport_violation.sum()),
            "network_below_euclidean_medical_records": int(medical_violation.sum()),
            "deep_dive_mesh": DEEP_DIVE_MESH,
            "audit_sample_buildings": audit_samples.to_dict(orient="records"),
            "transport_shortest_path_certificate": transport_certificate,
            "medical_shortest_path_certificate": medical_certificate,
        },
        "privacy": building_summary["privacy"],
        "provenance": {
            "plateau_archive_sha256": ARCHIVE_SHA256,
            "building_demographics_summary_sha256": _sha256(BUILDING_SUMMARY),
            "graph_config_hash": config_hash,
            "analysis_crs": ANALYSIS_CRS,
            "software": _software_state(),
            "generated_at": datetime.now(UTC).isoformat(),
        },
        "performance": {
            **{key: round(value, 3) for key, value in timings.items()},
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "node_parquet_bytes": NODE_PARQUET.stat().st_size,
            "edge_parquet_bytes": EDGE_PARQUET.stat().st_size,
            "access_parquet_bytes": ACCESS_PARQUET.stat().st_size,
            "transport_labels_parquet_bytes": TRANSPORT_LABELS_PARQUET.stat().st_size,
            "medical_labels_parquet_bytes": MEDICAL_LABELS_PARQUET.stat().st_size,
            "mesh_csv_bytes": MESH_OUTPUT.stat().st_size,
        },
        "limitations": [
            "The experimental graph is not official RoadNetwork Generator output.",
            "Road-space mode and pedestrian permission are unknown for every fallback edge.",
            "Representative-point links approximate travel through each LOD1 surface.",
            "A validated walking route must not be inferred from this result.",
            "Terrain components are added only after DEM-to-edge coverage validation.",
        ],
    }
    _write_json(SUMMARY_OUTPUT, report)
    print(json.dumps(_json_value(report["graph"]), ensure_ascii=False))
    print(json.dumps(_json_value(report["coverage"]), ensure_ascii=False))
    print(json.dumps(_json_value(report["performance"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
