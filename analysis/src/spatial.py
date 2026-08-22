"""Boundary filtering and facility-layer normalization."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely import normalize
from shapely.ops import polygonize, unary_union

from .mesh import GEOGRAPHIC_CRS


def boundary_from_plateau(border: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Polygonize the official PLATEAU administrative-border line layer."""
    if border.empty:
        raise ValueError("PLATEAU border layer is empty")
    source = border.set_crs(GEOGRAPHIC_CRS) if border.crs is None else border.to_crs(GEOGRAPHIC_CRS)
    polygons = list(polygonize(source.geometry.explode(index_parts=False)))
    if not polygons:
        raise ValueError("PLATEAU border linework could not be polygonized")
    geometry = unary_union(polygons)
    return gpd.GeoDataFrame(
        {"city_code": ["26202"], "city_name": ["舞鶴市"]},
        geometry=[geometry],
        crs=GEOGRAPHIC_CRS,
    )


def intersects_boundary(
    features: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Keep features intersecting the administrative polygon, never a bbox alone."""
    if features.crs is None:
        raise ValueError("Feature layer must declare a CRS")
    projected_boundary = boundary.to_crs(features.crs).geometry.union_all()
    return features.loc[features.geometry.intersects(projected_boundary)].copy()


def deduplicate_stations(stations: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Collapse route-level duplicate records at the same named station/location."""
    result = stations.copy()
    name_column = "駅名" if "駅名" in result else "station_name"
    result["station_name"] = result[name_column].astype("string").str.strip()
    result["_geometry_key"] = result.geometry.map(lambda value: normalize(value).wkb_hex)
    result = result.drop_duplicates(["station_name", "_geometry_key"]).drop(columns="_geometry_key")
    return result.reset_index(drop=True)


def filter_medical_primary(medical: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Select hospitals and general clinics (P04_001 codes 1 and 2)."""
    if "P04_001" not in medical:
        raise ValueError("Medical layer lacks P04_001")
    codes = pd.to_numeric(medical["P04_001"], errors="coerce")
    return medical.loc[codes.isin([1, 2])].copy()
