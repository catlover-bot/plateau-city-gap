"""Tests use synthetic values only; they are not Maizuru findings."""

import math

import numpy as np
import pandas as pd

from analysis.src.metrics import add_gap_metrics, euclidean_distance_m, percentile


def test_euclidean_distance() -> None:
    assert euclidean_distance_m((0, 0), (300, 400)) == 500


def test_percentile_and_ties() -> None:
    actual = percentile(pd.Series([10, 20, 20, 40]))
    assert actual.tolist() == [0.25, 0.625, 0.625, 1.0]


def test_gap_score_and_ranking() -> None:
    source = pd.DataFrame(
        {
            "elderly_ratio": [0.1, 0.2, 0.3],
            "station_distance_m": [100, 200, 300],
            "bus_stop_distance_m": [100, 200, 300],
            "medical_distance_m": [100, 200, 300],
        }
    )
    result = add_gap_metrics(source)
    assert result.loc[2, "gap_score"] == 1.0
    assert result.loc[2, "rank"] == 1
    assert result["gap_score"].is_monotonic_increasing


def test_missing_component_does_not_create_score() -> None:
    source = pd.DataFrame(
        {
            "elderly_ratio": [0.1, 0.2],
            "station_distance_m": [100, np.nan],
            "bus_stop_distance_m": [100, 200],
            "medical_distance_m": [100, 200],
        }
    )
    result = add_gap_metrics(source)
    assert math.isnan(result.loc[1, "transport_accessibility_deficit"])
    assert math.isnan(result.loc[1, "gap_score"])

