import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from analysis.src.plateau_road_network import ANALYSIS_CRS
from analysis.src.plateau_terrain import (
    assign_dem_elevations,
    attach_edge_terrain,
    calculate_route_terrain,
)

DEM_GML = """<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
 xmlns:gml="http://www.opengis.net/gml"
 xmlns:dem="http://www.opengis.net/citygml/relief/2.0">
 <gml:boundedBy><gml:Envelope srsName="http://www.opengis.net/def/crs/EPSG/0/6697">
  <gml:lowerCorner>34.99 134.99 0</gml:lowerCorner>
  <gml:upperCorner>35.02 135.02 20</gml:upperCorner>
 </gml:Envelope></gml:boundedBy>
 <core:cityObjectMember><dem:ReliefFeature gml:id="dem-1"><dem:lod>1</dem:lod>
  <dem:reliefComponent><dem:TINRelief><dem:tin><gml:TriangulatedSurface>
   <gml:trianglePatches><gml:Triangle><gml:exterior><gml:LinearRing>
    <gml:posList>35 135 10 35 135.01 20 35.01 135 30 35 135 10</gml:posList>
   </gml:LinearRing></gml:exterior></gml:Triangle></gml:trianglePatches>
  </gml:TriangulatedSurface></dem:tin></dem:TINRelief></dem:reliefComponent>
 </dem:ReliefFeature></core:cityObjectMember>
</core:CityModel>"""


def test_dem_tin_barycentric_interpolation_preserves_missing_coverage(tmp_path: Path) -> None:
    archive_path = tmp_path / "dem.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("udx/dem/fixture.gml", DEM_GML)
    geographic = gpd.GeoDataFrame(
        {"node_id": ["inside", "outside"]},
        geometry=[Point(135.0025, 35.0025), Point(135.018, 35.018)],
        crs="EPSG:4326",
    )
    nodes = geographic.to_crs(ANALYSIS_CRS)

    elevations, report = assign_dem_elevations(archive_path, nodes)
    result = elevations.set_index("node_id")
    assert result.loc["inside", "elevation_m"] == pytest.approx(17.5)
    assert pd.isna(result.loc["outside", "elevation_m"])
    assert result.loc["inside", "terrain_triangle_index"] == 0
    assert report["nodes_with_elevation"] == 1
    assert report["node_terrain_coverage"] == 0.5
    assert report["members"][0]["status"] == "processed_with_gaps"


def test_edge_and_route_terrain_remain_separate_from_distance() -> None:
    nodes = pd.DataFrame(
        {"node_id": ["a", "b", "c"], "elevation_m": [10.0, 20.0, 15.0]}
    )
    edges = pd.DataFrame(
        {
            "edge_id": ["ab", "bc"],
            "source_node_id": ["a", "b"],
            "target_node_id": ["b", "c"],
            "length_m": [100.0, 50.0],
        }
    )
    enriched, edge_report = attach_edge_terrain(nodes, edges)
    assert enriched["length_m"].tolist() == [100.0, 50.0]
    assert enriched["absolute_grade_percent"].tolist() == [10.0, 10.0]
    assert edge_report["edge_terrain_coverage"] == 1

    routing = pd.DataFrame(
        {
            "node_id": ["a", "b", "c"],
            "network_to_destination_distance_m": [150.0, 50.0, 0.0],
            "predecessor_node_id": ["b", "c", None],
            "predecessor_edge_id": ["ab", "bc", None],
        }
    )
    terrain = calculate_route_terrain(nodes, edges, routing).set_index("node_id")
    assert terrain.loc["a", "route_graph_length_m"] == 150
    assert terrain.loc["a", "route_ascent_m"] == 10
    assert terrain.loc["a", "route_descent_m"] == 5
    assert terrain.loc["a", "maximum_observed_absolute_grade_percent"] == 10
    assert terrain.loc["a", "terrain_route_status"] == "available"


def test_missing_elevation_yields_partial_route_not_invented_value() -> None:
    nodes = pd.DataFrame(
        {"node_id": ["a", "b", "c"], "elevation_m": [10.0, None, 15.0]}
    )
    edges = pd.DataFrame(
        {
            "edge_id": ["ab", "bc"],
            "source_node_id": ["a", "b"],
            "target_node_id": ["b", "c"],
            "length_m": [100.0, 50.0],
        }
    )
    routing = pd.DataFrame(
        {
            "node_id": ["a", "b", "c"],
            "network_to_destination_distance_m": [150.0, 50.0, 0.0],
            "predecessor_node_id": ["b", "c", None],
            "predecessor_edge_id": ["ab", "bc", None],
        }
    )
    terrain = calculate_route_terrain(nodes, edges, routing).set_index("node_id")
    assert terrain.loc["a", "terrain_route_status"] == "unavailable"
    assert pd.isna(terrain.loc["a", "route_ascent_m"])
    assert pd.isna(terrain.loc["a", "route_descent_m"])
