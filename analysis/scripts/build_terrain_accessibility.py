"""Attach official PLATEAU DEM terrain components to experimental network paths."""

from __future__ import annotations

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

from analysis.scripts.build_building_demographics import ARCHIVE, ARCHIVE_SHA256
from analysis.src.building_demographics import weighted_statistics
from analysis.src.plateau_terrain import (
    assign_dem_elevations,
    attach_edge_terrain,
    calculate_route_terrain,
)

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"
NODE_PARQUET = REAL / "maizuru_road_graph_nodes.parquet"
EDGE_PARQUET = REAL / "maizuru_road_graph_edges.parquet"
ACCESS_PARQUET = REAL / "maizuru_building_network_accessibility.parquet"
TRANSPORT_LABELS_PARQUET = REAL / "maizuru_transport_network_labels.parquet"
MEDICAL_LABELS_PARQUET = REAL / "maizuru_medical_network_labels.parquet"
DEMOGRAPHICS_PARQUET = REAL / "maizuru_building_demographics.parquet"
ROAD_SUMMARY = REAL / "maizuru_road_network_summary.json"
ROAD_EVIDENCE = REAL / "maizuru_network_deep_dive_evidence.json"

TERRAIN_NODE_PARQUET = REAL / "maizuru_road_graph_nodes_terrain.parquet"
TERRAIN_EDGE_PARQUET = REAL / "maizuru_road_graph_edges_terrain.parquet"
TERRAIN_ACCESS_PARQUET = REAL / "maizuru_building_terrain_accessibility.parquet"
MESH_OUTPUT = REAL / "maizuru_terrain_accessibility_meshes.csv"
SUMMARY_OUTPUT = REAL / "maizuru_terrain_network_summary.json"
EVIDENCE_OUTPUT = REAL / "maizuru_network_deep_dive_terrain.json"


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


def _prefixed_route_terrain(route: pd.DataFrame, prefix: str) -> pd.DataFrame:
    renamed = {
        column: f"{prefix}_{column}"
        for column in route.columns
        if column != "node_id"
    }
    return route.rename(columns=renamed)


def _mesh_metrics(demographics: pd.DataFrame, access: pd.DataFrame) -> pd.DataFrame:
    detailed = demographics.merge(access, on="gml_id", how="left", validate="many_to_one")
    rows: list[dict[str, Any]] = []
    for mesh_code, group in detailed.groupby("mesh_code", sort=True):
        total_weight = float(group["estimated_elderly_population"].sum())
        row: dict[str, Any] = {"mesh_code": mesh_code}
        for prefix in ("transport", "medical"):
            available = group[f"{prefix}_terrain_route_status"].eq("available")
            covered_weight = float(group.loc[available, "estimated_elderly_population"].sum())
            ascent = weighted_statistics(
                group[f"{prefix}_route_ascent_m"], group["estimated_elderly_population"]
            )
            descent = weighted_statistics(
                group[f"{prefix}_route_descent_m"], group["estimated_elderly_population"]
            )
            grade = weighted_statistics(
                group[f"{prefix}_maximum_observed_absolute_grade_percent"].where(available),
                group["estimated_elderly_population"],
            )
            row.update(
                {
                    f"{prefix}_terrain_elderly_weight_coverage": (
                        covered_weight / total_weight if total_weight > 0 else np.nan
                    ),
                    f"{prefix}_weighted_mean_ascent_m": ascent["mean"],
                    f"{prefix}_weighted_median_ascent_m": ascent["median"],
                    f"{prefix}_weighted_p90_ascent_m": ascent["p90"],
                    f"{prefix}_weighted_mean_descent_m": descent["mean"],
                    f"{prefix}_weighted_mean_maximum_grade_percent": grade["mean"],
                }
            )
        rows.append(row)
    result = pd.DataFrame(rows)
    minimum_coverage = result[
        ["transport_terrain_elderly_weight_coverage", "medical_terrain_elderly_weight_coverage"]
    ].min(axis=1)
    result["terrain_metric_status"] = "available"
    result.loc[minimum_coverage.lt(1 - 1e-12), "terrain_metric_status"] = "partial"
    result.loc[minimum_coverage.le(0), "terrain_metric_status"] = "unavailable"
    return result


def _route_evidence(
    base: dict[str, Any],
    nodes: pd.DataFrame,
    route_terrain: pd.DataFrame,
) -> dict[str, Any]:
    terrain = route_terrain.set_index("node_id")
    elevation = nodes.set_index("node_id")["elevation_m"]
    node_ids = [str(value) for value in base["route_node_ids"]]
    origin = terrain.loc[node_ids[0]]
    return {
        "terrain_route_status": origin["terrain_route_status"],
        "graph_edge_distance_m": origin["route_graph_length_m"],
        "terrain_covered_graph_length_m": origin["terrain_covered_graph_length_m"],
        "terrain_route_coverage": origin["terrain_route_coverage"],
        "ascent_m": origin["route_ascent_m"],
        "descent_m": origin["route_descent_m"],
        "observed_ascent_m": origin["observed_ascent_m"],
        "observed_descent_m": origin["observed_descent_m"],
        "maximum_observed_absolute_grade_percent": origin[
            "maximum_observed_absolute_grade_percent"
        ],
        "elevation_profile": [
            {"node_id": node_id, "elevation_m": elevation.get(node_id)} for node_id in node_ids
        ],
        "connector_terrain_status": "not_computed",
    }


def main() -> None:
    started_total = time.perf_counter()
    required = (
        NODE_PARQUET,
        EDGE_PARQUET,
        ACCESS_PARQUET,
        TRANSPORT_LABELS_PARQUET,
        MEDICAL_LABELS_PARQUET,
        DEMOGRAPHICS_PARQUET,
        ROAD_SUMMARY,
        ROAD_EVIDENCE,
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Run the road-network pipeline first; missing {missing}")
    if _sha256(ARCHIVE) != ARCHIVE_SHA256:
        raise ValueError("PLATEAU archive hash does not match the audited Maizuru dataset")

    nodes = gpd.read_parquet(NODE_PARQUET)
    edges = gpd.read_parquet(EDGE_PARQUET)
    access = pd.read_parquet(ACCESS_PARQUET)
    transport_routing = pd.read_parquet(TRANSPORT_LABELS_PARQUET)
    medical_routing = pd.read_parquet(MEDICAL_LABELS_PARQUET)
    demographics = pd.read_parquet(DEMOGRAPHICS_PARQUET)
    road_summary = json.loads(ROAD_SUMMARY.read_text(encoding="utf-8"))
    road_evidence = json.loads(ROAD_EVIDENCE.read_text(encoding="utf-8"))

    started = time.perf_counter()
    elevations, node_report = assign_dem_elevations(ARCHIVE, nodes)
    nodes = nodes.merge(elevations, on="node_id", how="left", validate="one_to_one")
    timings = {"dem_interpolation_seconds": time.perf_counter() - started}
    nodes.to_parquet(TERRAIN_NODE_PARQUET, index=False)

    started = time.perf_counter()
    edges, edge_report = attach_edge_terrain(nodes, edges)
    edges.to_parquet(TERRAIN_EDGE_PARQUET, index=False)
    transport_terrain = calculate_route_terrain(nodes, edges, transport_routing)
    medical_terrain = calculate_route_terrain(nodes, edges, medical_routing)
    terrain_access = access[["gml_id", "node_id", "graph_version"]].merge(
        _prefixed_route_terrain(transport_terrain, "transport"),
        on="node_id",
        how="left",
        validate="many_to_one",
    )
    terrain_access = terrain_access.merge(
        _prefixed_route_terrain(medical_terrain, "medical"),
        on="node_id",
        how="left",
        validate="many_to_one",
    )
    terrain_access["terrain_component_policy"] = (
        "separate_from_distance_connectors_excluded_no_routing_penalty"
    )
    terrain_access.to_parquet(TERRAIN_ACCESS_PARQUET, index=False)
    mesh_metrics = _mesh_metrics(demographics, terrain_access)
    mesh_metrics.to_csv(MESH_OUTPUT, index=False)
    timings["terrain_route_seconds"] = time.perf_counter() - started

    evidence = {
        "interpretation": (
            "PLATEAU DEM elevation components along the experimental road-surface adjacency "
            "path; not a validated pedestrian slope or walking-energy model."
        ),
        "graph_version": road_summary["graph"]["graph_version"],
        "building": road_evidence["building"],
        "transport": _route_evidence(
            road_evidence["transport"], nodes, transport_terrain
        ),
        "medical": _route_evidence(road_evidence["medical"], nodes, medical_terrain),
        "distance_terrain_separation": {
            "network_distance_source": "road-network artifact; unchanged",
            "terrain_source": "PLATEAU LOD1 DEM TIN endpoint interpolation",
            "routing_penalty_applied": False,
            "building_and_facility_connector_terrain": "not_computed",
        },
        "provenance": {
            "plateau_archive_sha256": ARCHIVE_SHA256,
            "road_network_summary_sha256": _sha256(ROAD_SUMMARY),
        },
    }
    _write_json(EVIDENCE_OUTPUT, evidence)

    timings["total_seconds"] = time.perf_counter() - started_total
    report = {
        "schema_version": 1,
        "graph_version": road_summary["graph"]["graph_version"],
        "route_semantics": road_summary["graph"]["route_semantics"],
        "pedestrian_network": False,
        "node_terrain": node_report,
        "edge_terrain": edge_report,
        "building_routes": {
            "transport_status_counts": terrain_access[
                "transport_terrain_route_status"
            ].value_counts(dropna=False).to_dict(),
            "medical_status_counts": terrain_access[
                "medical_terrain_route_status"
            ].value_counts(dropna=False).to_dict(),
            "mesh_status_counts": mesh_metrics["terrain_metric_status"].value_counts().to_dict(),
        },
        "validation": {
            "distance_columns_modified": False,
            "routing_penalty_applied": False,
            "negative_ascent_records": int(
                terrain_access["transport_observed_ascent_m"].lt(0).sum()
                + terrain_access["medical_observed_ascent_m"].lt(0).sum()
            ),
            "negative_descent_records": int(
                terrain_access["transport_observed_descent_m"].lt(0).sum()
                + terrain_access["medical_observed_descent_m"].lt(0).sum()
            ),
        },
        "provenance": {
            "plateau_archive_sha256": ARCHIVE_SHA256,
            "road_network_summary_sha256": _sha256(ROAD_SUMMARY),
            "analysis_crs": str(nodes.crs),
            "software": _software_state(),
            "generated_at": datetime.now(UTC).isoformat(),
        },
        "performance": {
            **{key: round(value, 3) for key, value in timings.items()},
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "terrain_node_parquet_bytes": TERRAIN_NODE_PARQUET.stat().st_size,
            "terrain_edge_parquet_bytes": TERRAIN_EDGE_PARQUET.stat().st_size,
            "terrain_access_parquet_bytes": TERRAIN_ACCESS_PARQUET.stat().st_size,
        },
        "limitations": [
            "Terrain uses DEM interpolation at road representative points, not surveyed road grade.",
            "Ascent, descent, and grade cover graph edges only; origin/destination connectors are excluded.",
            "Partial terrain routes retain observed components but do not publish full-route ascent/descent.",
            "Terrain is not mixed into routing distance or an accessibility score.",
            "The underlying fallback graph is not a validated pedestrian network.",
        ],
    }
    _write_json(SUMMARY_OUTPUT, report)
    print(json.dumps(_json_value(node_report), ensure_ascii=False))
    print(json.dumps(_json_value(edge_report), ensure_ascii=False))
    print(json.dumps(_json_value(report["building_routes"]), ensure_ascii=False))
    print(json.dumps(_json_value(report["performance"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
