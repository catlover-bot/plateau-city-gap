from io import BytesIO
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, box

from analysis.src.plateau_road_network import (
    ANALYSIS_CRS,
    EXPERIMENTAL_GRAPH_METHOD,
    OFFICIAL_GRAPH_METHOD,
    build_surface_adjacency_graph,
    iter_road_surfaces,
    multi_source_shortest_paths,
    read_official_generator_output,
    reconstruct_route,
    snap_points_to_surfaces,
)


def test_citygml_lod1_road_parser_preserves_hole_and_lineage() -> None:
    xml = b"""<core:CityModel
      xmlns:core="http://www.opengis.net/citygml/2.0"
      xmlns:tran="http://www.opengis.net/citygml/transportation/2.0"
      xmlns:gml="http://www.opengis.net/gml">
      <core:cityObjectMember><tran:Road gml:id="road-with-hole">
        <gml:name>Sample road</gml:name><tran:class>1000</tran:class>
        <tran:function>1010</tran:function><tran:usage>1</tran:usage>
        <tran:lod2MultiSurface><gml:MultiSurface><gml:surfaceMember><gml:Polygon>
          <gml:exterior><gml:LinearRing><gml:posList>
            20 20 0 20 30 0 30 30 0 30 20 0 20 20 0
          </gml:posList></gml:LinearRing></gml:exterior>
        </gml:Polygon></gml:surfaceMember></gml:MultiSurface></tran:lod2MultiSurface>
        <tran:lod1MultiSurface><gml:MultiSurface><gml:surfaceMember><gml:Polygon>
          <gml:exterior><gml:LinearRing><gml:posList>
            0 0 0 0 10 0 10 10 0 10 0 0 0 0 0
          </gml:posList></gml:LinearRing></gml:exterior>
          <gml:interior><gml:LinearRing><gml:posList>
            3 3 0 3 7 0 7 7 0 7 3 0 3 3 0
          </gml:posList></gml:LinearRing></gml:interior>
        </gml:Polygon></gml:surfaceMember></gml:MultiSurface></tran:lod1MultiSurface>
      </tran:Road></core:cityObjectMember>
    </core:CityModel>"""
    records = list(
        iter_road_surfaces(
            BytesIO(xml), source_member="udx/tran/fixture.gml", source_member_crc32="abc12345"
        )
    )
    assert len(records) == 1
    record = records[0]
    assert record["surface_id"] == "road-with-hole:0"
    assert record["road_class"] == "1000"
    assert record["function_code"] == "1010"
    assert record["usage_code"] == "1"
    assert record["source_member"] == "udx/tran/fixture.gml"
    assert record["source_member_crc32"] == "abc12345"
    assert "depth" not in record
    assert record["geometry"].area == pytest.approx(84)
    assert len(record["geometry"].interiors) == 1


def _surface_fixture() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "surface_id": ["road-a:0", "road-b:0", "road-c:0"],
            "gml_id": ["road-a", "road-b", "road-c"],
        },
        geometry=[box(0, 0, 10, 10), box(10.04, 0, 20.04, 10), box(30, 0, 40, 10)],
        crs=ANALYSIS_CRS,
    )


def test_experimental_graph_reports_tolerance_bridge_and_components() -> None:
    nodes, edges, report = build_surface_adjacency_graph(
        _surface_fixture(), tolerance_m=0.05
    )
    assert len(nodes) == 3
    assert len(edges) == 1
    assert edges.iloc[0]["topology_relation"] == "tolerance_bridge"
    assert edges.iloc[0]["surface_gap_m"] == pytest.approx(0.04)
    assert edges.iloc[0]["length_m"] > 0
    referenced_nodes = set(edges["source_node_id"]) | set(edges["target_node_id"])
    assert referenced_nodes.issubset(set(nodes["node_id"]))
    assert nodes["component_id"].nunique() == 2
    assert report["components"] == 2
    assert report["tolerance_bridge_edges"] == 1
    assert report["graph_method"] == EXPERIMENTAL_GRAPH_METHOD
    assert report["pedestrian_network"] is False
    assert set(nodes["pedestrian_permission"]) == {"unknown"}
    assert set(edges["pedestrian_permission"]) == {"unknown"}


def test_experimental_graph_accepts_city_configured_projected_crs() -> None:
    surfaces = _surface_fixture().to_crs("EPSG:6677")
    nodes, edges, _ = build_surface_adjacency_graph(surfaces, tolerance_m=0.05)
    assert nodes.crs == surfaces.crs
    assert edges.crs == surfaces.crs


def _route_fixture() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    nodes = gpd.GeoDataFrame(
        {"node_id": ["a", "b", "c"]},
        geometry=[Point(0, 0), Point(1, 0), Point(2, 0)],
        crs=ANALYSIS_CRS,
    )
    edges = gpd.GeoDataFrame(
        {
            "edge_id": ["ab", "bc"],
            "source_node_id": ["a", "b"],
            "target_node_id": ["b", "c"],
            "length_m": [1.0, 1.0],
        },
        geometry=[LineString([(0, 0), (1, 0)]), LineString([(1, 0), (2, 0)])],
        crs=ANALYSIS_CRS,
    )
    return nodes, edges


def test_multi_source_dijkstra_is_deterministic_and_reconstructs_route() -> None:
    nodes, edges = _route_fixture()
    seeds = pd.DataFrame(
        {
            "node_id": ["c", "a"],
            "origin_to_node_distance_m": [0.0, 0.0],
            "facility_id": ["z-destination", "a-destination"],
            "facility_name": ["Z", "A"],
        }
    )
    result = multi_source_shortest_paths(
        nodes,
        edges,
        seeds,
        destination_id_column="facility_id",
        destination_name_column="facility_name",
    ).set_index("node_id")
    assert result.loc["b", "network_to_destination_distance_m"] == pytest.approx(1)
    assert result.loc["b", "destination_id"] == "a-destination"
    route_nodes, route_edges = reconstruct_route(result.reset_index(), "b")
    assert route_nodes == ["b", "a"]
    assert route_edges == ["ab"]


def test_point_snapping_keeps_surface_and_connector_distances_separate() -> None:
    surfaces = _surface_fixture().iloc[:2].copy()
    nodes, _, _ = build_surface_adjacency_graph(surfaces, tolerance_m=0.05)
    points = gpd.GeoDataFrame(
        {"origin_id": ["origin"]}, geometry=[Point(-2, 5)], crs=ANALYSIS_CRS
    )
    snapped = snap_points_to_surfaces(
        points, surfaces, nodes, id_column="origin_id"
    ).iloc[0]
    assert snapped["surface_id"] == "road-a:0"
    assert snapped["road_surface_distance_m"] == pytest.approx(2)
    assert snapped["origin_to_node_distance_m"] == pytest.approx(7)


def test_official_generator_adapter_normalizes_documented_fields(tmp_path: Path) -> None:
    node_path = tmp_path / "nodes.geojson"
    link_path = tmp_path / "links.geojson"
    gpd.GeoDataFrame(
        {"node_id": [1, 2], "elevation": [10.0, 11.0]},
        geometry=[Point(135.0, 35.0), Point(135.001, 35.0)],
        crs="EPSG:4326",
    ).to_file(node_path, driver="GeoJSON")
    gpd.GeoDataFrame(
        {"link_id": [7], "start_id": [1], "end_id": [2], "distance": [91.0]},
        geometry=[LineString([(135.0, 35.0), (135.001, 35.0)])],
        crs="EPSG:4326",
    ).to_file(link_path, driver="GeoJSON")

    nodes, edges, report = read_official_generator_output(
        node_path, link_path, network_type="walk", graph_version="official-test-v1"
    )
    assert nodes.crs.to_string() == ANALYSIS_CRS
    assert edges.crs.to_string() == ANALYSIS_CRS
    assert nodes["node_id"].tolist() == ["1", "2"]
    assert edges["edge_id"].tolist() == ["7"]
    assert edges["source_node_id"].tolist() == ["1"]
    assert edges["length_m"].tolist() == [91.0]
    assert set(nodes["graph_method"]) == {OFFICIAL_GRAPH_METHOD}
    assert report["pedestrian_network"] is True
    assert report["network_type"] == "walk"


def test_official_generator_adapter_rejects_missing_documented_fields(
    tmp_path: Path,
) -> None:
    node_path = tmp_path / "nodes.geojson"
    link_path = tmp_path / "links.geojson"
    gpd.GeoDataFrame(
        {"wrong_node_id": [1]}, geometry=[Point(135, 35)], crs="EPSG:4326"
    ).to_file(node_path, driver="GeoJSON")
    gpd.GeoDataFrame(
        {"link_id": [1], "start_id": [1], "end_id": [1], "distance": [1.0]},
        geometry=[LineString([(135, 35), (135.0001, 35)])],
        crs="EPSG:4326",
    ).to_file(link_path, driver="GeoJSON")
    with pytest.raises(ValueError, match="Official output columns missing"):
        read_official_generator_output(
            node_path, link_path, network_type="road", graph_version="invalid"
        )
