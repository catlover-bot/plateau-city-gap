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


def _ensure_open_data_record(database_url: str) -> dict[str, object]:
    import psycopg

    _prepare_service_fixture(database_url)
    suffix = uuid.uuid4().hex
    raw_sha = (suffix * 2)[:64]
    with psycopg.connect(database_url) as connection:
        city_id = connection.execute(
            "SELECT id FROM cities WHERE organization_id = %s AND city_key = 'maizuru'",
            (ORG_A,),
        ).fetchone()[0]
        source_id = connection.execute(
            """SELECT id FROM city_open_data_sources
               WHERE organization_id = %s AND city_id = %s ORDER BY id LIMIT 1""",
            (ORG_A, city_id),
        ).fetchone()[0]
        dataset_id = str(uuid.uuid4())
        connection.execute(
            """INSERT INTO datasets (
                   id, organization_id, city_id, dataset_key, title, provider,
                   data_classification, dataset_category
               ) VALUES (%s, %s, %s, %s, 'review loop fixture', 'official fixture',
                         'public', 'facilities')""",
            (dataset_id, ORG_A, city_id, f"review-loop-{suffix}"),
        )
        version_id = str(uuid.uuid4())
        connection.execute(
            """INSERT INTO dataset_versions (
                   id, organization_id, dataset_id, version_key, dataset_year, data_format,
                   source_url, license, declared_source_crs, verification_status,
                   registered_at, data_classification
               ) VALUES (%s, %s, %s, %s, 2026, 'CSV', %s, 'CC BY 4.0',
                         'EPSG:4326', 'checksum_verified', now(), 'public')""",
            (
                version_id,
                ORG_A,
                dataset_id,
                f"2026-{suffix}",
                f"https://data.bodik.jp/dataset/{suffix}",
            ),
        )
        blob_id = connection.execute(
            """INSERT INTO open_data_raw_blobs (
                   owner_organization_id, sha256, size_bytes, content_type,
                   storage_provider, object_key, reuse_scope, first_retrieved_at
               ) VALUES (NULL, %s, 32, 'text/csv', 'local', %s,
                         'public_verified', now()) RETURNING id""",
            (raw_sha, f"sha256/{raw_sha[:2]}/{raw_sha}"),
        ).fetchone()[0]
        resource_id = connection.execute(
            """INSERT INTO open_data_resources (
                   organization_id, city_source_id, dataset_version_id, raw_blob_id,
                   external_resource_id, resource_title, resource_url, format,
                   content_length, raw_checksum, retrieved_at, adapter_version
               ) VALUES (%s, %s, %s, %s, %s, 'review loop resource', %s,
                         'CSV', 32, %s, now(), 'ckan-v3@1') RETURNING id""",
            (
                ORG_A,
                source_id,
                version_id,
                blob_id,
                f"review-loop-{suffix}",
                f"https://data.bodik.jp/resource/{suffix}.csv",
                raw_sha,
            ),
        ).fetchone()[0]
        transformation_id = connection.execute(
            """INSERT INTO open_data_transformation_runs (
                   organization_id, resource_id, adapter_id, adapter_version,
                   transformation_version, canonical_version, status,
                   input_row_count, output_record_count, completed_at, metadata
               ) VALUES (%s, %s, 'ckan-v3@1', '1', 'review-loop@1',
                         'canonical@1', 'succeeded', 1, 1, now(), '{}') RETURNING id""",
            (ORG_A, resource_id),
        ).fetchone()[0]
        external_record_id = f"facility-{suffix}"
        record_id = connection.execute(
            """INSERT INTO canonical_open_data_records (
                   organization_id, city_id, dataset_version_id, source_resource_id,
                   transformation_run_id, record_type, external_record_id,
                   display_name, source_row_locator, reference_date, attributes, geom
               ) VALUES (%s, %s, %s, %s, %s, 'facility', %s,
                         'review loop facility', 'row:1', '2026-01-01',
                         '{"official":true}',
                         ST_SetSRID(ST_MakePoint(135.32, 35.46), 4326)) RETURNING id""",
            (
                ORG_A,
                city_id,
                version_id,
                resource_id,
                transformation_id,
                external_record_id,
            ),
        ).fetchone()[0]
    return {
        "city_id": city_id,
        "source_id": source_id,
        "dataset_version_id": version_id,
        "blob_id": blob_id,
        "resource_id": resource_id,
        "record_id": record_id,
        "external_record_id": external_record_id,
        "raw_sha": raw_sha,
    }


def test_role_based_finding_to_human_decision_acceptance(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_id = _prepare_service_fixture(database_url)
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalServiceRepository(database_url)))

    catalog_response = client.get("/api/v1/analysis-definitions", headers=_headers("analyst"))
    assert catalog_response.status_code == 200, catalog_response.text
    catalog = {item["id"]: item for item in catalog_response.json()["items"]}
    assert len(catalog) == 12
    assert {
        requirement["requirement_level"]
        for requirement in catalog["care-access"]["dataset_requirements"]
    } == {"required", "optional", "enhancement"}

    finding_payload = {
        "finding_type": "care_access_review_candidate",
        "title": "実データに基づく介護アクセス追加調査候補",
        "summary": "介護不足の認定や政策判断ではなく、庁内確認へ進める候補",
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

    import psycopg

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """INSERT INTO investigation_entities (
                   organization_id, investigation_id, entity_type, entity_id, label,
                   geometry, source, source_year, attributes, evidence, added_by
               ) VALUES (
                   %s, %s, 'mesh', '533513381', '検証500mメッシュ',
                   ST_SetSRID(ST_MakePoint(135.32, 35.46), 4326),
                   'e-Stat T001192', 2020, '{"fixture":true}',
                   '[{"statistics_id":"T001192"}]', 'acceptance-analyst'
               )""",
            (ORG_A, investigation_id),
        )

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
    assert any(
        item["source_title"] == "e-Stat T001192" and item["reference_period"] == "2020"
        for item in case.json()["source_timeline"]
    )
    assert case.json()["source_contributions"][0]["entity_id"] == "533513381"
    assert case.json()["source_contributions"][0]["contribution_role"] == (
        "investigation_entity_source"
    )


def test_data_hub_v2_exposes_coverage_lineage_without_automatic_truth_selection(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_service_fixture(database_url)
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalServiceRepository(database_url)))

    hub_response = client.get("/api/v1/cities/maizuru/data-hub", headers=_headers("viewer"))
    assert hub_response.status_code == 200, hub_response.text
    hub = hub_response.json()
    assert hub["coverage_summary"]["total"] >= 20
    assert hub["coverage_summary"]["gaps"] >= 3
    coverage = {item["dataset_family"]: item for item in hub["coverage"]}
    assert coverage["plateau_buildings"]["status"] == "available"
    assert coverage["mhlw_medical"]["status"] == "partial"
    assert coverage["official_pedestrian_network"] == {
        **coverage["official_pedestrian_network"],
        "status": "unavailable",
        "unavailable_reason": "outside_coverage",
    }
    assert coverage["gtfs"]["unavailable_reason"] == "not_published"
    assert coverage["social_participation"]["status"] == "unavailable"
    assert coverage["social_participation"]["unavailable_reason"] == "outside_coverage"
    assert coverage["welfare"]["status"] == "requires_review"
    assert coverage["station_usage"]["temporal_alignment"] == "stale"
    assert coverage["mobility"]["unavailable_reason"] == "not_verified"
    assert any(
        item["dataset_family"] == "mhlw_medical" and item["effect"] == "BASE"
        for item in hub["missing_data"]
    )
    assert any(
        item["dataset_family"] == "official_pedestrian_network" and item["effect"] == "BASE"
        for item in hub["missing_data"]
    )
    assert [item["reference_period"] for item in hub["source_timeline"]] == [
        "2020-10-01",
        "2020 model",
        "2021-06-01",
        "2021",
        "2022",
        "2023/2024 occurrence dates in 2024 annual file",
        "2025 release",
        "2025 / 2050 / 2070 projections (R6 2024 production)",
        "2026-03 catalog",
        "2026-03 catalog",
        "2026-06-01",
        "2026-06-30",
        "2026-06-30",
    ]
    comparison = hub["comparisons"][0]
    assert comparison["automatic_selection"] is False
    assert comparison["dimensions"]["record_counts"] == {"p04_2020": 105, "mhlw_2026": 83}
    assert comparison["dimensions"]["identity"]["ambiguous"] == 18
    assert hub["conflicts"][0]["automatic_truth_selection"] is False
    assert hub["conflicts"][0]["status"] == "unresolved"
    assert all("score" not in item for item in hub["coverage"])

    sources = client.get("/api/v1/cities/maizuru/sources", headers=_headers("viewer"))
    assert sources.status_code == 200
    assert any(item["title"].startswith("医療情報ネット") for item in sources.json()["items"])
    timeline = client.get("/api/v1/cities/maizuru/source-timeline", headers=_headers("viewer"))
    assert timeline.status_code == 200
    assert len(timeline.json()["items"]) == 13
    assert (
        client.get(
            "/api/v1/cities/maizuru/data-coverage", headers=_headers("viewer", ORG_B)
        ).status_code
        == 404
    )

    search = client.get(
        "/api/v1/search?q=%E5%8C%BB%E7%99%82%E6%83%85%E5%A0%B1%E3%83%8D%E3%83%83%E3%83%88",
        headers=_headers("viewer"),
    )
    assert search.status_code == 200
    assert any(item["entity_type"] == "source" for item in search.json()["items"])

    datasets_response = client.get(
        "/api/v1/datasets?city=maizuru&q=PLATEAU", headers=_headers("viewer")
    )
    assert datasets_response.status_code == 200
    datasets = datasets_response.json()["items"]
    assert datasets
    dataset_id = datasets[0]["id"]
    detail = client.get(f"/api/v1/datasets/{dataset_id}", headers=_headers("viewer"))
    assert detail.status_code == 200
    assert detail.json()["versions"]
    lineage = client.get(f"/api/v1/datasets/{dataset_id}/lineage", headers=_headers("viewer"))
    assert lineage.status_code == 200
    assert lineage.json()["automatic_latest_substitution"] is False
    assert lineage.json()["chain"].startswith("raw_blob -> resource -> adapter")


def test_open_data_operator_workflows_are_explicit_versioned_and_tenant_scoped(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_service_fixture(database_url)
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalServiceRepository(database_url)))
    manager = _headers("data_manager")

    discovery = client.post(
        "/api/v1/sources/discover",
        headers=manager,
        json={"city": "maizuru", "source_keys": ["bodik-maizuru"]},
    )
    assert discovery.status_code == 202, discovery.text
    assert discovery.json()["discovery_only"] is True
    assert discovery.json()["automatic_acceptance"] is False
    assert discovery.json()["job"]["job_type"] == "source_discovery"

    hub = client.get("/api/v1/cities/maizuru/data-hub", headers=manager).json()
    source = next(item for item in hub["sources"] if item["source_key"] == "bodik-maizuru")
    metadata = client.post(
        f"/api/v1/sources/{source['id']}/metadata-checks",
        headers=manager,
        json={"reason": "acceptance test approved metadata-only check"},
    )
    assert metadata.status_code == 202, metadata.text
    assert metadata.json()["metadata_only"] is True
    assert metadata.json()["current_promoted_data_retained"] is True
    assert metadata.json()["job"]["job_type"] == "metadata_refresh"
    assert (
        client.post(
            f"/api/v1/sources/{source['id']}/metadata-checks",
            headers=_headers("data_manager", ORG_B),
            json={"reason": "cross-tenant source refresh attempt"},
        ).status_code
        == 404
    )

    suffix = uuid.uuid4().hex[:8]
    registered = client.post(
        "/api/v1/cities/maizuru/datasets",
        headers=manager,
        json={
            "dataset_key": f"operator-flow-{suffix}",
            "title": f"更新運用受入検証 {suffix}",
            "provider": "official source acceptance fixture",
            "dataset_category": "facilities",
            "data_classification": "internal",
            "version_key": f"2026-{suffix}",
            "dataset_year": 2026,
            "data_format": "CSV",
            "source_url": "https://data.bodik.jp/",
            "license": "CC BY 4.0",
            "declared_source_crs": "EPSG:4326",
        },
    )
    assert registered.status_code == 201, registered.text
    dataset_id = registered.json()["dataset"]["id"]
    version_id = registered.json()["version"]["id"]
    validation = client.post(
        f"/api/v1/datasets/{dataset_id}/validate",
        headers=manager,
        json={
            "version_id": version_id,
            "expected_status": "registered",
            "note": "schema, CRS, checksum and licence gates must run",
        },
    )
    assert validation.status_code == 202, validation.text
    assert validation.json()["service_status"] == "validating"
    assert validation.json()["workflow_job"]["job_type"] == "source_validation"
    assert (
        client.post(
            f"/api/v1/datasets/{dataset_id}/validate",
            headers=_headers("data_manager", ORG_B),
            json={
                "version_id": version_id,
                "expected_status": "registered",
                "note": "cross-tenant attempt",
            },
        ).status_code
        == 404
    )

    import psycopg

    raw_sha = (uuid.uuid4().hex * 2)[:64]
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """UPDATE dataset_versions
               SET lifecycle_status = 'available', quality_status = 'passed',
                   analysis_ready = true, service_status = 'analysis_ready'
               WHERE organization_id = %s AND id = %s""",
            (ORG_A, version_id),
        )
        city_id = connection.execute(
            "SELECT id FROM cities WHERE organization_id = %s AND city_key = 'maizuru'",
            (ORG_A,),
        ).fetchone()[0]
        blob_id = connection.execute(
            """INSERT INTO open_data_raw_blobs (
                   owner_organization_id, sha256, size_bytes, content_type,
                   storage_provider, object_key, reuse_scope, first_retrieved_at
               ) VALUES (%s, %s, 18, 'text/csv', 'local', %s, 'tenant_only', now())
               RETURNING id""",
            (ORG_A, raw_sha, f"sha256/{raw_sha[:2]}/{raw_sha}"),
        ).fetchone()[0]
        resource_id = connection.execute(
            """INSERT INTO open_data_resources (
                   organization_id, city_source_id, dataset_version_id, raw_blob_id,
                   external_resource_id, resource_title, resource_url, format,
                   content_length, raw_checksum, retrieved_at, source_crs,
                   source_schema_version, adapter_version
               ) VALUES (%s, %s, %s, %s, %s, 'acceptance resource',
                         'https://data.bodik.jp/dataset/acceptance.csv', 'CSV', 18,
                         %s, now(), 'EPSG:4326', 'acceptance-v1', 'ckan-v3@1')
               RETURNING id""",
            (ORG_A, source["id"], version_id, blob_id, f"resource-{suffix}", raw_sha),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO open_data_resource_processing (
                   organization_id, resource_id, state, status_reason
               ) VALUES (%s, %s, 'canonicalized', 'acceptance fixture')""",
            (ORG_A, resource_id),
        )
        transformation_id = connection.execute(
            """INSERT INTO open_data_transformation_runs (
                   organization_id, resource_id, adapter_id, adapter_version,
                   transformation_version, canonical_version, status,
                   input_row_count, output_record_count, completed_at, metadata
               ) VALUES (%s, %s, 'ckan-v3@1', '1', 'acceptance-transform@1',
                         'canonical@1', 'succeeded', 1, 1, now(), '{}')
               RETURNING id""",
            (ORG_A, resource_id),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO canonical_open_data_records (
                   organization_id, city_id, dataset_version_id, source_resource_id,
                   transformation_run_id, record_type, external_record_id,
                   display_name, source_row_locator, reference_date, attributes, geom
               ) VALUES (%s, %s, %s, %s, %s, 'facility', %s,
                         'acceptance facility', 'row:1', '2026-01-01',
                         '{"acceptance_fixture":true}',
                         ST_SetSRID(ST_MakePoint(135.32, 35.46), 4326))""",
            (ORG_A, city_id, version_id, resource_id, transformation_id, f"facility-{suffix}"),
        )
        promoted_before = connection.execute(
            """SELECT id FROM dataset_versions
               WHERE organization_id = %s AND service_status = 'promoted'
               ORDER BY promoted_at DESC NULLS LAST, id LIMIT 1""",
            (ORG_A,),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO open_data_update_checks (
                   organization_id, city_source_id, result, next_check_after, detail
               ) VALUES (%s, %s, 'failed', now() + interval '7 days',
                         'provider unavailable; keep current promoted version')""",
            (ORG_A, source["id"]),
        )
        promoted_after = connection.execute(
            """SELECT id FROM dataset_versions
               WHERE organization_id = %s AND service_status = 'promoted'
               ORDER BY promoted_at DESC NULLS LAST, id LIMIT 1""",
            (ORG_A,),
        ).fetchone()[0]
        assert promoted_after == promoted_before
        connection.execute(
            """INSERT INTO open_data_update_checks (
                   organization_id, city_source_id, result, observed_checksum,
                   next_check_after, detail
               ) VALUES (%s, %s, 'update_available', %s,
                         now() + interval '7 days', 'new bytes require human review')""",
            (ORG_A, source["id"], (uuid.uuid4().hex * 2)[:64]),
        )

    promoted = client.post(
        f"/api/v1/datasets/{dataset_id}/promote",
        headers=manager,
        json={
            "version_id": version_id,
            "expected_status": "analysis_ready",
            "note": "quality and licence gates explicitly reviewed",
        },
    )
    assert promoted.status_code == 202, promoted.text
    assert promoted.json()["service_status"] == "promoted"
    assert promoted.json()["workflow_job"]["job_type"] == "capability_refresh"

    reprocessed = client.post(
        f"/api/v1/resources/{resource_id}/reprocess",
        headers=manager,
        json={
            "adapter_id": "ckan-v3@1",
            "adapter_version": "2",
            "transformation_version": "acceptance-transform@2",
            "canonical_version": "canonical@2",
            "previous_transformation_run_id": str(transformation_id),
            "reason": "known schema adapter update",
        },
    )
    assert reprocessed.status_code == 202, reprocessed.text
    assert reprocessed.json()["previous_canonical_retained"] is True
    assert reprocessed.json()["job"]["job_type"] == "schema_normalization"
    assert (
        client.post(
            f"/api/v1/resources/{resource_id}/reprocess",
            headers=_headers("data_manager", ORG_B),
            json={
                "adapter_id": "ckan-v3@1",
                "adapter_version": "2",
                "transformation_version": "acceptance-transform@2",
                "canonical_version": "canonical@2",
                "previous_transformation_run_id": str(transformation_id),
                "reason": "cross-tenant reprocess attempt",
            },
        ).status_code
        == 404
    )

    quarantined = client.post(
        f"/api/v1/resources/{resource_id}/quarantine",
        headers=manager,
        json={
            "category": "schema_changed",
            "reason": "required field semantics changed and need human mapping review",
            "transformation_run_id": str(transformation_id),
            "evidence": {"field": "facility_type", "automatic_mapping": False},
        },
    )
    assert quarantined.status_code == 201, quarantined.text
    assert quarantined.json()["analysis_blocked"] is True
    assert quarantined.json()["promoted_dataset_automatically_replaced"] is False

    tasks = client.get("/api/v1/cities/maizuru/data-tasks", headers=manager)
    assert tasks.status_code == 200, tasks.text
    update_task = next(
        item for item in tasks.json()["items"] if item["task_type"] == "update_available"
    )
    started = client.patch(
        f"/api/v1/data-tasks/{update_task['id']}",
        headers=manager,
        json={
            "expected_status": "open",
            "proposed_status": "in_progress",
            "resolution_note": None,
        },
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "in_progress"
    assert (
        client.patch(
            f"/api/v1/data-tasks/{update_task['id']}",
            headers=_headers("data_manager", ORG_B),
            json={
                "expected_status": "in_progress",
                "proposed_status": "resolved",
                "resolution_note": "cross-tenant task mutation attempt",
            },
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/cities/maizuru/data-tasks", headers=_headers("viewer", ORG_B)
        ).status_code
        == 404
    )

    with psycopg.connect(database_url) as connection:
        assert connection.execute(
            """SELECT count(*) FROM canonical_open_data_records
               WHERE organization_id = %s AND source_resource_id = %s""",
            (ORG_A, resource_id),
        ).fetchone()[0] == 1
        request_row = connection.execute(
            """SELECT preserve_previous_canonical, target_adapter_version
               FROM open_data_reprocessing_requests
               WHERE organization_id = %s AND resource_id = %s""",
            (ORG_A, resource_id),
        ).fetchone()
        assert request_row == (True, "2")
        processing = connection.execute(
            """SELECT state FROM open_data_resource_processing
               WHERE organization_id = %s AND resource_id = %s""",
            (ORG_A, resource_id),
        ).fetchone()[0]
        assert processing == "quarantined"


def test_public_raw_blob_dedup_keeps_tenant_source_metadata_separate(
    database_url: str,
) -> None:
    _prepare_service_fixture(database_url)

    import psycopg

    suffix = uuid.uuid4().hex
    raw_sha = (suffix * 2)[:64]
    with psycopg.connect(database_url) as connection:
        city_a = connection.execute(
            "SELECT id FROM cities WHERE organization_id = %s AND city_key = 'maizuru'",
            (ORG_A,),
        ).fetchone()[0]
        source_a = connection.execute(
            """SELECT id FROM city_open_data_sources
               WHERE organization_id = %s AND city_id = %s
               ORDER BY id LIMIT 1""",
            (ORG_A, city_a),
        ).fetchone()[0]
        license_id = connection.execute(
            """SELECT license_id FROM open_data_license_policies
               WHERE unknown_terms = false ORDER BY license_id LIMIT 1"""
        ).fetchone()[0]
        source_b = connection.execute(
            """INSERT INTO city_open_data_sources (
                   organization_id, city_id, source_key, external_dataset_id,
                   dataset_family, title, source_url, availability, review_status,
                   license_id, reference_date
               ) VALUES (%s, %s, 'bodik-maizuru', %s, 'municipal_facilities',
                         '組織B 公開raw共有検証', 'https://data.bodik.jp/',
                         'available', 'selected', %s, '2026-01-01')
               RETURNING id""",
            (ORG_B, CITY_B, f"tenant-b-{suffix}", license_id),
        ).fetchone()[0]

        blob_id = connection.execute(
            """INSERT INTO open_data_raw_blobs (
                   owner_organization_id, sha256, size_bytes, content_type,
                   storage_provider, object_key, reuse_scope, first_retrieved_at
               ) VALUES (NULL, %s, 24, 'text/csv', 'local', %s,
                         'public_verified', now())
               RETURNING id""",
            (raw_sha, f"sha256/{raw_sha[:2]}/{raw_sha}"),
        ).fetchone()[0]
        reused_blob_id = connection.execute(
            """INSERT INTO open_data_raw_blobs (
                   owner_organization_id, sha256, size_bytes, content_type,
                   storage_provider, object_key, reuse_scope, first_retrieved_at
               ) VALUES (NULL, %s, 24, 'text/csv', 'local', %s,
                         'public_verified', now())
               ON CONFLICT (sha256, owner_organization_id) DO UPDATE SET
                   size_bytes = EXCLUDED.size_bytes
               RETURNING id""",
            (raw_sha, f"duplicate-attempt/{suffix}"),
        ).fetchone()[0]
        assert reused_blob_id == blob_id

        resource_a = connection.execute(
            """INSERT INTO open_data_resources (
                   organization_id, city_source_id, raw_blob_id,
                   external_resource_id, resource_title, resource_url, format,
                   content_length, raw_checksum, retrieved_at, adapter_version
               ) VALUES (%s, %s, %s, %s, '組織A metadata', %s, 'CSV', 24,
                         %s, now(), 'ckan-v3@1')
               RETURNING id""",
            (
                ORG_A,
                source_a,
                blob_id,
                f"tenant-a-{suffix}",
                f"https://data.bodik.jp/resource/{suffix}/a.csv",
                raw_sha,
            ),
        ).fetchone()[0]
        resource_b = connection.execute(
            """INSERT INTO open_data_resources (
                   organization_id, city_source_id, raw_blob_id,
                   external_resource_id, resource_title, resource_url, format,
                   content_length, raw_checksum, retrieved_at, adapter_version
               ) VALUES (%s, %s, %s, %s, '組織B metadata', %s, 'CSV', 24,
                         %s, now(), 'ckan-v3@1')
               RETURNING id""",
            (
                ORG_B,
                source_b,
                blob_id,
                f"tenant-b-{suffix}",
                f"https://data.bodik.jp/resource/{suffix}/b.csv",
                raw_sha,
            ),
        ).fetchone()[0]
        assert resource_a != resource_b
        assert connection.execute(
            "SELECT count(*) FROM open_data_raw_blobs WHERE sha256 = %s",
            (raw_sha,),
        ).fetchone()[0] == 1
        assert connection.execute(
            """SELECT count(DISTINCT organization_id)
               FROM open_data_resources WHERE raw_blob_id = %s""",
            (blob_id,),
        ).fetchone()[0] == 2

        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            connection.execute(
                """INSERT INTO open_data_resources (
                           organization_id, city_source_id, raw_blob_id,
                           external_resource_id, resource_title, resource_url, format,
                           raw_checksum, adapter_version
                       ) VALUES (%s, %s, %s, %s, 'cross-tenant metadata', %s,
                                 'CSV', %s, 'ckan-v3@1')""",
                (
                    ORG_B,
                    source_a,
                    blob_id,
                    f"forbidden-{suffix}",
                    f"https://data.bodik.jp/resource/{suffix}/forbidden.csv",
                    raw_sha,
                ),
            )

        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            connection.execute(
                """INSERT INTO open_data_source_feedback (
                           organization_id, city_id, city_source_id, feedback_type,
                           statement, submitted_by
                       ) VALUES (%s, %s, %s, 'attribute_issue',
                                 'cross-tenant source feedback attempt', 'acceptance-test')""",
                (ORG_B, CITY_B, source_a),
            )


def test_feedback_override_evidence_report_and_transparency_review_loop(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _ensure_open_data_record(database_url)
    monkeypatch.setenv("CITYGAP_API_SURFACE", "municipal")
    client = TestClient(create_app(MunicipalServiceRepository(database_url)))

    import psycopg

    with psycopg.connect(database_url) as connection:
        before_counts = connection.execute(
            """SELECT
                   (SELECT count(*) FROM open_data_raw_blobs WHERE id = %s),
                   (SELECT count(*) FROM canonical_open_data_records
                    WHERE organization_id = %s AND id = %s),
                   (SELECT sha256 FROM open_data_raw_blobs WHERE id = %s)""",
            (fixture["blob_id"], ORG_A, fixture["record_id"], fixture["blob_id"]),
        ).fetchone()

    feedback = client.post(
        "/api/v1/cities/maizuru/source-feedback",
        headers=_headers("field_staff"),
        json={
            "city_source_id": str(fixture["source_id"]),
            "canonical_record_id": fixture["record_id"],
            "feedback_type": "facility_closed",
            "statement": "現地掲示では利用停止中。公式source更新まではfeedbackとして分離保存する。",
            "evidence": {"observation": "posted notice", "raw_mutation": False},
        },
    )
    assert feedback.status_code == 201, feedback.text
    assert feedback.json()["official_raw_mutated"] is False
    assert feedback.json()["official_canonical_mutated"] is False
    feedback_id = feedback.json()["id"]
    assert (
        client.post(
            "/api/v1/cities/maizuru/source-feedback",
            headers=_headers("field_staff", ORG_B),
            json={
                "city_source_id": str(fixture["source_id"]),
                "canonical_record_id": fixture["record_id"],
                "feedback_type": "attribute_issue",
                "statement": "cross-tenant attempt",
            },
        ).status_code
        == 404
    )

    task = client.post(
        f"/api/v1/source-feedback/{feedback_id}/field-task",
        headers=_headers("field_staff"),
        json={
            "expected_feedback_status": "submitted",
            "title": "施設利用状況の現地確認",
            "checklist": ["掲示内容を確認", "位置と確認日時を記録"],
            "due_date": "2026-09-30",
        },
    )
    assert task.status_code == 201, task.text
    assert task.json()["official_records_mutated"] is False
    task_id = task.json()["id"]
    completed = client.patch(
        f"/api/v1/open-data-field-tasks/{task_id}",
        headers=_headers("field_staff"),
        json={
            "expected_status": "open",
            "proposed_status": "completed",
            "resolution_note": "2026-08-29に現地掲示と位置を確認。公式sourceは変更していない。",
        },
    )
    assert completed.status_code == 200, completed.text
    feedback_list = client.get(
        "/api/v1/cities/maizuru/source-feedback", headers=_headers("viewer")
    )
    assert feedback_list.status_code == 200
    saved_feedback = next(item for item in feedback_list.json()["items"] if item["id"] == feedback_id)
    assert saved_feedback["status"] == "reconciled"
    assert saved_feedback["raw_mutation_permitted"] is False
    assert saved_feedback["canonical_mutation_permitted"] is False

    override = client.post(
        "/api/v1/cities/maizuru/local-overrides",
        headers=_headers("data_manager"),
        json={
            "canonical_record_id": fixture["record_id"],
            "override_patch": {"local_operating_status": "temporary_unavailable"},
            "reason": "現地確認結果を庁内分析layerで期限付き反映",
            "evidence": {"source_feedback_id": feedback_id, "field_task_id": task_id},
            "effective_date": "2026-08-29",
            "expires_at": "2027-02-28",
            "review_status": "in_review",
        },
    )
    assert override.status_code == 201, override.text
    assert override.json()["official_record_mutated"] is False
    override_id = override.json()["id"]
    reviewed = client.patch(
        f"/api/v1/local-overrides/{override_id}/review",
        headers=_headers("data_manager"),
        json={
            "expected_status": "in_review",
            "proposed_status": "reviewed",
            "review_note": "根拠、適用日、見直し期限を確認",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviewed_by"] == "acceptance-data_manager"

    with psycopg.connect(database_url) as connection:
        next_transform = connection.execute(
            """INSERT INTO open_data_transformation_runs (
                   organization_id, resource_id, adapter_id, adapter_version,
                   transformation_version, canonical_version, status,
                   input_row_count, output_record_count, completed_at, metadata
               ) VALUES (%s, %s, 'ckan-v3@1', '2', 'review-loop@2',
                         'canonical@2', 'succeeded', 1, 1, now(), '{}') RETURNING id""",
            (ORG_A, fixture["resource_id"]),
        ).fetchone()[0]
        candidate_record_id = connection.execute(
            """INSERT INTO canonical_open_data_records (
                   organization_id, city_id, dataset_version_id, source_resource_id,
                   transformation_run_id, record_type, external_record_id,
                   display_name, source_row_locator, reference_date, attributes
               ) VALUES (%s, %s, %s, %s, %s, 'facility', %s,
                         'review loop facility updated', 'row:1', '2026-08-01',
                         '{"official_update":true}') RETURNING id""",
            (
                ORG_A,
                fixture["city_id"],
                fixture["dataset_version_id"],
                fixture["resource_id"],
                next_transform,
                fixture["external_record_id"],
            ),
        ).fetchone()[0]
        reconciliation = connection.execute(
            """SELECT status FROM open_data_override_reconciliations
               WHERE organization_id = %s AND override_id = %s
                 AND candidate_canonical_record_id = %s""",
            (ORG_A, override_id, candidate_record_id),
        ).fetchone()
        assert reconciliation == ("candidate",)
        assert connection.execute(
            """SELECT count(*) FROM local_data_overrides
               WHERE organization_id = %s AND id = %s""",
            (ORG_A, override_id),
        ).fetchone()[0] == 1
        after_counts = connection.execute(
            """SELECT
                   (SELECT count(*) FROM open_data_raw_blobs WHERE id = %s),
                   (SELECT count(*) FROM canonical_open_data_records
                    WHERE organization_id = %s AND id = %s),
                   (SELECT sha256 FROM open_data_raw_blobs WHERE id = %s)""",
            (fixture["blob_id"], ORG_A, fixture["record_id"], fixture["blob_id"]),
        ).fetchone()
        assert after_counts == before_counts

    evidence = client.post(
        "/api/v1/cities/maizuru/evidence-centers",
        headers=_headers("planner"),
        json={
            "schema_version": "2.0.0",
            "source_manifest": {
                "sources": [
                    {
                        "title": "official review-loop fixture",
                        "data_classification": "public",
                        "raw_sha256": fixture["raw_sha"],
                    }
                ]
            },
            "algorithm_manifest": {"adapter": "ckan-v3@1", "canonical": "canonical@2"},
            "validation_manifest": {"feedback_reviewed": True, "override_reviewed": True},
            "open_data_lineage_manifest": {
                "resource_id": str(fixture["resource_id"]),
                "raw_sha256": fixture["raw_sha"],
                "adapter_version": "2",
                "canonical_version": "canonical@2",
            },
            "report_manifest": {"deterministic": True},
            "data_classification": "public",
        },
    )
    assert evidence.status_code == 201, evidence.text
    evidence_id = evidence.json()["id"]
    detail = client.get(
        f"/api/v1/evidence-centers/{evidence_id}", headers=_headers("viewer")
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["integrity_verified"] is True
    assert detail.json()["evidence_center"]["schema_version"] == "2.0.0"

    report_payload = {
        "report_type": "data_quality",
        "title": "舞鶴市 公開データ品質レポート",
        "data_classification": "internal",
    }
    report_a = client.post(
        "/api/v1/cities/maizuru/reports",
        headers=_headers("planner"),
        json=report_payload,
    )
    report_b = client.post(
        "/api/v1/cities/maizuru/reports",
        headers=_headers("planner"),
        json=report_payload,
    )
    assert report_a.status_code == 201, report_a.text
    assert report_b.status_code == 201, report_b.text
    assert report_a.json()["artifact_sha256"] == report_b.json()["artifact_sha256"]
    assert report_a.json()["deterministic"] is True
    assert report_a.json()["content_schema_version"] == "2.0.0"

    transparency = client.post(
        "/api/v1/cities/maizuru/public-transparency",
        headers=_headers("planner"),
        json={
            "evidence_center_id": evidence_id,
            "title": "舞鶴市 公開データ確認記録",
            "summary": {"review_scope": "source, field feedback, local override boundary"},
            "source_citations": [
                {"title": "official review-loop fixture", "raw_sha256": fixture["raw_sha"]}
            ],
            "limitations": ["現地確認は公式sourceの内容を直接変更しません"],
            "publish": True,
        },
    )
    assert transparency.status_code == 201, transparency.text
    assert transparency.json()["publication_status"] == "published"
    public_list = client.get(
        "/api/v1/cities/maizuru/public-transparency", headers=_headers("viewer")
    )
    assert public_list.status_code == 200
    assert any(item["id"] == transparency.json()["id"] for item in public_list.json()["items"])
    assert "建物単位推計人口" in public_list.json()["boundary"]


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
                   analysis_ready = true, service_status = 'analysis_ready'
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
