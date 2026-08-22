"""Synthetic geometry tests; no observation is a Maizuru result."""

import geopandas as gpd
from shapely.geometry import Point, box

from analysis.src.accessibility import METRIC_CRS, nearest_distance


def test_nearest_distance_in_metric_crs() -> None:
    areas = gpd.GeoDataFrame({"geometry": [box(0, 0, 10, 10)]}, crs=METRIC_CRS)
    targets = gpd.GeoDataFrame({"geometry": [Point(305, 405)]}, crs=METRIC_CRS)
    assert nearest_distance(areas, targets).iloc[0] == 500


def test_empty_targets_returns_missing() -> None:
    areas = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs=METRIC_CRS)
    targets = gpd.GeoDataFrame({"geometry": []}, crs=METRIC_CRS)
    assert nearest_distance(areas, targets).isna().all()

