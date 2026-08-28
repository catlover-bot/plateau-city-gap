from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.observability import current_request_context
from backend.citygap_platform.security.auth import DEFAULT_ORGANIZATION_ID
from backend.citygap_platform.storage import LocalAttachmentStore

ORG_A = DEFAULT_ORGANIZATION_ID
ORG_B = "00000000-0000-0000-0000-000000000002"
CITY_ID = "10000000-0000-0000-0000-000000000001"
STATE_ID = "20000000-0000-0000-0000-000000000001"
NEXT_STATE_ID = "20000000-0000-0000-0000-000000000002"
FINDING_ID = "30000000-0000-0000-0000-000000000001"
INVESTIGATION_ID = "40000000-0000-0000-0000-000000000001"
REVIEW_ID = "50000000-0000-0000-0000-000000000001"
EVIDENCE_ID = "60000000-0000-0000-0000-000000000001"
VERSION_ID = "70000000-0000-0000-0000-000000000001"
SCENARIO_A = "80000000-0000-0000-0000-000000000001"
SCENARIO_B = "80000000-0000-0000-0000-000000000002"
REPORT_ID = "90000000-0000-0000-0000-000000000001"
JOB_ID = "a0000000-0000-0000-0000-000000000001"
ATTACHMENT_ID = "b0000000-0000-0000-0000-000000000001"
USER_ID = "c0000000-0000-0000-0000-000000000001"
SHARE_TOKEN = "d" * 48


def headers(role: str, organization_id: str = ORG_A) -> dict[str, str]:
    return {
        "X-CITYGAP-Actor": f"fixture-{role}",
        "X-CITYGAP-Roles": role,
        "X-CITYGAP-Organization": organization_id,
    }


class MunicipalRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.attachment: dict[str, Any] | None = None

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

    def organization_members(self, organization_id: str):
        return (
            []
            if organization_id != ORG_A
            else [
                {
                    "user_id": USER_ID,
                    "display_name": "検証管理者",
                    "role": "administrator",
                    "active": True,
                }
            ]
        )

    def create_organization_membership(self, organization_id: str, payload: dict[str, Any]):
        return {"user_id": USER_ID, "active": True, **payload}

    def transition_organization_membership(
        self,
        organization_id: str,
        user_id: str,
        role: str,
        expected_active: bool,
        proposed_active: bool,
        note: str,
    ):
        return {
            "user_id": user_id,
            "role": role,
            "active": proposed_active,
            "note": note,
        }

    def organization_settings(self, organization_id: str):
        return {
            "configuration": [],
            "retention_policies": [],
        }

    def update_organization_configuration(
        self,
        organization_id: str,
        config_key: str,
        config_value: Any,
        expected_updated_at,
        note: str,
    ):
        return {
            "config_key": config_key,
            "config_value": config_value,
            "updated_by": "fixture-administrator",
            "updated_at": "2026-08-28T12:00:00+09:00",
        }

    def update_retention_policy(
        self,
        organization_id: str,
        resource_type: str,
        expected_retention_days: int | None,
        proposed_retention_days: int | None,
        legal_hold_supported: bool,
        note: str,
    ):
        return {
            "resource_type": resource_type,
            "retention_days": proposed_retention_days,
            "legal_hold_supported": legal_hold_supported,
            "enforcement_enabled": False,
        }

    def create_service_city(self, organization_id: str, payload: dict[str, Any]):
        return {"id": CITY_ID, "service_status": "onboarding", **payload}

    def city_onboarding(self, organization_id: str, city: str):
        if organization_id != ORG_A or city != "fixture-city":
            return None
        return {"city": {"id": CITY_ID}, "steps": [], "capabilities": []}

    def service_urban_states(self, organization_id: str, city: str, limit: int):
        return [{"id": STATE_ID, "lifecycle_status": "validated"}]

    def create_service_urban_state(self, organization_id: str, city: str, payload: dict[str, Any]):
        return {"id": STATE_ID, "lifecycle_status": "draft", **payload}

    def transition_service_urban_state(
        self,
        organization_id: str,
        state_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ):
        return {"id": state_id, "lifecycle_status": proposed_status}

    def annual_updates(self, organization_id: str, city: str, limit: int):
        if organization_id != ORG_A or city != "fixture-city":
            return None
        return [
            {
                "id": EVIDENCE_ID,
                "from_urban_state_id": STATE_ID,
                "to_urban_state_id": NEXT_STATE_ID,
                "job_state": "queued",
            }
        ]

    def create_annual_update(self, organization_id: str, city: str, payload: dict[str, Any]):
        if organization_id != ORG_A or city != "fixture-city":
            return None
        return {
            "change_set": {"id": EVIDENCE_ID, "status": "pending"},
            "job": {"id": JOB_ID, "state": "queued"},
            "contract": payload,
            "previous_records": {
                "investigations": 1,
                "analysis_runs": 1,
                "reports": 1,
                "changed_by_this_request": False,
            },
            "created": True,
        }

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

    def saved_view(self, organization_id: str, share_token: str):
        if organization_id != ORG_A or share_token != SHARE_TOKEN:
            return None
        return {
            "id": FINDING_ID,
            "investigation_id": INVESTIGATION_ID,
            "title": "庁内確認ビュー",
            "spatial_state": {"viewport": {"longitude": 135.3, "latitude": 35.4, "zoom": 14}},
        }

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

    def attachment_city(self, organization_id: str, city: str):
        if organization_id != ORG_A or city != "fixture-city":
            return None
        return {"id": CITY_ID, "city_key": city}

    def create_attachment_metadata(self, organization_id: str, city: str, payload: dict[str, Any]):
        if organization_id != ORG_A or city != "fixture-city":
            return None
        self.attachment = {
            "id": ATTACHMENT_ID,
            "city_id": CITY_ID,
            "created_by": "fixture-field_staff",
            **payload,
        }
        return self.attachment

    def attachment_metadata(self, organization_id: str, attachment_id: str):
        if organization_id != ORG_A or attachment_id != ATTACHMENT_ID:
            return None
        return self.attachment

    def create_field_offline_package(
        self,
        city: str,
        urban_state_id: str,
        scenario_run_id: str,
        site_order: int,
        expires_at: str | None,
    ):
        if current_request_context().organization_id != ORG_A or city != "fixture-city":
            return None
        return {
            "offline_package_id": EVIDENCE_ID,
            "package_version": 1,
            "content_sha256": "a" * 64,
            "content": {
                "package_scope": "single_selected_site",
                "urban_state_id": urban_state_id,
                "scenario_run_id": scenario_run_id,
                "site_order": site_order,
            },
            "expires_at": expires_at,
        }

    def sync_field_operation(self, city: str, operation: dict[str, Any]):
        if current_request_context().organization_id != ORG_A or city != "fixture-city":
            return None
        if operation["base_record_version"] == 2:
            return {
                "client_operation_id": operation["client_operation_id"],
                "status": "conflict",
                "conflict_id": REVIEW_ID,
                "silent_last_write_wins": False,
            }
        return {
            "client_operation_id": operation["client_operation_id"],
            "status": "applied",
            "record_version": 2,
        }

    def field_sync_conflict(self, conflict_id: str):
        if current_request_context().organization_id != ORG_A or conflict_id != REVIEW_ID:
            return None
        return {
            "conflict_id": conflict_id,
            "resolution_status": "unresolved",
            "silent_last_write_wins": False,
        }

    def resolve_field_sync_conflict(self, city: str, conflict_id: str, resolution: dict[str, Any]):
        if current_request_context().organization_id != ORG_A or city != "fixture-city":
            return None
        return {"conflict_id": conflict_id, **resolution, "silent_last_write_wins": False}

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
        return {"city": {"id": CITY_ID}, "datasets": [], "urban_states": []}

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

    def register_service_dataset(self, organization_id: str, city: str, payload: dict[str, Any]):
        return {
            "dataset": {"id": FINDING_ID, **payload},
            "version": {"id": VERSION_ID, "service_status": "registered"},
        }

    def analysis_catalog(self):
        return [{"id": "accessibility-gap", "version": "1.0.0"}]

    def service_analysis_runs(self, organization_id: str, city: str, limit: int):
        return []

    def create_service_analysis_run(self, organization_id: str, city: str, payload: dict[str, Any]):
        return {
            "analysis_run": {"id": FINDING_ID, "status": "queued"},
            "job": {"id": REVIEW_ID, "state": "queued"},
            "reproducibility": payload,
        }

    def scenario_library(self, organization_id: str, city: str, limit: int):
        return []

    def clone_scenario(self, organization_id: str, scenario_id: str, title: str):
        if organization_id != ORG_A:
            return None
        return {
            "id": SCENARIO_B,
            "parent_scenario_run_id": scenario_id,
            "title": title,
            "lifecycle_status": "draft",
        }

    def scenario_comparisons(self, organization_id: str, city: str, limit: int):
        return []

    def create_scenario_comparison(self, organization_id: str, city: str, payload: dict[str, Any]):
        return {"id": FINDING_ID, **payload}

    def create_evidence_center(self, organization_id: str, city: str, payload: dict[str, Any]):
        return {"id": EVIDENCE_ID, **payload}

    def evidence_library(self, organization_id: str, city: str, limit: int):
        if organization_id != ORG_A or city != "fixture-city":
            return None
        return {
            "city": {"id": CITY_ID},
            "evidence_centers": [{"id": EVIDENCE_ID}],
            "reports": [{"id": REPORT_ID}],
            "validation_runs": [],
        }

    def create_report_record(self, organization_id: str, city: str, payload: dict[str, Any]):
        self.calls.append(("create_report", organization_id))
        if organization_id != ORG_A or city != "fixture-city":
            return None
        return {
            "id": REPORT_ID,
            "artifact_sha256": "a" * 64,
            "data_classification": payload["data_classification"],
            **payload,
        }

    def report_artifact(self, organization_id: str, report_id: str):
        if organization_id != ORG_A or report_id != REPORT_ID:
            return None
        return {
            "structured_content": {
                "schema_version": "citygap-municipal-report-1.0.0",
                "claim_boundary": "human decision required",
            },
            "artifact_sha256": "a" * 64,
            "data_classification": "internal",
        }

    def export_report(self, organization_id: str, report_id: str, export_scope: str):
        if export_scope == "public":
            raise ValueError("Only public-classified reports can be exported publicly")
        return {"id": EVIDENCE_ID, "report_id": report_id, "export_scope": export_scope}

    def service_search(self, organization_id: str, query: str, city: str | None, limit: int):
        self.calls.append(("search", organization_id))
        return []

    def activity_feed(self, organization_id: str, city: str | None, limit: int):
        return []

    def service_audit_events(
        self,
        organization_id: str,
        city: str | None,
        action: str | None,
        actor: str | None,
        occurred_from,
        occurred_to,
        limit: int,
        cursor: str | None,
    ):
        if organization_id != ORG_A:
            return {"items": [], "next_cursor": None}
        return {
            "items": [
                {
                    "id": 1,
                    "actor": actor or "fixture-administrator",
                    "action": action or "finding.create",
                    "city_id": CITY_ID,
                }
            ],
            "next_cursor": None,
        }

    def record_usage(
        self,
        organization_id: str,
        city: str | None,
        event_name: str,
        feature_key: str,
    ) -> None:
        self.calls.append(("usage", organization_id))

    def operations_overview(self, organization_id: str):
        return {
            "jobs": {"queued": 1, "running": 0, "failed": 0, "cancelled": 0},
            "datasets": {"failed": 0},
            "backups": [],
            "releases": [],
            "configuration": [],
            "retention_policies": [],
            "boundaries": {},
        }

    def service_jobs(self, organization_id: str, state: str | None, limit: int):
        if organization_id != ORG_A:
            return []
        return [{"id": JOB_ID, "state": state or "queued", "job_type": "analysis_run"}]

    def service_job_detail(self, organization_id: str, job_id: str):
        if organization_id != ORG_A:
            return None
        return {"job": {"id": job_id, "effective_state": "queued"}, "events": []}

    def operate_service_job(
        self,
        organization_id: str,
        job_id: str,
        action: str,
        expected_state: str,
        reason: str,
        cancel_confirmation: str | None,
    ):
        return {
            "id": job_id,
            "effective_state": "cancelled" if action == "cancel" else "queued",
        }

    def service_health(self, organization_id: str):
        return {"status": "ready"}

    def prometheus_metrics(self, organization_id: str):
        return 'citygap_jobs{state="queued"} 1\n'


def test_v1_openapi_exposes_stable_service_resources() -> None:
    application = create_app(MunicipalRepository())  # type: ignore[arg-type]
    schema = application.openapi()
    assert schema["info"]["version"] == "0.2.0"
    for path in (
        "/api/v1/cities",
        "/api/v1/organizations/current/memberships",
        "/api/v1/organizations/current/settings",
        "/api/v1/organizations/current/configuration/{config_key}",
        "/api/v1/organizations/current/retention-policies/{resource_type}",
        "/api/v1/cities/{city}/home",
        "/api/v1/cities/{city}/onboarding",
        "/api/v1/cities/{city}/urban-states",
        "/api/v1/urban-states/{state_id}/status",
        "/api/v1/cities/{city}/annual-updates",
        "/api/v1/cities/{city}/findings",
        "/api/v1/cities/{city}/investigations",
        "/api/v1/saved-views/{share_token}",
        "/api/v1/investigations/{investigation_id}/reviews",
        "/api/v1/investigations/{investigation_id}/status",
        "/api/v1/investigations/{investigation_id}/field-observations",
        "/api/v1/cities/{city}/field/offline-packages",
        "/api/v1/cities/{city}/field/sync",
        "/api/v1/field-conflicts/{conflict_id}",
        "/api/v1/cities/{city}/field-conflicts/{conflict_id}/resolve",
        "/api/v1/cities/{city}/attachments",
        "/api/v1/attachments/{attachment_id}",
        "/api/v1/investigations/{investigation_id}/decisions",
        "/api/v1/cities/{city}/data-hub",
        "/api/v1/cities/{city}/datasets",
        "/api/v1/analysis-definitions",
        "/api/v1/cities/{city}/analysis-runs",
        "/api/v1/cities/{city}/scenario-comparisons",
        "/api/v1/scenarios/{scenario_id}/clone",
        "/api/v1/cities/{city}/evidence",
        "/api/v1/cities/{city}/reports",
        "/api/v1/reports/{report_id}/artifact",
        "/api/v1/reports/{report_id}/exports",
        "/api/v1/operations/overview",
        "/api/v1/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/operations",
        "/api/v1/metrics",
        "/api/v1/audit-events",
        "/api/v1/support-bundle",
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
        "detail": None,
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


def test_administrator_manages_directory_backed_memberships_without_invitation_claims() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    url = "/api/v1/organizations/current/memberships"
    assert client.get(url, headers=headers("planner")).status_code == 403
    listed = client.get(url, headers=headers("administrator"))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["role"] == "administrator"
    created = client.post(
        url,
        headers=headers("administrator"),
        json={
            "issuer": "https://identity.example.jp",
            "subject": "directory-user-42",
            "display_name": "データ担当者",
            "email": "data@example.jp",
            "role": "data_manager",
        },
    )
    assert created.status_code == 201
    assert created.json()["role"] == "data_manager"
    disabled = client.patch(
        f"{url}/{USER_ID}/data_manager",
        headers=headers("administrator"),
        json={
            "expected_active": True,
            "proposed_active": False,
            "note": "担当変更をIdP記録と照合",
        },
    )
    assert disabled.status_code == 200
    assert disabled.json()["active"] is False


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


def test_attachment_bytes_are_hash_verified_and_tenant_authorized(tmp_path) -> None:
    repository = MunicipalRepository()
    store = LocalAttachmentStore(tmp_path / "attachments")
    client = TestClient(create_app(repository, attachment_store=store))  # type: ignore[arg-type]
    content = b"field evidence"
    uploaded = client.post(
        "/api/v1/cities/fixture-city/attachments",
        headers={**headers("field_staff"), "Content-Type": "text/plain"},
        params={"filename": "field-note.txt", "data_classification": "restricted"},
        content=content,
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["id"] == ATTACHMENT_ID
    assert (
        uploaded.json()["sha256"]
        == "986cf303719fc088e1157cdefd2a8a92e0c58fc05f86676756384a6f017dc49a"
    )
    assert "object_key" not in uploaded.json()

    downloaded = client.get(f"/api/v1/attachments/{ATTACHMENT_ID}", headers=headers("field_staff"))
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["etag"] == f'"{uploaded.json()["sha256"]}"'
    assert downloaded.headers["x-content-type-options"] == "nosniff"

    tenant_leak = client.get(
        f"/api/v1/attachments/{ATTACHMENT_ID}", headers=headers("field_staff", ORG_B)
    )
    assert tenant_leak.status_code == 404
    invalid_name = client.post(
        "/api/v1/cities/fixture-city/attachments",
        headers={**headers("field_staff"), "Content-Type": "text/plain"},
        params={"filename": "../field-note.txt"},
        content=content,
    )
    assert invalid_name.status_code == 422


def test_selected_site_offline_sync_requires_explicit_conflict_resolution() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    package = client.post(
        "/api/v1/cities/fixture-city/field/offline-packages",
        headers=headers("field_staff"),
        json={
            "urban_state_id": STATE_ID,
            "scenario_run_id": SCENARIO_A,
            "site_order": 1,
            "expires_at": "2026-09-01T00:00:00+09:00",
        },
    )
    assert package.status_code == 201
    assert package.json()["content"]["package_scope"] == "single_selected_site"
    operation = {
        "client_operation_id": ATTACHMENT_ID,
        "offline_package_id": EVIDENCE_ID,
        "scenario_run_id": SCENARIO_A,
        "site_order": 1,
        "base_record_version": 2,
        "client_updated_at": "2026-08-28T12:00:00+09:00",
        "payload": {"notes": "現地確認", "site_access": "confirmed"},
    }
    conflict = client.post(
        "/api/v1/cities/fixture-city/field/sync",
        headers=headers("field_staff"),
        json=operation,
    )
    assert conflict.status_code == 409
    assert conflict.json()["silent_last_write_wins"] is False

    other_tenant = client.get(
        f"/api/v1/field-conflicts/{REVIEW_ID}", headers=headers("field_staff", ORG_B)
    )
    assert other_tenant.status_code == 404
    missing_merge = client.post(
        f"/api/v1/cities/fixture-city/field-conflicts/{REVIEW_ID}/resolve",
        headers=headers("planner"),
        json={"resolution_status": "merged"},
    )
    assert missing_merge.status_code == 422
    resolved = client.post(
        f"/api/v1/cities/fixture-city/field-conflicts/{REVIEW_ID}/resolve",
        headers=headers("planner"),
        json={
            "resolution_status": "merged",
            "resolved_state": {"notes": "サーバー記録と現地記録を確認して統合"},
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolution_status"] == "merged"


def test_analysis_run_requires_explicit_versions_and_analysis_role() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    payload = {
        "analysis_id": "accessibility-gap",
        "analysis_version": "1.0.0",
        "urban_state_id": STATE_ID,
        "dataset_versions": {
            "population": VERSION_ID,
            "facilities": VERSION_ID,
            "plateau_buildings": VERSION_ID,
        },
        "parameters": {"candidate_limit": 10},
    }
    url = "/api/v1/cities/fixture-city/analysis-runs"
    assert client.post(url, headers=headers("viewer"), json=payload).status_code == 403
    result = client.post(url, headers=headers("analyst"), json=payload)
    assert result.status_code == 202
    assert result.json()["analysis_run"]["status"] == "queued"
    missing_versions = client.post(
        url, headers=headers("analyst"), json={**payload, "dataset_versions": {}}
    )
    assert missing_versions.status_code == 422


def test_report_center_is_planner_authored_and_artifact_is_hash_addressed() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    url = "/api/v1/cities/fixture-city/reports"
    payload = {
        "report_type": "data_quality",
        "title": "データ品質レポート",
        "data_classification": "internal",
    }
    assert client.post(url, headers=headers("analyst"), json=payload).status_code == 403
    created = client.post(url, headers=headers("planner"), json=payload)
    assert created.status_code == 201
    assert created.json()["id"] == REPORT_ID

    artifact = client.get(f"/api/v1/reports/{REPORT_ID}/artifact", headers=headers("viewer"))
    assert artifact.status_code == 200
    assert artifact.headers["etag"] == f'"{"a" * 64}"'
    assert artifact.headers["x-citygap-data-classification"] == "internal"
    assert artifact.json()["claim_boundary"] == "human decision required"

    public_export = client.post(
        f"/api/v1/reports/{REPORT_ID}/exports",
        headers=headers("planner"),
        json={"export_scope": "public"},
    )
    assert public_export.status_code == 422
    internal_export = client.post(
        f"/api/v1/reports/{REPORT_ID}/exports",
        headers=headers("planner"),
        json={"export_scope": "internal"},
    )
    assert internal_export.status_code == 201


def test_evidence_library_is_tenant_scoped() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    result = client.get("/api/v1/cities/fixture-city/evidence", headers=headers("viewer"))
    assert result.status_code == 200
    assert result.json()["reports"][0]["id"] == REPORT_ID
    outside_tenant = client.get(
        "/api/v1/cities/fixture-city/evidence", headers=headers("viewer", ORG_B)
    )
    assert outside_tenant.status_code == 404


def test_job_operations_are_visible_to_data_manager_but_mutated_only_by_admin() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    assert client.get("/api/v1/jobs", headers=headers("viewer")).status_code == 403
    listed = client.get("/api/v1/jobs", headers=headers("data_manager"))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == JOB_ID

    operation = {
        "action": "cancel",
        "expected_state": "queued",
        "reason": "入力versionを再確認する",
        "cancel_confirmation": "cancel",
    }
    url = f"/api/v1/jobs/{JOB_ID}/operations"
    assert client.post(url, headers=headers("data_manager"), json=operation).status_code == 403
    cancelled = client.post(url, headers=headers("administrator"), json=operation)
    assert cancelled.status_code == 200
    assert cancelled.json()["effective_state"] == "cancelled"

    missing_confirmation = client.post(
        url,
        headers=headers("administrator"),
        json={**operation, "cancel_confirmation": None},
    )
    assert missing_confirmation.status_code == 422


def test_metrics_are_admin_only_and_use_bounded_service_labels() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    assert client.get("/api/v1/metrics", headers=headers("data_manager")).status_code == 403
    metrics = client.get("/api/v1/metrics", headers=headers("administrator"))
    assert metrics.status_code == 200
    assert metrics.headers["content-type"].startswith("text/plain")
    assert "citygap_http_requests_total" in metrics.text
    assert 'citygap_jobs{state="queued"} 1' in metrics.text
    assert ORG_A not in metrics.text


def test_immutable_audit_api_is_admin_only_and_tenant_scoped() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    assert client.get("/api/v1/audit-events", headers=headers("data_manager")).status_code == 403
    response = client.get(
        "/api/v1/audit-events?action=finding.create&actor=fixture-administrator",
        headers=headers("administrator"),
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["action"] == "finding.create"
    assert (
        client.get(
            "/api/v1/audit-events?occurred_from=2026-08-28T12:00:00",
            headers=headers("administrator"),
        ).status_code
        == 422
    )


def test_support_bundle_excludes_secret_and_attachment_content() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    assert client.get("/api/v1/support-bundle", headers=headers("data_manager")).status_code == 403
    response = client.get(
        "/api/v1/support-bundle",
        headers={**headers("administrator"), "X-Request-ID": "support-request"},
    )
    assert response.status_code == 200
    assert response.json()["request_id"] == "support-request"
    assert "tokens" in response.json()["excluded"]
    assert "backups" not in response.json()


def test_municipal_deployment_surface_blocks_legacy_tenant_unsafe_paths(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    assert client.get("/cities", headers=headers("administrator")).status_code == 404
    assert client.get("/jobs/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/v1/cities", headers=headers("viewer")).status_code == 200
    assert client.get("/health").status_code == 200
    schema = client.get("/openapi.json", headers=headers("viewer")).json()
    assert "/api/v1/cities" in schema["paths"]
    assert "/cities" not in schema["paths"]


def test_admin_and_data_manager_own_explicit_onboarding_lifecycle() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    city_payload = {
        "city_code": "99999",
        "city_key": "new-city",
        "name": "新規市",
        "prefecture_code": "99",
        "prefecture_name": "検証県",
        "analysis_crs": "EPSG:6674",
    }
    assert (
        client.post("/api/v1/cities", headers=headers("viewer"), json=city_payload).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/cities", headers=headers("administrator"), json=city_payload
        ).status_code
        == 201
    )
    dataset_payload = {
        "dataset_key": "plateau-2026",
        "title": "PLATEAU 2026",
        "provider": "Project PLATEAU",
        "dataset_category": "plateau",
        "data_classification": "public",
        "version_key": "2026-v1",
        "dataset_year": 2026,
        "data_format": "CityGML",
    }
    dataset_url = "/api/v1/cities/fixture-city/datasets"
    assert (
        client.post(dataset_url, headers=headers("planner"), json=dataset_payload).status_code
        == 403
    )
    registered = client.post(dataset_url, headers=headers("data_manager"), json=dataset_payload)
    assert registered.status_code == 201
    assert registered.json()["version"]["service_status"] == "registered"

    state_payload = {
        "state_key": "observed-2026",
        "label": "2026年度都市状態",
        "effective_date": "2026-01-01",
        "state_type": "observed",
        "primary_dataset_version_id": VERSION_ID,
        "source_verified": True,
    }
    state_url = "/api/v1/cities/fixture-city/urban-states"
    assert client.post(state_url, headers=headers("analyst"), json=state_payload).status_code == 403
    state = client.post(state_url, headers=headers("data_manager"), json=state_payload)
    assert state.status_code == 201
    transition = client.patch(
        f"/api/v1/urban-states/{STATE_ID}/status",
        headers=headers("data_manager"),
        json={
            "expected_status": "draft",
            "proposed_status": "validated",
            "note": "出典と品質を確認",
        },
    )
    assert transition.status_code == 200
    assert transition.json()["lifecycle_status"] == "validated"


def test_annual_update_queues_version_diff_without_mutating_previous_records() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    url = "/api/v1/cities/fixture-city/annual-updates"
    payload = {
        "from_urban_state_id": STATE_ID,
        "to_urban_state_id": NEXT_STATE_ID,
        "algorithm_version": "citygap-state-diff@1.0.0",
    }
    assert client.post(url, headers=headers("analyst"), json=payload).status_code == 403
    response = client.post(url, headers=headers("data_manager"), json=payload)
    assert response.status_code == 202
    assert response.json()["job"]["state"] == "queued"
    assert response.json()["previous_records"]["changed_by_this_request"] is False
    listed = client.get(url, headers=headers("viewer"))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["to_urban_state_id"] == NEXT_STATE_ID

    same_state = client.post(
        url,
        headers=headers("data_manager"),
        json={**payload, "to_urban_state_id": STATE_ID},
    )
    assert same_state.status_code == 422


def test_saved_view_share_token_still_requires_tenant_membership() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    url = f"/api/v1/saved-views/{SHARE_TOKEN}"
    shared = client.get(url, headers=headers("viewer"))
    assert shared.status_code == 200
    assert shared.json()["investigation_id"] == INVESTIGATION_ID
    assert client.get(url, headers=headers("viewer", ORG_B)).status_code == 404
    assert (
        client.get("/api/v1/saved-views/not-a-token", headers=headers("viewer")).status_code == 404
    )


def test_scenario_clone_is_a_draft_action_and_remains_tenant_scoped() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    url = f"/api/v1/scenarios/{SCENARIO_A}/clone"
    assert client.post(url, headers=headers("viewer"), json={"title": "複製"}).status_code == 403
    cloned = client.post(url, headers=headers("analyst"), json={"title": "比較用の複製"})
    assert cloned.status_code == 201
    assert cloned.json()["parent_scenario_run_id"] == SCENARIO_A
    assert cloned.json()["lifecycle_status"] == "draft"
    assert (
        client.post(url, headers=headers("analyst", ORG_B), json={"title": "越境"}).status_code
        == 404
    )


def test_non_secret_configuration_and_retention_boundaries_are_admin_controlled() -> None:
    client = TestClient(create_app(MunicipalRepository()))  # type: ignore[arg-type]
    settings_url = "/api/v1/organizations/current/settings"
    assert client.get(settings_url, headers=headers("viewer")).status_code == 403
    settings = client.get(settings_url, headers=headers("data_manager"))
    assert settings.status_code == 200
    assert "timezone" in settings.json()["allowed_config_keys"]
    assert settings.json()["boundaries"]["legal_hold"] == "not implemented"

    config_url = "/api/v1/organizations/current/configuration/timezone"
    body = {
        "expected_updated_at": None,
        "config_value": "Asia/Tokyo",
        "note": "自治体運用時刻を確認",
    }
    assert client.patch(config_url, headers=headers("data_manager"), json=body).status_code == 403
    updated = client.patch(config_url, headers=headers("administrator"), json=body)
    assert updated.status_code == 200
    assert updated.json()["config_value"] == "Asia/Tokyo"
    assert (
        client.patch(
            "/api/v1/organizations/current/configuration/unsupported",
            headers=headers("administrator"),
            json=body,
        ).status_code
        == 422
    )
    assert (
        client.patch(
            config_url,
            headers=headers("administrator"),
            json={**body, "config_value": {"api_token": "must-not-be-stored"}},
        ).status_code
        == 422
    )

    retention_url = "/api/v1/organizations/current/retention-policies/audit"
    retention = client.patch(
        retention_url,
        headers=headers("administrator"),
        json={
            "expected_retention_days": None,
            "proposed_retention_days": 3650,
            "legal_hold_supported": False,
            "note": "条例・庁内規程の確認前の設定記録",
        },
    )
    assert retention.status_code == 200
    assert retention.json()["enforcement_enabled"] is False
    unsupported_hold = client.patch(
        retention_url,
        headers=headers("administrator"),
        json={
            "expected_retention_days": 3650,
            "proposed_retention_days": 3650,
            "legal_hold_supported": True,
            "note": "未実装境界",
        },
    )
    assert unsupported_hold.status_code == 422
