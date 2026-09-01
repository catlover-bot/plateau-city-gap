"""Build deterministic PLATEAU display geometry for the Public Area journey.

The artifacts are presentation-only derivatives of the checked-in Maizuru
CityGML release. They preserve source identity and explicit source attributes;
they do not add analytical facts, inferred use, walking meaning, or risk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, mapping, shape

from analysis.src.plateau_buildings import read_buildings
from analysis.src.plateau_road_network import read_road_surfaces

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend/public/data"
OUTPUT = PUBLIC / "cartography"
ARCHIVE = ROOT / "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
AREA_FIXTURE = PUBLIC / "investigation_area_summary.json"
BOUNDARY = PUBLIC / "maizuru_boundary.geojson"
USAGE_AUDIT = ROOT / "analysis/outputs/real/maizuru_building_usage_audit.csv"
PLANNING = ROOT / "analysis/outputs/real/maizuru_plateau_urban_planning.parquet"
PACK = PUBLIC / "data/spatial-packs/maizuru-533513314-plateau-2025-v1/objects.json"
if not PACK.exists():
    PACK = PUBLIC / "spatial-packs/maizuru-533513314-plateau-2025-v1/objects.json"

ANALYSIS_CRS = "EPSG:6674"
WEB_CRS = "EPSG:4326"
RULE_VERSION = "citygap-public-cartography@1.0.0"
GENERATOR_VERSION = "citygap-public-cartography-generator@1.1.0"
GENERATED_AT = "2026-09-01T00:00:00+09:00"
SOURCE_VERSION = "26202_maizuru-shi_city_2025_citygml_1_op"
SOURCE_SHA256 = "13f4020ade066dc7139b7653c47a55a09af0093dee743f6b9cca5d3177a71cff"
FILES = {
    "buildings": "plateau_buildings.geojson",
    "roads": "plateau_roads.geojson",
    "planning": "plateau_planning.geojson",
}
TARGET_FILE = "plateau_targets.geojson"
PROPERTY_ALLOWLISTS = {
    "buildings": {
        "object_id", "object_type", "usage_code", "usage_label", "geometry_source",
        "source_member", "source_member_crc32",
    },
    "roads": {
        "object_id", "object_type", "surface_id", "surface_index", "road_name",
        "road_class", "function_code", "usage_code", "source_member",
        "source_member_crc32",
    },
    "planning": {
        "object_id", "object_type", "planning_label", "planning_type", "name",
        "building_coverage_rate", "floor_area_rate", "geometry_semantics",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean(value: Any) -> Any:
    if value is None or (not isinstance(value, (str, bool)) and pd.isna(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def public_area() -> tuple[Any, dict[str, Any], set[str]]:
    fixture = json.loads(AREA_FIXTURE.read_text(encoding="utf-8"))
    areas = fixture["areas"]
    if not areas:
        raise ValueError("Public Area fixture contains no areas")
    primary = max(areas, key=lambda item: int(item["radius_m"]))
    center = Point(primary["origin"]["coordinates"])
    center_metric = gpd.GeoSeries([center], crs=WEB_CRS).to_crs(ANALYSIS_CRS).iloc[0]
    requested = center_metric.buffer(int(primary["radius_m"]), quad_segs=64)
    boundary = gpd.read_file(BOUNDARY).to_crs(ANALYSIS_CRS).geometry.union_all()
    effective = requested.intersection(boundary)
    if effective.is_empty:
        raise ValueError("Public Area does not intersect Maizuru")
    target_ids = {
        item["target"]["source_object_id"]
        for area in areas
        for item in area["unknowns"]
        if item["target"]["scope"] == "plateau_object"
    }
    return effective, primary, target_ids


def existing_pack_audit(target_ids: set[str]) -> dict[str, Any]:
    if not PACK.exists():
        return {"path": None, "reused_target_ids": [], "missing_target_ids": sorted(target_ids)}
    value = json.loads(PACK.read_text(encoding="utf-8"))
    objects = {str(item["id"]): item for item in value.get("objects", [])}
    reused = sorted(target_ids.intersection(objects))
    return {
        "path": str(PACK.relative_to(ROOT)),
        "sha256": sha256(PACK),
        "reused_target_ids": reused,
        "missing_target_ids": sorted(target_ids.difference(objects)),
        "sufficient_for_public_area": target_ids.issubset(objects),
    }


def feature_collection(frame: gpd.GeoDataFrame, columns: list[str]) -> dict[str, Any]:
    features = []
    frame = frame.to_crs(WEB_CRS).sort_values(["object_id", *(
        ["surface_index"] if "surface_index" in frame.columns else []
    )], kind="stable")
    for row in frame.itertuples(index=False):
        values = row._asdict()
        geometry = values.pop("geometry")
        properties = {column: clean(values.get(column)) for column in columns}
        features.append({
            "type": "Feature",
            "id": str(properties["object_id"]) + (
                ":" + str(properties["surface_index"])
                if "surface_index" in properties else ""
            ),
            "properties": properties,
            "geometry": mapping(geometry),
        })
    return {"type": "FeatureCollection", "features": features}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    effective, primary, target_ids = public_area()
    source_hash = sha256(ARCHIVE)
    if source_hash != SOURCE_SHA256:
        raise ValueError("Maizuru CityGML source hash does not match the pinned release")

    usage = pd.read_csv(USAGE_AUDIT, dtype={"usage_code": "string"})
    usage_labels = usage.set_index("usage_code")["official_label"]
    buildings = read_buildings(ARCHIVE)
    buildings = buildings.loc[buildings.geometry.notna() & ~buildings.geometry.is_empty].copy()
    buildings = buildings.sort_values(["gml_id", "source_gml"]).drop_duplicates("gml_id")
    buildings["usage_code"] = buildings["usage"].astype("string")
    buildings["usage_label"] = buildings["usage_code"].map(usage_labels)
    buildings = buildings.to_crs(ANALYSIS_CRS)
    buildings = buildings.loc[buildings.geometry.intersects(effective)].copy()
    buildings = buildings.rename(columns={
        "gml_id": "object_id",
        "source_gml": "source_member",
    })
    buildings["object_type"] = "building"

    roads = read_road_surfaces(ARCHIVE).to_crs(ANALYSIS_CRS)
    roads = roads.loc[roads.geometry.intersects(effective)].copy()
    roads = roads.rename(columns={"gml_id": "object_id"})
    roads["object_type"] = "road"

    planning = gpd.read_parquet(PLANNING).to_crs(ANALYSIS_CRS)
    planning = planning.loc[planning.geometry.intersects(effective)].copy()
    planning = planning.rename(columns={"gml_id": "object_id"})
    planning["object_type"] = "planning"
    planning["geometry"] = planning.geometry.intersection(effective)
    planning["geometry_semantics"] = "source_geometry_clipped_to_public_area_for_display"

    collections = {
        "buildings": feature_collection(buildings, sorted(PROPERTY_ALLOWLISTS["buildings"])),
        "roads": feature_collection(roads, sorted(PROPERTY_ALLOWLISTS["roads"])),
        "planning": feature_collection(planning, sorted(PROPERTY_ALLOWLISTS["planning"])),
    }
    target_features = [
        feature
        for kind in ("buildings", "roads")
        for feature in collections[kind]["features"]
        if str(feature["properties"]["object_id"]) in target_ids
    ]
    target_features.sort(
        key=lambda feature: (str(feature["properties"]["object_id"]), str(feature["id"]))
    )
    target_collection = {"type": "FeatureCollection", "features": target_features}
    for kind, collection in collections.items():
        write_json(OUTPUT / FILES[kind], collection)
    write_json(OUTPUT / TARGET_FILE, target_collection)

    resolved = {}
    for kind, collection in collections.items():
        ids = {str(feature["properties"]["object_id"]) for feature in collection["features"]}
        resolved[kind] = sorted(target_ids.intersection(ids))

    manifest = {
        "schema_version": "citygap.public-cartography@1",
        "generated_at": GENERATED_AT,
        "artifact_kind": "display_derivative",
        "generator_version": GENERATOR_VERSION,
        "rule_version": RULE_VERSION,
        "source": {
            "path": str(ARCHIVE.relative_to(ROOT)),
            "version": SOURCE_VERSION,
            "sha256": source_hash,
            "city_code": "26202",
            "crs": WEB_CRS,
        },
        "scope": {
            "area_id": primary["id"],
            "area_version": primary["version"],
            "radius_m": primary["radius_m"],
            "area_content_sha256": primary["content_sha256"],
            "origin": {
                "kind": primary["origin"]["kind"],
                "source_feature_id": primary["origin"]["source_feature_id"],
                "coordinates": primary["origin"]["coordinates"],
            },
        },
        "reuse_audit": existing_pack_audit(target_ids),
        "target_ids": sorted(target_ids),
        "resolved_target_ids": resolved,
        "artifacts": {},
        "prohibitions": [
            "no_external_data", "no_population_allocation", "no_usage_inference",
            "no_walking_semantics", "no_hazard_or_safety_meaning", "no_score",
        ],
    }
    for kind, filename in FILES.items():
        path = OUTPUT / filename
        artifact_hash = sha256(path)
        manifest["artifacts"][kind] = {
            "artifact_kind": f"area_{kind}_display_derivative",
            "path": filename,
            "source_dataset_version": SOURCE_VERSION,
            "source_sha256": source_hash,
            "generator_version": GENERATOR_VERSION,
            "rule_version": RULE_VERSION,
            "scope": {
                "area_id": primary["id"],
                "area_version": primary["version"],
                "radius_m": primary["radius_m"],
            },
            "feature_count": len(collections[kind]["features"]),
            "geometry_types": sorted({
                feature["geometry"]["type"] for feature in collections[kind]["features"]
            }),
            "property_allowlist": sorted(PROPERTY_ALLOWLISTS[kind]),
            "sha256": artifact_hash,
            "artifact_sha256": artifact_hash,
        }
    target_path = OUTPUT / TARGET_FILE
    target_hash = sha256(target_path)
    manifest["artifacts"]["targets"] = {
        "artifact_kind": "exact_target_display_derivative",
        "path": TARGET_FILE,
        "source_dataset_version": SOURCE_VERSION,
        "source_sha256": source_hash,
        "generator_version": GENERATOR_VERSION,
        "rule_version": RULE_VERSION,
        "scope": {"target_ids": sorted(target_ids)},
        "feature_count": len(target_collection["features"]),
        "geometry_types": sorted({
            feature["geometry"]["type"] for feature in target_collection["features"]
        }),
        "object_ids": sorted({
            str(feature["properties"]["object_id"])
            for feature in target_collection["features"]
        }),
        "property_allowlist": sorted(
            PROPERTY_ALLOWLISTS["buildings"] | PROPERTY_ALLOWLISTS["roads"]
        ),
        "sha256": target_hash,
        "artifact_sha256": target_hash,
    }
    write_json(OUTPUT / "manifest.json", manifest)
    return manifest


def validate_collection(kind: str, collection: dict[str, Any]) -> set[str]:
    if collection.get("type") != "FeatureCollection" or not isinstance(
        collection.get("features"), list
    ):
        raise ValueError(f"Invalid display FeatureCollection: {kind}")
    feature_ids: set[str] = set()
    object_ids: set[str] = set()
    for feature in collection["features"]:
        feature_id = str(feature.get("id", ""))
        if not feature_id or feature_id in feature_ids:
            raise ValueError(f"Duplicate or missing display feature ID: {kind}")
        feature_ids.add(feature_id)
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise TypeError(f"Missing display properties: {kind}")
        if not set(properties).issubset(PROPERTY_ALLOWLISTS[kind]):
            raise ValueError(f"Unexpected display properties: {kind}")
        object_id = str(properties.get("object_id", ""))
        if not object_id:
            raise ValueError(f"Missing source object identity: {kind}")
        object_ids.add(object_id)
        geometry = shape(feature.get("geometry"))
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid display geometry: {kind}:{feature_id}")
    return object_ids


def check() -> dict[str, Any]:
    manifest_path = OUTPUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "citygap.public-cartography@1":
        raise ValueError("Display derivative schema version mismatch")
    if manifest.get("generated_at") != GENERATED_AT:
        raise ValueError("Display derivative generation checkpoint mismatch")
    if manifest["source"]["version"] != SOURCE_VERSION:
        raise ValueError("Display derivative source version mismatch")
    if manifest["source"]["sha256"] != SOURCE_SHA256:
        raise ValueError("Display derivative source hash does not match the pinned CityGML release")
    if manifest.get("generator_version") != GENERATOR_VERSION:
        raise ValueError("Display derivative generator version mismatch")
    # Raw municipal/PLATEAU archives are intentionally not tracked in Git. A
    # development checkout that has the archive must prove its bytes match the
    # pinned release; CI still verifies the pinned source identity plus every
    # checked-in derivative hash and object relation below.
    if ARCHIVE.exists() and sha256(ARCHIVE) != SOURCE_SHA256:
        raise ValueError("Available CityGML archive does not match the pinned release")

    _, primary, target_ids = public_area()
    expected_scope = {
        "area_id": primary["id"],
        "area_version": primary["version"],
        "radius_m": primary["radius_m"],
        "area_content_sha256": primary["content_sha256"],
        "origin": {
            "kind": primary["origin"]["kind"],
            "source_feature_id": primary["origin"]["source_feature_id"],
            "coordinates": primary["origin"]["coordinates"],
        },
    }
    if manifest.get("scope") != expected_scope:
        raise ValueError("Display derivative Area scope mismatch")
    if set(manifest.get("target_ids", [])) != target_ids:
        raise ValueError("Display derivative target scope mismatch")

    loaded_collections: dict[str, dict[str, Any]] = {}
    for kind, item in manifest["artifacts"].items():
        if kind not in {*PROPERTY_ALLOWLISTS, "targets"}:
            raise ValueError(f"Unexpected display artifact: {kind}")
        path = OUTPUT / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Display derivative hash mismatch: {kind}")
        if item.get("artifact_sha256") != item["sha256"]:
            raise ValueError(f"Display derivative artifact hash mismatch: {kind}")
        if item.get("source_dataset_version") != SOURCE_VERSION:
            raise ValueError(f"Display derivative source version mismatch: {kind}")
        if item.get("source_sha256") != SOURCE_SHA256:
            raise ValueError(f"Display derivative source hash mismatch: {kind}")
        if item.get("generator_version") != GENERATOR_VERSION:
            raise ValueError(f"Display derivative generator mismatch: {kind}")
        if item.get("rule_version") != RULE_VERSION:
            raise ValueError(f"Display derivative rule mismatch: {kind}")
        collection = json.loads(path.read_text(encoding="utf-8"))
        if len(collection["features"]) != item["feature_count"]:
            raise ValueError(f"Display derivative feature count mismatch: {kind}")
        loaded_collections[kind] = collection

    resolved: dict[str, list[str]] = {}
    source_features: dict[str, list[dict[str, Any]]] = {}
    for kind in PROPERTY_ALLOWLISTS:
        item = manifest["artifacts"][kind]
        collection = loaded_collections[kind]
        object_ids = validate_collection(kind, collection)
        geometry_types = sorted({
            feature["geometry"]["type"] for feature in collection["features"]
        })
        if geometry_types != item["geometry_types"]:
            raise ValueError(f"Display derivative geometry type mismatch: {kind}")
        resolved[kind] = sorted(target_ids.intersection(object_ids))
        if kind in {"buildings", "roads"}:
            for feature in collection["features"]:
                source_features.setdefault(
                    str(feature["properties"]["object_id"]), []
                ).append(feature)

    target_item = manifest["artifacts"].get("targets")
    target_collection = loaded_collections.get("targets")
    if not target_item or not target_collection:
        raise ValueError("Exact target display derivative is missing")
    target_feature_ids: set[str] = set()
    target_object_ids: set[str] = set()
    for feature in target_collection["features"]:
        feature_id = str(feature.get("id", ""))
        if not feature_id or feature_id in target_feature_ids:
            raise ValueError("Duplicate or missing display feature ID: targets")
        target_feature_ids.add(feature_id)
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise TypeError("Missing display properties: targets")
        object_type = str(properties.get("object_type", ""))
        source_kind = (
            "buildings" if object_type == "building"
            else "roads" if object_type == "road"
            else ""
        )
        if not source_kind or not set(properties).issubset(PROPERTY_ALLOWLISTS[source_kind]):
            raise ValueError("Unexpected display properties: targets")
        object_id = str(properties.get("object_id", ""))
        if not object_id:
            raise ValueError("Missing source object identity: targets")
        target_object_ids.add(object_id)
        geometry = shape(feature.get("geometry"))
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid display geometry: targets:{feature_id}")
    if target_object_ids != target_ids or target_item.get("object_ids") != sorted(target_ids):
        raise ValueError("Exact target display derivative identity mismatch")
    expected_target_features = sorted(
        (
            feature
            for object_id in sorted(target_ids)
            for feature in source_features.get(object_id, [])
        ),
        key=lambda feature: (str(feature["properties"]["object_id"]), str(feature["id"])),
    )
    if target_collection["features"] != expected_target_features:
        raise ValueError("Exact target geometry differs from the Area source derivative")
    target_geometry_types = sorted({
        feature["geometry"]["type"] for feature in target_collection["features"]
    })
    if target_geometry_types != target_item["geometry_types"]:
        raise ValueError("Exact target display derivative geometry type mismatch")
    if resolved != manifest.get("resolved_target_ids"):
        raise ValueError("Display derivative target resolution mismatch")
    if set(resolved["buildings"] + resolved["roads"]) != target_ids:
        raise ValueError("A scoped PLATEAU target did not resolve exactly")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = check() if args.check else build()
    print(json.dumps({
        "schema_version": manifest["schema_version"],
        "source_sha256": manifest["source"]["sha256"],
        "feature_counts": {
            kind: item["feature_count"] for kind, item in manifest["artifacts"].items()
        },
        "resolved_target_ids": manifest["resolved_target_ids"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
