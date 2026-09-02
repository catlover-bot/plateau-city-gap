"""Build lazy, Area-scoped PLATEAU display contexts for Guided.

The output is a presentation-only partition of the pinned Maizuru 2025
CityGML source.  It records deterministic geometry intersection membership;
it does not add population allocation, walking semantics, risk, inferred use,
scores, or recommendations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping, shape

from analysis.src.plateau_buildings import read_buildings
from analysis.src.plateau_road_network import read_road_surfaces

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend/public/data"
OUTPUT = PUBLIC / "guided/area-context"
CATALOG = PUBLIC / "guided/area-context-catalog.json"
ARCHIVE = ROOT / "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
MESHES = PUBLIC / "mesh_metrics.geojson"
USAGE_AUDIT = ROOT / "analysis/outputs/real/maizuru_building_usage_audit.csv"
PLANNING = ROOT / "analysis/outputs/real/maizuru_plateau_urban_planning.parquet"

ANALYSIS_CRS = "EPSG:6674"
WEB_CRS = "EPSG:4326"
SCHEMA_VERSION = "citygap.guided-area-context@1"
CATALOG_SCHEMA_VERSION = "citygap.guided-area-context-catalog@1"
RULE_VERSION = "citygap-guided-area-membership@1.0.0"
GENERATOR_VERSION = "citygap-guided-area-context-generator@1.0.0"
SOURCE_VERSION = "26202_maizuru-shi_city_2025_citygml_1_op"
SOURCE_SHA256 = "13f4020ade066dc7139b7653c47a55a09af0093dee743f6b9cca5d3177a71cff"
SECTION_MESH_CODE = "533513314"
SECTION_PACK_ID = "maizuru-533513314-plateau-2025-v1"
SECTION_FILE = PUBLIC / f"spatial-packs/{SECTION_PACK_ID}/sections.json"
VERIFICATION_TARGET_GML_ID = "tran_05dbefba-6a77-40ea-88ac-a568a63a2f05"

PROPERTY_ALLOWLISTS = {
    "buildings": [
        "object_id",
        "object_type",
        "usage_code",
        "usage_label",
        "geometry_source",
        "source_member",
        "source_member_crc32",
    ],
    "roads": [
        "object_id",
        "object_type",
        "surface_id",
        "surface_index",
        "road_name",
        "road_class",
        "function_code",
        "usage_code",
        "source_member",
        "source_member_crc32",
    ],
    "planning": [
        "object_id",
        "object_type",
        "planning_label",
        "planning_type",
        "name",
        "building_coverage_rate",
        "floor_area_rate",
        "geometry_semantics",
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def clean(value: Any) -> Any:
    if value is None or (not isinstance(value, (str, bool)) and pd.isna(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def source_contract() -> dict[str, Any]:
    return {
        "dataset": "Project PLATEAU Maizuru 2025 CityGML",
        "version": SOURCE_VERSION,
        "sha256": SOURCE_SHA256,
        "crs": WEB_CRS,
        "membership_rule": "source geometry intersects selected 500 m mesh polygon; display geometry is clipped to that polygon",
        "rule_version": RULE_VERSION,
        "generator_version": GENERATOR_VERSION,
        "limitations": [
            "display membership only",
            "no inferred use",
            "no walking semantics",
            "no risk or recommendation",
        ],
    }


def prepare_sources() -> tuple[gpd.GeoDataFrame, dict[str, gpd.GeoDataFrame]]:
    source_hash = sha256(ARCHIVE)
    if source_hash != SOURCE_SHA256:
        raise ValueError("Maizuru CityGML source hash does not match the pinned release")

    meshes = gpd.read_file(MESHES).to_crs(ANALYSIS_CRS)
    meshes["mesh_code"] = meshes["mesh_code"].astype(str)
    meshes = meshes.sort_values("mesh_code", kind="stable").reset_index(drop=True)

    usage = pd.read_csv(USAGE_AUDIT, dtype={"usage_code": "string"})
    usage_labels = usage.set_index("usage_code")["official_label"]
    buildings = read_buildings(ARCHIVE)
    buildings = buildings.loc[buildings.geometry.notna() & ~buildings.geometry.is_empty].copy()
    buildings = buildings.sort_values(["gml_id", "source_gml"]).drop_duplicates("gml_id")
    buildings["usage_code"] = buildings["usage"].astype("string")
    buildings["usage_label"] = buildings["usage_code"].map(usage_labels)
    buildings = buildings.rename(columns={"gml_id": "object_id", "source_gml": "source_member"})
    buildings["object_type"] = "building"
    buildings = buildings.to_crs(ANALYSIS_CRS)

    roads = read_road_surfaces(ARCHIVE).to_crs(ANALYSIS_CRS)
    roads = roads.rename(columns={"gml_id": "object_id"})
    roads["object_type"] = "road"

    planning = gpd.read_parquet(PLANNING).to_crs(ANALYSIS_CRS)
    planning = planning.rename(columns={"gml_id": "object_id"})
    planning["object_type"] = "planning"
    planning["geometry_semantics"] = "official geometry intersecting selected Area"
    return meshes, {"buildings": buildings, "roads": roads, "planning": planning}


def membership(
    frame: gpd.GeoDataFrame,
    meshes: gpd.GeoDataFrame,
) -> dict[str, gpd.GeoDataFrame]:
    joined = gpd.sjoin(
        frame,
        meshes[["mesh_code", "geometry"]],
        how="inner",
        predicate="intersects",
    ).drop(columns=["index_right"])
    joined = joined.to_crs(WEB_CRS)
    return {
        str(mesh_code): group.drop(columns=["mesh_code"]).copy()
        for mesh_code, group in joined.groupby("mesh_code", sort=True)
    }


def feature_collection(
    frame: gpd.GeoDataFrame,
    kind: str,
    clip_geometry: Any,
) -> dict[str, Any]:
    columns = PROPERTY_ALLOWLISTS[kind]
    sort_columns = ["object_id"]
    if "surface_index" in frame.columns:
        sort_columns.append("surface_index")
    features: list[dict[str, Any]] = []
    for row in frame.sort_values(sort_columns, kind="stable").itertuples(index=False):
        values = row._asdict()
        geometry = values.pop("geometry").intersection(clip_geometry)
        if geometry.is_empty:
            continue
        properties = {column: clean(values.get(column)) for column in columns}
        suffix = f":{properties['surface_index']}" if "surface_index" in properties else ""
        features.append(
            {
                "type": "Feature",
                "id": f"{properties['object_id']}{suffix}",
                "properties": properties,
                "geometry": mapping(geometry),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def empty_frame(source: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return source.iloc[0:0].to_crs(WEB_CRS)


def capability(count: int, label: str) -> dict[str, Any]:
    return {
        "status": "available" if count else "partial",
        "object_count": count,
        "reason": (
            f"Pinned citywide CityGMLからAreaと交差する{label}を表示"
            if count
            else f"Pinned citywide CityGMLでAreaと交差する{label}を確認できず、存在しないとは断定しない"
        ),
    }


def catalog_capabilities(capabilities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Keep the first-load catalog free of selected-Area references and payloads."""
    return {
        key: {
            field: value[field]
            for field in ("status", "reason", "object_count")
            if field in value
        }
        for key, value in capabilities.items()
    }


def build() -> dict[str, Any]:
    meshes, sources = prepare_sources()
    memberships = {
        kind: membership(frame, meshes)
        for kind, frame in sources.items()
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    existing = {path.name for path in OUTPUT.glob("*.json")}
    expected: set[str] = set()
    catalog_items: list[dict[str, Any]] = []

    source = source_contract()
    for mesh in meshes.itertuples(index=False):
        mesh_code = str(mesh.mesh_code)
        filename = f"{mesh_code}.json"
        expected.add(filename)
        area_geometry_web = gpd.GeoSeries(
            [mesh.geometry], crs=ANALYSIS_CRS
        ).to_crs(WEB_CRS).iloc[0]
        layers = {
            kind: feature_collection(
                memberships[kind].get(mesh_code, empty_frame(sources[kind])),
                kind,
                area_geometry_web,
            )
            for kind in ("buildings", "roads", "planning")
        }
        counts = {kind: len(collection["features"]) for kind, collection in layers.items()}
        if mesh_code == SECTION_MESH_CODE and not any(
            feature["properties"]["object_id"] == VERIFICATION_TARGET_GML_ID
            and feature["properties"]["surface_index"] == 0
            for feature in layers["roads"]["features"]
        ):
            raise ValueError("Verified Guided road target is missing from its Area context")
        area_geometry = mapping(area_geometry_web)
        section = (
            {
                "status": "available",
                "reason": "このAreaに対応する検証済み断面artifactがあります",
                "pack_id": SECTION_PACK_ID,
                "path": f"data/spatial-packs/{SECTION_PACK_ID}/sections.json",
                "sha256": sha256(SECTION_FILE),
                "bytes": SECTION_FILE.stat().st_size,
            }
            if mesh_code == SECTION_MESH_CODE
            else {
                "status": "unavailable",
                "reason": "このAreaに対応する検証済み断面artifactはありません",
            }
        )
        capabilities = {
            "plateau_buildings": capability(counts["buildings"], "建物"),
            "plateau_roads": capability(counts["roads"], "道路面"),
            "planning": capability(counts["planning"], "都市計画geometry"),
            "terrain": (
                {
                    "status": "available",
                    "reason": "検証済みsectionのPLATEAU DEM terrain sampleを表示",
                }
                if mesh_code == SECTION_MESH_CODE
                else {
                    "status": "unavailable",
                    "reason": "このAreaには配布可能な検証済みterrain display contextがありません",
                }
            ),
            "urban_section": section,
            "verification_targets": {
                "status": "available" if mesh_code == SECTION_MESH_CODE else "partial",
                "reason": (
                    "検証済みobject targetとArea fallbackを利用"
                    if mesh_code == SECTION_MESH_CODE
                    else "PLATEAU object targetは未解決のためArea fallbackを利用"
                ),
            },
        }
        context = {
            "schema_version": SCHEMA_VERSION,
            "area_id": f"maizuru-{mesh_code}",
            "mesh_code": mesh_code,
            "area_geometry_sha256": json_sha256(area_geometry),
            "source": source,
            "capabilities": capabilities,
            "layers": layers,
            "section": section,
        }
        path = OUTPUT / filename
        write_json(path, context)
        context_hash = sha256(path)
        catalog_items.append(
            {
                "area_id": context["area_id"],
                "mesh_code": mesh_code,
                "context_path": f"data/guided/area-context/{filename}",
                "context_sha256": context_hash,
                "context_bytes": path.stat().st_size,
                "area_geometry_sha256": context["area_geometry_sha256"],
                "capabilities": catalog_capabilities(capabilities),
                "counts": counts,
            }
        )

    for stale in existing.difference(expected):
        (OUTPUT / stale).unlink()

    catalog = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "source": source,
        "mesh_source": {
            "path": "data/mesh_metrics.geojson",
            "sha256": sha256(MESHES),
            "area_count": len(catalog_items),
        },
        "items": catalog_items,
        "prohibitions": [
            "no_population_allocation",
            "no_walking_semantics",
            "no_risk_or_recommendation",
            "no_inferred_use",
            "no_fake_geometry",
        ],
    }
    write_json(CATALOG, catalog)
    return catalog


def repack_existing() -> dict[str, Any]:
    """Upgrade an already parsed deterministic partition without re-reading CityGML."""
    if not CATALOG.exists():
        raise ValueError("Guided Area catalog does not exist; run the full build first")
    meshes = gpd.read_file(MESHES).to_crs(WEB_CRS)
    mesh_geometry = {
        str(row.mesh_code): row.geometry
        for row in meshes.itertuples(index=False)
    }
    previous = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_items: list[dict[str, Any]] = []
    source = source_contract()
    for item in previous["items"]:
        mesh_code = str(item["mesh_code"])
        path = ROOT / "frontend/public" / item["context_path"]
        context = json.loads(path.read_text(encoding="utf-8"))
        area_geometry = mesh_geometry[mesh_code]
        for kind in PROPERTY_ALLOWLISTS:
            clipped: list[dict[str, Any]] = []
            for feature in context["layers"][kind]["features"]:
                geometry = shape(feature["geometry"]).intersection(area_geometry)
                if geometry.is_empty:
                    continue
                feature["geometry"] = mapping(geometry)
                clipped.append(feature)
            context["layers"][kind]["features"] = clipped
        counts = {
            kind: len(context["layers"][kind]["features"])
            for kind in PROPERTY_ALLOWLISTS
        }
        section = (
            {
                "status": "available",
                "reason": "このAreaに対応する検証済み断面artifactがあります",
                "pack_id": SECTION_PACK_ID,
                "path": f"data/spatial-packs/{SECTION_PACK_ID}/sections.json",
                "sha256": sha256(SECTION_FILE),
                "bytes": SECTION_FILE.stat().st_size,
            }
            if mesh_code == SECTION_MESH_CODE
            else {
                "status": "unavailable",
                "reason": "このAreaに対応する検証済み断面artifactはありません",
            }
        )
        context["source"] = source
        context["area_geometry_sha256"] = json_sha256(mapping(area_geometry))
        context["section"] = section
        context["capabilities"]["urban_section"] = section
        for kind, capability_name in (
            ("buildings", "plateau_buildings"),
            ("roads", "plateau_roads"),
            ("planning", "planning"),
        ):
            context["capabilities"][capability_name]["object_count"] = counts[kind]
        write_json(path, context)
        catalog_items.append(
            {
                "area_id": context["area_id"],
                "mesh_code": mesh_code,
                "context_path": item["context_path"],
                "context_sha256": sha256(path),
                "context_bytes": path.stat().st_size,
                "area_geometry_sha256": context["area_geometry_sha256"],
                "capabilities": catalog_capabilities(context["capabilities"]),
                "counts": counts,
            }
        )
    catalog = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "source": source,
        "mesh_source": {
            "path": "data/mesh_metrics.geojson",
            "sha256": sha256(MESHES),
            "area_count": len(catalog_items),
        },
        "items": catalog_items,
        "prohibitions": [
            "no_population_allocation",
            "no_walking_semantics",
            "no_risk_or_recommendation",
            "no_inferred_use",
            "no_fake_geometry",
        ],
    }
    write_json(CATALOG, catalog)
    return catalog


def validate_collection(value: dict[str, Any], kind: str) -> None:
    if value.get("type") != "FeatureCollection" or not isinstance(value.get("features"), list):
        raise ValueError(f"Invalid Guided Area layer: {kind}")
    ids: set[str] = set()
    for feature in value["features"]:
        feature_id = str(feature.get("id", ""))
        if not feature_id or feature_id in ids:
            raise ValueError(f"Duplicate or missing Guided feature ID: {kind}")
        ids.add(feature_id)
        properties = feature.get("properties")
        if not isinstance(properties, dict) or not set(properties).issubset(
            PROPERTY_ALLOWLISTS[kind]
        ):
            raise ValueError(f"Unexpected Guided properties: {kind}")
        geometry = shape(feature.get("geometry"))
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid Guided geometry: {kind}:{feature_id}")


@lru_cache(maxsize=1)
def check() -> dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise ValueError("Guided Area catalog schema mismatch")
    if catalog["source"] != source_contract():
        raise ValueError("Guided Area source contract mismatch")
    if catalog["mesh_source"]["sha256"] != sha256(MESHES):
        raise ValueError("Guided Area mesh source hash mismatch")
    if catalog["mesh_source"]["area_count"] != 495 or len(catalog["items"]) != 495:
        raise ValueError("Guided Area catalog must contain 495 Areas")
    if ARCHIVE.exists() and sha256(ARCHIVE) != SOURCE_SHA256:
        raise ValueError("Available CityGML archive does not match the pinned release")

    mesh_codes: set[str] = set()
    for item in catalog["items"]:
        mesh_code = str(item["mesh_code"])
        if mesh_code in mesh_codes:
            raise ValueError("Duplicate Guided Area")
        mesh_codes.add(mesh_code)
        path = ROOT / "frontend/public" / item["context_path"]
        if sha256(path) != item["context_sha256"] or path.stat().st_size != item["context_bytes"]:
            raise ValueError(f"Guided Area context hash mismatch: {mesh_code}")
        context = json.loads(path.read_text(encoding="utf-8"))
        if context["schema_version"] != SCHEMA_VERSION or context["mesh_code"] != mesh_code:
            raise ValueError(f"Guided Area context identity mismatch: {mesh_code}")
        if context["source"] != catalog["source"]:
            raise ValueError(f"Guided Area source mismatch: {mesh_code}")
        if context["area_geometry_sha256"] != item["area_geometry_sha256"]:
            raise ValueError(f"Guided Area geometry hash mismatch: {mesh_code}")
        for kind in PROPERTY_ALLOWLISTS:
            validate_collection(context["layers"][kind], kind)
            if len(context["layers"][kind]["features"]) != item["counts"][kind]:
                raise ValueError(f"Guided Area count mismatch: {mesh_code}:{kind}")
        if mesh_code == SECTION_MESH_CODE and not any(
            feature["properties"]["object_id"] == VERIFICATION_TARGET_GML_ID
            and feature["properties"]["surface_index"] == 0
            for feature in context["layers"]["roads"]["features"]
        ):
            raise ValueError("Verified Guided road target is missing from its Area context")
        section_available = context["section"]["status"] == "available"
        if section_available != (mesh_code == SECTION_MESH_CODE):
            raise ValueError(f"Guided section leaked to another Area: {mesh_code}")
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--repack-existing", action="store_true")
    args = parser.parse_args()
    value = check() if args.check else repack_existing() if args.repack_existing else build()
    print(
        json.dumps(
            {
                "schema_version": value["schema_version"],
                "area_count": len(value["items"]),
                "source": value["source"]["version"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
