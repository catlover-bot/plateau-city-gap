"""Synthetic spatial fixtures; no geometry represents Maizuru."""

import geopandas as gpd
from shapely.geometry import LineString, Point, box

from analysis.src.mesh import GEOGRAPHIC_CRS
from analysis.src.spatial import (
    boundary_from_plateau,
    deduplicate_stations,
    filter_medical_primary,
    intersects_boundary,
)


def test_boundary_filter_uses_polygon_intersection() -> None:
    border = gpd.GeoDataFrame(
        geometry=[LineString([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
        crs=GEOGRAPHIC_CRS,
    )
    boundary = boundary_from_plateau(border)
    features = gpd.GeoDataFrame(
        {"id": ["inside", "outside"]},
        geometry=[box(0.2, 0.2, 0.3, 0.3), box(2, 2, 3, 3)],
        crs=GEOGRAPHIC_CRS,
    )
    assert intersects_boundary(features, boundary)["id"].tolist() == ["inside"]


def test_hospital_and_clinic_filter_excludes_dentistry() -> None:
    medical = gpd.GeoDataFrame(
        {"P04_001": [1, "2", 3]},
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2)],
        crs=GEOGRAPHIC_CRS,
    )
    assert len(filter_medical_primary(medical)) == 2


def test_duplicate_station_name_and_location_is_collapsed() -> None:
    stations = gpd.GeoDataFrame(
        {"駅名": ["同一駅", "同一駅", "別駅"]},
        geometry=[Point(1, 1), Point(1, 1), Point(2, 2)],
        crs=GEOGRAPHIC_CRS,
    )
    result = deduplicate_stations(stations)
    assert result["station_name"].tolist() == ["同一駅", "別駅"]
