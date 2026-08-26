"""Stream PLATEAU context features without inventing thematic attributes.

The Maizuru package stores land use, urban-planning and hazard geometries as
LOD1 multi-surfaces.  Flood and tsunami features can contain many thousands of
triangles, so this reader retains only the current CityGML feature and unions
surface chunks before yielding it.  Attribute values retain their XML path,
codeSpace, unit and source-member lineage; official labels are resolved only
from dictionaries shipped in the same PLATEAU archive.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

import geopandas as gpd
from shapely import coverage_union_all, union_all
from shapely.errors import GEOSException
from shapely.geometry import Polygon

GML_ID = "{http://www.opengis.net/gml}id"
LOD_PATTERN = re.compile(r"^lod([0-4])", re.IGNORECASE)
GEOMETRY_LEAVES = {"pos", "posList", "coordinates", "lowerCorner", "upperCorner"}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ring_coordinates(text: str, dimension: int) -> list[tuple[float, float]] | None:
    values = [float(value) for value in text.replace(",", " ").split()]
    if dimension not in {2, 3} or len(values) < dimension * 4 or len(values) % dimension:
        return None
    # EPSG:6697 in the source package is encoded as latitude, longitude, height.
    return [(values[index + 1], values[index]) for index in range(0, len(values), dimension)]


def _safe_union(geometries: list[Any], *, coverage: bool) -> Any | None:
    usable = [geometry for geometry in geometries if geometry is not None and not geometry.is_empty]
    if not usable:
        return None
    if len(usable) == 1:
        return usable[0]
    if coverage:
        try:
            result = coverage_union_all(usable)
            if result is not None and not result.is_empty and result.is_valid:
                return result
        except GEOSException:
            # Some official features contain overlapping source faces and are not a
            # strict coverage. The robust union below retains those geometries.
            result = None
    result = union_all(usable)
    return result if result is not None and not result.is_empty else None


def _append_attribute(current: dict[str, Any], path: str, element: ET.Element) -> None:
    value = (element.text or "").strip()
    name = local_name(element.tag)
    if not value or name in GEOMETRY_LEAVES:
        return
    item = {"path": path, "value": value}
    if code_space := element.get("codeSpace"):
        item["code_space"] = code_space
    if unit := element.get("uom"):
        item["unit"] = unit
    current["attributes"].setdefault(name, []).append(item)


def iter_lod1_polygon_features(
    stream: BinaryIO,
    *,
    source_member: str,
    source_member_crc32: str,
    feature_types: set[str] | None = None,
    coverage_geometry: bool = False,
    union_chunk_size: int = 20_000,
) -> Iterator[dict[str, Any]]:
    """Yield top-level CityGML features with one 2D LOD1 geometry each."""

    stack: list[str] = []
    dimensions: list[int] = []
    current: dict[str, Any] | None = None
    active_lod: int | None = None
    polygon_depth: int | None = None
    polygon_exterior: list[tuple[float, float]] | None = None
    polygon_interiors: list[list[tuple[float, float]]] = []

    for event, element in ET.iterparse(stream, events=("start", "end")):
        name = local_name(element.tag)
        if event == "start":
            parent = stack[-1] if stack else None
            stack.append(name)
            inherited_dimension = dimensions[-1] if dimensions else 3
            dimensions.append(int(element.get("srsDimension", inherited_dimension)))

            lod_match = LOD_PATTERN.match(name)
            if lod_match:
                active_lod = int(lod_match.group(1))

            gml_id = element.get(GML_ID)
            if (
                parent == "cityObjectMember"
                and gml_id
                and (feature_types is None or name in feature_types)
            ):
                current = {
                    "depth": len(stack),
                    "gml_id": gml_id,
                    "feature_type": name,
                    "source_gml": source_member,
                    "source_member_crc32": source_member_crc32,
                    "attributes": {},
                    "surface_parts": [],
                    "union_chunks": [],
                    "surface_part_count": 0,
                }
            elif current is not None and name == "Polygon" and active_lod == 1:
                polygon_depth = len(stack)
                polygon_exterior = None
                polygon_interiors = []
            continue

        if current is not None:
            text = (element.text or "").strip()
            if name == "posList" and text and polygon_depth is not None:
                coordinates = _ring_coordinates(text, dimensions[-1])
                if coordinates is not None:
                    if "interior" in stack[polygon_depth:]:
                        polygon_interiors.append(coordinates)
                    else:
                        polygon_exterior = coordinates
            elif len(stack) > current["depth"]:
                relative_path = "/".join(stack[current["depth"] :])
                _append_attribute(current, relative_path, element)

            if name == "Polygon" and len(stack) == polygon_depth:
                if polygon_exterior is not None:
                    polygon = Polygon(polygon_exterior, polygon_interiors)
                    if not polygon.is_empty and polygon.area > 0:
                        if not polygon.is_valid:
                            polygon = polygon.buffer(0)
                        if not polygon.is_empty and polygon.is_valid:
                            current["surface_parts"].append(polygon)
                            current["surface_part_count"] += 1
                if len(current["surface_parts"]) >= union_chunk_size:
                    chunk = _safe_union(current["surface_parts"], coverage=coverage_geometry)
                    if chunk is not None:
                        current["union_chunks"].append(chunk)
                    current["surface_parts"] = []
                polygon_depth = None
                polygon_exterior = None
                polygon_interiors = []

            if len(stack) == current["depth"]:
                chunks = current["union_chunks"] + current["surface_parts"]
                geometry = _safe_union(chunks, coverage=coverage_geometry)
                yield {
                    key: value
                    for key, value in current.items()
                    if key not in {"depth", "surface_parts", "union_chunks"}
                } | {"geometry": geometry}
                current = None

        element.clear()
        ended = stack.pop()
        dimensions.pop()
        if LOD_PATTERN.match(ended):
            active_lod = next(
                (
                    int(match.group(1))
                    for ancestor in reversed(stack)
                    if (match := LOD_PATTERN.match(ancestor))
                ),
                None,
            )


def read_theme_features(
    archive_path: str | Path,
    theme: str,
    *,
    feature_types: set[str] | None = None,
    coverage_geometry: bool = False,
) -> gpd.GeoDataFrame:
    """Read every GML member of one theme in deterministic member order."""

    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = sorted(
            (
                info
                for info in archive.infolist()
                if f"/udx/{theme}/" in "/" + info.filename and info.filename.endswith(".gml")
            ),
            key=lambda info: info.filename,
        )
        for info in members:
            with archive.open(info) as stream:
                records.extend(
                    iter_lod1_polygon_features(
                        stream,
                        source_member=info.filename,
                        source_member_crc32=f"{info.CRC:08x}",
                        feature_types=feature_types,
                        coverage_geometry=coverage_geometry,
                    )
                )
    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


@dataclass(frozen=True)
class OfficialCode:
    code: str
    label: str
    codelist: str


class PackageCodelists:
    """Resolve only package-local PLATEAU GML dictionaries by basename."""

    def __init__(self, archive_path: str | Path):
        self.archive_path = Path(archive_path)
        self._member_by_name: dict[str, str] = {}
        self._cache: dict[str, dict[str, str]] = {}
        with zipfile.ZipFile(self.archive_path) as archive:
            for name in sorted(archive.namelist(), key=lambda item: (len(item), item)):
                if "/codelists/" in "/" + name and name.endswith(".xml"):
                    self._member_by_name.setdefault(PurePosixPath(name).name, name)

    def dictionary(self, code_space: str) -> dict[str, str]:
        basename = PurePosixPath(code_space).name
        if basename in self._cache:
            return self._cache[basename]
        member = self._member_by_name.get(basename)
        if member is None:
            self._cache[basename] = {}
            return self._cache[basename]
        with zipfile.ZipFile(self.archive_path) as archive:
            root = ET.parse(archive.open(member)).getroot()
        result: dict[str, str] = {}
        for definition in root.iter():
            if local_name(definition.tag) != "Definition":
                continue
            children = {local_name(child.tag): (child.text or "").strip() for child in definition}
            code = children.get("name")
            if code:
                result[code] = children.get("description", "")
        self._cache[basename] = result
        return result

    def resolve(self, code: str | None, code_space: str | None) -> OfficialCode | None:
        if not code or not code_space:
            return None
        basename = PurePosixPath(code_space).name
        label = self.dictionary(code_space).get(code)
        if label is None:
            return None
        return OfficialCode(code=code, label=label, codelist=basename)


def first_attribute(record: dict[str, Any] | Any, name: str) -> dict[str, str] | None:
    """Return the first actual XML value for a local attribute name."""

    attributes = record["attributes"] if isinstance(record, dict) else record.attributes
    values = attributes.get(name, [])
    return values[0] if values else None


def resolved_attribute(
    record: dict[str, Any] | Any, name: str, codelists: PackageCodelists
) -> dict[str, str] | None:
    item = first_attribute(record, name)
    if item is None:
        return None
    result = dict(item)
    resolved = codelists.resolve(item.get("value"), item.get("code_space"))
    if resolved is not None:
        result["official_label"] = resolved.label
        result["codelist"] = resolved.codelist
    return result
