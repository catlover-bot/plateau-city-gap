from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.src.network_scenario import (
    balanced_greedy_select,
    build_candidate_gain_matrix,
    evaluate_selected,
    greedy_select,
)


def _fixture():
    nodes = pd.DataFrame({"node_id": ["a", "b", "c", "d"]})
    edges = pd.DataFrame(
        {
            "source_node_id": ["a", "b", "c"],
            "target_node_id": ["b", "c", "d"],
            "length_m": [2.0, 2.0, 2.0],
        }
    )
    candidates = pd.DataFrame({"candidate_id": ["site-b", "site-c"], "node_id": ["b", "c"]})
    demand = pd.DataFrame({"node_id": ["a", "d"], "baseline_graph_distance_m": [7.0, 7.0]})
    return nodes, edges, candidates, demand


def test_sparse_gain_matrix_keeps_only_true_network_improvements() -> None:
    matrix = build_candidate_gain_matrix(*_fixture())
    assert matrix.candidate_ids == ("site-b", "site-c")
    assert len(matrix.distance_reduction_m) == 4
    best, assigned = evaluate_selected(matrix, [0])
    assert best.tolist() == [5.0, 3.0]
    assert assigned.tolist() == [0, 0]
    both, assigned_both = evaluate_selected(matrix, [0, 1])
    assert both.tolist() == [5.0, 5.0]
    assert assigned_both.tolist() == [0, 1]


def test_one_site_is_exact_and_n_site_prefix_is_deterministic_greedy() -> None:
    matrix = build_candidate_gain_matrix(*_fixture())
    selected, trace = greedy_select(
        matrix,
        np.asarray([1.0, 1.0]),
        np.asarray([1.0, 1.0]),
        np.asarray([0.0, 10.0]),
        np.asarray([0.0, 0.0]),
        max_sites=2,
        minimum_separation_m=1.0,
    )
    # Both candidates have exact one-site gain 8; lexical candidate order is the tie-break.
    assert selected == [0, 1]
    assert [row["candidate_id"] for row in trace] == ["site-b", "site-c"]
    assert trace[0]["marginal_objective"] == 8.0
    assert trace[1]["marginal_objective"] == 2.0


def test_spacing_and_unreachable_component_are_separate_lexicographic_objectives() -> None:
    matrix = build_candidate_gain_matrix(*_fixture())
    selected, trace = greedy_select(
        matrix,
        np.asarray([1.0, 1.0]),
        np.asarray([1.0, 1.0]),
        np.asarray([0.0, 0.5]),
        np.asarray([0.0, 0.0]),
        max_sites=2,
        minimum_separation_m=1.0,
        candidate_components=np.asarray(["main", "isolated"]),
        unreachable_component_weights={"isolated": 3.0},
    )
    assert selected == [1]
    assert trace[0]["newly_reachable_weight"] == 3.0


def test_balanced_selection_uses_maximin_vector_not_weighted_score() -> None:
    matrix = build_candidate_gain_matrix(*_fixture())
    selected, trace = balanced_greedy_select(
        matrix,
        {
            "left": np.asarray([1.0, 0.0]),
            "right": np.asarray([0.0, 1.0]),
        },
        np.asarray([1.0, 1.0]),
        np.asarray([0.0, 10.0]),
        np.asarray([0.0, 0.0]),
        max_sites=1,
        minimum_separation_m=1.0,
    )
    assert selected == [0]
    assert trace[0]["normalized_maximin_vector"] == [0.6, 1.0]
