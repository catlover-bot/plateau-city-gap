"""Pure building-demographic allocation and accessibility calculations."""

from __future__ import annotations

from typing import Literal

import geopandas as gpd
import numpy as np
import pandas as pd

STRICT_RESIDENTIAL_CODES = frozenset({"411", "412"})
MIXED_RESIDENTIAL_CODES = frozenset({"413", "414", "415"})
UNCERTAIN_CODES = frozenset({"461"})
INVALID_SENTINELS = frozenset({-9999.0, 9999.0})
POLICY_CODES = {
    "strict_residential": STRICT_RESIDENTIAL_CODES,
    "residential_plus_mixed": STRICT_RESIDENTIAL_CODES | MIXED_RESIDENTIAL_CODES,
}


def classify_usage(code: object) -> str:
    value = "" if pd.isna(code) else str(code).strip()
    if value in STRICT_RESIDENTIAL_CODES:
        return "residential"
    if value in MIXED_RESIDENTIAL_CODES:
        return "mixed_residential"
    if not value or value in UNCERTAIN_CODES:
        return "uncertain"
    return "non_residential"


def numeric_values(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce")


def valid_area(values: pd.Series) -> pd.Series:
    numeric = numeric_values(values)
    return numeric.notna() & np.isfinite(numeric) & numeric.gt(0) & ~numeric.isin(INVALID_SENTINELS)


def valid_storeys(values: pd.Series) -> pd.Series:
    numeric = numeric_values(values)
    return (
        numeric.notna()
        & np.isfinite(numeric)
        & numeric.ge(1)
        & numeric.le(200)
        & ~numeric.isin(INVALID_SENTINELS)
    )


def assign_capacity(buildings: pd.DataFrame) -> pd.DataFrame:
    """Apply the audited, explicit area hierarchy without clamping invalid data."""

    result = buildings.copy()
    total = numeric_values(result["totalFloorArea"])
    footprint = numeric_values(result["buildingFootprintArea"])
    storeys = numeric_values(result["storeysAboveGround"])
    total_valid = valid_area(result["totalFloorArea"])
    footprint_valid = valid_area(result["buildingFootprintArea"])
    storeys_valid = valid_storeys(result["storeysAboveGround"])

    result["allocation_weight"] = np.nan
    result["allocation_weight_source"] = "not_allocatable"
    result.loc[footprint_valid, "allocation_weight"] = footprint.loc[footprint_valid]
    result.loc[footprint_valid, "allocation_weight_source"] = "footprint_only"
    estimated = footprint_valid & storeys_valid
    result.loc[estimated, "allocation_weight"] = footprint.loc[estimated] * storeys.loc[estimated]
    result.loc[estimated, "allocation_weight_source"] = "footprint_times_storeys"
    result.loc[total_valid, "allocation_weight"] = total.loc[total_valid]
    result.loc[total_valid, "allocation_weight_source"] = "total_floor_area"
    return result


def building_mesh_crosswalk(
    buildings: gpd.GeoDataFrame, meshes: gpd.GeoDataFrame
) -> pd.DataFrame:
    """Intersect footprints with meshes and retain exact positive-area fractions."""

    if buildings.crs is None or meshes.crs is None or buildings.crs != meshes.crs:
        raise ValueError("Buildings and meshes must use the same declared CRS")
    source = buildings.loc[buildings.geometry.notna() & ~buildings.geometry.is_empty].copy()
    candidates = gpd.sjoin(
        source,
        meshes[["mesh_code", "geometry"]],
        how="inner",
        predicate="intersects",
    )
    mesh_geometries = meshes.geometry
    candidates["geometry_footprint_area"] = candidates.geometry.area
    candidates["intersection_area"] = [
        geometry.intersection(mesh_geometries.loc[index]).area
        for geometry, index in zip(candidates.geometry, candidates["index_right"], strict=True)
    ]
    candidates = candidates.loc[
        candidates["intersection_area"].gt(0)
        & candidates["geometry_footprint_area"].gt(0)
    ].copy()
    candidates["intersection_fraction"] = (
        candidates["intersection_area"] / candidates["geometry_footprint_area"]
    )
    if candidates["intersection_fraction"].gt(1 + 1e-9).any():
        raise ValueError("Building/mesh intersection fraction exceeds one")
    return pd.DataFrame(candidates.drop(columns=["geometry", "index_right"]))


def allocate_by_mesh(
    crosswalk: pd.DataFrame,
    meshes: pd.DataFrame,
    *,
    policy: Literal["strict_residential", "residential_plus_mixed"],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate safe mesh totals using effective floor area and enforce conservation."""

    eligible_codes = POLICY_CODES[policy]
    rows = crosswalk.loc[
        crosswalk["usage_code"].astype(str).isin(eligible_codes)
        & crosswalk["allocation_weight"].gt(0)
    ].copy()
    rows["effective_floor_area_in_mesh"] = (
        rows["allocation_weight"] * rows["intersection_fraction"]
    )
    mesh_values = meshes.set_index("mesh_code")
    rows = rows.loc[
        rows["mesh_code"].isin(
            mesh_values.index[mesh_values["primary_eligible_disclosure"].astype(bool)]
        )
    ].copy()
    totals = rows.groupby("mesh_code")["effective_floor_area_in_mesh"].transform("sum")
    rows["allocation_fraction"] = rows["effective_floor_area_in_mesh"] / totals
    rows["estimated_population"] = rows["allocation_fraction"] * rows["mesh_code"].map(
        mesh_values["population"]
    )
    rows["estimated_elderly_population"] = rows["allocation_fraction"] * rows[
        "mesh_code"
    ].map(mesh_values["elderly_population"])
    rows["population_resolution"] = "building_estimate"
    rows["allocation_method"] = policy

    allocated = rows.groupby("mesh_code").agg(
        allocated_population=("estimated_population", "sum"),
        allocated_elderly=("estimated_elderly_population", "sum"),
        eligible_buildings=("gml_id", "nunique"),
        weight_sum=("effective_floor_area_in_mesh", "sum"),
    )
    conservation = mesh_values[["population", "elderly_population"]].join(allocated, how="left")
    conservation["population_error"] = (
        conservation["allocated_population"] - conservation["population"]
    )
    conservation["elderly_error"] = (
        conservation["allocated_elderly"] - conservation["elderly_population"]
    )
    tested = conservation["allocated_population"].notna()
    if not np.allclose(
        conservation.loc[tested, "allocated_population"],
        conservation.loc[tested, "population"],
        rtol=0,
        atol=1e-9,
    ):
        raise ValueError("Population conservation failed")
    if not np.allclose(
        conservation.loc[tested, "allocated_elderly"],
        conservation.loc[tested, "elderly_population"],
        rtol=0,
        atol=1e-9,
    ):
        raise ValueError("Elderly population conservation failed")
    return rows, conservation.reset_index()


def weighted_quantile(values: pd.Series, weights: pd.Series, quantile: float) -> float:
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between zero and one")
    frame = pd.DataFrame({"value": values, "weight": weights}).dropna()
    frame = frame.loc[frame["weight"].gt(0)].sort_values("value", kind="stable")
    if frame.empty:
        return float("nan")
    threshold = quantile * frame["weight"].sum()
    index = frame["weight"].cumsum().ge(threshold).idxmax()
    return float(frame.loc[index, "value"])


def weighted_statistics(values: pd.Series, weights: pd.Series) -> dict[str, float]:
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return {"mean": float("nan"), "median": float("nan"), "p90": float("nan")}
    return {
        "mean": float(np.average(values.loc[valid], weights=weights.loc[valid])),
        "median": weighted_quantile(values.loc[valid], weights.loc[valid], 0.5),
        "p90": weighted_quantile(values.loc[valid], weights.loc[valid], 0.9),
    }


def nearest_facility(
    origins: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    *,
    name_column: str,
    type_column: str | None = None,
) -> pd.DataFrame:
    """Spatial-index nearest lookup in a metric CRS, with deterministic tie-breaking."""

    if origins.crs is None or facilities.crs is None or origins.crs != facilities.crs:
        raise ValueError("Origins and facilities must use the same declared CRS")
    if facilities.empty:
        return pd.DataFrame(index=origins.index, columns=["name", "type", "distance_m"])
    facility_columns = [name_column, "geometry"]
    if type_column:
        facility_columns.insert(1, type_column)
    left = origins[["geometry"]].copy()
    left["_origin_index"] = origins.index
    joined = gpd.sjoin_nearest(
        left,
        facilities[facility_columns],
        how="left",
        distance_col="distance_m",
    )
    joined["_name_sort"] = joined[name_column].astype(str)
    joined = joined.sort_values(["_origin_index", "distance_m", "_name_sort"]).drop_duplicates(
        "_origin_index"
    )
    result = pd.DataFrame(index=origins.index)
    indexed = joined.set_index("_origin_index")
    result["name"] = indexed[name_column].reindex(result.index)
    result["type"] = indexed[type_column].reindex(result.index) if type_column else pd.NA
    result["distance_m"] = indexed["distance_m"].reindex(result.index)
    return result
