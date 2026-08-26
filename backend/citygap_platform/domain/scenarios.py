"""Scenario review lifecycle and human field-check contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ScenarioStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    FIELD_CHECK_REQUIRED = "field_check_required"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


ALLOWED_TRANSITIONS: dict[ScenarioStatus, frozenset[ScenarioStatus]] = {
    ScenarioStatus.DRAFT: frozenset({ScenarioStatus.UNDER_REVIEW, ScenarioStatus.ARCHIVED}),
    ScenarioStatus.UNDER_REVIEW: frozenset(
        {
            ScenarioStatus.FIELD_CHECK_REQUIRED,
            ScenarioStatus.REVIEWED,
            ScenarioStatus.ARCHIVED,
        }
    ),
    ScenarioStatus.FIELD_CHECK_REQUIRED: frozenset(
        {
            ScenarioStatus.UNDER_REVIEW,
            ScenarioStatus.REVIEWED,
            ScenarioStatus.ARCHIVED,
        }
    ),
    ScenarioStatus.REVIEWED: frozenset({ScenarioStatus.UNDER_REVIEW, ScenarioStatus.ARCHIVED}),
    ScenarioStatus.ARCHIVED: frozenset(),
}


def validate_status_transition(
    current: str, proposed: str
) -> tuple[ScenarioStatus, ScenarioStatus]:
    """Validate an explicit human lifecycle transition.

    A draft cannot become reviewed in one operation. This makes review a visible
    workflow event and prevents an optimizer or import job from silently approving a plan.
    """

    try:
        current_status = ScenarioStatus(current)
        proposed_status = ScenarioStatus(proposed)
    except ValueError as error:
        raise ValueError("Unknown scenario lifecycle status") from error
    if proposed_status not in ALLOWED_TRANSITIONS[current_status]:
        raise ValueError(f"Invalid scenario transition: {current_status} -> {proposed_status}")
    return current_status, proposed_status


class FieldCheckValue(str, Enum):
    UNKNOWN = "unknown"
    CONFIRMED = "confirmed"
    ATTENTION = "attention"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class FieldCheck:
    site_access: FieldCheckValue = FieldCheckValue.UNKNOWN
    road_safety: FieldCheckValue = FieldCheckValue.UNKNOWN
    land_ownership_unknown: FieldCheckValue = FieldCheckValue.UNKNOWN
    existing_service: FieldCheckValue = FieldCheckValue.UNKNOWN
    facility_condition: FieldCheckValue = FieldCheckValue.UNKNOWN
    hazard_confirmation: FieldCheckValue = FieldCheckValue.UNKNOWN
    operator_consultation: FieldCheckValue = FieldCheckValue.UNKNOWN
    notes: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> FieldCheck:
        fields = {}
        for name in (
            "site_access",
            "road_safety",
            "land_ownership_unknown",
            "existing_service",
            "facility_condition",
            "hazard_confirmation",
            "operator_consultation",
        ):
            fields[name] = FieldCheckValue(value.get(name, FieldCheckValue.UNKNOWN))
        fields["notes"] = str(value.get("notes", "")).strip()
        return cls(**fields)

    def as_dict(self) -> dict[str, Any]:
        return {
            "site_access": self.site_access.value,
            "road_safety": self.road_safety.value,
            "land_ownership_unknown": self.land_ownership_unknown.value,
            "existing_service": self.existing_service.value,
            "facility_condition": self.facility_condition.value,
            "hazard_confirmation": self.hazard_confirmation.value,
            "operator_consultation": self.operator_consultation.value,
            "notes": self.notes,
        }
