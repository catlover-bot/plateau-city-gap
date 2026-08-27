from __future__ import annotations

import math

import pytest

from analysis.src.urban_resilience import (
    BuildingDemand,
    HazardClosureAssumption,
    NetworkEdge,
    ServiceChange,
    apply_service_changes,
    k_shortest_paths,
    multi_source_distances,
    network_criticality_candidates,
    run_network_stress_test,
    stress_test_cache_key,
    verify_bridge_by_removal,
)


def _edges() -> tuple[NetworkEdge, ...]:
    return (
        NetworkEdge("ab", "a", "b", 10),
        NetworkEdge("bc", "b", "c", 10),
        NetworkEdge("cd", "c", "d", 10),
        NetworkEdge("bd", "b", "d", 25),
        NetworkEdge("ce", "c", "e", 5),
    )


def _buildings() -> tuple[BuildingDemand, ...]:
    baseline = multi_source_distances(_edges(), {"a": 0})
    return tuple(
        BuildingDemand(
            f"building-{node}",
            node,
            2,
            10,
            4 if node in {"d", "e"} else 2,
            {"medical": baseline[node] + 2},
        )
        for node in ("b", "c", "d", "e")
    )


def test_hazard_overlap_requires_explicit_counterfactual_contract() -> None:
    with pytest.raises(ValueError, match="explicit counterfactual"):
        HazardClosureAssumption(
            "plateau-hazard-2025",
            "flood",
            ("3",),
            "overlap_edges_unavailable",
            "analyst-selected exercise",
            False,
        )
    assumption = HazardClosureAssumption(
        "plateau-hazard-2025",
        "flood",
        ("3",),
        "overlap_edges_unavailable",
        "analyst-selected exercise",
        True,
    )
    assert "not a prediction" in assumption.limitation


def test_stress_test_computes_reachability_distance_and_fragmentation() -> None:
    result = run_network_stress_test(
        _edges(), _buildings(), {"medical": {"a": 0}}, frozenset({"bc", "bd"})
    )
    medical = result.service_metrics["medical"]
    assert result.closed_edge_count == 2
    assert result.component_fragmentation_increase == 1
    assert medical["newly_unreachable_buildings"] == 3
    assert medical["estimated_elderly_population_disconnected"] == 10


def test_tarjan_criticality_matches_independent_edge_removal_verifier() -> None:
    candidates = network_criticality_candidates(
        _edges(), _buildings(), {"medical": {"a": 0}}
    )
    by_edge = {row.edge_id: row for row in candidates}
    assert set(by_edge) == {"ab", "ce"}
    assert by_edge["ab"].affected_buildings == 4
    assert by_edge["ab"].affected_estimated_elderly_population == 12
    assert verify_bridge_by_removal(_edges(), "ab") is True
    assert verify_bridge_by_removal(_edges(), "bc") is False


def test_selected_pair_has_primary_and_second_best_route() -> None:
    paths = k_shortest_paths(_edges(), "b", "d", 2)
    assert [path.edge_ids for path in paths] == [("bc", "cd"), ("bd",)]
    assert [path.distance_m for path in paths] == [20, 25]


def test_service_changes_are_never_fabricated_and_cache_key_is_version_complete() -> None:
    with pytest.raises(ValueError, match="user-input"):
        ServiceChange("hospital-x", "medical", "close", False, from_node_id="a")
    changed = apply_service_changes(
        {"medical": {"a": 3}},
        (
            ServiceChange(
                "hospital-x", "medical", "relocate", True, "a", "e", connector_m=4
            ),
        ),
    )
    assert changed == {"medical": {"e": 4}}
    key = stress_test_cache_key(
        "26202", "state-2025", "network-v1", {"closed_edges": ["ab"]}, "stress-v1"
    )
    changed_key = stress_test_cache_key(
        "26202", "state-2025", "network-v2", {"closed_edges": ["ab"]}, "stress-v1"
    )
    assert len(key) == 64 and key != changed_key
    assert math.isfinite(multi_source_distances(_edges(), {"a": 0})["e"])
