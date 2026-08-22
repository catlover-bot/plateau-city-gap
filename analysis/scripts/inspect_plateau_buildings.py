"""Inspect the official Maizuru PLATEAU building 3D Tiles deterministically."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import struct
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data/raw/plateau_3d/extracted"
TOP10_CSV = ROOT / "analysis/outputs/real/maizuru_city_gap_top10.csv"
OUTPUT = ROOT / "analysis/outputs/real/maizuru_plateau_building_inspection.json"

LOD_DIRS = {
    "lod1": EXTRACTED
    / "26202_maizuru-shi_city_2025_citygml_1_op_bldg_3dtiles_lod1",
    "lod2": EXTRACTED
    / "26202_maizuru-shi_city_2025_citygml_1_op_bldg_3dtiles_lod2",
}

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


def repository_path(path: Path) -> str:
    """Return a checkout-independent path for report lineage."""
    return path.resolve().relative_to(ROOT).as_posix()


def read_b3dm(path: Path) -> tuple[int, dict, bytes]:
    with path.open("rb") as stream:
        header = stream.read(28)
        if header[:4] != b"b3dm":
            raise ValueError(f"not b3dm: {path}")
        version, byte_length, ft_json_len, ft_bin_len, bt_json_len, bt_bin_len = (
            struct.unpack("<6I", header[4:])
        )
        if version != 1 or byte_length != path.stat().st_size:
            raise ValueError(f"bad b3dm header: {path}")
        feature_table = json.loads(stream.read(ft_json_len))
        stream.read(ft_bin_len)
        batch_table = json.loads(stream.read(bt_json_len))
        batch_binary = stream.read(bt_bin_len)
    return int(feature_table["BATCH_LENGTH"]), batch_table, batch_binary


def decode_property(batch_table: dict, batch_binary: bytes, name: str, count: int):
    value = batch_table.get(name)
    if not isinstance(value, dict) or "byteOffset" not in value:
        return value
    fmt = COMPONENT_FORMAT[value["componentType"]]
    return struct.unpack_from(
        "<" + fmt * count,
        batch_binary,
        int(value["byteOffset"]),
    )


def tile_metadata(tileset_path: Path) -> dict[str, dict]:
    tileset = json.loads(tileset_path.read_text(encoding="utf-8"))
    result: dict[str, dict] = {}

    def visit(tile: dict, depth: int) -> None:
        content = tile.get("content")
        if content and content.get("uri"):
            result[content["uri"]] = {
                "depth": depth,
                "leaf": not bool(tile.get("children")),
                "tile_bounding_volume": tile.get("boundingVolume"),
                "content_bounding_volume": content.get("boundingVolume"),
                "geometric_error": tile.get("geometricError"),
            }
        for child in tile.get("children", []):
            visit(child, depth + 1)

    visit(tileset["root"], 0)
    return result


def parse_directory(directory: Path) -> dict:
    metadata = tile_metadata(directory / "tileset.json")
    occurrences: dict[str, list[dict]] = defaultdict(list)
    instance_count = 0
    batch_lengths = []
    all_keys = set()

    for path in sorted((directory / "data").glob("*.b3dm")):
        count, batch_table, batch_binary = read_b3dm(path)
        batch_lengths.append(count)
        instance_count += count
        all_keys.update(batch_table)
        ids = batch_table["gml_id"]
        attrs = batch_table["attributes"]
        xs = decode_property(batch_table, batch_binary, "_x", count)
        ys = decode_property(batch_table, batch_binary, "_y", count)
        xmins = decode_property(batch_table, batch_binary, "_xmin", count)
        xmaxs = decode_property(batch_table, batch_binary, "_xmax", count)
        ymins = decode_property(batch_table, batch_binary, "_ymin", count)
        ymaxs = decode_property(batch_table, batch_binary, "_ymax", count)
        lods = decode_property(batch_table, batch_binary, "_lod", count)
        uri = "data/" + path.name
        info = metadata[uri]
        for index in range(count):
            occurrences[ids[index]].append(
                {
                    "gml_id": ids[index],
                    "attrs": attrs[index],
                    "x": xs[index],
                    "y": ys[index],
                    "xmin": xmins[index],
                    "xmax": xmaxs[index],
                    "ymin": ymins[index],
                    "ymax": ymaxs[index],
                    "lod": lods[index],
                    "uri": uri,
                    "file": repository_path(path),
                    **info,
                }
            )

    chosen = {
        gml_id: max(items, key=lambda item: (item["depth"], item["leaf"]))
        for gml_id, items in occurrences.items()
    }
    attr_mismatch = sum(
        1
        for items in occurrences.values()
        if len({json.dumps(item["attrs"], sort_keys=True) for item in items}) > 1
    )
    coordinate_mismatch = sum(
        1
        for items in occurrences.values()
        if len({(round(item["x"], 12), round(item["y"], 12)) for item in items}) > 1
    )
    occurrence_histogram = Counter(len(items) for items in occurrences.values())
    return {
        "directory": repository_path(directory),
        "tileset_bytes": (directory / "tileset.json").stat().st_size,
        "b3dm_files": len(batch_lengths),
        "b3dm_bytes": sum(path.stat().st_size for path in (directory / "data").glob("*.b3dm")),
        "batch_instances": instance_count,
        "unique_buildings": len(occurrences),
        "duplicate_instances": instance_count - len(occurrences),
        "occurrence_histogram": dict(sorted(occurrence_histogram.items())),
        "max_occurrences_per_building": max(occurrence_histogram),
        "attribute_mismatch_across_duplicates": attr_mismatch,
        "coordinate_mismatch_across_duplicates": coordinate_mismatch,
        "batch_table_keys": sorted(all_keys),
        "records": chosen,
    }


def top10_bounds() -> list[dict]:
    result = []
    with TOP10_CSV.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            lon = float(row["centroid_lon"])
            lat = float(row["centroid_lat"])
            result.append(
                {
                    "rank": int(row["rank"]),
                    "mesh_code": row["mesh_code"],
                    "population": int(row["population"]),
                    "elderly_population": int(float(row["elderly_population"])),
                    "west": lon - 0.003125,
                    "east": lon + 0.003125,
                    "south": lat - (1 / 480),
                    "north": lat + (1 / 480),
                }
            )
    return result


def containing_top_mesh(record: dict, bounds: list[dict]) -> dict | None:
    for mesh in bounds:
        if (
            mesh["west"] <= record["x"] < mesh["east"]
            and mesh["south"] <= record["y"] < mesh["north"]
        ):
            return mesh
    return None


def bbox_intersects_mesh(record: dict, mesh: dict) -> bool:
    return not (
        record["xmax"] < mesh["west"]
        or record["xmin"] > mesh["east"]
        or record["ymax"] < mesh["south"]
        or record["ymin"] > mesh["north"]
    )


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1r, lat1r, lon2r, lat2r = map(math.radians, (lon1, lat1, lon2, lat2))
    dlon = lon2r - lon1r
    dlat = lat2r - lat1r
    term = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(math.sqrt(term))


def point_to_mesh_distance_m(lon: float, lat: float, mesh: dict) -> float:
    near_lon = min(max(lon, mesh["west"]), mesh["east"])
    near_lat = min(max(lat, mesh["south"]), mesh["north"])
    return haversine_m(lon, lat, near_lon, near_lat)


def bbox_to_mesh_distance_m(record: dict, mesh: dict) -> float:
    if record["xmax"] < mesh["west"]:
        lon1, lon2 = record["xmax"], mesh["west"]
    elif record["xmin"] > mesh["east"]:
        lon1, lon2 = record["xmin"], mesh["east"]
    else:
        lon1 = lon2 = max(record["xmin"], mesh["west"])
    if record["ymax"] < mesh["south"]:
        lat1, lat2 = record["ymax"], mesh["south"]
    elif record["ymin"] > mesh["north"]:
        lat1, lat2 = record["ymin"], mesh["north"]
    else:
        lat1 = lat2 = max(record["ymin"], mesh["south"])
    return haversine_m(lon1, lat1, lon2, lat2)


def nearest_building_summary(records: list[dict], mesh: dict) -> dict:
    center_nearest = min(
        records,
        key=lambda record: point_to_mesh_distance_m(record["x"], record["y"], mesh),
    )
    bbox_nearest = min(records, key=lambda record: bbox_to_mesh_distance_m(record, mesh))
    centroid_nearest = min(
        records,
        key=lambda record: haversine_m(
            record["x"],
            record["y"],
            (mesh["west"] + mesh["east"]) / 2,
            (mesh["south"] + mesh["north"]) / 2,
        ),
    )

    def identify(record: dict) -> dict:
        return {
            "gml_id": record["gml_id"],
            "lon": record["x"],
            "lat": record["y"],
            "source_third_mesh": str(record["attrs"].get("meshcode")),
            "usage": record["attrs"].get("bldg:usage"),
        }

    return {
        "building_centers_inside": sum(
            1 for record in records if containing_top_mesh(record, [mesh])
        ),
        "building_bboxes_intersecting": sum(
            1 for record in records if bbox_intersects_mesh(record, mesh)
        ),
        "nearest_from_mesh_boundary_to_building_center_m": round(
            point_to_mesh_distance_m(center_nearest["x"], center_nearest["y"], mesh), 3
        ),
        "nearest_building_center": identify(center_nearest),
        "nearest_from_mesh_boundary_to_building_bbox_m": round(
            bbox_to_mesh_distance_m(bbox_nearest, mesh), 3
        ),
        "nearest_building_bbox": identify(bbox_nearest),
        "nearest_from_mesh_centroid_to_building_center_m": round(
            haversine_m(
                centroid_nearest["x"],
                centroid_nearest["y"],
                (mesh["west"] + mesh["east"]) / 2,
                (mesh["south"] + mesh["north"]) / 2,
            ),
            3,
        ),
        "nearest_to_centroid_building": identify(centroid_nearest),
    }


def first_dict(value) -> dict:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def valid_number(value, *, allow_zero: bool = False) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if not math.isfinite(value) or value in {-9999, 9999}:
        return False
    return value >= 0 if allow_zero else value > 0


def summarize(records: list[dict]) -> dict:
    total = len(records)
    usage = []
    measured_height = []
    storeys_above = []
    storeys_below = []
    footprint = []
    total_floor_area = []
    height_types = []
    geometry_src_lod2 = []
    lods = []
    classes = []

    for record in records:
        attrs = record["attrs"]
        detail = first_dict(attrs.get("uro:BuildingDetailAttribute"))
        quality = first_dict(attrs.get("uro:DataQualityAttribute"))
        usage.append(attrs.get("bldg:usage"))
        measured_height.append(attrs.get("bldg:measuredHeight"))
        storeys_above.append(attrs.get("bldg:storeysAboveGround"))
        storeys_below.append(attrs.get("bldg:storeysBelowGround"))
        footprint.append(detail.get("uro:buildingFootprintArea"))
        total_floor_area.append(detail.get("uro:totalFloorArea"))
        height_types.append(quality.get("uro:lod1HeightType"))
        geometry_src_lod2.append(quality.get("uro:geometrySrcDescLod2"))
        lods.append(record["lod"])
        classes.append(attrs.get("bldg:class"))

    def values_summary(values, allow_zero=False):
        known = [value for value in values if valid_number(value, allow_zero=allow_zero)]
        return {
            "known": len(known),
            "missing_or_sentinel": total - len(known),
            "completeness_percent": round(100 * len(known) / total, 3) if total else None,
            "min": min(known) if known else None,
            "median": statistics.median(known) if known else None,
            "max": max(known) if known else None,
        }

    usage_populated = [value for value in usage if value not in {None, ""}]
    usage_known = [value for value in usage_populated if value != "不明"]
    lod2_real = [
        value
        for value in geometry_src_lod2
        if value not in {None, "", "未使用", "未作成"}
    ]
    return {
        "buildings": total,
        "usage": {
            "populated_including_unknown": len(usage_populated),
            "known_excluding_unknown": len(usage_known),
            "known_percent": round(100 * len(usage_known) / total, 3) if total else None,
            "values": dict(Counter(usage).most_common()),
        },
        "measured_height_m": values_summary(measured_height),
        "storeys_above_ground": values_summary(storeys_above, allow_zero=True),
        "storeys_below_ground": values_summary(storeys_below, allow_zero=True),
        "building_footprint_area_m2": values_summary(footprint),
        "total_floor_area_m2": values_summary(total_floor_area),
        "lod1_height_type": dict(Counter(height_types).most_common()),
        "lod2_source_populated": len(lod2_real),
        "lod2_source_percent": round(100 * len(lod2_real) / total, 3) if total else None,
        "geometry_lod_in_3dtiles": dict(Counter(lods).most_common()),
        "building_class": dict(Counter(classes).most_common()),
    }


def compact(parsed: dict) -> dict:
    return {key: value for key, value in parsed.items() if key != "records"}


def build_report() -> dict:
    parsed = {name: parse_directory(path) for name, path in LOD_DIRS.items()}
    bounds = top10_bounds()
    lod1_records = list(parsed["lod1"]["records"].values())
    lod2_records = list(parsed["lod2"]["records"].values())

    top_records = []
    by_mesh = defaultdict(list)
    for record in lod1_records:
        mesh = containing_top_mesh(record, bounds)
        if mesh:
            top_records.append(record)
            by_mesh[mesh["mesh_code"]].append(record)

    top_lod2_records = []
    for record in lod2_records:
        if containing_top_mesh(record, bounds):
            top_lod2_records.append(record)

    files = sorted({record["file"] for record in top_records})
    deepest_files = {
        record["uri"]: record["depth"] for record in top_records
    }
    return {
        "input": {
            "top10_csv": repository_path(TOP10_CSV),
            "top10_meshes": bounds,
        },
        "lod1_container": compact(parsed["lod1"]),
        "lod2_container": compact(parsed["lod2"]),
        "lod1_unique_ids_equal_lod2": set(parsed["lod1"]["records"])
        == set(parsed["lod2"]["records"]),
        "whole_city_lod1_attributes": summarize(lod1_records),
        "whole_city_lod2_attributes": summarize(lod2_records),
        "top10_lod1_attributes": summarize(top_records),
        "top10_lod2_attributes": summarize(top_lod2_records),
        "top10_by_mesh": [
            {
                **mesh,
                "attribute_summary": summarize(by_mesh[mesh["mesh_code"]]),
                "coverage_distance": nearest_building_summary(lod1_records, mesh),
                "third_mesh_codes": sorted(
                    {
                        str(record["attrs"].get("meshcode"))
                        for record in by_mesh[mesh["mesh_code"]]
                    }
                ),
            }
            for mesh in bounds
        ],
        "top10_deepest_b3dm_files": {
            "count": len(files),
            "bytes": sum((ROOT / path).stat().st_size for path in files),
            "paths": files,
            "depths": dict(Counter(deepest_files.values())),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    output = args.output.absolute()
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise ValueError("Inspection output must be a regular file, not a symlink")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    try:
        display_path = output.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        display_path = str(output)
    print(
        json.dumps(
            {"output": display_path, "bytes": output.stat().st_size},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
