"""Nearest-name and Euclidean-distance calculations in a projected CRS."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd


def nearest_named(
    origins: gpd.GeoDataFrame,
    targets: gpd.GeoDataFrame,
    *,
    name_column: str,
    analysis_crs: str,
) -> pd.DataFrame:
    """Return nearest target name and straight-line distance for every origin."""
    if origins.crs is None or targets.crs is None:
        raise ValueError("Origins and targets must declare CRS")
    if targets.empty:
        return pd.DataFrame(
            {"name": pd.Series(pd.NA, index=origins.index), "distance_m": np.nan},
            index=origins.index,
        )
    projected_origins = origins.to_crs(analysis_crs)
    projected_targets = targets.to_crs(analysis_crs)
    rows: list[dict[str, object]] = []
    for point in projected_origins.geometry:
        distances = projected_targets.geometry.distance(point)
        target_index = distances.idxmin()
        rows.append(
            {
                "name": targets.loc[target_index, name_column],
                "distance_m": float(distances.loc[target_index]),
            }
        )
    return pd.DataFrame(rows, index=origins.index)
