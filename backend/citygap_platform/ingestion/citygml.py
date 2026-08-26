"""Streaming, event-oriented CityGML reader.

The reader never retains a complete city object.  Geometry rings are emitted
as soon as they close, which also keeps large DEM/TIN features bounded in
memory.  Source coordinates are preserved in event metadata while emitted WKT
uses conventional GIS x/y order (longitude, latitude) for storage in EPSG:4326.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Literal

GML_ID = "{http://www.opengis.net/gml}id"
LOD_PATTERN = re.compile(r"^lod([0-4])", re.IGNORECASE)
COORDINATE_TAGS = frozenset({"coordinates", "pos", "posList"})
UNSAFE_XML_DECLARATIONS = (b"<!DOCTYPE", b"<!ENTITY")


def ensure_safe_xml_stream(stream: BinaryIO, inspection_bytes: int = 64 * 1024) -> None:
    """Reject entity declarations before handing a seekable stream to ElementTree."""

    if not stream.seekable():
        raise ValueError("CityGML input must be seekable for XML safety inspection")
    position = stream.tell()
    prefix = stream.read(inspection_bytes).upper()
    stream.seek(position)
    if any(declaration in prefix for declaration in UNSAFE_XML_DECLARATIONS):
        raise ValueError("CityGML DTD and entity declarations are prohibited")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass(frozen=True)
class FeatureStart:
    kind: Literal["feature_start"] = "feature_start"
    gml_id: str = ""
    feature_type: str = ""
    theme: str = ""
    source_member: str = ""
    source_member_crc32: str = ""


@dataclass(frozen=True)
class GeometryPart:
    kind: Literal["geometry_part"] = "geometry_part"
    role: str = "geometry"
    geometry_type: str = ""
    lod: int | None = None
    source_crs: str | None = None
    ewkt: str = ""


@dataclass(frozen=True)
class FeatureEnd:
    kind: Literal["feature_end"] = "feature_end"
    gml_id: str = ""
    lods: tuple[int, ...] = ()
    source_crs: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)


CityGMLEvent = FeatureStart | GeometryPart | FeatureEnd


def _coordinates(text: str, dimension: int) -> list[tuple[float, float, float | None]]:
    values = [float(value) for value in text.replace(",", " ").split()]
    if dimension not in (2, 3) or len(values) < dimension or len(values) % dimension:
        return []
    points: list[tuple[float, float, float | None]] = []
    for index in range(0, len(values), dimension):
        # PLATEAU EPSG:6697 GML follows CRS axis order: latitude, longitude, height.
        latitude, longitude = values[index : index + 2]
        height = values[index + 2] if dimension == 3 else None
        points.append((longitude, latitude, height))
    return points


def _point_text(point: tuple[float, float, float | None]) -> str:
    longitude, latitude, height = point
    if height is None:
        return f"{longitude:.12g} {latitude:.12g}"
    return f"{longitude:.12g} {latitude:.12g} {height:.12g}"


def _geometry_ewkt(points: list[tuple[float, float, float | None]], polygon: bool) -> str | None:
    if not points:
        return None
    has_z = points[0][2] is not None
    suffix = " Z" if has_z else ""
    coordinates = ", ".join(_point_text(point) for point in points)
    if polygon and len(points) >= 4 and points[0] == points[-1]:
        return f"SRID=4326;POLYGON{suffix}(({coordinates}))"
    if len(points) >= 2:
        return f"SRID=4326;LINESTRING{suffix}({coordinates})"
    return f"SRID=4326;POINT{suffix}({_point_text(points[0])})"


def _append_attribute(attributes: dict[str, Any], key: str, value: str) -> None:
    existing = attributes.get(key)
    if existing is None:
        attributes[key] = value
    elif isinstance(existing, list):
        if value not in existing:
            existing.append(value)
    elif existing != value:
        attributes[key] = [existing, value]


def _geometry_type(ewkt: str) -> str:
    return ewkt.split(";", 1)[1].split("(", 1)[0].removesuffix(" Z")


def iter_citygml_events(
    stream: BinaryIO,
    *,
    theme: str,
    source_member: str,
    source_member_crc32: str,
    coordinate_dimension: int = 3,
) -> Iterator[CityGMLEvent]:
    """Yield feature lifecycle and geometry events from one CityGML stream."""

    ensure_safe_xml_stream(stream)

    stack: list[str] = []
    current: dict | None = None
    coordinate_contexts: list[dict] = []
    active_lod: int | None = None

    for event, element in ET.iterparse(stream, events=("start", "end")):
        local = local_name(element.tag)
        if event == "start":
            parent = stack[-1] if stack else None
            stack.append(local)
            lod_match = LOD_PATTERN.match(local)
            if lod_match:
                active_lod = int(lod_match.group(1))

            gml_id = element.get(GML_ID)
            if parent == "cityObjectMember" and gml_id:
                current = {
                    "depth": len(stack),
                    "gml_id": gml_id,
                    "lods": set(),
                    "declared_lod": None,
                    "crs": set(),
                    "attributes": {},
                }
                yield FeatureStart(
                    gml_id=gml_id,
                    feature_type=local,
                    theme=theme,
                    source_member=source_member,
                    source_member_crc32=source_member_crc32,
                )

            if current is not None:
                if lod_match:
                    current["lods"].add(active_lod)
                srs_name = element.get("srsName")
                if srs_name:
                    current["crs"].add(srs_name)
                if local in {"LinearRing", "LineString"}:
                    coordinate_contexts.append(
                        {
                            "depth": len(stack),
                            "type": local,
                            "role": parent or "geometry",
                            "lod": active_lod if active_lod is not None else current["declared_lod"],
                            "crs": srs_name,
                            "points": [],
                        }
                    )
            continue

        if current is not None:
            text = (element.text or "").strip()
            if local == "lod" and text in {"0", "1", "2", "3", "4"}:
                current["declared_lod"] = int(text)
                current["lods"].add(int(text))
            if text and local in COORDINATE_TAGS:
                points = _coordinates(text, coordinate_dimension)
                if coordinate_contexts:
                    coordinate_contexts[-1]["points"].extend(points)
                elif points:
                    ewkt = _geometry_ewkt(points, polygon=False)
                    if ewkt:
                        yield GeometryPart(
                            role=stack[-2] if len(stack) > 1 else "geometry",
                            geometry_type=_geometry_type(ewkt),
                            lod=(
                                active_lod
                                if active_lod is not None
                                else current["declared_lod"]
                            ),
                            source_crs=next(iter(current["crs"]), None),
                            ewkt=ewkt,
                        )
            elif text and not list(element) and local not in COORDINATE_TAGS:
                _append_attribute(current["attributes"], local, text)
                metadata = {
                    local_name(key): value
                    for key, value in element.attrib.items()
                    if key != GML_ID
                }
                if metadata:
                    current["attributes"].setdefault("_xml_attributes", {}).setdefault(
                        local, []
                    ).append(metadata)

            if coordinate_contexts and len(stack) == coordinate_contexts[-1]["depth"]:
                context = coordinate_contexts.pop()
                ewkt = _geometry_ewkt(context["points"], polygon=context["type"] == "LinearRing")
                if ewkt:
                    yield GeometryPart(
                        role=context["role"],
                        geometry_type=_geometry_type(ewkt),
                        lod=context["lod"],
                        source_crs=context["crs"] or next(iter(current["crs"]), None),
                        ewkt=ewkt,
                    )

            if len(stack) == current["depth"]:
                yield FeatureEnd(
                    gml_id=current["gml_id"],
                    lods=tuple(sorted(current["lods"])),
                    source_crs=tuple(sorted(current["crs"])),
                    attributes=current["attributes"],
                )
                current = None
                coordinate_contexts.clear()

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
