"""Deterministic PLATEAU TIN cross-section primitives.

Sampling is performed in a local projected CRS and uses barycentric
interpolation inside source triangles. No terrain, height or coverage is
invented when the transect leaves the TIN.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import transform
from shapely.strtree import STRtree


@dataclass(frozen=True, slots=True)
class TerrainTriangle:
    triangle_id: str
    coordinates: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]


@dataclass(frozen=True, slots=True)
class TerrainSample:
    sample_order: int
    distance_m: float
    longitude: float
    latitude: float
    elevation_m: float | None
    source_triangle_id: str | None
    quality: str


def sample_tin_transect(
    line_coordinates: list[list[float]] | tuple[tuple[float, float], ...],
    triangles: Iterable[TerrainTriangle],
    *,
    sample_interval_m: float = 5.0,
    projected_crs: str = "EPSG:6674",
) -> list[TerrainSample]:
    """Sample an exact TIN along a line and retain source-triangle lineage."""

    if sample_interval_m <= 0 or not math.isfinite(sample_interval_m):
        raise ValueError("sample_interval_m must be a positive finite distance")
    forward = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True).transform
    reverse = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True).transform
    line = transform(forward, LineString(line_coordinates))
    if line.is_empty or line.length <= 0:
        raise ValueError("transect must have a positive length")

    records = list(triangles)
    valid_records: list[TerrainTriangle] = []
    polygons: list[Polygon] = []
    projected_vertices: list[tuple[tuple[float, float, float], ...]] = []
    for record in records:
        projected = tuple((*forward(lon, lat), elevation) for lon, lat, elevation in record.coordinates)
        polygon = Polygon([(x, y) for x, y, _ in projected])
        if polygon.is_valid and polygon.area > 1e-8:
            valid_records.append(record)
            polygons.append(polygon)
            projected_vertices.append(projected)
    tree = STRtree(polygons)

    distances = [min(index * sample_interval_m, line.length) for index in range(math.ceil(line.length / sample_interval_m) + 1)]
    if distances[-1] < line.length:
        distances.append(line.length)
    result: list[TerrainSample] = []
    for order, distance in enumerate(distances):
        point = line.interpolate(distance)
        lon, lat = reverse(point.x, point.y)
        candidates = tree.query(point, predicate="intersects")
        if len(candidates) == 0:
            result.append(TerrainSample(order, distance, lon, lat, None, None, "no_coverage"))
            continue
        # Shared TIN edges may return two triangles. Sort by durable triangle ID
        # so the same input is byte-for-byte reproducible.
        candidate_indexes = sorted(
            (int(index) for index in candidates),
            key=lambda index: valid_records[index].triangle_id,
        )
        selected = candidate_indexes[0]
        elevation = _barycentric_height(point.x, point.y, projected_vertices[selected])
        quality = "boundary" if polygons[selected].boundary.distance(point) <= 1e-7 else "direct_tin"
        result.append(
            TerrainSample(
                order,
                distance,
                lon,
                lat,
                elevation,
                valid_records[selected].triangle_id,
                quality,
            )
        )
    return result


def section_relations(
    line_coordinates: list[list[float]],
    objects: Iterable[dict[str, Any]],
    *,
    buffer_m: float,
    projected_crs: str = "EPSG:6674",
) -> list[dict[str, Any]]:
    """Relate actual objects to a transect as direct intersections or nearby."""

    forward = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True).transform
    line = transform(forward, LineString(line_coordinates))
    nearby_area = line if buffer_m == 0 else line.buffer(buffer_m)
    relations: list[dict[str, Any]] = []
    for item in objects:
        geometry = transform(forward, shape(item["geometry"]))
        if geometry.is_empty or not nearby_area.intersects(geometry):
            continue
        direct = line.intersects(geometry)
        projected_start, projected_end = _distance_range(line, geometry)
        relations.append(
            {
                "source_object_id": str(item["id"]),
                "relation": "direct" if direct else "nearby",
                "start_distance_m": round(projected_start, 3),
                "end_distance_m": round(projected_end, 3),
                "offset_distance_m": round(line.distance(geometry), 3),
                "properties": item.get("properties", {}),
            }
        )
    return sorted(relations, key=lambda item: (item["start_distance_m"], item["source_object_id"]))


def _distance_range(line: LineString, geometry: Any) -> tuple[float, float]:
    intersection = line.intersection(geometry)
    target = intersection if not intersection.is_empty else geometry
    coordinates: list[tuple[float, float]] = []
    if hasattr(target, "geoms"):
        for part in target.geoms:
            coordinates.extend(_coordinates(part))
    else:
        coordinates.extend(_coordinates(target))
    if not coordinates:
        nearest = line.interpolate(line.project(geometry.centroid))
        coordinates = [(nearest.x, nearest.y)]
    distances = [line.project(Point(x, y)) for x, y in coordinates]
    return min(distances), max(distances)


def _coordinates(geometry: Any) -> list[tuple[float, float]]:
    if hasattr(geometry, "exterior") and geometry.exterior is not None:
        return list(geometry.exterior.coords)
    if hasattr(geometry, "coords"):
        return list(geometry.coords)
    return []


def _barycentric_height(
    x: float,
    y: float,
    vertices: tuple[tuple[float, float, float], ...],
) -> float:
    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = vertices
    denominator = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(denominator) <= 1e-12:
        raise ValueError("Degenerate source TIN triangle")
    first = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / denominator
    second = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / denominator
    third = 1.0 - first - second
    return first * z1 + second * z2 + third * z3
