"""Build the canonical public Spatial Evidence Pack for mesh 533513314.

Inputs are repository-tracked derivatives of official PLATEAU Maizuru 2025,
National Land Numerical Information P11 facilities/stops and existing CITY GAP
analysis. The builder never reads the network and never emits per-building
model population. Large 3D geometry remains in immutable referenced tilesets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, box, mapping, shape

from analysis.scripts.build_plateau_web_subset import (
    DEEP_DIVE,
    _decode_property,
    _first_dict,
)
from analysis.src.urban_section import TerrainTriangle, sample_tin_transect, section_relations
from backend.citygap_platform.domain.spatial_evidence import (
    assert_public_pack_safe,
    canonical_sha256,
)

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DATA = ROOT / "frontend/public/data"
PACK_ID = "maizuru-533513314-plateau-2025-v1"
OUTPUT = PUBLIC_DATA / "spatial-packs" / PACK_ID
PACK_BOUNDS = (
    DEEP_DIVE["west"],
    DEEP_DIVE["south"],
    DEEP_DIVE["east"],
    DEEP_DIVE["north"],
)
BUILDING_FILES = tuple(sorted((PUBLIC_DATA / "plateau/data").glob("*.b3dm")))
TERRAIN_GLB = PUBLIC_DATA / "plateau-terrain/terrain.glb"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def clean_number(value: Any, *, allow_zero: bool = True) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value in {-9999, 9999}:
        return None
    if value < 0 or (not allow_zero and value == 0):
        return None
    return value


def read_building_batch(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as stream:
        header = stream.read(28)
        if header[:4] != b"b3dm":
            raise ValueError(f"Not a b3dm: {path}")
        version, length, feature_json_length, feature_binary_length, batch_json_length, batch_binary_length = struct.unpack(
            "<6I", header[4:]
        )
        if version != 1 or length != path.stat().st_size:
            raise ValueError(f"Invalid b3dm header: {path}")
        feature = json.loads(stream.read(feature_json_length))
        stream.read(feature_binary_length)
        batch = json.loads(stream.read(batch_json_length))
        binary = stream.read(batch_binary_length)
    count = int(feature["BATCH_LENGTH"])
    fields = {
        key: _decode_property(batch, binary, key, count)
        for key in ("_x", "_y", "_xmin", "_xmax", "_ymin", "_ymax", "_zmin", "_zmax", "_lod")
    }
    return [
        {
            "id": batch["gml_id"][index],
            "attributes": batch["attributes"][index],
            "source_tile": f"plateau/data/{path.name}",
            **{key[1:]: values[index] for key, values in fields.items()},
        }
        for index in range(count)
    ]


def building_object(record: dict[str, Any]) -> dict[str, Any]:
    attributes = record["attributes"]
    detail = _first_dict(attributes.get("uro:BuildingDetailAttribute"))
    hazards = []
    for key, value in sorted(attributes.items()):
        if not any(token in key for token in ("洪水", "浸水", "津波", "土砂", "地すべり", "急傾斜", "土石流")):
            continue
        if value not in (None, "", [], {}) and clean_number(value) != 0:
            hazards.append({"source_attribute": key, "value": value})
    properties = {
        "gml_id": record["id"],
        "usage": attributes.get("bldg:usage"),
        "measured_height_m": clean_number(attributes.get("bldg:measuredHeight"), allow_zero=False),
        "storeys_above_ground": clean_number(attributes.get("bldg:storeysAboveGround")),
        "storeys_below_ground": clean_number(attributes.get("bldg:storeysBelowGround")),
        "footprint_area_m2": clean_number(detail.get("uro:buildingFootprintArea"), allow_zero=False),
        "total_floor_area_m2": clean_number(detail.get("uro:totalFloorArea"), allow_zero=False),
        "geometry_lod": record["lod"],
        "source_z_min_m": record["zmin"],
        "source_z_max_m": record["zmax"],
        "creation_date": attributes.get("core:creationDate"),
        "source_tile": record["source_tile"],
        "geometry_semantics": "official_3d_tiles_source_bbox; rendered geometry remains in referenced b3dm",
        "planning": {
            "urban_plan_type": detail.get("uro:urbanPlanType"),
            "area_classification": detail.get("uro:areaClassificationType"),
            "districts_and_zones": detail.get("uro:districtsAndZonesType"),
            "land_use": detail.get("uro:landUseType"),
            "building_coverage_rate_percent": clean_number(detail.get("uro:specifiedBuildingCoverageRate")),
            "floor_area_rate_percent": clean_number(detail.get("uro:specifiedFloorAreaRate")),
            "survey_year": clean_number(detail.get("uro:surveyYear")),
        },
        "hazards": hazards,
        "unknown_policy": "null means source unknown; values are not imputed",
    }
    return {
        "id": record["id"],
        "object_type": "building",
        "geometry": mapping(box(record["xmin"], record["ymin"], record["xmax"], record["ymax"])),
        "properties": properties,
    }


def load_target_buildings() -> list[dict[str, Any]]:
    records = [item for path in BUILDING_FILES for item in read_building_batch(path)]
    west, south, east, north = PACK_BOUNDS
    target = [item for item in records if west <= item["x"] <= east and south <= item["y"] <= north]
    objects = sorted((building_object(record) for record in target), key=lambda item: item["id"])
    if len(objects) != DEEP_DIVE["expected_buildings"]:
        raise ValueError(f"Expected 296 target buildings, found {len(objects)}")
    return objects


def load_geojson_objects(path: Path, object_type: str, *, include_all: bool = False) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    boundary = box(*PACK_BOUNDS)
    result = []
    for index, feature in enumerate(document["features"]):
        geometry = shape(feature["geometry"])
        if not include_all and not boundary.intersects(geometry):
            continue
        identifier = feature.get("id") or feature.get("properties", {}).get("id") or f"{object_type}-{index}"
        result.append(
            {
                "id": str(identifier),
                "object_type": object_type,
                "geometry": feature["geometry"],
                "properties": feature.get("properties", {}),
            }
        )
    return sorted(result, key=lambda item: item["id"])


def load_service_objects() -> list[dict[str, Any]]:
    # Keep nearest official P11-derived locations within 2 km as section context.
    center = box(*PACK_BOUNDS).centroid
    candidates = []
    for path, kind in (
        (PUBLIC_DATA / "medical_facilities.geojson", "medical_facility"),
        (PUBLIC_DATA / "bus_stops.geojson", "bus_stop"),
        (PUBLIC_DATA / "stations.geojson", "station"),
    ):
        for item in load_geojson_objects(path, "facility", include_all=True):
            distance = center.distance(shape(item["geometry"]))
            item["properties"] = {**item["properties"], "facility_type": kind}
            candidates.append((distance, item))
    return [item for _, item in sorted(candidates, key=lambda pair: (pair[0], pair[1]["id"]))[:16]]


def parse_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    blob = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", blob, 0)
    if magic != b"glTF" or version != 2 or length != len(blob):
        raise ValueError("Invalid terrain GLB")
    offset = 12
    chunks: dict[int, bytes] = {}
    while offset < len(blob):
        chunk_length, chunk_type = struct.unpack_from("<II", blob, offset)
        offset += 8
        chunks[chunk_type] = blob[offset : offset + chunk_length]
        offset += chunk_length
    return json.loads(chunks[0x4E4F534A]), chunks[0x004E4942]


def accessor_array(document: dict[str, Any], binary: bytes, accessor_index: int) -> np.ndarray:
    accessor = document["accessors"][accessor_index]
    view = document["bufferViews"][accessor["bufferView"]]
    component = {5126: np.dtype("<f4"), 5125: np.dtype("<u4"), 5123: np.dtype("<u2")}[accessor["componentType"]]
    width = {"SCALAR": 1, "VEC3": 3}[accessor["type"]]
    offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    values = np.frombuffer(binary, dtype=component, count=int(accessor["count"]) * width, offset=offset)
    return values.reshape(-1, width) if width > 1 else values


def load_terrain_triangles() -> list[TerrainTriangle]:
    document, binary = parse_glb(TERRAIN_GLB)
    primitive = document["meshes"][0]["primitives"][0]
    local = accessor_array(document, binary, primitive["attributes"]["POSITION"]).astype(np.float64)
    indices = accessor_array(document, binary, primitive["indices"]).astype(np.int64).reshape(-1, 3)
    tileset = json.loads((PUBLIC_DATA / "plateau-terrain/tileset.json").read_text(encoding="utf-8"))
    matrix = tileset["root"]["transform"]
    ecef = np.column_stack(
        (
            matrix[0] * local[:, 0] + matrix[4] * local[:, 1] + matrix[8] * local[:, 2] + matrix[12],
            matrix[1] * local[:, 0] + matrix[5] * local[:, 1] + matrix[9] * local[:, 2] + matrix[13],
            matrix[2] * local[:, 0] + matrix[6] * local[:, 1] + matrix[10] * local[:, 2] + matrix[14],
        )
    )
    to_geographic = Transformer.from_crs("EPSG:4978", "EPSG:4979", always_xy=True)
    lon, lat, elevation = to_geographic.transform(ecef[:, 0], ecef[:, 1], ecef[:, 2])
    geographic = np.column_stack((lon, lat, elevation))
    return [
        TerrainTriangle(
            f"plateau-dem-tin-{index}",
            tuple(tuple(float(value) for value in geographic[vertex]) for vertex in face),
        )
        for index, face in enumerate(indices)
    ]


def choose_transect(buildings: list[dict[str, Any]], roads: list[dict[str, Any]]) -> list[list[float]]:
    west, south, east, north = PACK_BOUNDS
    candidates: list[list[list[float]]] = []
    for step in range(2, 19):
        fraction = step / 20
        latitude = south + (north - south) * fraction
        longitude = west + (east - west) * fraction
        candidates.append([[west, latitude], [east, latitude]])
        candidates.append([[longitude, south], [longitude, north]])
    candidates.extend(
        [
            [[west, south], [east, north]],
            [[west, north], [east, south]],
        ]
    )
    scored = []
    for coordinates in candidates:
        line = LineString(coordinates)
        building_hits = sum(line.intersects(shape(item["geometry"])) for item in buildings)
        road_hits = sum(line.intersects(shape(item["geometry"])) for item in roads)
        scored.append((building_hits * 10 + road_hits, building_hits, road_hits, coordinates))
    return max(scored, key=lambda item: (item[0], item[1], item[2], item[3]))[3]


def build() -> dict[str, Any]:
    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    buildings = load_target_buildings()
    roads = load_geojson_objects(PUBLIC_DATA / "plateau_roads.geojson", "road")
    facilities = load_service_objects()
    mesh = next(
        item
        for item in load_geojson_objects(PUBLIC_DATA / "mesh_metrics.geojson", "analysis_relation")
        if item["id"] == DEEP_DIVE["mesh_code"]
    )
    objects = [*buildings, *roads, *facilities, mesh]
    assert_public_pack_safe(objects)

    transect_coordinates = choose_transect(buildings, roads)
    terrain_triangles = load_terrain_triangles()
    terrain_samples = sample_tin_transect(transect_coordinates, terrain_triangles, sample_interval_m=5)
    building_relations = section_relations(transect_coordinates, buildings, buffer_m=12)
    road_relations = section_relations(transect_coordinates, roads, buffer_m=0)
    facility_relations = section_relations(transect_coordinates, facilities, buffer_m=2000)
    section = {
        "schema": "citygap.urban-section@1",
        "transect_id": f"{PACK_ID}-default-section",
        "pack_id": PACK_ID,
        "geometry": {"type": "LineString", "coordinates": transect_coordinates},
        "buffer_m": 12,
        "sample_interval_m": 5,
        "vertical_datum": "WGS 84 ellipsoidal height (EPSG:4979), transformed from JGD2011/GSI height (EPSG:6697) using GSIGEO2011",
        "terrain_source": "Project PLATEAU 舞鶴市2025 dem:TINRelief",
        "terrain_interpolation": "source TIN barycentric interpolation; no smoothing or exaggeration",
        "terrain_samples": [asdict(sample) for sample in terrain_samples],
        "buildings": building_relations,
        "roads": road_relations,
        "service_locations": facility_relations,
        "planning_bands": [
            {
                "source_object_id": item["source_object_id"],
                "start_distance_m": item["start_distance_m"],
                "end_distance_m": item["end_distance_m"],
                "planning": item["properties"].get("planning", {}),
            }
            for item in building_relations
            if any(item["properties"].get("planning", {}).values())
        ],
        "hazard_bands": [
            {
                "source_object_id": item["source_object_id"],
                "start_distance_m": item["start_distance_m"],
                "end_distance_m": item["end_distance_m"],
                "hazards": item["properties"].get("hazards", []),
                "semantics": "extent/depth shown only when present in official building attribute",
            }
            for item in building_relations
            if item["properties"].get("hazards")
        ],
    }
    assert any(sample["elevation_m"] is not None for sample in section["terrain_samples"])
    write_json(OUTPUT / "objects.json", {"schema": "citygap.spatial-pack-objects@1", "objects": objects})
    write_json(OUTPUT / "sections.json", section)
    artifacts = {
        name: {
            "uri": name,
            "bytes": (OUTPUT / name).stat().st_size,
            "sha256": sha256_file(OUTPUT / name),
            "etag": f'"sha256-{sha256_file(OUTPUT / name)}"',
            "cache_control": "public, max-age=31536000, immutable",
        }
        for name in ("objects.json", "sections.json")
    }
    content_hash = canonical_sha256({name: value["sha256"] for name, value in artifacts.items()})
    terrain_metadata = json.loads((PUBLIC_DATA / "plateau-terrain/metadata.json").read_text(encoding="utf-8"))
    plateau_metadata = json.loads((PUBLIC_DATA / "plateau/metadata.json").read_text(encoding="utf-8"))
    manifest_payload = {
        "schema": "citygap.spatial-evidence-pack@1",
        "pack_id": PACK_ID,
        "organization_scope": "public-demo-review",
        "city": {"code": "26202", "name": "舞鶴市"},
        "urban_state": "observed-2025",
        "finding": "mesh-533513314-accessibility-gap",
        "investigation": "maizuru-municipal-pilot",
        "geometry": mapping(box(*PACK_BOUNDS)),
        "bbox": list(PACK_BOUNDS),
        "buffer_m": 0,
        "status": "ready",
        "data_classification": "public",
        "content_sha256": content_hash,
        "objects": {
            "target_buildings": DEEP_DIVE["expected_buildings"],
            "loaded_target_buildings": len(buildings),
            "target_coverage_ratio": len(buildings) / DEEP_DIVE["expected_buildings"],
            "roads": len(roads),
            "facilities": len(facilities),
            "analysis_relations": 1,
            "terrain_source_triangles": len(terrain_triangles),
        },
        "source_versions": {
            "buildings": plateau_metadata.get("source", plateau_metadata.get("official_source")),
            "terrain": {
                "dataset": terrain_metadata["dataset"],
                "source_archive_sha256": terrain_metadata["source_archive"]["sha256"],
                "source_members": terrain_metadata["source_archive"]["members"],
            },
            "roads": "Project PLATEAU 舞鶴市2025 道路LOD1",
            "facilities_transport": "国土数値情報 P04/P11 tracked CITY GAP derivatives; official GTFS unavailable/not published",
            "analysis": "CITY GAP mesh metrics deterministic public derivative",
        },
        "render_assets": {
            "building_tileset": "../../plateau/tileset.json",
            "terrain_tileset": "../../plateau-terrain/tileset.json",
            "roads": "../../plateau_roads.geojson",
        },
        "terrain_contract": {
            "source_crs": terrain_metadata.get("source_crs"),
            "render_crs": terrain_metadata.get("render_crs"),
            "vertical_transform": terrain_metadata.get("vertical_transform"),
            "rendered_triangles": len(terrain_triangles),
            "transform": json.loads((PUBLIC_DATA / "plateau-terrain/tileset.json").read_text(encoding="utf-8"))["root"]["transform"],
            "elevation_exaggeration": 1,
        },
        "section": {
            "default_transect_id": section["transect_id"],
            "terrain_samples": len(terrain_samples),
            "terrain_samples_with_coverage": sum(sample.elevation_m is not None for sample in terrain_samples),
            "building_direct": sum(item["relation"] == "direct" for item in building_relations),
            "building_nearby": sum(item["relation"] == "nearby" for item in building_relations),
            "road_intersections": len(road_relations),
            "service_locations": len(facility_relations),
        },
        "privacy": {
            "public_building_population_model": "excluded",
            "municipal_model_boundary": "building-level demographic estimates remain internal/restricted",
        },
        "artifacts": artifacts,
    }
    manifest_hash = canonical_sha256(manifest_payload)
    manifest = {**manifest_payload, "pack_manifest_sha256": manifest_hash}
    write_json(OUTPUT / "manifest.json", manifest)
    result = {
        "pack_id": PACK_ID,
        "buildings": len(buildings),
        "roads": len(roads),
        "terrain_triangles": len(terrain_triangles),
        "terrain_samples": len(terrain_samples),
        "building_intersections": len(building_relations),
        "road_intersections": len(road_relations),
        "content_sha256": content_hash,
        "manifest_sha256": manifest_hash,
        "pack_bytes": sum(path.stat().st_size for path in OUTPUT.iterdir() if path.is_file()),
        "build_seconds": round(time.perf_counter() - started, 3),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    build()


if __name__ == "__main__":
    main()
