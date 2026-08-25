"""Build the final, evidence-backed assets used by the CITY GAP demo.

The script joins official PLATEAU building representative points to the same
500 m meshes used by the analysis, extracts the road surfaces around the
selected deep-dive mesh, and evaluates deterministic intervention anchors on
official PLATEAU road surfaces.  A road-surface point is only a screening
anchor; it is never described as an available parcel or a confirmed stop.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import mapping

from analysis.scripts.inspect_plateau_buildings import LOD_DIRS, parse_directory
from analysis.src.plateau_road_network import iter_road_surfaces
from analysis.src.spatial import boundary_from_plateau, intersects_boundary

ROOT = Path(__file__).resolve().parents[2]
CITYGML_ZIP = (
    ROOT / "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
)
METRICS_CSV = ROOT / "analysis/outputs/real/maizuru_mesh_metrics.csv"
METRICS_GEOJSON = ROOT / "analysis/outputs/real/maizuru_city_gap.geojson"
BORDER = ROOT / "data/raw/plateau_related/26202_maizuru-shi_city_2025_border.geojson"
STATIONS = ROOT / "data/raw/plateau_related/26202_maizuru-shi_city_2025_station.geojson"
BUS_STOPS = (
    ROOT
    / "data/raw/transport/P11-22_26_SHP/P11-22_26_SHP/P11-22_26.geojson"
)
OUTPUT_CSV = ROOT / "analysis/outputs/real/plateau_covered_candidates.csv"
OUTPUT_REPORT = ROOT / "analysis/outputs/real/maizuru_final_demo.json"
OUTPUT_WEB = ROOT / "frontend/public/data/final_demo.json"
OUTPUT_ROADS = ROOT / "frontend/public/data/plateau_roads.geojson"
NETWORK_METRICS = ROOT / "analysis/outputs/real/maizuru_network_accessibility_meshes.csv"
NETWORK_SUMMARY = ROOT / "analysis/outputs/real/maizuru_road_network_summary.json"
TERRAIN_METRICS = ROOT / "analysis/outputs/real/maizuru_terrain_accessibility_meshes.csv"
TERRAIN_SUMMARY = ROOT / "analysis/outputs/real/maizuru_terrain_network_summary.json"
BUILDING_DEMOGRAPHICS_SUMMARY = (
    ROOT / "analysis/outputs/real/maizuru_building_demographics_summary.json"
)

WEB_CRS = "EPSG:4326"
ANALYSIS_CRS = "EPSG:6674"
MIN_EXISTING_TRANSPORT_DISTANCE_M = 150.0
MIN_CANDIDATE_SEPARATION_M = 1_500.0
TOP_CANDIDATES = 3
TOP_COVERED = 5

def _write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = {"ensure_ascii": False}
    if compact:
        options["separators"] = (",", ":")
    else:
        options["indent"] = 2
    path.write_text(json.dumps(value, **options) + "\n", encoding="utf-8")


def _building_demographic_detail(mesh_code: str) -> dict[str, Any] | None:
    if not BUILDING_DEMOGRAPHICS_SUMMARY.exists():
        return None
    summary = json.loads(BUILDING_DEMOGRAPHICS_SUMMARY.read_text(encoding="utf-8"))
    deep = summary.get(f"deep_dive_mesh_{mesh_code}")
    if deep is None:
        return None
    return {
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
        "weighted_median_medical_distance_m": float(
            deep["weighted_median_medical_distance"]
        ),
        "weighted_p90_medical_distance_m": float(deep["weighted_p90_medical_distance"]),
    }


def _area_label(name: Any, transport_type: Any) -> str:
    clean = str(name).strip() if name is not None and not pd.isna(name) else ""
    if not clean:
        return "名称未確認の地域"
    if transport_type == "station" or clean.endswith("駅"):
        return f"{clean}周辺"
    return f"{clean}バス停周辺"


def _mesh_bounds(row: pd.Series) -> tuple[float, float, float, float]:
    return (
        float(row["centroid_lon"]) - 0.003125,
        float(row["centroid_lat"]) - 1 / 480,
        float(row["centroid_lon"]) + 0.003125,
        float(row["centroid_lat"]) + 1 / 480,
    )


def _building_coverage(
    metrics: pd.DataFrame, meshes: gpd.GeoDataFrame
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    parsed = parse_directory(LOD_DIRS["lod2"])
    records = list(parsed["records"].values())
    points = gpd.GeoDataFrame(
        [{"gml_id": item["gml_id"]} for item in records],
        geometry=gpd.points_from_xy(
            [item["x"] for item in records], [item["y"] for item in records]
        ),
        crs=WEB_CRS,
    )
    joined = gpd.sjoin(
        points,
        meshes[["mesh_code", "geometry"]].to_crs(WEB_CRS),
        predicate="within",
        how="inner",
    )
    counts = joined.groupby("mesh_code").size().rename("plateau_building_count")
    covered = metrics.merge(counts, on="mesh_code", how="inner")
    covered = covered.loc[covered["rank_c_unfiltered"].notna()].sort_values(
        ["rank_c_unfiltered", "mesh_code"]
    )
    by_id = {item["gml_id"]: item for item in records}
    mesh_records: dict[str, dict[str, Any]] = {}
    for mesh_code, rows in joined.groupby("mesh_code"):
        mesh_records[str(mesh_code)] = {
            str(identifier): by_id[str(identifier)] for identifier in rows["gml_id"]
        }
    return covered, mesh_records


def _covered_rows(covered: pd.DataFrame) -> list[dict[str, Any]]:
    result = []
    for row in covered.head(TOP_COVERED).itertuples():
        result.append(
            {
                "mesh_code": str(row.mesh_code),
                "overall_rank": int(row.rank_c_unfiltered),
                "population": int(row.population),
                "elderly_population": int(row.elderly_population),
                "elderly_ratio": round(float(row.elderly_ratio), 6),
                "transport_distance": round(
                    float(row.nearest_public_transport_distance_m), 3
                ),
                "medical_distance": round(float(row.nearest_medical_distance_m), 3),
                "score_c": round(float(row.exploratory_score_c), 9),
                "plateau_building_count": int(row.plateau_building_count),
                "area_label": _area_label(
                    row.nearest_public_transport_name,
                    row.nearest_public_transport_type,
                ),
            }
        )
    return result


def _write_covered_csv(rows: list[dict[str, Any]]) -> None:
    required = [
        "mesh_code",
        "overall_rank",
        "population",
        "elderly_population",
        "elderly_ratio",
        "transport_distance",
        "medical_distance",
        "score_c",
        "plateau_building_count",
    ]
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=required, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _parse_roads(archive: zipfile.ZipFile) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    members = sorted(
        name
        for name in archive.namelist()
        if name.startswith("udx/tran/") and name.endswith(".gml")
    )
    for member in members:
        info = archive.getinfo(member)
        with archive.open(info) as stream:
            for surface in iter_road_surfaces(
                stream,
                source_member=member,
                source_member_crc32=f"{info.CRC:08x}",
            ):
                polygon = surface["geometry"]
                point = polygon.representative_point()
                rows.append(
                    {
                        "road_id": f"{surface['gml_id']}-{surface['surface_index']}",
                        "road_name": surface["name"],
                        "road_class": surface["road_class"],
                        "road_function": surface["function_code"],
                        "source_member": member,
                        "source_member_crc32": surface["source_member_crc32"],
                        "anchor_lon": point.x,
                        "anchor_lat": point.y,
                        "geometry": polygon,
                    }
                )
    inventory = {
        "gml_files": len(members),
        "gml_uncompressed_bytes": sum(archive.getinfo(name).file_size for name in members),
        "road_surfaces": len(rows),
        "geometry_lod": "LOD1 MultiSurface",
        "parser_policy": "LOD1 exterior with interior rings; LOD2 traffic-area polygons excluded",
        "network_topology": False,
    }
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=WEB_CRS), inventory


def _transport_points(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    stations = intersects_boundary(gpd.read_file(STATIONS), boundary).to_crs(WEB_CRS)
    buses = intersects_boundary(gpd.read_file(BUS_STOPS), boundary).to_crs(WEB_CRS)
    station_points = gpd.GeoDataFrame(
        {
            "transport_name": stations["駅名"].astype(str).str.strip(),
            "transport_type": "station",
        },
        geometry=stations.geometry,
        crs=WEB_CRS,
    )
    bus_points = gpd.GeoDataFrame(
        {
            "transport_name": buses["P11_001"].astype(str).str.strip(),
            "transport_type": "bus_stop",
        },
        geometry=buses.geometry,
        crs=WEB_CRS,
    )
    return pd.concat([station_points, bus_points], ignore_index=True)


def _percentile_ranks(values: np.ndarray) -> np.ndarray:
    return pd.Series(values).rank(method="average", pct=True).to_numpy()


def _evaluate_point(
    metrics: pd.DataFrame,
    mesh_x: np.ndarray,
    mesh_y: np.ndarray,
    point_x: float,
    point_y: float,
    *,
    detailed: bool = False,
) -> dict[str, Any]:
    before_distance = metrics["nearest_public_transport_distance_m"].to_numpy(float)
    point_distance = np.hypot(mesh_x - point_x, mesh_y - point_y)
    after_distance = np.minimum(before_distance, point_distance)
    after_percentile = _percentile_ranks(after_distance)
    before_score = metrics["exploratory_score_c"].to_numpy(float)
    after_score = (
        metrics["elderly_population_percentile"].to_numpy(float)
        * after_percentile
        * metrics["medical_distance_percentile"].to_numpy(float)
    )
    reduction = before_score - after_score
    improved = after_distance < before_distance - 1e-6
    elderly = metrics["elderly_population"].fillna(0).to_numpy(float)
    top_index = int(np.argmax(reduction))
    result: dict[str, Any] = {
        "objective_total_score_c_reduction": round(float(reduction.sum()), 9),
        "improved_mesh_count": int(improved.sum()),
        "affected_elderly_population": int(elderly[improved].sum()),
        "average_transport_distance_improvement_m": round(
            float((before_distance[improved] - after_distance[improved]).mean())
            if improved.any()
            else 0.0,
            3,
        ),
        "top_improvement_mesh": str(metrics.iloc[top_index]["mesh_code"]),
        "top_improvement": {
            "before_distance_m": round(float(before_distance[top_index]), 3),
            "after_distance_m": round(float(after_distance[top_index]), 3),
            "before_score_c": round(float(before_score[top_index]), 9),
            "after_score_c": round(float(after_score[top_index]), 9),
            "score_c_reduction": round(float(reduction[top_index]), 9),
        },
    }
    if detailed:
        result["mesh_results"] = {
            str(metrics.iloc[index]["mesh_code"]): {
                "before_distance_m": round(float(before_distance[index]), 3),
                "after_distance_m": round(float(after_distance[index]), 3),
                "before_score_c": round(float(before_score[index]), 9),
                "after_score_c": round(float(after_score[index]), 9),
                "score_c_reduction": round(float(reduction[index]), 9),
            }
            for index in range(len(metrics))
        }
    return result


def _placement_candidates(
    metrics: pd.DataFrame,
    roads: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
) -> list[dict[str, Any]]:
    comparison = metrics.loc[metrics["rank_c_unfiltered"].notna()].copy().reset_index(drop=True)
    transformer = Transformer.from_crs(WEB_CRS, ANALYSIS_CRS, always_xy=True)
    mesh_x, mesh_y = transformer.transform(
        comparison["centroid_lon"].to_numpy(), comparison["centroid_lat"].to_numpy()
    )
    city_roads = intersects_boundary(roads, boundary).reset_index(drop=True)
    anchor_x, anchor_y = transformer.transform(
        city_roads["anchor_lon"].to_numpy(), city_roads["anchor_lat"].to_numpy()
    )
    road_points = gpd.GeoDataFrame(
        city_roads.drop(columns="geometry"),
        geometry=gpd.points_from_xy(anchor_x, anchor_y),
        crs=ANALYSIS_CRS,
    )
    transport = _transport_points(boundary).to_crs(ANALYSIS_CRS)
    nearest = gpd.sjoin_nearest(
        road_points,
        transport,
        how="left",
        distance_col="existing_transport_distance_m",
    )
    nearest = nearest.loc[~nearest.index.duplicated(keep="first")]
    pool = nearest.loc[
        nearest["existing_transport_distance_m"] > MIN_EXISTING_TRANSPORT_DISTANCE_M
    ].reset_index(drop=True)

    evaluated: list[tuple[float, int, dict[str, Any]]] = []
    for row in pool.itertuples():
        result = _evaluate_point(
            comparison,
            np.asarray(mesh_x),
            np.asarray(mesh_y),
            float(row.geometry.x),
            float(row.geometry.y),
        )
        evaluated.append(
            (
                float(result["objective_total_score_c_reduction"]),
                int(row.Index),
                result,
            )
        )
    evaluated.sort(key=lambda item: (-item[0], str(pool.loc[item[1], "road_id"])))

    selected: list[tuple[int, dict[str, Any]]] = []
    for _, pool_index, result in evaluated:
        point = pool.loc[pool_index].geometry
        if any(
            point.distance(pool.loc[other_index].geometry) < MIN_CANDIDATE_SEPARATION_M
            for other_index, _ in selected
        ):
            continue
        selected.append((pool_index, result))
        if len(selected) == TOP_CANDIDATES:
            break
    if len(selected) != TOP_CANDIDATES:
        raise ValueError("Could not select three spatially separated placement candidates")

    result_rows = []
    for rank, (pool_index, result) in enumerate(selected, start=1):
        row = pool.loc[pool_index]
        result = _evaluate_point(
            comparison,
            np.asarray(mesh_x),
            np.asarray(mesh_y),
            float(row.geometry.x),
            float(row.geometry.y),
            detailed=True,
        )
        mesh_results = result.pop("mesh_results")
        top_mesh = result["top_improvement_mesh"]
        result_rows.append(
            {
                "candidate_rank": rank,
                "candidate_id": str(row["road_id"]),
                "area_label": _area_label(
                    row["transport_name"], row["transport_type"]
                ),
                "longitude": round(float(row["anchor_lon"]), 9),
                "latitude": round(float(row["anchor_lat"]), 9),
                "source": "Project PLATEAU 舞鶴市2025 道路LOD1面の代表点",
                "road_name": row["road_name"],
                "road_function_code": row["road_function"],
                "nearest_existing_transport_name": row["transport_name"],
                "existing_transport_distance_m": round(
                    float(row["existing_transport_distance_m"]), 3
                ),
                **result,
                "top_improvement": {"mesh_code": top_mesh, **result["top_improvement"]},
                "deep_dive_before_after": mesh_results.get(top_mesh),
            }
        )
    return result_rows


def _theme_inventory(archive: zipfile.ZipFile) -> dict[str, Any]:
    themes = {}
    for theme in ("bldg", "tran", "dem", "luse", "urf", "tnm", "fld"):
        members = [
            info
            for info in archive.infolist()
            if info.filename.startswith(f"udx/{theme}/")
            and info.filename.endswith(".gml")
        ]
        themes[theme] = {
            "available": bool(members),
            "gml_files": len(members),
            "uncompressed_bytes": sum(info.file_size for info in members),
        }
    return themes


def _dem_member_for_mesh(
    archive: zipfile.ZipFile, mesh_row: pd.Series
) -> str | None:
    longitude = float(mesh_row["centroid_lon"])
    latitude = float(mesh_row["centroid_lat"])
    prefix = str(mesh_row["mesh_code"])[:6]
    for name in sorted(archive.namelist()):
        if not name.startswith(f"udx/dem/{prefix}_") or not name.endswith(".gml"):
            continue
        with archive.open(name) as stream:
            head = stream.read(12_000).decode("utf-8", errors="replace")
        lower_start = head.find("<gml:lowerCorner>")
        lower_end = head.find("</gml:lowerCorner>")
        upper_start = head.find("<gml:upperCorner>")
        upper_end = head.find("</gml:upperCorner>")
        if min(lower_start, lower_end, upper_start, upper_end) < 0:
            continue
        lower = [float(value) for value in head[lower_start + 17 : lower_end].split()]
        upper = [float(value) for value in head[upper_start + 17 : upper_end].split()]
        if lower[0] <= latitude <= upper[0] and lower[1] <= longitude <= upper[1]:
            return name
    return None


def _terrain_summary(
    archive: zipfile.ZipFile, mesh_row: pd.Series, *, skip: bool
) -> dict[str, Any]:
    member = _dem_member_for_mesh(archive, mesh_row)
    if member is None:
        return {"status": "not_covered", "source_member": None}
    if skip:
        return {"status": "available_not_computed", "source_member": member}
    west, south, east, north = _mesh_bounds(mesh_row)
    transformer = Transformer.from_crs(WEB_CRS, ANALYSIS_CRS, always_xy=True)
    elevations: list[float] = []
    slopes: list[float] = []
    with archive.open(member) as stream:
        start_tag = b"<gml:posList>"
        end_tag = b"</gml:posList>"
        buffer = b""
        finished = False
        while not finished:
            chunk = stream.read(1024 * 1024)
            if chunk:
                buffer += chunk
            else:
                finished = True
            while True:
                start = buffer.find(start_tag)
                if start < 0:
                    if len(buffer) > len(start_tag):
                        buffer = buffer[-len(start_tag) :]
                    break
                end = buffer.find(end_tag, start + len(start_tag))
                if end < 0:
                    buffer = buffer[start:]
                    break
                text = buffer[start + len(start_tag) : end]
                buffer = buffer[end + len(end_tag) :]
                values = [float(value) for value in text.split()]
                if len(values) < 12 or len(values) % 3:
                    continue
                points = [
                    (values[cursor + 1], values[cursor], values[cursor + 2])
                    for cursor in range(0, len(values) - 3, 3)
                ]
                if len(points) < 3:
                    continue
                longitude = sum(point[0] for point in points[:3]) / 3
                latitude = sum(point[1] for point in points[:3]) / 3
                if not (west <= longitude < east and south <= latitude < north):
                    continue
                first, second, third = points[:3]
                ax, ay = transformer.transform(first[0], first[1])
                bx, by = transformer.transform(second[0], second[1])
                cx, cy = transformer.transform(third[0], third[1])
                ux, uy, uz = bx - ax, by - ay, second[2] - first[2]
                vx, vy, vz = cx - ax, cy - ay, third[2] - first[2]
                nx = uy * vz - uz * vy
                ny = uz * vx - ux * vz
                nz = ux * vy - uy * vx
                slopes.append(math.degrees(math.atan2(math.hypot(nx, ny), abs(nz))))
                elevations.extend(point[2] for point in points[:3])
    if not slopes:
        return {"status": "available_no_triangles_in_mesh", "source_member": member}
    ordered = sorted(slopes)
    return {
        "status": "computed_from_official_dem_tin",
        "source_member": member,
        "triangles": len(slopes),
        "elevation_m": {
            "min": round(min(elevations), 3),
            "median": round(statistics.median(elevations), 3),
            "max": round(max(elevations), 3),
        },
        "triangle_slope_degrees": {
            "median": round(statistics.median(slopes), 3),
            "p90": round(ordered[int(0.9 * (len(ordered) - 1))], 3),
            "max": round(max(slopes), 3),
        },
        "limitation": "TIN三角形の局所勾配要約であり、歩行経路の坂や通行可能性ではない。",
    }


def _building_attribute_summary(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def detail(attributes: dict[str, Any]) -> dict[str, Any]:
        value = attributes.get("uro:BuildingDetailAttribute")
        return value[0] if isinstance(value, list) and value else {}

    attributes = [record["attrs"] for record in records.values()]
    lods = [int(record["lod"]) for record in records.values()]
    return {
        "records": len(records),
        "geometry_lod": {str(key): value for key, value in sorted(Counter(lods).items())},
        "displayed_on_click": [
            "gml_id",
            "bldg:usage",
            "bldg:measuredHeight",
            "bldg:storeysAboveGround",
            "bldg:storeysBelowGround",
            "uro:buildingFootprintArea",
            "uro:totalFloorArea",
            "3D Tiles geometry LOD",
        ],
        "attribute_known_counts": {
            "usage": sum(item.get("bldg:usage") not in {None, "", "不明"} for item in attributes),
            "measured_height": sum(
                isinstance(item.get("bldg:measuredHeight"), (int, float))
                and item.get("bldg:measuredHeight") not in {-9999, 9999}
                for item in attributes
            ),
            "storeys_above_ground": sum(
                isinstance(item.get("bldg:storeysAboveGround"), (int, float))
                and item.get("bldg:storeysAboveGround") not in {-9999, 9999}
                for item in attributes
            ),
            "footprint_area": sum(
                isinstance(detail(item).get("uro:buildingFootprintArea"), (int, float))
                and detail(item).get("uro:buildingFootprintArea") not in {-9999, 9999}
                for item in attributes
            ),
            "total_floor_area": sum(
                isinstance(detail(item).get("uro:totalFloorArea"), (int, float))
                and detail(item).get("uro:totalFloorArea") not in {-9999, 9999}
                for item in attributes
            ),
        },
    }


def build(*, skip_dem: bool = False) -> dict[str, Any]:
    for required in (CITYGML_ZIP, METRICS_CSV, METRICS_GEOJSON, BORDER, STATIONS, BUS_STOPS):
        if not required.is_file():
            raise FileNotFoundError(required)
    published_building_detail = None
    if OUTPUT_REPORT.exists():
        existing_report = json.loads(OUTPUT_REPORT.read_text(encoding="utf-8"))
        published_building_detail = existing_report.get("deep_dive", {}).get(
            "building_demographics_detail"
        )
    metrics = pd.read_csv(METRICS_CSV, dtype={"mesh_code": str})
    network_metrics = (
        pd.read_csv(NETWORK_METRICS, dtype={"mesh_code": str}).set_index("mesh_code")
        if NETWORK_METRICS.exists()
        else None
    )
    terrain_metrics = (
        pd.read_csv(TERRAIN_METRICS, dtype={"mesh_code": str}).set_index("mesh_code")
        if TERRAIN_METRICS.exists()
        else None
    )
    network_summary = (
        json.loads(NETWORK_SUMMARY.read_text(encoding="utf-8"))
        if NETWORK_SUMMARY.exists()
        else None
    )
    terrain_summary = (
        json.loads(TERRAIN_SUMMARY.read_text(encoding="utf-8"))
        if TERRAIN_SUMMARY.exists()
        else None
    )
    meshes = gpd.read_file(METRICS_GEOJSON)
    meshes["mesh_code"] = meshes["mesh_code"].astype(str)
    covered, mesh_records = _building_coverage(metrics, meshes)
    covered_rows = _covered_rows(covered)
    _write_covered_csv(covered_rows)

    border = gpd.read_file(BORDER)
    boundary = boundary_from_plateau(border)
    with zipfile.ZipFile(CITYGML_ZIP) as archive:
        roads, road_inventory = _parse_roads(archive)
        placements = _placement_candidates(metrics, roads, boundary)
        deep_mesh_code = placements[0]["top_improvement_mesh"]
        if deep_mesh_code not in {row["mesh_code"] for row in covered_rows}:
            deep_mesh_code = covered_rows[0]["mesh_code"]
        deep_row = metrics.set_index("mesh_code").loc[deep_mesh_code].copy()
        deep_row["mesh_code"] = deep_mesh_code
        deep_geometry = meshes.set_index("mesh_code").loc[deep_mesh_code].geometry
        deep_roads = roads.loc[roads.intersects(deep_geometry)].copy()
        road_features = []
        for row in deep_roads.itertuples():
            road_features.append(
                {
                    "type": "Feature",
                    "id": row.road_id,
                    "properties": {
                        "road_id": row.road_id,
                        "road_name": row.road_name,
                        "road_class": row.road_class,
                        "road_function": row.road_function,
                        "source": "Project PLATEAU 舞鶴市2025 道路LOD1",
                    },
                    "geometry": mapping(row.geometry),
                }
            )
        roads_geojson = {"type": "FeatureCollection", "features": road_features}
        _write_json(OUTPUT_ROADS, roads_geojson, compact=True)
        terrain = _terrain_summary(archive, deep_row, skip=skip_dem)
        themes = _theme_inventory(archive)

    deep_covered = next(row for row in covered_rows if row["mesh_code"] == deep_mesh_code)
    deep_records = mesh_records[deep_mesh_code]
    published_building_detail = (
        _building_demographic_detail(deep_mesh_code) or published_building_detail
    )
    network_row = (
        network_metrics.loc[deep_mesh_code]
        if network_metrics is not None and deep_mesh_code in network_metrics.index
        else None
    )
    terrain_row = (
        terrain_metrics.loc[deep_mesh_code]
        if terrain_metrics is not None and deep_mesh_code in terrain_metrics.index
        else None
    )
    rank_one = metrics.loc[metrics["rank"] == 1].iloc[0]
    report = {
        "schema_version": "1.0.0",
        "dataset": "3D都市モデル（Project PLATEAU）舞鶴市（2025年度）",
        "comparison_mesh_count": int(metrics["rank_c_unfiltered"].notna().sum()),
        "rank_one": {
            "mesh_code": str(rank_one["mesh_code"]),
            "area_label": _area_label(
                rank_one["nearest_public_transport_name"],
                rank_one["nearest_public_transport_type"],
            ),
            "plateau_building_count": 0,
            "road_gml_for_third_mesh": False,
        },
        "plateau_covered_candidates": covered_rows,
        "deep_dive": {
            **deep_covered,
            "selection_reason": (
                "PLATEAU建物があるCITY GAP上位5件であり、最良の道路面配置候補と"
                "その最大改善メッシュが同じ範囲にあるため。"
            ),
            "plateau_buildings": _building_attribute_summary(deep_records),
            "plateau_road_surfaces_intersecting_mesh": len(deep_roads),
            "terrain": terrain,
            "building_score_linkage": False,
            "building_score_note": (
                "建物属性は地域文脈の確認用。CITY GAPは500mメッシュ単位であり、"
                "個々の建物にスコアを付与していない。"
            ),
            **(
                {"building_demographics_detail": published_building_detail}
                if published_building_detail is not None
                else {}
            ),
        },
        "placement_optimization": {
            "candidate_source": "公式PLATEAU道路LOD1面の内部代表点",
            "screening_rule": (
                f"舞鶴市内、既存駅・バス停から{MIN_EXISTING_TRANSPORT_DISTANCE_M:.0f}m超、"
                f"上位地点間を{MIN_CANDIDATE_SEPARATION_M:.0f}m以上離す"
            ),
            "objective": (
                "既存286比較メッシュのCITY GAP Score C合計の純減少量を最大化。"
                "同じEPSG:6674直線距離とpercentile再計算を使用。"
            ),
            "evaluated_meaning": (
                "道路面上の探索アンカーであり、用地確保・停留所設置・運行可能性を"
                "確認した候補地ではない。"
            ),
            "candidates": placements,
        },
        "plateau_context": {
            "themes": themes,
            "roads": road_inventory,
            "distance_comparison": {
                "mesh_code": deep_mesh_code,
                "centroid_euclidean_transport_distance_m": deep_covered[
                    "transport_distance"
                ],
                "building_weighted_euclidean_transport_distance_m": (
                    float(network_row["weighted_mean_transport_distance"])
                    if network_row is not None
                    else None
                ),
                "experimental_road_surface_network_transport_distance_m": (
                    float(network_row["network_transport_weighted_mean_distance_m"])
                    if network_row is not None
                    else None
                ),
                "network_metric_status": (
                    network_row["network_metric_status"] if network_row is not None else "unavailable"
                ),
                "graph_version": (
                    network_summary["graph"]["graph_version"] if network_summary else None
                ),
                "pedestrian_network": False,
                "route_semantics": (
                    network_summary["graph"]["route_semantics"] if network_summary else None
                ),
                "claim_boundary": (
                    "実験的なPLATEAU LOD1道路面隣接距離であり、徒歩経路・所要時間ではない。"
                ),
            },
            "terrain_route_context": {
                "status": terrain_row["terrain_metric_status"] if terrain_row is not None else "unavailable",
                "transport_weighted_mean_ascent_m": (
                    float(terrain_row["transport_weighted_mean_ascent_m"])
                    if terrain_row is not None
                    else None
                ),
                "transport_weighted_mean_descent_m": (
                    float(terrain_row["transport_weighted_mean_descent_m"])
                    if terrain_row is not None
                    else None
                ),
                "node_terrain_coverage": (
                    terrain_summary["node_terrain"]["node_terrain_coverage"]
                    if terrain_summary
                    else None
                ),
                "routing_penalty_applied": False,
                "claim_boundary": (
                    "道路面代表点間のDEM端点成分。測量道路勾配・歩行energyではない。"
                ),
            },
            "current_use": [
                "500mメッシュ境界と公式施設点を重ねる",
                "公式3D建物と実属性をクリック確認する",
                "建物収録範囲を可視化する",
                "公式道路面上から配置探索アンカーを生成する",
                "DEM TINから地域内の標高・局所勾配を要約する",
                "建物加重Euclidean距離と実験道路面隣接距離を比較する",
                "DEM標高からrouteの上り・下りを距離と分けて表示する",
            ],
            "future_use": [
                "公式歩行者networkによる建物入口起点の経路距離",
                "確認済みの道路接続・横断条件を含む到達圏",
                "現地確認済みの候補用地と運行条件による最適化",
            ],
        },
        "offline": {
            "runtime_external_api_required": False,
            "static_assets": [
                "分析GeoJSON/JSON",
                "公式PLATEAU 3D Tiles subset",
                "公式PLATEAU道路GeoJSON subset",
                "CesiumJS runtime assets",
                "Natural Earth II imagery",
            ],
        },
    }
    _write_json(OUTPUT_REPORT, report)
    _write_json(OUTPUT_WEB, report, compact=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-dem", action="store_true", help="Record DEM availability without parsing TIN"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build(skip_dem=args.skip_dem)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
