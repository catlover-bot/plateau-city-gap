from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.api.repository import PostGISRepository
from backend.citygap_platform.database.migrations import migration_files, migration_status
from backend.citygap_platform.worker import ClaimedJob, PostgresWorker

ROOT = Path(__file__).resolve().parents[2]


def test_extensions_migrations_indexes_and_foreign_keys(database_url: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        extensions = dict(
            connection.execute(
                "SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis', 'pgrouting')"
            ).fetchall()
        )
        assert set(extensions) == {"postgis", "pgrouting"}
        assert connection.execute("SELECT PostGIS_Version() IS NOT NULL").fetchone() == (True,)
        assert connection.execute("SELECT pgr_version() IS NOT NULL").fetchone() == (True,)
        geometry_srids = dict(
            connection.execute(
                """SELECT attrelid::regclass::text, postgis_typmod_srid(atttypmod)
                   FROM pg_attribute
                   WHERE attrelid IN ('road_network_nodes'::regclass,
                                      'road_network_edges'::regclass)
                     AND attname = 'geom'"""
            ).fetchall()
        )
        assert geometry_srids == {"road_network_nodes": 0, "road_network_edges": 0}
        indexes = connection.execute(
            """SELECT indexname FROM pg_indexes
               WHERE indexname IN ('plateau_city_objects_envelope_idx', 'scenario_sites_geom_idx')"""
        ).fetchall()
        assert {row[0] for row in indexes} == {
            "plateau_city_objects_envelope_idx",
            "scenario_sites_geom_idx",
        }
        foreign_keys = connection.execute(
            """SELECT count(*) FROM pg_constraint
               WHERE contype = 'f' AND conrelid IN (
                   'scenario_sites'::regclass, 'road_network_edges'::regclass
               )"""
        ).fetchone()[0]
        assert foreign_keys >= 4
    status = migration_status(database_url, ROOT / "infra/migrations")
    assert status["ready"] is True
    assert len(status["applied"]) == len(migration_files(ROOT / "infra/migrations"))


def test_real_canonical_scenarios_spatial_api_and_comparison(database_url: str) -> None:
    import psycopg

    repository = PostGISRepository(database_url)
    client = TestClient(create_app(repository))
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    pilot = client.get("/admin/pilot-readiness/26202")
    assert pilot.status_code == 200
    assert pilot.json()["status"] == "NOT_READY"
    assert pilot.json()["facts"]["plateau_registered"] is True
    assert {"population_registered", "facility_registered", "quality_gate", "auth_mode"} <= set(
        pilot.json()["blockers"]
    )
    snapshot = client.get("/admin/snapshot")
    assert snapshot.status_code == 200
    assert snapshot.json()["cities"][0]["city_code"] == "26202"
    assert snapshot.json()["networks"][0]["source_type"] == "experimental_surface_adjacency"
    cities = client.get("/cities")
    assert cities.status_code == 200
    assert cities.json()[0]["city_id"] == "26202"
    buildings = client.get(
        "/cities/26202/buildings", params={"bbox": "135.3,35.4,135.4,35.5"}
    )
    assert buildings.status_code == 200
    assert buildings.json()["features"][0]["gml_id"] == "fixture-building-1"
    tile = client.get(
        "/cities/26202/tiles/buildings/0/0/0.mvt",
        params={"dataset_version_id": "20000000-0000-0000-0000-000000000001"},
    )
    assert tile.status_code == 200
    assert tile.headers["content-type"].startswith("application/vnd.mapbox-vector-tile")
    assert len(tile.content) > 0
    unchanged = client.get(
        "/cities/26202/tiles/buildings/0/0/0.mvt",
        params={"dataset_version_id": "20000000-0000-0000-0000-000000000001"},
        headers={"If-None-Match": tile.headers["etag"]},
    )
    assert unchanged.status_code == 304

    scenarios = client.get("/cities/26202/scenarios").json()["scenarios"]
    assert len(scenarios) == 30
    scenario_ids = [str(row["scenario_id"]) for row in scenarios[:3]]
    comparison = client.get(
        "/cities/26202/scenario-comparison",
        params={"scenario_ids": ",".join(scenario_ids)},
    )
    assert comparison.status_code == 200
    assert len(comparison.json()["plans"]) == 3

    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT count(*) FROM scenario_runs").fetchone() == (30,)
        assert connection.execute("SELECT count(*) FROM scenario_sites").fetchone() == (90,)
        plan = connection.execute(
            """EXPLAIN (FORMAT JSON) SELECT id FROM plateau_city_objects
               WHERE geometry_envelope && ST_MakeEnvelope(135.3,35.4,135.4,35.5,4326)"""
        ).fetchone()[0]
        assert "plateau_city_objects_envelope_idx" in json.dumps(plan)


def test_scenario_transaction_lifecycle_field_check_and_rollback(database_url: str) -> None:
    import psycopg

    client = TestClient(create_app(PostGISRepository(database_url)))
    scenario = client.get("/cities/26202/scenarios", params={"status": "draft"}).json()[
        "scenarios"
    ][0]
    scenario_id = str(scenario["scenario_id"])
    transitioned = client.patch(
        f"/cities/26202/scenarios/{scenario_id}/status",
        json={"expected_status": "draft", "proposed_status": "under_review", "note": "CI"},
    )
    assert transitioned.status_code == 200
    conflict = client.patch(
        f"/cities/26202/scenarios/{scenario_id}/status",
        json={"expected_status": "draft", "proposed_status": "reviewed", "note": "skip"},
    )
    assert conflict.status_code == 409
    saved = client.put(
        f"/cities/26202/scenarios/{scenario_id}/sites/1/field-check",
        json={"site_access": "confirmed", "road_safety": "attention", "notes": "現地確認"},
    )
    assert saved.status_code == 200
    assert saved.json()["road_safety"] == "attention"

    with psycopg.connect(database_url) as connection:
        before = connection.execute("SELECT count(*) FROM scenario_field_checks").fetchone()[0]
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                """INSERT INTO city_dataset_versions (
                       city_id, city_name, dataset_year, dataset_name,
                       product_specification_version, archive_file_name,
                       archive_sha256, archive_size_bytes
                   ) VALUES ('26202','舞鶴市',1900,'invalid','3.5','bad.zip',repeat('0',64),1)"""
            )
        after = connection.execute("SELECT count(*) FROM scenario_field_checks").fetchone()[0]
        assert after == before


def test_loader_rejects_wrong_dataset_version(database_url: str) -> None:
    import psycopg

    from backend.citygap_platform.ingestion.scenarios import load_scenario_artifacts

    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE city_dataset_versions SET archive_sha256 = repeat('f',64)")
        connection.commit()
    with pytest.raises(RuntimeError, match="Exact scenario dataset version is not loaded"):
        load_scenario_artifacts(database_url, ROOT / "analysis/outputs/real")


def test_database_worker_idempotency_success_retry_and_audit(database_url: str) -> None:
    import psycopg

    repository = PostGISRepository(database_url)
    version_id = "10000000-0000-0000-0000-000000000002"
    first = repository.create_job(
        "26202", "evidence_export", [version_id], "a" * 64, "evidence-v2", {"scenario": "A"}
    )
    duplicate = repository.create_job(
        "26202", "evidence_export", [version_id], "a" * 64, "evidence-v2", {"scenario": "A"}
    )
    assert first is not None and duplicate is not None
    assert first["job_id"] == duplicate["job_id"]

    completed: list[str] = []

    class RecordingExecutor:
        def execute(self, job: ClaimedJob, stage: str) -> None:
            completed.append(stage)

    worker = PostgresWorker(database_url, "integration-worker")
    assert worker.run_once(RecordingExecutor()) is True
    succeeded = repository.job_detail(str(first["job_id"]))
    assert succeeded is not None and succeeded["state"] == "succeeded"
    assert completed[-1] == "persist_artifacts"

    failing = repository.create_job(
        "26202", "evidence_export", [version_id], "b" * 64, "evidence-v2", {"scenario": "B"}
    )
    assert failing is not None
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE job_runs SET max_retries=0 WHERE id=%s", (failing["job_id"],))
        connection.commit()

    class FailingExecutor:
        def execute(self, job: ClaimedJob, stage: str) -> None:
            raise RuntimeError("fixture failure")

    assert worker.run_once(FailingExecutor()) is True
    failed = repository.job_detail(str(failing["job_id"]))
    assert failed is not None and failed["state"] == "failed"
    assert "fixture failure" in failed["error"]
    audit = repository.audit_events("26202", 20)
    assert any(event["action"] == "job.create" for event in audit)
