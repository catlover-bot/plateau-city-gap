from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pyproj import Transformer

from analysis.src.decision_studio import deterministic_order, percentile_rank

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "analysis/outputs/real"
WEB = ROOT / "frontend/public/data"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_percentile_and_order_are_deterministic_with_ties() -> None:
    ranks = percentile_rank(np.asarray([10.0, 20.0, 20.0, 40.0]))
    assert np.allclose(ranks, [0.25, 0.625, 0.625, 1.0])
    assert deterministic_order(["3", "1", "2"], np.asarray([0.5, 0.5, 0.1]), np.ones(3)) == [1, 0, 2]


def test_robustness_scenarios_and_counts_are_published_without_probability_language() -> None:
    report = _json(OUTPUTS / "maizuru_robustness.json")
    assert report["scenario_count"] == 9
    assert [scenario["id"] for scenario in report["scenarios"]] == [
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
        "S7a",
        "S7b",
        "S8",
    ]
    rank_one = report["top_candidates"][0]
    assert rank_one["mesh_code"] == "533512753"
    assert rank_one["top10_frequency"] == 9
    assert rank_one["top20_frequency"] == 9
    assert (rank_one["rank_min"], rank_one["rank_max"]) == (1, 5)
    assert "確率" in report["interpretation"]
    assert "信頼度" in report["interpretation"]


def test_intervention_plans_cover_one_two_three_sites_and_diminishing_returns() -> None:
    report = _json(WEB / "intervention_scenarios.json")
    assert report["metadata"]["candidate_count"] == 12_062
    assert "approximate" in report["metadata"]["exactness"]
    overall = report["plans"]["overall"]
    assert [len(overall[str(count)]["sites"]) for count in (1, 2, 3)] == [1, 2, 3]
    assert overall["1"]["sites"][0]["candidate_id"] == "tran_cc18f5e0-cb03-484f-8756-8ead484d3c36-0"
    assert [overall[str(count)]["impact"]["improved_mesh_count"] for count in (1, 2, 3)] == [5, 7, 9]
    reductions = [row["total_score_c_reduction"] for row in report["diminishing_returns"]]
    assert reductions == sorted(reductions)


def test_fairness_and_robust_objectives_produce_distinct_comparison_plans() -> None:
    report = _json(WEB / "intervention_scenarios.json")
    overall = report["plans"]["overall"]["2"]
    fairness = report["plans"]["fairness"]["2"]
    robust = report["plans"]["robust"]["2"]
    assert fairness["sites"] != overall["sites"]
    assert robust["sites"] != overall["sites"]
    assert fairness["impact"]["worst_decile_mean_reduction_m"] > overall["impact"]["worst_decile_mean_reduction_m"]
    assert robust["impact"]["robust_top20_improved_count"] > overall["impact"]["robust_top20_improved_count"]


def test_candidate_constraints_verification_and_evidence_are_consistent() -> None:
    report = _json(WEB / "intervention_scenarios.json")
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
    for mode_plans in report["plans"].values():
        for plan in mode_plans.values():
            assert all(site["existing_transport_distance_m"] > 150 for site in plan["sites"])
            x, y = transformer.transform(
                [site["longitude"] for site in plan["sites"]],
                [site["latitude"] for site in plan["sites"]],
            )
            assert all(
                np.hypot(x[left] - x[right], y[left] - y[right]) >= 1_500 - 1e-3
                for left in range(len(x))
                for right in range(left)
            )
    verification = _json(OUTPUTS / "maizuru_decision_studio_verification.json")
    evidence = _json(WEB / "evidence.json")
    assert verification["plans_checked"] == 9
    assert verification["exact_match"] is True
    assert evidence["rank_one"]["transport"]["value_m"] == 2321.6556089062638
    assert evidence["intervention"]["plans"]["overall"]["1"]["impact"] == report["plans"]["overall"]["1"]["impact"]
