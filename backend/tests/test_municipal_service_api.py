from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.security.auth import DEFAULT_ORGANIZATION_ID

ORG_A = DEFAULT_ORGANIZATION_ID
ORG_B = "00000000-0000-0000-0000-000000000002"
CITY_ID = "10000000-0000-0000-0000-000000000001"
STATE_ID = "20000000-0000-0000-0000-000000000001"
FINDING_ID = "30000000-0000-0000-0000-000000000001"
INVESTIGATION_ID = "40000000-0000-0000-0000-000000000001"
REVIEW_ID = "50000000-0000-0000-0000-000000000001"
EVIDENCE_ID = "60000000-0000-0000-0000-000000000001"
VERSION_ID = "70000000-0000-0000-0000-000000000001"
SCENARIO_A = "80000000-0000-0000-0000-000000000001"
SCENARIO_B = "80000000-0000-0000-0000-000000000002"


def headers(role: str, organization_id: str = ORG_A) -> dict[str, str]:
    return {
        "X-CITYGAP-Actor": f"fixture-{role}",
        "X-CITYGAP-Roles": role,
        "X-CITYGAP-Organization": organization_id,
    }


class MunicipalRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def service_profile(self, organization_id: str, actor: str, issuer: str):
        self.calls.append(("profile", organization_id))
        if organization_id != ORG_A:
            return None
        return {
            "organization": {
                "id": ORG_A,
                "organization_key": "fixture-city",
                "name": "検証自治体",
            },
            "user": None,
            "memberships": [],
        }

    def service_cities(self, organization_id: str):
        self.calls.append(("cities", organization_id))
        return [] if organization_id != ORG_A else [{"city_id": CITY_ID, "name": "検証市"}]

    def city_service_home(self, organization_id: str, city: str):
        self.calls.append(("home", organization_id))
        if organization_id != ORG_A or city != "fixture-city":
            return None
        return {"city": {"id": CITY_ID, "name": "検証市"}, "summary": {}}

    def findings(
        self,
        organization_id: str,
        city: str,
        status: str | None,
        finding_type: str | None,
        search: str | None,
        limit: int,
        cursor: str | None,
    ):
        self.calls.append(("findings", organization_id))
        if organization_id != ORG_A:
            return None
        return {"city": {"id": CITY_ID}, "items": [], "next_cursor": None}

    def create_finding(self, organization_id: str, city: str, payload: dict[str, Any]):
        self.calls.append(("create_finding", organization_id))
        return {"id": FINDING_ID, "status": "new", **payload}

    def transition_finding(
        self,
        organization_id: str,
        finding_id: str,
        expected_status: str,
        proposed_status: str,
        dismissal_reason: str | None,
    ):
        self.calls.append(("transition_finding", organization_id))
        return {"id": finding_id, "status": proposed_status}

    def create_investigation(self, organization_id: str, city: str, payload: dict[str, Any]):
        self.calls.append(("create_investigation", organization_id))
        return {"id": INVESTIGATION_ID, "status": "open", **payload}

    def investigations(
        self,
        organization_id: str,
        city: str,
        status: str | None,
        search: str | None,
        limit: int,
    ):
        return [{"id": INVESTIGATION_ID, "status": status or "open"}]

    def transition_investigation(
        self,
        organization_id: str,
        investigation_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ):
        return {"id": investigation_id, "status": proposed_status, "note": note}

    def investigation_detail(self, organization_id: str, investigation_id: str):
        self.calls.append(("investigation", organization_id))
        return {"investigation": {"id": investigation_id}, "findings": []}

    def save_investigation_view(
        self, organization_id: str, investigation_id: str, payload: dict[str, Any]
    ):
        return {"id": FINDING_ID, "investigation_id": investigation_id, **payload}

    def create_review(self, organization_id: str, investigation_id: str, payload: dict[str, Any]):
        self.calls.append(("create_review", organization_id))
        return {"id": REVIEW_ID, "status": "requested", **payload}

    def transition_review(
        self,
        organization_id: str,
        review_id: str,
        expected_status: str,
        proposed_status: str,
        review_note: str,
    ):
        return {"id": review_id, "status": proposed_status, "review_note": review_note}

    def create_field_observation(
        self, organization_id: str, investigation_id: str, payload: dict[str, Any]
    ):
        self.calls.append(("field", organization_id))
        return {"id": FINDING_ID, "investigation_id": investigation_id, **payload}

    def create_decision_record(
        self, organization_id: str, investigation_id: str, payload: dict[str, Any]
    ):
        self.calls.append(("decision", organization_id))
        return {
            "id": FINDING_ID,
            "investigation_id": investigation_id,
            "source": "human_entry",
            "optimizer_generated": False,
            **payload,
        }

    def create_review_note(
        self,
        organization_id: str,
        resource_type: str,
        resource_id: str,
        body: str,
        parent_note_id: str | None,
    ):
        return {"id": FINDING_ID, "resource_type": resource_type, "body": body}

    def create_assignment(self, organization_id: str, payload: dict[str, Any]):
        return {"id": FINDING_ID, "status": "assigned", **payload}

    def work_queue(self, organization_id: str, actor: str, issuer: str):
        return {"assignments": [], "notifications": [], "unregistered_identity": True}

    def data_hub(self, organization_id: str, city: str):
        self.calls.append(("data_hub", organization_id))
        return {"city": {"id": CITY_ID}, "datasets": []}

    def transition_dataset_version(
        self,
        organization_id: str,
        version_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ):
        self.calls.append(("dataset_transition", organization_id))
        return {"id": version_id, "service_status": proposed_status, "note": note}

    def analysis_catalog(self):
        return [{"id": "accessibility-gap", "version": "1.0.0"}]

    def scenario_library(self, organization_id: str, city: str, limit: int):
        return []

    def create_scenario_comparison(self, organization_id: str, city: str, payload: dict[str, Any]):
        return {"id": FINDING_ID, **payload}

    def create_evidence_center(self, organization_id: str, city: str, payload: dict[str, Any]):
        return {"id": EVIDENCE_ID, **payload}

    def service_search(self, organization_id: str, query: str, city: str | None, limit: int):
        self.calls.append(("search", organization_id))
        return []

    def activity_feed(self, organization_id: str, city: str | None, limit: int):
        return []

    def record_usage(
        self,
        organization_id: str,
        city: str | None,
        event_name: str,
        feature_key: str,
    ) -> None:
        self.calls.append(("usage", organization_id))

    def service_health(self):
        return {"status": "ready"}


def test_v1_openapi_exposes_stable_service_resources() -> None:
    application = create_app(MunicipalRepository())  # type: ignore[arg-type]
    schema = application.openapi()
    assert schema["info"]["version"] == "0.2.0"
    for path in (
        "/api/v1/cities",
        "/api/v1/cities/{city}/home",
        "/api/v1/cities/{city}/findings",
        "/api/v1/cities/{city}/investigations",
        "/api/v1/investigations/{investigation_id}/reviews",
        "/api/v1/investigations/{investigation_id}/status",
        "/api/v1/investigations/{investigation_id}/field-observations",
        "/api/v1/investigations/{investigation_id}/decisions",
        "/api/v1/cities/{city}/data-hub",
        "/api/v1/analysis-definitions",
    ):
        assert path in schema["paths"]


def test_tenant_context_is_forwarded_and_unknown_tenant_is_not_found() -> None:
    repository = MunicipalRepository()
    client = TestClient(create_app(repository))  # type: ignore[arg-type]
    response = client.get("/api/v1/cities", headers=headers("viewer"))
    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "検証市"
    assert ("cities", ORG_A) in repository.calls

    other = client.get(
        "/api/v1/cities/fixture-city/home",
        headers={**headers("viewer", ORG_B), "X-Request-ID": "tenant-boundary-test"},
    )
    assert other.status_code == 404
    assert other.json()["error"] == {
        "code": "resource_not_found",
        "message": "City not found in this organization",
        "request_id": "tenant-boundary-test",
        "remediation": "Confirm the resource belongs to the selected organization and city.",
    }


def test_six_roles_are_separated_across_the_municipal_workflow() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    finding = {
        "finding_type": "accessibility_gap",
        "title": "追加調査候補",
        "summary": "モデル上の候補であり行政判断ではない",
        "urban_state_id": STATE_ID,
    }
    assert (
        client.post(
            "/api/v1/cities/fixture-city/findings", headers=headers("viewer"), json=finding
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/cities/fixture-city/findings", headers=headers("analyst"), json=finding
        ).status_code
        == 201
    )

    review_url = f"/api/v1/investigations/{INVESTIGATION_ID}/reviews"
    assert client.post(review_url, headers=headers("analyst"), json={}).status_code == 403
    assert client.post(review_url, headers=headers("planner"), json={}).status_code == 201

    field_url = f"/api/v1/investigations/{INVESTIGATION_ID}/field-observations"
    observation = {
        "observation_type": "access_check",
        "observed_at": "2026-08-28T12:00:00+09:00",
        "longitude": 135.3,
        "latitude": 35.4,
    }
    assert (
        client.post(field_url, headers=headers("field_staff"), json=observation).status_code == 201
    )

    transition_url = f"/api/v1/dataset-versions/{VERSION_ID}/status"
    transition = {
        "expected_status": "analysis_ready",
        "proposed_status": "promoted",
        "note": "品質・ingestion gate確認済み",
    }
    assert (
        client.patch(transition_url, headers=headers("planner"), json=transition).status_code == 403
    )
    assert (
        client.patch(transition_url, headers=headers("data_manager"), json=transition).status_code
        == 200
    )
    assert (
        client.patch(transition_url, headers=headers("administrator"), json=transition).status_code
        == 200
    )


def test_decision_contract_rejects_automation_fields_and_requires_planner() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    url = f"/api/v1/investigations/{INVESTIGATION_ID}/decisions"
    payload = {
        "review_request_id": REVIEW_ID,
        "decision": "additional_investigation",
        "reason": "現地確認結果を追加する必要がある",
        "related_evidence_ids": [EVIDENCE_ID],
    }
    assert client.post(url, headers=headers("analyst"), json=payload).status_code == 403
    response = client.post(url, headers=headers("planner"), json=payload)
    assert response.status_code == 201
    assert response.json()["source"] == "human_entry"
    automated = client.post(
        url,
        headers=headers("planner"),
        json={**payload, "source": "optimizer", "actor": "optimizer"},
    )
    assert automated.status_code == 422
    fields = automated.json()["error"]["fields"]
    assert {item["loc"][-1] for item in fields} == {"source", "actor"}


def test_collaboration_routes_preserve_human_authorship_and_role_boundaries() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    transition = client.patch(
        f"/api/v1/investigations/{INVESTIGATION_ID}/status",
        headers=headers("analyst"),
        json={
            "expected_status": "open",
            "proposed_status": "in_review",
            "note": "レビュー対象を整理",
        },
    )
    assert transition.status_code == 200
    comment = client.post(
        f"/api/v1/comments/investigation/{INVESTIGATION_ID}",
        headers=headers("field_staff"),
        json={"body": "現地で道路接続を確認"},
    )
    assert comment.status_code == 201
    assignment = {
        "assignment_type": "field_check",
        "resource_id": INVESTIGATION_ID,
        "assigned_to": FINDING_ID,
        "note": "現地確認を依頼",
    }
    assert (
        client.post("/api/v1/assignments", headers=headers("analyst"), json=assignment).status_code
        == 403
    )
    assert (
        client.post("/api/v1/assignments", headers=headers("planner"), json=assignment).status_code
        == 201
    )
    assert client.get("/api/v1/work-queue", headers=headers("viewer")).status_code == 200


def test_spatial_and_scenario_inputs_are_bounded_and_explicit() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    observation_url = f"/api/v1/investigations/{INVESTIGATION_ID}/field-observations"
    invalid_coordinates = client.post(
        observation_url,
        headers=headers("field_staff"),
        json={
            "observation_type": "access_check",
            "observed_at": "2026-08-28T12:00:00+09:00",
            "longitude": 135.3,
        },
    )
    assert invalid_coordinates.status_code == 422
    duplicate_scenarios = client.post(
        "/api/v1/cities/fixture-city/scenario-comparisons",
        headers=headers("analyst"),
        json={
            "title": "比較",
            "scenario_run_ids": [SCENARIO_A, SCENARIO_A],
            "comparison_dimensions": [{"key": "coverage"}],
        },
    )
    assert duplicate_scenarios.status_code == 422
    valid = client.post(
        "/api/v1/cities/fixture-city/scenario-comparisons",
        headers=headers("analyst"),
        json={
            "title": "2案比較",
            "scenario_run_ids": [SCENARIO_A, SCENARIO_B],
            "comparison_dimensions": [{"key": "coverage"}],
        },
    )
    assert valid.status_code == 201
