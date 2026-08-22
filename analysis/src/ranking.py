"""Multi-view exploratory rankings and Pareto candidates."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import percentile

COMPONENT_COLUMNS = [
    "elderly_population_percentile",
    "elderly_ratio_percentile",
    "transport_distance_percentile",
    "medical_distance_percentile",
]


def pareto_frontier(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Return non-dominated rows while maximizing every named component."""
    values = frame[columns].to_numpy(dtype=float)
    valid = np.isfinite(values).all(axis=1)
    frontier = np.zeros(len(frame), dtype=bool)
    for index in np.flatnonzero(valid):
        others = values[valid]
        candidate = values[index]
        dominated = np.any(np.all(others >= candidate, axis=1) & np.any(others > candidate, axis=1))
        frontier[index] = not dominated
    return pd.Series(frontier, index=frame.index)


def add_candidate_rankings(frame: pd.DataFrame) -> pd.DataFrame:
    """Add component percentiles and A/B/C exploratory product scores."""
    result = frame.copy()
    result["elderly_population_percentile"] = percentile(result["elderly_population"])
    result["elderly_ratio_percentile"] = percentile(result["elderly_ratio"])
    result["transport_distance_percentile"] = percentile(
        result["nearest_public_transport_distance_m"]
    )
    result["medical_distance_percentile"] = percentile(result["nearest_medical_distance_m"])
    result["exploratory_score_a"] = (
        result["elderly_population_percentile"] * result["transport_distance_percentile"]
    )
    result["exploratory_score_b"] = (
        result["elderly_population_percentile"] * result["medical_distance_percentile"]
    )
    result["exploratory_score_c"] = (
        result["elderly_population_percentile"]
        * result["transport_distance_percentile"]
        * result["medical_distance_percentile"]
    )
    for label in ("a", "b", "c"):
        result[f"rank_{label}_unfiltered"] = result[f"exploratory_score_{label}"].rank(
            method="min", ascending=False
        ).astype("Int64")
    result["pareto_frontier"] = pareto_frontier(
        result,
        [
            "elderly_population",
            "nearest_public_transport_distance_m",
            "nearest_medical_distance_m",
        ],
    )
    return result


def add_eligibility_rank(
    frame: pd.DataFrame, *, minimum_population: int = 20, minimum_elderly: int = 10
) -> pd.DataFrame:
    """Rank disclosed, sufficiently populated meshes without dropping other rows."""
    result = frame.copy()
    result["eligibility_population_threshold"] = result["population"] >= minimum_population
    result["eligibility_elderly_threshold"] = result["elderly_population"] >= minimum_elderly
    result["primary_eligible"] = (
        result["primary_eligible_disclosure"]
        & result["eligibility_population_threshold"]
        & result["eligibility_elderly_threshold"]
        & result["exploratory_score_c"].notna()
    )
    ranks = result.loc[result["primary_eligible"], "exploratory_score_c"].rank(
        method="min", ascending=False
    )
    result["rank"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result.loc[ranks.index, "rank"] = ranks.astype("Int64")
    return result
