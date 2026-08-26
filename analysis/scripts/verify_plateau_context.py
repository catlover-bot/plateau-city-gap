"""Independently verify published PLATEAU context relations and semantics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import from_wkb
from shapely.geometry import Point

from analysis.scripts.build_final_demo_assets import ANALYSIS_CRS, METRICS_GEOJSON

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real"
INVENTORY = OUTPUT / "maizuru_plateau_inventory.json"
SUMMARY = OUTPUT / "maizuru_plateau_context_summary.json"
VERIFICATION = OUTPUT / "maizuru_plateau_context_verification.json"


def _sample_indices(size: int, count: int) -> np.ndarray:
    if size <= count:
        return np.arange(size, dtype=int)
    return np.unique(np.linspace(0, size - 1, count, dtype=int))


def _write(value: dict[str, Any]) -> None:
    VERIFICATION.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def verify() -> dict[str, Any]:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    landuse = gpd.read_parquet(OUTPUT / "maizuru_plateau_landuse.parquet")
    planning = gpd.read_parquet(OUTPUT / "maizuru_plateau_urban_planning.parquet")
    hazards = gpd.read_parquet(OUTPUT / "maizuru_plateau_hazards.parquet")
    building_context = pd.read_parquet(OUTPUT / "maizuru_building_plateau_context.parquet")
    road_context = pd.read_parquet(OUTPUT / "maizuru_road_hazard_context.parquet")
    candidate_context = pd.read_parquet(OUTPUT / "maizuru_scenario_candidate_context.parquet")
    mesh_context = pd.read_csv(
        OUTPUT / "maizuru_mesh_plateau_context.csv", dtype={"mesh_code": str}
    )

    expected = {
        "land_use": inventory["themes"]["luse"]["feature_count"],
        "urban_planning": inventory["themes"]["urf"]["feature_count"],
        "landslide": inventory["themes"]["lsld"]["feature_count"],
        "flood": inventory["themes"]["fld"]["feature_count"],
        "tsunami": inventory["themes"]["tnm"]["feature_count"],
    }
    actual = {
        "land_use": len(landuse),
        "urban_planning": len(planning),
        **hazards.hazard_type.value_counts().to_dict(),
    }
    count_match = expected == actual == summary["feature_counts"]
    unique_ids = {
        "land_use": bool(landuse.gml_id.is_unique),
        "urban_planning": bool(planning.gml_id.is_unique),
        "hazards": bool(hazards.gml_id.is_unique),
    }
    geometry_valid = {
        "land_use": int(landuse.geometry.is_valid.sum()) == len(landuse),
        "urban_planning": int(planning.geometry.is_valid.sum()) == len(planning),
        "hazards": int(hazards.geometry.is_valid.sum()) == len(hazards),
    }
    label_resolution = {
        "land_use": int(landuse.class_label.notna().sum()) == len(landuse),
        "hazard_rank": int(hazards.rank_label.notna().sum()) == len(hazards),
        "land_use_codelist": set(landuse.class_codelist) == {"Common_landUseType.xml"},
        "hazard_codelists": set(hazards.rank_codelist)
        == {
            "LandSlideRiskAttribute_areaType.xml",
            "RiverFloodingRiskAttribute_rankOrg.xml",
            "TsunamiRiskAttribute_rankOrg.xml",
        },
    }

    hazard_buildings = building_context.loc[building_context.context_type.eq("hazard")]
    semantic_frames = (
        hazard_buildings,
        road_context,
        candidate_context.loc[candidate_context.context_type.eq("hazard")],
    )
    hazard_semantics = all(
        set(frame.review_status) == {"additional_confirmation_required"}
        and set(frame.siting_feasibility) == {"not_determined"}
        for frame in semantic_frames
    )

    feature_maps = {
        "landuse": landuse.set_index("gml_id").geometry,
        "planning": planning.set_index("gml_id").geometry,
        "hazard": hazards.set_index("gml_id").geometry,
    }
    buildings = pd.read_parquet(OUTPUT / "maizuru_building_demographics.parquet")
    buildings = buildings.sort_values(["gml_id", "mesh_code"]).drop_duplicates("gml_id")
    building_points = {
        row.gml_id: gpd.GeoSeries([Point(row.longitude, row.latitude)], crs="EPSG:4326")
        .to_crs(ANALYSIS_CRS)
        .iloc[0]
        for row in buildings.itertuples()
    }
    building_samples = building_context.iloc[_sample_indices(len(building_context), 300)]
    building_relation_failures = []
    for row in building_samples.itertuples():
        feature_id = row.context_gml_id
        geometry = feature_maps[row.context_type].get(feature_id)
        if geometry is None or not geometry.intersects(building_points[row.gml_id]):
            building_relation_failures.append(
                {"building_gml_id": row.gml_id, "context_gml_id": feature_id}
            )

    edge_rows = pd.read_parquet(OUTPUT / "maizuru_road_graph_edges.parquet")
    edge_geometry = pd.Series(from_wkb(edge_rows.geometry.to_numpy()), index=edge_rows.edge_id)
    hazard_geometry = hazards.set_index("gml_id").geometry
    road_samples = road_context.iloc[_sample_indices(len(road_context), 300)]
    road_residuals = []
    for row in road_samples.itertuples():
        computed = edge_geometry[row.edge_id].intersection(hazard_geometry[row.gml_id]).length
        road_residuals.append(abs(computed - row.intersection_length_m))

    meshes = gpd.read_file(METRICS_GEOJSON).to_crs(ANALYSIS_CRS).set_index("mesh_code")
    parsed_mesh_context = {
        str(row.mesh_code): {
            "landuse": json.loads(row.landuse_context),
            "planning": json.loads(row.planning_context),
            "hazard": json.loads(row.hazard_context),
        }
        for row in mesh_context.itertuples()
    }
    deep = parsed_mesh_context["533513314"]
    mesh_residuals = []
    deep_geometry = meshes.loc["533513314"].geometry
    for relation_type, context_rows, geometries in (
        ("planning", deep["planning"], planning.set_index("gml_id").geometry),
        ("hazard", deep["hazard"], hazard_geometry),
    ):
        for row in context_rows:
            computed = deep_geometry.intersection(geometries[row["gml_id"]]).area
            mesh_residuals.append(
                {
                    "context_type": relation_type,
                    "gml_id": row["gml_id"],
                    "residual_m2": abs(computed - row["intersection_area_m2"]),
                }
            )

    checks = {
        "inventory_feature_counts_match": count_match,
        "gml_ids_unique": all(unique_ids.values()),
        "all_geometries_valid": all(geometry_valid.values()),
        "all_required_official_labels_resolved": all(label_resolution.values()),
        "hazard_overlap_never_encodes_infeasibility": hazard_semantics,
        "sampled_building_relations_recompute": not building_relation_failures,
        "sampled_road_intersection_lengths_recompute": max(road_residuals, default=0.0) < 1e-8,
        "deep_mesh_intersection_areas_recompute": max(
            (row["residual_m2"] for row in mesh_residuals), default=0.0
        )
        < 1e-6,
        "all_meshes_exported": len(mesh_context) == summary["targets"]["census_meshes"],
        "all_candidates_have_summary": pd.read_csv(
            OUTPUT / "maizuru_scenario_candidate_context.csv"
        ).shape[0]
        == summary["targets"]["scenario_candidates"],
    }
    report = {
        "schema_version": "1.0.0",
        "verification_method": "independent artifact reload and direct Shapely recomputation",
        "checks": checks,
        "passed": all(checks.values()),
        "evidence": {
            "inventory_expected": expected,
            "normalised_actual": actual,
            "unique_ids": unique_ids,
            "geometry_valid": geometry_valid,
            "label_resolution": label_resolution,
            "building_relation_sample_count": len(building_samples),
            "building_relation_failures": building_relation_failures,
            "road_relation_sample_count": len(road_samples),
            "road_max_length_residual_m": max(road_residuals, default=0.0),
            "deep_mesh_relation_count": len(mesh_residuals),
            "deep_mesh_max_area_residual_m2": max(
                (row["residual_m2"] for row in mesh_residuals), default=0.0
            ),
        },
    }
    _write(report)
    return report


def main() -> None:
    report = verify()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
