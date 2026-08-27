"""Independent reference-network validation primitives.

OpenStreetMap is used only as a versioned ``reference_network``.  It is not a
ground truth and it does not replace CITY GAP's production network model.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

OSM_ATTRIBUTION = "© OpenStreetMap contributors"
OSM_LICENSE = "Open Data Commons Open Database License (ODbL)"
REFERENCE_SEMANTICS = "reference_network_not_ground_truth"
ALGORITHM_VERSION = "citygap-network-cross-validation-v1.0.0"


@dataclass(frozen=True, slots=True)
class ReferenceGraph:
    nodes: gpd.GeoDataFrame
    edges: gpd.GeoDataFrame
    adjacency: dict[str, list[tuple[str, float, str]]]
    report: dict[str, Any]


def _coordinate_id(longitude: float, latitude: float) -> str:
    value = f"{longitude:.7f},{latitude:.7f}"
    return f"osmref::{hashlib.sha1(value.encode()).hexdigest()[:20]}"


def read_osm_overpass_reference(
    source: str | Path,
    *,
    analysis_crs: str,
    retrieval_date: str,
    extract_source: str,
    source_sha256: str,
) -> ReferenceGraph:
    """Read a pinned Overpass JSON extract into a deterministic undirected graph."""

    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    edge_candidates: dict[tuple[str, str], dict[str, Any]] = {}
    coordinate_by_id: dict[str, tuple[float, float]] = {}
    way_count = 0
    excluded_bad_geometry = 0
    tag_counts = {"bridge": 0, "tunnel": 0, "oneway": 0, "sidewalk": 0}
    highway_counts: dict[str, int] = {}
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        geometry = element.get("geometry") or []
        tags = element.get("tags") or {}
        if len(geometry) < 2 or any("lon" not in item or "lat" not in item for item in geometry):
            excluded_bad_geometry += 1
            continue
        way_count += 1
        highway = str(tags.get("highway", "unknown"))
        highway_counts[highway] = highway_counts.get(highway, 0) + 1
        flags = {
            "bridge": str(tags.get("bridge", "no")) not in {"", "no", "false", "0"},
            "tunnel": str(tags.get("tunnel", "no")) not in {"", "no", "false", "0"},
            "oneway": str(tags.get("oneway", "no")) not in {"", "no", "false", "0"},
            "sidewalk": "sidewalk" in tags,
        }
        for name, enabled in flags.items():
            tag_counts[name] += int(enabled)
        points: list[tuple[str, tuple[float, float]]] = []
        for coordinate in geometry:
            lon = round(float(coordinate["lon"]), 7)
            lat = round(float(coordinate["lat"]), 7)
            node_id = _coordinate_id(lon, lat)
            coordinate_by_id[node_id] = (lon, lat)
            points.append((node_id, (lon, lat)))
        for (left_id, left), (right_id, right) in pairwise(points):
            if left_id == right_id:
                continue
            key = tuple(sorted((left_id, right_id)))
            candidate = {
                "source_node_id": key[0],
                "target_node_id": key[1],
                "way_id": str(element.get("id")),
                "highway": highway,
                **flags,
                "geometry_wgs84": LineString([left, right]),
            }
            current = edge_candidates.get(key)
            if current is None or candidate["way_id"] < current["way_id"]:
                edge_candidates[key] = candidate

    if not coordinate_by_id or not edge_candidates:
        raise ValueError("OSM reference extract produced an empty graph")
    nodes = gpd.GeoDataFrame(
        {"node_id": sorted(coordinate_by_id)},
        geometry=[Point(coordinate_by_id[node_id]) for node_id in sorted(coordinate_by_id)],
        crs="EPSG:4326",
    ).to_crs(analysis_crs)
    projected_by_id = dict(zip(nodes["node_id"], nodes.geometry, strict=True))
    edge_rows: list[dict[str, Any]] = []
    for key, row in sorted(edge_candidates.items()):
        left = projected_by_id[row["source_node_id"]]
        right = projected_by_id[row["target_node_id"]]
        length = float(left.distance(right))
        if length <= 0:
            continue
        edge_id = f"osmref::{hashlib.sha1('|'.join(key).encode()).hexdigest()[:20]}"
        edge_rows.append(
            {
                "edge_id": edge_id,
                "source_node_id": row["source_node_id"],
                "target_node_id": row["target_node_id"],
                "length_m": length,
                "way_id": row["way_id"],
                "highway": row["highway"],
                "bridge": row["bridge"],
                "tunnel": row["tunnel"],
                "oneway": row["oneway"],
                "sidewalk": row["sidewalk"],
                "geometry": LineString([left, right]),
            }
        )
    edges = gpd.GeoDataFrame(edge_rows, geometry="geometry", crs=analysis_crs)
    adjacency: dict[str, list[tuple[str, float, str]]] = {
        str(node_id): [] for node_id in nodes["node_id"]
    }
    for row in edges.itertuples(index=False):
        adjacency[row.source_node_id].append((row.target_node_id, float(row.length_m), row.edge_id))
        adjacency[row.target_node_id].append((row.source_node_id, float(row.length_m), row.edge_id))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[2]))

    components = _component_sizes(adjacency)
    report = {
        "reference_semantics": REFERENCE_SEMANTICS,
        "replacement_for_production_network": False,
        "extract_source": extract_source,
        "retrieval_date": retrieval_date,
        "source_sha256": source_sha256,
        "attribution": OSM_ATTRIBUTION,
        "license": OSM_LICENSE,
        "network_extraction_rule": (
            "Overpass highway ways; motorway/trunk/construction/proposed and explicit "
            "private/no access or foot=no/private excluded; undirected pedestrian-reference semantics"
        ),
        "pedestrian_semantics": (
            "walk-permitted public highway reference where tagged; missing sidewalk/crossing/entrance "
            "attributes remain a known limitation"
        ),
        "ways": way_count,
        "nodes": len(nodes),
        "edges": len(edges),
        "components": len(components),
        "largest_component_nodes": components[0] if components else 0,
        "largest_component_fraction": components[0] / len(nodes) if components else 0.0,
        "excluded_bad_geometry_ways": excluded_bad_geometry,
        "highway_counts": dict(sorted(highway_counts.items())),
        "tagged_way_counts": tag_counts,
    }
    return ReferenceGraph(nodes=nodes, edges=edges, adjacency=adjacency, report=report)


def _component_sizes(adjacency: dict[str, list[tuple[str, float, str]]]) -> list[int]:
    unvisited = set(adjacency)
    sizes: list[int] = []
    while unvisited:
        seed = min(unvisited)
        unvisited.remove(seed)
        stack = [seed]
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            for neighbor, _, _ in adjacency[node]:
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    stack.append(neighbor)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def snap_points_to_reference_nodes(
    points: gpd.GeoDataFrame,
    nodes: gpd.GeoDataFrame,
    *,
    id_column: str,
) -> pd.DataFrame:
    if points.crs != nodes.crs:
        points = points.to_crs(nodes.crs)
    joined = gpd.sjoin_nearest(
        points[[id_column, "geometry"]],
        nodes[["node_id", "geometry"]],
        how="left",
        distance_col="snap_distance_m",
    )
    joined = joined.sort_values([id_column, "snap_distance_m", "node_id"])
    joined = joined.drop_duplicates(id_column)
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"]))


def shortest_path(
    graph: ReferenceGraph,
    origin_node_id: str,
    destination_node_id: str,
    *,
    origin_connector_m: float = 0.0,
    destination_connector_m: float = 0.0,
) -> dict[str, Any]:
    """Deterministic A* path with connector distances reported separately."""

    if origin_node_id not in graph.adjacency or destination_node_id not in graph.adjacency:
        return {"reachable": False, "distance_m": None, "nodes": [], "edges": []}
    xy = dict(zip(graph.nodes["node_id"], graph.nodes.geometry, strict=True))
    destination_point = xy[destination_node_id]

    def heuristic(node_id: str) -> float:
        return float(xy[node_id].distance(destination_point))

    distance = {origin_node_id: 0.0}
    predecessor: dict[str, tuple[str, str]] = {}
    queue: list[tuple[float, float, str]] = [(heuristic(origin_node_id), 0.0, origin_node_id)]
    settled: set[str] = set()
    while queue:
        _, current_distance, node_id = heapq.heappop(queue)
        if node_id in settled:
            continue
        settled.add(node_id)
        if node_id == destination_node_id:
            break
        for neighbor, weight, edge_id in graph.adjacency[node_id]:
            proposed = current_distance + weight
            if proposed < distance.get(neighbor, math.inf) - 1e-9:
                distance[neighbor] = proposed
                predecessor[neighbor] = (node_id, edge_id)
                heapq.heappush(queue, (proposed + heuristic(neighbor), proposed, neighbor))
    if destination_node_id not in distance:
        return {
            "reachable": False,
            "distance_m": None,
            "graph_distance_m": None,
            "origin_snap_distance_m": origin_connector_m,
            "destination_snap_distance_m": destination_connector_m,
            "nodes": [],
            "edges": [],
        }
    node_id = destination_node_id
    route_nodes = [node_id]
    route_edges: list[str] = []
    while node_id != origin_node_id:
        previous, edge_id = predecessor[node_id]
        route_edges.append(edge_id)
        route_nodes.append(previous)
        node_id = previous
    route_nodes.reverse()
    route_edges.reverse()
    graph_distance = float(distance[destination_node_id])
    return {
        "reachable": True,
        "distance_m": graph_distance + origin_connector_m + destination_connector_m,
        "graph_distance_m": graph_distance,
        "origin_snap_distance_m": origin_connector_m,
        "destination_snap_distance_m": destination_connector_m,
        "nodes": route_nodes,
        "edges": route_edges,
    }


def multi_source_reference_destinations(
    graph: ReferenceGraph,
    seeds: pd.DataFrame,
    *,
    destination_id_column: str,
) -> pd.DataFrame:
    """Nearest reference destination for destination-agreement measurement."""

    distance = {node_id: math.inf for node_id in graph.adjacency}
    destination: dict[str, str | None] = {node_id: None for node_id in graph.adjacency}
    queue: list[tuple[float, str, str]] = []
    for row in seeds.sort_values(["node_id", "snap_distance_m", destination_id_column]).itertuples():
        node_id = str(row.node_id)
        destination_id = str(getattr(row, destination_id_column))
        initial = float(row.snap_distance_m)
        if initial < distance[node_id] - 1e-9 or (
            abs(initial - distance[node_id]) <= 1e-9
            and (destination[node_id] is None or destination_id < str(destination[node_id]))
        ):
            distance[node_id] = initial
            destination[node_id] = destination_id
            heapq.heappush(queue, (initial, destination_id, node_id))
    while queue:
        current, destination_id, node_id = heapq.heappop(queue)
        if current > distance[node_id] + 1e-9 or destination[node_id] != destination_id:
            continue
        for neighbor, weight, _ in graph.adjacency[node_id]:
            proposed = current + weight
            if proposed < distance[neighbor] - 1e-9 or (
                abs(proposed - distance[neighbor]) <= 1e-9
                and (destination[neighbor] is None or destination_id < str(destination[neighbor]))
            ):
                distance[neighbor] = proposed
                destination[neighbor] = destination_id
                heapq.heappush(queue, (proposed, destination_id, neighbor))
    return pd.DataFrame(
        {
            "node_id": sorted(graph.adjacency),
            "reference_nearest_destination_id": [destination[node] for node in sorted(graph.adjacency)],
            "reference_nearest_destination_distance_from_node_m": [
                distance[node] if math.isfinite(distance[node]) else np.nan
                for node in sorted(graph.adjacency)
            ],
        }
    )


def route_geometry(graph: ReferenceGraph, edge_ids: Iterable[str]) -> LineString | None:
    lookup = graph.edges.set_index("edge_id").geometry
    coordinates: list[tuple[float, float]] = []
    for edge_id in edge_ids:
        line = lookup.loc[edge_id]
        part = list(line.coords)
        if coordinates and (coordinates[-1] == part[-1] or coordinates[-1] != part[0]):
            part.reverse()
        coordinates.extend(part if not coordinates else part[1:])
    return LineString(coordinates) if len(coordinates) >= 2 else None


def reference_agreement(
    primary_distance_m: float | None,
    reference_distance_m: float | None,
    primary_reachable: bool,
    reference_reachable: bool,
) -> str:
    if primary_reachable != reference_reachable:
        return "connectivity_disagreement"
    if not primary_reachable:
        return "connectivity_agreement"
    assert primary_distance_m is not None and reference_distance_m is not None
    relative = abs(primary_distance_m - reference_distance_m) / max(reference_distance_m, 1.0)
    if relative <= 0.20:
        return "distance_similar"
    if relative <= 0.50:
        return "moderate_difference"
    return "large_difference"


def comparison_statistics(samples: pd.DataFrame) -> dict[str, Any]:
    comparable = samples.loc[
        samples["primary_reachable"]
        & samples["reference_reachable"]
        & samples["primary_distance_m"].notna()
        & samples["reference_distance_m"].notna()
    ].copy()
    differences = (comparable["primary_distance_m"] - comparable["reference_distance_m"]).abs()
    relative = differences / comparable["reference_distance_m"].clip(lower=1.0)
    both_reachability = samples["primary_reachable"].eq(samples["reference_reachable"])
    reachable = samples["primary_reachable"] & samples["reference_reachable"]
    unreachable = ~samples["primary_reachable"] & ~samples["reference_reachable"]
    return {
        "sample_count": len(samples),
        "comparable_distance_count": len(comparable),
        "distance_mae_m": float(differences.mean()) if len(comparable) else None,
        "median_absolute_difference_m": float(differences.median()) if len(comparable) else None,
        "p90_absolute_difference_m": float(differences.quantile(0.90)) if len(comparable) else None,
        "mean_relative_error": float(relative.mean()) if len(comparable) else None,
        "spearman_rank_correlation": (
            float(
                comparable["primary_distance_m"].rank(method="average").corr(
                    comparable["reference_distance_m"].rank(method="average"),
                    method="pearson",
                )
            )
            if len(comparable) >= 2
            else None
        ),
        "connectivity_agreement_fraction": float(both_reachability.mean()) if len(samples) else None,
        "both_reachable_count": int(reachable.sum()),
        "both_unreachable_count": int(unreachable.sum()),
        "connectivity_disagreement_count": int((~both_reachability).sum()),
        "destination_agreement_fraction": (
            float(samples["destination_agreement"].mean())
            if "destination_agreement" in samples and samples["destination_agreement"].notna().any()
            else None
        ),
        "median_primary_snap_m": float(samples["primary_origin_snap_m"].median()),
        "median_reference_snap_m": float(samples["reference_origin_snap_m"].median()),
        "median_route_overlap_fraction": (
            float(samples["route_overlap_fraction"].median())
            if "route_overlap_fraction" in samples and samples["route_overlap_fraction"].notna().any()
            else None
        ),
        "agreement_categories": samples["reference_agreement"].value_counts().sort_index().to_dict(),
    }


def classify_disagreement_cause(record: dict[str, Any]) -> tuple[str, str]:
    """Assign only deterministic cause candidates; ambiguous cases stay undetermined."""

    if record.get("primary_reachable") != record.get("reference_reachable"):
        if not record.get("primary_reachable") and record.get("reference_reachable"):
            return "topology", "primary graph disconnected while reference graph has a path"
        return "road_coverage", "reference graph disconnected while primary graph has a path"
    if max(float(record.get("primary_origin_snap_m") or 0), float(record.get("reference_origin_snap_m") or 0)) > 150:
        return "snap", "at least one origin connector exceeds 150 m"
    if record.get("reference_route_has_bridge") or record.get("reference_route_has_tunnel"):
        return "bridge", "reference route includes a tagged bridge or tunnel"
    if record.get("reference_route_has_oneway"):
        return "one_way", "reference route includes a tagged one-way way; walking graph is undirected"
    overlap = record.get("route_overlap_fraction")
    if overlap is not None and overlap < 0.20:
        return "geometry_resolution", "buffered route overlap is below 0.20"
    if record.get("reference_agreement") in {"moderate_difference", "large_difference"}:
        return "topology", "distance difference remains after connector and tagged-structure checks"
    return "undetermined", "available deterministic rules do not isolate a cause"
