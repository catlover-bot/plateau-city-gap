from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_real_urban_futures_validation_has_two_cities_and_golden_cases() -> None:
    artifact = json.loads(
        (ROOT / "analysis/outputs/real/urban_futures_validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["analysis_status"] == "real_official_data"
    assert artifact["generated_from_synthetic_data"] is False
    assert set(artifact["cities"]) == {"maizuru", "fujisawa"}
    assert len(artifact["golden_maizuru_cases"]) >= 5
    assert all(case["status"] == "pass" for case in artifact["golden_maizuru_cases"])
    maizuru = artifact["cities"]["maizuru"]
    assert set(maizuru["stress_tests"]) == {"flood", "landslide", "tsunami"}
    assert all(
        row["independent_removal_verifier"]
        for row in maizuru["criticality"]["independent_verification"]
    )
    assert maizuru["planning_context"]["legal_compliance_claimed"] is False
    assert maizuru["official_future_population"]["prediction_claimed"] is False


def test_public_resilience_artifact_is_aggregated_and_has_claim_boundaries() -> None:
    public = json.loads(
        (ROOT / "frontend/public/data/urban_futures_resilience.json").read_text(
            encoding="utf-8"
        )
    )
    assert public["building_level_demographics_included"] is False
    assert public["story"]["prediction_claimed"] is False
    serialized = json.dumps(public, ensure_ascii=False)
    assert "building_id" not in serialized
    assert "estimated_population_disconnected" in serialized


def test_synthetic_scale_artifact_executed_all_declared_scales() -> None:
    artifact = json.loads(
        (ROOT / "analysis/outputs/benchmarks/urban_resilience_scale.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["classification"] == "synthetic_performance_fixture_not_real_city_data"
    assert artifact["all_requested_scales_executed"] is True
    assert [row["road_edges"] for row in artifact["benchmarks"]] == [100_000, 250_000, 500_000]
    assert all(row["generated_from_synthetic_data"] for row in artifact["benchmarks"])
