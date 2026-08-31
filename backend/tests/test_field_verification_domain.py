import pytest

from backend.citygap_platform.domain.field_verification import (
    FieldConclusion,
    GpsCaptureState,
    MunicipalDisposition,
    TargetObjectType,
    TargetScope,
    VerificationKind,
    VerificationTaskStatus,
    automatic_confirmation_allowed,
    derive_template,
    finding_field_validation,
    review_task_status,
    validate_task_transition,
)


def test_every_uncertainty_has_a_bounded_deterministic_template():
    first = [derive_template(kind) for kind in VerificationKind]
    second = [derive_template(kind.value) for kind in VerificationKind]
    assert first == second
    assert all(3 <= len(template.requirements) <= 5 for template in first)
    assert all(template.reason and template.title for template in first)


def test_fixed_conditional_branches_are_explicit():
    gtfs = derive_template(VerificationKind.GTFS_SERVICE)
    terrain = derive_template(VerificationKind.TERRAIN_ACCESS)
    facility = derive_template(VerificationKind.FACILITY_AVAILABILITY)
    assert {item.relevant_when for item in gtfs.requirements} >= {"stop_present=no"}
    assert {item.relevant_when for item in terrain.requirements} >= {"steep_slope=yes"}
    assert {item.relevant_when for item in facility.requirements} >= {"facility_open=no"}


def test_task_transitions_cannot_skip_human_workflow():
    validate_task_transition(VerificationTaskStatus.UNVERIFIED, VerificationTaskStatus.ASSIGNED)
    validate_task_transition(VerificationTaskStatus.UNDER_REVIEW, VerificationTaskStatus.CLOSED)
    with pytest.raises(ValueError):
        validate_task_transition(
            VerificationTaskStatus.UNVERIFIED, VerificationTaskStatus.SUBMITTED
        )
    with pytest.raises(ValueError):
        validate_task_transition(VerificationTaskStatus.CLOSED, VerificationTaskStatus.ASSIGNED)


@pytest.mark.parametrize(
    ("conclusion", "expected"),
    [
        (FieldConclusion.SUPPORTED, "supported_by_field"),
        (FieldConclusion.CONTRADICTED, "contradicted_by_field"),
        (FieldConclusion.PARTIALLY_SUPPORTED, "partially_supported"),
        (FieldConclusion.NEEDS_MORE_DATA, "needs_more_data"),
        (FieldConclusion.NOT_ASSESSED, None),
    ],
)
def test_review_conclusion_maps_only_to_field_validation(conclusion, expected):
    assert finding_field_validation(conclusion) == expected


def test_disposition_is_separate_from_evidence_conclusion():
    assert review_task_status(
        FieldConclusion.NOT_ASSESSED, MunicipalDisposition.OUT_OF_SCOPE
    ) is VerificationTaskStatus.CLOSED
    assert review_task_status(
        FieldConclusion.NEEDS_MORE_DATA, MunicipalDisposition.CONTINUE_REVIEW
    ) is VerificationTaskStatus.NEEDS_MORE_DATA
    assert automatic_confirmation_allowed() is False


def test_public_enums_do_not_expand_into_generic_field_gis():
    assert set(TargetScope) == {
        TargetScope.MESH,
        TargetScope.PLATEAU_OBJECT,
        TargetScope.PLATEAU_OBJECT_GROUP,
    }
    assert set(TargetObjectType) == {
        TargetObjectType.MESH,
        TargetObjectType.BUILDING,
        TargetObjectType.ROAD,
        TargetObjectType.TERRAIN,
        TargetObjectType.LANDUSE,
        TargetObjectType.PLANNING,
        TargetObjectType.HAZARD,
        TargetObjectType.FACILITY,
    }
    assert GpsCaptureState.PERMISSION_DENIED.value == "permission_denied"
