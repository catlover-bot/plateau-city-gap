"""Stream actual PLATEAU building attributes and footprint geometry from CityGML."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

import geopandas as gpd
from shapely import union_all
from shapely.geometry import Polygon

GML_ID = "{http://www.opengis.net/gml}id"
LOD_PATTERN = re.compile(r"^lod([0-4])", re.IGNORECASE)
BUILDING_ATTRIBUTES = (
    "usage",
    "totalFloorArea",
    "buildingFootprintArea",
    "measuredHeight",
    "storeysAboveGround",
    "storeysBelowGround",
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ring_coordinates(text: str, dimension: int = 3) -> list[tuple[float, float]] | None:
    values = [float(value) for value in text.replace(",", " ").split()]
    if len(values) < dimension * 4 or len(values) % dimension:
        return None
    coordinates = [
        (values[index + 1], values[index]) for index in range(0, len(values), dimension)
    ]
    return coordinates


def _footprint(current: dict) -> tuple[object | None, str | None]:
    # Maizuru has LOD0 roof-edge geometry rather than bldg:lod0FootPrint. Its 2D
    # projection is preferred; the LOD1 solid projection is a documented fallback.
    for key, source in (("lod0", "lod0_roof_edge_projection"), ("lod1", "lod1_solid_projection")):
        polygons = current[key]
        if polygons:
            geometry = union_all(polygons)
            if not geometry.is_empty and geometry.is_valid and geometry.area > 0:
                return geometry, source
    return None, None


def iter_buildings(
    stream: BinaryIO,
    *,
    source_member: str,
    source_member_crc32: str,
) -> Iterator[dict]:
    """Yield one record per top-level Building while retaining only one feature."""

    stack: list[str] = []
    current: dict | None = None
    active_lod: int | None = None
    polygon_depth: int | None = None
    polygon_lod: int | None = None
    polygon_exterior: list[tuple[float, float]] | None = None
    polygon_interiors: list[list[tuple[float, float]]] = []

    for event, element in ET.iterparse(stream, events=("start", "end")):
        local = _local_name(element.tag)
        if event == "start":
            parent = stack[-1] if stack else None
            stack.append(local)
            lod_match = LOD_PATTERN.match(local)
            if lod_match:
                active_lod = int(lod_match.group(1))
            if parent == "cityObjectMember" and local == "Building" and element.get(GML_ID):
                current = {
                    "depth": len(stack),
                    "gml_id": element.get(GML_ID),
                    "source_gml": source_member,
                    "source_member_crc32": source_member_crc32,
                    "lod0": [],
                    "lod1": [],
                    "units": {},
                    **{name: None for name in BUILDING_ATTRIBUTES},
                }
            elif current is not None and local == "Polygon" and active_lod in {0, 1}:
                polygon_depth = len(stack)
                polygon_lod = active_lod
                polygon_exterior = None
                polygon_interiors = []
            continue

        if current is not None:
            text = (element.text or "").strip()
            if local == "posList" and text and polygon_depth is not None:
                coordinates = _ring_coordinates(text)
                if coordinates is not None:
                    if "interior" in stack:
                        polygon_interiors.append(coordinates)
                    else:
                        polygon_exterior = coordinates
            elif local in BUILDING_ATTRIBUTES and text:
                current[local] = text
                if element.get("uom"):
                    current["units"][local] = element.get("uom")

            if local == "Polygon" and len(stack) == polygon_depth:
                if polygon_exterior is not None and polygon_lod is not None:
                    polygon = Polygon(polygon_exterior, polygon_interiors)
                    if not polygon.is_empty and polygon.is_valid and polygon.area > 0:
                        current[f"lod{polygon_lod}"].append(polygon)
                polygon_depth = None
                polygon_lod = None
                polygon_exterior = None
                polygon_interiors = []

            if len(stack) == current["depth"]:
                geometry, geometry_source = _footprint(current)
                yield {
                    key: value
                    for key, value in current.items()
                    if key not in {"depth", "lod0", "lod1"}
                } | {"geometry": geometry, "geometry_source": geometry_source}
                current = None

        element.clear()
        ended = stack.pop()
        if LOD_PATTERN.match(ended):
            active_lod = next(
                (
                    int(match.group(1))
                    for name in reversed(stack)
                    if (match := LOD_PATTERN.match(name))
                ),
                None,
            )


def read_buildings(archive_path: str | Path) -> gpd.GeoDataFrame:
    """Read all building members from a PLATEAU archive into a GeoDataFrame."""

    records: list[dict] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = sorted(
            (
                info
                for info in archive.infolist()
                if "/udx/bldg/" in "/" + info.filename and info.filename.endswith(".gml")
            ),
            key=lambda info: info.filename,
        )
        for info in members:
            with archive.open(info) as stream:
                records.extend(
                    iter_buildings(
                        stream,
                        source_member=info.filename,
                        source_member_crc32=f"{info.CRC:08x}",
                    )
                )
    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


def read_gml_dictionary(archive_path: str | Path, member: str) -> list[dict[str, str]]:
    """Read code/official-label pairs from a package-local GML Dictionary."""

    with zipfile.ZipFile(archive_path) as archive:
        root = ET.parse(archive.open(member)).getroot()
    rows = []
    for definition in root.iter():
        if _local_name(definition.tag) != "Definition":
            continue
        values = {_local_name(child.tag): (child.text or "").strip() for child in definition}
        if values.get("name"):
            rows.append({"usage_code": values["name"], "official_label": values.get("description", "")})
    return rows
