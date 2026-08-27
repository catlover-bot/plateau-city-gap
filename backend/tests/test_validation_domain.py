from __future__ import annotations

import pytest

from backend.citygap_platform.domain.validation import (
    CLAIM_REGISTRY,
    EVIDENCE_DIMENSIONS,
    UNCERTAINTY_CATEGORIES,
    EvidenceValue,
    ValidationStatus,
    claim_registry_payload,
    validate_evidence_strength,
    validation_priority_key,
)


def test_claim_registry_has_explicit_meaning_boundary_method_and_status() -> None:
    assert {claim.claim_key for claim in CLAIM_REGISTRY} == {
        "building_population_allocation",
        "building_euclidean_accessibility",
        "experimental_network_accessibility",
        "hazard_stress_test",
        "network_criticality",
        "future_population_allocation",
        "scenario_improvement",
        "planning_context",
        "shelter_reachability",
    }
    for claim in claim_registry_payload():
        assert claim["what_it_means"]
        assert claim["what_it_does_not_mean"]
        assert claim["required_data"]
        assert claim["validation_method"]
        assert claim["current_validation_status"] in {value.value for value in ValidationStatus}


def test_evidence_strength_is_not_a_percentage_or_aggregate_score() -> None:
    matrix = {dimension: EvidenceValue.NO.value for dimension in EVIDENCE_DIMENSIONS}
    assert validate_evidence_strength(matrix) == matrix
    with pytest.raises(ValueError):
        validate_evidence_strength({**matrix, "confidence": "82%"})
    with pytest.raises(ValueError):
        validate_evidence_strength({**matrix, EVIDENCE_DIMENSIONS[0]: "MAYBE"})


def test_uncertainty_categories_are_structured_and_priority_is_lexicographic() -> None:
    assert len(UNCERTAINTY_CATEGORIES) == 8
    records = [
        {"sample_id": "a", "reference_agreement": "large_difference", "coverage": 1.0},
        {"sample_id": "b", "connectivity_disagreement": True, "coverage": 0.9},
        {"sample_id": "c", "assumption_sensitive": True, "coverage": 0.5},
    ]
    assert [row["sample_id"] for row in sorted(records, key=validation_priority_key)] == [
        "b",
        "a",
        "c",
    ]

