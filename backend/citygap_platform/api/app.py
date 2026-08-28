"""CITY GAP Platform HTTP API."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from backend.citygap_platform.domain.jobs import JOB_STAGES
from backend.citygap_platform.domain.scenarios import FieldCheckValue, ScenarioStatus
from backend.citygap_platform.domain.validation import MunicipalFeedback, ValidationStatus
from backend.citygap_platform.observability import request_observability_middleware
from backend.citygap_platform.security.auth import (
    AuthSettings,
    Identity,
    OidcVerifier,
    require_permission,
    resolve_identity,
)

from .repository import PlatformRepository, PostGISRepository
from .service import router as municipal_service_router
from .service_repository import MunicipalServiceRepository
from .tile_cache import CachedVectorTile, VectorTileKey, VersionedTileCache


class ScenarioTransitionRequest(BaseModel):
    expected_status: ScenarioStatus
    proposed_status: ScenarioStatus
    note: str = Field(default="", max_length=2000)


class FieldCheckRequest(BaseModel):
    site_access: FieldCheckValue = FieldCheckValue.UNKNOWN
    road_safety: FieldCheckValue = FieldCheckValue.UNKNOWN
    land_ownership_unknown: FieldCheckValue = FieldCheckValue.UNKNOWN
    existing_service: FieldCheckValue = FieldCheckValue.UNKNOWN
    facility_condition: FieldCheckValue = FieldCheckValue.UNKNOWN
    hazard_confirmation: FieldCheckValue = FieldCheckValue.UNKNOWN
    operator_consultation: FieldCheckValue = FieldCheckValue.UNKNOWN
    notes: str = Field(default="", max_length=4000)
    photo_urls: list[str] = Field(default_factory=list, max_length=10)
    location_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("photo_urls")
    @classmethod
    def validate_photo_urls(cls, values: list[str]) -> list[str]:
        if any(not value.startswith("https://") or len(value) > 2000 for value in values):
            raise ValueError("photo_urls must contain bounded HTTPS references")
        return values


class JobCreateRequest(BaseModel):
    job_type: str
    dataset_version_ids: list[str] = Field(min_length=1, max_length=50)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    algorithm_version: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)


class JobTransitionRequest(BaseModel):
    action: Literal["start", "advance", "succeed", "fail"]
    stage: str | None = None
    error: str | None = Field(default=None, max_length=4000)


class ValidationRunRequest(BaseModel):
    claim_key: str = Field(min_length=1, max_length=200)
    method_key: str = Field(min_length=1, max_length=200)
    urban_state_id: str | None = Field(default=None, min_length=36, max_length=36)
    dataset_versions: dict[str, str] = Field(min_length=1, max_length=100)
    network_version_id: str | None = Field(default=None, min_length=36, max_length=36)
    algorithm_version: str = Field(min_length=1, max_length=200)
    reference_source: dict[str, Any]
    sample_rule: dict[str, Any]
    limitations: list[str] = Field(min_length=1, max_length=100)


class ValidationFieldReviewRequest(BaseModel):
    validation_result_id: str = Field(min_length=36, max_length=36)
    observation_type: str = Field(min_length=1, max_length=200)
    observed_accessibility_issue: str | None = Field(default=None, max_length=4000)
    road_passability: Literal["passable", "not_passable", "uncertain"] | None = None
    facility_availability: Literal["available", "unavailable", "uncertain"] | None = None
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    observed_at: datetime
    evidence_attachment_reference: str | None = Field(default=None, max_length=2000)
    municipal_feedback: MunicipalFeedback = MunicipalFeedback.NOT_REVIEWED
    review_note: str = Field(default="", max_length=4000)

    @field_validator("observed_at")
    @classmethod
    def field_timestamp_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("field observation timestamp must include a timezone")
        return value

    @field_validator("evidence_attachment_reference")
    @classmethod
    def evidence_reference_is_bounded_https_or_object_key(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "evidence://")):
            raise ValueError("evidence attachment must be HTTPS or an evidence:// object reference")
        return value


class ValidationStatusRequest(BaseModel):
    expected_status: ValidationStatus
    proposed_status: ValidationStatus
    note: str = Field(min_length=1, max_length=4000)


class ValidationReferenceRequest(BaseModel):
    reference_key: str = Field(min_length=1, max_length=200)
    source_type: Literal["official_plateau", "municipal_public", "other_public", "osm"]
    source_url: str = Field(min_length=1, max_length=2000)
    retrieval_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license: str = Field(min_length=1, max_length=1000)
    attribution: str = Field(min_length=1, max_length=1000)
    extraction_rule: str = Field(min_length=1, max_length=4000)
    coverage: dict[str, Any]
    status: Literal["available", "not_available", "manual_import_required"]
    limitations: list[str] = Field(min_length=1, max_length=100)


class StressTestAssumptionRequest(BaseModel):
    assumption_type: Literal[
        "edge_closure",
        "road_group_closure",
        "area_closure",
        "hazard_overlap_closure",
        "service_open",
        "service_close",
        "service_relocate",
        "service_temporary_unavailable",
    ]
    hazard_dataset_version_id: str | None = Field(default=None, min_length=36, max_length=36)
    hazard_type: str | None = Field(default=None, max_length=100)
    hazard_class: str | None = Field(default=None, max_length=500)
    closure_assumption: str = Field(min_length=1, max_length=2000)
    assumption_payload: dict[str, Any] = Field(default_factory=dict)
    assumption_source: str = Field(min_length=1, max_length=2000)
    explicitly_confirmed: bool

    @field_validator("explicitly_confirmed")
    @classmethod
    def require_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("stress-test assumptions must be explicitly confirmed")
        return value


class StressTestCreateRequest(BaseModel):
    base_urban_state_id: str = Field(min_length=36, max_length=36)
    network_version_id: str = Field(min_length=36, max_length=36)
    stress_test_key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    stress_test_type: Literal[
        "edge_closure",
        "road_group_closure",
        "area_closure",
        "hazard_counterfactual",
        "service_change",
    ]
    algorithm_version: str = Field(min_length=1, max_length=200)
    route_semantics: str = Field(min_length=1, max_length=1000)
    assumptions: list[StressTestAssumptionRequest] = Field(min_length=1, max_length=100)

    @field_validator("assumptions")
    @classmethod
    def validate_hazard_contract(
        cls, values: list[StressTestAssumptionRequest]
    ) -> list[StressTestAssumptionRequest]:
        for value in values:
            if value.assumption_type == "hazard_overlap_closure" and not all(
                (value.hazard_dataset_version_id, value.hazard_type, value.hazard_class)
            ):
                raise ValueError("hazard overlap requires dataset version, type and class")
        return values


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


class OfflinePackageCreateRequest(BaseModel):
    urban_state_id: str = Field(min_length=36, max_length=36)
    scenario_run_id: str = Field(min_length=36, max_length=36)
    site_order: int = Field(ge=1, le=20)
    expires_at: datetime | None = None


class FieldSyncRequest(BaseModel):
    client_operation_id: str = Field(min_length=36, max_length=36)
    offline_package_id: str = Field(min_length=36, max_length=36)
    scenario_run_id: str = Field(min_length=36, max_length=36)
    site_order: int = Field(ge=1, le=20)
    base_record_version: int = Field(ge=1)
    client_updated_at: datetime
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value or set(value) - FIELD_SYNC_KEYS:
            raise ValueError("field sync payload contains missing or unsupported fields")
        invalid_checks = {
            key: item
            for key, item in value.items()
            if key in FIELD_CHECK_KEYS and item not in FIELD_CHECK_VALUES
        }
        if invalid_checks:
            raise ValueError("field sync checklist contains an unsupported status")
        if "notes" in value and not isinstance(value["notes"], str):
            raise ValueError("field sync notes must be text")
        if "gps_confirmation" in value and not isinstance(value["gps_confirmation"], dict):
            raise ValueError("field sync GPS confirmation must be an object")
        if len(json.dumps(value, ensure_ascii=False).encode()) > 65536:
            raise ValueError("field sync payload exceeds 64 KiB")
        return value

    @field_validator("client_updated_at")
    @classmethod
    def validate_client_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("field sync timestamp must include a timezone")
        return value


class ConflictResolutionRequest(BaseModel):
    resolution_status: Literal["use_server", "use_client", "merged"]
    resolved_state: dict[str, Any] | None = None

    @field_validator("resolved_state")
    @classmethod
    def validate_resolved_state(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and (not value or set(value) - FIELD_SYNC_KEYS):
            raise ValueError("resolved state contains unsupported fields")
        return value


def _repository(request: Request) -> PlatformRepository:
    return request.app.state.repository


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        parts = tuple(float(part) for part in value.split(","))
    except ValueError as error:
        raise HTTPException(status_code=422, detail="bbox must contain four numbers") from error
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise HTTPException(status_code=422, detail="bbox must be minLon,minLat,maxLon,maxLat")
    return parts


def create_app(
    repository: PlatformRepository | None = None,
    auth_settings: AuthSettings | None = None,
    oidc_verifier: OidcVerifier | None = None,
) -> FastAPI:
    application = FastAPI(
        title="CITY GAP Municipal Urban Intelligence Platform",
        version="0.2.0",
        description=(
            "Tenant-aware municipal workflow and version-aware PLATEAU/PostGIS API. "
            "Large layers require bounded queries."
        ),
    )
    database_url = os.getenv(
        "CITYGAP_DATABASE_URL", "postgresql://citygap:citygap_dev@postgres:5432/citygap"
    )
    application.state.repository = repository or MunicipalServiceRepository(database_url)
    application.state.auth_settings = auth_settings or AuthSettings.from_environment()
    application.state.tile_cache = VersionedTileCache(
        int(os.getenv("CITYGAP_TILE_CACHE_ITEMS", "512"))
    )
    application.include_router(municipal_service_router)

    def service_error_content(
        request: Request,
        status_code: int,
        detail: Any,
        validation: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        code = {
            400: "invalid_request",
            401: "authentication_required",
            403: "permission_denied",
            404: "resource_not_found",
            409: "state_conflict",
            413: "request_too_large",
            422: "validation_error",
            429: "rate_limited",
            503: "service_unavailable",
        }.get(status_code, "service_error")
        message = detail if isinstance(detail, str) else "Request could not be processed"
        remediation = {
            401: "Supply a verified identity.",
            403: "Confirm organization membership and the required role.",
            404: "Confirm the resource belongs to the selected organization and city.",
            409: "Reload the resource and retry from its current lifecycle state.",
            422: "Correct the indicated fields and submit again.",
            503: "Check service-health and retry after the dependency recovers.",
        }.get(status_code, "Use the request ID when contacting support.")
        payload: dict[str, Any] = {
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", None)
                or request.headers.get("X-Request-ID"),
                "remediation": remediation,
            }
        }
        if validation:
            payload["error"]["fields"] = validation
        return payload

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, error: HTTPException):
        if request.url.path.startswith("/api/v1"):
            return JSONResponse(
                status_code=error.status_code,
                content=jsonable_encoder(
                    service_error_content(request, error.status_code, error.detail)
                ),
                headers=error.headers,
            )
        return JSONResponse(
            status_code=error.status_code,
            content=jsonable_encoder({"detail": error.detail}),
            headers=error.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, error: RequestValidationError):
        if request.url.path.startswith("/api/v1"):
            return JSONResponse(
                status_code=422,
                content=jsonable_encoder(
                    service_error_content(
                        request,
                        422,
                        "Request validation failed",
                        validation=error.errors(),
                    )
                ),
            )
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": error.errors()}),
        )

    @application.middleware("http")
    async def authentication_and_observability(request: Request, call_next):
        if request.url.path in {"/health", "/ready"}:
            request.state.identity = Identity(
                actor="health-probe",
                issuer="citygap-internal",
                roles=frozenset({"viewer"}),
            )
        else:
            try:
                request.state.identity = resolve_identity(
                    request, application.state.auth_settings, oidc_verifier
                )
            except HTTPException as error:
                content = (
                    service_error_content(request, error.status_code, error.detail)
                    if request.url.path.startswith("/api/v1")
                    else {"detail": error.detail}
                )
                failure = JSONResponse(
                    status_code=error.status_code, content=jsonable_encoder(content)
                )

                async def unauthorized(_request: Request):
                    return failure

                return await request_observability_middleware(request, unauthorized)
            identity = request.state.identity
            if (
                request.url.path.startswith("/api/v1")
                and application.state.auth_settings.mode == "oidc"
            ):
                authorize = getattr(application.state.repository, "authorize_identity", None)
                authorized = bool(
                    identity.organization_id
                    and authorize
                    and authorize(
                        identity.organization_id,
                        identity.actor,
                        identity.issuer,
                        identity.roles,
                    )
                )
                if not authorized:
                    failure = JSONResponse(
                        status_code=403,
                        content=jsonable_encoder(
                            service_error_content(
                                request,
                                403,
                                "Active organization membership is required",
                            )
                        ),
                    )

                    async def membership_denied(_request: Request):
                        return failure

                    return await request_observability_middleware(request, membership_denied)
        return await request_observability_middleware(request, call_next)

    @application.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @application.get("/ready")
    def ready(
        response: Response, repo: Annotated[PlatformRepository, Depends(_repository)]
    ) -> dict:
        detail = repo.readiness(os.getenv("CITYGAP_REQUIRED_CITY_ID") or None)
        if not detail["ready"]:
            response.status_code = 503
        return detail

    @application.get("/cities")
    def cities(repo: Annotated[PlatformRepository, Depends(_repository)]) -> list[dict]:
        return repo.cities()

    @application.get("/cities/{city_id}/layers")
    def layers(
        city_id: str, repo: Annotated[PlatformRepository, Depends(_repository)]
    ) -> list[dict]:
        return repo.layers(city_id)

    @application.get("/cities/{city_id}/states")
    def urban_states(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        lifecycle_status: Literal["draft", "validated", "current", "superseded", "archived"]
        | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> dict:
        return {
            "city_id": city_id,
            "states": repo.urban_states(city_id, lifecycle_status, limit),
        }

    @application.get("/cities/{city_id}/states/{state_id}")
    def urban_state_detail(
        city_id: str,
        state_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.urban_state_detail(city_id, state_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Urban state not found")
        return result

    @application.get("/cities/{city_id}/state-comparison")
    def state_comparison(
        city_id: str,
        state_ids: Annotated[str, Query(description="Two or three comma-separated state UUIDs")],
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        identifiers = [value.strip() for value in state_ids.split(",") if value.strip()]
        if not 2 <= len(identifiers) <= 3 or len(identifiers) != len(set(identifiers)):
            raise HTTPException(status_code=422, detail="state_ids requires two or three values")
        states = []
        for identifier in identifiers:
            state = repo.urban_state_detail(city_id, identifier)
            if state is None:
                raise HTTPException(status_code=404, detail=f"Urban state not found: {identifier}")
            states.append(state)
        return {"city_id": city_id, "comparison_limit": 3, "states": states}

    @application.get("/cities/{city_id}/changes")
    def state_changes(
        city_id: str,
        from_state_id: Annotated[str, Query(min_length=36, max_length=36)],
        to_state_id: Annotated[str, Query(min_length=36, max_length=36)],
        bbox: Annotated[str, Query(description="Required bounded map window")],
        repo: Annotated[PlatformRepository, Depends(_repository)],
        limit: Annotated[int, Query(ge=1, le=1000)] = 250,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        parsed_bbox = _parse_bbox(bbox)
        return repo.state_changes(city_id, from_state_id, to_state_id, parsed_bbox, limit, offset)

    @application.get("/cities/{city_id}/buildings")
    def buildings(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        bbox: Annotated[
            str,
            Query(description="Required minLon,minLat,maxLon,maxLat window"),
        ],
        limit: Annotated[int, Query(ge=1, le=1000)] = 250,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        parsed_bbox = _parse_bbox(bbox)
        return {
            "city_id": city_id,
            "bbox": parsed_bbox,
            "limit": limit,
            "offset": offset,
            "features": repo.buildings(city_id, parsed_bbox, limit, offset),
        }

    @application.get("/cities/{city_id}/meshes/{mesh_code}/detail")
    def mesh_detail(
        city_id: str,
        mesh_code: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        detail = repo.mesh_detail(city_id, mesh_code)
        if detail is None:
            raise HTTPException(status_code=404, detail="PLATEAU mesh detail not found")
        return detail

    @application.get("/cities/{city_id}/buildings/{gml_id}")
    def building_detail(
        city_id: str,
        gml_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        detail = repo.building_detail(city_id, gml_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Building not found")
        return detail

    @application.get("/cities/{city_id}/buildings/{gml_id}/accessibility")
    def building_accessibility(
        city_id: str,
        gml_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        detail = repo.building_accessibility(city_id, gml_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Building accessibility not found")
        return detail

    @application.get("/cities/{city_id}/networks")
    def networks(
        city_id: str, repo: Annotated[PlatformRepository, Depends(_repository)]
    ) -> list[dict]:
        return repo.networks(city_id)

    @application.get("/cities/{city_id}/road-edges")
    def road_edges(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        bbox: Annotated[
            str,
            Query(description="Required minLon,minLat,maxLon,maxLat window"),
        ],
        limit: Annotated[int, Query(ge=1, le=1000)] = 250,
        offset: Annotated[int, Query(ge=0)] = 0,
        graph_version: str | None = None,
    ) -> dict:
        parsed_bbox = _parse_bbox(bbox)
        return {
            "city_id": city_id,
            "bbox": parsed_bbox,
            "limit": limit,
            "offset": offset,
            "features": repo.road_edges(city_id, parsed_bbox, limit, offset, graph_version),
        }

    @application.get("/cities/{city_id}/tiles/{layer}/{z}/{x}/{y}.mvt")
    def vector_tile(
        city_id: str,
        layer: Literal["buildings", "road_edges", "hazards", "scenario_impacts"],
        z: int,
        x: int,
        y: int,
        request: Request,
        dataset_version_id: Annotated[str, Query(min_length=36, max_length=36)],
        repo: Annotated[PlatformRepository, Depends(_repository)],
        _identity: Annotated[Identity, Depends(require_permission("platform:read"))],
        network_version_id: Annotated[str | None, Query(min_length=36, max_length=36)] = None,
        scenario_id: Annotated[str | None, Query(min_length=36, max_length=36)] = None,
        algorithm_version: Annotated[str | None, Query(max_length=200)] = None,
    ) -> Response:
        tile_count = 1 << z if 0 <= z <= 22 else 0
        if tile_count == 0 or not (0 <= x < tile_count and 0 <= y < tile_count):
            raise HTTPException(status_code=422, detail="invalid Web Mercator tile coordinate")
        if layer == "road_edges" and network_version_id is None:
            raise HTTPException(status_code=422, detail="road_edges requires network_version_id")
        if layer == "scenario_impacts" and (
            network_version_id is None or scenario_id is None or algorithm_version is None
        ):
            raise HTTPException(
                status_code=422,
                detail="scenario_impacts requires network, scenario, and algorithm versions",
            )
        key = VectorTileKey(
            city_id=city_id,
            dataset_version_id=dataset_version_id,
            network_version_id=network_version_id,
            scenario_id=scenario_id,
            algorithm_version=algorithm_version,
            layer=layer,
            z=z,
            x=x,
            y=y,
        )
        cache: VersionedTileCache = request.app.state.tile_cache
        cached = cache.get(key)
        if cached is None:
            try:
                content = repo.vector_tile(
                    city_id,
                    layer,
                    z,
                    x,
                    y,
                    dataset_version_id,
                    network_version_id,
                    scenario_id,
                    algorithm_version,
                )
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            digest = hashlib.sha256(repr(key).encode() + content).hexdigest()
            cached = CachedVectorTile(content=content, etag=f'"{digest}"')
            cache.put(key, cached)
        headers = {
            "ETag": cached.etag,
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-CITYGAP-Dataset-Version": dataset_version_id,
        }
        if request.headers.get("If-None-Match") == cached.etag:
            return Response(status_code=304, headers=headers)
        return Response(
            content=cached.content,
            media_type="application/vnd.mapbox-vector-tile",
            headers=headers,
        )

    @application.get("/cities/{city_id}/buildings/{gml_id}/network-accessibility")
    def building_network_accessibility(
        city_id: str,
        gml_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        detail = repo.building_network_accessibility(city_id, gml_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Building network accessibility not found")
        return detail

    @application.get("/cities/{city_id}/context/{layer}")
    def context_features(
        city_id: str,
        layer: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        bbox: Annotated[
            str,
            Query(description="Required minLon,minLat,maxLon,maxLat window"),
        ],
        limit: Annotated[int, Query(ge=1, le=1000)] = 250,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        if layer not in {"landuse", "planning", "hazards"}:
            raise HTTPException(status_code=404, detail="Context layer not found")
        parsed_bbox = _parse_bbox(bbox)
        return {
            "city_id": city_id,
            "layer": layer,
            "bbox": parsed_bbox,
            "limit": limit,
            "offset": offset,
            "features": repo.context_features(city_id, layer, parsed_bbox, limit, offset),
        }

    @application.get("/cities/{city_id}/meshes/{mesh_code}/context")
    def mesh_context(
        city_id: str,
        mesh_code: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        return {
            "city_id": city_id,
            "mesh_code": mesh_code,
            "contexts": repo.mesh_context(city_id, mesh_code),
        }

    @application.get("/cities/{city_id}/scenario-candidates/{candidate_id}/context")
    def scenario_candidate_context(
        city_id: str,
        candidate_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        return {
            "city_id": city_id,
            "candidate_id": candidate_id,
            "siting_decision": "not_determined",
            "contexts": repo.scenario_candidate_context(city_id, candidate_id),
        }

    @application.get("/cities/{city_id}/road-edges/{edge_id}/hazards")
    def road_edge_hazards(
        city_id: str,
        edge_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        graph_version: str | None = None,
    ) -> dict:
        return {
            "city_id": city_id,
            "edge_id": edge_id,
            "graph_version": graph_version,
            "interpretation": "overlap requires additional confirmation; feasibility is not determined",
            "hazards": repo.road_edge_hazards(city_id, edge_id, graph_version),
        }

    @application.get("/cities/{city_id}/scenarios")
    def scenarios(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        status: ScenarioStatus | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> dict:
        return {
            "city_id": city_id,
            "status": status.value if status else None,
            "scenarios": repo.scenarios(city_id, status.value if status else None, limit),
        }

    @application.post(
        "/cities/{city_id}/stress-tests",
        status_code=202,
        dependencies=[Depends(require_permission("stress_test:create"))],
    )
    def create_stress_test(
        city_id: str,
        request_body: StressTestCreateRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        try:
            result = repo.create_stress_test(city_id, request_body.model_dump(mode="json"))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="City/state/network combination not found")
        return result

    @application.get("/stress-tests/{stress_test_id}")
    def stress_test_detail(
        stress_test_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.stress_test_detail(stress_test_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Stress test not found")
        return result

    @application.get("/stress-tests/{stress_test_id}/impacts")
    def stress_test_impacts(
        stress_test_id: str,
        bbox: Annotated[str, Query(description="Required bounded map window")],
        repo: Annotated[PlatformRepository, Depends(_repository)],
        service_category: Literal[
            "medical", "emergency", "evacuation", "administrative", "transport_hub"
        ]
        | None = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 250,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        return repo.stress_test_impacts(
            stress_test_id, _parse_bbox(bbox), service_category, limit, offset
        )

    @application.get("/cities/{city_id}/network/criticality")
    def network_criticality(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        urban_state_id: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> dict:
        return {
            "city_id": city_id,
            "candidate_label": "network criticality candidate",
            "candidates": repo.network_criticality(city_id, urban_state_id, limit),
        }

    @application.get("/cities/{city_id}/future-states")
    def future_states(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        return {
            "city_id": city_id,
            "prediction_claimed": False,
            "states": repo.future_states(city_id),
        }

    @application.get("/cities/{city_id}/outcomes")
    def outcomes(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> dict:
        return {
            "city_id": city_id,
            "causal_effect_claimed": False,
            "evaluations": repo.outcomes(city_id, limit),
        }

    @application.get("/cities/{city_id}/scenario-comparison")
    def scenario_comparison(
        city_id: str,
        scenario_ids: Annotated[
            str, Query(description="Two or three comma-separated scenario UUIDs")
        ],
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        identifiers = [value.strip() for value in scenario_ids.split(",") if value.strip()]
        if not 2 <= len(identifiers) <= 3 or len(set(identifiers)) != len(identifiers):
            raise HTTPException(
                status_code=422, detail="scenario_ids must contain two or three distinct values"
            )
        plans = []
        for identifier in identifiers:
            detail = repo.scenario_detail(city_id, identifier)
            if detail is None:
                raise HTTPException(status_code=404, detail=f"Scenario not found: {identifier}")
            plans.append(
                {
                    "scenario_id": detail["scenario_id"],
                    "scenario_key": detail["scenario_key"],
                    "objective_mode": detail["objective_mode"],
                    "site_count": detail["site_count"],
                    "sites": detail["sites"],
                    "impacts": detail["impacts"],
                    "contexts": detail["contexts"],
                    "algorithm_kind": detail["algorithm_kind"],
                    "algorithm_version": detail["algorithm_version"],
                    "lifecycle_status": detail["lifecycle_status"],
                }
            )
        return {
            "city_id": city_id,
            "comparison_limit": 3,
            "recommendation": None,
            "interpretation": "trade-off comparison; municipal review required",
            "plans": plans,
        }

    @application.get("/cities/{city_id}/scenarios/{scenario_id}")
    def scenario_detail(
        city_id: str,
        scenario_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        detail = repo.scenario_detail(city_id, scenario_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return detail

    @application.patch(
        "/cities/{city_id}/scenarios/{scenario_id}/status",
        dependencies=[Depends(require_permission("scenario:review"))],
    )
    def transition_scenario(
        city_id: str,
        scenario_id: str,
        transition: ScenarioTransitionRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        try:
            result = repo.transition_scenario(
                city_id,
                scenario_id,
                transition.expected_status.value,
                transition.proposed_status.value,
                transition.note.strip(),
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return result

    @application.get("/cities/{city_id}/scenarios/{scenario_id}/sites/{site_order}/field-check")
    def field_check(
        city_id: str,
        scenario_id: str,
        site_order: int,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.field_check(city_id, scenario_id, site_order)
        if result is None:
            raise HTTPException(status_code=404, detail="Field check not found")
        return result

    @application.put(
        "/cities/{city_id}/scenarios/{scenario_id}/sites/{site_order}/field-check",
        dependencies=[Depends(require_permission("field:write"))],
    )
    def save_field_check(
        city_id: str,
        scenario_id: str,
        site_order: int,
        checklist: FieldCheckRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.save_field_check(
            city_id,
            scenario_id,
            site_order,
            checklist.model_dump(mode="json"),
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Scenario site not found")
        return result

    @application.post(
        "/cities/{city_id}/field/offline-packages",
        status_code=201,
        dependencies=[Depends(require_permission("field:sync"))],
    )
    def create_field_offline_package(
        city_id: str,
        request_body: OfflinePackageCreateRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.create_field_offline_package(
            city_id,
            request_body.urban_state_id,
            request_body.scenario_run_id,
            request_body.site_order,
            request_body.expires_at.isoformat() if request_body.expires_at else None,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Selected state/scenario site not found")
        return result

    @application.post(
        "/cities/{city_id}/field/sync",
        dependencies=[Depends(require_permission("field:sync"))],
    )
    def sync_field_operation(
        city_id: str,
        request_body: FieldSyncRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> Response:
        result = repo.sync_field_operation(city_id, request_body.model_dump(mode="json"))
        if result is None:
            raise HTTPException(status_code=404, detail="Offline package or field record not found")
        status_code = 409 if result.get("status") == "conflict" else 200
        return JSONResponse(status_code=status_code, content=jsonable_encoder(result))

    @application.get("/field-conflicts/{conflict_id}")
    def field_sync_conflict(
        conflict_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.field_sync_conflict(conflict_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Field sync conflict not found")
        return result

    @application.post(
        "/cities/{city_id}/field-conflicts/{conflict_id}/resolve",
        dependencies=[Depends(require_permission("field:sync"))],
    )
    def resolve_field_sync_conflict(
        city_id: str,
        conflict_id: str,
        request_body: ConflictResolutionRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        if request_body.resolution_status == "merged" and request_body.resolved_state is None:
            raise HTTPException(status_code=422, detail="Merged resolution requires state")
        try:
            result = repo.resolve_field_sync_conflict(
                city_id, conflict_id, request_body.model_dump(mode="json")
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Field sync conflict not found")
        return result

    @application.get("/registry/cities")
    def city_registry(
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        return {
            "capability_statuses": ["available", "partial", "unavailable"],
            "cities": repo.city_registry(),
        }

    @application.get("/registry/cities/{city_id}/datasets")
    def dataset_registry(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        return {
            "city_id": city_id,
            "version_selection": "explicit dataset_version_id; never implicit latest",
            "dataset_versions": repo.dataset_registry(city_id),
        }

    @application.get("/registry/cities/{city_id}/analysis-runs")
    def analysis_runs(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> dict:
        return {
            "city_id": city_id,
            "analysis_runs": repo.analysis_runs(city_id, limit),
        }

    @application.post(
        "/registry/cities/{city_id}/jobs",
        status_code=201,
        dependencies=[Depends(require_permission("analysis:run"))],
    )
    def create_job(
        city_id: str,
        request_body: JobCreateRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        if request_body.job_type not in JOB_STAGES:
            raise HTTPException(status_code=422, detail="Unknown job type")
        try:
            result = repo.create_job(
                city_id,
                request_body.job_type,
                request_body.dataset_version_ids,
                request_body.config_hash,
                request_body.algorithm_version,
                request_body.parameters,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Registry city not found")
        return result

    @application.get("/jobs/{job_id}")
    def job_detail(
        job_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.job_detail(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return result

    @application.post(
        "/jobs/{job_id}/transition",
        dependencies=[Depends(require_permission("platform:operate"))],
    )
    def transition_job(
        job_id: str,
        request_body: JobTransitionRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        try:
            result = repo.transition_job(
                job_id,
                request_body.action,
                request_body.stage,
                request_body.error,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return result

    @application.get("/validation/claims")
    def validation_claims(
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        return {
            "status_semantics": (
                "Recorded evidence-governance status; test success never promotes a claim automatically."
            ),
            "allowed_statuses": [status.value for status in ValidationStatus],
            "claims": repo.validation_claims(),
        }

    @application.get("/cities/{city_id}/validation")
    def city_validations(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        return {
            "city_id": city_id,
            "limit": limit,
            "offset": offset,
            "validation_runs": repo.city_validations(city_id, limit, offset),
        }

    @application.post(
        "/cities/{city_id}/validation",
        status_code=201,
        dependencies=[Depends(require_permission("validation:run"))],
    )
    def create_validation_run(
        city_id: str,
        request_body: ValidationRunRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        try:
            result = repo.create_validation_run(city_id, request_body.model_dump(mode="json"))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="City, claim, method, or version not found")
        return result

    @application.get("/validation/{validation_id}")
    def validation_detail(
        validation_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.validation_detail(validation_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Validation run not found")
        return result

    @application.get("/validation/{validation_id}/samples")
    def validation_samples(
        validation_id: str,
        bbox: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        limit: Annotated[int, Query(ge=1, le=5000)] = 500,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        return repo.validation_samples(validation_id, _parse_bbox(bbox), limit, offset)

    @application.get("/validation/{validation_id}/disagreements")
    def validation_disagreements(
        validation_id: str,
        bbox: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        limit: Annotated[int, Query(ge=1, le=5000)] = 500,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        return repo.validation_disagreements(validation_id, _parse_bbox(bbox), limit, offset)

    @application.get("/validation/{validation_id}/sensitivity")
    def validation_sensitivity(
        validation_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        return repo.validation_sensitivity(validation_id, limit, offset)

    @application.post(
        "/validation/{validation_id}/field-review",
        status_code=201,
        dependencies=[Depends(require_permission("validation:review"))],
    )
    def validation_field_review(
        validation_id: str,
        request_body: ValidationFieldReviewRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        try:
            result = repo.create_validation_field_review(
                validation_id, request_body.model_dump(mode="json")
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Validation result not found")
        return result

    @application.patch(
        "/validation/{validation_id}/status",
        dependencies=[Depends(require_permission("validation:review"))],
    )
    def update_validation_status(
        validation_id: str,
        request_body: ValidationStatusRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        try:
            result = repo.update_validation_status(
                validation_id,
                request_body.expected_status.value,
                request_body.proposed_status.value,
                request_body.note,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Validation run not found")
        return result

    @application.post(
        "/cities/{city_id}/validation/references",
        status_code=201,
        dependencies=[Depends(require_permission("validation:reference:register"))],
    )
    def register_validation_reference(
        city_id: str,
        request_body: ValidationReferenceRequest,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        result = repo.register_validation_reference(city_id, request_body.model_dump(mode="json"))
        if result is None:
            raise HTTPException(status_code=404, detail="City not found")
        return result

    @application.get(
        "/admin/audit",
        dependencies=[Depends(require_permission("platform:operate"))],
    )
    def audit_events(
        repo: Annotated[PlatformRepository, Depends(_repository)],
        city_id: str | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> dict:
        return {"events": repo.audit_events(city_id, limit)}

    @application.get(
        "/admin/snapshot",
        dependencies=[Depends(require_permission("platform:operate"))],
    )
    def admin_snapshot(
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        return repo.admin_snapshot()

    @application.get(
        "/admin/pilot-readiness/{city_id}",
        dependencies=[Depends(require_permission("platform:operate"))],
    )
    def pilot_readiness(
        city_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        if not isinstance(repo, PostGISRepository):
            raise HTTPException(status_code=501, detail="Pilot readiness requires PostGIS")
        from backend.citygap_platform.readiness import PilotReadinessService

        return PilotReadinessService(repo).check(city_id)

    return application


app = create_app()
