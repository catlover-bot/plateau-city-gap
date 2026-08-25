"""Independently verify persisted terrain edges and deep-dive route components."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"
NODES = REAL / "maizuru_road_graph_nodes_terrain.parquet"
EDGES = REAL / "maizuru_road_graph_edges_terrain.parquet"
ROAD_EVIDENCE = REAL / "maizuru_network_deep_dive_evidence.json"
TERRAIN_EVIDENCE = REAL / "maizuru_network_deep_dive_terrain.json"
OUTPUT = REAL / "maizuru_terrain_verification.json"
TOLERANCE = 1e-7


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) or not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _route_check(
    route: dict[str, Any],
    expected: dict[str, Any],
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
) -> dict[str, Any]:
    elevation = nodes.set_index("node_id")["elevation_m"]
    edge_lookup = edges.set_index("edge_id")
    node_ids = [str(value) for value in route["route_node_ids"]]
    edge_ids = [str(value) for value in route["route_edge_ids"]]
    if len(node_ids) != len(edge_ids) + 1:
        raise ValueError("Deep-dive route node/edge counts are inconsistent")
    distance = 0.0
    ascent = 0.0
    descent = 0.0
    maximum_grade = 0.0
    for source, target, edge_id in zip(
        node_ids[:-1], node_ids[1:], edge_ids, strict=True
    ):
        edge = edge_lookup.loc[edge_id]
        if {source, target} != {str(edge["source_node_id"]), str(edge["target_node_id"])}:
            raise ValueError(f"Route edge {edge_id} does not connect consecutive nodes")
        length = float(edge["length_m"])
        delta = float(elevation.loc[target]) - float(elevation.loc[source])
        distance += length
        ascent += max(delta, 0.0)
        descent += max(-delta, 0.0)
        maximum_grade = max(maximum_grade, abs(delta) / length * 100)
    residuals = {
        "graph_edge_distance_m": abs(distance - float(expected["graph_edge_distance_m"])),
        "ascent_m": abs(ascent - float(expected["ascent_m"])),
        "descent_m": abs(descent - float(expected["descent_m"])),
        "maximum_grade_percent": abs(
            maximum_grade - float(expected["maximum_observed_absolute_grade_percent"])
        ),
    }
    return {
        "edge_count": len(edge_ids),
        "recomputed_graph_edge_distance_m": distance,
        "recomputed_ascent_m": ascent,
        "recomputed_descent_m": descent,
        "recomputed_maximum_absolute_grade_percent": maximum_grade,
        "maximum_residual": max(residuals.values(), default=0.0),
        "residuals": residuals,
        "verified": max(residuals.values(), default=0.0) <= TOLERANCE,
    }


def main() -> None:
    nodes = gpd.read_parquet(NODES)
    edges = gpd.read_parquet(EDGES)
    road_evidence = json.loads(ROAD_EVIDENCE.read_text(encoding="utf-8"))
    terrain_evidence = json.loads(TERRAIN_EVIDENCE.read_text(encoding="utf-8"))

    elevation = nodes.set_index("node_id")["elevation_m"]
    recomputed_delta = edges["target_node_id"].map(elevation) - edges["source_node_id"].map(
        elevation
    )
    recomputed_grade = recomputed_delta.abs() / edges["length_m"] * 100
    delta_residual = (recomputed_delta - edges["elevation_delta_source_to_target_m"]).abs()
    grade_residual = (recomputed_grade - edges["absolute_grade_percent"]).abs()
    edge_verified = bool(
        delta_residual.max() <= TOLERANCE and grade_residual.max() <= TOLERANCE
    )

    transport = _route_check(
        road_evidence["transport"], terrain_evidence["transport"], nodes, edges
    )
    medical = _route_check(
        road_evidence["medical"], terrain_evidence["medical"], nodes, edges
    )
    top_grade = edges.nlargest(10, "absolute_grade_percent")[
        [
            "edge_id",
            "source_node_id",
            "target_node_id",
            "length_m",
            "source_elevation_m",
            "target_elevation_m",
            "absolute_grade_percent",
            "topology_relation",
            "surface_gap_m",
        ]
    ]
    result = {
        "method": "independent_persisted_edge_and_route_arithmetic",
        "production_terrain_accumulator_reused": False,
        "verified": edge_verified and transport["verified"] and medical["verified"],
        "tolerance": TOLERANCE,
        "nodes": {
            "records": len(nodes),
            "finite_elevations": int(nodes["elevation_m"].notna().sum()),
            "provenance_complete": bool(
                nodes[
                    [
                        "terrain_source_member",
                        "terrain_source_member_crc32",
                        "terrain_triangle_index",
                    ]
                ]
                .notna()
                .all(axis=1)
                .all()
            ),
        },
        "edges": {
            "records": len(edges),
            "maximum_elevation_delta_residual_m": delta_residual.max(),
            "maximum_grade_residual_percent": grade_residual.max(),
            "verified": edge_verified,
            "top_absolute_grade_edges": top_grade.to_dict(orient="records"),
        },
        "transport_deep_dive": transport,
        "medical_deep_dive": medical,
        "inputs": {
            "terrain_nodes_sha256": _sha256(NODES),
            "terrain_edges_sha256": _sha256(EDGES),
            "road_evidence_sha256": _sha256(ROAD_EVIDENCE),
            "terrain_evidence_sha256": _sha256(TERRAIN_EVIDENCE),
        },
    }
    if not result["verified"]:
        raise ValueError("Terrain verification failed")
    OUTPUT.write_text(
        json.dumps(_json_value(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_json_value(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
