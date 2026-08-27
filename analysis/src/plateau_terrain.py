"""Stream PLATEAU DEM TIN elevation onto a versioned road graph."""

from __future__ import annotations

import math
import re
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO

import geopandas as gpd
import numpy as np
import pandas as pd

DEM_ELEVATION_METHOD = "plateau_dem_lod1_tin_barycentric_interpolation"
GRID_CELL_DEGREES = 0.001
LOWER_CORNER = re.compile(rb"<gml:lowerCorner>([^<]+)</gml:lowerCorner>")
UPPER_CORNER = re.compile(rb"<gml:upperCorner>([^<]+)</gml:upperCorner>")


def iter_dem_triangles(
    stream: BinaryIO,
) -> Iterable[tuple[int, tuple[tuple[float, float, float], ...]]]:
    """Yield the first three unique vertices of each PLATEAU DEM triangle."""

    start_tag = b"<gml:posList>"
    end_tag = b"</gml:posList>"
    buffer = b""
    triangle_index = 0
    finished = False
    while not finished:
        chunk = stream.read(1024 * 1024)
        if chunk:
            buffer += chunk
        else:
            finished = True
        while True:
            start = buffer.find(start_tag)
            if start < 0:
                if len(buffer) > len(start_tag):
                    buffer = buffer[-len(start_tag) :]
                break
            end = buffer.find(end_tag, start + len(start_tag))
            if end < 0:
                buffer = buffer[start:]
                break
            text = buffer[start + len(start_tag) : end]
            buffer = buffer[end + len(end_tag) :]
            values = [float(value) for value in text.split()]
            current_index = triangle_index
            triangle_index += 1
            if len(values) < 12 or len(values) % 3:
                continue
            points = tuple(
                (values[offset + 1], values[offset], values[offset + 2])
                for offset in range(0, 9, 3)
            )
            yield current_index, points


def _member_envelope(stream: BinaryIO) -> tuple[float, float, float, float]:
    head = stream.read(128_000)
    lower_match = LOWER_CORNER.search(head)
    upper_match = UPPER_CORNER.search(head)
    if lower_match is None or upper_match is None:
        raise ValueError("DEM member does not declare a readable GML envelope")
    lower = [float(value) for value in lower_match.group(1).split()]
    upper = [float(value) for value in upper_match.group(1).split()]
    if len(lower) < 2 or len(upper) < 2:
        raise ValueError("DEM envelope has fewer than two coordinate dimensions")
    return lower[1], lower[0], upper[1], upper[0]


def _barycentric_elevation(
    longitude: float,
    latitude: float,
    triangle: tuple[tuple[float, float, float], ...],
    *,
    weight_tolerance: float = 1e-8,
) -> float | None:
    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = triangle
    denominator = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(denominator) <= 1e-20:
        return None
    first = ((y2 - y3) * (longitude - x3) + (x3 - x2) * (latitude - y3)) / denominator
    second = ((y3 - y1) * (longitude - x3) + (x1 - x3) * (latitude - y3)) / denominator
    third = 1.0 - first - second
    if min(first, second, third) < -weight_tolerance:
        return None
    return first * z1 + second * z2 + third * z3


def assign_dem_elevations(
    archive_path: str | Path,
    nodes: gpd.GeoDataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Interpolate elevation for road nodes, streaming only relevant DEM members."""

    if nodes.crs is None or not nodes.crs.is_projected:
        raise ValueError("Road nodes must use a projected analysis CRS")
    if nodes["node_id"].duplicated().any():
        raise ValueError("Road node IDs must be unique")
    geographic = nodes[["node_id", "geometry"]].to_crs("EPSG:4326").reset_index(drop=True)
    longitudes = geographic.geometry.x.to_numpy()
    latitudes = geographic.geometry.y.to_numpy()
    elevations = np.full(len(geographic), np.nan)
    source_members: list[str | None] = [None] * len(geographic)
    source_crc32: list[str | None] = [None] * len(geographic)
    triangle_indices = np.full(len(geographic), -1, dtype=np.int64)
    member_reports: list[dict[str, Any]] = []

    with zipfile.ZipFile(archive_path) as archive:
        members = sorted(
            (
                info
                for info in archive.infolist()
                if info.filename.startswith("udx/dem/") and info.filename.endswith(".gml")
            ),
            key=lambda info: info.filename,
        )
        for info in members:
            with archive.open(info) as stream:
                west, south, east, north = _member_envelope(stream)
            missing = np.isnan(elevations)
            candidate_indices = np.flatnonzero(
                missing
                & (longitudes >= west - 1e-12)
                & (longitudes <= east + 1e-12)
                & (latitudes >= south - 1e-12)
                & (latitudes <= north + 1e-12)
            )
            if not len(candidate_indices):
                member_reports.append(
                    {
                        "source_member": info.filename,
                        "source_member_crc32": f"{info.CRC:08x}",
                        "candidate_nodes": 0,
                        "assigned_nodes": 0,
                        "triangles_scanned": 0,
                        "status": "skipped_no_unassigned_nodes_in_envelope",
                    }
                )
                continue

            buckets: dict[tuple[int, int], list[int]] = {}
            for index in candidate_indices:
                key = (
                    math.floor(longitudes[index] / GRID_CELL_DEGREES),
                    math.floor(latitudes[index] / GRID_CELL_DEGREES),
                )
                buckets.setdefault(key, []).append(int(index))
            unresolved = {int(index) for index in candidate_indices}
            triangles_scanned = 0
            with archive.open(info) as stream:
                for triangle_index, triangle in iter_dem_triangles(stream):
                    triangles_scanned += 1
                    minimum_x = min(point[0] for point in triangle)
                    maximum_x = max(point[0] for point in triangle)
                    minimum_y = min(point[1] for point in triangle)
                    maximum_y = max(point[1] for point in triangle)
                    minimum_cell_x = math.floor(minimum_x / GRID_CELL_DEGREES)
                    maximum_cell_x = math.floor(maximum_x / GRID_CELL_DEGREES)
                    minimum_cell_y = math.floor(minimum_y / GRID_CELL_DEGREES)
                    maximum_cell_y = math.floor(maximum_y / GRID_CELL_DEGREES)
                    for cell_x in range(minimum_cell_x, maximum_cell_x + 1):
                        for cell_y in range(minimum_cell_y, maximum_cell_y + 1):
                            for index in buckets.get((cell_x, cell_y), ()):
                                if index not in unresolved:
                                    continue
                                if not (
                                    minimum_x - 1e-12 <= longitudes[index] <= maximum_x + 1e-12
                                    and minimum_y - 1e-12 <= latitudes[index] <= maximum_y + 1e-12
                                ):
                                    continue
                                elevation = _barycentric_elevation(
                                    longitudes[index], latitudes[index], triangle
                                )
                                if elevation is None:
                                    continue
                                elevations[index] = elevation
                                source_members[index] = info.filename
                                source_crc32[index] = f"{info.CRC:08x}"
                                triangle_indices[index] = triangle_index
                                unresolved.remove(index)
                    if not unresolved:
                        break
            assigned = len(candidate_indices) - len(unresolved)
            member_reports.append(
                {
                    "source_member": info.filename,
                    "source_member_crc32": f"{info.CRC:08x}",
                    "candidate_nodes": len(candidate_indices),
                    "assigned_nodes": assigned,
                    "triangles_scanned": triangles_scanned,
                    "status": "processed_all_candidates_resolved" if not unresolved else "processed_with_gaps",
                }
            )

    result = pd.DataFrame(
        {
            "node_id": geographic["node_id"].astype(str),
            "elevation_m": elevations,
            "terrain_source_member": source_members,
            "terrain_source_member_crc32": source_crc32,
            "terrain_triangle_index": pd.array(
                np.where(triangle_indices >= 0, triangle_indices, None), dtype="Int64"
            ),
            "terrain_method": np.where(
                np.isfinite(elevations), DEM_ELEVATION_METHOD, "unavailable"
            ),
        }
    )
    covered = int(result["elevation_m"].notna().sum())
    report = {
        "method": DEM_ELEVATION_METHOD,
        "source_crs": "EPSG:6697_axis_order_latitude_longitude_height",
        "interpolation_coordinates": "longitude_latitude_affine_barycentric",
        "road_nodes": len(result),
        "nodes_with_elevation": covered,
        "node_terrain_coverage": covered / len(result) if len(result) else 0.0,
        "dem_members_in_archive": len(member_reports),
        "dem_members_scanned": sum(item["triangles_scanned"] > 0 for item in member_reports),
        "triangles_scanned": sum(item["triangles_scanned"] for item in member_reports),
        "members": member_reports,
    }
    return result, report


def attach_edge_terrain(
    nodes: pd.DataFrame, edges: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Keep distance and endpoint-derived terrain measures in separate columns."""

    elevation = nodes.set_index("node_id")["elevation_m"]
    result = edges.copy()
    result["source_elevation_m"] = result["source_node_id"].map(elevation)
    result["target_elevation_m"] = result["target_node_id"].map(elevation)
    result["elevation_delta_source_to_target_m"] = (
        result["target_elevation_m"] - result["source_elevation_m"]
    )
    result["absolute_grade_percent"] = (
        result["elevation_delta_source_to_target_m"].abs() / result["length_m"] * 100
    )
    result["terrain_status"] = np.where(
        result[["source_elevation_m", "target_elevation_m"]].notna().all(axis=1),
        "available",
        "unavailable",
    )
    covered = int(result["terrain_status"].eq("available").sum())
    report = {
        "road_edges": len(result),
        "edges_with_endpoint_elevation": covered,
        "edge_terrain_coverage": covered / len(result) if len(result) else 0.0,
        "absolute_grade_percent": {
            "median": result["absolute_grade_percent"].median(),
            "p90": result["absolute_grade_percent"].quantile(0.9),
            "p99": result["absolute_grade_percent"].quantile(0.99),
            "maximum": result["absolute_grade_percent"].max(),
        },
    }
    return result, report


def calculate_route_terrain(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    routing: pd.DataFrame,
) -> pd.DataFrame:
    """Accumulate separate ascent/descent/grade components along predecessor paths."""

    elevation = nodes.set_index("node_id")["elevation_m"].to_dict()
    edge_lookup = {
        str(row.edge_id): (str(row.source_node_id), str(row.target_node_id), float(row.length_m))
        for row in edges.itertuples(index=False)
    }
    route = routing.sort_values(
        ["network_to_destination_distance_m", "node_id"], na_position="last"
    )
    accumulated: dict[str, dict[str, Any]] = {}
    for row in route.itertuples(index=False):
        node_id = str(row.node_id)
        if pd.isna(row.network_to_destination_distance_m):
            accumulated[node_id] = {
                "route_graph_length_m": np.nan,
                "terrain_covered_graph_length_m": np.nan,
                "observed_ascent_m": np.nan,
                "observed_descent_m": np.nan,
                "maximum_observed_absolute_grade_percent": np.nan,
                "terrain_route_status": "network_unreachable",
            }
            continue
        if pd.isna(row.predecessor_node_id):
            covered = 0.0
            status = "available" if pd.notna(elevation.get(node_id)) else "unavailable"
            accumulated[node_id] = {
                "route_graph_length_m": 0.0,
                "terrain_covered_graph_length_m": covered,
                "observed_ascent_m": 0.0,
                "observed_descent_m": 0.0,
                "maximum_observed_absolute_grade_percent": 0.0,
                "terrain_route_status": status,
            }
            continue
        previous = str(row.predecessor_node_id)
        edge_id = str(row.predecessor_edge_id)
        source, target, length = edge_lookup[edge_id]
        if {node_id, previous} != {source, target}:
            raise ValueError(f"Routing predecessor does not match edge {edge_id}")
        prior = accumulated[previous]
        total_length = float(prior["route_graph_length_m"]) + length
        covered_length = float(prior["terrain_covered_graph_length_m"])
        ascent = float(prior["observed_ascent_m"])
        descent = float(prior["observed_descent_m"])
        maximum_grade = float(prior["maximum_observed_absolute_grade_percent"])
        current_elevation = elevation.get(node_id)
        previous_elevation = elevation.get(previous)
        if pd.notna(current_elevation) and pd.notna(previous_elevation):
            delta = float(previous_elevation) - float(current_elevation)
            covered_length += length
            ascent += max(delta, 0.0)
            descent += max(-delta, 0.0)
            maximum_grade = max(maximum_grade, abs(delta) / length * 100)
        coverage = covered_length / total_length if total_length else 0.0
        status = "available" if coverage >= 1 - 1e-12 else ("partial" if coverage > 0 else "unavailable")
        accumulated[node_id] = {
            "route_graph_length_m": total_length,
            "terrain_covered_graph_length_m": covered_length,
            "observed_ascent_m": ascent,
            "observed_descent_m": descent,
            "maximum_observed_absolute_grade_percent": maximum_grade,
            "terrain_route_status": status,
        }
    result = pd.DataFrame.from_dict(accumulated, orient="index").rename_axis("node_id").reset_index()
    result["terrain_route_coverage"] = (
        result["terrain_covered_graph_length_m"] / result["route_graph_length_m"]
    )
    terminal = result["route_graph_length_m"].eq(0)
    result.loc[terminal & result["terrain_route_status"].eq("available"), "terrain_route_coverage"] = 1.0
    result["route_ascent_m"] = result["observed_ascent_m"].where(
        result["terrain_route_status"].eq("available")
    )
    result["route_descent_m"] = result["observed_descent_m"].where(
        result["terrain_route_status"].eq("available")
    )
    return result
