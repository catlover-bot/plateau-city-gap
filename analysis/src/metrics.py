"""Transparent component metrics for exploratory CITY GAP ranking."""

from __future__ import annotations

import numpy as np
import pandas as pd


def percentile(series: pd.Series, *, higher_is_worse: bool = True) -> pd.Series:
    """Return empirical percentile ranks in [0, 1], preserving missing values."""
    numeric = pd.to_numeric(series, errors="coerce")
    ranked = numeric.rank(method="average", pct=True)
    if not higher_is_worse:
        ranked = 1.0 - ranked + (1.0 / numeric.notna().sum() if numeric.notna().any() else 0)
    return ranked.clip(0.0, 1.0)


def row_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Mean only when every requested component is present."""
    return frame[columns].mean(axis=1, skipna=False)


def add_gap_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Add independently inspectable need, deficit, score, percentile, and rank.

    The score is exploratory: demographic need multiplied by the unweighted mean
    of transport and medical deficits. No policy threshold is implied.
    """
    result = frame.copy()
    result["demographic_need_percentile"] = percentile(result["elderly_ratio"])
    result["station_deficit_percentile"] = percentile(result["station_distance_m"])
    result["bus_stop_deficit_percentile"] = percentile(result["bus_stop_distance_m"])
    result["medical_deficit_percentile"] = percentile(result["medical_distance_m"])
    result["transport_accessibility_deficit"] = row_mean(
        result, ["station_deficit_percentile", "bus_stop_deficit_percentile"]
    )
    result["accessibility_deficit"] = row_mean(
        result, ["transport_accessibility_deficit", "medical_deficit_percentile"]
    )
    result["gap_score"] = (
        result["demographic_need_percentile"] * result["accessibility_deficit"]
    )
    result["gap_percentile"] = percentile(result["gap_score"])
    result["rank"] = result["gap_score"].rank(method="min", ascending=False).astype("Int64")
    return result


def euclidean_distance_m(origin_xy: tuple[float, float], target_xy: tuple[float, float]) -> float:
    """Euclidean distance between two points in a metric projected CRS."""
    return float(np.hypot(target_xy[0] - origin_xy[0], target_xy[1] - origin_xy[1]))

