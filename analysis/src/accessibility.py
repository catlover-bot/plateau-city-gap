"""Euclidean nearest-facility accessibility calculations."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

METRIC_CRS = "EPSG:6674"  # JGD2011 / Japan Plane Rectangular CS VI (Kyoto)


def nearest_distance(areas: gpd.GeoDataFrame, targets: gpd.GeoDataFrame) -> pd.Series:
    """Distance in metres from each area representative point to its nearest target."""
    if areas.crs is None or targets.crs is None:
        raise ValueError("Both layers must declare a CRS")
    if targets.empty:
        return pd.Series(float("nan"), index=areas.index, dtype="float64")
    origins = areas.to_crs(METRIC_CRS).geometry.representative_point()
    destinations = targets.to_crs(METRIC_CRS).geometry
    return origins.apply(lambda point: float(destinations.distance(point).min()))
