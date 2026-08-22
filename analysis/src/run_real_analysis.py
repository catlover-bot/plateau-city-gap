"""Run the real-data Maizuru 500 m CITY GAP analysis end to end."""

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

from .accessibility import METRIC_CRS
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

DEFAULTS = {
    "population": Path("data/raw/population/tblT001192H26/tblT001192H26.txt"),
    "border": Path(
        "data/raw/plateau_related/26202_maizuru-shi_city_2025_border.geojson"
    ),
    "stations": Path(
        "data/raw/plateau_related/26202_maizuru-shi_city_2025_station.geojson"
    ),
    "bus_stops": Path(
        "data/raw/transport/P11-22_26_SHP/P11-22_26_SHP/P11-22_26.geojson"
    ),
    "medical": Path("data/raw/medical/P04-20_26_GML/P04-20_26_GML/P04-20_26.geojson"),
    "output_dir": Path("analysis/outputs/real"),
}

OUTPUT_COLUMNS = [
    "mesh_code",
    "centroid_lat",
    "centroid_lon",
    "maizuru_area_fraction",
    "centroid_within_maizuru",
    "population",
    "elderly_population",
    "reported_elderly_population",
    "elderly_ratio",
    "HTKSYORI",
    "HTKSAKI",
    "GASSAN",
    "disclosure_status",
    "suppression_flag",
    "aggregation_target_flag",
    "aggregation_flag",
    "primary_eligible_disclosure",
    "nearest_station_name",
    "nearest_station_distance_m",
    "nearest_bus_stop_name",
    "nearest_bus_stop_distance_m",
    "nearest_public_transport_type",
    "nearest_public_transport_name",
    "nearest_public_transport_distance_m",
    "nearest_medical_name",
    "nearest_medical_distance_m",
    "nearest_hospital_name",
    "nearest_hospital_distance_m",
    "nearest_clinic_name",
    "nearest_clinic_distance_m",
    "elderly_population_percentile",
    "elderly_ratio_percentile",
    "transport_distance_percentile",
    "medical_distance_percentile",
    "exploratory_score_a",
    "exploratory_score_b",
    "exploratory_score_c",
    "rank_a_unfiltered",
    "rank_b_unfiltered",
    "rank_c_unfiltered",
    "pareto_frontier",
    "eligibility_population_threshold",
    "eligibility_elderly_threshold",
    "primary_eligible",
    "rank",
    "geometry",
]


def _to_jgd2011(layer: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize declared source coordinates to JGD2011 geographic."""
    if layer.crs is None:
        raise ValueError("Source layer does not declare a CRS")
    return layer.to_crs(GEOGRAPHIC_CRS)


def _nearest_columns(
    meshes: gpd.GeoDataFrame,
    targets: gpd.GeoDataFrame,
    *,
    name_column: str,
    prefix: str,
) -> None:
    origins = gpd.GeoDataFrame(
        meshes[["mesh_code"]].copy(),
        geometry=[Point(xy) for xy in zip(meshes["centroid_lon"], meshes["centroid_lat"])],
        crs=GEOGRAPHIC_CRS,
    )
    nearest = nearest_named(
        origins, targets, name_column=name_column, analysis_crs=METRIC_CRS
    )
    meshes[f"nearest_{prefix}_name"] = nearest["name"]
    meshes[f"nearest_{prefix}_distance_m"] = nearest["distance_m"]


def _top_codes(
    metrics: pd.DataFrame, minimum_population: int, minimum_elderly: int
) -> list[str]:
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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    raise TypeError(f"Cannot serialize {type(value)}")


def _write_map(
    metrics: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
    stations: gpd.GeoDataFrame,
    buses: gpd.GeoDataFrame,
    medical: gpd.GeoDataFrame,
    path: Path,
) -> None:
    projected = metrics.to_crs(METRIC_CRS)
    projected_boundary = boundary.to_crs(METRIC_CRS)
    projected_buses = buses.to_crs(METRIC_CRS)
    projected_stations = stations.to_crs(METRIC_CRS)
    projected_medical = medical.to_crs(METRIC_CRS)
    top = projected.loc[projected["rank"].le(10)]
    fig, axes = plt.subplots(1, 2, figsize=(16, 9))
    for index, axis in enumerate(axes):
        projected.plot(
            ax=axis,
            column="exploratory_score_c",
            cmap="YlOrRd",
            linewidth=0.15,
            edgecolor="#999999",
            legend=index == 1,
            missing_kwds={"color": "#eeeeee", "label": "not primary-ranked"},
        )
        projected_boundary.boundary.plot(ax=axis, color="black", linewidth=1.0)
        projected_buses.plot(ax=axis, color="#1976d2", markersize=4, label="bus stop")
        projected_stations.plot(
            ax=axis, color="#6a1b9a", marker="s", markersize=22, label="station"
        )
        projected_medical.plot(
            ax=axis, color="#00897b", marker="+", markersize=18, label="hospital/clinic"
        )
        top.boundary.plot(ax=axis, color="#00e5ff", linewidth=2.2, label="primary Top 10")
        axis.set_axis_off()
    axes[0].set_title("Full administrative extent")
    axes[1].set_title("Populated-mesh extent")
    minimum_x, minimum_y, maximum_x, maximum_y = projected.total_bounds
    padding = 3_000
    axes[1].set_xlim(minimum_x - padding, maximum_x + padding)
    axes[1].set_ylim(minimum_y - padding, maximum_y + padding)
    axes[1].legend(loc="lower right")
    fig.suptitle("Maizuru 500 m CITY GAP QA (real data; straight-line distances)")
    fig.text(
        0.5,
        0.01,
        "Processed from e-Stat Census 2020, MLIT P11-2022/P04-2020, and Project PLATEAU Maizuru 2025 related data",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def run(args: argparse.Namespace) -> dict[str, object]:
    population_source = read_estat_csv(args.population)
    population = add_population_metrics(population_source)
    meshes = population_to_geodataframe(population)

    border_source = gpd.read_file(args.border)
    raw_border = _to_jgd2011(border_source)
    boundary = boundary_from_plateau(raw_border)
    meshes = intersects_boundary(meshes, boundary).reset_index(drop=True)
    projected_meshes = meshes.to_crs(METRIC_CRS)
    projected_city = boundary.to_crs(METRIC_CRS).geometry.union_all()
    meshes["maizuru_area_fraction"] = projected_meshes.geometry.intersection(
        projected_city
    ).area.div(projected_meshes.geometry.area)
    city_geographic = boundary.geometry.union_all()
    meshes["centroid_within_maizuru"] = [
        city_geographic.covers(Point(longitude, latitude))
        for longitude, latitude in zip(meshes["centroid_lon"], meshes["centroid_lat"])
    ]

    station_source = gpd.read_file(args.stations)
    stations_raw = _to_jgd2011(station_source)
    stations_city = intersects_boundary(stations_raw, boundary)
    station_location_count = stations_city.geometry.map(lambda item: item.wkb_hex).nunique()
    stations = deduplicate_stations(stations_city)

    bus_source = gpd.read_file(args.bus_stops)
    buses_raw = _to_jgd2011(bus_source)
    buses = intersects_boundary(buses_raw, boundary).reset_index(drop=True)

    medical_source = gpd.read_file(args.medical)
    medical_raw = _to_jgd2011(medical_source)
    medical_city = intersects_boundary(medical_raw, boundary).reset_index(drop=True)
    category = pd.to_numeric(medical_city["P04_001"], errors="coerce")
    hospitals = medical_city.loc[category.eq(1)].copy()
    clinics = medical_city.loc[category.eq(2)].copy()
    dental = medical_city.loc[category.eq(3)].copy()
    medical_primary = filter_medical_primary(medical_city)

    _nearest_columns(meshes, stations, name_column="station_name", prefix="station")
    _nearest_columns(meshes, buses, name_column="P11_001", prefix="bus_stop")
    _nearest_columns(meshes, medical_primary, name_column="P04_002", prefix="medical")
    _nearest_columns(meshes, hospitals, name_column="P04_002", prefix="hospital")
    _nearest_columns(meshes, clinics, name_column="P04_002", prefix="clinic")

    station_is_nearest = (
        meshes["nearest_station_distance_m"] <= meshes["nearest_bus_stop_distance_m"]
    )
    meshes["nearest_public_transport_type"] = np.where(
        station_is_nearest, "station", "bus_stop"
    )
    meshes["nearest_public_transport_name"] = np.where(
        station_is_nearest, meshes["nearest_station_name"], meshes["nearest_bus_stop_name"]
    )
    meshes["nearest_public_transport_distance_m"] = meshes[
        ["nearest_station_distance_m", "nearest_bus_stop_distance_m"]
    ].min(axis=1)

    primary_index = meshes.index[meshes["primary_eligible_disclosure"]]
    ranked = add_candidate_rankings(meshes.loc[primary_index])
    ranking_columns = [column for column in ranked if column not in meshes]
    for column in ranking_columns:
        meshes[column] = pd.NA
        meshes.loc[primary_index, column] = ranked[column]
    meshes = add_eligibility_rank(meshes, minimum_population=20, minimum_elderly=10)
    metrics = meshes[OUTPUT_COLUMNS].copy()
    validation_checks = validate_real_metrics(metrics)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_metrics = metrics.drop(columns="geometry")
    csv_metrics.to_csv(args.output_dir / "maizuru_mesh_metrics.csv", index=False)
    metrics.to_file(args.output_dir / "maizuru_city_gap.geojson", driver="GeoJSON")
    top10 = metrics.loc[metrics["rank"].le(10)].sort_values("rank")
    top10_csv = top10.drop(columns="geometry")
    leading_columns = [
        "rank",
        "mesh_code",
        "centroid_lat",
        "centroid_lon",
        "population",
        "elderly_population",
        "elderly_ratio",
        "nearest_station_distance_m",
        "nearest_bus_stop_distance_m",
        "nearest_public_transport_distance_m",
        "nearest_medical_distance_m",
        "exploratory_score_c",
        "pareto_frontier",
        "suppression_flag",
    ]
    top10_csv = top10_csv[
        leading_columns + [column for column in top10_csv if column not in leading_columns]
    ]
    top10_csv.to_csv(
        args.output_dir / "maizuru_city_gap_top10.csv", index=False
    )
    _write_map(
        metrics,
        boundary,
        stations,
        buses,
        medical_primary,
        args.output_dir / "maizuru_city_gap_overview.png",
    )

    threshold_sets = {
        "none": _top_codes(meshes, 0, 0),
        "population_10_elderly_5": _top_codes(meshes, 10, 5),
        "population_20_elderly_10": _top_codes(meshes, 20, 10),
        "population_50_elderly_20": _top_codes(meshes, 50, 20),
    }
    baseline = set(threshold_sets["population_20_elderly_10"])
    threshold_stability = {
        name: {
            "top10_mesh_codes": codes,
            "overlap_with_primary_top10": len(baseline.intersection(codes)),
        }
        for name, codes in threshold_sets.items()
    }
    crs = CRS.from_user_input(METRIC_CRS)
    top1 = None
    if not top10.empty:
        top1 = {
            key: None if pd.isna(value) else value
            for key, value in top10.iloc[0].drop(labels="geometry").to_dict().items()
        }
    summary: dict[str, object] = {
        "analysis_status": "real data",
        "generated_from_synthetic_data": False,
        "distance_method": "centroid-to-point straight-line (Euclidean) distance",
        "analysis_crs": {
            "code": METRIC_CRS,
            "name": crs.name,
            "area_of_use": crs.area_of_use.name,
            "bounds": list(crs.area_of_use.bounds),
        },
        "record_counts": {
            "population_kyoto": len(population_source),
            "population_meshes_intersecting_maizuru": len(meshes),
            "population_unaffected": int(meshes["primary_eligible_disclosure"].sum()),
            "population_suppressed_source": int(meshes["suppression_flag"].sum()),
            "population_aggregation_destination": int(meshes["aggregation_target_flag"].sum()),
            "stations_raw": len(stations_raw),
            "stations_within_maizuru": len(stations_city),
            "station_unique_locations": station_location_count,
            "station_unique_names": int(stations_city["駅名"].nunique()),
            "station_deduplicated": len(stations),
            "bus_stops_kyoto": len(buses_raw),
            "bus_stops_maizuru": len(buses),
            "medical_kyoto": len(medical_raw),
            "medical_maizuru": len(medical_city),
            "hospitals_maizuru": len(hospitals),
            "clinics_maizuru": len(clinics),
            "dental_clinics_maizuru": len(dental),
            "medical_primary_maizuru": len(medical_primary),
            "primary_rank_eligible_meshes": int(meshes["primary_eligible"].sum()),
        },
        "crs_transform_log": {
            "maizuru_boundary": {
                "original": str(border_source.crs),
                "analysis": METRIC_CRS,
                "transformed_records": len(boundary),
            },
            "population": {
                "original": GEOGRAPHIC_CRS,
                "analysis": METRIC_CRS,
                "transformed_records": len(meshes),
            },
            "stations": {
                "original": str(station_source.crs),
                "analysis": METRIC_CRS,
                "transformed_records": len(stations),
            },
            "bus_stops": {
                "original": str(bus_source.crs),
                "analysis": METRIC_CRS,
                "transformed_records": len(buses),
            },
            "medical_primary": {
                "original": str(medical_source.crs),
                "analysis": METRIC_CRS,
                "transformed_records": len(medical_primary),
            },
        },
        "primary_ranking": {
            "score": "elderly_population_percentile * transport_distance_percentile * medical_distance_percentile",
            "minimum_population": 20,
            "minimum_elderly_population": 10,
            "top1": top1,
        },
        "threshold_stability": threshold_stability,
        "validation_checks": validation_checks,
        "limitations": [
            "Distances are straight-line Euclidean distances, not walking or route distances.",
            "P11 2022 excludes demand, highway and facility shuttle buses.",
            "P04 represents facilities collected for July 2020, not current availability.",
            "Suppressed sources and aggregation destinations are retained but excluded from primary ranks.",
        ],
    }
    (args.output_dir / "maizuru_summary.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("population", "border", "stations", "bus_stops", "medical"):
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, default=DEFAULTS[name])
    parser.add_argument("--output-dir", type=Path, default=DEFAULTS["output_dir"])
    return parser.parse_args()


def main() -> None:
    summary = run(parse_args())
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
