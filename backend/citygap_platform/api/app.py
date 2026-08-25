"""CITY GAP Platform HTTP API."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response

from .repository import PlatformRepository, PostGISRepository


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


def create_app(repository: PlatformRepository | None = None) -> FastAPI:
    application = FastAPI(
        title="CITY GAP Urban Digital Twin Platform",
        version="0.1.0",
        description="Version-aware PLATEAU/PostGIS API. Large layers require bbox queries.",
    )
    database_url = os.getenv(
        "CITYGAP_DATABASE_URL", "postgresql://citygap:citygap_dev@postgres:5432/citygap"
    )
    application.state.repository = repository or PostGISRepository(database_url)

    @application.get("/health")
    def health(
        response: Response, repo: Annotated[PlatformRepository, Depends(_repository)]
    ) -> dict:
        database = repo.health()
        if not database:
            response.status_code = 503
        return {"status": "ok" if database else "degraded", "database": database}

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
            "features": repo.road_edges(
                city_id, parsed_bbox, limit, offset, graph_version
            ),
        }

    @application.get("/cities/{city_id}/buildings/{gml_id}/network-accessibility")
    def building_network_accessibility(
        city_id: str,
        gml_id: str,
        repo: Annotated[PlatformRepository, Depends(_repository)],
    ) -> dict:
        detail = repo.building_network_accessibility(city_id, gml_id)
        if detail is None:
            raise HTTPException(
                status_code=404, detail="Building network accessibility not found"
            )
        return detail

    return application


app = create_app()
