from __future__ import annotations

import pandas as pd

from analysis.src.sensitivity_validation import (
    criticality_robustness,
    hazard_assumption_edge_sets,
)


def test_hazard_assumptions_are_named_bounded_real_attribute_rules() -> None:
    edges = pd.DataFrame(
        [
            {"edge_id": "e1", "source_node_id": "a", "target_node_id": "b", "length_m": 10.0},
            {"edge_id": "e2", "source_node_id": "b", "target_node_id": "c", "length_m": 10.0},
            {"edge_id": "e3", "source_node_id": "d", "target_node_id": "e", "length_m": 10.0},
        ]
    )
    nodes = pd.DataFrame(
        [
            {"node_id": "a", "gml_id": "road-a"},
            {"node_id": "b", "gml_id": "road-b"},
            {"node_id": "c", "gml_id": "road-c"},
            {"node_id": "d", "gml_id": "road-d"},
            {"node_id": "e", "gml_id": "road-e"},
        ]
    )
    hazards = pd.DataFrame(
        [
            {"edge_id": "e1", "rank_code": "1", "rank_label": "one", "intersection_length_m": 6.0},
            {"edge_id": "e2", "rank_code": "2", "rank_label": "two", "intersection_length_m": 2.0},
        ]
    )
    rules = hazard_assumption_edge_sets(hazards, edges, nodes, {"e2"})
    assert set(rules) == {
        "S1_all_overlap_edges",
        "S2_published_rank_threshold",
        "S3_overlap_ratio_threshold",
        "S4_road_group_closure",
        "S5_critical_overlap_only",
    }
    assert rules["S3_overlap_ratio_threshold"]["closed_edges"] == frozenset({"e1"})
    assert rules["S5_critical_overlap_only"]["closed_edges"] == frozenset({"e2"})


def test_criticality_robustness_reports_ranges_not_magic_score() -> None:
    result = criticality_robustness(
        {
            "baseline": [
                {"edge_id": "e1", "affected_buildings": 10, "affected_estimated_elderly_population": 3.0}
            ],
            "snap_50m": [
                {"edge_id": "e1", "affected_buildings": 7, "affected_estimated_elderly_population": 2.0},
                {"edge_id": "e2", "affected_buildings": 1, "affected_estimated_elderly_population": 0.2},
            ],
        }
    )
    assert result[0]["edge_id"] == "e1"
    assert result[0]["present_in_n_models"] == 2
    assert result[0]["affected_building_range"] == [7, 10]
    assert "score" not in result[0]
