"""Reproduce the final score, medical, boundary, and Rank 1 audits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from shapely.geometry import Point

from analysis.src.audit import (
    classify_medical_access,
    ordered_mesh_codes,
    rank_correlation,
    tie_summary,
)
from analysis.src.city_config import CityConfig, load_city_config
from analysis.src.distances import nearest_named
from analysis.src.mesh import GEOGRAPHIC_CRS, decode_500m_mesh
from analysis.src.metrics import percentile
from analysis.src.population import ELDERLY_COLUMNS, add_population_metrics, read_estat_csv
from analysis.src.ranking import pareto_frontier
from analysis.src.spatial import (
    boundary_from_plateau,
    deduplicate_stations,
    filter_medical_primary,
    intersects_boundary,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIGS = (ROOT / "analysis/config/maizuru.yaml", ROOT / "analysis/config/fujisawa.yaml")
DEFAULT_REVIEW = ROOT / "analysis/config/medical_access_review.yaml"
DEFAULT_OUTPUT = ROOT / "analysis/outputs/real/final_audit.json"
FINAL_DEMO = ROOT / "frontend/public/data/final_demo.json"
BUFFER_M = 2_000.0


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    raise TypeError(type(value).__name__)


def _confirmed_review(path: Path) -> tuple[dict[str, list[str]], dict[str, list[dict[str, str]]]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    reviewed = raw.get("confirmed_public", {})
    names: dict[str, list[str]] = {}
    evidence: dict[str, list[dict[str, str]]] = {}
    for city_id, entries in reviewed.items():
        if not isinstance(entries, list):
            raise TypeError(f"confirmed_public.{city_id} must be a list")
        evidence[city_id] = [dict(item) for item in entries]
        names[city_id] = [str(item["name"]) for item in entries]
    return names, evidence


def _comparison_masks(metrics: gpd.GeoDataFrame, config: CityConfig) -> tuple[pd.Series, pd.Series]:
    disclosure = metrics["primary_eligible_disclosure"].astype(bool)
    boundary = metrics["centroid_within_city"].astype(bool) if config.require_centroid_within_city else True
    comparison = disclosure & boundary
    eligible = (
        comparison
        & metrics["population"].ge(config.minimum_population)
        & metrics["elderly_population"].ge(config.minimum_elderly_population)
    )
    return comparison, eligible


def _boolean_series(values: pd.Series) -> pd.Series:
    return values.map(
        lambda value: value is True
        or isinstance(value, (np.bool_,)) and bool(value)
        or isinstance(value, str) and value.strip().lower() == "true"
    ).astype(bool)


def _variant_audit(metrics: gpd.GeoDataFrame, config: CityConfig) -> dict[str, Any]:
    comparison, eligible = _comparison_masks(metrics, config)
    scores = {
        "A_elderly_count_transport_medical": (
            metrics["elderly_population_percentile"]
            * metrics["transport_distance_percentile"]
            * metrics["medical_distance_percentile"]
        ),
        "B_elderly_ratio_transport_medical": (
            metrics["elderly_ratio_percentile"]
            * metrics["transport_distance_percentile"]
            * metrics["medical_distance_percentile"]
        ),
        "C_elderly_count_transport": (
            metrics["elderly_population_percentile"]
            * metrics["transport_distance_percentile"]
        ),
        "D_elderly_count_medical": (
            metrics["elderly_population_percentile"]
            * metrics["medical_distance_percentile"]
        ),
    }
    base_name = "A_elderly_count_transport_medical"
    base = scores[base_name]
    base_top10 = ordered_mesh_codes(metrics, base, eligible, limit=10)
    base_top5 = base_top10[:5]
    variants: dict[str, Any] = {}
    for name, score in scores.items():
        top10 = ordered_mesh_codes(metrics, score, eligible, limit=10)
        top5 = top10[:5]
        variants[name] = {
            "top10_mesh_codes": top10,
            "top10_overlap_with_A": len(set(top10).intersection(base_top10)),
            "top5_overlap_with_A": len(set(top5).intersection(base_top5)),
            "spearman_with_A_all_eligible": rank_correlation(base.loc[eligible], score.loc[eligible]),
            "A_rank_one_position": ordered_mesh_codes(
                metrics, score, eligible, limit=int(eligible.sum())
            ).index(base_top10[0]) + 1,
        }

    eligible_frame = metrics.loc[eligible]
    frontier = pareto_frontier(
        eligible_frame,
        ["elderly_population", "nearest_public_transport_distance_m", "nearest_medical_distance_m"],
    )
    frontier_codes = eligible_frame.loc[frontier, "mesh_code"].astype(str).tolist()
    stored_all = _boolean_series(metrics["pareto_frontier"])
    stored = stored_all.loc[eligible]
    stored_frontier_codes = metrics.loc[
        comparison & stored_all, "mesh_code"
    ].astype(str).tolist()
    return {
        "percentile_definition": "pandas rank(method='average', pct=True), higher raw value receives higher percentile",
        "rank_tie_definition": "score rank(method='min', ascending=False); exported ordering uses mesh_code ascending as deterministic tie-breaker",
        "comparison_denominator": int(comparison.sum()),
        "eligible_denominator": int(eligible.sum()),
        "suppression_or_aggregation_excluded": int((~metrics["primary_eligible_disclosure"].astype(bool)).sum()),
        "comparison_missing": {
            column: int(metrics.loc[comparison, column].isna().sum())
            for column in (
                "elderly_population",
                "nearest_public_transport_distance_m",
                "nearest_medical_distance_m",
                "exploratory_score_c",
            )
        },
        "ties": {
            column: tie_summary(metrics.loc[comparison, column])
            for column in (
                "elderly_population",
                "nearest_public_transport_distance_m",
                "nearest_medical_distance_m",
                "exploratory_score_c",
            )
        },
        "stored_score_c_max_abs_error": float(
            (metrics["exploratory_score_c"] - scores[base_name]).abs().max()
        ),
        "variants": variants,
        "pareto_only": {
            "stored_comparison_frontier_count": len(stored_frontier_codes),
            "stored_comparison_frontier_mesh_codes": stored_frontier_codes,
            "A_top10_on_stored_comparison_frontier": len(
                set(base_top10).intersection(stored_frontier_codes)
            ),
            "A_top5_on_stored_comparison_frontier": len(
                set(base_top5).intersection(stored_frontier_codes)
            ),
            "eligible_frontier_count": len(frontier_codes),
            "frontier_mesh_codes": frontier_codes,
            "A_top10_on_frontier": len(set(base_top10).intersection(frontier_codes)),
            "A_top5_on_frontier": len(set(base_top5).intersection(frontier_codes)),
            "stored_vs_eligible_frontier_disagreement": int((stored != frontier).sum()),
        },
    }


def _origins(metrics: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"mesh_code": metrics["mesh_code"].astype(str)},
        geometry=[Point(x, y) for x, y in zip(metrics["centroid_lon"], metrics["centroid_lat"])],
        crs=GEOGRAPHIC_CRS,
        index=metrics.index,
    )


def _within_buffer(layer: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame, config: CityConfig) -> gpd.GeoDataFrame:
    buffered = boundary.to_crs(config.analysis_crs).geometry.union_all().buffer(BUFFER_M)
    projected = layer.to_crs(config.analysis_crs)
    return layer.loc[projected.geometry.intersects(buffered)].copy()


def _nearest(origins: gpd.GeoDataFrame, targets: gpd.GeoDataFrame, name: str, config: CityConfig) -> pd.DataFrame:
    return nearest_named(origins, targets, name_column=name, analysis_crs=config.analysis_crs)


def _score_with_distances(
    metrics: gpd.GeoDataFrame,
    config: CityConfig,
    *,
    transport_distance: pd.Series | None = None,
    medical_distance: pd.Series | None = None,
) -> tuple[pd.Series, pd.Series, list[str]]:
    comparison, eligible = _comparison_masks(metrics, config)
    transport = transport_distance if transport_distance is not None else metrics["nearest_public_transport_distance_m"]
    medical = medical_distance if medical_distance is not None else metrics["nearest_medical_distance_m"]
    transport_pct = pd.Series(np.nan, index=metrics.index)
    medical_pct = pd.Series(np.nan, index=metrics.index)
    transport_pct.loc[comparison] = percentile(transport.loc[comparison])
    medical_pct.loc[comparison] = percentile(medical.loc[comparison])
    score = metrics["elderly_population_percentile"] * transport_pct * medical_pct
    return score, eligible, ordered_mesh_codes(metrics, score, eligible, limit=10)


def _scenario_comparison(
    metrics: gpd.GeoDataFrame,
    config: CityConfig,
    base_top10: list[str],
    *,
    transport_distance: pd.Series | None = None,
    medical_distance: pd.Series | None = None,
) -> dict[str, Any]:
    score, eligible, top10 = _score_with_distances(
        metrics,
        config,
        transport_distance=transport_distance,
        medical_distance=medical_distance,
    )
    full_order = ordered_mesh_codes(metrics, score, eligible, limit=int(eligible.sum()))
    return {
        "top10_mesh_codes": top10,
        "top10_overlap_with_primary": len(set(top10).intersection(base_top10)),
        "top5_overlap_with_primary": len(set(top10[:5]).intersection(base_top10[:5])),
        "spearman_with_primary_all_eligible": rank_correlation(
            metrics.loc[eligible, "exploratory_score_c"], score.loc[eligible]
        ),
        "primary_rank_one_position": full_order.index(base_top10[0]) + 1,
    }


def _facility_audit(
    metrics: gpd.GeoDataFrame,
    config: CityConfig,
    confirmed_names: list[str],
) -> tuple[dict[str, Any], dict[str, pd.Series]]:
    boundary_source = gpd.read_file(config.boundary.path)
    boundary = boundary_from_plateau(
        boundary_source.to_crs(GEOGRAPHIC_CRS), city_code=config.city_code, city_name=config.city_name
    )
    origins = _origins(metrics)

    medical_source = gpd.read_file(config.medical.path).to_crs(GEOGRAPHIC_CRS)
    medical_city = intersects_boundary(medical_source, boundary)
    medical_primary = filter_medical_primary(medical_city)
    classification = classify_medical_access(
        medical_primary["P04_002"], confirmed_public_names=confirmed_names
    )
    medical_primary = medical_primary.join(classification)
    medical_without_uncertain = medical_primary.loc[
        medical_primary["medical_access_class"].ne("uncertain_access")
    ]
    hospitals_city = medical_city.loc[pd.to_numeric(medical_city["P04_001"], errors="coerce").eq(1)]

    nearest_current = _nearest(origins, medical_primary, "P04_002", config)
    nearest_filtered = _nearest(origins, medical_without_uncertain, "P04_002", config)
    nearest_hospital = _nearest(origins, hospitals_city, "P04_002", config)
    current_error = (
        nearest_current["distance_m"] - metrics["nearest_medical_distance_m"]
    ).abs().max()

    base_top10 = (
        metrics.loc[metrics["rank"].notna()]
        .sort_values(["rank", "mesh_code"])
        .head(10)["mesh_code"]
        .astype(str)
        .tolist()
    )
    sensitivity = {
        "A_hospital_and_clinic": _scenario_comparison(metrics, config, base_top10),
        "B_exclude_uncertain_access": _scenario_comparison(
            metrics,
            config,
            base_top10,
            medical_distance=nearest_filtered["distance_m"],
        ),
        "C_hospital_only": _scenario_comparison(
            metrics,
            config,
            base_top10,
            medical_distance=nearest_hospital["distance_m"],
        ),
    }

    buses_source = gpd.read_file(config.bus_stops.path).to_crs(GEOGRAPHIC_CRS)
    buses_city = intersects_boundary(buses_source, boundary)
    buses_buffer = _within_buffer(buses_source, boundary, config)
    nearest_buffer_bus = _nearest(origins, buses_buffer, "P11_001", config)
    station_source = gpd.read_file(config.stations.path).to_crs(GEOGRAPHIC_CRS)
    stations = deduplicate_stations(intersects_boundary(station_source, boundary))
    nearest_station = _nearest(origins, stations, "station_name", config)
    buffer_transport_distance = pd.concat(
        [nearest_buffer_bus["distance_m"], nearest_station["distance_m"]], axis=1
    ).min(axis=1)

    medical_buffer = filter_medical_primary(_within_buffer(medical_source, boundary, config))
    buffer_classification = classify_medical_access(
        medical_buffer["P04_002"], confirmed_public_names=confirmed_names
    )
    medical_buffer = medical_buffer.join(buffer_classification)
    medical_buffer_without_uncertain = medical_buffer.loc[
        medical_buffer["medical_access_class"].ne("uncertain_access")
    ]
    nearest_buffer_medical = _nearest(origins, medical_buffer, "P04_002", config)
    nearest_buffer_filtered_medical = _nearest(
        origins, medical_buffer_without_uncertain, "P04_002", config
    )
    boundary_sensitivity = _scenario_comparison(
        metrics,
        config,
        base_top10,
        transport_distance=buffer_transport_distance,
        medical_distance=nearest_buffer_medical["distance_m"],
    )
    boundary_sensitivity.update(
        {
            "buffer_m": BUFFER_M,
            "city_bus_stops": len(buses_city),
            "buffer_bus_stops": len(buses_buffer),
            "outside_city_bus_stops_added": len(buses_buffer) - len(buses_city),
            "city_medical_primary": len(medical_primary),
            "buffer_medical_primary": len(medical_buffer),
            "outside_city_medical_added": len(medical_buffer) - len(medical_primary),
            "station_scope": "PLATEAU city-related station layer only; neighboring-city stations are not included",
            "prefecture_scope": "P11/P04 source prefecture only; cross-prefecture neighbors are not included",
        }
    )
    boundary_filtered_sensitivity = _scenario_comparison(
        metrics,
        config,
        base_top10,
        transport_distance=buffer_transport_distance,
        medical_distance=nearest_buffer_filtered_medical["distance_m"],
    )
    boundary_filtered_sensitivity.update(
        {
            "buffer_m": BUFFER_M,
            "medical_access_scope": "confirmed_public + likely_public; uncertain_access retained in source but excluded from this sensitivity",
            "buffer_medical_primary": len(medical_buffer),
            "buffer_medical_after_uncertain_exclusion": len(medical_buffer_without_uncertain),
        }
    )
    access_records = medical_primary.loc[
        medical_primary["medical_access_class"].eq("uncertain_access"),
        ["P04_001", "P04_002", "P04_003", "medical_access_reason"],
    ].to_dict("records")
    result = {
        "classification_rule": (
            "P04 hospital/clinic records are retained. Explicit institutional-name patterns are flagged, "
            "not automatically deleted. confirmed_public requires reviewed external evidence."
        ),
        "access_class_counts": {
            str(key): int(value)
            for key, value in medical_primary["medical_access_class"].value_counts().items()
        },
        "uncertain_access_records": access_records,
        "current_distance_reproduction_max_abs_error_m": float(current_error),
        "medical_sensitivity": sensitivity,
        "boundary_sensitivity": boundary_sensitivity,
        "boundary_sensitivity_excluding_uncertain_medical": boundary_filtered_sensitivity,
    }
    return result, {
        "current_medical_name": nearest_current["name"],
        "current_medical_distance": nearest_current["distance_m"],
        "filtered_medical_name": nearest_filtered["name"],
        "filtered_medical_distance": nearest_filtered["distance_m"],
        "hospital_name": nearest_hospital["name"],
        "hospital_distance": nearest_hospital["distance_m"],
        "buffer_medical_name": nearest_buffer_medical["name"],
        "buffer_medical_distance": nearest_buffer_medical["distance_m"],
        "buffer_filtered_medical_name": nearest_buffer_filtered_medical["name"],
        "buffer_filtered_medical_distance": nearest_buffer_filtered_medical["distance_m"],
        "buffer_bus_name": nearest_buffer_bus["name"],
        "buffer_bus_distance": nearest_buffer_bus["distance_m"],
        "buffer_transport_distance": buffer_transport_distance,
    }


def _rank_one_audit(
    metrics: gpd.GeoDataFrame,
    config: CityConfig,
    facility_series: dict[str, pd.Series],
    evidence: list[dict[str, str]],
) -> dict[str, Any]:
    rank_one = metrics.loc[metrics["rank"].eq(1)].iloc[0]
    code = str(rank_one["mesh_code"])
    raw_population = add_population_metrics(read_estat_csv(config.population.path))
    population_row = raw_population.loc[raw_population["mesh_code"].astype(str).eq(code)].iloc[0]
    elderly_components = {
        column: int(float(population_row[column])) for column in ELDERLY_COLUMNS
    }
    bounds = decode_500m_mesh(code)
    boundary = boundary_from_plateau(
        gpd.read_file(config.boundary.path).to_crs(GEOGRAPHIC_CRS),
        city_code=config.city_code,
        city_name=config.city_name,
    )
    centroid = gpd.GeoSeries(
        [Point(rank_one["centroid_lon"], rank_one["centroid_lat"])], crs=GEOGRAPHIC_CRS
    ).to_crs(config.analysis_crs).iloc[0]
    city = boundary.to_crs(config.analysis_crs).geometry.union_all()
    index = rank_one.name
    current_name = str(facility_series["current_medical_name"].loc[index])
    return {
        "mesh_code": code,
        "mesh_bounds_jgd2011": {
            "west": bounds.west,
            "south": bounds.south,
            "east": bounds.east,
            "north": bounds.north,
        },
        "centroid": {
            "longitude": float(rank_one["centroid_lon"]),
            "latitude": float(rank_one["centroid_lat"]),
            "within_city": bool(city.covers(centroid)),
            "distance_to_city_boundary_m": float(centroid.distance(city.boundary)),
            "city_area_fraction": float(rank_one["city_area_fraction"]),
        },
        "population": {
            "total": int(float(population_row["population"])),
            "elderly_components": elderly_components,
            "elderly_sum": sum(elderly_components.values()),
            "elderly_output": int(float(rank_one["elderly_population"])),
            "elderly_ratio": float(rank_one["elderly_ratio"]),
            "HTKSYORI": str(population_row["HTKSYORI"]),
            "HTKSAKI": None if pd.isna(population_row["HTKSAKI"]) else str(population_row["HTKSAKI"]),
            "GASSAN": None if pd.isna(population_row["GASSAN"]) else str(population_row["GASSAN"]),
            "primary_eligible_disclosure": bool(population_row["primary_eligible_disclosure"]),
        },
        "nearest": {
            "station": {
                "name": rank_one["nearest_station_name"],
                "distance_m": float(rank_one["nearest_station_distance_m"]),
            },
            "bus_stop": {
                "name": rank_one["nearest_bus_stop_name"],
                "distance_m": float(rank_one["nearest_bus_stop_distance_m"]),
            },
            "medical": {
                "name": current_name,
                "distance_m": float(facility_series["current_medical_distance"].loc[index]),
                "confirmed_public_evidence": [item for item in evidence if item["name"] == current_name],
            },
            "hospital": {
                "name": facility_series["hospital_name"].loc[index],
                "distance_m": float(facility_series["hospital_distance"].loc[index]),
            },
        },
        "two_km_buffer_sensitivity": {
            "bus_stop_name": facility_series["buffer_bus_name"].loc[index],
            "bus_stop_distance_m": float(facility_series["buffer_bus_distance"].loc[index]),
            "public_transport_distance_m": float(facility_series["buffer_transport_distance"].loc[index]),
            "medical_name": facility_series["buffer_medical_name"].loc[index],
            "medical_distance_m": float(facility_series["buffer_medical_distance"].loc[index]),
            "medical_excluding_uncertain_name": facility_series["buffer_filtered_medical_name"].loc[index],
            "medical_excluding_uncertain_distance_m": float(
                facility_series["buffer_filtered_medical_distance"].loc[index]
            ),
        },
        "score": {
            "elderly_population_percentile": float(rank_one["elderly_population_percentile"]),
            "transport_distance_percentile": float(rank_one["transport_distance_percentile"]),
            "medical_distance_percentile": float(rank_one["medical_distance_percentile"]),
            "score_c": float(rank_one["exploratory_score_c"]),
            "pareto_frontier": str(rank_one["pareto_frontier"]).strip().lower() == "true",
        },
    }


def _what_if_audit() -> dict[str, Any]:
    demo = json.loads(FINAL_DEMO.read_text(encoding="utf-8"))
    candidate = demo["placement_optimization"]["candidates"][0]
    metrics = pd.read_csv(
        ROOT / "analysis/outputs/real/maizuru_mesh_metrics.csv",
        dtype={"mesh_code": str},
    )
    comparison = metrics.loc[metrics["rank_c_unfiltered"].notna()].copy()
    projected = gpd.GeoSeries(
        [Point(x, y) for x, y in zip(comparison["centroid_lon"], comparison["centroid_lat"])],
        crs=GEOGRAPHIC_CRS,
    ).to_crs("EPSG:6674")
    point = gpd.GeoSeries(
        [Point(candidate["longitude"], candidate["latitude"])], crs=GEOGRAPHIC_CRS
    ).to_crs("EPSG:6674").iloc[0]
    point_distance = projected.distance(point).to_numpy()
    before_distance = comparison["nearest_public_transport_distance_m"].to_numpy(float)
    after_distance = np.minimum(before_distance, point_distance)
    after_percentile = pd.Series(after_distance).rank(method="average", pct=True).to_numpy()
    before_score = comparison["exploratory_score_c"].to_numpy(float)
    after_score = (
        comparison["elderly_population_percentile"].to_numpy(float)
        * after_percentile
        * comparison["medical_distance_percentile"].to_numpy(float)
    )
    reduction = before_score - after_score
    improved = after_distance < before_distance - 1e-6
    top_index = int(np.argmax(reduction))
    reproduced = {
        "objective_total_score_c_reduction": round(float(reduction.sum()), 9),
        "improved_mesh_count": int(improved.sum()),
        "affected_elderly_population": int(comparison.loc[improved, "elderly_population"].sum()),
        "average_transport_distance_improvement_m": round(
            float((before_distance[improved] - after_distance[improved]).mean()), 3
        ),
        "top_improvement_mesh": str(comparison.iloc[top_index]["mesh_code"]),
        "top_improvement": {
            "mesh_code": str(comparison.iloc[top_index]["mesh_code"]),
            "before_distance_m": round(float(before_distance[top_index]), 3),
            "after_distance_m": round(float(after_distance[top_index]), 3),
            "before_score_c": round(float(before_score[top_index]), 9),
            "after_score_c": round(float(after_score[top_index]), 9),
            "score_c_reduction": round(float(reduction[top_index]), 9),
        },
    }
    expected = {
        key: candidate[key]
        for key in (
            "objective_total_score_c_reduction",
            "improved_mesh_count",
            "affected_elderly_population",
            "average_transport_distance_improvement_m",
            "top_improvement_mesh",
            "top_improvement",
        )
    }
    return {
        "candidate_id": candidate["candidate_id"],
        "road_name": candidate["road_name"],
        "reproduced": reproduced,
        "published": expected,
        "exact_match": reproduced == expected,
        "affected_elderly_definition": "sum of recorded 65+ population in meshes whose straight-line transport distance decreases; not users, beneficiaries, demand, or ridership",
    }


def audit_city(
    config: CityConfig,
    confirmed_names: list[str],
    evidence: list[dict[str, str]],
) -> dict[str, Any]:
    metrics_path = config.output_dir / f"{config.output_prefix}_city_gap.geojson"
    metrics = gpd.read_file(metrics_path)
    metrics["mesh_code"] = metrics["mesh_code"].astype(str)
    numeric_columns = (
        "population",
        "elderly_population",
        "elderly_ratio",
        "centroid_lon",
        "centroid_lat",
        "city_area_fraction",
        "nearest_station_distance_m",
        "nearest_bus_stop_distance_m",
        "nearest_public_transport_distance_m",
        "nearest_medical_distance_m",
        "nearest_hospital_distance_m",
        "elderly_population_percentile",
        "elderly_ratio_percentile",
        "transport_distance_percentile",
        "medical_distance_percentile",
        "exploratory_score_c",
        "rank",
    )
    for column in numeric_columns:
        metrics[column] = pd.to_numeric(metrics[column], errors="coerce")
    facility_audit, series = _facility_audit(metrics, config, confirmed_names)
    return {
        "city": {
            "id": config.city_id,
            "name": config.city_name,
            "analysis_crs": config.analysis_crs,
        },
        "score_audit": _variant_audit(metrics, config),
        "facility_audit": facility_audit,
        "rank_one_audit": _rank_one_audit(metrics, config, series, evidence),
    }


def build_audit(config_paths: list[Path], review_path: Path) -> dict[str, Any]:
    names, evidence = _confirmed_review(review_path)
    cities = {}
    for path in config_paths:
        config = load_city_config(path)
        cities[config.city_id] = audit_city(
            config,
            names.get(config.city_id, []),
            evidence.get(config.city_id, []),
        )
    return {
        "schema_version": "1.0.0",
        "audit_date": "2026-08-23",
        "facility_buffer_m": BUFFER_M,
        "cities": cities,
        "what_if": _what_if_audit(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", action="append", type=Path, dest="configs")
    parser.add_argument("--medical-review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_paths = args.configs or list(DEFAULT_CONFIGS)
    report = build_audit(config_paths, args.medical_review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default, allow_nan=False))


if __name__ == "__main__":
    main()
