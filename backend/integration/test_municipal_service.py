from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.api.service_repository import MunicipalServiceRepository
from backend.citygap_platform.security.auth import DEFAULT_ORGANIZATION_ID

ORG_A = DEFAULT_ORGANIZATION_ID
ORG_B = "00000000-0000-0000-0000-0000000000b2"
CITY_B = "00000000-0000-0000-0000-0000000000c2"


def _headers(role: str, organization_id: str = ORG_A) -> dict[str, str]:
    return {
        "X-CITYGAP-Actor": f"acceptance-{role}",
        "X-CITYGAP-Roles": role,
        "X-CITYGAP-Organization": organization_id,
    }


def _prepare_service_fixture(database_url: str) -> str:
    import psycopg

    with psycopg.connect(database_url) as connection:
        city_id = connection.execute("SELECT id FROM cities WHERE city_key = 'maizuru'").fetchone()[
            0
        ]
        plateau_version_id = connection.execute(
            """SELECT id FROM city_dataset_versions
               WHERE city_id = '26202' ORDER BY dataset_year DESC LIMIT 1"""
        ).fetchone()[0]
        registry_version_id = connection.execute(
            """UPDATE dataset_versions
               SET lifecycle_status = 'available', quality_status = 'passed',
                   analysis_ready = true, service_status = 'promoted'
               WHERE id = '10000000-0000-0000-0000-000000000002'
               RETURNING id"""
        ).fetchone()[0]
        state_id = connection.execute(
            """INSERT INTO urban_states (
                   city_id, state_key, label, effective_date, state_type,
                   lifecycle_status, primary_plateau_dataset_version_id,
                   source_verified, validation_report, validated_at,
                   organization_id
               ) VALUES (
                   %s, 'acceptance-observed-2025', '舞鶴市 2025 acceptance state',
                   '2025-01-01', 'observed', 'validated', %s, true,
                   '{"acceptance_fixture":true}', now(), %s
               ) ON CONFLICT (city_id, state_key) DO UPDATE
                   SET validation_report = EXCLUDED.validation_report
               RETURNING id""",
            (city_id, plateau_version_id, ORG_A),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO state_dataset_versions (
                   organization_id, urban_state_id, dataset_role, dataset_version_id,
                   source_verified, metadata
               ) VALUES (%s, %s, 'plateau', %s, true, '{"acceptance_fixture":true}')
               ON CONFLICT DO NOTHING""",
            (ORG_A, state_id, registry_version_id),
        )
        connection.execute(
            """INSERT INTO organizations (
                   id, organization_key, name, organization_type
               ) VALUES (%s, 'acceptance-org-b', '分離検証組織B', 'municipality')
               ON CONFLICT (id) DO NOTHING""",
            (ORG_B,),
        )
        connection.execute(
            """INSERT INTO cities (
                   id, city_code, city_key, name, prefecture_code,
                   prefecture_name, analysis_crs, organization_id, service_status
               ) VALUES (%s, '99992', 'acceptance-city-b', '分離検証市B',
                         '99', '分離検証県', 'EPSG:6674', %s, 'active')
               ON CONFLICT (id) DO NOTHING""",
            (CITY_B, ORG_B),
        )
    return str(state_id)


def test_role_based_finding_to_human_decision_acceptance(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_id = _prepare_service_fixture(database_url)
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalServiceRepository(database_url)))

    finding_payload = {
        "finding_type": "accessibility_gap",
        "title": "実データに基づく追加調査候補",
        "summary": "政策判断ではなく、庁内確認へ進める候補",
        "urban_state_id": state_id,
    }
    finding_response = client.post(
        "/api/v1/cities/maizuru/findings",
        headers=_headers("analyst"),
        json=finding_payload,
    )
    assert finding_response.status_code == 201, finding_response.text
    finding_id = finding_response.json()["id"]
    assert (
        client.patch(
            f"/api/v1/findings/{finding_id}/status",
            headers=_headers("analyst"),
            json={"expected_status": "new", "proposed_status": "triaged"},
        ).status_code
        == 200
    )

    investigation_response = client.post(
        "/api/v1/cities/maizuru/investigations",
        headers=_headers("analyst"),
        json={
            "urban_state_id": state_id,
            "title": "候補地点の庁内・現地調査",
            "objective": "出典と空間条件を確認し、人が判断を記録する",
            "finding_ids": [finding_id],
            "spatial_state": {"layers": ["plateau_buildings"]},
        },
    )
    assert investigation_response.status_code == 201, investigation_response.text
    investigation_id = investigation_response.json()["id"]

    assert (
        client.post(
            f"/api/v1/investigations/{investigation_id}/reviews",
            headers=_headers("analyst"),
            json={"request_note": "review権限境界"},
        ).status_code
        == 403
    )
    review_response = client.post(
        f"/api/v1/investigations/{investigation_id}/reviews",
        headers=_headers("planner"),
        json={"request_note": "出典・限界・現地確認項目をレビュー"},
    )
    assert review_response.status_code == 201, review_response.text
    review_id = review_response.json()["id"]
    for expected, proposed, note in (
        ("requested", "in_review", ""),
        ("in_review", "reviewed", "出典とclaim boundaryを確認"),
    ):
        response = client.patch(
            f"/api/v1/reviews/{review_id}/status",
            headers=_headers("planner"),
            json={
                "expected_status": expected,
                "proposed_status": proposed,
                "review_note": note,
            },
        )
        assert response.status_code == 200, response.text

    evidence_response = client.post(
        "/api/v1/cities/maizuru/evidence-centers",
        headers=_headers("planner"),
        json={
            "investigation_id": investigation_id,
            "source_manifest": {
                "sources": [
                    {
                        "dataset_version_id": "10000000-0000-0000-0000-000000000002",
                        "data_classification": "internal",
                    }
                ]
            },
            "algorithm_manifest": {"workflow": "human-reviewed-investigation"},
            "validation_manifest": {"review_request_id": review_id},
            "data_classification": "internal",
        },
    )
    assert evidence_response.status_code == 201, evidence_response.text
    evidence_id = evidence_response.json()["id"]

    field_response = client.post(
        f"/api/v1/investigations/{investigation_id}/field-observations",
        headers=_headers("field_staff"),
        json={
            "observation_type": "access_check",
            "notes": "現地で接続状況を確認",
            "observed_at": "2026-08-28T12:00:00+09:00",
            "longitude": 135.32,
            "latitude": 35.46,
        },
    )
    assert field_response.status_code == 201, field_response.text
    assert (
        client.patch(
            f"/api/v1/investigations/{investigation_id}/status",
            headers=_headers("planner"),
            json={
                "expected_status": "field_check",
                "proposed_status": "decision_pending",
                "note": "現地記録を確認",
            },
        ).status_code
        == 200
    )

    decision_payload = {
        "review_request_id": review_id,
        "decision": "additional_investigation",
        "reason": "確認範囲を広げる必要がある",
        "related_evidence_ids": [evidence_id],
    }
    assert (
        client.post(
            f"/api/v1/investigations/{investigation_id}/decisions",
            headers=_headers("field_staff"),
            json=decision_payload,
        ).status_code
        == 403
    )
    decision_response = client.post(
        f"/api/v1/investigations/{investigation_id}/decisions",
        headers=_headers("planner"),
        json=decision_payload,
    )
    assert decision_response.status_code == 201, decision_response.text
    assert decision_response.json()["source"] == "human_entry"
    assert decision_response.json()["optimizer_generated"] is False

    case = client.get(f"/api/v1/investigations/{investigation_id}", headers=_headers("viewer"))
    assert case.status_code == 200
    assert case.json()["investigation"]["status"] == "closed"
    assert len(case.json()["field_observations"]) == 1
    assert len(case.json()["decisions"]) == 1


def test_organization_a_b_isolation_for_api_and_database_constraints(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_service_fixture(database_url)
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalServiceRepository(database_url)))

    org_b_cities = client.get("/api/v1/cities", headers=_headers("viewer", ORG_B))
    assert org_b_cities.status_code == 200
    assert [item["city_key"] for item in org_b_cities.json()["items"]] == ["acceptance-city-b"]
    assert (
        client.get("/api/v1/cities/maizuru/home", headers=_headers("viewer", ORG_B)).status_code
        == 404
    )
    search = client.get(
        "/api/v1/search?q=%E8%BF%BD%E5%8A%A0%E8%AA%BF%E6%9F%BB",
        headers=_headers("viewer", ORG_B),
    )
    assert search.status_code == 200
    assert search.json()["items"] == []
    assert client.get("/cities", headers=_headers("administrator", ORG_B)).status_code == 404

    import psycopg

    with psycopg.connect(database_url) as connection:
        city_a = connection.execute("SELECT id FROM cities WHERE city_key = 'maizuru'").fetchone()[
            0
        ]
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            connection.execute(
                """INSERT INTO attachment_objects (
                       id, organization_id, city_id, storage_provider, object_key,
                       original_file_name, content_type, size_bytes, sha256,
                       data_classification, created_by
                   ) VALUES (%s, %s, %s, 'local', 'cross-tenant/forbidden',
                             'forbidden.pdf', 'application/pdf', 1, repeat('a', 64),
                             'restricted', 'isolation-test')""",
                (str(uuid.uuid4()), ORG_B, city_a),
            )
        connection.rollback()

    membership = client.post(
        "/api/v1/organizations/current/memberships",
        headers=_headers("administrator", ORG_B),
        json={
            "issuer": "https://identity.integration.example",
            "subject": "org-b-admin",
            "display_name": "組織B管理者",
            "email": "org-b-admin@example.jp",
            "role": "administrator",
        },
    )
    assert membership.status_code == 201, membership.text
    user_id = membership.json()["user_id"]
    org_b_members = client.get(
        "/api/v1/organizations/current/memberships",
        headers=_headers("administrator", ORG_B),
    )
    assert any(item["subject"] == "org-b-admin" for item in org_b_members.json()["items"])
    org_a_members = client.get(
        "/api/v1/organizations/current/memberships", headers=_headers("administrator")
    )
    assert all(item["subject"] != "org-b-admin" for item in org_a_members.json()["items"])
    org_a_setting = client.patch(
        "/api/v1/organizations/current/configuration/timezone",
        headers=_headers("administrator"),
        json={
            "expected_updated_at": None,
            "config_value": "Asia/Tokyo",
            "note": "Organization A timezone",
        },
    )
    assert org_a_setting.status_code == 200, org_a_setting.text
    org_b_settings = client.get(
        "/api/v1/organizations/current/settings",
        headers=_headers("data_manager", ORG_B),
    )
    assert org_b_settings.status_code == 200
    assert all(item["config_key"] != "timezone" for item in org_b_settings.json()["configuration"])
    org_b_retention = client.patch(
        "/api/v1/organizations/current/retention-policies/attachment",
        headers=_headers("administrator", ORG_B),
        json={
            "expected_retention_days": None,
            "proposed_retention_days": 365,
            "legal_hold_supported": False,
            "note": "policy record only",
        },
    )
    assert org_b_retention.status_code == 200, org_b_retention.text
    assert org_b_retention.json()["enforcement_enabled"] is False
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """INSERT INTO service_metric_samples (
                   organization_id, metric_name, metric_value, labels
               ) VALUES (%s, 'api_error', 2, '{}'), (%s, 'api_error', 900, '{}')""",
            (ORG_A, ORG_B),
        )
    org_a_metrics = client.get("/api/v1/metrics", headers=_headers("administrator"))
    assert org_a_metrics.status_code == 200
    assert "citygap_service_api_error_count 1" in org_a_metrics.text
    assert "citygap_service_api_error_sum 2" in org_a_metrics.text
    last_admin = client.patch(
        f"/api/v1/organizations/current/memberships/{user_id}/administrator",
        headers=_headers("administrator", ORG_B),
        json={
            "expected_active": True,
            "proposed_active": False,
            "note": "last administrator guard integration",
        },
    )
    assert last_admin.status_code == 409


def test_annual_data_update_preserves_previous_investigation_and_versions(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous_state_id = _prepare_service_fixture(database_url)
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalServiceRepository(database_url)))
    suffix = uuid.uuid4().hex[:10]

    investigation = client.post(
        "/api/v1/cities/maizuru/investigations",
        headers=_headers("analyst"),
        json={
            "urban_state_id": previous_state_id,
            "title": f"年次更新前の再現性記録 {suffix}",
            "objective": "新年度データ登録後も旧Urban State参照を保持する",
            "spatial_state": {"urban_state_id": previous_state_id},
        },
    )
    assert investigation.status_code == 201, investigation.text
    investigation_id = investigation.json()["id"]
    saved_view = client.post(
        f"/api/v1/investigations/{investigation_id}/saved-views",
        headers=_headers("analyst"),
        json={
            "title": f"年次更新前の空間状態 {suffix}",
            "spatial_state": {
                "urban_state_id": previous_state_id,
                "viewport": {"longitude": 135.33, "latitude": 35.47, "zoom": 13},
                "layers": ["investigation_entities"],
            },
            "data_classification": "internal",
        },
    )
    assert saved_view.status_code == 201, saved_view.text
    share_token = saved_view.json()["share_token"]
    assert (
        client.get(f"/api/v1/saved-views/{share_token}", headers=_headers("viewer")).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/saved-views/{share_token}", headers=_headers("viewer", ORG_B)
        ).status_code
        == 404
    )

    registered = client.post(
        "/api/v1/cities/maizuru/datasets",
        headers=_headers("data_manager"),
        json={
            "dataset_key": f"annual-plateau-{suffix}",
            "title": f"年次更新検証 PLATEAU {suffix}",
            "provider": "Project PLATEAU public source metadata",
            "dataset_category": "plateau",
            "data_classification": "public",
            "version_key": f"2027-{suffix}",
            "dataset_year": 2027,
            "data_format": "CityGML",
            "source_url": "https://www.geospatial.jp/ckan/dataset/plateau",
            "license": "source metadata only; fixture bytes are not substituted",
            "declared_source_crs": "EPSG:6697",
        },
    )
    assert registered.status_code == 201, registered.text
    version_id = registered.json()["version"]["id"]

    # Actual ingestion and quality checks are worker/operator responsibilities.  The
    # integration fixture marks their verified outcome explicitly, then exercises
    # the service promotion gate rather than pretending the upload itself promoted.
    import psycopg

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """UPDATE dataset_versions
               SET lifecycle_status = 'available', quality_status = 'passed',
                   analysis_ready = true, service_status = 'analysis_ready',
                   verification_status = 'fixture_worker_verified'
               WHERE organization_id = %s AND id = %s""",
            (ORG_A, version_id),
        )
        connection.execute(
            """INSERT INTO dataset_quality_checks (
                   organization_id, dataset_version_id, check_key, status,
                   observed_value, explanation
               ) VALUES (%s, %s, 'feature_count', 'passed',
                         '{"fixture":true}',
                         'PostGIS integration fixture explicitly completed the worker gate')""",
            (ORG_A, version_id),
        )

    promoted = client.patch(
        f"/api/v1/dataset-versions/{version_id}/status",
        headers=_headers("data_manager"),
        json={
            "expected_status": "analysis_ready",
            "proposed_status": "promoted",
            "note": "PostGIS品質ゲート結果を確認",
        },
    )
    assert promoted.status_code == 200, promoted.text

    state = client.post(
        "/api/v1/cities/maizuru/urban-states",
        headers=_headers("data_manager"),
        json={
            "state_key": f"annual-observed-2027-{suffix}",
            "label": f"舞鶴市 2027 年次更新 {suffix}",
            "effective_date": "2027-01-01",
            "state_type": "observed",
            "primary_dataset_version_id": version_id,
            "source_verified": True,
        },
    )
    assert state.status_code == 201, state.text
    next_state_id = state.json()["id"]
    assert (
        client.patch(
            f"/api/v1/urban-states/{next_state_id}/status",
            headers=_headers("data_manager"),
            json={
                "expected_status": "draft",
                "proposed_status": "validated",
                "note": "公開出典と品質ゲートを確認",
            },
        ).status_code
        == 200
    )

    update_payload = {
        "from_urban_state_id": previous_state_id,
        "to_urban_state_id": next_state_id,
        "algorithm_version": "citygap-state-diff@1.0.0",
    }
    annual = client.post(
        "/api/v1/cities/maizuru/annual-updates",
        headers=_headers("data_manager"),
        json=update_payload,
    )
    assert annual.status_code == 202, annual.text
    result = annual.json()
    assert result["created"] is True
    assert result["job"]["state"] == "queued"
    assert result["previous_records"]["investigations"] >= 1
    assert result["previous_records"]["changed_by_this_request"] is False
    assert version_id in result["contract"]["dataset_version_ids"]

    repeated = client.post(
        "/api/v1/cities/maizuru/annual-updates",
        headers=_headers("data_manager"),
        json=update_payload,
    )
    assert repeated.status_code == 202
    assert repeated.json()["created"] is False
    assert repeated.json()["job"]["id"] == result["job"]["id"]

    previous = client.get(f"/api/v1/investigations/{investigation_id}", headers=_headers("viewer"))
    assert previous.status_code == 200
    assert str(previous.json()["investigation"]["urban_state_id"]) == previous_state_id
    assert (
        client.get(
            "/api/v1/cities/maizuru/annual-updates",
            headers=_headers("viewer", ORG_B),
        ).status_code
        == 404
    )


def test_scenario_clone_preserves_computed_result_and_resets_human_checks(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_service_fixture(database_url)
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalServiceRepository(database_url)))
    import psycopg

    with psycopg.connect(database_url) as connection:
        parent_id, parent_sites = connection.execute(
            """SELECT scenario.id, count(site.site_order)
               FROM scenario_runs AS scenario
               JOIN scenario_sites AS site ON site.scenario_run_id = scenario.id
               WHERE scenario.organization_id = %s
               GROUP BY scenario.id ORDER BY scenario.id LIMIT 1""",
            (ORG_A,),
        ).fetchone()

    clone = client.post(
        f"/api/v1/scenarios/{parent_id}/clone",
        headers=_headers("analyst"),
        json={"title": "自治体比較用clone"},
    )
    assert clone.status_code == 201, clone.text
    cloned_id = clone.json()["id"]
    assert str(clone.json()["parent_scenario_run_id"]) == str(parent_id)
    assert clone.json()["lifecycle_status"] == "draft"
    assert clone.json()["review_status"] == "not_requested"
    assert (
        client.post(
            f"/api/v1/scenarios/{parent_id}/clone",
            headers=_headers("analyst", ORG_B),
            json={"title": "越境clone"},
        ).status_code
        == 404
    )

    with psycopg.connect(database_url) as connection:
        cloned_sites = connection.execute(
            "SELECT count(*) FROM scenario_sites WHERE scenario_run_id = %s", (cloned_id,)
        ).fetchone()[0]
        checks = connection.execute(
            """SELECT count(*), bool_and(
                   site_access = 'unknown' AND road_safety = 'unknown'
                   AND hazard_confirmation = 'unknown' AND notes = ''
               ) FROM scenario_field_checks WHERE scenario_run_id = %s""",
            (cloned_id,),
        ).fetchone()
    assert cloned_sites == parent_sites
    assert checks == (parent_sites, True)
