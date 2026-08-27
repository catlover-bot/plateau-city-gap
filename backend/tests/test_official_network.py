from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from backend.citygap_platform.ingestion.official_network import (
    OfficialNetworkFieldMap,
    OfficialRoadNetworkAdapter,
)


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    nodes_path = tmp_path / "nodes.geojson"
    edges_path = tmp_path / "edges.geojson"
    gpd.GeoDataFrame(
        {"node_id": ["n1", "n2", "n3"]},
        geometry=[Point(139.46, 35.34), Point(139.47, 35.34), Point(139.50, 35.35)],
        crs="EPSG:4326",
    ).to_file(nodes_path, driver="GeoJSON")
    gpd.GeoDataFrame(
        {"edge_id": ["e1"], "source": ["n1"], "target": ["n2"]},
        geometry=[LineString([(139.46, 35.34), (139.47, 35.34)])],
        crs="EPSG:4326",
    ).to_file(edges_path, driver="GeoJSON")
    return nodes_path, edges_path


def test_official_output_adapter_preserves_source_type_version_and_components(tmp_path: Path) -> None:
    nodes, edges = _write_fixture(tmp_path)
    adapter = OfficialRoadNetworkAdapter(
        nodes,
        edges,
        source_type="official_walk",
        fields=OfficialNetworkFieldMap("node_id", "edge_id", "source", "target"),
        analysis_crs="EPSG:6677",
    )
    inspection = adapter.inspect()
    assert inspection.source_type == "official_walk"
    assert inspection.graph_version.startswith("official-walk-")
    assert inspection.node_count == 3
    assert inspection.edge_count == 1
    assert inspection.component_count == 2


def test_official_output_adapter_rejects_unknown_nodes_and_experimental_claims(tmp_path: Path) -> None:
    nodes, edges = _write_fixture(tmp_path)
    edge_frame = gpd.read_file(edges)
    edge_frame.loc[0, "target"] = "missing"
    edge_frame.to_file(edges, driver="GeoJSON")
    with pytest.raises(ValueError, match="unknown node"):
        OfficialRoadNetworkAdapter(
            nodes,
            edges,
            source_type="official_drive",
            fields=OfficialNetworkFieldMap("node_id", "edge_id", "source", "target"),
            analysis_crs="EPSG:6677",
        ).inspect()
    with pytest.raises(ValueError, match="accepts only"):
        OfficialRoadNetworkAdapter(
            nodes,
            edges,
            source_type="experimental_surface_adjacency",  # type: ignore[arg-type]
            fields=OfficialNetworkFieldMap("node_id", "edge_id", "source", "target"),
            analysis_crs="EPSG:6677",
        )
