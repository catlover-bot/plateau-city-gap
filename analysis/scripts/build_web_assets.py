"""Build validated, lightweight static assets for the CITY GAP web application.

The real analysis outputs remain the source of truth.  This module selects only
the fields needed by the browser, converts every geometry to WGS 84, and fails
before publishing when the analysis and web-facing datasets disagree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import mapping, shape

from analysis.src.spatial import (
    boundary_from_plateau,
    deduplicate_stations,
    intersects_boundary,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WEB_CRS = "EPSG:4326"
SCHEMA_VERSION = "1.0.0"
ANALYSIS_VERSION = "0.1.0"

DEFAULTS = {
    "metrics": REPOSITORY_ROOT
    / "analysis/outputs/real/maizuru_city_gap.geojson",
    "top10": REPOSITORY_ROOT
    / "analysis/outputs/real/maizuru_city_gap_top10.csv",
    "summary": REPOSITORY_ROOT / "analysis/outputs/real/maizuru_summary.json",
    "stations": REPOSITORY_ROOT
    / "data/raw/plateau_related/26202_maizuru-shi_city_2025_station.geojson",
    "bus_stops": REPOSITORY_ROOT
    / "data/raw/transport/P11-22_26_SHP/P11-22_26_SHP/P11-22_26.geojson",
    "medical": REPOSITORY_ROOT
    / "data/raw/medical/P04-20_26_GML/P04-20_26_GML/P04-20_26.geojson",
    "boundary": REPOSITORY_ROOT
    / "data/raw/plateau_related/26202_maizuru-shi_city_2025_border.geojson",
    "plateau_inspection": REPOSITORY_ROOT
    / "analysis/outputs/real/maizuru_plateau_building_inspection.json",
    "output_dir": REPOSITORY_ROOT / "frontend/public/data",
}

MESH_PROPERTIES = [
    "mesh_code",
    "area_label",
    "area_label_basis",
    "rank",
    "population",
    "elderly_population",
    "elderly_ratio",
    "centroid_lat",
    "centroid_lon",
    "city_area_fraction",
    "disclosure_status",
    "primary_eligible",
    "nearest_station_name",
    "nearest_station_distance_m",
    "nearest_bus_stop_name",
    "nearest_bus_stop_distance_m",
    "nearest_public_transport_type",
    "nearest_public_transport_name",
    "nearest_public_transport_distance_m",
    "nearest_medical_name",
    "nearest_medical_distance_m",
    "nearest_hospital_name",
    "nearest_hospital_distance_m",
    "elderly_population_percentile",
    "transport_distance_percentile",
    "medical_distance_percentile",
    "exploratory_score_c",
    "pareto_frontier",
]

DISTANCE_PROPERTIES = [
    "nearest_station_distance_m",
    "nearest_bus_stop_distance_m",
    "nearest_public_transport_distance_m",
    "nearest_medical_distance_m",
    "nearest_hospital_distance_m",
]

NUMERIC_MESH_PROPERTIES = [
    "population",
    "elderly_population",
    "elderly_ratio",
    "centroid_lat",
    "centroid_lon",
    "city_area_fraction",
    *DISTANCE_PROPERTIES,
    "elderly_population_percentile",
    "transport_distance_percentile",
    "medical_distance_percentile",
    "exploratory_score_c",
]

LIMITATIONS = [
    "Distances are centroid-to-point straight-line Euclidean distances, not walking or route distances.",
    "P11 2022 does not include service frequency, demand buses, highway buses, or facility shuttles.",
    "P04 describes facilities collected in July 2020 and does not guarantee current availability.",
    "The source years differ: Census and medical data are 2020, bus stops are 2022, and PLATEAU related data are 2025.",
    "Suppressed and aggregation-affected population meshes remain visible but are excluded from the primary ranking.",
    "CITY GAP is an exploratory screening indicator, not a policy decision or confirmation of a local problem.",
    "Official PLATEAU 2025 contains no building models inside the CITY GAP Top 10; a separately validated PLATEAU-covered rank-23 Deep Dive is shown instead.",
    "PLATEAU road LOD1 surfaces do not provide a connected walking network, crossings, or passability; candidate effects therefore remain Euclidean-distance scenarios.",
]


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"Required input is missing: {path}. "
            "Run the real analysis/download workflow before building web assets."
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _json_value(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, str) and value.strip() in {"<NA>", "NaN", "nan"}:
        return None
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _nullable_boolean(value: Any) -> object:
    cleaned = _json_value(value)
    if cleaned is None:
        return pd.NA
    if isinstance(cleaned, bool):
        return cleaned
    if isinstance(cleaned, str) and cleaned.strip().lower() in {"true", "false"}:
        return cleaned.strip().lower() == "true"
    raise ValueError(f"Cannot interpret {value!r} as a boolean")


def _feature_collection(
    layer: gpd.GeoDataFrame,
    properties: Iterable[str],
    *,
    id_column: str | None = None,
) -> dict[str, Any]:
    if layer.crs is None:
        raise ValueError("A source layer does not declare a CRS")
    web_layer = layer.to_crs(WEB_CRS)
    columns = list(properties)
    missing = sorted(set(columns).difference(web_layer.columns))
    if missing:
        raise ValueError(f"Layer is missing web properties: {missing}")
    features: list[dict[str, Any]] = []
    for _, row in web_layer.iterrows():
        feature: dict[str, Any] = {
            "type": "Feature",
            "properties": {column: _json_value(row[column]) for column in columns},
            "geometry": mapping(row.geometry),
        }
        if id_column is not None:
            feature["id"] = str(row[id_column])
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_geojson_geometry(
    collection: Mapping[str, Any],
    *,
    expected_types: set[str] | None = None,
    allow_empty: bool = False,
) -> None:
    """Validate GeoJSON geometry and WGS 84 coordinate ranges."""
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Web geometry must be a GeoJSON FeatureCollection")
    features = collection.get("features")
    if not isinstance(features, list):
        raise TypeError("GeoJSON features must be a list")
    if not features and not allow_empty:
        raise ValueError("GeoJSON FeatureCollection is unexpectedly empty")
    for index, feature in enumerate(features):
        geometry_data = feature.get("geometry")
        if not isinstance(geometry_data, Mapping):
            raise TypeError(f"Feature {index} has no geometry")
        geometry = shape(geometry_data)
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Feature {index} has invalid geometry")
        if expected_types is not None and geometry.geom_type not in expected_types:
            raise ValueError(
                f"Feature {index} has {geometry.geom_type}, expected {expected_types}"
            )
        minimum_x, minimum_y, maximum_x, maximum_y = geometry.bounds
        if not (
            -180 <= minimum_x <= 180
            and -180 <= maximum_x <= 180
            and -90 <= minimum_y <= 90
            and -90 <= maximum_y <= 90
        ):
            raise ValueError(f"Feature {index} has coordinates outside valid lon/lat")


def validate_mesh_assets(
    mesh_collection: Mapping[str, Any], top10: Mapping[str, Any]
) -> None:
    """Validate analysis invariants required by the static frontend."""
    validate_geojson_geometry(
        mesh_collection, expected_types={"Polygon", "MultiPolygon"}
    )
    features = mesh_collection["features"]
    codes: list[str] = []
    feature_by_code: dict[str, Mapping[str, Any]] = {}
    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        code = str(properties.get("mesh_code", "")).strip()
        if not code:
            raise ValueError(f"Mesh feature {index} has no mesh code")
        codes.append(code)
        feature_by_code[code] = feature

        population = properties.get("population")
        elderly = properties.get("elderly_population")
        if not _is_finite_number(population) or population < 0:
            raise ValueError(f"Mesh {code} has invalid population")
        if elderly is not None:
            if not _is_finite_number(elderly) or elderly < 0:
                raise ValueError(f"Mesh {code} has invalid elderly population")
            if elderly > population:
                raise ValueError(f"Mesh {code} has elderly population above population")

        latitude = properties.get("centroid_lat")
        longitude = properties.get("centroid_lon")
        if not _is_finite_number(latitude) or not -90 <= latitude <= 90:
            raise ValueError(f"Mesh {code} has invalid centroid latitude")
        if not _is_finite_number(longitude) or not -180 <= longitude <= 180:
            raise ValueError(f"Mesh {code} has invalid centroid longitude")
        for column in DISTANCE_PROPERTIES:
            distance = properties.get(column)
            if not _is_finite_number(distance) or distance < 0:
                raise ValueError(f"Mesh {code} has invalid {column}")
        for column in (
            "elderly_population_percentile",
            "transport_distance_percentile",
            "medical_distance_percentile",
            "exploratory_score_c",
        ):
            metric = properties.get(column)
            if metric is not None and (
                not _is_finite_number(metric) or not 0 <= metric <= 1
            ):
                raise ValueError(f"Mesh {code} has invalid {column}")

    if len(codes) != len(set(codes)):
        raise ValueError("Mesh codes must be unique")

    items = top10.get("items")
    if not isinstance(items, list) or len(items) != 10:
        raise ValueError("Top 10 must contain exactly ten records")
    ranks = [item.get("rank") for item in items]
    if ranks != list(range(1, 11)):
        raise ValueError("Top 10 ranks must be exactly 1 through 10")
    top_codes = [str(item.get("mesh_code", "")) for item in items]
    if len(top_codes) != len(set(top_codes)):
        raise ValueError("Top 10 mesh codes must be unique")
    missing = sorted(set(top_codes).difference(feature_by_code))
    if missing:
        raise ValueError(f"Top 10 meshes are missing from the full dataset: {missing}")
    for item in items:
        code = str(item["mesh_code"])
        full_rank = feature_by_code[code]["properties"].get("rank")
        if full_rank != item["rank"]:
            raise ValueError(f"Top 10 rank disagrees with mesh dataset for {code}")


def _check_count(label: str, actual: int, expected: Any) -> None:
    if not isinstance(expected, int) or actual != expected:
        raise ValueError(f"{label} count is {actual}; analysis summary expects {expected}")


def _summary_count(counts: Mapping[str, Any], generic: str, legacy: str) -> Any:
    """Read the shared schema while accepting pre-refactor Maizuru summaries."""
    return counts.get(generic, counts.get(legacy))


def _point_sort(layer: gpd.GeoDataFrame, name_column: str) -> gpd.GeoDataFrame:
    result = layer.copy()
    result["_longitude"] = result.to_crs(WEB_CRS).geometry.x
    result["_latitude"] = result.to_crs(WEB_CRS).geometry.y
    result = result.sort_values(
        [name_column, "_longitude", "_latitude"], na_position="last"
    )
    return result.drop(columns=["_longitude", "_latitude"]).reset_index(drop=True)


def _route_values(row: pd.Series) -> list[str]:
    routes: list[str] = []
    for column in sorted(column for column in row.index if column.startswith("P11_003_")):
        value = _json_value(row[column])
        if isinstance(value, str) and value.strip() and value not in routes:
            routes.append(value.strip())
    return routes


def _build_point_layers(
    station_path: Path,
    bus_path: Path,
    medical_path: Path,
    boundary: gpd.GeoDataFrame,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, int]]:
    station_source = gpd.read_file(station_path)
    stations = intersects_boundary(station_source.to_crs(WEB_CRS), boundary)
    stations = _point_sort(deduplicate_stations(stations), "station_name")
    stations["id"] = [f"station-{index:03d}" for index in range(1, len(stations) + 1)]
    stations["name"] = stations["station_name"]
    stations["route_name"] = stations["路線名"]
    stations["operator"] = stations["運営会社"]
    stations["height_m"] = pd.to_numeric(stations["高さ"], errors="coerce")
    stations["source_year"] = 2025
    station_collection = _feature_collection(
        stations,
        ["id", "name", "route_name", "operator", "height_m", "source_year"],
        id_column="id",
    )

    bus_source = gpd.read_file(bus_path)
    buses = _point_sort(
        intersects_boundary(bus_source.to_crs(WEB_CRS), boundary), "P11_001"
    )
    buses["id"] = [f"bus-{index:03d}" for index in range(1, len(buses) + 1)]
    buses["name"] = buses["P11_001"]
    buses["operator"] = buses["P11_002"]
    buses["routes"] = buses.apply(_route_values, axis=1)
    buses["source_year"] = 2022
    bus_collection = _feature_collection(
        buses,
        ["id", "name", "operator", "routes", "source_year"],
        id_column="id",
    )

    medical_source = gpd.read_file(medical_path)
    medical = intersects_boundary(medical_source.to_crs(WEB_CRS), boundary)
    medical["category_code"] = pd.to_numeric(medical["P04_001"], errors="raise").astype(
        int
    )
    medical = _point_sort(medical, "P04_002")
    categories = {1: "hospital", 2: "clinic", 3: "dental_clinic"}
    medical["id"] = [f"medical-{index:03d}" for index in range(1, len(medical) + 1)]
    medical["name"] = medical["P04_002"]
    medical["category"] = medical["category_code"].map(categories).fillna("other")
    medical["address"] = medical["P04_003"]
    medical["included_in_primary_distance"] = medical["category_code"].isin([1, 2])
    medical["source_year"] = 2020
    medical_collection = _feature_collection(
        medical,
        [
            "id",
            "name",
            "category_code",
            "category",
            "address",
            "included_in_primary_distance",
            "source_year",
        ],
        id_column="id",
    )
    counts = {
        "stations_source": len(station_source),
        "stations_web": len(stations),
        "bus_stops_source": len(bus_source),
        "bus_stops_web": len(buses),
        "medical_source": len(medical_source),
        "medical_web": len(medical),
        "medical_primary_web": int(medical["included_in_primary_distance"].sum()),
    }
    return station_collection, bus_collection, medical_collection, counts


def _why_city_gap(properties: Mapping[str, Any]) -> str:
    elderly = int(properties["elderly_population"])
    transport_km = properties["nearest_public_transport_distance_m"] / 1000
    medical_km = properties["nearest_medical_distance_m"] / 1000
    return (
        f"この地域には65歳以上人口が{elderly}人います。"
        f"最寄りの公共交通まで直線約{transport_km:.1f}km、"
        f"医療機関まで直線約{medical_km:.1f}kmあり、追加調査の候補です。"
    )


def _build_mesh_assets(
    metrics_path: Path, top10_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics = gpd.read_file(metrics_path)
    if "city_area_fraction" not in metrics and "maizuru_area_fraction" in metrics:
        metrics["city_area_fraction"] = metrics["maizuru_area_fraction"]
    metrics["mesh_code"] = metrics["mesh_code"].astype(str)
    for column in NUMERIC_MESH_PROPERTIES:
        metrics[column] = pd.to_numeric(metrics[column], errors="coerce")
    metrics["rank"] = pd.to_numeric(metrics["rank"], errors="coerce").astype("Int64")
    metrics["pareto_frontier"] = metrics["pareto_frontier"].map(
        _nullable_boolean
    ).astype("boolean")
    names = metrics["nearest_public_transport_name"].astype("string").str.strip()
    station_mask = metrics["nearest_public_transport_type"].eq("station") | names.str.endswith(
        "駅", na=False
    )
    metrics["area_label"] = np.where(
        station_mask,
        names.fillna("名称未確認") + "周辺",
        names.fillna("名称未確認") + "バス停周辺",
    )
    metrics["area_label_basis"] = "最寄りの実在公共交通名称（行政地名ではない）"
    missing = sorted(set(MESH_PROPERTIES).difference(metrics.columns))
    if missing:
        raise ValueError(f"Analysis metrics are missing fields: {missing}")
    metrics = metrics.sort_values("mesh_code").reset_index(drop=True)
    mesh_collection = _feature_collection(
        metrics, MESH_PROPERTIES, id_column="mesh_code"
    )
    properties_by_code = {
        feature["properties"]["mesh_code"]: feature["properties"]
        for feature in mesh_collection["features"]
    }

    top_source = pd.read_csv(top10_path, dtype={"mesh_code": "string"})
    top_source = top_source.sort_values("rank")
    if top_source["rank"].tolist() != list(range(1, 11)):
        raise ValueError("Analysis Top 10 CSV ranks must be exactly 1 through 10")
    items: list[dict[str, Any]] = []
    for source_record in top_source.to_dict(orient="records"):
        code = str(source_record["mesh_code"])
        if code not in properties_by_code:
            raise ValueError(f"Top 10 mesh {code} is absent from analysis GeoJSON")
        properties = dict(properties_by_code[code])
        if properties["rank"] != source_record["rank"]:
            raise ValueError(f"Top 10 rank disagrees between analysis outputs for {code}")
        for column in (
            "population",
            "elderly_population",
            "nearest_public_transport_distance_m",
            "nearest_medical_distance_m",
            "exploratory_score_c",
        ):
            if not math.isclose(
                float(properties[column]), float(source_record[column]), rel_tol=1e-12
            ):
                raise ValueError(
                    f"Top 10 {column} disagrees between analysis outputs for {code}"
                )
        properties["why_city_gap"] = _why_city_gap(properties)
        items.append(properties)
    top10 = {"schema_version": SCHEMA_VERSION, "count": len(items), "items": items}
    validate_mesh_assets(mesh_collection, top10)
    return mesh_collection, top10


def _build_boundary(
    source_path: Path,
) -> tuple[gpd.GeoDataFrame, dict[str, Any], int]:
    source = gpd.read_file(source_path)
    boundary = boundary_from_plateau(source)
    source_row = source.iloc[0]
    boundary["city_code"] = str(source_row.get("city_code", "26202"))
    boundary["city_name"] = source_row.get("city_name", "舞鶴市")
    boundary["prefecture_code"] = str(source_row.get("prefecture_code", "26"))
    boundary["prefecture_name"] = source_row.get("prefecture_name", "京都府")
    boundary["source_year"] = 2025
    collection = _feature_collection(
        boundary,
        [
            "city_code",
            "city_name",
            "prefecture_code",
            "prefecture_name",
            "source_year",
        ],
        id_column="city_code",
    )
    return boundary, collection, len(source)


def _generated_at(explicit: str | None) -> str:
    if explicit:
        parsed = datetime.fromisoformat(explicit.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch:
        timestamp = datetime.fromtimestamp(int(source_date_epoch), timezone.utc)
    else:
        timestamp = datetime.now(timezone.utc)
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def _build_plateau_status(
    inspection_path: Path,
    top10: Mapping[str, Any],
    reference_metadata_path: Path | None = None,
) -> tuple[dict[str, Any], Path | None]:
    status: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "dataset": "3D都市モデル（Project PLATEAU）舞鶴市（2025年度）",
        "dataset_url": "https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025",
        "year": 2025,
        "packages": {
            "citygml": {
                "version": 5,
                "url": "https://assets.cms.plateau.reearth.io/assets/8f/8ad134-6969-4a6c-a7c2-4ac370a73096/26202_maizuru-shi_city_2025_citygml_1_op.zip",
            },
            "3d_tiles": {
                "version": 5,
                "url": "https://assets.cms.plateau.reearth.io/assets/55/2c1991-f75e-4bf8-9108-531c27952a2b/26202_maizuru-shi_city_2025_3dtiles_mvt_1_op.zip",
            },
        },
        "related_data_usage": {
            "status": "included",
            "layers": ["stations", "administrative_boundary"],
        },
    }
    def attach_reference_layer() -> None:
        if reference_metadata_path is None or not reference_metadata_path.is_file():
            return
        reference = json.loads(reference_metadata_path.read_text(encoding="utf-8"))
        selection = reference.get("selection", {})
        buildings = reference.get("buildings", {})
        deep_buildings = reference.get("deep_dive_buildings", {})
        featured_building = reference.get("featured_building", {})
        top10_scope = reference.get("city_gap_top10", {})
        files = reference.get("files", [])
        records = buildings.get("records")
        tiles = selection.get("tiles")
        b3dm_bytes = selection.get("b3dm_bytes")
        geometry_lod = buildings.get("geometry_lod", {})
        deep_view = selection.get("deep_dive", {})
        if (
            reference.get("status") != "deep_dive_subset_available"
            or not isinstance(records, int)
            or records <= 0
            or not isinstance(tiles, int)
            or tiles <= 0
            or not isinstance(b3dm_bytes, int)
            or b3dm_bytes <= 0
            or not isinstance(files, list)
            or len(files) != tiles
            or top10_scope.get("building_centers") != 0
            or top10_scope.get("building_bbox_intersections") != 0
            or deep_buildings.get("records") != deep_view.get("expected_buildings")
            or not _is_finite_number(deep_view.get("longitude"))
            or not _is_finite_number(deep_view.get("latitude"))
            or featured_building.get("usage") != "住宅"
            or featured_building.get("storeys_above_ground") != 2
            or not _is_finite_number(featured_building.get("measured_height_m"))
            or not _is_finite_number(featured_building.get("building_footprint_area_m2"))
        ):
            raise ValueError("PLATEAU reference subset metadata is inconsistent")
        if sum(int(item.get("bytes", -1)) for item in files) != b3dm_bytes:
            raise ValueError("PLATEAU reference subset byte totals disagree")
        status["reference_layer"] = {
            "status": "included",
            "scope": "常団地前バス停周辺・全市23位の3D Deep Dive; Top 10ではない",
            "records": records,
            "deep_dive_buildings": deep_buildings["records"],
            "deep_dive_mesh_code": str(deep_view["mesh_code"]),
            "deep_dive_overall_rank": int(deep_view["overall_rank"]),
            "area_label": str(deep_view["area_label"]),
            "selected_tiles": tiles,
            "bytes": b3dm_bytes,
            "tileset_url": "data/plateau/tileset.json",
            "lod1_buildings": int(geometry_lod.get("1", 0)),
            "lod2_buildings": int(geometry_lod.get("2", 0)),
            "attributes": [
                "gml_id",
                "bldg:usage",
                "bldg:measuredHeight",
                "bldg:storeysAboveGround",
                "bldg:storeysBelowGround",
                "uro:buildingFootprintArea",
                "uro:totalFloorArea",
                "_lod",
            ],
            "reason": (
                "A deterministic lightweight subset of official 3D Tiles is included "
                "to inspect a verified PLATEAU-covered CITY GAP candidate without "
                "fabricating Top 10 buildings."
            ),
            "viewpoint": {
                "longitude": deep_view["longitude"],
                "latitude": deep_view["latitude"],
                "height": 620,
            },
            "featured_building": featured_building,
            "metadata": {
                "path": _relative_path(reference_metadata_path),
                "bytes": reference_metadata_path.stat().st_size,
                "sha256": _sha256(reference_metadata_path),
            },
        }

    if not inspection_path.is_file():
        raise FileNotFoundError(
            "Verified PLATEAU building inspection is required; refusing to publish "
            "an unverified coverage status"
        )

    inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
    lod1_container = inspection.get("lod1_container", {})
    lod2_container = inspection.get("lod2_container", {})
    city_buildings = lod1_container.get("unique_buildings")
    lod2_buildings = lod2_container.get("unique_buildings")
    top10_buildings = inspection.get("top10_lod1_attributes", {}).get("buildings")
    top10_lod2_buildings = inspection.get("top10_lod2_attributes", {}).get(
        "buildings"
    )
    by_mesh = inspection.get("top10_by_mesh")
    if (
        city_buildings != 44_640
        or lod2_buildings != city_buildings
        or lod1_container.get("b3dm_files") != 427
        or lod2_container.get("b3dm_files") != 427
        or inspection.get("lod1_unique_ids_equal_lod2") is not True
    ):
        raise ValueError("PLATEAU inspection has an unexpected full-city inventory")
    if top10_buildings != 0 or top10_lod2_buildings != 0:
        raise ValueError("PLATEAU inspection has an unexpected Top 10 inventory")
    if not isinstance(by_mesh, list) or len(by_mesh) != 10:
        raise ValueError("PLATEAU inspection must contain all ten ranked meshes")
    inspected_pairs = [
        (item.get("rank"), str(item.get("mesh_code"))) for item in by_mesh
    ]
    expected_pairs = [
        (item.get("rank"), str(item.get("mesh_code"))) for item in top10["items"]
    ]
    if inspected_pairs != expected_pairs:
        raise ValueError("PLATEAU inspection ranks/meshes disagree with CITY GAP Top 10")
    per_mesh_counts = [
        item.get("attribute_summary", {}).get("buildings") for item in by_mesh
    ]
    if any(not isinstance(count, int) or count < 0 for count in per_mesh_counts):
        raise ValueError("PLATEAU inspection contains an invalid per-mesh building count")
    if sum(per_mesh_counts) != top10_buildings:
        raise ValueError("PLATEAU aggregate and per-mesh building counts disagree")
    if any(
        item.get("coverage_distance", {}).get("building_centers_inside") != 0
        or item.get("coverage_distance", {}).get("building_bboxes_intersecting")
        != 0
        for item in by_mesh
    ):
        raise ValueError("PLATEAU Top 10 coverage checks must both be empty")
    if top10_buildings:
        raise ValueError(
            "PLATEAU inspection found Top 10 buildings, but no verified lightweight "
            "building geometry was supplied; refusing to publish an empty layer"
        )

    status["building_layer"] = {
        "status": "verified_empty_for_top10",
        "scope": "CITY GAP Top 10 500 m meshes",
        "records": 0,
        "source_distribution_unique_buildings": city_buildings,
        "attributes": [],
        "inspection_method": (
            "Full official LOD1/LOD2 3D Tiles batch metadata inspection: _x/_y "
            "representative-point inclusion and _xmin/_xmax/_ymin/_ymax building "
            "bounding-box intersection for every Top 10 mesh"
        ),
        "geometry_relation": (
            "representative point-in-mesh and building bounding-box intersection; "
            "not an exact footprint intersection"
        ),
        "reason": (
            "The official PLATEAU package was inspected and contained zero building "
            "records in the Top 10 mesh scope. The empty layer is intentional."
        ),
        "per_mesh": [
            {
                "rank": rank,
                "mesh_code": mesh_code,
                "records": count,
            }
            for (rank, mesh_code), count in zip(
                inspected_pairs, per_mesh_counts, strict=True
            )
        ],
    }
    status["inspection_report"] = {
        "path": _relative_path(inspection_path),
        "bytes": inspection_path.stat().st_size,
        "sha256": _sha256(inspection_path),
    }
    attach_reference_layer()
    return status, inspection_path


def _write_json(path: Path, value: Mapping[str, Any], *, compact: bool = False) -> None:
    options: dict[str, Any] = {
        "ensure_ascii": False,
        "allow_nan": False,
    }
    if compact:
        options["separators"] = (",", ":")
    else:
        options["indent"] = 2
    path.write_text(json.dumps(value, **options) + "\n", encoding="utf-8")


def _file_record(path: Path, records: int, *, status: str = "available") -> dict[str, Any]:
    return {
        "file": path.name,
        "status": status,
        "records": records,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_web_assets(args: argparse.Namespace) -> dict[str, Any]:
    """Build all assets and return the generated manifest."""
    input_paths = [
        args.metrics,
        args.top10,
        args.summary,
        args.stations,
        args.bus_stops,
        args.medical,
        args.boundary,
    ]
    for path in input_paths:
        _require_file(path)
    _require_file(args.plateau_inspection)

    analysis_summary = json.loads(args.summary.read_text(encoding="utf-8"))
    if analysis_summary.get("analysis_status") != "real data":
        raise ValueError("Web assets can only be generated from real-data analysis")
    if analysis_summary.get("generated_from_synthetic_data") is not False:
        raise ValueError("Synthetic analysis output cannot be published as web data")

    mesh_collection, top10 = _build_mesh_assets(args.metrics, args.top10)
    boundary, boundary_collection, boundary_source_count = _build_boundary(args.boundary)
    stations, buses, medical, point_counts = _build_point_layers(
        args.stations, args.bus_stops, args.medical, boundary
    )
    validate_geojson_geometry(stations, expected_types={"Point"})
    validate_geojson_geometry(buses, expected_types={"Point"})
    validate_geojson_geometry(medical, expected_types={"Point"})
    validate_geojson_geometry(
        boundary_collection, expected_types={"Polygon", "MultiPolygon"}
    )

    expected = analysis_summary.get("record_counts", {})
    _check_count(
        "Maizuru meshes",
        len(mesh_collection["features"]),
        _summary_count(expected, "population_meshes_intersecting_city", "population_meshes_intersecting_maizuru"),
    )
    _check_count("raw stations", point_counts["stations_source"], expected.get("stations_raw"))
    _check_count(
        "deduplicated stations",
        point_counts["stations_web"],
        expected.get("station_deduplicated"),
    )
    _check_count("raw bus stops", point_counts["bus_stops_source"], _summary_count(expected, "bus_stops_prefecture", "bus_stops_kyoto"))
    _check_count("Maizuru bus stops", point_counts["bus_stops_web"], _summary_count(expected, "bus_stops_city", "bus_stops_maizuru"))
    _check_count("raw medical facilities", point_counts["medical_source"], _summary_count(expected, "medical_prefecture", "medical_kyoto"))
    _check_count("Maizuru medical facilities", point_counts["medical_web"], _summary_count(expected, "medical_city", "medical_maizuru"))
    _check_count(
        "primary medical facilities",
        point_counts["medical_primary_web"],
        _summary_count(expected, "medical_primary_city", "medical_primary_maizuru"),
    )
    if boundary_source_count != 1:
        raise ValueError(f"PLATEAU boundary source contains {boundary_source_count} records")

    web_summary = {
        "schema_version": SCHEMA_VERSION,
        "analysis_status": "real_data",
        "generated_from_synthetic_data": False,
        "distance_method": analysis_summary["distance_method"],
        "analysis_crs": analysis_summary["analysis_crs"],
        "web_crs": WEB_CRS,
        "record_counts": expected,
        "primary_ranking": {
            "metric": "exploratory_score_c",
            "label_ja": "CITY GAP探索スコア",
            "formula": analysis_summary["primary_ranking"]["score"],
            "minimum_population": analysis_summary["primary_ranking"][
                "minimum_population"
            ],
            "minimum_elderly_population": analysis_summary["primary_ranking"][
                "minimum_elderly_population"
            ],
        },
        "threshold_stability": analysis_summary.get("threshold_stability", {}),
        "limitations": LIMITATIONS,
    }
    plateau_status, inspection_input = _build_plateau_status(
        args.plateau_inspection,
        top10,
        args.output_dir / "plateau/metadata.json",
    )
    plateau_buildings: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": plateau_status["building_layer"],
    }
    validate_geojson_geometry(plateau_buildings, allow_empty=True)

    final_demo_path = args.output_dir / "final_demo.json"
    plateau_roads_path = args.output_dir / "plateau_roads.geojson"
    _require_file(final_demo_path)
    _require_file(plateau_roads_path)
    final_demo = json.loads(final_demo_path.read_text(encoding="utf-8"))
    plateau_roads = json.loads(plateau_roads_path.read_text(encoding="utf-8"))
    if final_demo.get("comparison_mesh_count") != expected.get("population_unaffected"):
        raise ValueError("Final demo comparison-mesh count disagrees with analysis")
    if len(final_demo.get("plateau_covered_candidates", [])) != 5:
        raise ValueError("Final demo must contain five PLATEAU-covered candidates")
    validate_geojson_geometry(
        plateau_roads, expected_types={"Polygon", "MultiPolygon"}
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_values: dict[str, Mapping[str, Any]] = {
        "mesh_metrics.geojson": mesh_collection,
        "top10.json": top10,
        "summary.json": web_summary,
        "stations.geojson": stations,
        "bus_stops.geojson": buses,
        "medical_facilities.geojson": medical,
        "maizuru_boundary.geojson": boundary_collection,
        "plateau_buildings.geojson": plateau_buildings,
        "plateau_metadata.json": plateau_status,
    }
    for filename, value in output_values.items():
        _write_json(
            args.output_dir / filename,
            value,
            compact=filename.endswith(".geojson"),
        )

    record_counts = {
        "mesh_metrics.geojson": len(mesh_collection["features"]),
        "top10.json": len(top10["items"]),
        "summary.json": 1,
        "stations.geojson": len(stations["features"]),
        "bus_stops.geojson": len(buses["features"]),
        "medical_facilities.geojson": len(medical["features"]),
        "maizuru_boundary.geojson": len(boundary_collection["features"]),
        "plateau_buildings.geojson": 0,
        "plateau_metadata.json": 1,
    }
    outputs = [
        _file_record(
            args.output_dir / filename,
            record_counts[filename],
            status=(
                plateau_status["building_layer"]["status"]
                if filename == "plateau_buildings.geojson"
                else "available"
            ),
        )
        for filename in output_values
    ]
    outputs.extend(
        [
            _file_record(final_demo_path, 1),
            _file_record(
                plateau_roads_path, len(plateau_roads["features"])
            ),
        ]
    )
    plateau_reference_outputs = [
        {
            "file": path.relative_to(args.output_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted((args.output_dir / "plateau").rglob("*"))
        if path.is_file()
    ]
    sources = [
        {
            "id": "estat-t001192",
            "provider": "e-Stat",
            "title": "2020 Census JGD2011 500 m mesh population by five-year age group",
            "year": 2020,
            "source_records": _summary_count(expected, "population_prefecture", "population_kyoto"),
            "web_records": _summary_count(expected, "population_meshes_intersecting_city", "population_meshes_intersecting_maizuru"),
            "url": "https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=26&downloadType=2",
        },
        {
            "id": "ksj-p11-2022",
            "provider": "National Land Numerical Information",
            "title": "Bus stops P11",
            "year": 2022,
            "source_records": point_counts["bus_stops_source"],
            "web_records": point_counts["bus_stops_web"],
            "url": "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html",
        },
        {
            "id": "ksj-p04-2020",
            "provider": "National Land Numerical Information",
            "title": "Medical facilities P04",
            "year": 2020,
            "source_records": point_counts["medical_source"],
            "web_records": point_counts["medical_web"],
            "analysis_records": point_counts["medical_primary_web"],
            "url": "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html",
        },
        {
            "id": "plateau-maizuru-2025-related",
            "provider": "Project PLATEAU",
            "title": "3D都市モデル（舞鶴市）2025年度 関連データ",
            "year": 2025,
            "source_records": {
                "stations": point_counts["stations_source"],
                "boundary": boundary_source_count,
            },
            "web_records": {
                "stations": point_counts["stations_web"],
                "boundary": len(boundary_collection["features"]),
                "buildings": 0,
            },
            "buildings_in_3d_source_distribution": plateau_status["building_layer"].get(
                "source_distribution_unique_buildings"
            ),
            "building_status": plateau_status["building_layer"]["status"],
            "url": "https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025",
        },
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _generated_at(args.generated_at),
        "analysis_version": ANALYSIS_VERSION,
        "builder": "analysis/scripts/build_web_assets.py",
        "crs": {
            "analysis": analysis_summary["analysis_crs"]["code"],
            "web": WEB_CRS,
        },
        "data_years": {
            "population": 2020,
            "medical": 2020,
            "bus_stops": 2022,
            "plateau_related": 2025,
        },
        "source_datasets": sources,
        "record_counts": {
            "mesh_metrics": record_counts["mesh_metrics.geojson"],
            "top10": record_counts["top10.json"],
            "stations": record_counts["stations.geojson"],
            "bus_stops": record_counts["bus_stops.geojson"],
            "medical_facilities": record_counts["medical_facilities.geojson"],
            "administrative_boundary": record_counts["maizuru_boundary.geojson"],
            "plateau_top10_buildings": record_counts["plateau_buildings.geojson"],
            "plateau_reference_buildings": plateau_status.get(
                "reference_layer", {}
            ).get("records", 0),
            "plateau_deep_dive_roads": len(plateau_roads["features"]),
        },
        "outputs": outputs,
        "plateau_reference_outputs": plateau_reference_outputs,
        "lineage": {
            "analysis_sources_of_truth": [
                _relative_path(args.metrics),
                _relative_path(args.top10),
                _relative_path(args.summary),
            ],
            "inputs": [
                {
                    "path": _relative_path(path),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in (
                    [*input_paths, inspection_input]
                    if inspection_input is not None
                    else input_paths
                )
            ],
            "transformations": [
                "select browser-facing attributes without recalculating analysis metrics",
                "filter point layers by the PLATEAU administrative boundary using intersects",
                "deduplicate PLATEAU station records by name and location",
                "convert all geometries to EPSG:4326",
                "validate analysis and geographic invariants before publication",
                "join all official PLATEAU building representative points to analysis meshes",
                "extract official PLATEAU road surfaces and precompute placement candidates",
            ],
        },
        "limitations": LIMITATIONS,
    }
    _write_json(args.output_dir / "manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "metrics",
        "top10",
        "summary",
        "stations",
        "bus_stops",
        "medical",
        "boundary",
        "plateau_inspection",
        "output_dir",
    ):
        parser.add_argument(
            f"--{name.replace('_', '-')}", type=Path, default=DEFAULTS[name]
        )
    parser.add_argument(
        "--generated-at",
        help="ISO 8601 timestamp override (SOURCE_DATE_EPOCH is also supported)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_web_assets(args)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "generated_at": manifest["generated_at"],
                "outputs": manifest["outputs"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
