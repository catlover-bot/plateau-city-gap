"""Deterministic robustness and intervention utilities for CITY GAP Decision Studio."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import numpy as np
import pandas as pd


def percentile_rank(values: np.ndarray) -> np.ndarray:
    """Return pandas-compatible average percentile ranks for finite values."""
    array = np.asarray(values, dtype=float)
    result = np.full(array.shape, np.nan, dtype=float)
    valid_indices = np.flatnonzero(np.isfinite(array))
    if valid_indices.size == 0:
        return result
    ordered = valid_indices[np.argsort(array[valid_indices], kind="mergesort")]
    cursor = 0
    count = len(ordered)
    while cursor < count:
        end = cursor + 1
        while end < count and array[ordered[end]] == array[ordered[cursor]]:
            end += 1
        average_rank = ((cursor + 1) + end) / 2
        result[ordered[cursor:end]] = average_rank / count
        cursor = end
    return result


def deterministic_order(
    mesh_codes: Iterable[str],
    scores: np.ndarray,
    eligible: np.ndarray,
) -> list[int]:
    """Order eligible rows by descending score and ascending mesh code."""
    codes = np.asarray([str(value) for value in mesh_codes], dtype=object)
    score_values = np.asarray(scores, dtype=float)
    eligible_values = np.asarray(eligible, dtype=bool) & np.isfinite(score_values)
    indices = np.flatnonzero(eligible_values)
    return sorted(indices.tolist(), key=lambda index: (-score_values[index], codes[index]))


def pareto_mask(values: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    """Return rows not dominated when every supplied component is maximized."""
    matrix = np.asarray(values, dtype=float)
    allowed = np.asarray(eligible, dtype=bool) & np.isfinite(matrix).all(axis=1)
    result = np.zeros(len(matrix), dtype=bool)
    indices = np.flatnonzero(allowed)
    for index in indices:
        other = matrix[indices]
        target = matrix[index]
        dominated = np.any(np.all(other >= target, axis=1) & np.any(other > target, axis=1))
        result[index] = not dominated
    return result


def robustness_rows(
    metrics: pd.DataFrame,
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate transparent frequency/rank summaries over named scenarios."""
    codes = metrics["mesh_code"].astype(str).tolist()
    rows: list[dict[str, Any]] = []
    for index, code in enumerate(codes):
        scenario_results = {
            scenario["id"]: {
                "rank": scenario["ranks"].get(code),
                "top10": code in scenario["top10"],
                "top20": code in scenario["top20"],
                "pareto": code in scenario["pareto"],
            }
            for scenario in scenarios
        }
        ranks = [
            int(result["rank"])
            for result in scenario_results.values()
            if result["rank"] is not None
        ]
        if not ranks:
            continue
        rows.append(
            {
                "mesh_code": code,
                "area_label": metrics.iloc[index].get("area_label"),
                "scenario_count": len(scenarios),
                "ranked_scenario_count": len(ranks),
                "top10_frequency": sum(result["top10"] for result in scenario_results.values()),
                "top20_frequency": sum(result["top20"] for result in scenario_results.values()),
                "pareto_frequency": sum(result["pareto"] for result in scenario_results.values()),
                "median_rank": float(np.median(ranks)),
                "rank_min": min(ranks),
                "rank_max": max(ranks),
                "scenarios": scenario_results,
            }
        )
    rows.sort(
        key=lambda row: (
            -row["top10_frequency"],
            row["median_rank"],
            -row["top20_frequency"],
            row["mesh_code"],
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["robust_rank"] = rank
    return rows


def evaluate_intervention(
    metrics: pd.DataFrame,
    point_distances: np.ndarray,
    selected_indices: Iterable[int],
    *,
    worst_decile_indices: np.ndarray,
    robust_indices: np.ndarray,
) -> dict[str, Any]:
    """Recompute distances, percentile scores, fairness, and robust coverage."""
    selected = list(selected_indices)
    before_distance = metrics["nearest_public_transport_distance_m"].to_numpy(float)
    if selected:
        selected_distances = point_distances[selected]
        closest_site_position = np.argmin(selected_distances, axis=0)
        virtual_distance = selected_distances[closest_site_position, np.arange(len(metrics))]
        after_distance = np.minimum(before_distance, virtual_distance)
    else:
        closest_site_position = np.full(len(metrics), -1, dtype=int)
        after_distance = before_distance.copy()
    after_percentile = percentile_rank(after_distance)
    before_score = metrics["exploratory_score_c"].to_numpy(float)
    after_score = (
        metrics["elderly_population_percentile"].to_numpy(float)
        * after_percentile
        * metrics["medical_distance_percentile"].to_numpy(float)
    )
    distance_reduction = np.maximum(0.0, before_distance - after_distance)
    score_reduction = before_score - after_score
    improved = distance_reduction > 1e-6
    elderly = metrics["elderly_population"].fillna(0).to_numpy(float)
    worst_reductions = distance_reduction[worst_decile_indices]
    robust_reductions = distance_reduction[robust_indices]
    return {
        "after_distance": after_distance,
        "after_score": after_score,
        "distance_reduction": distance_reduction,
        "score_reduction": score_reduction,
        "improved": improved,
        "closest_site_position": closest_site_position,
        "objective_values": {
            "total_score_c_reduction": float(np.nansum(score_reduction)),
            "improved_mesh_count": int(improved.sum()),
            "affected_elderly_population": int(elderly[improved].sum()),
            "mean_improvement_among_improved_m": (
                float(distance_reduction[improved].mean()) if improved.any() else 0.0
            ),
            "total_transport_distance_reduction_m": float(distance_reduction.sum()),
            "worst_decile_mean_reduction_m": (
                float(worst_reductions.mean()) if len(worst_reductions) else 0.0
            ),
            "worst_decile_improved_count": int((worst_reductions > 1e-6).sum()),
            "robust_top20_improved_count": int((robust_reductions > 1e-6).sum()),
            "robust_top20_median_reduction_m": (
                float(np.median(robust_reductions)) if len(robust_reductions) else 0.0
            ),
        },
    }


def greedy_select(
    candidate_count: int,
    site_count: int,
    evaluate: Callable[[list[int]], dict[str, Any]],
    objective_key: Callable[[dict[str, Any]], tuple[float, ...]],
    candidate_ids: list[str],
    candidate_x: np.ndarray,
    candidate_y: np.ndarray,
    *,
    minimum_separation_m: float,
) -> tuple[list[int], dict[str, Any]]:
    """Deterministic greedy selection with a disclosed spacing constraint."""
    selected: list[int] = []
    result = evaluate(selected)
    for _ in range(site_count):
        best_index: int | None = None
        best_result: dict[str, Any] | None = None
        best_key: tuple[float, ...] | None = None
        for index in range(candidate_count):
            if index in selected:
                continue
            if any(
                np.hypot(candidate_x[index] - candidate_x[other], candidate_y[index] - candidate_y[other])
                < minimum_separation_m
                for other in selected
            ):
                continue
            candidate_result = evaluate([*selected, index])
            key = objective_key(candidate_result)
            if best_key is None or key > best_key or (
                key == best_key and candidate_ids[index] < candidate_ids[best_index]  # type: ignore[index]
            ):
                best_index = index
                best_result = candidate_result
                best_key = key
        if best_index is None or best_result is None:
            raise ValueError(f"Could not select {site_count} spatially separated sites")
        selected.append(best_index)
        result = best_result
    return selected, result
