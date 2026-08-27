"""Versioned PLATEAU road-network adapters and experimental graph calculations.

The official Project PLATEAU generator output and the fallback CityGML surface
adjacency graph are intentionally different methods.  The fallback is not a
pedestrian network and must never be labelled as a walking route.
"""

from __future__ import annotations

import hashlib
import heapq
import math
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO, Literal

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Polygon

GML_ID = "{http://www.opengis.net/gml}id"
ANALYSIS_CRS = "EPSG:6674"
OFFICIAL_NODE_COLUMNS = frozenset({"node_id"})
OFFICIAL_LINK_COLUMNS = frozenset({"link_id", "start_id", "end_id", "distance"})
EXPERIMENTAL_GRAPH_METHOD = "experimental_citygml_lod1_surface_adjacency"
OFFICIAL_GRAPH_METHOD = "plateau_roadnetwork_generator_output"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ring_coordinates(text: str, dimension: int = 3) -> list[tuple[float, float]] | None:
    values = [float(value) for value in text.replace(",", " ").split()]
    if len(values) < dimension * 4 or len(values) % dimension:
        return None
    return [
        (values[index + 1], values[index]) for index in range(0, len(values), dimension)
    ]


def iter_road_surfaces(
    stream: BinaryIO,
    *,
    source_member: str,
    source_member_crc32: str,
) -> Iterable[dict[str, Any]]:
    """Yield actual LOD1 Road polygons from one CityGML member."""

    stack: list[str] = []
    current: dict[str, Any] | None = None
    active_lod: int | None = None
    polygon_depth: int | None = None
    polygon_exterior: list[tuple[float, float]] | None = None
    polygon_interiors: list[list[tuple[float, float]]] = []

    for event, element in ET.iterparse(stream, events=("start", "end")):
        local = _local_name(element.tag)
        if event == "start":
            parent = stack[-1] if stack else None
            stack.append(local)
            if local.startswith("lod") and len(local) > 3 and local[3].isdigit():
                active_lod = int(local[3])
            if parent == "cityObjectMember" and local == "Road" and element.get(GML_ID):
                current = {
                    "depth": len(stack),
                    "gml_id": element.get(GML_ID),
                    "source_member": source_member,
                    "source_member_crc32": source_member_crc32,
                    "name": None,
                    "road_class": None,
                    "function_code": None,
                    "usage_code": None,
                    "surfaces": [],
                }
            elif current is not None and local == "Polygon" and active_lod == 1:
                polygon_depth = len(stack)
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
            elif text and local == "name" and current["name"] is None:
                current["name"] = text
            elif text and local == "class" and current["road_class"] is None:
                current["road_class"] = text
            elif text and local == "function" and current["function_code"] is None:
                current["function_code"] = text
            elif text and local == "usage" and current["usage_code"] is None:
                current["usage_code"] = text

            if local == "Polygon" and len(stack) == polygon_depth:
                if polygon_exterior is not None:
                    polygon = Polygon(polygon_exterior, polygon_interiors)
                    if not polygon.is_empty and polygon.is_valid and polygon.area > 0:
                        current["surfaces"].append(polygon)
                polygon_depth = None
                polygon_exterior = None
                polygon_interiors = []

            if len(stack) == current["depth"]:
                current.pop("depth")
                for surface_index, geometry in enumerate(current.pop("surfaces")):
                    yield {
                        **current,
                        "surface_index": surface_index,
                        "surface_id": f"{current['gml_id']}:{surface_index}",
                        "geometry": geometry,
                    }
                current = None

        element.clear()
        ended = stack.pop()
        if ended.startswith("lod") and len(ended) > 3 and ended[3].isdigit():
            active_lod = next(
                (
                    int(name[3])
                    for name in reversed(stack)
                    if name.startswith("lod") and len(name) > 3 and name[3].isdigit()
                ),
                None,
            )


def read_road_surfaces(archive_path: str | Path) -> gpd.GeoDataFrame:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = sorted(
            (
                info
                for info in archive.infolist()
                if info.filename.startswith("udx/tran/") and info.filename.endswith(".gml")
            ),
            key=lambda info: info.filename,
        )
        for info in members:
            with archive.open(info) as stream:
                rows.extend(
                    iter_road_surfaces(
                        stream,
                        source_member=info.filename,
                        source_member_crc32=f"{info.CRC:08x}",
                    )
                )
    result = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    if result.empty or result["surface_id"].duplicated().any():
        raise ValueError("Road surface extraction produced no data or duplicate IDs")
    return result


class _UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.size = [1] * size

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.size[left_root] < self.size[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        self.size[left_root] += self.size[right_root]


def build_surface_adjacency_graph(
    surfaces: gpd.GeoDataFrame,
    *,
    tolerance_m: float = 0.05,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict[str, Any]]:
    """Build a deterministic fallback graph from touching LOD1 road surfaces."""

    if surfaces.crs is None or not surfaces.crs.is_projected:
        raise ValueError("Road surfaces must use a projected analysis CRS")
    if tolerance_m < 0 or tolerance_m > 1:
        raise ValueError("Surface topology tolerance must be between zero and one metre")
    source = surfaces.sort_values("surface_id").reset_index(drop=True).copy()
    source["node_id"] = source["surface_id"].map(lambda value: f"exp::{value}")
    node_geometry = source.geometry.representative_point()
    nodes = gpd.GeoDataFrame(
        source.drop(columns="geometry"), geometry=node_geometry, crs=surfaces.crs
    )

    left = source[["surface_id", "geometry"]].rename(columns={"surface_id": "left_id"})
    right = source[["surface_id", "geometry"]].rename(columns={"surface_id": "right_id"})
    if tolerance_m == 0:
        pairs = gpd.sjoin(left, right, how="inner", predicate="intersects")
    else:
        pairs = gpd.sjoin(
            left,
            right,
            how="inner",
            predicate="dwithin",
            distance=tolerance_m,
        )
    pairs = pairs.loc[pairs["left_id"].lt(pairs["right_id"]), ["left_id", "right_id"]]
    pairs = pairs.drop_duplicates().sort_values(["left_id", "right_id"]).reset_index(drop=True)

    surface_position = {value: index for index, value in enumerate(source["surface_id"])}
    point_by_surface = dict(zip(source["surface_id"], node_geometry, strict=True))
    polygon_by_surface = dict(zip(source["surface_id"], source.geometry, strict=True))
    edge_rows: list[dict[str, Any]] = []
    topology_bridges = 0
    union = _UnionFind(len(source))
    for left_id, right_id in pairs.itertuples(index=False):
        left_point = point_by_surface[left_id]
        right_point = point_by_surface[right_id]
        length = float(left_point.distance(right_point))
        if length <= 1e-9:
            continue
        gap = float(polygon_by_surface[left_id].distance(polygon_by_surface[right_id]))
        relation = "surface_intersection" if gap <= 1e-9 else "tolerance_bridge"
        topology_bridges += int(relation == "tolerance_bridge")
        digest = hashlib.sha1(f"{left_id}|{right_id}".encode()).hexdigest()[:20]
        edge_rows.append(
            {
                "edge_id": f"exp::{digest}",
                "source_node_id": f"exp::{left_id}",
                "target_node_id": f"exp::{right_id}",
                "length_m": length,
                "topology_relation": relation,
                "surface_gap_m": gap,
                "graph_method": EXPERIMENTAL_GRAPH_METHOD,
                "pedestrian_permission": "unknown",
                "geometry": LineString([left_point, right_point]),
            }
        )
        union.union(surface_position[left_id], surface_position[right_id])
    edges = gpd.GeoDataFrame(edge_rows, geometry="geometry", crs=surfaces.crs)
    if edges.empty:
        raise ValueError("Road surface graph contains no edges")

    roots: dict[int, list[int]] = {}
    for index in range(len(nodes)):
        roots.setdefault(union.find(index), []).append(index)
    ordered_roots = sorted(
        roots,
        key=lambda root: (-len(roots[root]), str(nodes.iloc[min(roots[root])]["node_id"])),
    )
    component_by_root = {
        root: f"component_{rank:04d}" for rank, root in enumerate(ordered_roots, start=1)
    }
    nodes["component_id"] = [component_by_root[union.find(index)] for index in range(len(nodes))]
    nodes["graph_method"] = EXPERIMENTAL_GRAPH_METHOD
    nodes["pedestrian_permission"] = "unknown"
    component_sizes = nodes["component_id"].value_counts()
    report = {
        "graph_method": EXPERIMENTAL_GRAPH_METHOD,
        "pedestrian_network": False,
        "route_semantics": "PLATEAU LOD1 road-surface adjacency path; mode not validated",
        "topology_tolerance_m": tolerance_m,
        "nodes": len(nodes),
        "edges": len(edges),
        "components": len(component_sizes),
        "largest_component_nodes": int(component_sizes.iloc[0]),
        "largest_component_fraction": float(component_sizes.iloc[0] / len(nodes)),
        "tolerance_bridge_edges": topology_bridges,
        "zero_length_pairs_dropped": int(len(pairs) - len(edges)),
    }
    validate_graph(nodes, edges)
    return nodes, edges, report


def validate_graph(nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame) -> None:
    if nodes["node_id"].duplicated().any() or edges["edge_id"].duplicated().any():
        raise ValueError("Graph IDs must be unique")
    node_ids = set(nodes["node_id"])
    referenced = set(edges["source_node_id"]) | set(edges["target_node_id"])
    missing = referenced - node_ids
    if missing:
        raise ValueError(f"Edges reference missing nodes: {sorted(missing)[:3]}")
    if edges["length_m"].isna().any() or edges["length_m"].le(0).any():
        raise ValueError("Every graph edge must have a positive length")


def read_official_generator_output(
    node_path: str | Path,
    link_path: str | Path,
    *,
    network_type: Literal["road", "walk"],
    graph_version: str,
    analysis_crs: str = ANALYSIS_CRS,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict[str, Any]]:
    """Normalize official PLATEAU RoadNetwork Generator GeoJSON/Shapefile output."""

    source_nodes = gpd.read_file(node_path)
    source_edges = gpd.read_file(link_path)
    missing_nodes = OFFICIAL_NODE_COLUMNS - set(source_nodes.columns)
    missing_edges = OFFICIAL_LINK_COLUMNS - set(source_edges.columns)
    if missing_nodes or missing_edges:
        raise ValueError(
            f"Official output columns missing: nodes={sorted(missing_nodes)}, "
            f"links={sorted(missing_edges)}"
        )
    if source_nodes.crs is None or source_edges.crs is None:
        raise ValueError("Official generator output must declare a CRS")
    nodes = source_nodes.to_crs(analysis_crs).rename(columns={"node_id": "node_id"}).copy()
    nodes["node_id"] = nodes["node_id"].astype(str)
    nodes["graph_method"] = OFFICIAL_GRAPH_METHOD
    nodes["graph_version"] = graph_version
    nodes["pedestrian_permission"] = "generator_walk_output" if network_type == "walk" else "unknown"
    edges = source_edges.to_crs(analysis_crs).rename(
        columns={
            "link_id": "edge_id",
            "start_id": "source_node_id",
            "end_id": "target_node_id",
            "distance": "length_m",
        }
    )
    for column in ("edge_id", "source_node_id", "target_node_id"):
        edges[column] = edges[column].astype(str)
    edges["length_m"] = pd.to_numeric(edges["length_m"], errors="coerce")
    edges["graph_method"] = OFFICIAL_GRAPH_METHOD
    edges["graph_version"] = graph_version
    edges["pedestrian_permission"] = (
        "generator_walk_output" if network_type == "walk" else "unknown"
    )
    validate_graph(nodes, edges)
    report = {
        "graph_method": OFFICIAL_GRAPH_METHOD,
        "graph_version": graph_version,
        "network_type": network_type,
        "nodes": len(nodes),
        "edges": len(edges),
        "pedestrian_network": network_type == "walk",
    }
    return nodes, edges, report


def snap_points_to_surfaces(
    points: gpd.GeoDataFrame,
    surfaces: gpd.GeoDataFrame,
    nodes: gpd.GeoDataFrame,
    *,
    id_column: str,
) -> pd.DataFrame:
    """Attach origins to their nearest PLATEAU road surface and graph node."""

    if points.crs != surfaces.crs or points.crs != nodes.crs:
        raise ValueError("Points, road surfaces, and nodes must use the same CRS")
    origins = points[[id_column, "geometry"]].reset_index(drop=True).copy()
    joined = gpd.sjoin_nearest(
        origins,
        surfaces[["surface_id", "geometry"]],
        how="left",
        distance_col="road_surface_distance_m",
    )
    joined = joined.sort_values([id_column, "road_surface_distance_m", "surface_id"])
    joined = joined.drop_duplicates(id_column)
    node_lookup = nodes.set_index("surface_id")
    joined["node_id"] = joined["surface_id"].map(node_lookup["node_id"])
    graph_points = joined["surface_id"].map(node_lookup.geometry)
    joined["origin_to_node_distance_m"] = [
        origin.distance(node) for origin, node in zip(joined.geometry, graph_points, strict=True)
    ]
    joined["snap_method"] = "nearest_lod1_road_surface_to_representative_graph_node"
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"]))


def multi_source_shortest_paths(
    nodes: gpd.GeoDataFrame,
    edges: gpd.GeoDataFrame,
    seeds: pd.DataFrame,
    *,
    destination_id_column: str,
    destination_name_column: str,
) -> pd.DataFrame:
    """Deterministic undirected multi-source Dijkstra with destination lineage."""

    validate_graph(nodes, edges)
    required = {"node_id", "origin_to_node_distance_m", destination_id_column, destination_name_column}
    missing = required - set(seeds.columns)
    if missing:
        raise ValueError(f"Routing seeds lack columns: {sorted(missing)}")
    adjacency: dict[str, list[tuple[str, float, str]]] = {
        str(node_id): [] for node_id in nodes["node_id"]
    }
    for row in edges.itertuples(index=False):
        source = str(row.source_node_id)
        target = str(row.target_node_id)
        weight = float(row.length_m)
        edge_id = str(row.edge_id)
        adjacency[source].append((target, weight, edge_id))
        adjacency[target].append((source, weight, edge_id))
    for node_id, neighbors in adjacency.items():
        neighbors.sort(key=lambda item: (item[0], item[2]))

    distance = {node_id: math.inf for node_id in adjacency}
    destination: dict[str, tuple[str, str] | None] = {node_id: None for node_id in adjacency}
    predecessor: dict[str, tuple[str, str] | None] = {node_id: None for node_id in adjacency}
    queue: list[tuple[float, str, str, str]] = []
    ordered_seeds = seeds.sort_values(
        ["node_id", "origin_to_node_distance_m", destination_id_column]
    )
    for row in ordered_seeds.itertuples(index=False):
        node_id = str(row.node_id)
        destination_id = str(getattr(row, destination_id_column))
        destination_name = str(getattr(row, destination_name_column))
        initial = float(row.origin_to_node_distance_m)
        candidate_key = (destination_id, destination_name)
        current_key = destination[node_id]
        if initial < distance[node_id] - 1e-9 or (
            abs(initial - distance[node_id]) <= 1e-9
            and (current_key is None or candidate_key < current_key)
        ):
            distance[node_id] = initial
            destination[node_id] = candidate_key
            predecessor[node_id] = None
            heapq.heappush(queue, (initial, destination_id, destination_name, node_id))

    while queue:
        current_distance, destination_id, destination_name, node_id = heapq.heappop(queue)
        if current_distance > distance[node_id] + 1e-9:
            continue
        if destination[node_id] != (destination_id, destination_name):
            continue
        for neighbor, weight, edge_id in adjacency[node_id]:
            proposed = current_distance + weight
            proposed_key = (destination_id, destination_name)
            current_key = destination[neighbor]
            if proposed < distance[neighbor] - 1e-9 or (
                abs(proposed - distance[neighbor]) <= 1e-9
                and (current_key is None or proposed_key < current_key)
            ):
                distance[neighbor] = proposed
                destination[neighbor] = proposed_key
                predecessor[neighbor] = (node_id, edge_id)
                heapq.heappush(
                    queue, (proposed, destination_id, destination_name, neighbor)
                )

    rows = []
    for node_id in sorted(adjacency):
        target = destination[node_id]
        previous = predecessor[node_id]
        rows.append(
            {
                "node_id": node_id,
                "network_to_destination_distance_m": (
                    distance[node_id] if math.isfinite(distance[node_id]) else np.nan
                ),
                "destination_id": target[0] if target else None,
                "destination_name": target[1] if target else None,
                "predecessor_node_id": previous[0] if previous else None,
                "predecessor_edge_id": previous[1] if previous else None,
            }
        )
    return pd.DataFrame(rows)


def reconstruct_route(
    result: pd.DataFrame,
    origin_node_id: str,
    *,
    maximum_edges: int = 100_000,
) -> tuple[list[str], list[str]]:
    """Return node and edge IDs from an origin toward the chosen Dijkstra seed."""

    lookup = result.set_index("node_id")
    if origin_node_id not in lookup.index:
        raise ValueError(f"Unknown route origin node {origin_node_id}")
    nodes = [origin_node_id]
    edges: list[str] = []
    seen = {origin_node_id}
    while len(edges) < maximum_edges:
        row = lookup.loc[nodes[-1]]
        previous = row["predecessor_node_id"]
        edge = row["predecessor_edge_id"]
        if pd.isna(previous) or pd.isna(edge):
            return nodes, edges
        previous = str(previous)
        if previous in seen:
            raise ValueError("Route predecessor chain contains a cycle")
        seen.add(previous)
        edges.append(str(edge))
        nodes.append(previous)
    raise ValueError("Route exceeds maximum edge count")
