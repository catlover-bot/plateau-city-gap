"""Synthetic output-contract test; not a Maizuru result."""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from analysis.src.validation import validate_real_metrics


def test_valid_top10_contract() -> None:
    frame = gpd.GeoDataFrame(
        {
            "mesh_code": [str(index) for index in range(10)],
            "rank": pd.Series(range(1, 11), dtype="Int64"),
            "primary_eligible_disclosure": [True] * 10,
            "population": [20] * 10,
            "elderly_population": [10] * 10,
            "centroid_within_city": [True] * 10,
            "nearest_station_distance_m": [1.0] * 10,
            "nearest_bus_stop_distance_m": [1.0] * 10,
            "nearest_public_transport_distance_m": [1.0] * 10,
            "nearest_medical_distance_m": [1.0] * 10,
        },
        geometry=[Point(index, index) for index in range(10)],
        crs="EPSG:6674",
    )
    assert validate_real_metrics(frame)["top10_count"] == 10
