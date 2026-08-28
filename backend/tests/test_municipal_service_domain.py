from __future__ import annotations

import pytest

from backend.citygap_platform.domain.municipal_service import (
    ANALYSIS_CATALOG,
    SERVICE_ENTITIES,
    AnalysisTier,
    DataClassification,
    DatasetReleaseStatus,
    DecisionRecordDraft,
    DecisionValue,
    FindingStatus,
    InvestigationStatus,
    ProductRole,
    ReviewStatus,
    decode_cursor,
    encode_cursor,
    evaluate_analysis_tier,
    validate_dataset_transition,
    validate_finding_transition,
    validate_investigation_transition,
    validate_review_transition,
)


def test_required_municipal_entities_and_roles_are_explicit() -> None:
    assert len(SERVICE_ENTITIES) == 27
    assert {
        "Organization",
        "OpenDataAdapter",
        "OpenDataSource",
        "DataCoverage",
        "CanonicalOpenDataRecord",
        "Finding",
        "Investigation",
        "DecisionRecord",
        "AuditEvent",
    } <= set(SERVICE_ENTITIES)
    assert set(ProductRole) == {
        ProductRole.VIEWER,
        ProductRole.ANALYST,
        ProductRole.PLANNER,
        ProductRole.FIELD_STAFF,
        ProductRole.DATA_MANAGER,
        ProductRole.ADMINISTRATOR,
    }
    assert set(DataClassification) == {
        DataClassification.PUBLIC,
        DataClassification.INTERNAL,
        DataClassification.RESTRICTED,
    }


def test_finding_review_and_dataset_lifecycle_reject_shortcuts() -> None:
    validate_finding_transition(FindingStatus.NEW, FindingStatus.TRIAGED)
    validate_finding_transition(FindingStatus.TRIAGED, FindingStatus.INVESTIGATING)
    validate_review_transition(ReviewStatus.REQUESTED, ReviewStatus.IN_REVIEW)
    validate_review_transition(ReviewStatus.IN_REVIEW, ReviewStatus.REVIEWED)
    validate_dataset_transition(DatasetReleaseStatus.REGISTERED, DatasetReleaseStatus.VALIDATING)
    validate_dataset_transition(DatasetReleaseStatus.VALIDATED, DatasetReleaseStatus.ACCEPTED)
    validate_dataset_transition(DatasetReleaseStatus.ANALYSIS_READY, DatasetReleaseStatus.PROMOTED)
    validate_investigation_transition(
        InvestigationStatus.IN_REVIEW, InvestigationStatus.DECISION_PENDING
    )
    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        validate_finding_transition(FindingStatus.NEW, FindingStatus.RESOLVED)
    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        validate_review_transition(ReviewStatus.REQUESTED, ReviewStatus.REVIEWED)
    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        validate_dataset_transition(DatasetReleaseStatus.VALIDATED, DatasetReleaseStatus.PROMOTED)
    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        validate_investigation_transition(InvestigationStatus.OPEN, InvestigationStatus.CLOSED)


def test_decision_record_is_human_reviewed_and_evidence_backed() -> None:
    DecisionRecordDraft(
        decision=DecisionValue.ADDITIONAL_INVESTIGATION,
        reason="現地確認結果を追加する必要があるため",
        actor="planner@example.invalid",
        review_status=ReviewStatus.REVIEWED,
        related_evidence_ids=("evidence-1",),
    ).validate()
    with pytest.raises(ValueError, match="explicit human"):
        DecisionRecordDraft(
            decision=DecisionValue.ADOPTED,
            reason="optimizer output",
            actor="optimizer",
            review_status=ReviewStatus.REVIEWED,
            related_evidence_ids=("evidence-1",),
            source="optimizer",
        ).validate()


def test_analysis_catalog_has_versioned_parameters_and_claim_boundaries() -> None:
    assert len(ANALYSIS_CATALOG) == 12
    assert len({definition.analysis_id for definition in ANALYSIS_CATALOG}) == len(ANALYSIS_CATALOG)
    assert all(
        definition.algorithm_version and definition.claim_boundary
        for definition in ANALYSIS_CATALOG
    )
    candidate_limit = ANALYSIS_CATALOG[0].parameters[0]
    assert candidate_limit.minimum == 1 and candidate_limit.maximum == 100
    v2 = {definition.analysis_id: definition for definition in ANALYSIS_CATALOG}
    assert {
        "medical-access-v2",
        "care-access",
        "future-population-spatial",
        "daytime-activity-context",
        "earthquake-ground-context",
        "historical-traffic-safety-context",
    } <= set(v2)
    assert all(
        v2[key].dataset_requirements
        for key in v2
        if key
        in {
            "medical-access-v2",
            "care-access",
            "future-population-spatial",
            "daytime-activity-context",
            "earthquake-ground-context",
            "historical-traffic-safety-context",
        }
    )


def test_analysis_tiers_degrade_without_hiding_missing_datasets() -> None:
    medical = next(
        definition
        for definition in ANALYSIS_CATALOG
        if definition.analysis_id == "medical-access-v2"
    )
    unavailable = evaluate_analysis_tier(medical, {"mhlw_medical"})
    assert unavailable.tier is AnalysisTier.UNAVAILABLE
    assert unavailable.missing_required == ("census_population_500m",)

    base = evaluate_analysis_tier(
        medical, {"census_population_500m", "mhlw_medical", "plateau_buildings"}
    )
    assert base.tier is AnalysisTier.BASE
    assert base.missing_optional == ("road_network",)
    assert base.missing_enhancement == ("official_pedestrian_network",)

    enhanced = evaluate_analysis_tier(
        medical,
        {
            "census_population_500m",
            "mhlw_medical",
            "plateau_buildings",
            "road_network",
            "official_pedestrian_network",
        },
    )
    assert enhanced.tier is AnalysisTier.ENHANCED


def test_cursor_round_trip_and_invalid_payload() -> None:
    cursor = encode_cursor({"created_at": "2026-08-28T00:00:00Z", "id": "item-1"})
    assert decode_cursor(cursor) == {
        "created_at": "2026-08-28T00:00:00Z",
        "id": "item-1",
    }
    with pytest.raises(ValueError, match="Invalid pagination cursor"):
        decode_cursor("not-json")
