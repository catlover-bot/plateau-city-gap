"""Memory-bounded inventory of a PLATEAU CityGML ZIP archive.

The inventory deliberately counts only features directly contained by a
``core:cityObjectMember``.  ADE objects nested inside a city object may also
have ``gml:id`` values, but they are not independent city objects and must not
inflate feature totals.
"""

from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path
from typing import BinaryIO

from backend.citygap_platform.ingestion.citygml import ensure_safe_xml_stream

GML_ID = "{http://www.opengis.net/gml}id"
LOD_PATTERN = re.compile(r"^lod([0-4])", re.IGNORECASE)
THEME_PATTERN = re.compile(r"/(?:udx|citygml)/([^/]+)/.+\.gml$", re.IGNORECASE)
GEOMETRY_ELEMENTS = frozenset(
    {
        "CompositeCurve",
        "CompositeSolid",
        "CompositeSurface",
        "Curve",
        "LineString",
        "MultiCurve",
        "MultiGeometry",
        "MultiPoint",
        "MultiSolid",
        "MultiSurface",
        "Point",
        "Polygon",
        "Solid",
        "Surface",
        "Triangle",
        "TriangulatedSurface",
    }
)
NON_ATTRIBUTE_LEAVES = frozenset(
    {
        "coordinates",
        "lowerCorner",
        "pos",
        "posList",
        "upperCorner",
    }
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str | None:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return None


def _sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_theme_stats() -> dict:
    return {
        "file_count": 0,
        "compressed_bytes": 0,
        "uncompressed_bytes": 0,
        "feature_count": 0,
        "feature_types": Counter(),
        "lod_feature_counts": Counter(),
        "geometry_feature_counts": Counter(),
        "attribute_feature_counts": Counter(),
        "crs_names": Counter(),
        "namespace_uris": set(),
        "duplicate_gml_id_count": 0,
        "parse_seconds": 0.0,
    }


def _inventory_stream(
    stream: BinaryIO,
    stats: dict,
    seen_gml_ids: set[str],
    member_name: str,
) -> None:
    ensure_safe_xml_stream(stream)
    stack: list[str] = []
    current: dict | None = None

    for event, element in ET.iterparse(stream, events=("start", "end")):
        local = _local_name(element.tag)
        if event == "start":
            parent = stack[-1] if stack else None
            stack.append(local)
            namespace = _namespace(element.tag)
            if namespace:
                stats["namespace_uris"].add(namespace)

            if parent == "cityObjectMember" and element.get(GML_ID):
                gml_id = element.get(GML_ID)
                duplicate = gml_id in seen_gml_ids
                if duplicate:
                    stats["duplicate_gml_id_count"] += 1
                else:
                    seen_gml_ids.add(gml_id)
                current = {
                    "depth": len(stack),
                    "gml_id": gml_id,
                    "feature_type": local,
                    "lods": set(),
                    "geometries": set(),
                    "attributes": set(),
                    "crs": set(),
                    "member": member_name,
                }

            if current is not None:
                lod_match = LOD_PATTERN.match(local)
                if lod_match:
                    current["lods"].add(int(lod_match.group(1)))
                if local in GEOMETRY_ELEMENTS:
                    current["geometries"].add(local)
                srs_name = element.get("srsName")
                if srs_name:
                    current["crs"].add(srs_name)
            continue

        if current is not None:
            text = (element.text or "").strip()
            if local == "lod" and text in {"0", "1", "2", "3", "4"}:
                current["lods"].add(int(text))
            if not list(element) and text and local not in NON_ATTRIBUTE_LEAVES:
                current["attributes"].add(local)

            if len(stack) == current["depth"]:
                stats["feature_count"] += 1
                stats["feature_types"][current["feature_type"]] += 1
                stats["lod_feature_counts"].update(current["lods"])
                stats["geometry_feature_counts"].update(current["geometries"])
                stats["attribute_feature_counts"].update(current["attributes"])
                stats["crs_names"].update(current["crs"])
                current = None

        element.clear()
        stack.pop()


def _serialise_stats(stats: dict) -> dict:
    def sorted_counter(counter: Counter) -> dict[str, int]:
        return {str(key): value for key, value in sorted(counter.items(), key=lambda item: str(item[0]))}

    return {
        "file_count": stats["file_count"],
        "compressed_bytes": stats["compressed_bytes"],
        "uncompressed_bytes": stats["uncompressed_bytes"],
        "feature_count": stats["feature_count"],
        "feature_types": sorted_counter(stats["feature_types"]),
        "lod_feature_counts": sorted_counter(stats["lod_feature_counts"]),
        "geometry_feature_counts": sorted_counter(stats["geometry_feature_counts"]),
        "attribute_feature_counts": sorted_counter(stats["attribute_feature_counts"]),
        "crs_names": sorted_counter(stats["crs_names"]),
        "namespace_uris": sorted(stats["namespace_uris"]),
        "duplicate_gml_id_count": stats["duplicate_gml_id_count"],
        "parse_seconds": round(stats["parse_seconds"], 3),
    }


def build_archive_inventory(
    archive_path: str | Path,
    *,
    city_id: str,
    dataset_year: int,
    product_specification_version: str,
    ade_schema_version: str | None = None,
) -> dict:
    """Stream every CityGML member and return a deterministic inventory.

    Peak memory is bounded by the largest single XML element being processed;
    completed elements are cleared immediately.  The archive is never
    extracted to disk.
    """

    archive = Path(archive_path)
    started = time.perf_counter()
    themes: dict[str, dict] = {}
    seen_gml_ids: set[str] = set()
    members: list[dict] = []

    with zipfile.ZipFile(archive) as citygml_zip:
        all_infos = citygml_zip.infolist()
        for info in all_infos:
            normalized_name = "/" + info.filename.replace("\\", "/")
            match = THEME_PATTERN.search(normalized_name)
            if not match:
                continue
            theme = match.group(1).lower()
            stats = themes.setdefault(theme, _new_theme_stats())
            stats["file_count"] += 1
            stats["compressed_bytes"] += info.compress_size
            stats["uncompressed_bytes"] += info.file_size
            member_started = time.perf_counter()
            with citygml_zip.open(info) as stream:
                _inventory_stream(stream, stats, seen_gml_ids, info.filename)
            member_seconds = time.perf_counter() - member_started
            stats["parse_seconds"] += member_seconds
            members.append(
                {
                    "path": info.filename,
                    "theme": theme,
                    "crc32": f"{info.CRC:08x}",
                    "compressed_bytes": info.compress_size,
                    "uncompressed_bytes": info.file_size,
                    "parse_seconds": round(member_seconds, 3),
                }
            )

        archive_file_count = len(all_infos)
        archive_uncompressed_bytes = sum(info.file_size for info in all_infos)
        archive_compressed_member_bytes = sum(info.compress_size for info in all_infos)

    serialised_themes = {name: _serialise_stats(themes[name]) for name in sorted(themes)}
    return {
        "schema_version": 1,
        "parser": {
            "mode": "zip-stream+xml-etree-iterparse",
            "feature_boundary": "direct child of core:cityObjectMember",
            "geometry_materialized": False,
        },
        "dataset": {
            "city_id": city_id,
            "dataset_year": dataset_year,
            "product_specification_version": product_specification_version,
            "ade_schema_version": ade_schema_version,
        },
        "archive": {
            "file_name": archive.name,
            "sha256": _sha256(archive),
            "size_bytes": archive.stat().st_size,
            "zip_file_count": archive_file_count,
            "zip_member_compressed_bytes": archive_compressed_member_bytes,
            "uncompressed_bytes": archive_uncompressed_bytes,
            "citygml_file_count": sum(theme["file_count"] for theme in serialised_themes.values()),
        },
        "totals": {
            "feature_count": sum(theme["feature_count"] for theme in serialised_themes.values()),
            "duplicate_gml_id_count": sum(
                theme["duplicate_gml_id_count"] for theme in serialised_themes.values()
            ),
            "unique_gml_id_count": len(seen_gml_ids),
            "parse_seconds": round(time.perf_counter() - started, 3),
        },
        "themes": serialised_themes,
        "members": sorted(members, key=lambda item: item["path"]),
    }
