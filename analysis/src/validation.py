"""Output-contract checks for a completed real-data analysis."""

from __future__ import annotations

import geopandas as gpd


def validate_real_metrics(
    metrics: gpd.GeoDataFrame,
    *,
    minimum_population: int = 20,
    minimum_elderly: int = 10,
) -> dict[str, bool | int]:
    distance_columns = [
        "nearest_station_distance_m",
        "nearest_bus_stop_distance_m",
        "nearest_public_transport_distance_m",
        "nearest_medical_distance_m",
    ]
    top10 = metrics.loc[metrics["rank"].le(10)].sort_values("rank")
    checks: dict[str, bool | int] = {
        "mesh_codes_unique": bool(metrics["mesh_code"].is_unique),
        "geometries_valid": bool(metrics.geometry.notna().all() and metrics.geometry.is_valid.all()),
        "top10_count": len(top10),
        "top10_ranks_1_to_10": top10["rank"].astype(int).tolist() == list(range(1, 11)),
        "top10_disclosure_unaffected": bool(top10["primary_eligible_disclosure"].all()),
        "top10_population_thresholds": bool(
            (top10["population"] >= minimum_population).all()
            & (top10["elderly_population"] >= minimum_elderly).all()
        ),
        "top10_centroids_within_city": bool(top10["centroid_within_city"].all()),
        "distances_nonnegative": bool((metrics[distance_columns] >= 0).all().all()),
    }
    failed = [name for name, value in checks.items() if value is False]
    if checks["top10_count"] != 10:
        failed.append("top10_count")
    if failed:
        raise ValueError(f"Real output validation failed: {', '.join(failed)}")
    return checks
