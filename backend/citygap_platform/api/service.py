"""Stable v1 HTTP surface for CITY GAP municipal operations."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import PurePath
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.citygap_platform.domain.investigation_area import (
    RadiusMethodology,
    validate_radius,
)
from backend.citygap_platform.domain.municipal_service import (
    DataClassification,
    DatasetReleaseStatus,
    DecisionValue,
    FindingStatus,
    FindingType,
    InvestigationStatus,
    ProductRole,
    ReviewStatus,
)
from backend.citygap_platform.domain.scenarios import FieldCheckValue
from backend.citygap_platform.observability import render_request_metrics
from backend.citygap_platform.security.auth import (
    Identity,
    require_organization,
    require_permission,
)
from backend.citygap_platform.storage import AttachmentStore

from .service_repository import MunicipalServiceRepository

router = APIRouter(prefix="/api/v1", tags=["municipal-service"])
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
ALLOWED_ATTACHMENT_CONTENT_TYPES = frozenset(
    {
        "application/geo+json",
        "application/json",
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/csv",
        "text/plain",
    }
)
ORGANIZATION_CONFIG_KEYS = frozenset(
    {
        "annual_update_algorithm_version",
        "default_data_classification",
        "default_map_basemap",
        "field_offline_expiry_hours",
        "locale",
        "timezone",
    }
)
FORBIDDEN_CONFIG_FRAGMENTS = (
    "secret",
    "password",
    "token",
    "credential",
    "private_key",
)


def _repository(request: Request) -> MunicipalServiceRepository:
    return request.app.state.repository


def _identity(request: Request) -> Identity:
    identity: Identity | None = getattr(request.state, "identity", None)
    if identity is None:
        raise HTTPException(status_code=401, detail="Identity unavailable")
    return identity


def _attachment_store(request: Request) -> AttachmentStore:
    return request.app.state.attachment_store


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


class AnnualUpdateCreateRequest(StrictRequest):
    from_urban_state_id: UUID
    to_urban_state_id: UUID
    algorithm_version: str = Field(
        default="citygap-state-diff@1.0.0",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._@+-]{1,99}$",
    )

    @model_validator(mode="after")
    def distinct_states(self) -> AnnualUpdateCreateRequest:
        if self.from_urban_state_id == self.to_urban_state_id:
            raise ValueError("Annual update states must be different")
        return self


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


class AreaOriginRequest(StrictRequest):
    kind: Literal["station", "map_point"]
    coordinates: tuple[float, float] | None = None
    source_dataset_version_id: UUID | None = None
    source_feature_id: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def valid_origin(self) -> AreaOriginRequest:
        if self.kind == "station":
            if self.coordinates is not None:
                raise ValueError("station coordinates are resolved from the official source")
            if self.source_dataset_version_id is None or self.source_feature_id is None:
                raise ValueError("station origin requires a versioned official source feature")
        else:
            if self.coordinates is None:
                raise ValueError("map_point origin requires coordinates")
            longitude, latitude = self.coordinates
            if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise ValueError("map_point coordinates are outside EPSG:4326")
            if self.source_dataset_version_id is not None or self.source_feature_id is not None:
                raise ValueError("map_point cannot claim an official source feature")
        return self


class InvestigationAreaCreateRequest(StrictRequest):
    geometry_kind: Literal["point_radius", "source_boundary"]
    label: str = Field(min_length=1, max_length=500)
    origin: AreaOriginRequest | None = None
    radius_m: int | None = None
    radius_methodology: Literal[
        "mlit_elderly_walk_reference_500m",
        "mlit_general_walk_reference_800m",
        "broad_context_1000m",
        "custom_radius",
    ] | None = None
    source_boundary_kind: Literal["census_2020_small_area"] | None = None
    source_dataset_version_id: UUID | None = None
    source_feature_id: str | None = Field(default=None, min_length=1, max_length=500)
    area_series_id: UUID | None = None
    expected_area_version: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_area_definition(self) -> InvestigationAreaCreateRequest:
        if self.geometry_kind == "point_radius":
            if self.origin is None or self.radius_m is None or self.radius_methodology is None:
                raise ValueError("point_radius requires origin, radius_m and radius_methodology")
            validate_radius(self.radius_m, RadiusMethodology(self.radius_methodology))
            if (
                self.source_boundary_kind is not None
                or self.source_dataset_version_id is not None
                or self.source_feature_id is not None
            ):
                raise ValueError("point_radius cannot also be a source boundary")
        else:
            if self.origin is not None or self.radius_m is not None or self.radius_methodology is not None:
                raise ValueError("source_boundary cannot contain point-radius fields")
            if (
                self.source_boundary_kind is None
                or self.source_dataset_version_id is None
                or self.source_feature_id is None
            ):
                raise ValueError("source_boundary requires a versioned source feature")
        if self.area_series_id is None and self.expected_area_version != 0:
            raise ValueError("a new area series must expect version 0")
        return self


class AreaAnalysisCreateRequest(StrictRequest):
    source_dataset_version_ids: list[UUID] = Field(min_length=1, max_length=100)
    expected_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class InvestigationTransitionRequest(StrictRequest):
    expected_status: InvestigationStatus
    proposed_status: InvestigationStatus
    note: str = Field(default="", max_length=4000)


class SavedViewCreateRequest(StrictRequest):
    title: str = Field(min_length=1, max_length=500)
    spatial_state: dict[str, Any]
    data_classification: DataClassification = DataClassification.INTERNAL

    @field_validator("spatial_state")
    @classmethod
    def bounded_spatial_state(cls, value: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=False).encode()
        if len(encoded) > 65536:
            raise ValueError("spatial_state exceeds 64 KiB")
        return value


class SpatialPackCreateRequest(StrictRequest):
    geometry: dict[str, Any]
    bbox: tuple[float, float, float, float]
    buffer_m: float = Field(default=0, ge=0, le=10_000)
    data_classification: DataClassification = DataClassification.INTERNAL
    source_dataset_version_ids: list[UUID] = Field(min_length=1, max_length=100)
    network_version_id: UUID | None = None
    analysis_run_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("geometry")
    @classmethod
    def bounded_geometry(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("type") not in {"Polygon", "MultiPolygon", "LineString", "MultiLineString"}:
            raise ValueError("pack geometry must be a polygon or line GeoJSON geometry")
        if "coordinates" not in value or len(json.dumps(value, ensure_ascii=False).encode()) > 262_144:
            raise ValueError("pack geometry is missing or exceeds 256 KiB")
        return value

    @field_validator("bbox")
    @classmethod
    def valid_bbox(
        cls, value: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        west, south, east, north = value
        valid = -180 <= west < east <= 180 and -90 <= south < north <= 90
        if not valid:
            raise ValueError("bbox must be west,south,east,north in EPSG:4326")
        return value


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


class MembershipCreateRequest(StrictRequest):
    issuer: str = Field(min_length=1, max_length=2000)
    subject: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=300)
    email: str | None = Field(default=None, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: ProductRole


class MembershipStatusRequest(StrictRequest):
    expected_active: bool
    proposed_active: bool
    note: str = Field(min_length=1, max_length=2000)


def _configuration_contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            any(fragment in str(key).lower() for fragment in FORBIDDEN_CONFIG_FRAGMENTS)
            or _configuration_contains_secret_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_configuration_contains_secret_key(child) for child in value)
    return False


class OrganizationConfigurationRequest(StrictRequest):
    expected_updated_at: datetime | None = None
    config_value: Any
    note: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def non_secret_and_bounded(self) -> OrganizationConfigurationRequest:
        if self.expected_updated_at is not None and (
            self.expected_updated_at.tzinfo is None or self.expected_updated_at.utcoffset() is None
        ):
            raise ValueError("expected_updated_at must include a timezone")
        if _configuration_contains_secret_key(self.config_value):
            raise ValueError("Organization configuration cannot contain secret-bearing keys")
        if len(json.dumps(self.config_value, ensure_ascii=False).encode()) > 16384:
            raise ValueError("Organization configuration value exceeds 16 KiB")
        return self


class RetentionPolicyRequest(StrictRequest):
    expected_retention_days: int | None = Field(default=None, ge=1, le=36500)
    proposed_retention_days: int | None = Field(default=None, ge=1, le=36500)
    legal_hold_supported: bool = False
    note: str = Field(min_length=1, max_length=2000)


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


FIELD_SYNC_KEYS = frozenset(
    {
        "site_access",
        "road_safety",
        "land_ownership_unknown",
        "existing_service",
        "facility_condition",
        "hazard_confirmation",
        "operator_consultation",
        "notes",
        "gps_confirmation",
    }
)
FIELD_CHECK_KEYS = FIELD_SYNC_KEYS - {"notes", "gps_confirmation"}
FIELD_CHECK_VALUES = frozenset(value.value for value in FieldCheckValue)


class FieldOfflinePackageCreateRequest(StrictRequest):
    urban_state_id: UUID
    scenario_run_id: UUID
    site_order: int = Field(ge=1, le=20)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def timezone_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("expires_at must include a timezone")
        return value


class FieldSyncOperationRequest(StrictRequest):
    client_operation_id: UUID
    offline_package_id: UUID
    scenario_run_id: UUID
    site_order: int = Field(ge=1, le=20)
    base_record_version: int = Field(ge=1)
    client_updated_at: datetime
    payload: dict[str, Any]

    @field_validator("client_updated_at")
    @classmethod
    def timezone_client_update(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("client_updated_at must include a timezone")
        return value

    @field_validator("payload")
    @classmethod
    def bounded_field_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value or set(value) - FIELD_SYNC_KEYS:
            raise ValueError("field sync payload contains missing or unsupported fields")
        if any(
            key in FIELD_CHECK_KEYS and item not in FIELD_CHECK_VALUES
            for key, item in value.items()
        ):
            raise ValueError("field sync checklist contains an unsupported status")
        if "notes" in value and (not isinstance(value["notes"], str) or len(value["notes"]) > 4000):
            raise ValueError("field sync notes must be text of at most 4000 characters")
        if "gps_confirmation" in value and not isinstance(value["gps_confirmation"], dict):
            raise ValueError("field sync GPS confirmation must be an object")
        if len(json.dumps(value, ensure_ascii=False).encode()) > 65536:
            raise ValueError("field sync payload exceeds 64 KiB")
        return value


class FieldConflictResolutionRequest(StrictRequest):
    resolution_status: Literal["use_server", "use_client", "merged"]
    resolved_state: dict[str, Any] | None = None

    @model_validator(mode="after")
    def explicit_merge(self) -> FieldConflictResolutionRequest:
        if self.resolution_status == "merged" and not self.resolved_state:
            raise ValueError("Merged resolution requires resolved_state")
        if self.resolved_state and set(self.resolved_state) - FIELD_SYNC_KEYS:
            raise ValueError("resolved_state contains unsupported fields")
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


class SourceDiscoveryRequest(StrictRequest):
    city: str = Field(min_length=1, max_length=100)
    source_keys: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("source_keys")
    @classmethod
    def safe_source_keys(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("source_keys must be unique")
        if any(
            len(key) > 150 or not key.replace("-", "").replace("_", "").isalnum() for key in value
        ):
            raise ValueError("source_keys must be bounded identifiers")
        return value


class DatasetValidationRequest(StrictRequest):
    version_id: UUID
    expected_status: Literal["registered", "rejected", "failed"]
    note: str = Field(min_length=1, max_length=4000)


class DatasetPromotionRequest(StrictRequest):
    version_id: UUID
    expected_status: Literal["analysis_ready"] = "analysis_ready"
    note: str = Field(min_length=1, max_length=4000)


class MetadataCheckRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)


class MetadataScheduleRequest(StrictRequest):
    city: str | None = Field(default=None, min_length=1, max_length=100)
    limit: int = Field(default=25, ge=1, le=100)


class ResourceReprocessRequest(StrictRequest):
    adapter_id: str = Field(min_length=1, max_length=150)
    adapter_version: str = Field(min_length=1, max_length=100)
    transformation_version: str = Field(min_length=1, max_length=100)
    canonical_version: str = Field(min_length=1, max_length=100)
    previous_transformation_run_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=4000)


class ResourceQuarantineRequest(StrictRequest):
    category: Literal[
        "schema_invalid",
        "schema_changed",
        "checksum_mismatch",
        "crs_unknown",
        "license_unknown",
        "archive_unsafe",
        "xml_unsafe",
        "formula_unsafe",
        "geometry_oversized",
        "encoding_invalid",
        "malformed_content",
        "other",
    ]
    reason: str = Field(min_length=1, max_length=4000)
    transformation_run_id: UUID | None = None
    evidence: dict[str, Any] = Field(default_factory=dict, max_length=100)


class DataTaskTransitionRequest(StrictRequest):
    expected_status: Literal["open", "in_progress"]
    proposed_status: Literal["in_progress", "resolved", "dismissed"]
    resolution_note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def closed_task_has_reason(self) -> DataTaskTransitionRequest:
        if self.proposed_status in {"resolved", "dismissed"} and not (
            self.resolution_note and self.resolution_note.strip()
        ):
            raise ValueError("Resolving or dismissing a data task requires a note")
        return self


class SourceFeedbackCreateRequest(StrictRequest):
    city_source_id: UUID
    canonical_record_id: int | None = Field(default=None, ge=1)
    feedback_type: Literal[
        "facility_closed",
        "service_changed",
        "timetable_mismatch",
        "geometry_issue",
        "attribute_issue",
        "other",
    ]
    statement: str = Field(min_length=1, max_length=4000)
    evidence: dict[str, Any] = Field(default_factory=dict, max_length=100)


class FeedbackFieldTaskCreateRequest(StrictRequest):
    expected_feedback_status: Literal["submitted", "triaged"]
    title: str = Field(min_length=1, max_length=500)
    checklist: list[str] = Field(min_length=1, max_length=30)
    assigned_to: str | None = Field(default=None, min_length=1, max_length=200)
    due_date: date | None = None

    @field_validator("checklist")
    @classmethod
    def bounded_checklist(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 500 for item in value):
            raise ValueError("checklist items must be non-empty and at most 500 characters")
        return value


class OpenDataFieldTaskTransitionRequest(StrictRequest):
    expected_status: Literal["open", "assigned", "in_progress"]
    proposed_status: Literal["assigned", "in_progress", "completed", "cancelled"]
    assigned_to: str | None = Field(default=None, min_length=1, max_length=200)
    resolution_note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def completed_task_has_result(self) -> OpenDataFieldTaskTransitionRequest:
        if self.proposed_status == "completed" and not (
            self.resolution_note and self.resolution_note.strip()
        ):
            raise ValueError("Completing a field task requires a resolution note")
        if self.proposed_status == "assigned" and not self.assigned_to:
            raise ValueError("Assigning a field task requires assigned_to")
        return self


class LocalOverrideCreateRequest(StrictRequest):
    canonical_record_id: int = Field(ge=1)
    override_patch: dict[str, Any] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=4000)
    evidence: dict[str, Any] | list[dict[str, Any]]
    effective_date: date
    expires_at: date
    review_status: Literal["draft", "in_review"] = "draft"

    @model_validator(mode="after")
    def valid_review_horizon(self) -> LocalOverrideCreateRequest:
        if self.expires_at < self.effective_date:
            raise ValueError("Override expiry cannot precede its effective date")
        return self


class LocalOverrideReviewRequest(StrictRequest):
    expected_status: Literal["draft", "in_review"]
    proposed_status: Literal["in_review", "reviewed", "rejected"]
    review_note: str = Field(min_length=1, max_length=4000)


class PublicTransparencyCreateRequest(StrictRequest):
    report_id: UUID | None = None
    evidence_center_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    summary: dict[str, Any] = Field(min_length=1, max_length=100)
    source_citations: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    limitations: list[str] = Field(min_length=1, max_length=100)
    publish: bool = False

    @model_validator(mode="after")
    def has_public_subject(self) -> PublicTransparencyCreateRequest:
        if self.report_id is None and self.evidence_center_id is None:
            raise ValueError("A transparency record requires a report or Evidence Center")
        if any(not item.strip() or len(item) > 2000 for item in self.limitations):
            raise ValueError("limitations must be bounded non-empty statements")
        return self


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


class ScenarioCloneRequest(StrictRequest):
    title: str = Field(min_length=1, max_length=500)


class EvidenceCenterCreateRequest(StrictRequest):
    schema_version: Literal["2.0.0"] = "2.0.0"
    investigation_id: UUID | None = None
    scenario_run_id: UUID | None = None
    source_manifest: dict[str, Any]
    algorithm_manifest: dict[str, Any]
    validation_manifest: dict[str, Any]
    open_data_lineage_manifest: dict[str, Any] = Field(default_factory=dict, max_length=100)
    report_manifest: dict[str, Any] = Field(default_factory=dict, max_length=100)
    claim_boundary: str = Field(
        default=(
            "公開データとモデル結果の出典・仮定・限界を記録し、"
            "行政判断や政策効果を自動認定しません。"
        ),
        min_length=1,
        max_length=4000,
    )
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


@router.get(
    "/organizations/current/memberships",
    dependencies=[Depends(require_permission("organization:manage"))],
)
def organization_memberships(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    return {"items": repo.organization_members(organization_id)}


@router.post(
    "/organizations/current/memberships",
    status_code=201,
    dependencies=[Depends(require_permission("organization:manage"))],
)
def create_organization_membership(
    body: MembershipCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    return repo.create_organization_membership(organization_id, body.model_dump(mode="json"))


@router.patch(
    "/organizations/current/memberships/{user_id}/{role}",
    dependencies=[Depends(require_permission("organization:manage"))],
)
def transition_organization_membership(
    user_id: UUID,
    role: ProductRole,
    body: MembershipStatusRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_organization_membership(
            organization_id,
            str(user_id),
            role.value,
            body.expected_active,
            body.proposed_active,
            body.note,
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Organization membership")
    return result


@router.get(
    "/organizations/current/settings",
    dependencies=[Depends(require_permission("operations:read"))],
)
def organization_settings(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    return {
        **repo.organization_settings(organization_id),
        "allowed_config_keys": sorted(ORGANIZATION_CONFIG_KEYS),
        "boundaries": {
            "secrets": "environment or secret manager only",
            "retention_enforcement": "policy record only; no purge worker is enabled",
            "legal_hold": "not implemented",
        },
    }


@router.patch(
    "/organizations/current/configuration/{config_key}",
    dependencies=[Depends(require_permission("organization:manage"))],
)
def update_organization_configuration(
    config_key: str,
    body: OrganizationConfigurationRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    if config_key not in ORGANIZATION_CONFIG_KEYS:
        raise HTTPException(status_code=422, detail="Unsupported organization config key")
    try:
        return repo.update_organization_configuration(
            organization_id,
            config_key,
            body.config_value,
            body.expected_updated_at,
            body.note,
        )
    except ValueError as error:
        raise _conflict(error) from error


@router.patch(
    "/organizations/current/retention-policies/{resource_type}",
    dependencies=[Depends(require_permission("organization:manage"))],
)
def update_retention_policy(
    resource_type: Literal["audit", "field_observation", "attachment", "job"],
    body: RetentionPolicyRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    if body.legal_hold_supported:
        raise HTTPException(status_code=422, detail="Legal hold is not implemented")
    try:
        return repo.update_retention_policy(
            organization_id,
            resource_type,
            body.expected_retention_days,
            body.proposed_retention_days,
            body.legal_hold_supported,
            body.note,
        )
    except ValueError as error:
        raise _conflict(error) from error


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
    "/cities/{city}/annual-updates",
    dependencies=[Depends(require_permission("platform:read"))],
)
def annual_updates(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    items = repo.annual_updates(organization_id, city, limit)
    if items is None:
        raise _not_found("City")
    return {"items": items}


@router.post(
    "/cities/{city}/annual-updates",
    status_code=202,
    dependencies=[Depends(require_permission("dataset:promote"))],
)
def create_annual_update(
    city: str,
    body: AnnualUpdateCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_annual_update(organization_id, city, body.model_dump(mode="json"))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("City")
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


@router.post(
    "/investigations/{investigation_id}/areas",
    status_code=201,
    dependencies=[Depends(require_permission("investigation:write"))],
)
def create_investigation_area(
    investigation_id: UUID,
    body: InvestigationAreaCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_investigation_area(
            organization_id, str(investigation_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Investigation")
    return result


@router.get(
    "/investigations/{investigation_id}/areas",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def investigation_areas(
    investigation_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    items = repo.investigation_areas(organization_id, str(investigation_id))
    if items is None:
        raise _not_found("Investigation")
    return {"items": items}


@router.get(
    "/investigation-areas/{area_id}",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def investigation_area_detail(
    area_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.investigation_area_detail(organization_id, str(area_id))
    if result is None:
        raise _not_found("Investigation Area")
    return result


@router.post(
    "/investigation-areas/{area_id}/analyses",
    status_code=202,
    dependencies=[Depends(require_permission("investigation:write"))],
)
def create_investigation_area_analysis(
    area_id: UUID,
    body: AreaAnalysisCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_investigation_area_analysis(
            organization_id, str(area_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Investigation Area")
    return result


@router.get(
    "/investigation-areas/{area_id}/summary",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def investigation_area_summary(
    area_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.investigation_area_summary(organization_id, str(area_id))
    if result is None:
        raise _not_found("Investigation Area")
    return result


@router.post(
    "/investigations/{investigation_id}/spatial-packs",
    status_code=202,
    dependencies=[Depends(require_permission("investigation:write"))],
)
def create_spatial_pack(
    investigation_id: UUID,
    body: SpatialPackCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_spatial_pack(
            organization_id, str(investigation_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Investigation")
    return result


@router.get(
    "/spatial-packs/{pack_id}",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def spatial_pack_detail(
    pack_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.spatial_pack_detail(organization_id, str(pack_id))
    if result is None:
        raise _not_found("Spatial Evidence Pack")
    return result


@router.get(
    "/spatial-packs/{pack_id}/manifest",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def spatial_pack_manifest(
    pack_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.spatial_pack_manifest(organization_id, str(pack_id))
    if result is None:
        raise _not_found("Spatial Evidence Pack")
    return result


@router.get(
    "/spatial-packs/{pack_id}/objects",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def spatial_pack_objects(
    pack_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    object_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> dict[str, Any]:
    result = repo.spatial_pack_objects(
        organization_id, str(pack_id), object_type, limit, offset
    )
    if result is None:
        raise _not_found("Spatial Evidence Pack")
    return result


@router.get(
    "/spatial-packs/{pack_id}/sections",
    dependencies=[Depends(require_permission("investigation:read"))],
)
def spatial_pack_sections(
    pack_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.spatial_pack_sections(organization_id, str(pack_id))
    if result is None:
        raise _not_found("Spatial Evidence Pack")
    return result


@router.post(
    "/spatial-packs/{pack_id}/refresh",
    status_code=202,
    dependencies=[Depends(require_permission("investigation:write"))],
)
def refresh_spatial_pack(
    pack_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.refresh_spatial_pack(organization_id, str(pack_id))
    if result is None:
        raise _not_found("Spatial Evidence Pack")
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


@router.get(
    "/saved-views/{share_token}",
    dependencies=[Depends(require_permission("investigation:read"))],
    summary="Open a tenant-authenticated saved spatial view by opaque share token",
)
def saved_view(
    share_token: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    if len(share_token) != 48 or any(
        character not in "0123456789abcdef" for character in share_token
    ):
        raise _not_found("Saved view")
    result = repo.saved_view(organization_id, share_token)
    if result is None:
        raise _not_found("Saved view")
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
    "/cities/{city}/field/offline-packages",
    status_code=201,
    dependencies=[Depends(require_permission("field:sync"))],
    summary="Download a versioned package for one selected scenario site",
)
def create_field_offline_package(
    city: str,
    body: FieldOfflinePackageCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    del organization_id  # repository reads the verified tenant from request context
    result = repo.create_field_offline_package(
        city,
        str(body.urban_state_id),
        str(body.scenario_run_id),
        body.site_order,
        body.expires_at.isoformat() if body.expires_at else None,
    )
    if result is None:
        raise _not_found("Selected state/scenario site")
    return result


@router.post(
    "/cities/{city}/field/sync",
    dependencies=[Depends(require_permission("field:sync"))],
    summary="Idempotently apply an offline field operation",
)
def sync_field_operation(
    city: str,
    body: FieldSyncOperationRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> JSONResponse:
    del organization_id
    result = repo.sync_field_operation(city, body.model_dump(mode="json"))
    if result is None:
        raise _not_found("Offline package or field record")
    return JSONResponse(
        status_code=409 if result.get("status") == "conflict" else 200,
        content=jsonable_encoder(result),
    )


@router.get(
    "/field-conflicts/{conflict_id}",
    dependencies=[Depends(require_permission("field:read"))],
    summary="Read an explicit tenant-scoped field sync conflict",
)
def field_sync_conflict(
    conflict_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    del organization_id
    result = repo.field_sync_conflict(str(conflict_id))
    if result is None:
        raise _not_found("Field sync conflict")
    return result


@router.post(
    "/cities/{city}/field-conflicts/{conflict_id}/resolve",
    dependencies=[Depends(require_permission("field:sync"))],
    summary="Resolve a field conflict without silent last-write-wins",
)
def resolve_field_sync_conflict(
    city: str,
    conflict_id: UUID,
    body: FieldConflictResolutionRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    del organization_id
    try:
        result = repo.resolve_field_sync_conflict(
            city, str(conflict_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Field sync conflict")
    return result


@router.post(
    "/cities/{city}/attachments",
    status_code=201,
    dependencies=[Depends(require_permission("field:write"))],
    summary="Upload a tenant-scoped field attachment",
)
async def upload_attachment(
    city: str,
    request: Request,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    store: Annotated[AttachmentStore, Depends(_attachment_store)],
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    data_classification: Annotated[
        DataClassification, Query(description="Classification retained with the object metadata")
    ] = DataClassification.RESTRICTED,
) -> dict[str, Any]:
    if filename in {".", ".."} or any(
        separator in filename for separator in ("/", "\\", "\x00", "\r", "\n")
    ):
        raise HTTPException(status_code=422, detail="filename must be a plain file name")
    if PurePath(filename).name != filename:
        raise HTTPException(status_code=422, detail="filename must not contain a path")
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Unsupported attachment content type",
        )
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(status_code=422, detail="Encoded attachment bodies are not accepted")
    city_record = repo.attachment_city(organization_id, city)
    if city_record is None:
        raise _not_found("City")
    try:
        stored = await store.put(
            request.stream(),
            organization_id=organization_id,
            city_id=str(city_record["id"]),
            max_bytes=MAX_ATTACHMENT_BYTES,
        )
    except ValueError as error:
        status = 413 if "exceeds" in str(error) else 422
        raise HTTPException(status_code=status, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    try:
        result = repo.create_attachment_metadata(
            organization_id,
            city,
            {
                "storage_provider": store.provider,
                "object_key": stored.object_key,
                "original_file_name": filename,
                "content_type": content_type,
                "size_bytes": stored.size_bytes,
                "sha256": stored.sha256,
                "data_classification": data_classification.value,
            },
        )
    except Exception:
        store.delete(stored.object_key)
        raise
    if result is None:
        store.delete(stored.object_key)
        raise _not_found("City")
    return {key: value for key, value in result.items() if key != "object_key"}


@router.get(
    "/attachments/{attachment_id}",
    dependencies=[Depends(require_permission("field:read"))],
    summary="Download an attachment after tenant metadata authorization",
)
def download_attachment(
    attachment_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    store: Annotated[AttachmentStore, Depends(_attachment_store)],
) -> StreamingResponse:
    metadata = repo.attachment_metadata(organization_id, str(attachment_id))
    if metadata is None:
        raise _not_found("Attachment")
    if metadata["storage_provider"] != store.provider:
        raise HTTPException(status_code=503, detail="Attachment storage provider is unavailable")
    try:
        exists = store.exists(metadata["object_key"])
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if not exists:
        raise HTTPException(status_code=503, detail="Attachment bytes are unavailable")
    safe_name = quote(metadata["original_file_name"], safe="")
    return StreamingResponse(
        store.iter_bytes(metadata["object_key"]),
        media_type=metadata["content_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}",
            "Content-Length": str(metadata["size_bytes"]),
            "ETag": f'"{metadata["sha256"]}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


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


@router.get(
    "/cities/{city}/data-coverage",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def city_data_coverage(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.city_data_coverage(organization_id, city)
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/cities/{city}/sources",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def city_open_data_sources(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.city_open_data_sources(organization_id, city)
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/cities/{city}/source-timeline",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def city_source_timeline(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.city_source_timeline(organization_id, city)
    if result is None:
        raise _not_found("City")
    return result


@router.post(
    "/sources/discover",
    status_code=202,
    dependencies=[Depends(require_permission("dataset:register"))],
)
def discover_open_data_sources(
    body: SourceDiscoveryRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.queue_source_discovery(organization_id, body.city, body.source_keys)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("City")
    return result


@router.post(
    "/sources/metadata-checks/schedule",
    status_code=202,
    dependencies=[Depends(require_permission("dataset:validate"))],
)
def schedule_open_data_metadata_checks(
    body: MetadataScheduleRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    return repo.schedule_due_metadata_checks(organization_id, body.city, body.limit)


@router.post(
    "/sources/{source_id}/metadata-checks",
    status_code=202,
    dependencies=[Depends(require_permission("dataset:validate"))],
)
def check_open_data_source_metadata(
    source_id: UUID,
    body: MetadataCheckRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.queue_source_metadata_check(organization_id, str(source_id), body.reason)
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Source")
    return result


@router.get("/datasets", dependencies=[Depends(require_permission("dataset:read"))])
def datasets(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    city: str | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    return {"items": repo.service_datasets(organization_id, city, q, limit)}


@router.get(
    "/datasets/{dataset_id}",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def dataset_detail(
    dataset_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.service_dataset(organization_id, str(dataset_id))
    if result is None:
        raise _not_found("Dataset")
    return result


@router.get(
    "/datasets/{dataset_id}/lineage",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def dataset_lineage(
    dataset_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.service_dataset_lineage(organization_id, str(dataset_id))
    if result is None:
        raise _not_found("Dataset")
    return result


@router.post(
    "/datasets/{dataset_id}/validate",
    status_code=202,
    dependencies=[Depends(require_permission("dataset:validate"))],
)
def validate_dataset(
    dataset_id: UUID,
    body: DatasetValidationRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_dataset_version(
            organization_id,
            str(body.version_id),
            body.expected_status,
            "validating",
            body.note,
            dataset_id=str(dataset_id),
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Dataset version")
    return result


@router.post(
    "/datasets/{dataset_id}/promote",
    status_code=202,
    dependencies=[Depends(require_permission("dataset:promote"))],
)
def promote_dataset(
    dataset_id: UUID,
    body: DatasetPromotionRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_dataset_version(
            organization_id,
            str(body.version_id),
            body.expected_status,
            "promoted",
            body.note,
            dataset_id=str(dataset_id),
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Dataset version")
    return result


@router.post(
    "/resources/{resource_id}/reprocess",
    status_code=202,
    dependencies=[Depends(require_permission("dataset:validate"))],
)
def reprocess_open_data_resource(
    resource_id: UUID,
    body: ResourceReprocessRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.queue_open_data_reprocessing(
            organization_id, str(resource_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Open data resource")
    return result


@router.post(
    "/resources/{resource_id}/quarantine",
    status_code=201,
    dependencies=[Depends(require_permission("dataset:validate"))],
)
def quarantine_open_data_resource(
    resource_id: UUID,
    body: ResourceQuarantineRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.quarantine_open_data_resource(
            organization_id, str(resource_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Open data resource")
    return result


@router.get(
    "/cities/{city}/data-tasks",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def data_manager_tasks(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    status: Annotated[
        Literal["open", "in_progress", "resolved", "dismissed"] | None,
        Query(),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    result = repo.data_manager_tasks(organization_id, city, status, limit)
    if result is None:
        raise _not_found("City")
    return result


@router.patch(
    "/data-tasks/{task_id}",
    dependencies=[Depends(require_permission("dataset:validate"))],
)
def transition_data_manager_task(
    task_id: UUID,
    body: DataTaskTransitionRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_data_manager_task(
            organization_id,
            str(task_id),
            body.expected_status,
            body.proposed_status,
            body.resolution_note,
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Data task")
    return result


@router.post(
    "/cities/{city}/source-feedback",
    status_code=201,
    dependencies=[Depends(require_permission("field:write"))],
)
def create_source_feedback(
    city: str,
    body: SourceFeedbackCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_source_feedback(
            organization_id, city, body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("City or source")
    return result


@router.get(
    "/cities/{city}/source-feedback",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def source_feedback(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    result = repo.source_feedback(organization_id, city, limit)
    if result is None:
        raise _not_found("City")
    return result


@router.post(
    "/source-feedback/{feedback_id}/field-task",
    status_code=201,
    dependencies=[Depends(require_permission("field:write"))],
)
def create_feedback_field_task(
    feedback_id: UUID,
    body: FeedbackFieldTaskCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_feedback_field_task(
            organization_id, str(feedback_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Source feedback")
    return result


@router.get(
    "/cities/{city}/open-data-field-tasks",
    dependencies=[Depends(require_permission("field:read"))],
)
def open_data_field_tasks(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    result = repo.open_data_field_tasks(organization_id, city, limit)
    if result is None:
        raise _not_found("City")
    return result


@router.patch(
    "/open-data-field-tasks/{task_id}",
    dependencies=[Depends(require_permission("field:write"))],
)
def transition_open_data_field_task(
    task_id: UUID,
    body: OpenDataFieldTaskTransitionRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.transition_open_data_field_task(
            organization_id, str(task_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Open-data field task")
    return result


@router.post(
    "/cities/{city}/local-overrides",
    status_code=201,
    dependencies=[Depends(require_permission("dataset:validate"))],
)
def create_local_override(
    city: str,
    body: LocalOverrideCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_local_override(
            organization_id, city, body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("City or canonical record")
    return result


@router.get(
    "/cities/{city}/local-overrides",
    dependencies=[Depends(require_permission("dataset:read"))],
)
def local_overrides(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    result = repo.local_overrides(organization_id, city, limit)
    if result is None:
        raise _not_found("City")
    return result


@router.patch(
    "/local-overrides/{override_id}/review",
    dependencies=[Depends(require_permission("dataset:accept"))],
)
def review_local_override(
    override_id: UUID,
    body: LocalOverrideReviewRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.review_local_override(
            organization_id, str(override_id), body.model_dump(mode="json")
        )
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Local override")
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


@router.post(
    "/scenarios/{scenario_id}/clone",
    status_code=201,
    dependencies=[Depends(require_permission("scenario:draft"))],
)
def clone_scenario(
    scenario_id: UUID,
    body: ScenarioCloneRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    result = repo.clone_scenario(organization_id, str(scenario_id), body.title)
    if result is None:
        raise _not_found("Scenario")
    return result


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


@router.get(
    "/evidence-centers/{evidence_id}",
    dependencies=[Depends(require_permission("evidence:read"))],
)
def evidence_center_detail(
    evidence_id: UUID,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.evidence_center_detail(organization_id, str(evidence_id))
    except ValueError as error:
        raise _conflict(error) from error
    if result is None:
        raise _not_found("Evidence Center")
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


@router.post(
    "/cities/{city}/public-transparency",
    status_code=201,
    dependencies=[Depends(require_permission("evidence:export"))],
)
def create_public_transparency_record(
    city: str,
    body: PublicTransparencyCreateRequest,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    try:
        result = repo.create_public_transparency_record(
            organization_id, city, body.model_dump(mode="json")
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise _not_found("City")
    return result


@router.get(
    "/cities/{city}/public-transparency",
    dependencies=[Depends(require_permission("platform:read"))],
)
def public_transparency_records(
    city: str,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    result = repo.public_transparency_records(organization_id, city, limit)
    if result is None:
        raise _not_found("City")
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


@router.get(
    "/audit-events",
    dependencies=[Depends(require_permission("audit:read"))],
    summary="List immutable tenant audit events with opaque cursor pagination",
)
def audit_events(
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
    city: Annotated[str | None, Query(max_length=100)] = None,
    action: Annotated[str | None, Query(max_length=200)] = None,
    actor: Annotated[str | None, Query(max_length=200)] = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> dict[str, Any]:
    for value in (occurred_from, occurred_to):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise HTTPException(status_code=422, detail="Audit timestamps must include a timezone")
    if occurred_from and occurred_to and occurred_from > occurred_to:
        raise HTTPException(status_code=422, detail="occurred_from must not exceed occurred_to")
    try:
        return repo.service_audit_events(
            organization_id,
            city,
            action,
            actor,
            occurred_from,
            occurred_to,
            limit,
            cursor,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


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
    "/support-bundle",
    dependencies=[Depends(require_permission("organization:manage"))],
    summary="Build a secret-free support snapshot for an administrator",
)
def support_bundle(
    request: Request,
    organization_id: Annotated[str, Depends(require_organization)],
    repo: Annotated[MunicipalServiceRepository, Depends(_repository)],
) -> dict[str, Any]:
    operations = repo.operations_overview(organization_id)
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "request_id": getattr(request.state, "request_id", None),
        "health": repo.service_health(organization_id),
        "jobs": operations["jobs"],
        "datasets": operations["datasets"],
        "releases": operations["releases"],
        "boundaries": operations["boundaries"],
        "excluded": [
            "tokens",
            "credentials",
            "attachment_bytes",
            "restricted_record_bodies",
        ],
    }


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
