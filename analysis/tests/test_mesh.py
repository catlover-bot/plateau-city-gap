"""Synthetic regional mesh geometry tests."""

import math

import pandas as pd

from analysis.src.mesh import decode_500m_mesh, population_to_geodataframe


def test_500m_mesh_quadrants_partition_third_mesh() -> None:
    southwest = decode_500m_mesh("533537411")
    northeast = decode_500m_mesh("533537414")
    assert math.isclose(southwest.north, northeast.south)
    assert math.isclose(southwest.east, northeast.west)
    assert math.isclose(southwest.north - southwest.south, 1 / 240)
    assert math.isclose(southwest.east - southwest.west, 1 / 160)


def test_mesh_polygon_has_centroid_coordinates() -> None:
    result = population_to_geodataframe(pd.DataFrame({"mesh_code": ["533537411"]}))
    assert result.crs.to_epsg() == 6668
    assert result.geometry.iloc[0].is_valid
    assert result.geometry.iloc[0].contains(result.geometry.iloc[0].centroid)
    assert result.loc[0, "centroid_lat"] > 0
    assert result.loc[0, "centroid_lon"] > 100
