"""Independently verify real Priority 2 outputs without calling allocation helpers."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "analysis/outputs/real/maizuru_building_demographics.parquet"
MESHES = ROOT / "analysis/outputs/real/maizuru_city_gap.geojson"
DETAIL = ROOT / "analysis/outputs/real/maizuru_plateau_detail_meshes.csv"
OUTPUT = ROOT / "analysis/outputs/real/maizuru_building_demographics_verification.json"
DEEP_DIVE = "533513314"
TOLERANCE = 1e-9


def _weighted(values: pd.Series, weights: pd.Series, quantile: float) -> float:
    """Independent inverse-CDF weighted quantile implementation."""

    order = np.argsort(values.to_numpy(), kind="stable")
    sorted_values = values.to_numpy(dtype=float)[order]
    sorted_weights = weights.to_numpy(dtype=float)[order]
    index = int(np.searchsorted(np.cumsum(sorted_weights), quantile * sorted_weights.sum()))
    return float(sorted_values[min(index, len(sorted_values) - 1)])


def main() -> None:
    records = pd.read_parquet(PARQUET)
    meshes = gpd.read_file(MESHES).drop(columns="geometry")
    meshes["mesh_code"] = meshes["mesh_code"].astype(str)
    detail = pd.read_csv(DETAIL, dtype={"mesh_code": str})
    ranked = detail.dropna(subset=["citywide_screening_rank"]).sort_values(
        ["citywide_screening_rank", "mesh_code"]
    )
    sample = [DEEP_DIVE]
    sample.extend(code for code in ranked["mesh_code"] if code != DEEP_DIVE)
    sample = sample[:5]
    if len(sample) != 5:
        raise ValueError("Independent verification requires five covered real meshes")

    mesh_lookup = meshes.set_index("mesh_code")
    detail_lookup = detail.set_index("mesh_code")
    results: list[dict[str, object]] = []
    maximum_difference = 0.0
    for mesh_code in sample:
        group = records.loc[records["mesh_code"].eq(mesh_code)].copy()
        if group.empty:
            raise ValueError(f"No building records for verification mesh {mesh_code}")
        source = mesh_lookup.loc[mesh_code]
        reported = detail_lookup.loc[mesh_code]
        population_sum = float(group["estimated_population"].sum())
        elderly_sum = float(group["estimated_elderly_population"].sum())
        weight_sum = float(group["allocation_weight"].sum())
        reconstructed_weight_sum = float(
            (
                group["verified_building_floor_area"]
                * group["footprint_intersection_fraction"]
            ).sum()
        )
        fraction_sum = float(group["allocation_fraction"].sum())
        allocation_fraction_max_difference = float(
            (
                group["allocation_fraction"]
                - group["allocation_weight"] / weight_sum
            ).abs().max()
        )
        transport_mean = float(
            np.average(
                group["nearest_public_transport_distance_m"],
                weights=group["estimated_elderly_population"],
            )
        )
        medical_mean = float(
            np.average(
                group["nearest_medical_distance_m"],
                weights=group["estimated_elderly_population"],
            )
        )
        independently_calculated = {
            "population_sum": population_sum,
            "elderly_sum": elderly_sum,
            "building_weight_sum": weight_sum,
            "reconstructed_building_weight_sum": reconstructed_weight_sum,
            "allocation_fraction_sum": fraction_sum,
            "weighted_transport_mean": transport_mean,
            "weighted_transport_median": _weighted(
                group["nearest_public_transport_distance_m"],
                group["estimated_elderly_population"],
                0.5,
            ),
            "weighted_transport_p90": _weighted(
                group["nearest_public_transport_distance_m"],
                group["estimated_elderly_population"],
                0.9,
            ),
            "weighted_medical_mean": medical_mean,
            "weighted_medical_median": _weighted(
                group["nearest_medical_distance_m"],
                group["estimated_elderly_population"],
                0.5,
            ),
            "weighted_medical_p90": _weighted(
                group["nearest_medical_distance_m"],
                group["estimated_elderly_population"],
                0.9,
            ),
        }
        differences = {
            "population": population_sum - float(source["population"]),
            "elderly": elderly_sum - float(source["elderly_population"]),
            "allocation_fraction": fraction_sum - 1.0,
            "building_weight_sum": weight_sum - reconstructed_weight_sum,
            "per_record_allocation_fraction_max": allocation_fraction_max_difference,
            "weighted_transport_mean": transport_mean
            - float(reported["weighted_mean_transport_distance"]),
            "weighted_transport_median": independently_calculated[
                "weighted_transport_median"
            ]
            - float(reported["weighted_median_transport_distance"]),
            "weighted_transport_p90": independently_calculated["weighted_transport_p90"]
            - float(reported["weighted_p90_transport_distance"]),
            "weighted_medical_mean": medical_mean
            - float(reported["weighted_mean_medical_distance"]),
            "weighted_medical_median": independently_calculated[
                "weighted_medical_median"
            ]
            - float(reported["weighted_median_medical_distance"]),
            "weighted_medical_p90": independently_calculated["weighted_medical_p90"]
            - float(reported["weighted_p90_medical_distance"]),
        }
        maximum_difference = max(maximum_difference, *(abs(float(v)) for v in differences.values()))
        results.append(
            {
                "mesh_code": mesh_code,
                "records": len(group),
                "independently_calculated": independently_calculated,
                "exact_differences": differences,
            }
        )

    if maximum_difference > TOLERANCE:
        raise ValueError(f"Independent verification failed: {maximum_difference}")
    report = {
        "verification_method": (
            "Direct Parquet group sums, numpy weighted means, and an independent inverse-CDF "
            "weighted quantile; no production allocation/statistics helper imported"
        ),
        "sample_selection": "deep dive plus four highest-ranked covered comparison meshes",
        "sample_meshes": sample,
        "tolerance": TOLERANCE,
        "maximum_absolute_difference": maximum_difference,
        "passed": True,
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": True, "sample_meshes": sample, "max": maximum_difference}))


if __name__ == "__main__":
    main()
