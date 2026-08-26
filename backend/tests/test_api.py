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

    def networks(self, city_id: str) -> list[dict[str, Any]]:
        return [
            {
                "city_id": city_id,
                "graph_version": "exp-test",
                "pedestrian_network": False,
            }
        ]

    def road_edges(
        self,
        city_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
        graph_version: str | None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "city_id": city_id,
                "edge_id": "edge-1",
                "bbox": bbox,
                "limit": limit,
                "graph_version": graph_version,
                "pedestrian_network": False,
            }
        ]

    def building_network_accessibility(self, city_id: str, gml_id: str) -> dict[str, Any] | None:
        if gml_id == "missing":
            return None
        return {
            "city_id": city_id,
            "gml_id": gml_id,
            "routes": [
                {
                    "destination_class": "transport",
                    "network_distance_m": 604.9,
                    "pedestrian_network": False,
                }
            ],
        }

    def context_features(
        self,
        city_id: str,
        layer: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        return [{"city_id": city_id, "layer": layer, "bbox": bbox, "gml_id": "ctx-1"}]

    def mesh_context(self, city_id: str, mesh_code: str) -> list[dict[str, Any]]:
        return [{"city_id": city_id, "mesh_code": mesh_code, "context_type": "planning"}]

    def scenario_candidate_context(self, city_id: str, candidate_id: str) -> list[dict[str, Any]]:
        return [
            {
                "city_id": city_id,
                "candidate_id": candidate_id,
                "context_type": "hazard",
                "review_status": "additional_confirmation_required",
                "siting_feasibility": "not_determined",
            }
        ]

    def road_edge_hazards(
        self, city_id: str, edge_id: str, graph_version: str | None
    ) -> list[dict[str, Any]]:
        return [
            {
                "city_id": city_id,
                "edge_id": edge_id,
                "graph_version": graph_version,
                "review_status": "additional_confirmation_required",
                "siting_feasibility": "not_determined",
            }
        ]


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
    assert accessibility["policies"][0]["origin_method"] == ("building_origin_representative_point")
    assert client.get("/cities/26202/buildings/missing").status_code == 404


def test_network_contracts_expose_claim_boundary_and_require_bbox() -> None:
    networks = client.get("/cities/26202/networks").json()
    assert networks[0]["graph_version"] == "exp-test"
    assert networks[0]["pedestrian_network"] is False
    assert client.get("/cities/26202/road-edges").status_code == 422
    response = client.get("/cities/26202/road-edges?bbox=135,35,136,36&graph_version=exp-test")
    assert response.status_code == 200
    assert response.json()["features"][0]["edge_id"] == "edge-1"
    network = client.get("/cities/26202/buildings/b-1/network-accessibility").json()
    assert network["routes"][0]["pedestrian_network"] is False
    assert client.get("/cities/26202/buildings/missing/network-accessibility").status_code == 404


def test_context_layers_require_bbox_and_preserve_hazard_review_semantics() -> None:
    assert client.get("/cities/26202/context/landuse").status_code == 422
    assert client.get("/cities/26202/context/unknown?bbox=135,35,136,36").status_code == 404
    response = client.get("/cities/26202/context/hazards?bbox=135,35,136,36")
    assert response.status_code == 200
    assert response.json()["features"][0]["layer"] == "hazards"

    mesh = client.get("/cities/26202/meshes/533513314/context").json()
    assert mesh["contexts"][0]["context_type"] == "planning"
    candidate = client.get("/cities/26202/scenario-candidates/tran-1/context").json()
    assert candidate["siting_decision"] == "not_determined"
    assert candidate["contexts"][0]["review_status"] == ("additional_confirmation_required")
    hazards = client.get("/cities/26202/road-edges/edge-1/hazards?graph_version=exp-test").json()
    assert hazards["hazards"][0]["siting_feasibility"] == "not_determined"
