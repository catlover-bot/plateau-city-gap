from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.domain.jobs import (
    JobSnapshot,
    advance_job,
    fail_job,
    start_job,
    succeed_job,
)
from backend.citygap_platform.domain.scenarios import validate_status_transition


class FakeRepository:
    def __init__(self) -> None:
        self.lifecycle_status = "draft"
        self.checklists: dict[tuple[str, int], dict[str, Any]] = {}
        self.jobs: dict[str, JobSnapshot] = {}
        self.tile_calls = 0

    def health(self) -> bool:
        return True

    def readiness(self, required_city_id: str | None) -> dict[str, Any]:
        ready = self.health()
        return {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "checks": {"database": ready},
            "details": {"required_city_id": required_city_id},
        }

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

    def vector_tile(
        self,
        city_id: str,
        layer: str,
        z: int,
        x: int,
        y: int,
        dataset_version_id: str,
        network_version_id: str | None,
        scenario_id: str | None,
        algorithm_version: str | None,
    ) -> bytes:
        self.tile_calls += 1
        return f"{city_id}:{dataset_version_id}:{layer}:{z}/{x}/{y}".encode()

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

    def scenarios(self, city_id: str, status: str | None, limit: int) -> list[dict[str, Any]]:
        scenario = {
            "scenario_id": "scenario-a",
            "scenario_key": "network-overall-3",
            "city_id": city_id,
            "objective_mode": "overall",
            "site_count": 3,
            "lifecycle_status": self.lifecycle_status,
        }
        return [scenario] if status is None or status == self.lifecycle_status else []

    def scenario_detail(self, city_id: str, scenario_id: str) -> dict[str, Any] | None:
        if scenario_id == "missing":
            return None
        return {
            "scenario_id": scenario_id,
            "scenario_key": f"network-{scenario_id}",
            "city_id": city_id,
            "objective_mode": "overall" if scenario_id == "scenario-a" else "worst_served",
            "site_count": 3,
            "sites": [{"candidate_id": "tran-1"}],
            "impacts": {"improved_building_count": {"value": 42, "unit": "building"}},
            "contexts": [{"type": "hazard", "review_status": "additional_confirmation_required"}],
            "algorithm_kind": "deterministic_greedy_approximation",
            "algorithm_version": "network-scenario-test",
            "lifecycle_status": self.lifecycle_status,
        }

    def transition_scenario(
        self,
        city_id: str,
        scenario_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ) -> dict[str, Any] | None:
        if scenario_id == "missing":
            return None
        if expected_status != self.lifecycle_status:
            raise ValueError("Scenario status changed")
        validate_status_transition(self.lifecycle_status, proposed_status)
        self.lifecycle_status = proposed_status
        return {
            "scenario_id": scenario_id,
            "city_id": city_id,
            "lifecycle_status": proposed_status,
            "note": note,
        }

    def field_check(self, city_id: str, scenario_id: str, site_order: int) -> dict[str, Any] | None:
        return self.checklists.get((scenario_id, site_order))

    def save_field_check(
        self,
        city_id: str,
        scenario_id: str,
        site_order: int,
        checklist: dict[str, Any],
    ) -> dict[str, Any] | None:
        if scenario_id == "missing":
            return None
        value = {
            "city_id": city_id,
            "scenario_id": scenario_id,
            "site_order": site_order,
            **checklist,
        }
        self.checklists[(scenario_id, site_order)] = value
        return value

    def city_registry(self) -> list[dict[str, Any]]:
        return [
            {
                "city_code": "26202",
                "city_id": "maizuru",
                "capabilities": [
                    {"capability": "screening", "status": "available"},
                    {"capability": "gtfs", "status": "unavailable"},
                ],
            },
            {
                "city_code": "14205",
                "city_id": "fujisawa",
                "capabilities": [
                    {"capability": "screening", "status": "available"},
                    {"capability": "scenario", "status": "unavailable"},
                ],
            },
        ]

    def dataset_registry(self, city_id: str) -> list[dict[str, Any]]:
        return [
            {
                "dataset_version_id": "version-2025",
                "city_id": city_id,
                "dataset_key": "plateau",
                "year": 2025,
            }
        ]

    def analysis_runs(self, city_id: str, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "analysis_run_id": "run-screening",
                "city_id": city_id,
                "analysis_type": "screening",
                "status": "succeeded",
                "limit": limit,
            }
        ]

    def create_job(
        self,
        city_id: str,
        job_type: str,
        dataset_version_ids: list[str],
        config_hash: str,
        algorithm_version: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any] | None:
        if city_id == "missing":
            return None
        self.jobs["job-1"] = JobSnapshot(job_type=job_type)
        return self.job_detail("job-1")

    def job_detail(self, job_id: str) -> dict[str, Any] | None:
        snapshot = self.jobs.get(job_id)
        if snapshot is None:
            return None
        return {
            "job_id": job_id,
            "job_type": snapshot.job_type,
            "state": snapshot.state.value,
            "current_stage": snapshot.current_stage,
            "completed_stages": snapshot.completed_stages,
            "error": snapshot.error,
        }

    def transition_job(
        self, job_id: str, action: str, stage: str | None, error: str | None
    ) -> dict[str, Any] | None:
        snapshot = self.jobs.get(job_id)
        if snapshot is None:
            return None
        if action == "start":
            updated = start_job(snapshot)
        elif action == "advance":
            updated = advance_job(snapshot, stage or "")
        elif action == "succeed":
            updated = succeed_job(snapshot)
        else:
            updated = fail_job(snapshot, error or "")
        self.jobs[job_id] = updated
        return self.job_detail(job_id)

    def audit_events(self, city_id: str | None, limit: int) -> list[dict[str, Any]]:
        return [{"actor": "test", "city_id": city_id, "limit": limit}]

    def admin_snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "cities": [{"city_code": "26202"}],
            "datasets": [],
            "capabilities": [],
            "networks": [],
            "jobs": [],
            "users": [],
        }


client = TestClient(create_app(FakeRepository()))


def test_health_and_city_endpoints() -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json()["ready"] is True
    assert client.get("/cities").json()[0]["city_id"] == "26202"
    assert client.get("/cities/26202/layers").json()[0]["theme"] == "bldg"


def test_liveness_is_independent_but_readiness_checks_dependencies() -> None:
    repository = FakeRepository()
    repository.health = lambda: False  # type: ignore[method-assign]
    probe_client = TestClient(create_app(repository))
    assert probe_client.get("/health").status_code == 200
    response = probe_client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


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


def test_versioned_vector_tiles_are_bounded_cached_and_private() -> None:
    repository = FakeRepository()
    tile_client = TestClient(create_app(repository))
    version = "10000000-0000-0000-0000-000000000002"
    url = f"/cities/26202/tiles/buildings/0/0/0.mvt?dataset_version_id={version}"
    response = tile_client.get(url, headers={"X-CITYGAP-Roles": "viewer"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.mapbox-vector-tile")
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert response.headers["x-citygap-dataset-version"] == version
    etag = response.headers["etag"]
    assert repository.tile_calls == 1
    cached = tile_client.get(
        url,
        headers={"X-CITYGAP-Roles": "viewer", "If-None-Match": etag},
    )
    assert cached.status_code == 304
    assert repository.tile_calls == 1
    assert tile_client.get(
        f"/cities/26202/tiles/buildings/2/4/0.mvt?dataset_version_id={version}"
    ).status_code == 422
    assert tile_client.get(
        f"/cities/26202/tiles/road_edges/0/0/0.mvt?dataset_version_id={version}"
    ).status_code == 422


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


def test_scenario_comparison_is_bounded_to_three_without_recommendation() -> None:
    scenarios = client.get("/cities/26202/scenarios?status=draft").json()
    assert scenarios["scenarios"][0]["scenario_key"] == "network-overall-3"
    comparison = client.get("/cities/26202/scenario-comparison?scenario_ids=scenario-a,scenario-b")
    assert comparison.status_code == 200
    assert comparison.json()["comparison_limit"] == 3
    assert comparison.json()["recommendation"] is None
    assert len(comparison.json()["plans"]) == 2
    assert client.get("/cities/26202/scenario-comparison?scenario_ids=a,b,c,d").status_code == 422


def test_scenario_lifecycle_requires_explicit_valid_transitions() -> None:
    repository = FakeRepository()
    scenario_client = TestClient(create_app(repository))
    invalid = scenario_client.patch(
        "/cities/26202/scenarios/scenario-a/status",
        json={
            "expected_status": "draft",
            "proposed_status": "reviewed",
            "note": "must not skip review",
        },
    )
    assert invalid.status_code == 409
    valid = scenario_client.patch(
        "/cities/26202/scenarios/scenario-a/status",
        json={
            "expected_status": "draft",
            "proposed_status": "under_review",
            "note": "submitted by a municipal reviewer",
        },
    )
    assert valid.status_code == 200
    assert valid.json()["lifecycle_status"] == "under_review"


def test_field_check_is_human_entered_and_persisted_by_site() -> None:
    repository = FakeRepository()
    scenario_client = TestClient(create_app(repository))
    path = "/cities/26202/scenarios/scenario-a/sites/1/field-check"
    assert scenario_client.get(path).status_code == 404
    saved = scenario_client.put(
        path,
        json={
            "site_access": "confirmed",
            "road_safety": "attention",
            "land_ownership_unknown": "unknown",
            "existing_service": "confirmed",
            "facility_condition": "unknown",
            "hazard_confirmation": "attention",
            "operator_consultation": "unknown",
            "notes": "現地で横断位置を確認",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["hazard_confirmation"] == "attention"
    assert scenario_client.get(path).json()["notes"] == "現地で横断位置を確認"


def test_city_dataset_and_analysis_registries_expose_explicit_versions() -> None:
    cities = client.get("/registry/cities").json()
    assert cities["capability_statuses"] == ["available", "partial", "unavailable"]
    assert cities["cities"][1]["capabilities"][1] == {
        "capability": "scenario",
        "status": "unavailable",
    }
    datasets = client.get("/registry/cities/26202/datasets").json()
    assert datasets["dataset_versions"][0]["dataset_version_id"] == "version-2025"
    assert "never implicit latest" in datasets["version_selection"]
    runs = client.get("/registry/cities/26202/analysis-runs?limit=10").json()
    assert runs["analysis_runs"][0]["status"] == "succeeded"
    assert client.get("/registry/cities/26202/analysis-runs?limit=101").status_code == 422


def test_jobs_report_real_stages_without_fake_percentages() -> None:
    repository = FakeRepository()
    job_client = TestClient(create_app(repository))
    created = job_client.post(
        "/registry/cities/26202/jobs",
        json={
            "job_type": "scenario_optimization",
            "dataset_version_ids": ["version-2025"],
            "config_hash": "a" * 64,
            "algorithm_version": "network-scenario-test",
            "parameters": {"site_count": 3},
        },
    )
    assert created.status_code == 201
    assert created.json()["state"] == "queued"
    assert "progress" not in created.json()
    started = job_client.post("/jobs/job-1/transition", json={"action": "start"})
    assert started.json()["current_stage"] == "prepare_candidates"
    advanced = job_client.post(
        "/jobs/job-1/transition",
        json={"action": "advance", "stage": "build_sparse_matrix"},
    )
    assert advanced.json()["current_stage"] == "build_sparse_matrix"
    invalid = job_client.post(
        "/jobs/job-1/transition",
        json={"action": "advance", "stage": "persist_artifacts"},
    )
    assert invalid.status_code == 409
    assert job_client.get("/jobs/missing").status_code == 404


def test_rbac_separates_view_analysis_review_and_platform_operations() -> None:
    repository = FakeRepository()
    rbac_client = TestClient(create_app(repository))
    viewer = {"X-CITYGAP-Actor": "viewer-1", "X-CITYGAP-Roles": "viewer"}
    analyst = {"X-CITYGAP-Actor": "analyst-1", "X-CITYGAP-Roles": "analyst"}
    planner = {"X-CITYGAP-Actor": "planner-1", "X-CITYGAP-Roles": "planner"}
    administrator = {"X-CITYGAP-Actor": "admin-1", "X-CITYGAP-Roles": "administrator"}
    assert rbac_client.get("/cities", headers=viewer).status_code == 200
    assert rbac_client.post(
        "/registry/cities/26202/jobs",
        headers=viewer,
        json={
            "job_type": "scenario_optimization",
            "dataset_version_ids": ["version-2025"],
            "config_hash": "a" * 64,
            "algorithm_version": "test",
        },
    ).status_code == 403
    assert rbac_client.post(
        "/registry/cities/26202/jobs",
        headers=analyst,
        json={
            "job_type": "scenario_optimization",
            "dataset_version_ids": ["version-2025"],
            "config_hash": "a" * 64,
            "algorithm_version": "test",
        },
    ).status_code == 201
    assert rbac_client.put(
        "/cities/26202/scenarios/scenario-a/sites/1/field-check",
        headers=analyst,
        json={"notes": "not allowed"},
    ).status_code == 403
    assert rbac_client.put(
        "/cities/26202/scenarios/scenario-a/sites/1/field-check",
        headers=planner,
        json={"notes": "allowed"},
    ).status_code == 200
    assert rbac_client.get("/admin/audit", headers=planner).status_code == 403
    assert rbac_client.get("/admin/snapshot", headers=planner).status_code == 403
    assert rbac_client.get("/admin/snapshot", headers=administrator).json()["cities"] == [
        {"city_code": "26202"}
    ]
