"""Build privacy-preserving PLATEAU building demographics and accessibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from analysis.src.audit import classify_medical_access
from analysis.src.building_demographics import (
    MIXED_RESIDENTIAL_CODES,
    STRICT_RESIDENTIAL_CODES,
    allocate_by_mesh,
    assign_capacity,
    building_mesh_crosswalk,
    classify_usage,
    nearest_facility,
    numeric_values,
    valid_area,
    valid_storeys,
    weighted_statistics,
)
from analysis.src.plateau_buildings import read_buildings, read_gml_dictionary
from analysis.src.spatial import (
    boundary_from_plateau,
    deduplicate_stations,
    filter_medical_primary,
    intersects_boundary,
)

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
MESHES = ROOT / "analysis/outputs/real/maizuru_city_gap.geojson"
STATIONS = ROOT / "data/raw/plateau_related/26202_maizuru-shi_city_2025_station.geojson"
BUS_STOPS = ROOT / "data/raw/transport/P11-22_26_SHP/P11-22_26_SHP/P11-22_26.geojson"
MEDICAL = ROOT / "data/raw/medical/P04-20_26_GML/P04-20_26_GML/P04-20_26.geojson"
BORDER = ROOT / "data/raw/plateau_related/26202_maizuru-shi_city_2025_border.geojson"
INVENTORY = ROOT / "analysis/outputs/real/maizuru_plateau_inventory.json"
AUDIT_OUTPUT = ROOT / "analysis/outputs/real/maizuru_building_attribute_audit.json"
USAGE_OUTPUT = ROOT / "analysis/outputs/real/maizuru_building_usage_audit.csv"
PARQUET_OUTPUT = ROOT / "analysis/outputs/real/maizuru_building_demographics.parquet"
SUMMARY_OUTPUT = ROOT / "analysis/outputs/real/maizuru_building_demographics_summary.json"
DETAIL_OUTPUT = ROOT / "analysis/outputs/real/maizuru_plateau_detail_meshes.csv"
CANDIDATE_OUTPUT = ROOT / "analysis/outputs/real/maizuru_plateau_detail_candidates.csv"
FINAL_DEMO_OUTPUTS = (
    ROOT / "analysis/outputs/real/maizuru_final_demo.json",
    ROOT / "frontend/public/data/final_demo.json",
)
USAGE_CODELIST = "codelists/Building_usage.xml"
ANALYSIS_CRS = "EPSG:6674"
ARCHIVE_SHA256 = "13f4020ade066dc7139b7653c47a55a09af0093dee743f6b9cca5d3177a71cff"
DEEP_DIVE_MESH = "533513314"
BUFFER_M = 2_000.0


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


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_value(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _publish_aggregated_demo_detail(deep: dict[str, Any]) -> None:
    """Publish only mesh aggregates; never expose per-building estimates."""

    aggregate = {
        "method": "estimated 500m census allocated by strict residential PLATEAU floor area",
        "privacy": "mesh aggregate only; no per-building estimated person counts",
        "residential_building_count": int(deep["residential_building_count"]),
        "mixed_residential_building_count": int(deep["mixed_residential_buildings"]),
        "estimated_population_allocated": float(deep["estimated_population_allocated"]),
        "estimated_elderly_allocated": float(deep["estimated_elderly_allocated"]),
        "centroid_transport_distance_m": float(deep["centroid_transport_distance"]),
        "weighted_mean_transport_distance_m": float(deep["weighted_mean_transport_distance"]),
        "weighted_median_transport_distance_m": float(
            deep["weighted_median_transport_distance"]
        ),
        "weighted_p90_transport_distance_m": float(deep["weighted_p90_transport_distance"]),
        "centroid_medical_distance_m": float(deep["centroid_medical_distance"]),
        "weighted_mean_medical_distance_m": float(deep["weighted_mean_medical_distance"]),
        "weighted_median_medical_distance_m": float(deep["weighted_median_medical_distance"]),
        "weighted_p90_medical_distance_m": float(deep["weighted_p90_medical_distance"]),
    }
    for index, path in enumerate(FINAL_DEMO_OUTPUTS):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["deep_dive"]["building_demographics_detail"] = aggregate
        options = {"indent": 2} if index == 0 else {"separators": (",", ":")}
        path.write_text(
            json.dumps(payload, ensure_ascii=False, **options) + "\n",
            encoding="utf-8",
        )
    web_output = FINAL_DEMO_OUTPUTS[1]
    manifest_path = web_output.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for output in manifest["outputs"]:
        if output["file"] == web_output.name:
            output["bytes"] = web_output.stat().st_size
            output["sha256"] = _sha256(web_output)
            break
    else:
        raise ValueError("Web manifest does not declare final_demo.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _attribute_audit(buildings: pd.DataFrame) -> dict[str, Any]:
    fields = {
        "usage": None,
        "totalFloorArea": "m2",
        "buildingFootprintArea": "m2",
        "measuredHeight": "m",
        "storeysAboveGround": "count",
        "storeysBelowGround": "count",
    }
    result: dict[str, Any] = {}
    for field, expected_unit in fields.items():
        raw = buildings[field]
        numeric = numeric_values(raw) if field != "usage" else pd.Series(dtype=float)
        if field == "usage":
            result[field] = {
                "present_count": int(raw.notna().sum()),
                "null_count": int(raw.isna().sum()),
                "distinct_count": int(raw.nunique(dropna=True)),
                "values": {str(key): int(value) for key, value in raw.value_counts().sort_index().items()},
                "unit": None,
            }
            continue
        valid = (
            valid_storeys(raw)
            if field == "storeysAboveGround"
            else (
                numeric.notna() & numeric.ge(0) & numeric.le(200) & ~numeric.isin([-9999, 9999])
                if field == "storeysBelowGround"
                else valid_area(raw)
            )
        )
        valid_numeric = numeric.loc[valid]
        units = Counter(
            unit
            for metadata in buildings["units"]
            if isinstance(metadata, dict)
            for key, unit in metadata.items()
            if key == field
        )
        outliers = buildings.assign(_numeric=numeric).sort_values("_numeric").loc[
            :, ["gml_id", field, "source_gml"]
        ]
        result[field] = {
            "present_count": int(raw.notna().sum()),
            "numeric_parse_count": int(numeric.notna().sum()),
            "numeric_parse_failure_count": int((raw.notna() & numeric.isna()).sum()),
            "null_count": int(raw.isna().sum()),
            "zero_count": int(numeric.eq(0).sum()),
            "negative_count": int(numeric.lt(0).sum()),
            "sentinel_minus_9999_count": int(numeric.eq(-9999).sum()),
            "sentinel_9999_count": int(numeric.eq(9999).sum()),
            "valid_count": int(valid.sum()),
            "invalid_count": int((~valid).sum()),
            "minimum": valid_numeric.min(),
            "median": valid_numeric.median(),
            "p95": valid_numeric.quantile(0.95),
            "p99": valid_numeric.quantile(0.99),
            "maximum": valid_numeric.max(),
            "raw_minimum": numeric.min(),
            "raw_maximum": numeric.max(),
            "unit": expected_unit,
            "source_uom_counts": dict(units),
            "outlier_examples_low": outliers.head(5).to_dict("records"),
            "outlier_examples_high": outliers.tail(5).to_dict("records"),
        }

    total = numeric_values(buildings["totalFloorArea"])
    footprint = numeric_values(buildings["buildingFootprintArea"])
    storeys = numeric_values(buildings["storeysAboveGround"])
    comparable = valid_area(buildings["totalFloorArea"]) & valid_area(
        buildings["buildingFootprintArea"]
    )
    violation = comparable & total.lt(footprint - 1e-9)
    storey_comparable = comparable & valid_storeys(buildings["storeysAboveGround"])
    ratio = total.loc[storey_comparable] / (
        footprint.loc[storey_comparable] * storeys.loc[storey_comparable]
    )
    result["floor_area_validation"] = {
        "comparable_count": int(comparable.sum()),
        "total_floor_area_ge_footprint_count": int((comparable & ~violation).sum()),
        "total_floor_area_lt_footprint_count": int(violation.sum()),
        "total_floor_area_lt_footprint_examples": buildings.loc[
            violation,
            ["gml_id", "usage", "totalFloorArea", "buildingFootprintArea", "source_gml"],
        ].head(20).to_dict("records"),
        "total_over_footprint_times_storeys": {
            "count": int(storey_comparable.sum()),
            "median": ratio.median(),
            "p01": ratio.quantile(0.01),
            "p99": ratio.quantile(0.99),
        },
        "policy": "No clamping. Positive non-sentinel totalFloorArea is primary; audited hierarchy is recorded per building.",
    }
    return result


def _usage_mapping(buildings: pd.DataFrame) -> pd.DataFrame:
    mapping = pd.DataFrame(read_gml_dictionary(ARCHIVE, USAGE_CODELIST))
    mapping["classification"] = mapping["usage_code"].map(classify_usage)
    counts = buildings["usage"].astype(str).value_counts()
    mapping["observed_building_count"] = mapping["usage_code"].map(counts).fillna(0).astype(int)
    mapping["mapping_source"] = (
        "dataset package codelists/Building_usage.xml; "
        "classification follows the explicit official Japanese label"
    )
    mapping["codelist_member"] = USAGE_CODELIST
    mapping["codelist_member_crc32"] = ""
    with __import__("zipfile").ZipFile(ARCHIVE) as archive:
        mapping["codelist_member_crc32"] = f"{archive.getinfo(USAGE_CODELIST).CRC:08x}"
    return mapping


def _buffer_features(
    layer: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    buffer = boundary.to_crs(ANALYSIS_CRS).geometry.union_all().buffer(BUFFER_M)
    projected = layer.to_crs(ANALYSIS_CRS)
    return layer.loc[projected.geometry.intersects(buffer)].copy()


def _facilities(boundary: gpd.GeoDataFrame) -> dict[str, gpd.GeoDataFrame]:
    stations = deduplicate_stations(
        intersects_boundary(gpd.read_file(STATIONS).to_crs("EPSG:4326"), boundary)
    )
    stations = stations[["station_name", "geometry"]].rename(columns={"station_name": "name"})
    stations["type"] = "station"

    buses_source = gpd.read_file(BUS_STOPS).to_crs("EPSG:4326")
    buses_city = intersects_boundary(buses_source, boundary)
    buses_buffer = _buffer_features(buses_source, boundary)
    def buses(layer: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        result = layer[["P11_001", "geometry"]].rename(columns={"P11_001": "name"})
        result["type"] = "bus_stop"
        return result

    medical_source = gpd.read_file(MEDICAL).to_crs("EPSG:4326")
    medical_city = filter_medical_primary(intersects_boundary(medical_source, boundary))
    medical_buffer = filter_medical_primary(_buffer_features(medical_source, boundary))
    for frame in (medical_city, medical_buffer):
        classified = classify_medical_access(frame["P04_002"])
        frame["medical_access_class"] = classified["medical_access_class"].to_numpy()
    medical_conservative = medical_buffer.loc[
        medical_buffer["medical_access_class"].ne("uncertain_access")
    ]
    def medical(layer: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        return layer[["P04_002", "medical_access_class", "geometry"]].rename(
            columns={"P04_002": "name"}
        )

    transport_city = pd.concat([stations, buses(buses_city)], ignore_index=True)
    transport_buffer = pd.concat([stations, buses(buses_buffer)], ignore_index=True)
    return {
        "stations": gpd.GeoDataFrame(stations, geometry="geometry", crs="EPSG:4326"),
        "buses": gpd.GeoDataFrame(buses(buses_city), geometry="geometry", crs="EPSG:4326"),
        "transport": gpd.GeoDataFrame(transport_city, geometry="geometry", crs="EPSG:4326"),
        "medical": gpd.GeoDataFrame(medical(medical_city), geometry="geometry", crs="EPSG:4326"),
        "conservative_transport": gpd.GeoDataFrame(
            transport_buffer, geometry="geometry", crs="EPSG:4326"
        ),
        "conservative_medical": gpd.GeoDataFrame(
            medical(medical_conservative), geometry="geometry", crs="EPSG:4326"
        ),
    }


def _accessibility(buildings: gpd.GeoDataFrame, facilities: dict) -> pd.DataFrame:
    origins = gpd.GeoDataFrame(
        {"gml_id": buildings["gml_id"].to_numpy()},
        geometry=buildings.geometry.representative_point(),
        crs=buildings.crs,
        index=buildings.index,
    )
    result = pd.DataFrame({"gml_id": buildings["gml_id"]}, index=buildings.index)
    lookups = {
        "station": (facilities["stations"], "name", None),
        "bus_stop": (facilities["buses"], "name", None),
        "public_transport": (facilities["transport"], "name", "type"),
        "medical": (facilities["medical"], "name", None),
        "conservative_public_transport": (
            facilities["conservative_transport"],
            "name",
            "type",
        ),
        "conservative_medical": (facilities["conservative_medical"], "name", None),
    }
    for prefix, (targets, name_column, type_column) in lookups.items():
        nearest = nearest_facility(
            origins,
            targets.to_crs(origins.crs),
            name_column=name_column,
            type_column=type_column,
        )
        result[f"nearest_{prefix}_name"] = nearest["name"]
        if type_column:
            result[f"nearest_{prefix}_type"] = nearest["type"]
        result[f"nearest_{prefix}_distance_m"] = nearest["distance_m"]
    geographic = origins.to_crs("EPSG:4326")
    result["longitude"] = geographic.geometry.x
    result["latitude"] = geographic.geometry.y
    result["origin_method"] = "building_origin_representative_point"
    result["facility_policy"] = "city_baseline_including_uncertain_medical"
    result["conservative_facility_policy"] = (
        "two_km_cross_border_excluding_uncertain_medical"
    )
    return result


def _detail_table(
    allocated: pd.DataFrame,
    access: pd.DataFrame,
    meshes: pd.DataFrame,
) -> pd.DataFrame:
    detailed = allocated.merge(access, on="gml_id", how="left", validate="many_to_one")
    rows = []
    for mesh_code, group in detailed.groupby("mesh_code", sort=True):
        transport = weighted_statistics(
            group["nearest_public_transport_distance_m"],
            group["estimated_elderly_population"],
        )
        medical = weighted_statistics(
            group["nearest_medical_distance_m"], group["estimated_elderly_population"]
        )
        population_transport = weighted_statistics(
            group["nearest_public_transport_distance_m"], group["estimated_population"]
        )
        population_medical = weighted_statistics(
            group["nearest_medical_distance_m"], group["estimated_population"]
        )
        mesh = meshes.loc[meshes["mesh_code"].eq(mesh_code)].iloc[0]
        rows.append(
            {
                "mesh_code": mesh_code,
                "centroid_transport_distance": mesh["nearest_public_transport_distance_m"],
                "weighted_mean_transport_distance": transport["mean"],
                "weighted_median_transport_distance": transport["median"],
                "weighted_p90_transport_distance": transport["p90"],
                "transport_difference": transport["mean"]
                - mesh["nearest_public_transport_distance_m"],
                "centroid_medical_distance": mesh["nearest_medical_distance_m"],
                "weighted_mean_medical_distance": medical["mean"],
                "weighted_median_medical_distance": medical["median"],
                "weighted_p90_medical_distance": medical["p90"],
                "medical_difference": medical["mean"] - mesh["nearest_medical_distance_m"],
                "population_weighted_mean_transport_distance": population_transport["mean"],
                "population_weighted_median_transport_distance": population_transport["median"],
                "population_weighted_p90_transport_distance": population_transport["p90"],
                "population_weighted_mean_medical_distance": population_medical["mean"],
                "population_weighted_median_medical_distance": population_medical["median"],
                "population_weighted_p90_medical_distance": population_medical["p90"],
                "residential_building_count": group["gml_id"].nunique(),
                "estimated_population_allocated": group["estimated_population"].sum(),
                "estimated_elderly_allocated": group["estimated_elderly_population"].sum(),
                "citywide_screening_rank": mesh["rank_c_unfiltered"],
                "label": (
                    f"{mesh['nearest_public_transport_name']}周辺"
                    if pd.notna(mesh["nearest_public_transport_name"])
                    else "名称未確認の地域"
                ),
            }
        )
    return pd.DataFrame(rows)


def _coverage(
    meshes: pd.DataFrame,
    crosswalk: pd.DataFrame,
    allocated: pd.DataFrame,
) -> pd.DataFrame:
    result = meshes[["mesh_code", "primary_eligible_disclosure"]].copy()
    all_counts = crosswalk.groupby("mesh_code")["gml_id"].nunique()
    residential = crosswalk.loc[crosswalk["usage_code"].astype(str).isin(STRICT_RESIDENTIAL_CODES)]
    residential_counts = residential.groupby("mesh_code")["gml_id"].nunique()
    allocatable_counts = allocated.groupby("mesh_code")["gml_id"].nunique()
    result["plateau_buildings"] = result["mesh_code"].map(all_counts).fillna(0).astype(int)
    result["strict_residential_buildings"] = (
        result["mesh_code"].map(residential_counts).fillna(0).astype(int)
    )
    result["allocatable_residential_buildings"] = (
        result["mesh_code"].map(allocatable_counts).fillna(0).astype(int)
    )
    result["population_resolution"] = "building_detail_available"
    result.loc[
        ~result["primary_eligible_disclosure"].astype(bool), "population_resolution"
    ] = "mesh_fallback_suppression"
    safe = result["primary_eligible_disclosure"].astype(bool)
    result.loc[safe & result["plateau_buildings"].eq(0), "population_resolution"] = (
        "mesh_fallback_no_plateau"
    )
    result.loc[
        safe
        & result["plateau_buildings"].gt(0)
        & result["strict_residential_buildings"].eq(0),
        "population_resolution",
    ] = "mesh_fallback_no_residential_building"
    result.loc[
        safe
        & result["strict_residential_buildings"].gt(0)
        & result["allocatable_residential_buildings"].eq(0),
        "population_resolution",
    ] = "building_detail_partial"
    result.loc[
        safe
        & result["allocatable_residential_buildings"].gt(0)
        & result["allocatable_residential_buildings"].lt(result["strict_residential_buildings"]),
        "population_resolution",
    ] = "building_detail_partial"
    return result


def _informative_examples(detail: pd.DataFrame) -> dict[str, dict]:
    rows = detail.copy()
    under = rows.sort_values(
        ["transport_difference", "mesh_code"], ascending=[False, True]
    ).iloc[0]
    over = rows.sort_values(
        ["transport_difference", "mesh_code"], ascending=[True, True]
    ).iloc[0]
    inequality = (
        rows["weighted_p90_transport_distance"]
        - rows["weighted_median_transport_distance"]
    )
    inequality_row = rows.loc[inequality.sort_values(ascending=False).index[0]]
    interpretation = rows.assign(
        _difference=rows[["transport_difference", "medical_difference"]].abs().max(axis=1)
    ).sort_values(["_difference", "mesh_code"], ascending=[False, True]).iloc[0]
    return {
        "centroid_underestimates_transport_most": under.to_dict(),
        "centroid_overestimates_transport_most": over.to_dict(),
        "largest_within_mesh_transport_inequality": inequality_row.to_dict(),
        "largest_absolute_mean_difference": interpretation.drop(labels="_difference").to_dict(),
    }


def main() -> None:
    global ANALYSIS_CRS, ARCHIVE, AUDIT_OUTPUT, BORDER, BUS_STOPS, CANDIDATE_OUTPUT
    global DEEP_DIVE_MESH, DETAIL_OUTPUT, INVENTORY, MEDICAL, MESHES, PARQUET_OUTPUT, STATIONS
    global SUMMARY_OUTPUT, USAGE_OUTPUT

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--city-id", default="26202")
    parser.add_argument("--city-name", default="舞鶴市")
    parser.add_argument("--meshes", type=Path, default=MESHES)
    parser.add_argument("--stations", type=Path, default=STATIONS)
    parser.add_argument("--bus-stops", type=Path, default=BUS_STOPS)
    parser.add_argument("--medical", type=Path, default=MEDICAL)
    parser.add_argument("--border", type=Path, default=BORDER)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis/outputs/real")
    parser.add_argument("--output-prefix", default="maizuru")
    parser.add_argument("--analysis-crs", default=ANALYSIS_CRS)
    parser.add_argument("--archive-sha256")
    parser.add_argument("--expected-building-count", type=int)
    parser.add_argument("--deep-dive-mesh", default=DEEP_DIVE_MESH)
    parser.add_argument("--population-year", type=int, default=2020)
    parser.add_argument(
        "--publish-demo",
        action="store_true",
        help="update the public Maizuru aggregate demo asset",
    )
    args = parser.parse_args()

    ARCHIVE = args.archive
    MESHES = args.meshes
    STATIONS = args.stations
    BUS_STOPS = args.bus_stops
    MEDICAL = args.medical
    BORDER = args.border
    INVENTORY = args.inventory
    ANALYSIS_CRS = args.analysis_crs
    DEEP_DIVE_MESH = args.deep_dive_mesh
    AUDIT_OUTPUT = args.output_dir / f"{args.output_prefix}_building_attribute_audit.json"
    USAGE_OUTPUT = args.output_dir / f"{args.output_prefix}_building_usage_audit.csv"
    PARQUET_OUTPUT = args.output_dir / f"{args.output_prefix}_building_demographics.parquet"
    SUMMARY_OUTPUT = args.output_dir / f"{args.output_prefix}_building_demographics_summary.json"
    DETAIL_OUTPUT = args.output_dir / f"{args.output_prefix}_plateau_detail_meshes.csv"
    CANDIDATE_OUTPUT = args.output_dir / f"{args.output_prefix}_plateau_detail_candidates.csv"

    total_started = time.perf_counter()
    timings: dict[str, float] = {}

    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    archive_sha256 = args.archive_sha256 or inventory["archive"]["sha256"]
    if _sha256(args.archive) != archive_sha256:
        raise ValueError("CityGML archive SHA-256 does not match the audited inventory")
    expected_buildings = args.expected_building_count or inventory["themes"]["bldg"][
        "feature_count"
    ]

    started = time.perf_counter()
    buildings = read_buildings(args.archive)
    timings["building_parse_seconds"] = time.perf_counter() - started
    if len(buildings) != expected_buildings or buildings["gml_id"].duplicated().any():
        raise ValueError(f"Expected {expected_buildings:,} unique buildings")
    if buildings.geometry.isna().any() or (~buildings.geometry.is_valid).any():
        raise ValueError("Every building must have a valid analytical footprint")

    audit = _attribute_audit(buildings)
    usage_mapping = _usage_mapping(buildings)
    usage_mapping.to_csv(USAGE_OUTPUT, index=False)
    label_by_code = usage_mapping.set_index("usage_code")["official_label"]
    buildings["usage_code"] = buildings["usage"].astype(str)
    buildings["usage_label"] = buildings["usage_code"].map(label_by_code)
    buildings["residential_class"] = buildings["usage_code"].map(classify_usage)
    buildings = assign_capacity(buildings)
    audit["allocation_weight_source_counts"] = buildings[
        "allocation_weight_source"
    ].value_counts().to_dict()
    audit["geometry"] = {
        "valid_count": int(buildings.geometry.is_valid.sum()),
        "missing_count": int(buildings.geometry.isna().sum()),
        "source_counts": buildings["geometry_source"].value_counts().to_dict(),
        "method": "2D projection of actual LOD0 roof-edge; LOD1 solid projection only as fallback",
    }
    audit["provenance"] = {
        "archive_sha256": archive_sha256,
        "product_specification_version": inventory["dataset"]["product_specification_version"],
        "ade_schema_version": inventory["dataset"]["ade_schema_version"],
        "usage_codelist": USAGE_CODELIST,
    }
    _write_json(AUDIT_OUTPUT, audit)

    meshes = gpd.read_file(MESHES)
    meshes["mesh_code"] = meshes["mesh_code"].astype(str)
    projected_meshes = meshes.to_crs(ANALYSIS_CRS)
    projected_buildings = buildings.to_crs(ANALYSIS_CRS)
    projected_buildings["building_origin_representative_point"] = (
        projected_buildings.geometry.representative_point()
    )
    projected_buildings["geometry_footprint_area_m2"] = projected_buildings.geometry.area

    started = time.perf_counter()
    crosswalk = building_mesh_crosswalk(projected_buildings, projected_meshes)
    timings["crosswalk_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    strict, strict_conservation = allocate_by_mesh(
        crosswalk, pd.DataFrame(meshes.drop(columns="geometry")), policy="strict_residential"
    )
    mixed, mixed_conservation = allocate_by_mesh(
        crosswalk,
        pd.DataFrame(meshes.drop(columns="geometry")),
        policy="residential_plus_mixed",
    )
    timings["allocation_seconds"] = time.perf_counter() - started

    covered_ids = set(mixed["gml_id"])
    access_buildings = projected_buildings.loc[
        projected_buildings["gml_id"].isin(covered_ids)
    ].copy()
    started = time.perf_counter()
    boundary = boundary_from_plateau(
        gpd.read_file(BORDER).to_crs("EPSG:4326"),
        city_code=args.city_id,
        city_name=args.city_name,
    )
    facilities = _facilities(boundary)
    access = _accessibility(access_buildings, facilities)
    timings["accessibility_seconds"] = time.perf_counter() - started

    strict_detail = _detail_table(strict, access, pd.DataFrame(meshes.drop(columns="geometry")))
    mixed_detail = _detail_table(mixed, access, pd.DataFrame(meshes.drop(columns="geometry")))
    strict_detail.to_csv(DETAIL_OUTPUT, index=False)

    candidates = strict_detail.loc[strict_detail["citywide_screening_rank"].notna()].copy()
    candidates = candidates.sort_values(["citywide_screening_rank", "mesh_code"])
    candidates.rename(
        columns={
            "residential_building_count": "residential_buildings",
            "estimated_elderly_allocated": "estimated_elderly",
            "centroid_transport_distance": "centroid_transport",
            "weighted_mean_transport_distance": "weighted_transport_mean",
            "weighted_p90_transport_distance": "weighted_transport_p90",
            "centroid_medical_distance": "centroid_medical",
            "weighted_mean_medical_distance": "weighted_medical_mean",
            "weighted_p90_medical_distance": "weighted_medical_p90",
        }
    )[
        [
            "citywide_screening_rank",
            "mesh_code",
            "label",
            "residential_buildings",
            "estimated_elderly",
            "centroid_transport",
            "weighted_transport_mean",
            "weighted_transport_p90",
            "centroid_medical",
            "weighted_medical_mean",
            "weighted_medical_p90",
        ]
    ].to_csv(CANDIDATE_OUTPUT, index=False)

    demographics = strict.merge(access, on="gml_id", how="left", validate="many_to_one")
    output_columns = {
        "gml_id": demographics["gml_id"],
        "mesh_code": demographics["mesh_code"],
        "usage_code": demographics["usage_code"],
        "usage_label": demographics["usage_label"],
        "residential_class": demographics["residential_class"],
        "allocation_method": demographics["allocation_method"],
        "allocation_weight_source": demographics["allocation_weight_source"],
        "allocation_weight": demographics["effective_floor_area_in_mesh"],
        "allocation_fraction": demographics["allocation_fraction"],
        "verified_building_floor_area": demographics["allocation_weight"],
        "building_geometry_footprint_area_m2": demographics[
            "geometry_footprint_area"
        ],
        "mesh_intersection_area_m2": demographics["intersection_area"],
        "footprint_intersection_fraction": demographics["intersection_fraction"],
        "effective_floor_area_in_mesh": demographics["effective_floor_area_in_mesh"],
        "estimated_population": demographics["estimated_population"],
        "estimated_elderly_population": demographics["estimated_elderly_population"],
        "population_resolution": demographics["population_resolution"],
        "footprint_area": numeric_values(demographics["buildingFootprintArea"]),
        "total_floor_area": numeric_values(demographics["totalFloorArea"]),
        "storeys_above_ground": numeric_values(demographics["storeysAboveGround"]),
        "longitude": demographics["longitude"],
        "latitude": demographics["latitude"],
        "nearest_station_name": demographics["nearest_station_name"],
        "nearest_station_distance_m": demographics["nearest_station_distance_m"],
        "nearest_bus_stop_name": demographics["nearest_bus_stop_name"],
        "nearest_bus_stop_distance_m": demographics["nearest_bus_stop_distance_m"],
        "nearest_public_transport_type": demographics["nearest_public_transport_type"],
        "nearest_public_transport_name": demographics["nearest_public_transport_name"],
        "nearest_public_transport_distance_m": demographics[
            "nearest_public_transport_distance_m"
        ],
        "nearest_medical_name": demographics["nearest_medical_name"],
        "nearest_medical_distance_m": demographics["nearest_medical_distance_m"],
        "conservative_facility_policy": demographics["conservative_facility_policy"],
        "nearest_conservative_public_transport_type": demographics[
            "nearest_conservative_public_transport_type"
        ],
        "nearest_conservative_public_transport_name": demographics[
            "nearest_conservative_public_transport_name"
        ],
        "nearest_conservative_public_transport_distance_m": demographics[
            "nearest_conservative_public_transport_distance_m"
        ],
        "nearest_conservative_medical_name": demographics[
            "nearest_conservative_medical_name"
        ],
        "nearest_conservative_medical_distance_m": demographics[
            "nearest_conservative_medical_distance_m"
        ],
        "facility_policy": demographics["facility_policy"],
        "origin_method": demographics["origin_method"],
        "source_gml": demographics["source_gml"],
        "source_member_crc32": demographics["source_member_crc32"],
        "source_hash": archive_sha256,
        "source_population_year": args.population_year,
    }
    pd.DataFrame(output_columns).to_parquet(PARQUET_OUTPUT, index=False)

    coverage = _coverage(
        pd.DataFrame(meshes.drop(columns="geometry")), crosswalk, strict
    )
    comparison_coverage = coverage.loc[coverage["primary_eligible_disclosure"].astype(bool)]
    deep_dive = strict_detail.loc[strict_detail["mesh_code"].eq(DEEP_DIVE_MESH)]
    if len(deep_dive) != 1:
        raise ValueError("Deep-dive mesh must have exactly one detail result")
    deep = deep_dive.iloc[0].to_dict()
    deep["mixed_residential_buildings"] = int(
        crosswalk.loc[
            crosswalk["mesh_code"].eq(DEEP_DIVE_MESH)
            & crosswalk["usage_code"].astype(str).isin(MIXED_RESIDENTIAL_CODES),
            "gml_id",
        ].nunique()
    )
    deep_records = demographics.loc[demographics["mesh_code"].eq(DEEP_DIVE_MESH)]
    conservative_transport = weighted_statistics(
        deep_records["nearest_conservative_public_transport_distance_m"],
        deep_records["estimated_elderly_population"],
    )
    conservative_medical = weighted_statistics(
        deep_records["nearest_conservative_medical_distance_m"],
        deep_records["estimated_elderly_population"],
    )
    if args.publish_demo:
        _publish_aggregated_demo_detail(deep)

    timings["total_seconds"] = time.perf_counter() - total_started
    provenance = {
        "dataset_archive_sha256": archive_sha256,
        "citygml_specification": inventory["dataset"]["product_specification_version"],
        "ade_schema_version": inventory["dataset"]["ade_schema_version"],
        "population_source": "e-Stat 2020 census 500m mesh T001192",
        "population_year": args.population_year,
        "facility_sources": {
            "station": "PLATEAU related data 2025",
            "bus_stop": "National Land Numerical Information P11 2022",
            "medical": "National Land Numerical Information P04 2020",
        },
        "usage_mapping_version": f"{USAGE_CODELIST}:{usage_mapping['codelist_member_crc32'].iloc[0]}",
        "allocation_policy": "strict_residential",
        "sensitivity_policy": "residential_plus_mixed_without_assumed_residential_share",
        "crs": ANALYSIS_CRS,
        "software": _software_state(),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    summary = {
        "schema_version": 1,
        "provenance": provenance,
        "counts": {
            "buildings_audited": len(buildings),
            "strict_residential_buildings_citywide": int(
                buildings["usage_code"].isin(STRICT_RESIDENTIAL_CODES).sum()
            ),
            "mixed_residential_buildings_citywide": int(
                buildings["usage_code"].isin(MIXED_RESIDENTIAL_CODES).sum()
            ),
            "uncertain_buildings_citywide": int(
                buildings["residential_class"].eq("uncertain").sum()
            ),
            "crosswalk_records": len(crosswalk),
            "multi_mesh_buildings": int(crosswalk.groupby("gml_id")["mesh_code"].nunique().gt(1).sum()),
            "strict_demographic_records": len(strict),
            "strict_allocated_meshes": int(strict["mesh_code"].nunique()),
            "mixed_sensitivity_allocated_meshes": int(mixed["mesh_code"].nunique()),
        },
        "coverage_all_meshes": coverage["population_resolution"].value_counts().to_dict(),
        "coverage_unaffected_comparison_meshes": {
            "denominator": len(comparison_coverage),
            "counts": comparison_coverage["population_resolution"].value_counts().to_dict(),
            "percentages": (
                comparison_coverage["population_resolution"].value_counts(normalize=True) * 100
            ).round(3).to_dict(),
        },
        "conservation": {
            "strict_population_max_abs_error": strict_conservation["population_error"].abs().max(),
            "strict_elderly_max_abs_error": strict_conservation["elderly_error"].abs().max(),
            "mixed_population_max_abs_error": mixed_conservation["population_error"].abs().max(),
            "mixed_elderly_max_abs_error": mixed_conservation["elderly_error"].abs().max(),
        },
        "sensitivity": {
            "strict": {
                "records": len(strict),
                "meshes": int(strict["mesh_code"].nunique()),
                "estimated_population": strict["estimated_population"].sum(),
                "estimated_elderly": strict["estimated_elderly_population"].sum(),
            },
            "residential_plus_mixed": {
                "records": len(mixed),
                "meshes": int(mixed["mesh_code"].nunique()),
                "estimated_population": mixed["estimated_population"].sum(),
                "estimated_elderly": mixed["estimated_elderly_population"].sum(),
                "mixed_use_share_assumption": None,
            },
            "deep_dive_strict": deep,
            "deep_dive_plus_mixed": mixed_detail.loc[
                mixed_detail["mesh_code"].eq(DEEP_DIVE_MESH)
            ].iloc[0].to_dict(),
            "deep_dive_cross_border_conservative": {
                "facility_policy": (
                    "two_km_cross_border_excluding_uncertain_medical"
                ),
                "weighted_transport": conservative_transport,
                "weighted_medical": conservative_medical,
            },
        },
        f"deep_dive_mesh_{DEEP_DIVE_MESH}": deep,
        "informative_examples": _informative_examples(strict_detail),
        "performance": {
            **{key: round(value, 3) for key, value in timings.items()},
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "parquet_bytes": PARQUET_OUTPUT.stat().st_size,
            "audit_json_bytes": AUDIT_OUTPUT.stat().st_size,
            "detail_csv_bytes": DETAIL_OUTPUT.stat().st_size,
        },
        "privacy": {
            "statement": "Model-based estimates allocated from 500m census statistics; not residents, registry, households, individuals, or confirmed occupancy.",
            "suppressed_or_aggregation_affected_disaggregated": False,
            "public_full_building_dataset": False,
        },
        "facility_policy_audit": {
            "baseline": {
                "policy": "city_baseline_including_uncertain_medical",
                "stations": len(facilities["stations"]),
                "bus_stops": len(facilities["buses"]),
                "transport_points": len(facilities["transport"]),
                "medical_points": len(facilities["medical"]),
            },
            "conservative": {
                "policy": "two_km_cross_border_excluding_uncertain_medical",
                "transport_points": len(facilities["conservative_transport"]),
                "medical_points": len(facilities["conservative_medical"]),
            },
        },
    }
    _write_json(SUMMARY_OUTPUT, summary)
    print(json.dumps(_json_value(summary["counts"]), ensure_ascii=False))
    print(json.dumps(_json_value(summary["performance"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
