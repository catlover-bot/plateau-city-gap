from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.domain.validation import claim_registry_payload


class ValidationRepository:
    def validation_claims(self) -> list[dict[str, Any]]:
        return claim_registry_payload()

    def city_validations(self, city_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        return [{"validation_id": "run-1", "city_id": city_id}]

    def create_validation_run(self, city_id: str, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "validation_id": "10000000-0000-0000-0000-000000000001",
            "city_id": city_id,
            "validation_status": "unvalidated",
            "automatic_promotion": False,
        }

    def validation_detail(self, validation_id: str) -> dict[str, Any] | None:
        return {"validation_id": validation_id, "validation_status": "cross_validated"}

    def validation_samples(
        self,
        validation_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        return {"validation_id": validation_id, "bbox": bbox, "limit": limit, "offset": offset, "features": []}

    def validation_disagreements(
        self,
        validation_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        return {"validation_id": validation_id, "bbox": bbox, "limit": limit, "offset": offset, "features": []}

    def validation_sensitivity(
        self, validation_id: str, limit: int, offset: int
    ) -> dict[str, Any]:
        return {"validation_id": validation_id, "aggregation_score": None, "uncertainties": []}

    def create_validation_field_review(
        self, validation_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "validation_id": validation_id,
            "municipal_feedback": request["municipal_feedback"],
            "status": "submitted",
        }

    def update_validation_status(
        self, validation_id: str, expected: str, proposed: str, note: str
    ) -> dict[str, Any]:
        return {
            "validation_id": validation_id,
            "validation_status": proposed,
            "automatic_promotion": False,
            "note": note,
        }

    def register_validation_reference(
        self, city_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        return {"city_id": city_id, "reference_key": request["reference_key"], "status": request["status"]}


RUN_REQUEST = {
    "claim_key": "experimental_network_accessibility",
    "method_key": "osm_reference_comparison",
    "dataset_versions": {"plateau": "2025"},
    "algorithm_version": "v1",
    "reference_source": {"semantics": "reference_network"},
    "sample_rule": {"method": "deterministic_stratified", "count": 120},
    "limitations": ["not field ground truth"],
}
FIELD_REVIEW = {
    "validation_result_id": "10000000-0000-0000-0000-000000000002",
    "observation_type": "road_passability",
    "road_passability": "uncertain",
    "longitude": 135.3,
    "latitude": 35.4,
    "observed_at": "2026-08-27T12:00:00+09:00",
    "municipal_feedback": "not_reviewed",
}
REFERENCE = {
    "reference_key": "osm-20260827",
    "source_type": "osm",
    "source_url": "https://overpass-api.de/",
    "retrieval_date": "2026-08-27",
    "source_sha256": "a" * 64,
    "license": "ODbL",
    "attribution": "© OpenStreetMap contributors",
    "extraction_rule": "pinned query",
    "coverage": {"ways": 10},
    "status": "available",
    "limitations": ["reference network, not ground truth"],
}


def _headers(role: str) -> dict[str, str]:
    return {"X-CITYGAP-Actor": f"test-{role}", "X-CITYGAP-Roles": role}


def test_validation_read_endpoints_are_paginated_and_bbox_bounded() -> None:
    client = TestClient(create_app(ValidationRepository()))  # type: ignore[arg-type]
    claims = client.get("/validation/claims", headers=_headers("viewer"))
    assert claims.status_code == 200
    assert len(claims.json()["claims"]) == 9
    assert "never promotes" in claims.json()["status_semantics"]
    assert client.get(
        "/validation/run-1/samples?bbox=135,35,136,36&limit=10&offset=2",
        headers=_headers("viewer"),
    ).json()["limit"] == 10
    assert client.get(
        "/validation/run-1/disagreements?bbox=invalid",
        headers=_headers("viewer"),
    ).status_code == 422
    assert client.get(
        "/validation/run-1/sensitivity", headers=_headers("viewer")
    ).json()["aggregation_score"] is None


def test_validation_rbac_separates_viewer_analyst_planner_and_admin() -> None:
    client = TestClient(create_app(ValidationRepository()))  # type: ignore[arg-type]
    endpoint = "/cities/maizuru/validation"
    assert client.post(endpoint, json=RUN_REQUEST, headers=_headers("viewer")).status_code == 403
    created = client.post(endpoint, json=RUN_REQUEST, headers=_headers("analyst"))
    assert created.status_code == 201
    assert created.json()["validation_status"] == "unvalidated"

    review_endpoint = "/validation/10000000-0000-0000-0000-000000000001/field-review"
    assert client.post(review_endpoint, json=FIELD_REVIEW, headers=_headers("analyst")).status_code == 403
    assert client.post(review_endpoint, json=FIELD_REVIEW, headers=_headers("planner")).status_code == 201

    status_endpoint = "/validation/10000000-0000-0000-0000-000000000001/status"
    status_payload = {
        "expected_status": "unvalidated",
        "proposed_status": "cross_validated",
        "note": "explicit evidence governance decision",
    }
    status = client.patch(status_endpoint, json=status_payload, headers=_headers("planner"))
    assert status.status_code == 200
    assert status.json()["automatic_promotion"] is False

    reference_endpoint = "/cities/maizuru/validation/references"
    assert client.post(reference_endpoint, json=REFERENCE, headers=_headers("planner")).status_code == 403
    assert client.post(reference_endpoint, json=REFERENCE, headers=_headers("administrator")).status_code == 201


def test_validation_rejects_oversized_and_local_file_field_review_inputs() -> None:
    client = TestClient(create_app(ValidationRepository()))  # type: ignore[arg-type]
    endpoint = "/validation/10000000-0000-0000-0000-000000000001/field-review"
    oversized = {**FIELD_REVIEW, "review_note": "x" * (1024 * 1024 + 1)}
    assert client.post(endpoint, json=oversized, headers=_headers("planner")).status_code == 413
    invalid_reference = {**FIELD_REVIEW, "evidence_attachment_reference": "file:///etc/passwd"}
    assert client.post(endpoint, json=invalid_reference, headers=_headers("planner")).status_code == 422
