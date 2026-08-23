"""Run the shared, configuration-driven 500 m CITY GAP analysis engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely.geometry import Point

from .audit import classify_medical_access
from .city_config import CityConfig, DatasetConfig, load_city_config
from .distances import nearest_named
from .mesh import GEOGRAPHIC_CRS, population_to_geodataframe
from .population import add_population_metrics, read_estat_csv
from .ranking import add_candidate_rankings, add_eligibility_rank
from .spatial import (
    boundary_from_plateau,
    deduplicate_stations,
    filter_medical_primary,
    intersects_boundary,
)
from .validation import validate_real_metrics

matplotlib.use("Agg")
from matplotlib import pyplot as plt

OUTPUT_COLUMNS = [
    "mesh_code", "centroid_lat", "centroid_lon", "city_area_fraction",
    "centroid_within_city", "population", "elderly_population",
    "reported_elderly_population", "elderly_ratio", "HTKSYORI", "HTKSAKI",
    "GASSAN", "disclosure_status", "suppression_flag",
    "aggregation_target_flag", "aggregation_flag", "primary_eligible_disclosure",
    "nearest_station_name", "nearest_station_distance_m", "nearest_bus_stop_name",
    "nearest_bus_stop_distance_m", "nearest_public_transport_type",
    "nearest_public_transport_name", "nearest_public_transport_distance_m",
    "nearest_medical_name", "nearest_medical_distance_m", "nearest_hospital_name",
    "nearest_medical_access_class",
    "nearest_hospital_distance_m", "nearest_clinic_name", "nearest_clinic_distance_m",
    "elderly_population_percentile", "elderly_ratio_percentile",
    "transport_distance_percentile", "medical_distance_percentile",
    "exploratory_score_a", "exploratory_score_b", "exploratory_score_c",
    "rank_a_unfiltered", "rank_b_unfiltered", "rank_c_unfiltered",
    "pareto_frontier", "eligibility_population_threshold",
    "eligibility_elderly_threshold", "primary_eligible", "rank", "geometry",
]


def _to_jgd2011(layer: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if layer.crs is None:
        raise ValueError("Source layer does not declare a CRS")
    return layer.to_crs(GEOGRAPHIC_CRS)


def _nearest_columns(
    meshes: gpd.GeoDataFrame,
    targets: gpd.GeoDataFrame,
    *,
    name_column: str,
    prefix: str,
    analysis_crs: str,
) -> None:
    origins = gpd.GeoDataFrame(
        meshes[["mesh_code"]].copy(),
        geometry=[Point(xy) for xy in zip(meshes["centroid_lon"], meshes["centroid_lat"])],
        crs=GEOGRAPHIC_CRS,
    )
    nearest = nearest_named(origins, targets, name_column=name_column, analysis_crs=analysis_crs)
    meshes[f"nearest_{prefix}_name"] = nearest["name"]
    meshes[f"nearest_{prefix}_distance_m"] = nearest["distance_m"]


def _top_codes(metrics: pd.DataFrame, minimum_population: int, minimum_elderly: int) -> list[str]:
    eligible = metrics.loc[
        metrics["primary_eligible_disclosure"]
        & (metrics["population"] >= minimum_population)
        & (metrics["elderly_population"] >= minimum_elderly)
    ]
    return (
        eligible.sort_values(["exploratory_score_c", "mesh_code"], ascending=[False, True])
        .head(10)["mesh_code"]
        .astype(str)
        .tolist()
    )


def _json_default(value: object) -> object:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if pd.isna(value):
        return None
    raise TypeError(f"Cannot serialize {type(value)}")


def _dataset_metadata(dataset: DatasetConfig, *, source_records: int, city_records: int) -> dict[str, object]:
    return {
        "provider": dataset.provider,
        "title": dataset.title,
        "year": dataset.year,
        "license": dataset.license,
        "source_url": dataset.source_url,
        "declared_source_crs": dataset.source_crs,
        "source_records": source_records,
        "city_records": city_records,
    }


def _write_map(
    config: CityConfig,
    metrics: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
    stations: gpd.GeoDataFrame,
    buses: gpd.GeoDataFrame,
    medical: gpd.GeoDataFrame,
    path: Path,
) -> None:
    projected = metrics.to_crs(config.analysis_crs)
    top = projected.loc[projected["rank"].le(10)]
    fig, axis = plt.subplots(figsize=(10, 9))
    projected.plot(
        ax=axis, column="exploratory_score_c", cmap="YlOrRd", linewidth=0.2,
        edgecolor="#9b9b95", legend=True,
        missing_kwds={"color": "#ecebe6", "label": "not primary-ranked"},
    )
    boundary.to_crs(config.analysis_crs).boundary.plot(ax=axis, color="#252622", linewidth=1.2)
    buses.to_crs(config.analysis_crs).plot(ax=axis, color="#267aa0", markersize=5, label="bus stop")
    stations.to_crs(config.analysis_crs).plot(ax=axis, color="#2c514c", marker="s", markersize=24, label="station")
    medical.to_crs(config.analysis_crs).plot(ax=axis, color="#b35b35", marker="+", markersize=20, label="hospital/clinic")
    top.boundary.plot(ax=axis, color="#e0aa35", linewidth=2.1, label="primary Top 10")
    axis.set_axis_off()
    axis.legend(loc="lower right")
    axis.set_title(f"{config.city_name} 500 m CITY GAP QA — official real data")
    fig.text(
        0.5, 0.015,
        "Census 2020 + P11 2022 + P04 2020 + Project PLATEAU 2025; centroid-to-point straight-line distance",
        ha="center", fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def run_city_analysis(config: CityConfig) -> dict[str, object]:
    """Calculate and publish one city's real-data outputs with shared logic."""
    datasets = (config.population, config.boundary, config.stations, config.bus_stops, config.medical)
    for dataset in datasets:
        if not dataset.path.is_file():
            raise FileNotFoundError(f"Required input is missing: {dataset.path}")

    population_source = read_estat_csv(config.population.path)
    meshes = population_to_geodataframe(add_population_metrics(population_source))

    border_source = gpd.read_file(config.boundary.path)
    boundary = boundary_from_plateau(
        _to_jgd2011(border_source), city_code=config.city_code, city_name=config.city_name
    )
    meshes = intersects_boundary(meshes, boundary).reset_index(drop=True)
    projected_meshes = meshes.to_crs(config.analysis_crs)
    projected_city = boundary.to_crs(config.analysis_crs).geometry.union_all()
    meshes["city_area_fraction"] = projected_meshes.geometry.intersection(projected_city).area.div(projected_meshes.geometry.area)
    city_geographic = boundary.geometry.union_all()
    meshes["centroid_within_city"] = [
        city_geographic.covers(Point(longitude, latitude))
        for longitude, latitude in zip(meshes["centroid_lon"], meshes["centroid_lat"])
    ]

    station_source = gpd.read_file(config.stations.path)
    stations_raw = _to_jgd2011(station_source)
    stations_city = intersects_boundary(stations_raw, boundary)
    station_location_count = stations_city.geometry.map(lambda item: item.wkb_hex).nunique()
    stations = deduplicate_stations(stations_city)

    bus_source = gpd.read_file(config.bus_stops.path)
    buses_raw = _to_jgd2011(bus_source)
    buses = intersects_boundary(buses_raw, boundary).reset_index(drop=True)

    medical_source = gpd.read_file(config.medical.path)
    medical_raw = _to_jgd2011(medical_source)
    medical_city = intersects_boundary(medical_raw, boundary).reset_index(drop=True)
    category = pd.to_numeric(medical_city["P04_001"], errors="coerce")
    hospitals = medical_city.loc[category.eq(1)].copy()
    clinics = medical_city.loc[category.eq(2)].copy()
    dental = medical_city.loc[category.eq(3)].copy()
    medical_primary = filter_medical_primary(medical_city)
    medical_access = classify_medical_access(medical_primary["P04_002"])
    medical_primary = medical_primary.join(medical_access)

    nearest_inputs = (
        (stations, "station_name", "station"),
        (buses, "P11_001", "bus_stop"),
        (medical_primary, "P04_002", "medical"),
        (hospitals, "P04_002", "hospital"),
        (clinics, "P04_002", "clinic"),
    )
    for targets, name_column, prefix in nearest_inputs:
        _nearest_columns(
            meshes, targets, name_column=name_column, prefix=prefix,
            analysis_crs=config.analysis_crs,
        )

    access_by_name = (
        medical_primary[["P04_002", "medical_access_class"]]
        .drop_duplicates("P04_002")
        .set_index("P04_002")["medical_access_class"]
    )
    meshes["nearest_medical_access_class"] = meshes["nearest_medical_name"].map(
        access_by_name
    )

    station_is_nearest = meshes["nearest_station_distance_m"] <= meshes["nearest_bus_stop_distance_m"]
    meshes["nearest_public_transport_type"] = np.where(station_is_nearest, "station", "bus_stop")
    meshes["nearest_public_transport_name"] = np.where(
        station_is_nearest, meshes["nearest_station_name"], meshes["nearest_bus_stop_name"]
    )
    meshes["nearest_public_transport_distance_m"] = meshes[
        ["nearest_station_distance_m", "nearest_bus_stop_distance_m"]
    ].min(axis=1)

    # Boundary-edge cells can contain population outside the municipality. Keep
    # them in the published geometry, but use centroid-inside cells for the
    # city-relative percentile comparison and primary ranking.
    boundary_scope = (
        meshes["centroid_within_city"]
        if config.require_centroid_within_city
        else pd.Series(True, index=meshes.index)
    )
    primary_comparison = meshes["primary_eligible_disclosure"] & boundary_scope
    primary_index = meshes.index[primary_comparison]
    ranked = add_candidate_rankings(meshes.loc[primary_index])
    for column in (column for column in ranked if column not in meshes):
        meshes[column] = pd.NA
        meshes.loc[primary_index, column] = ranked[column]
    meshes = add_eligibility_rank(
        meshes,
        minimum_population=config.minimum_population,
        minimum_elderly=config.minimum_elderly_population,
    )
    metrics = meshes[OUTPUT_COLUMNS].copy()
    validation_checks = validate_real_metrics(
        metrics,
        minimum_population=config.minimum_population,
        minimum_elderly=config.minimum_elderly_population,
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = config.output_prefix
    metrics.drop(columns="geometry").to_csv(config.output_dir / f"{prefix}_mesh_metrics.csv", index=False)
    metrics.to_file(config.output_dir / f"{prefix}_city_gap.geojson", driver="GeoJSON")
    top10 = metrics.loc[metrics["rank"].le(10)].sort_values("rank")
    leading_columns = [
        "rank", "mesh_code", "centroid_lat", "centroid_lon", "population",
        "elderly_population", "elderly_ratio", "nearest_station_distance_m",
        "nearest_bus_stop_distance_m", "nearest_public_transport_distance_m",
        "nearest_medical_distance_m", "exploratory_score_c", "pareto_frontier", "suppression_flag",
    ]
    top10_csv = top10.drop(columns="geometry")
    top10_csv = top10_csv[leading_columns + [column for column in top10_csv if column not in leading_columns]]
    top10_csv.to_csv(config.output_dir / f"{prefix}_city_gap_top10.csv", index=False)
    _write_map(
        config, metrics, boundary, stations, buses, medical_primary,
        config.output_dir / f"{prefix}_city_gap_overview.png",
    )

    threshold_sets = {
        "none": _top_codes(meshes, 0, 0),
        "population_10_elderly_5": _top_codes(meshes, 10, 5),
        "population_20_elderly_10": _top_codes(meshes, 20, 10),
        "population_50_elderly_20": _top_codes(meshes, 50, 20),
    }
    baseline = set(threshold_sets["population_20_elderly_10"])
    threshold_stability = {
        name: {"top10_mesh_codes": codes, "overlap_with_primary_top10": len(baseline.intersection(codes))}
        for name, codes in threshold_sets.items()
    }
    crs = CRS.from_user_input(config.analysis_crs)
    top1 = None
    if not top10.empty:
        top1 = {
            key: None if pd.isna(value) else value
            for key, value in top10.iloc[0].drop(labels="geometry").to_dict().items()
        }
    comparison_latitude = float(
        metrics.loc[primary_comparison, "centroid_lat"].median()
    )
    top10_north_count = int((top10["centroid_lat"] > comparison_latitude).sum())
    counts = {
        "population_prefecture": len(population_source),
        "population_meshes_intersecting_city": len(meshes),
        "population_unaffected": int(primary_comparison.sum()),
        "population_disclosure_unaffected": int(meshes["primary_eligible_disclosure"].sum()),
        "population_suppressed_source": int(meshes["suppression_flag"].sum()),
        "population_aggregation_destination": int(meshes["aggregation_target_flag"].sum()),
        "stations_raw": len(stations_raw),
        "stations_within_city": len(stations_city),
        "station_unique_locations": station_location_count,
        "station_unique_names": int(stations_city["駅名"].nunique()),
        "station_deduplicated": len(stations),
        "bus_stops_prefecture": len(buses_raw),
        "bus_stops_city": len(buses),
        "medical_prefecture": len(medical_raw),
        "medical_city": len(medical_city),
        "hospitals_city": len(hospitals),
        "clinics_city": len(clinics),
        "dental_clinics_city": len(dental),
        "medical_primary_city": len(medical_primary),
        "medical_uncertain_access_city": int(
            medical_primary["medical_access_class"].eq("uncertain_access").sum()
        ),
        "primary_rank_eligible_meshes": int(meshes["primary_eligible"].sum()),
    }
    summary: dict[str, object] = {
        "schema_version": "1.0.0",
        "city": {
            "id": config.city_id, "code": config.city_code, "name": config.city_name,
            "prefecture": config.prefecture_name, "mode": config.mode, "map_view": config.map_view,
        },
        "analysis_status": "real data",
        "generated_from_synthetic_data": False,
        "distance_method": "centroid-to-point straight-line (Euclidean) distance",
        "analysis_crs": {
            "code": config.analysis_crs, "name": crs.name,
            "area_of_use": crs.area_of_use.name, "bounds": list(crs.area_of_use.bounds),
        },
        "record_counts": counts,
        "datasets": {
            "population": _dataset_metadata(config.population, source_records=len(population_source), city_records=len(meshes)),
            "boundary": _dataset_metadata(config.boundary, source_records=len(border_source), city_records=len(boundary)),
            "stations": _dataset_metadata(config.stations, source_records=len(stations_raw), city_records=len(stations)),
            "bus_stops": _dataset_metadata(config.bus_stops, source_records=len(buses_raw), city_records=len(buses)),
            "medical": _dataset_metadata(config.medical, source_records=len(medical_raw), city_records=len(medical_primary)),
            "plateau": config.plateau_dataset,
        },
        "crs_transform_log": {
            "boundary": {"original": str(border_source.crs), "analysis": config.analysis_crs, "transformed_records": len(boundary)},
            "population": {"original": GEOGRAPHIC_CRS, "analysis": config.analysis_crs, "transformed_records": len(meshes)},
            "stations": {"original": str(station_source.crs), "analysis": config.analysis_crs, "transformed_records": len(stations)},
            "bus_stops": {"original": str(bus_source.crs), "analysis": config.analysis_crs, "transformed_records": len(buses)},
            "medical_primary": {"original": str(medical_source.crs), "analysis": config.analysis_crs, "transformed_records": len(medical_primary)},
        },
        "primary_ranking": {
            "score": "elderly_population_percentile * transport_distance_percentile * medical_distance_percentile",
            "minimum_population": config.minimum_population,
            "minimum_elderly_population": config.minimum_elderly_population,
            "require_centroid_within_city": config.require_centroid_within_city,
            "top1": top1,
            "comparison_scope": "Percentiles are calculated within this city only and cannot be compared across cities.",
        },
        "spatial_sanity": {
            "comparison_median_latitude": comparison_latitude,
            "top10_north_of_city_mesh_median": top10_north_count,
            "top10_south_of_or_at_city_mesh_median": len(top10) - top10_north_count,
        },
        "threshold_stability": threshold_stability,
        "validation_checks": validation_checks,
        "limitations": [
            "Distances are straight-line Euclidean distances, not walking or route distances.",
            "P11 2022 excludes demand, highway and facility shuttle buses and does not measure service frequency.",
            "P04 represents facilities collected for July 2020, not current availability.",
            "P04 hospital/clinic records with institutional names are flagged as uncertain access but retained in the primary baseline; see final_audit.json for exclusion sensitivity.",
            "Suppressed sources and aggregation destinations are retained but excluded from primary ranks.",
            "Percentile scores are city-relative; absolute scores must not be compared between cities.",
            "A high score is an exploratory prompt for field investigation, not proof of a local problem.",
        ],
    }
    (config.output_dir / f"{prefix}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_city_analysis(load_city_config(args.config))
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default, allow_nan=False))


if __name__ == "__main__":
    main()
