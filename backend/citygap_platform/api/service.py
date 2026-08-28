"""Stable v1 HTTP surface for CITY GAP municipal operations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.citygap_platform.domain.municipal_service import (
    DataClassification,
    DatasetReleaseStatus,
    DecisionValue,
    FindingStatus,
    FindingType,
    InvestigationStatus,
    ReviewStatus,
)
from backend.citygap_platform.observability import render_request_metrics
from backend.citygap_platform.security.auth import (
    Identity,
    require_organization,
    require_permission,
)

from .service_repository import MunicipalServiceRepository

router = APIRouter(prefix="/api/v1", tags=["municipal-service"])


def _repository(request: Request) -> MunicipalServiceRepository:
    return request.app.state.repository


def _identity(request: Request) -> Identity:
    identity: Identity | None = getattr(request.state, "identity", None)
    if identity is None:
        raise HTTPException(status_code=401, detail="Identity unavailable")
    return identity


def _not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{resource} not found in this organization")


def _conflict(error: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(error))


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindingCreateRequest(StrictRequest):
    finding_type: FindingType
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=5000)
    urban_state_id: UUID | None = None
    source_analysis_run_id: UUID | None = None
    validation_status: Literal[
        "unvalidated", "internally_validated", "externally_compared", "field_validated"
    ] = "unvalidated"
    geometry: dict[str, Any] | None = None

    @field_validator("geometry")
    @classmethod
    def validate_geojson(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and not {"type", "coordinates"} <= set(value):
            raise ValueError("geometry must be a GeoJSON geometry")
        return value


class CityCreateRequest(StrictRequest):
    city_code: str = Field(pattern=r"^[0-9]{5}$")
    city_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str = Field(min_length=1, max_length=300)
    prefecture_code: str = Field(pattern=r"^[0-9]{2}$")
    prefecture_name: str = Field(min_length=1, max_length=100)
    analysis_crs: str = Field(pattern=r"^EPSG:[0-9]{4,6}$")


class DatasetRegisterRequest(StrictRequest):
    dataset_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,99}$")
    title: str = Field(min_length=1, max_length=500)
    provider: str = Field(min_length=1, max_length=500)
    dataset_category: Literal[
        "plateau",
        "population",
        "facilities",
        "transport",
        "hazard",
        "planning",
        "municipal_custom",
    ]
    data_classification: DataClassification = DataClassification.INTERNAL
    version_key: str = Field(min_length=1, max_length=200)
    dataset_year: int = Field(ge=1900, le=2200)
    data_format: str = Field(min_length=1, max_length=100)
    source_url: str | None = Field(default=None, max_length=2000)
    license: str | None = Field(default=None, max_length=500)
    declared_source_crs: str | None = Field(default=None, max_length=100)


class UrbanStateCreateRequest(StrictRequest):
    state_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,99}$")
    label: str = Field(min_length=1, max_length=500)
    effective_date: date
    state_type: Literal["observed", "future", "scenario"] = "observed"
    primary_dataset_version_id: UUID
    base_state_id: UUID | None = None
    source_verified: bool
    population_model: str | None = Field(default=None, max_length=2000)
    fixed_service_assumption: bool = False

    @model_validator(mode="after")
    def state_contract(self) -> UrbanStateCreateRequest:
        if self.state_type != "observed" and self.base_state_id is None:
            raise ValueError("Future and scenario states require base_state_id")
        if self.state_type == "future" and not self.population_model:
            raise ValueError("Future states require a declared population_model")
        return self


class UrbanStateTransitionRequest(StrictRequest):
    expected_status: Literal["draft", "validated", "current", "superseded", "archived"]
    proposed_status: Literal["draft", "validated", "current", "superseded", "archived"]
    note: str = Field(min_length=1, max_length=4000)


class FindingTransitionRequest(StrictRequest):
    expected_status: FindingStatus
    proposed_status: FindingStatus
    dismissal_reason: str | None = Field(default=None, max_length=4000)


class InvestigationCreateRequest(StrictRequest):
    urban_state_id: UUID
    title: str = Field(min_length=1, max_length=500)
    objective: str = Field(min_length=1, max_length=5000)
    workspace_id: UUID | None = None
    finding_ids: list[UUID] = Field(default_factory=list, max_length=100)
    assigned_to: UUID | None = None
    due_date: date | None = None
    spatial_state: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=10000)


class InvestigationTransitionRequest(StrictRequest):
    expected_status: InvestigationStatus
    proposed_status: InvestigationStatus
    note: str = Field(default="", max_length=4000)


class SavedViewCreateRequest(StrictRequest):
    title: str = Field(min_length=1, max_length=500)
    spatial_state: dict[str, Any]
    data_classification: DataClassification = DataClassification.INTERNAL


class ReviewCreateRequest(StrictRequest):
    reviewer_id: UUID | None = None
    request_note: str = Field(default="", max_length=5000)


class ReviewTransitionRequest(StrictRequest):
    expected_status: ReviewStatus
    proposed_status: ReviewStatus
    review_note: str = Field(default="", max_length=10000)


class ReviewNoteCreateRequest(StrictRequest):
    body: str = Field(min_length=1, max_length=10000)
    parent_note_id: UUID | None = None


class AssignmentCreateRequest(StrictRequest):
    assignment_type: Literal["investigation", "review", "field_check"]
    resource_id: UUID
    assigned_to: UUID
    due_date: date | None = None
    note: str = Field(default="", max_length=4000)


class FieldObservationCreateRequest(StrictRequest):
    observation_type: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=10000)
    observed_at: datetime
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    related_finding_id: UUID | None = None
    related_scenario_run_id: UUID | None = None
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def paired_coordinates(self) -> FieldObservationCreateRequest:
        if (self.longitude is None) != (self.latitude is None):
            raise ValueError("longitude and latitude must be supplied together")
        return self


class DecisionRecordCreateRequest(StrictRequest):
    review_request_id: UUID
    decision: DecisionValue
    reason: str = Field(min_length=1, max_length=10000)
    related_evidence_ids: list[UUID] = Field(min_length=1, max_length=100)
    related_scenario_run_id: UUID | None = None
    official_approval_reference: str | None = Field(default=None, max_length=2000)


class DatasetTransitionRequest(StrictRequest):
    expected_status: DatasetReleaseStatus
    proposed_status: DatasetReleaseStatus
    note: str = Field(min_length=1, max_length=4000)


class AnalysisRunCreateRequest(StrictRequest):
    analysis_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    analysis_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    urban_state_id: UUID
    dataset_versions: dict[str, UUID] = Field(min_length=1, max_length=30)
    parameters: dict[str, Any] = Field(default_factory=dict, max_length=50)

    @field_validator("dataset_versions")
    @classmethod
    def safe_input_roles(cls, value: dict[str, UUID]) -> dict[str, UUID]:
        if any(not role.replace("_", "").isalnum() or len(role) > 100 for role in value):
            raise ValueError("dataset input roles must be bounded identifiers")
        return value


class ScenarioComparisonCreateRequest(StrictRequest):
    title: str = Field(min_length=1, max_length=500)
    scenario_run_ids: list[UUID] = Field(min_length=2, max_length=3)
    comparison_dimensions: list[dict[str, Any]] = Field(min_length=1, max_length=30)
    investigation_id: UUID | None = None

    @field_validator("scenario_run_ids")
    @classmethod
    def unique_scenarios(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("scenario_run_ids must be unique")
        return value


class EvidenceCenterCreateRequest(StrictRequest):
    investigation_id: UUID | None = None
    scenario_run_id: UUID | None = None
    source_manifest: dict[str, Any]
    algorithm_manifest: dict[str, Any]
    validation_manifest: dict[str, Any]
    field_evidence_manifest: list[dict[str, Any]] = Field(default_factory=list)
    decision_manifest: list[dict[str, Any]] = Field(default_factory=list)
    data_classification: DataClassification = DataClassification.INTERNAL

    @model_validator(mode="after")
    def only_one_subject(self) -> EvidenceCenterCreateRequest:
        if self.investigation_id is not None and self.scenario_run_id is not None:
            raise ValueError("Evidence Center can reference one primary subject")
        return self


class ReportCreateRequest(StrictRequest):
    report_type: Literal[
        "investigation",
        "scenario_comparison",
        "annual_change",
        "resilience_review",
        "data_quality",
    ]
    title: str = Field(min_length=1, max_length=500)
    investigation_id: UUID | None = None
    scenario_comparison_id: UUID | None = None
    data_classification: DataClassification = DataClassification.INTERNAL


class ReportExportRequest(StrictRequest):
    export_scope: Literal["public", "internal"]


class UsageEventRequest(StrictRequest):
    event_name: Literal["feature_used", "workflow_completed", "workflow_error"]
    feature_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,99}$")
    city: str | None = Field(default=None, max_length=100)


class JobOperationRequest(StrictRequest):
    action: Literal["retry", "cancel"]
    expected_state: Literal["queued", "failed"]
    reason: str = Field(min_length=1, max_length=4000)
    cancel_confirmation: Literal["cancel"] | None = None

    @model_validator(mode="after")
    def operation_matches_state(self) -> JobOperationRequest:
        if self.action == "cancel" and (
            self.expected_state != "queued" or self.cancel_confirmation != "cancel"
        ):
            raise ValueError("Cancelling requires queued state and explicit confirmation")
        if self.action == "retry" and self.expected_state != "failed":
            raise ValueError("Retry requires failed state")
        return self


@router.get("/me")
def current_user(
    request: Request,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    identity = _identity(request)
    profile = repo.service_profile(organization_id, identity.actor, identity.issuer)
    if profile is None:
        raise _not_found("Organization")
    return {
        "actor": identity.actor,
        "issuer": identity.issuer,
        "roles": sorted(identity.roles),
        **profile,
    }


@router.get("/organizations/current")
def current_organization(
    request: Request,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    identity = _identity(request)
    profile = repo.service_profile(organization_id, identity.actor, identity.issuer)
    if profile is None:
        raise _not_found("Organization")
    return profile["organization"]


@router.get("/cities", dependencies=[Depends(require_permission("platform:read"))])
def cities(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    return {"items": repo.service_cities(organization_id)}


@router.post(
    "/cities",
    status_code=201,
    dependencies=[Depends(require_permission("organization:manage"))],
)
def create_city(
    body: CityCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        return repo.create_service_city(organization_id, body.model_dump(mode="json"))
    except ValueError as error:
        raise _conflict(error) from error


@router.get("/cities/{city}/home", dependencies=[Depends(require_permission("platform:read"))])
def city_home(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.city_service_home(organization_id, city)
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/cities/{city}/onboarding",
    dependencies=[Depends(require_permission("platform:read"))],
)
def city_onboarding(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.city_onboarding(organization_id, city)
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/cities/{city}/urban-states",
    dependencies=[Depends(require_permission("platform:read"))],
)
def urban_states(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    items = repo.service_urban_states(organization_id, city, limit)
    if items is None:
        raise _not_found("City")
    return {"items": items}


@router.post(
    "/cities/{city}/urban-states",
    status_code=201,
    dependencies=[Depends(require_permission("dataset:promote"))],
)
def create_urban_state(
    city: str,
    body: UrbanStateCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_service_urban_state(
            organization_id, city, body.model_dump(mode="json")
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("City")
    return result


@router.patch(
    "/urban-states/{state_id}/status",
    dependencies=[Depends(require_permission("dataset:promote"))],
)
def transition_urban_state(
    state_id: UUID,
    body: UrbanStateTransitionRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_service_urban_state(
            organization_id,
            str(state_id),
            body.expected_status,
            body.proposed_status,
            body.note,
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Urban State")
    return result


@router.get(
    "/cities/{city}/findings",
    dependencies=[Depends(require_permission("finding:read"))],
)
def findings(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    status: FindingStatus | None = None,
    finding_type: FindingType | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> dict[str, Any]:
    try:
        result = repo.findings(
            organization_id,
            city,
            status.value if status else None,
            finding_type.value if finding_type else None,
            q,
            limit,
            cursor,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("City")
    return result


@router.post(
    "/cities/{city}/findings",
    status_code=201,
    dependencies=[Depends(require_permission("finding:write"))],
)
def create_finding(
    city: str,
    body: FindingCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.create_finding(organization_id, city, body.model_dump(mode="json"))
    if result is None:
        raise _not_found("City")
    return result


@router.patch(
    "/findings/{finding_id}/status",
    dependencies=[Depends(require_permission("finding:write"))],
)
def transition_finding(
    finding_id: UUID,
    body: FindingTransitionRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_finding(
            organization_id,
            str(finding_id),
            body.expected_status.value,
            body.proposed_status.value,
            body.dismissal_reason,
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Finding")
    return result


@router.post(
    "/cities/{city}/investigations",
    status_code=201,
    dependencies=[Depends(require_permission("investigation:write"))],
)
def create_investigation(
    city: str,
    body: InvestigationCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_investigation(organization_id, city, body.model_dump(mode="json"))
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/cities/{city}/investigations",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def investigations(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    status: InvestigationStatus | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    items = repo.investigations(organization_id, city, status.value if status else None, q, limit)
    if items is None:
        raise _not_found("City")
    return {"items": items}


@router.get(
    "/investigations/{investigation_id}",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def investigation_detail(
    investigation_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.investigation_detail(organization_id, str(investigation_id))
    if result is None:
        raise _not_found("Investigation")
    return result


@router.patch(
    "/investigations/{investigation_id}/status",
    dependencies=[Depends(require_permission("investigation:write"))],
)
def transition_investigation(
    investigation_id: UUID,
    body: InvestigationTransitionRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_investigation(
            organization_id,
            str(investigation_id),
            body.expected_status.value,
            body.proposed_status.value,
            body.note,
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Investigation")
    return result


@router.post(
    "/investigations/{investigation_id}/saved-views",
    status_code=201,
    dependencies=[Depends(require_permission("investigation:write"))],
)
def create_saved_view(
    investigation_id: UUID,
    body: SavedViewCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.save_investigation_view(
        organization_id, str(investigation_id), body.model_dump(mode="json")
    )
    if result is None:
        raise _not_found("Investigation")
    return result


@router.post(
    "/investigations/{investigation_id}/reviews",
    status_code=201,
    dependencies=[Depends(require_permission("review:write"))],
)
def create_review(
    investigation_id: UUID,
    body: ReviewCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.create_review(
        organization_id, str(investigation_id), body.model_dump(mode="json")
    )
    if result is None:
        raise _not_found("Investigation")
    return result


@router.patch(
    "/reviews/{review_id}/status",
    dependencies=[Depends(require_permission("review:write"))],
)
def transition_review(
    review_id: UUID,
    body: ReviewTransitionRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_review(
            organization_id,
            str(review_id),
            body.expected_status.value,
            body.proposed_status.value,
            body.review_note,
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Review")
    return result


@router.post(
    "/investigations/{investigation_id}/field-observations",
    status_code=201,
    dependencies=[Depends(require_permission("field:write"))],
)
def create_field_observation(
    investigation_id: UUID,
    body: FieldObservationCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_field_observation(
            organization_id, str(investigation_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Investigation")
    return result


@router.post(
    "/comments/{resource_type}/{resource_id}",
    status_code=201,
    dependencies=[Depends(require_permission("comment:write"))],
)
def create_comment(
    resource_type: Literal["finding", "investigation", "scenario", "review", "field_observation"],
    resource_id: UUID,
    body: ReviewNoteCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.create_review_note(
        organization_id,
        resource_type,
        str(resource_id),
        body.body,
        str(body.parent_note_id) if body.parent_note_id else None,
    )
    if result is None:
        raise _not_found(resource_type.replace("_", " ").title())
    return result


@router.post(
    "/assignments",
    status_code=201,
    dependencies=[Depends(require_permission("assignment:write"))],
)
def create_assignment(
    body: AssignmentCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_assignment(organization_id, body.model_dump(mode="json"))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("Assignment resource")
    return result


@router.get("/work-queue", dependencies=[Depends(require_permission("platform:read"))])
def work_queue(
    request: Request,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    identity = _identity(request)
    return repo.work_queue(organization_id, identity.actor, identity.issuer)


@router.post(
    "/investigations/{investigation_id}/decisions",
    status_code=201,
    dependencies=[Depends(require_permission("decision:write"))],
)
def create_decision_record(
    investigation_id: UUID,
    body: DecisionRecordCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_decision_record(
            organization_id, str(investigation_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Reviewed investigation")
    return result


@router.get(
    "/cities/{city}/data-hub",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def data_hub(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.data_hub(organization_id, city)
    if result is None:
        raise _not_found("City")
    return result


@router.post(
    "/cities/{city}/datasets",
    status_code=201,
    dependencies=[Depends(require_permission("dataset:register"))],
)
def register_dataset(
    city: str,
    body: DatasetRegisterRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.register_service_dataset(organization_id, city, body.model_dump(mode="json"))
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("City")
    return result


@router.patch("/dataset-versions/{version_id}/status")
def transition_dataset_version(
    version_id: UUID,
    body: DatasetTransitionRequest,
    request: Request,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    identity = _identity(request)
    permission = {
        DatasetReleaseStatus.VALIDATING: "dataset:validate",
        DatasetReleaseStatus.VALIDATED: "dataset:validate",
        DatasetReleaseStatus.ACCEPTED: "dataset:accept",
        DatasetReleaseStatus.INGESTING: "dataset:accept",
        DatasetReleaseStatus.ANALYSIS_READY: "dataset:promote",
        DatasetReleaseStatus.PROMOTED: "dataset:promote",
        DatasetReleaseStatus.REJECTED: "dataset:accept",
        DatasetReleaseStatus.FAILED: "dataset:validate",
        DatasetReleaseStatus.REGISTERED: "dataset:register",
    }[body.proposed_status]
    if not identity.permits(permission):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
    try:
        result = repo.transition_dataset_version(
            organization_id,
            str(version_id),
            body.expected_status.value,
            body.proposed_status.value,
            body.note,
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Dataset version")
    return result


@router.get(
    "/analysis-definitions",
    dependencies=[Depends(require_permission("analysis:read"))],
)
def analysis_definitions(
    _organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    return {"items": repo.analysis_catalog()}


@router.get(
    "/cities/{city}/analysis-runs",
    dependencies=[Depends(require_permission("analysis:read"))],
)
def analysis_runs(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    items = repo.service_analysis_runs(organization_id, city, limit)
    if items is None:
        raise _not_found("City")
    return {"items": items}


@router.post(
    "/cities/{city}/analysis-runs",
    status_code=202,
    dependencies=[Depends(require_permission("analysis:run"))],
)
def create_analysis_run(
    city: str,
    body: AnalysisRunCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_service_analysis_run(
            organization_id, city, body.model_dump(mode="json")
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/cities/{city}/scenarios",
    dependencies=[Depends(require_permission("scenario:read"))],
)
def scenario_library(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    items = repo.scenario_library(organization_id, city, limit)
    if items is None:
        raise _not_found("City")
    return {"items": items}


@router.get(
    "/cities/{city}/scenario-comparisons",
    dependencies=[Depends(require_permission("scenario:read"))],
)
def scenario_comparisons(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    items = repo.scenario_comparisons(organization_id, city, limit)
    if items is None:
        raise _not_found("City")
    return {"items": items}


@router.post(
    "/cities/{city}/scenario-comparisons",
    status_code=201,
    dependencies=[Depends(require_permission("scenario:draft"))],
)
def create_scenario_comparison(
    city: str,
    body: ScenarioComparisonCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_scenario_comparison(
            organization_id, city, body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("City")
    return result


@router.post(
    "/cities/{city}/evidence-centers",
    status_code=201,
    dependencies=[Depends(require_permission("evidence:export"))],
)
def create_evidence_center(
    city: str,
    body: EvidenceCenterCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_evidence_center(organization_id, city, body.model_dump(mode="json"))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/cities/{city}/evidence",
    dependencies=[Depends(require_permission("evidence:read"))],
)
def evidence_library(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    result = repo.evidence_library(organization_id, city, limit)
    if result is None:
        raise _not_found("City")
    return result


@router.post(
    "/cities/{city}/reports",
    status_code=201,
    dependencies=[Depends(require_permission("report:create"))],
)
def create_report(
    city: str,
    body: ReportCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_report_record(organization_id, city, body.model_dump(mode="json"))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/reports/{report_id}/artifact",
    dependencies=[Depends(require_permission("evidence:read"))],
)
def report_artifact(
    report_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> JSONResponse:
    try:
        result = repo.report_artifact(organization_id, str(report_id))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if result is None:
        raise _not_found("Report")
    return JSONResponse(
        content=jsonable_encoder(result["structured_content"]),
        headers={
            "ETag": f'"{result["artifact_sha256"]}"',
            "Content-Disposition": f'attachment; filename="citygap-report-{report_id}.json"',
            "X-CITYGAP-Data-Classification": result["data_classification"],
        },
    )


@router.post(
    "/reports/{report_id}/exports",
    status_code=201,
    dependencies=[Depends(require_permission("evidence:export"))],
)
def export_report(
    report_id: UUID,
    body: ReportExportRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.export_report(organization_id, str(report_id), body.export_scope)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("Report")
    return result


@router.get("/search", dependencies=[Depends(require_permission("platform:read"))])
def search(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    q: Annotated[str, Query(min_length=1, max_length=200)],
    city: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    return {"items": repo.service_search(organization_id, q, city, limit)}


@router.get("/activity", dependencies=[Depends(require_permission("activity:read"))])
def activity(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    city: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    return {"items": repo.activity_feed(organization_id, city, limit)}


@router.post("/usage-events", status_code=202)
def usage_event(
    body: UsageEventRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, bool]:
    try:
        repo.record_usage(organization_id, body.city, body.event_name, body.feature_key)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"accepted": True}


@router.get(
    "/operations/overview",
    dependencies=[Depends(require_permission("operations:read"))],
)
def operations_overview(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    return repo.operations_overview(organization_id)


@router.get(
    "/jobs",
    dependencies=[Depends(require_permission("operations:read"))],
)
def jobs(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    state: Annotated[
        Literal["queued", "running", "succeeded", "failed", "cancelled"] | None,
        Query(),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return {"items": repo.service_jobs(organization_id, state, limit)}


@router.get(
    "/jobs/{job_id}",
    dependencies=[Depends(require_permission("operations:read"))],
)
def job_detail(
    job_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.service_job_detail(organization_id, str(job_id))
    if result is None:
        raise _not_found("Job")
    return result


@router.post(
    "/jobs/{job_id}/operations",
    dependencies=[Depends(require_permission("operations:operate"))],
)
def operate_job(
    job_id: UUID,
    body: JobOperationRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.operate_service_job(
            organization_id,
            str(job_id),
            body.action,
            body.expected_state,
            body.reason,
            body.cancel_confirmation,
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Job")
    return result


@router.get("/service-health")
def service_health(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    return repo.service_health(organization_id)


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_permission("metrics:read"))],
)
def metrics(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> PlainTextResponse:
    body = render_request_metrics() + repo.prometheus_metrics(organization_id)
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")
