"""Synthetic ranking tests; values are not real CITY GAP results."""

import pandas as pd

from analysis.src.ranking import add_candidate_rankings, add_eligibility_rank, pareto_frontier


def test_pareto_frontier_marks_only_non_dominated_rows() -> None:
    frame = pd.DataFrame({"need": [3, 2, 1], "transport": [1, 2, 1], "medical": [1, 2, 1]})
    assert pareto_frontier(frame, ["need", "transport", "medical"]).tolist() == [True, True, False]


def test_eligibility_rank_keeps_unfiltered_rank() -> None:
    frame = pd.DataFrame(
        {
            "population": [5, 100, 80],
            "elderly_population": [4, 30, 20],
            "elderly_ratio": [0.8, 0.3, 0.25],
            "nearest_public_transport_distance_m": [3000, 1000, 500],
            "nearest_medical_distance_m": [3000, 1000, 500],
            "primary_eligible_disclosure": [True, True, True],
        }
    )
    ranked = add_eligibility_rank(add_candidate_rankings(frame))
    assert ranked.loc[0, "rank_c_unfiltered"] == 2
    assert pd.isna(ranked.loc[0, "rank"])
    assert ranked.loc[1, "rank"] == 1
