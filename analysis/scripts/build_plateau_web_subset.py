"""Build the static PLATEAU tileset for the final 3D Deep Dive.

The CITY GAP Top 10 is outside the official building-model coverage.  The
subset therefore targets the verified PLATEAU-covered comparison mesh used by
Story Mode, while retaining the zero-coverage statement for the Top 10.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import struct
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = (
    REPOSITORY_ROOT
    / "data/raw/plateau_3d/extracted"
    / "26202_maizuru-shi_city_2025_citygml_1_op_bldg_3dtiles_lod2"
)
SOURCE_ZIP = (
    REPOSITORY_ROOT
    / "data/raw/plateau_3d/26202_maizuru-shi_city_2025_3dtiles_mvt_1_op.zip"
)
INSPECTION = (
    REPOSITORY_ROOT
    / "analysis/outputs/real/maizuru_plateau_building_inspection.json"
)
TOP10_CSV = REPOSITORY_ROOT / "analysis/outputs/real/maizuru_city_gap_top10.csv"
OUTPUT_DIR = REPOSITORY_ROOT / "frontend/public/data/plateau"

OFFICIAL_URL = (
    "https://assets.cms.plateau.reearth.io/assets/55/"
    "2c1991-f75e-4bf8-9108-531c27952a2b/"
    "26202_maizuru-shi_city_2025_3dtiles_mvt_1_op.zip"
)
OFFICIAL_DATASET_URL = (
    "https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025"
)
OFFICIAL_ZIP_BYTES = 160_582_905
OFFICIAL_ZIP_SHA256 = (
    "15cf5e12b507b89e2b86fe0c2968a22e8d770ea36cb8c64cc7e8db578109f2d9"
)
MAX_OUTPUT_BYTES = 15_000_000
DEEP_DIVE = {
    "mesh_code": "533513314",
    "area_label": "常団地前バス停周辺",
    "overall_rank": 23,
    "west": 135.39375,
    "south": 35.44583333333334,
    "east": 135.4,
    "north": 35.45,
    "longitude": 135.396875,
    "latitude": 35.44791666666667,
    "expected_buildings": 296,
}
EXPECTED_URIS = {
    "data/data284.b3dm",
    "data/data285.b3dm",
    "data/data287.b3dm",
}
FEATURED_BUILDING_ID = "bldg_a490fb5b-d668-441e-b9af-5b35c4629006"
COMPONENT_FORMAT = {
    "BYTE": "b",
    "UNSIGNED_BYTE": "B",
    "SHORT": "h",
    "UNSIGNED_SHORT": "H",
    "INT": "i",
    "UNSIGNED_INT": "I",
    "FLOAT": "f",
    "DOUBLE": "d",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    options: dict[str, Any] = {"ensure_ascii": False}
    if compact:
        options["separators"] = (",", ":")
    else:
        options["indent"] = 2
    path.write_text(json.dumps(value, **options) + "\n", encoding="utf-8")


def _distance_to_region_m(lon: float, lat: float, region: list[float]) -> float:
    west, south, east, north = map(math.degrees, region[:4])
    near_lon = min(max(lon, west), east)
    near_lat = min(max(lat, south), north)
    dx = (
        math.radians(lon - near_lon)
        * math.cos(math.radians(lat))
        * 6_371_008.8
    )
    dy = math.radians(lat - near_lat) * 6_371_008.8
    return math.hypot(dx, dy)


def _leaf_tiles(tileset: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def visit(tile: dict[str, Any]) -> None:
        children = tile.get("children", [])
        content = tile.get("content")
        if content and not children:
            result.append(
                {
                    "uri": content["uri"],
                    "boundingVolume": content.get(
                        "boundingVolume", tile["boundingVolume"]
                    ),
                }
            )
        for child in children:
            visit(child)

    visit(tileset["root"])
    return result


def _decode_property(
    batch_table: dict[str, Any], batch_binary: bytes, name: str, count: int
) -> Any:
    value = batch_table.get(name)
    if not isinstance(value, dict) or "byteOffset" not in value:
        return value
    component_format = COMPONENT_FORMAT[value["componentType"]]
    return struct.unpack_from(
        "<" + component_format * count,
        batch_binary,
        int(value["byteOffset"]),
    )


def _read_buildings(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as stream:
        header = stream.read(28)
        if header[:4] != b"b3dm":
            raise ValueError(f"Not a b3dm file: {path}")
        version, byte_length, ft_json_len, ft_bin_len, bt_json_len, bt_bin_len = (
            struct.unpack("<6I", header[4:])
        )
        if version != 1 or byte_length != path.stat().st_size:
            raise ValueError(f"Invalid b3dm header: {path}")
        feature_table = json.loads(stream.read(ft_json_len))
        stream.read(ft_bin_len)
        batch_table = json.loads(stream.read(bt_json_len))
        batch_binary = stream.read(bt_bin_len)

    count = int(feature_table["BATCH_LENGTH"])
    identifiers = batch_table["gml_id"]
    attributes = batch_table["attributes"]
    xs = _decode_property(batch_table, batch_binary, "_x", count)
    ys = _decode_property(batch_table, batch_binary, "_y", count)
    lods = _decode_property(batch_table, batch_binary, "_lod", count)
    if not (
        len(identifiers) == len(attributes) == len(xs) == len(ys) == len(lods) == count
    ):
        raise ValueError(f"Inconsistent b3dm batch table: {path}")
    return [
        {
            "gml_id": identifiers[index],
            "attributes": attributes[index],
            "x": xs[index],
            "y": ys[index],
            "lod": lods[index],
        }
        for index in range(count)
    ]


def _first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def _valid_number(value: Any, *, allow_zero: bool = False) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if not math.isfinite(value) or value in {-9999, 9999}:
        return False
    return value >= 0 if allow_zero else value > 0


def _numeric_summary(values: list[Any], *, allow_zero: bool = False) -> dict[str, Any]:
    known = [value for value in values if _valid_number(value, allow_zero=allow_zero)]
    total = len(values)
    return {
        "known": len(known),
        "missing_or_sentinel": total - len(known),
        "completeness_percent": round(100 * len(known) / total, 3),
        "min": min(known) if known else None,
        "median": statistics.median(known) if known else None,
        "max": max(known) if known else None,
    }


def _building_summary(buildings: list[dict[str, Any]]) -> dict[str, Any]:
    unique = {building["gml_id"]: building for building in buildings}
    if len(unique) != len(buildings):
        raise ValueError("Selected leaf tiles contain duplicate building identifiers")
    usage: list[Any] = []
    height: list[Any] = []
    storeys_above: list[Any] = []
    storeys_below: list[Any] = []
    footprint: list[Any] = []
    total_floor_area: list[Any] = []
    lods: list[Any] = []
    for building in unique.values():
        attributes = building["attributes"]
        detail = _first_dict(attributes.get("uro:BuildingDetailAttribute"))
        usage.append(attributes.get("bldg:usage"))
        height.append(attributes.get("bldg:measuredHeight"))
        storeys_above.append(attributes.get("bldg:storeysAboveGround"))
        storeys_below.append(attributes.get("bldg:storeysBelowGround"))
        footprint.append(detail.get("uro:buildingFootprintArea"))
        total_floor_area.append(detail.get("uro:totalFloorArea"))
        lods.append(building["lod"])
    known_usage = [value for value in usage if value not in {None, "", "不明"}]
    total = len(unique)
    return {
        "records": total,
        "usage": {
            "known_excluding_unknown": len(known_usage),
            "known_percent": round(100 * len(known_usage) / total, 3),
            "values": dict(Counter(usage).most_common()),
        },
        "measured_height_m": _numeric_summary(height),
        "storeys_above_ground": _numeric_summary(storeys_above, allow_zero=True),
        "storeys_below_ground": _numeric_summary(storeys_below, allow_zero=True),
        "building_footprint_area_m2": _numeric_summary(footprint),
        "building_total_floor_area_m2": _numeric_summary(total_floor_area),
        "geometry_lod": {
            str(lod): count for lod, count in sorted(Counter(lods).items())
        },
    }


def _featured_building(buildings: list[dict[str, Any]]) -> dict[str, Any]:
    """Return one verified, legible official building for the Deep Dive story."""
    matches = [
        building for building in buildings
        if building["gml_id"] == FEATURED_BUILDING_ID
    ]
    if len(matches) != 1:
        raise ValueError("Verified Deep Dive building is missing or duplicated")
    building = matches[0]
    attributes = building["attributes"]
    detail = _first_dict(attributes.get("uro:BuildingDetailAttribute"))
    featured = {
        "id": building["gml_id"],
        "longitude": building["x"],
        "latitude": building["y"],
        "usage": attributes.get("bldg:usage"),
        "measured_height_m": attributes.get("bldg:measuredHeight"),
        "storeys_above_ground": attributes.get("bldg:storeysAboveGround"),
        "storeys_below_ground": attributes.get("bldg:storeysBelowGround"),
        "building_footprint_area_m2": detail.get("uro:buildingFootprintArea"),
        "total_floor_area_m2": detail.get("uro:totalFloorArea"),
        "lod": building["lod"],
    }
    expected = {
        "usage": "住宅",
        "measured_height_m": 8.5,
        "storeys_above_ground": 2,
        "storeys_below_ground": 0,
        "building_footprint_area_m2": 61.73,
        "total_floor_area_m2": 125.54,
        "lod": 1,
    }
    if any(featured[key] != value for key, value in expected.items()):
        raise ValueError("Verified Deep Dive building attributes changed")
    return featured


def _merged_region(selected: list[dict[str, Any]]) -> list[float]:
    regions = [tile["boundingVolume"]["region"] for tile in selected]
    return [
        min(region[0] for region in regions),
        min(region[1] for region in regions),
        max(region[2] for region in regions),
        max(region[3] for region in regions),
        min(region[4] for region in regions),
        max(region[5] for region in regions),
    ]


def _top10_pairs(path: Path = TOP10_CSV) -> list[tuple[int, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return [
            (int(row["rank"]), str(row["mesh_code"]))
            for row in csv.DictReader(stream)
        ]


def _validate_inspection(path: Path) -> dict[str, Any]:
    inspection = json.loads(path.read_text(encoding="utf-8"))
    expected_pairs = _top10_pairs()
    if len(expected_pairs) != 10 or [rank for rank, _ in expected_pairs] != list(
        range(1, 11)
    ):
        raise ValueError("Analysis Top 10 ranks must be exactly 1 through 10")
    input_pairs = [
        (int(item["rank"]), str(item["mesh_code"]))
        for item in inspection["input"]["top10_meshes"]
    ]
    per_mesh = inspection["top10_by_mesh"]
    inspected_pairs = [
        (int(item["rank"]), str(item["mesh_code"])) for item in per_mesh
    ]
    if input_pairs != expected_pairs or inspected_pairs != expected_pairs:
        raise ValueError("PLATEAU inspection does not match the analysis Top 10")
    for level in ("lod1_container", "lod2_container"):
        container = inspection[level]
        if container["b3dm_files"] != 427 or container["unique_buildings"] != 44_640:
            raise ValueError(f"Unexpected full PLATEAU building inventory in {level}")
    if inspection.get("lod1_unique_ids_equal_lod2") is not True:
        raise ValueError("PLATEAU LOD1 and LOD2 building identifiers disagree")
    expected_lods = {
        "whole_city_lod1_attributes": {"1": 44_640},
        "whole_city_lod2_attributes": {"1": 43_136, "2": 1_504},
    }
    for section, geometry_lods in expected_lods.items():
        attributes = inspection[section]
        if (
            attributes["lod2_source_populated"] != 1_504
            or attributes["geometry_lod_in_3dtiles"] != geometry_lods
        ):
            raise ValueError(f"Unexpected PLATEAU LOD inventory in {section}")
    if (
        inspection["top10_lod1_attributes"]["buildings"] != 0
        or inspection["top10_lod2_attributes"]["buildings"] != 0
    ):
        raise ValueError("Top 10 unexpectedly intersects PLATEAU building centers")
    if any(
        item["attribute_summary"]["buildings"] != 0
        or item["coverage_distance"]["building_centers_inside"] != 0
        or item["coverage_distance"]["building_bboxes_intersecting"] != 0
        for item in per_mesh
    ):
        raise ValueError("Top 10 unexpectedly intersects an official PLATEAU building")
    return inspection


def _verify_extracted_against_archive(
    source_dir: Path, source_zip: Path, relative_paths: list[str]
) -> None:
    prefix = source_dir.name
    with zipfile.ZipFile(source_zip) as archive:
        b3dm_names = [
            name
            for name in archive.namelist()
            if name.startswith(f"{prefix}/data/") and name.endswith(".b3dm")
        ]
        if len(b3dm_names) != 427:
            raise ValueError("Official PLATEAU ZIP does not contain 427 LOD2 building tiles")
        for relative in relative_paths:
            member_name = f"{prefix}/{relative}"
            try:
                info = archive.getinfo(member_name)
            except KeyError as error:
                raise ValueError(f"PLATEAU ZIP member is missing: {member_name}") from error
            extracted = source_dir / relative
            if info.file_size != extracted.stat().st_size:
                raise ValueError(f"Extracted PLATEAU member size differs: {relative}")
            archive_digest = hashlib.sha256()
            with archive.open(info) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    archive_digest.update(block)
            if archive_digest.hexdigest() != _sha256(extracted):
                raise ValueError(f"Extracted PLATEAU member hash differs: {relative}")


def _validate_output_target(source_dir: Path, output_dir: Path) -> None:
    source = source_dir.resolve()
    output = output_dir.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("PLATEAU source and output directories must be disjoint")
    candidate = output_dir.absolute()
    while candidate != candidate.parent:
        if candidate.is_symlink():
            raise ValueError("PLATEAU output directory must not traverse a symlink")
        candidate = candidate.parent
    data_dir = output_dir / "data"
    if data_dir.is_symlink():
        raise ValueError("PLATEAU output data directory must not be a symlink")
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("PLATEAU output target exists and is not a directory")


def _publish_subset(
    source_dir: Path,
    selected: list[dict[str, Any]],
    tileset: dict[str, Any],
    metadata: dict[str, Any],
    output_dir: Path,
) -> int:
    """Publish a fully staged subset, retaining the prior output on failure."""
    output_parent = output_dir.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    _validate_output_target(source_dir, output_dir)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_parent)
    )
    backup_holder: Path | None = None
    backup: Path | None = None
    try:
        (staging / "data").mkdir()
        for tile in selected:
            shutil.copy2(source_dir / tile["uri"], staging / tile["uri"])
        _write_json(staging / "tileset.json", tileset, compact=True)
        _write_json(staging / "metadata.json", metadata)
        actual_bytes = sum(
            path.stat().st_size for path in staging.rglob("*") if path.is_file()
        )
        if actual_bytes > MAX_OUTPUT_BYTES:
            raise ValueError("Complete PLATEAU web subset exceeds the byte budget")

        if output_dir.exists():
            backup_holder = Path(
                tempfile.mkdtemp(
                    prefix=f".{output_dir.name}.backup-", dir=output_parent
                )
            )
            backup = backup_holder / "previous"
            os.replace(output_dir, backup)
        try:
            os.replace(staging, output_dir)
        except Exception:
            if backup is not None and backup.exists():
                try:
                    os.replace(backup, output_dir)
                except Exception as restore_error:
                    raise RuntimeError(
                        f"PLATEAU publish failed and the prior output remains at {backup}"
                    ) from restore_error
            raise
        if backup_holder is not None:
            shutil.rmtree(backup_holder)
            backup_holder = None
        return actual_bytes
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup_holder is not None and backup_holder.exists() and not (
            backup_holder / "previous"
        ).exists():
            shutil.rmtree(backup_holder)


def build_subset(
    source_dir: Path, source_zip: Path, inspection_path: Path, output_dir: Path
) -> dict[str, Any]:
    _validate_output_target(source_dir, output_dir)
    for required in (source_dir / "tileset.json", source_zip, inspection_path):
        if not required.is_file():
            raise FileNotFoundError(f"Required PLATEAU input is missing: {required}")
    if source_zip.stat().st_size != OFFICIAL_ZIP_BYTES:
        raise ValueError("Official PLATEAU ZIP size does not match the verified package")
    if _sha256(source_zip) != OFFICIAL_ZIP_SHA256:
        raise ValueError("Official PLATEAU ZIP checksum does not match")
    inspection = _validate_inspection(inspection_path)

    source_tileset = json.loads((source_dir / "tileset.json").read_text(encoding="utf-8"))
    selected: list[dict[str, Any]] = []
    for tile in _leaf_tiles(source_tileset):
        region = tile["boundingVolume"]["region"]
        west, south, east, north = map(math.degrees, region[:4])
        intersects = not (
            east < DEEP_DIVE["west"]
            or west > DEEP_DIVE["east"]
            or north < DEEP_DIVE["south"]
            or south > DEEP_DIVE["north"]
        )
        if intersects:
            selected.append(tile)
    if {tile["uri"] for tile in selected} != EXPECTED_URIS:
        raise ValueError("PLATEAU leaf-tile selection differs from the verified subset")

    _verify_extracted_against_archive(
        source_dir,
        source_zip,
        ["tileset.json", *sorted(EXPECTED_URIS)],
    )

    selected_bytes = sum((source_dir / tile["uri"]).stat().st_size for tile in selected)
    if selected_bytes > MAX_OUTPUT_BYTES:
        raise ValueError("PLATEAU subset exceeds the web byte budget")
    root_region = _merged_region(selected)
    tileset = {
        "asset": {"version": "1.0"},
        "geometricError": source_tileset["geometricError"],
        "root": {
            "boundingVolume": {"region": root_region},
            "geometricError": source_tileset["geometricError"],
            "refine": "ADD",
            "children": [
                {
                    "boundingVolume": tile["boundingVolume"],
                    "geometricError": 0,
                    "refine": "ADD",
                    "content": {"uri": tile["uri"]},
                    "children": [],
                }
                for tile in selected
            ],
        },
    }
    buildings = [
        building
        for tile in selected
        for building in _read_buildings(source_dir / tile["uri"])
    ]
    deep_dive_buildings = [
        building
        for building in buildings
        if DEEP_DIVE["west"] <= building["x"] < DEEP_DIVE["east"]
        and DEEP_DIVE["south"] <= building["y"] < DEEP_DIVE["north"]
    ]
    if len(deep_dive_buildings) != DEEP_DIVE["expected_buildings"]:
        raise ValueError("PLATEAU Deep Dive building count differs from verified coverage")
    metadata = {
        "schema_version": "1.0.0",
        "status": "deep_dive_subset_available",
        "purpose": (
            "Official PLATEAU 3D Deep Dive for CITY GAP overall rank 23. "
            "It is not a building layer for CITY GAP Top 10."
        ),
        "official_dataset": "3D都市モデル（Project PLATEAU）舞鶴市（2025年度）",
        "official_dataset_url": OFFICIAL_DATASET_URL,
        "source": {
            "format": "3D Tiles 1.0 b3dm from the v5 distribution",
            "url": OFFICIAL_URL,
            "bytes": OFFICIAL_ZIP_BYTES,
            "sha256": OFFICIAL_ZIP_SHA256,
        },
        "license": {
            "attribution_required": True,
            "site_policy": "https://www.mlit.go.jp/plateau/site-policy/",
        },
        "city_gap_top10": {
            "status": "outside_official_building_coverage",
            "building_centers": 0,
            "building_bbox_intersections": 0,
            "official_distribution_unique_buildings": inspection["lod1_container"][
                "unique_buildings"
            ],
        },
        "selection": {
            "method": "LOD2 tileset leaf regions intersecting the verified 500 m mesh",
            "deep_dive": DEEP_DIVE,
            "tiles": len(selected),
            "b3dm_bytes": selected_bytes,
            "bounding_region_degrees": [
                math.degrees(root_region[0]),
                math.degrees(root_region[1]),
                math.degrees(root_region[2]),
                math.degrees(root_region[3]),
                root_region[4],
                root_region[5],
            ],
        },
        "buildings": _building_summary(buildings),
        "deep_dive_buildings": _building_summary(deep_dive_buildings),
        "featured_building": _featured_building(deep_dive_buildings),
        "files": [
            {
                "uri": tile["uri"],
                "bytes": (source_dir / tile["uri"]).stat().st_size,
                "sha256": _sha256(source_dir / tile["uri"]),
            }
            for tile in selected
        ],
    }
    actual_bytes = _publish_subset(
        source_dir, selected, tileset, metadata, output_dir
    )
    return {"output_dir": str(output_dir), "total_bytes": actual_bytes, **metadata}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    parser.add_argument("--inspection", type=Path, default=INSPECTION)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_subset(
        args.source_dir, args.source_zip, args.inspection, args.output_dir
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
