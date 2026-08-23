from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app


class FakeRepository:
    def health(self) -> bool:
        return True

    def cities(self) -> list[dict[str, Any]]:
        return [{"city_id": "26202", "city_name": "舞鶴市"}]

    def layers(self, city_id: str) -> list[dict[str, Any]]:
        return [{"theme": "bldg", "feature_count": 44647, "city_id": city_id}]

    def buildings(
        self, city_id: str, bbox: tuple[float, float, float, float], limit: int, offset: int
    ) -> list[dict[str, Any]]:
        return [{"gml_id": "b-1", "city_id": city_id, "bbox": bbox, "limit": limit}]

    def mesh_detail(self, city_id: str, mesh_code: str) -> dict[str, Any] | None:
        if mesh_code == "missing":
            return None
        return {"city_id": city_id, "mesh_code": mesh_code, "estimated_population": 471}

    def building_detail(self, city_id: str, gml_id: str) -> dict[str, Any] | None:
        if gml_id == "missing":
            return None
        return {"city_id": city_id, "gml_id": gml_id, "estimated_demographics": []}

    def building_accessibility(self, city_id: str, gml_id: str) -> dict[str, Any] | None:
        if gml_id == "missing":
            return None
        return {
            "city_id": city_id,
            "gml_id": gml_id,
            "policies": [
                {"origin_method": "building_origin_representative_point"},
                {"origin_method": "building_origin_representative_point"},
            ],
        }


client = TestClient(create_app(FakeRepository()))


def test_health_and_city_endpoints() -> None:
    assert client.get("/health").json() == {"status": "ok", "database": True}
    assert client.get("/cities").json()[0]["city_id"] == "26202"
    assert client.get("/cities/26202/layers").json()[0]["theme"] == "bldg"


def test_health_is_not_ready_when_database_is_unavailable() -> None:
    repository = FakeRepository()
    repository.health = lambda: False  # type: ignore[method-assign]
    response = TestClient(create_app(repository)).get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_buildings_requires_valid_bbox_and_is_bounded() -> None:
    assert client.get("/cities/26202/buildings").status_code == 422
    assert client.get("/cities/26202/buildings?bbox=135,35,134,36").status_code == 422
    response = client.get("/cities/26202/buildings?bbox=135,35,136,36&limit=10")
    assert response.status_code == 200
    assert response.json()["features"][0]["gml_id"] == "b-1"
    assert client.get("/cities/26202/buildings?bbox=135,35,136,36&limit=1001").status_code == 422


def test_priority2_detail_contracts_are_bounded_to_one_mesh_or_building() -> None:
    assert client.get("/cities/26202/meshes/533513314/detail").status_code == 200
    assert client.get("/cities/26202/meshes/missing/detail").status_code == 404
    assert client.get("/cities/26202/buildings/b-1").json()["gml_id"] == "b-1"
    accessibility = client.get("/cities/26202/buildings/b-1/accessibility").json()
    assert len(accessibility["policies"]) == 2
    assert accessibility["policies"][0]["origin_method"] == (
        "building_origin_representative_point"
    )
    assert client.get("/cities/26202/buildings/missing").status_code == 404
