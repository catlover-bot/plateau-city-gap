"""CITY GAP Platform HTTP API."""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from backend.citygap_platform.domain.jobs import JOB_STAGES
from backend.citygap_platform.domain.scenarios import FieldCheckValue, ScenarioStatus
from backend.citygap_platform.observability import request_observability_middleware
from backend.citygap_platform.security.auth import (
    AuthSettings,
    Identity,
    OidcVerifier,
    require_permission,
    resolve_identity,
)

from .repository import PlatformRepository, PostGISRepository


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
        title="CITY GAP Urban Digital Twin Platform",
        version="0.1.0",
        description="Version-aware PLATEAU/PostGIS API. Large layers require bbox queries.",
    )
    database_url = os.getenv(
        "CITYGAP_DATABASE_URL", "postgresql://citygap:citygap_dev@postgres:5432/citygap"
    )
    application.state.repository = repository or PostGISRepository(database_url)
    application.state.auth_settings = auth_settings or AuthSettings.from_environment()

    @application.middleware("http")
    async def authentication_and_observability(request: Request, call_next):
        if request.url.path in {"/health", "/ready"}:
            request.state.identity = Identity(
                actor="health-probe", issuer="citygap-internal", roles=frozenset({"viewer"})
            )
        else:
            try:
                request.state.identity = resolve_identity(
                    request, application.state.auth_settings, oidc_verifier
                )
            except HTTPException as error:
                failure = JSONResponse(
                    status_code=error.status_code, content={"detail": error.detail}
                )

                async def unauthorized(_request: Request):
                    return failure

                return await request_observability_middleware(request, unauthorized)
        return await request_observability_middleware(request, call_next)

    @application.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @application.get("/ready")
    def ready(
        response: Response, repo: Annotated[PlatformRepository, Depends(_repository)]
    ) -> dict:
        detail = repo.readiness(os.getenv("CITYGAP_REQUIRED_CITY_ID"))
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

    return application


app = create_app()
