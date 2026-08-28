from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPEN_DATA = ROOT / "analysis/outputs/real/open_data"


def _load(name: str) -> dict[str, object]:
    return json.loads((OPEN_DATA / name).read_text(encoding="utf-8"))


def test_real_municipal_open_data_analysis_has_all_audited_meshes_and_contexts() -> None:
    artifact = _load("municipal_open_data_analysis.geojson")
    features = artifact["features"]
    assert artifact["generated_from_synthetic_data"] is False
    assert artifact["public_distribution"] is False
    assert artifact["feature_count"] == len(features) == 822
    assert Counter(feature["properties"]["city_id"] for feature in features) == {
        "maizuru": 495,
        "fujisawa": 327,
    }
    required = {
        "plateau_spatial_model",
        "medical_access_v2",
        "care_access",
        "future_population_spatial",
        "daytime_activity_context",
        "earthquake_ground_context",
        "historical_traffic_safety_context",
    }
    assert all(required <= set(feature["properties"]) for feature in features)
    assert all(
        feature["properties"]["medical_access_v2"]["analysis_tier"] == "BASE"
        for feature in features
    )
    assert all(
        feature["properties"]["daytime_activity_context"]["employees_are_daytime_population"]
        is False
        for feature in features
    )
    assert any(
        feature["properties"]["medical_access_v2"]["straight_line"]["dental"]["distance_m"]
        is not None
        for feature in features
    )


def test_real_findings_are_review_candidates_without_scores_or_automatic_cases() -> None:
    artifact = _load("municipal_open_data_findings.json")
    findings = artifact["findings"]
    assert artifact["automatic_investigation_creation"] is False
    assert artifact["automatic_decision_creation"] is False
    assert artifact["finding_count"] == len(findings) > 0
    subtypes = Counter(finding["finding_subtype"] for finding in findings)
    assert subtypes["medical_access_review_candidate"] > 0
    assert subtypes["care_access_review_candidate"] > 0
    assert subtypes["activity_service_gap_candidate"] > 0
    assert "earthquake_ground_context" not in subtypes
    assert "historical_traffic_safety_context" not in subtypes
    assert all(finding["validation_status"] == "unvalidated" for finding in findings)
    assert all(finding["investigation_id"] is None for finding in findings)
    assert all(finding["decision_id"] is None for finding in findings)
    assert all(finding["combined_score"] is None for finding in findings)
    assert all(finding["priority_rank"] is None for finding in findings)


def test_real_evidence_preserves_lineage_mixed_years_and_missing_sources() -> None:
    evidence = _load("municipal_open_data_evidence.json")
    assert evidence["public_distribution"] is False
    assert evidence["review_status"] == "unvalidated_review_candidates"
    assert evidence["human_workflow"]["investigations_created"] is False
    assert evidence["human_workflow"]["decisions_created"] is False
    assert all(
        template["creation_status"] == "not_created_requires_human"
        for template in evidence["human_workflow"]["investigation_templates"]
    )
    for city in ("maizuru", "fujisawa"):
        periods = {item["reference_period"] for item in evidence["source_timeline"][city]}
        assert {"2020", "2021", "2022", "2025", "2026-06-01", "2026-06-30"} <= periods
    assert {item["dataset_family"] for item in evidence["missing_data"]} >= {
        "official_pedestrian_network",
        "social_participation",
        "traffic_volume",
        "gtfs",
        "gsi_foundation_map",
    }
    hashes = evidence["lineage"]["canonical_raw_sha256"]
    assert "b1d91bb65daaa3554026fcdc6426f7440356018fc0e6e18042c40ff9f54ac2f5" in hashes
    assert "f795cbe93f5f25aecc2fccea7be872a2581085bd780c2edb4f045a948b3ebeb7" in hashes
    assert all(analysis["tier"] == "BASE" for analysis in evidence["analyses"])


def test_real_summary_keeps_ground_and_accidents_as_context_only() -> None:
    summary = _load("municipal_open_data_analysis_summary.json")
    assert summary["mesh_count"] == 822
    assert summary["quality_model"]["single_quality_score"] is False
    assert summary["cities"]["maizuru"]["accident_coverage"] == {
        "municipality_filtered_record_count": 59,
        "linked_to_audited_mesh_count": 58,
        "unmatched_to_audited_mesh_count": 1,
        "unmatched_record_ids": ["npa-accident:b1d91bb65daaa355:2024-61-059-0007"],
    }
    assert (
        summary["cities"]["fujisawa"]["accident_coverage"]["unmatched_to_audited_mesh_count"] == 4
    )
    assert all(
        city["context_only_no_finding_types"]
        == [
            "earthquake_ground_context",
            "historical_traffic_safety_context",
            "future_population_spatial",
        ]
        for city in summary["cities"].values()
    )
