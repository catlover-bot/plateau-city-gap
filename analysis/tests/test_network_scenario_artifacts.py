from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real"


def _report() -> dict:
    return json.loads((OUTPUT / "maizuru_network_scenarios.json").read_text(encoding="utf-8"))


def test_real_network_scenario_contract_has_all_objectives_and_site_counts() -> None:
    report = _report()
    assert report["city"] == {"city_id": "26202", "name": "舞鶴市"}
    assert set(report["plans"]) == {
        "overall",
        "elderly",
        "worst_served",
        "robust",
        "balanced",
        "reachability",
    }
    for mode, plans in report["plans"].items():
        assert set(plans) == {"1", "2", "3", "4", "5"}
        assert len(report["diminishing_returns"][mode]) == 6
        assert [row["site_count"] for row in report["diminishing_returns"][mode]] == list(range(6))
        assert "exact" in plans["1"]["exactness"]
        for site_count in range(2, 6):
            plan = plans[str(site_count)]
            assert len(plan["sites"]) == site_count
            assert plan["exactness"] == (
                "deterministic forward-greedy approximation; not a global N-site optimum"
            )


def test_real_sites_keep_review_context_and_auditable_route_evidence() -> None:
    report = _report()
    required_flags = {
        "hazard_attention",
        "planning_attention",
        "landuse_attention",
        "network_component_attention",
        "long_connector_attention",
        "terrain_attention",
    }
    for plans in report["plans"].values():
        for plan in plans.values():
            for site in plan["sites"]:
                assert required_flags < set(site["feasibility_flags"])
                assert site["siting_feasibility"] == "not_determined"
                assert site["hazard_review_status"] in {
                    "additional_confirmation_required",
                    "no_overlap_in_source_layers",
                }
                assert site["road_gml_id"]
                assert site["road_source"]["source_member_crc32"]
                assert site["terrain"]["routing_penalty_applied"] is False
            evidence = plan["representative_evidence"]
            assert evidence["building_gml_id"]
            assert evidence["snap_node_id"]
            assert evidence["after"]["virtual_scenario_candidate_id"] in {
                site["candidate_id"] for site in plan["sites"]
            }
            assert len(evidence["after"]["road_node_sequence"]) == (
                len(evidence["after"]["road_edge_sequence"]) + 1
            )


def test_real_scenario_summary_performance_and_independent_verification_are_consistent() -> None:
    report = _report()
    summary = pd.read_csv(OUTPUT / "maizuru_network_scenario_summary.csv")
    performance = json.loads(
        (OUTPUT / "maizuru_network_scenario_performance.json").read_text(encoding="utf-8")
    )
    verification = json.loads(
        (OUTPUT / "maizuru_network_scenario_verification.json").read_text(encoding="utf-8")
    )
    assert len(summary) == 30
    assert summary.plan_id.nunique() == 30
    assert verification["passed"] is True
    assert all(verification["checks"].values())
    assert (
        performance["sparse_improvement_pair_count"]
        == report["sparse_gain_matrix"]["improving_candidate_demand_pairs"]
    )
    assert (
        performance["avoided_zero_gain_pair_count"]
        == report["sparse_gain_matrix"]["avoided_zero_gain_pair_count"]
    )
    assert set(performance["stage_runtime_by_objective_and_site_count"]) == set(report["plans"])
    assert all(
        set(timings) == {"1", "2", "3", "4", "5"}
        for timings in performance["stage_runtime_by_objective_and_site_count"].values()
    )


def test_public_asset_contains_only_the_two_selected_story_scenarios() -> None:
    public = json.loads(
        (ROOT / "frontend/public/data/network_scenario_story.json").read_text(encoding="utf-8")
    )
    assert [story["story_id"] for story in public["scenario_story"]] == [
        "scenario_a",
        "scenario_b",
    ]
    assert [story["mode"] for story in public["scenario_story"]] == [
        "overall",
        "worst_served",
    ]
    assert all(story["site_count"] == 3 for story in public["scenario_story"])
    assert all("mesh_results" not in story for story in public["scenario_story"])
    assert "plans" not in public
