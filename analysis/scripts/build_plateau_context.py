"""Build real PLATEAU land-use, planning and hazard context for a city.

Detailed feature and relation tables are Parquet working artifacts. Compact
CSV/JSON outputs provide reviewable evidence without shipping building-level
demographic estimates. Hazard overlap is always a review flag, never an
automatic siting prohibition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import area, from_wkb, intersection, length

from analysis.scripts.build_decision_studio_assets import _candidate_pool
from analysis.scripts.build_final_demo_assets import ANALYSIS_CRS, CITYGML_ZIP, METRICS_GEOJSON
from analysis.src.plateau_context import (
    PackageCodelists,
    first_attribute,
    read_theme_features,
    resolved_attribute,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real"
BUILDINGS = OUTPUT / "maizuru_building_demographics.parquet"
ROAD_EDGES = OUTPUT / "maizuru_road_graph_edges.parquet"
LANDUSE_CACHE = OUTPUT / "maizuru_plateau_landuse.parquet"
PLANNING_CACHE = OUTPUT / "maizuru_plateau_urban_planning.parquet"
HAZARD_CACHE = OUTPUT / "maizuru_plateau_hazards.parquet"
BUILDING_CONTEXT = OUTPUT / "maizuru_building_plateau_context.parquet"
ROAD_HAZARD_CONTEXT = OUTPUT / "maizuru_road_hazard_context.parquet"
CANDIDATE_CONTEXT = OUTPUT / "maizuru_scenario_candidate_context.parquet"
MESH_CONTEXT = OUTPUT / "maizuru_mesh_plateau_context.csv"
MESH_CONTEXT_DETAIL = OUTPUT / "maizuru_mesh_plateau_context.parquet"
CANDIDATE_REVIEW = OUTPUT / "maizuru_scenario_candidate_context.csv"
ROAD_REVIEW = OUTPUT / "maizuru_road_hazard_summary.csv"
SUMMARY = OUTPUT / "maizuru_plateau_context_summary.json"
DEEP_DIVE_MESH = "533513314"
ALGORITHM_VERSION = "plateau-context-1.0.0"
CITY_ID = "26202"
CITY_NAME = "舞鶴市"
PLATEAU_YEAR = 2025
CANDIDATES_CSV: Path | None = None
HAZARD_THEMES: tuple[str, ...] = ("lsld", "fld", "tnm")
HAZARD_TYPE_BY_THEME = {
    "lsld": "landslide",
    "fld": "flood",
    "tnm": "tsunami",
    "htd": "high_tide",
    "ifld": "inland_flood",
}


def _generated_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
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


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _plain(record: dict[str, Any], name: str) -> str | None:
    item = first_attribute(record, name)
    return item["value"] if item is not None else None


def _number(record: dict[str, Any], name: str) -> float | None:
    value = _plain(record, name)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _code_fields(
    record: dict[str, Any], name: str, codelists: PackageCodelists, prefix: str
) -> dict[str, str | None]:
    value = resolved_attribute(record, name, codelists)
    return {
        f"{prefix}_code": value.get("value") if value else None,
        f"{prefix}_label": value.get("official_label") if value else None,
        f"{prefix}_codelist": value.get("codelist") if value else None,
    }


def _normalise_landuse(source: gpd.GeoDataFrame, codelists: PackageCodelists) -> gpd.GeoDataFrame:
    rows = []
    for record in source.to_dict("records"):
        rows.append(
            {
                "gml_id": record["gml_id"],
                "feature_type": record["feature_type"],
                **_code_fields(record, "class", codelists, "class"),
                "source_area_m2": _number(record, "areaInSquareMeter"),
                "survey_year": _plain(record, "surveyYear"),
                "surface_part_count": record["surface_part_count"],
                "source_gml": record["source_gml"],
                "source_member_crc32": record["source_member_crc32"],
                "attributes_json": json.dumps(
                    record["attributes"], ensure_ascii=False, sort_keys=True
                ),
                "geometry": record["geometry"],
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=source.crs).to_crs(ANALYSIS_CRS)


def _normalise_planning(source: gpd.GeoDataFrame, codelists: PackageCodelists) -> gpd.GeoDataFrame:
    rows = []
    for record in source.to_dict("records"):
        function = _code_fields(record, "function", codelists, "function")
        urban_plan = _code_fields(record, "urbanPlanType", codelists, "urban_plan_type")
        rows.append(
            {
                "gml_id": record["gml_id"],
                "planning_type": record["feature_type"],
                "name": _plain(record, "name"),
                **function,
                **urban_plan,
                **_code_fields(
                    record, "areaClassificationType", codelists, "area_classification_type"
                ),
                "building_coverage_rate": _number(record, "buildingCoverageRate"),
                "floor_area_rate": _number(record, "floorAreaRate"),
                "valid_from": _plain(record, "validFrom"),
                "custodian": _plain(record, "custodian"),
                "surface_part_count": record["surface_part_count"],
                "source_gml": record["source_gml"],
                "source_member_crc32": record["source_member_crc32"],
                "attributes_json": json.dumps(
                    record["attributes"], ensure_ascii=False, sort_keys=True
                ),
                "geometry": record["geometry"],
            }
        )
    result = gpd.GeoDataFrame(rows, geometry="geometry", crs=source.crs).to_crs(ANALYSIS_CRS)
    result["planning_label"] = result["function_label"].fillna(result["urban_plan_type_label"])
    return result


def _normalise_hazard(
    source: gpd.GeoDataFrame, theme: str, codelists: PackageCodelists
) -> gpd.GeoDataFrame:
    hazard_type = HAZARD_TYPE_BY_THEME[theme]
    rows = []
    for record in source.to_dict("records"):
        if hazard_type == "landslide":
            rank = _code_fields(record, "areaType", codelists, "rank")
        else:
            rank = _code_fields(record, "rankOrg", codelists, "rank")
        rows.append(
            {
                "gml_id": record["gml_id"],
                "feature_type": record["feature_type"],
                "hazard_type": hazard_type,
                "name": _plain(record, "name"),
                **rank,
                **_code_fields(record, "description", codelists, "description"),
                **_code_fields(record, "disasterType", codelists, "disaster_type"),
                **_code_fields(record, "areaType", codelists, "area_type"),
                **_code_fields(record, "status", codelists, "status"),
                "valid_from": _plain(record, "validFrom"),
                "location": _plain(record, "location"),
                "zone_number": _plain(record, "zoneNumber"),
                "zone_name": _plain(record, "zoneName"),
                "surface_part_count": record["surface_part_count"],
                "source_gml": record["source_gml"],
                "source_member_crc32": record["source_member_crc32"],
                "attributes_json": json.dumps(
                    record["attributes"], ensure_ascii=False, sort_keys=True
                ),
                "geometry": record["geometry"],
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=source.crs).to_crs(ANALYSIS_CRS)


def _extract(refresh: bool) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    caches = (LANDUSE_CACHE, PLANNING_CACHE, HAZARD_CACHE)
    if not refresh and all(path.exists() for path in caches):
        return tuple(gpd.read_parquet(path) for path in caches)  # type: ignore[return-value]

    codelists = PackageCodelists(CITYGML_ZIP)
    landuse = _normalise_landuse(
        read_theme_features(CITYGML_ZIP, "luse", feature_types={"LandUse"}), codelists
    )
    planning = _normalise_planning(read_theme_features(CITYGML_ZIP, "urf"), codelists)
    hazard_parts = []
    for theme in HAZARD_THEMES:
        feature_type = "SedimentDisasterProneArea" if theme == "lsld" else "WaterBody"
        coverage = theme != "lsld"
        source = read_theme_features(
            CITYGML_ZIP,
            theme,
            feature_types={feature_type},
            coverage_geometry=coverage,
        )
        hazard_parts.append(_normalise_hazard(source, theme, codelists))
    hazards = gpd.GeoDataFrame(
        pd.concat(hazard_parts, ignore_index=True), geometry="geometry", crs=ANALYSIS_CRS
    )
    landuse.to_parquet(LANDUSE_CACHE, index=False)
    planning.to_parquet(PLANNING_CACHE, index=False)
    hazards.to_parquet(HAZARD_CACHE, index=False)
    return landuse, planning, hazards


def _point_relations(
    targets: gpd.GeoDataFrame,
    target_id: str,
    context: gpd.GeoDataFrame,
    fields: list[str],
) -> pd.DataFrame:
    right = context[[*fields, "geometry"]].copy()
    if target_id in fields:
        right = right.rename(columns={target_id: "context_gml_id"})
    joined = gpd.sjoin(
        targets[[target_id, "geometry"]],
        right,
        how="inner",
        predicate="intersects",
    )
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"])).drop_duplicates()


def _measured_relations(
    targets: gpd.GeoDataFrame,
    target_id: str,
    context: gpd.GeoDataFrame,
    fields: list[str],
    *,
    dimension: str,
) -> pd.DataFrame:
    target_indices, context_indices = context.sindex.query(targets.geometry, predicate="intersects")
    if not len(target_indices):
        return pd.DataFrame(columns=[target_id, *fields, f"intersection_{dimension}"])
    intersections = intersection(
        targets.geometry.array.take(target_indices),
        context.geometry.array.take(context_indices),
    )
    values = area(intersections) if dimension == "area_m2" else length(intersections)
    usable = np.asarray(values) > 1e-9
    left = targets.iloc[target_indices[usable]][[target_id]].reset_index(drop=True)
    right = context.iloc[context_indices[usable]][fields].reset_index(drop=True)
    result = pd.concat([left, right], axis=1)
    result[f"intersection_{dimension}"] = np.asarray(values)[usable]
    return result.drop_duplicates()


def _target_frames() -> tuple[
    gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame
]:
    building_rows = pd.read_parquet(BUILDINGS)
    building_rows = building_rows.sort_values(["gml_id", "mesh_code"]).drop_duplicates("gml_id")
    buildings = gpd.GeoDataFrame(
        building_rows[["gml_id", "mesh_code"]],
        geometry=gpd.points_from_xy(building_rows.longitude, building_rows.latitude),
        crs="EPSG:4326",
    ).to_crs(ANALYSIS_CRS)

    meshes = gpd.read_file(METRICS_GEOJSON).to_crs(ANALYSIS_CRS)
    if CANDIDATES_CSV is None:
        pool, _ = _candidate_pool()
        candidate_rows = pool.rename(
            columns={
                "road_id": "candidate_id",
                "anchor_lon": "longitude",
                "anchor_lat": "latitude",
            }
        )
        candidates = gpd.GeoDataFrame(
            candidate_rows[
                [
                    "candidate_id",
                    "road_name",
                    "existing_transport_distance_m",
                    "longitude",
                    "latitude",
                ]
            ],
            geometry=gpd.points_from_xy(pool.candidate_x, pool.candidate_y),
            crs=ANALYSIS_CRS,
        )
    else:
        candidate_rows = pd.read_csv(CANDIDATES_CSV, dtype={"mesh_code": str})
        candidate_rows["candidate_id"] = "mesh-" + candidate_rows["mesh_code"]
        candidate_rows["road_name"] = candidate_rows["nearest_public_transport_name"].fillna(
            "screening mesh"
        )
        candidate_rows["existing_transport_distance_m"] = candidate_rows[
            "nearest_public_transport_distance_m"
        ]
        candidate_rows["longitude"] = candidate_rows["centroid_lon"]
        candidate_rows["latitude"] = candidate_rows["centroid_lat"]
        candidates = gpd.GeoDataFrame(
            candidate_rows[
                [
                    "candidate_id",
                    "road_name",
                    "existing_transport_distance_m",
                    "longitude",
                    "latitude",
                ]
            ],
            geometry=gpd.points_from_xy(
                candidate_rows["longitude"], candidate_rows["latitude"]
            ),
            crs="EPSG:4326",
        ).to_crs(ANALYSIS_CRS)
    candidates["candidate_x"] = candidates.geometry.x
    candidates["candidate_y"] = candidates.geometry.y
    edge_rows = pd.read_parquet(ROAD_EDGES)
    edges = gpd.GeoDataFrame(
        edge_rows.drop(columns="geometry"),
        geometry=from_wkb(edge_rows.geometry.to_numpy()),
        crs=ANALYSIS_CRS,
    )
    return buildings, meshes, candidates, edges


def _json_group(rows: pd.DataFrame, fields: list[str]) -> str:
    records = rows[fields].replace({np.nan: None}).to_dict("records")
    return json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _mesh_output(
    meshes: gpd.GeoDataFrame,
    land: pd.DataFrame,
    planning: pd.DataFrame,
    hazards: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for mesh in meshes.mesh_code.astype(str):
        land_rows = land.loc[land.mesh_code.astype(str).eq(mesh)]
        land_grouped = (
            land_rows.groupby(["class_code", "class_label"], dropna=False)
            .agg(
                feature_count=("gml_id", "nunique"),
                intersection_area_m2=("intersection_area_m2", "sum"),
            )
            .reset_index()
        )
        plan_rows = planning.loc[planning.mesh_code.astype(str).eq(mesh)]
        hazard_rows = hazards.loc[hazards.mesh_code.astype(str).eq(mesh)]
        rows.append(
            {
                "mesh_code": mesh,
                "landuse_context": _json_group(
                    land_grouped,
                    ["class_code", "class_label", "feature_count", "intersection_area_m2"],
                ),
                "planning_context": _json_group(
                    plan_rows,
                    [
                        "gml_id",
                        "planning_type",
                        "planning_label",
                        "name",
                        "intersection_area_m2",
                    ],
                ),
                "hazard_context": _json_group(
                    hazard_rows,
                    [
                        "gml_id",
                        "hazard_type",
                        "rank_code",
                        "rank_label",
                        "intersection_area_m2",
                        "review_status",
                    ],
                ),
                "hazard_overlap": bool(len(hazard_rows)),
                "hazard_review_status": (
                    "additional_confirmation_required"
                    if len(hazard_rows)
                    else "no_overlap_in_source_layers"
                ),
            }
        )
    return pd.DataFrame(rows)


def _candidate_output(
    candidates: gpd.GeoDataFrame,
    land: pd.DataFrame,
    planning: pd.DataFrame,
    hazards: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for candidate_id in candidates.candidate_id.astype(str):
        candidate = candidates.loc[candidates.candidate_id.astype(str).eq(candidate_id)].iloc[0]
        land_rows = land.loc[land.candidate_id.astype(str).eq(candidate_id)]
        plan_rows = planning.loc[planning.candidate_id.astype(str).eq(candidate_id)]
        hazard_rows = hazards.loc[hazards.candidate_id.astype(str).eq(candidate_id)]
        rows.append(
            {
                "candidate_id": candidate_id,
                "longitude": float(candidate.longitude),
                "latitude": float(candidate.latitude),
                "candidate_x": float(candidate.candidate_x),
                "candidate_y": float(candidate.candidate_y),
                "landuse_labels": " | ".join(
                    sorted(set(land_rows.class_label.dropna().astype(str)))
                ),
                "planning_labels": " | ".join(
                    sorted(set(plan_rows.planning_label.dropna().astype(str)))
                ),
                "hazard_labels": " | ".join(
                    sorted(
                        {f"{row.hazard_type}: {row.rank_label}" for row in hazard_rows.itertuples()}
                    )
                ),
                "landuse_feature_count": int(land_rows.gml_id.nunique()),
                "planning_feature_count": int(plan_rows.gml_id.nunique()),
                "hazard_feature_count": int(hazard_rows.gml_id.nunique()),
                "hazard_overlap": bool(len(hazard_rows)),
                "hazard_review_status": (
                    "additional_confirmation_required"
                    if len(hazard_rows)
                    else "no_overlap_in_source_layers"
                ),
                "siting_feasibility": "not_determined",
            }
        )
    return pd.DataFrame(rows)


def build(*, refresh: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    for required in (CITYGML_ZIP, BUILDINGS, ROAD_EDGES, METRICS_GEOJSON):
        if not required.exists():
            raise FileNotFoundError(required)
    landuse, planning, hazards = _extract(refresh)
    buildings, meshes, candidates, edges = _target_frames()

    land_fields = ["gml_id", "class_code", "class_label", "class_codelist", "survey_year"]
    plan_fields = [
        "gml_id",
        "planning_type",
        "planning_label",
        "name",
        "function_code",
        "function_label",
        "building_coverage_rate",
        "floor_area_rate",
    ]
    hazard_fields = [
        "gml_id",
        "hazard_type",
        "rank_code",
        "rank_label",
        "rank_codelist",
        "description_label",
        "disaster_type_label",
        "area_type_label",
    ]

    building_relations = []
    for context_type, context, fields in (
        ("landuse", landuse, land_fields),
        ("planning", planning, plan_fields),
        ("hazard", hazards, hazard_fields),
    ):
        relation = _point_relations(buildings, "gml_id", context, fields)
        relation.insert(1, "context_type", context_type)
        if context_type == "hazard":
            relation["review_status"] = "additional_confirmation_required"
            relation["siting_feasibility"] = "not_determined"
        building_relations.append(relation)
    building_context = pd.concat(building_relations, ignore_index=True, sort=False)
    building_context.to_parquet(BUILDING_CONTEXT, index=False)

    mesh_land = _measured_relations(meshes, "mesh_code", landuse, land_fields, dimension="area_m2")
    mesh_plan = _measured_relations(meshes, "mesh_code", planning, plan_fields, dimension="area_m2")
    mesh_hazard = _measured_relations(
        meshes, "mesh_code", hazards, hazard_fields, dimension="area_m2"
    )
    mesh_hazard["review_status"] = "additional_confirmation_required"
    mesh_hazard["siting_feasibility"] = "not_determined"
    mesh_relations = []
    for context_type, relation in (
        ("landuse", mesh_land),
        ("planning", mesh_plan),
        ("hazard", mesh_hazard),
    ):
        relation = relation.copy()
        relation.insert(1, "context_type", context_type)
        mesh_relations.append(relation)
    pd.concat(mesh_relations, ignore_index=True, sort=False).to_parquet(
        MESH_CONTEXT_DETAIL, index=False
    )
    mesh_output = _mesh_output(meshes, mesh_land, mesh_plan, mesh_hazard)
    mesh_output.to_csv(MESH_CONTEXT, index=False)

    candidate_land = _point_relations(candidates, "candidate_id", landuse, land_fields)
    candidate_plan = _point_relations(candidates, "candidate_id", planning, plan_fields)
    candidate_hazard = _point_relations(candidates, "candidate_id", hazards, hazard_fields)
    candidate_hazard["review_status"] = "additional_confirmation_required"
    candidate_hazard["siting_feasibility"] = "not_determined"
    candidate_reference = pd.DataFrame(candidates.drop(columns="geometry"))[
        ["candidate_id", "longitude", "latitude", "candidate_x", "candidate_y"]
    ]
    candidate_relations = []
    for context_type, relation in (
        ("landuse", candidate_land),
        ("planning", candidate_plan),
        ("hazard", candidate_hazard),
    ):
        relation = relation.copy()
        relation = relation.merge(candidate_reference, on="candidate_id", validate="many_to_one")
        relation.insert(1, "context_type", context_type)
        candidate_relations.append(relation)
    pd.concat(candidate_relations, ignore_index=True, sort=False).to_parquet(
        CANDIDATE_CONTEXT, index=False
    )
    candidate_output = _candidate_output(
        candidates, candidate_land, candidate_plan, candidate_hazard
    )
    candidate_output.to_csv(CANDIDATE_REVIEW, index=False)

    road_hazard = _measured_relations(
        edges, "edge_id", hazards, hazard_fields, dimension="length_m"
    )
    road_hazard["review_status"] = "additional_confirmation_required"
    road_hazard["siting_feasibility"] = "not_determined"
    road_hazard.to_parquet(ROAD_HAZARD_CONTEXT, index=False)
    road_summary = (
        road_hazard.groupby(["hazard_type", "rank_code", "rank_label"], dropna=False)
        .agg(
            road_edge_count=("edge_id", "nunique"),
            hazard_feature_count=("gml_id", "nunique"),
            feature_intersection_length_sum_m=("intersection_length_m", "sum"),
        )
        .reset_index()
    )
    road_summary.to_csv(ROAD_REVIEW, index=False)

    archive_hash = _sha256(CITYGML_ZIP)
    hazard_counts = Counter(hazards.hazard_type)
    feature_counts = {"land_use": len(landuse), "urban_planning": len(planning)}
    feature_counts.update(
        {kind: int(hazard_counts[kind]) for kind in HAZARD_TYPE_BY_THEME.values()}
    )
    report = {
        "schema_version": "1.0.0",
        "generated_at": _generated_at(),
        "algorithm_version": ALGORITHM_VERSION,
        "city": {"city_id": CITY_ID, "name": CITY_NAME},
        "dataset": {
            "plateau_year": PLATEAU_YEAR,
            "archive_file": CITYGML_ZIP.name,
            "archive_sha256": archive_hash,
            "source_crs": "EPSG:6697",
            "analysis_crs": ANALYSIS_CRS,
        },
        "feature_counts": feature_counts,
        "surface_part_counts": {
            "land_use": int(landuse.surface_part_count.sum()),
            "urban_planning": int(planning.surface_part_count.sum()),
            **{
                kind: int(hazards.loc[hazards.hazard_type.eq(kind), "surface_part_count"].sum())
                for kind in HAZARD_TYPE_BY_THEME.values()
            },
        },
        "targets": {
            "strict_residential_buildings": len(buildings),
            "census_meshes": len(meshes),
            "scenario_candidates": len(candidates),
            "experimental_road_graph_edges": len(edges),
        },
        "coverage": {
            "building_landuse": int(
                building_context.loc[
                    building_context.context_type.eq("landuse"), "gml_id"
                ].nunique()
            ),
            "building_planning": int(
                building_context.loc[
                    building_context.context_type.eq("planning"), "gml_id"
                ].nunique()
            ),
            "building_hazard": int(
                building_context.loc[building_context.context_type.eq("hazard"), "gml_id"].nunique()
            ),
            "mesh_landuse": int(mesh_land.mesh_code.nunique()),
            "mesh_planning": int(mesh_plan.mesh_code.nunique()),
            "mesh_hazard": int(mesh_hazard.mesh_code.nunique()),
            "candidate_landuse": int(candidate_land.candidate_id.nunique()),
            "candidate_planning": int(candidate_plan.candidate_id.nunique()),
            "candidate_hazard": int(candidate_hazard.candidate_id.nunique()),
            "road_edge_hazard": int(road_hazard.edge_id.nunique()),
        },
        "landuse_classes": (
            landuse.groupby(["class_code", "class_label", "class_codelist"], dropna=False)
            .agg(feature_count=("gml_id", "count"), source_area_sum_m2=("source_area_m2", "sum"))
            .reset_index()
            .replace({np.nan: None})
            .to_dict("records")
        ),
        "planning_feature_types": dict(sorted(Counter(planning.planning_type).items())),
        "hazard_rank_counts": (
            hazards.groupby(
                ["hazard_type", "rank_code", "rank_label", "rank_codelist"], dropna=False
            )
            .size()
            .rename("feature_count")
            .reset_index()
            .replace({np.nan: None})
            .to_dict("records")
        ),
        "deep_dive_mesh": json.loads(
            mesh_output.loc[mesh_output.mesh_code.eq(DEEP_DIVE_MESH)].to_json(
                orient="records", force_ascii=False
            )
        )[0],
        "hazard_interpretation": {
            "overlap_means": "additional_confirmation_required",
            "overlap_does_not_mean": "siting_impossible",
            "depth_source": "official rankOrg codelist labels; geometry Z is not treated as depth",
            "overlap_measure_note": (
                "Relation tables retain each official feature intersection. Sums across overlapping "
                "official features can double-count and are labelled feature-intersection sums."
            ),
        },
        "lineage": {
            "feature_key": "PLATEAU gml:id",
            "source_member_fields": ["source_gml", "source_member_crc32"],
            "labels": "package-local official GML codelists only",
            "geometry": "LOD1 polygons with interior rings preserved",
            "spatial_relation": f"exact intersects/intersection in {ANALYSIS_CRS}",
        },
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "detailed_outputs": [
            path.name
            for path in (
                LANDUSE_CACHE,
                PLANNING_CACHE,
                HAZARD_CACHE,
                BUILDING_CONTEXT,
                MESH_CONTEXT_DETAIL,
                ROAD_HAZARD_CONTEXT,
                CANDIDATE_CONTEXT,
            )
        ],
    }
    _write_json(SUMMARY, report)
    return report


def main() -> None:
    global ANALYSIS_CRS, BUILDINGS, BUILDING_CONTEXT, CANDIDATES_CSV, CANDIDATE_CONTEXT
    global CANDIDATE_REVIEW, CITYGML_ZIP, CITY_ID, CITY_NAME, DEEP_DIVE_MESH
    global HAZARD_CACHE, HAZARD_THEMES, LANDUSE_CACHE, MESH_CONTEXT, MESH_CONTEXT_DETAIL
    global METRICS_GEOJSON, OUTPUT, PLANNING_CACHE, PLATEAU_YEAR, ROAD_EDGES
    global ROAD_HAZARD_CONTEXT, ROAD_REVIEW, SUMMARY

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Reparse CityGML instead of caches")
    parser.add_argument("--archive", type=Path, default=CITYGML_ZIP)
    parser.add_argument("--city-id", default=CITY_ID)
    parser.add_argument("--city-name", default=CITY_NAME)
    parser.add_argument("--plateau-year", type=int, default=PLATEAU_YEAR)
    parser.add_argument("--meshes", type=Path, default=METRICS_GEOJSON)
    parser.add_argument("--buildings", type=Path, default=BUILDINGS)
    parser.add_argument("--road-edges", type=Path, default=ROAD_EDGES)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--output-prefix", default="maizuru")
    parser.add_argument("--analysis-crs", default=ANALYSIS_CRS)
    parser.add_argument("--deep-dive-mesh", default=DEEP_DIVE_MESH)
    parser.add_argument(
        "--hazard-themes",
        default=",".join(HAZARD_THEMES),
        help="comma-separated PLATEAU hazard themes",
    )
    arguments = parser.parse_args()

    hazard_themes = tuple(
        theme.strip() for theme in arguments.hazard_themes.split(",") if theme.strip()
    )
    unknown_themes = sorted(set(hazard_themes) - set(HAZARD_TYPE_BY_THEME))
    if unknown_themes:
        parser.error(f"unknown hazard themes: {', '.join(unknown_themes)}")

    CITYGML_ZIP = arguments.archive
    CITY_ID = arguments.city_id
    CITY_NAME = arguments.city_name
    PLATEAU_YEAR = arguments.plateau_year
    METRICS_GEOJSON = arguments.meshes
    BUILDINGS = arguments.buildings
    ROAD_EDGES = arguments.road_edges
    CANDIDATES_CSV = arguments.candidates
    OUTPUT = arguments.output_dir
    ANALYSIS_CRS = arguments.analysis_crs
    DEEP_DIVE_MESH = arguments.deep_dive_mesh
    HAZARD_THEMES = hazard_themes
    prefix = arguments.output_prefix
    LANDUSE_CACHE = OUTPUT / f"{prefix}_plateau_landuse.parquet"
    PLANNING_CACHE = OUTPUT / f"{prefix}_plateau_urban_planning.parquet"
    HAZARD_CACHE = OUTPUT / f"{prefix}_plateau_hazards.parquet"
    BUILDING_CONTEXT = OUTPUT / f"{prefix}_building_plateau_context.parquet"
    ROAD_HAZARD_CONTEXT = OUTPUT / f"{prefix}_road_hazard_context.parquet"
    CANDIDATE_CONTEXT = OUTPUT / f"{prefix}_scenario_candidate_context.parquet"
    MESH_CONTEXT = OUTPUT / f"{prefix}_mesh_plateau_context.csv"
    MESH_CONTEXT_DETAIL = OUTPUT / f"{prefix}_mesh_plateau_context.parquet"
    CANDIDATE_REVIEW = OUTPUT / f"{prefix}_scenario_candidate_context.csv"
    ROAD_REVIEW = OUTPUT / f"{prefix}_road_hazard_summary.csv"
    SUMMARY = OUTPUT / f"{prefix}_plateau_context_summary.json"
    OUTPUT.mkdir(parents=True, exist_ok=True)

    report = build(refresh=arguments.refresh)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
