from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.api.repository import PostGISRepository
from backend.citygap_platform.database.migrations import migration_files, migration_status
from backend.citygap_platform.ingestion.evidence import register_evidence_manifest
from backend.citygap_platform.ingestion.official_network import (
    OfficialNetworkFieldMap,
    OfficialRoadNetworkAdapter,
    load_official_network,
)
from backend.citygap_platform.ingestion.postgis import (
    DatasetMetadata,
    archive_sha256,
    ingest_archive,
)
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

    evidence = register_evidence_manifest(
        database_url,
        ROOT
        / "analysis/outputs/real/evidence_packages/scenario-comparison-v2/manifest.json",
    )
    assert evidence["inserted_rows"] == 6
    repeated_evidence = register_evidence_manifest(
        database_url,
        ROOT
        / "analysis/outputs/real/evidence_packages/scenario-comparison-v2/manifest.json",
    )
    assert repeated_evidence["inserted_rows"] == 0
    assert repeated_evidence["reused_rows"] == 6

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
    assert pilot.json()["facts"]["evidence_count"] == 6
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
        assert connection.execute(
            "SELECT count(*) FROM audit_log WHERE action='scenario.create'"
        ).fetchone() == (30,)
        assert connection.execute(
            "SELECT count(*) FROM audit_log WHERE action='evidence.export'"
        ).fetchone() == (6,)
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

    stale = repository.create_job(
        "26202", "evidence_export", [version_id], "c" * 64, "evidence-v2", {"scenario": "C"}
    )
    assert stale is not None
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """UPDATE job_runs SET state='running', current_stage='collect_provenance',
                      started_at=now()-interval '2 hours',
                      last_heartbeat_at=now()-interval '2 hours', locked_by='dead-worker'
               WHERE id=%s""",
            (stale["job_id"],),
        )
        connection.execute(
            """INSERT INTO job_attempts (job_run_id, attempt_number, worker_id, started_at)
               VALUES (%s,1,'dead-worker',now()-interval '2 hours')""",
            (stale["job_id"],),
        )
        connection.commit()
    recovery_worker = PostgresWorker(database_url, "recovery-worker", stale_after_seconds=60)
    assert recovery_worker.recover_stale() == 1
    recovered = repository.job_detail(str(stale["job_id"]))
    assert recovered is not None
    assert recovered["state"] == "queued"
    assert recovered["retry_count"] == 1
    assert recovery_worker.run_once(RecordingExecutor()) is True
    recovered = repository.job_detail(str(stale["job_id"]))
    assert recovered is not None and recovered["state"] == "succeeded"
    with psycopg.connect(database_url) as connection:
        attempts = connection.execute(
            """SELECT attempt_number, result FROM job_attempts
               WHERE job_run_id=%s ORDER BY attempt_number""",
            (stale["job_id"],),
        ).fetchall()
        assert attempts == [(1, "requeued"), (2, "succeeded")]
        assert connection.execute(
            """SELECT count(*) FROM audit_log
               WHERE action='job.stale.recover' AND resource_id=%s""",
            (str(stale["job_id"]),),
        ).fetchone() == (1,)

    exhausted = repository.create_job(
        "26202", "evidence_export", [version_id], "d" * 64, "evidence-v2", {"scenario": "D"}
    )
    assert exhausted is not None
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """UPDATE job_runs SET state='running', current_stage='collect_provenance',
                      max_retries=0, started_at=now()-interval '2 hours',
                      last_heartbeat_at=now()-interval '2 hours', locked_by='dead-worker'
               WHERE id=%s""",
            (exhausted["job_id"],),
        )
        connection.execute(
            """INSERT INTO job_attempts (job_run_id, attempt_number, worker_id, started_at)
               VALUES (%s,1,'dead-worker',now()-interval '2 hours')""",
            (exhausted["job_id"],),
        )
        connection.commit()
    assert recovery_worker.recover_stale() == 1
    exhausted_detail = repository.job_detail(str(exhausted["job_id"]))
    assert exhausted_detail is not None and exhausted_detail["state"] == "failed"


CITYGML_FIXTURE = """<?xml version='1.0' encoding='UTF-8'?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
 xmlns:gml="http://www.opengis.net/gml"
 xmlns:bldg="http://www.opengis.net/citygml/building/2.0">
 <core:cityObjectMember><bldg:Building gml:id="building-atomic-1">
  <bldg:lod1Solid><gml:Solid srsName="http://www.opengis.net/def/crs/EPSG/0/6697">
   <gml:exterior><gml:CompositeSurface><gml:surfaceMember><gml:Polygon>
    <gml:exterior><gml:LinearRing><gml:posList>
     35 135 0 35 135.01 0 35.01 135 0 35 135 0
    </gml:posList></gml:LinearRing></gml:exterior>
   </gml:Polygon></gml:surfaceMember></gml:CompositeSurface></gml:exterior>
  </gml:Solid></bldg:lod1Solid>
 </bldg:Building></core:cityObjectMember>
</core:CityModel>
"""


def _seed_current_version(connection, city_id: str, archive_hash: str) -> str:
    connection.execute(
        """INSERT INTO cities (
               city_code, city_key, name, prefecture_code, prefecture_name, analysis_crs
           ) VALUES (%s,%s,%s,'99','Integration','EPSG:6677')
           ON CONFLICT (city_code) DO NOTHING""",
        (city_id, f"integration-{city_id}", city_id),
    )
    return str(
        connection.execute(
            """INSERT INTO city_dataset_versions (
                   city_id, city_name, dataset_year, dataset_name,
                   product_specification_version, archive_file_name,
                   archive_sha256, archive_size_bytes, is_current
               ) VALUES (%s,%s,2024,'previous','5.0','previous.zip',%s,1,true)
               RETURNING id""",
            (city_id, city_id, archive_hash),
        ).fetchone()[0]
    )


def test_ingestion_activates_only_completed_versions_and_is_idempotent(
    database_url: str, tmp_path: Path
) -> None:
    import psycopg

    failed_city = "99001"
    with psycopg.connect(database_url) as connection:
        previous_id = _seed_current_version(connection, failed_city, "1" * 64)
        connection.commit()
    broken_archive = tmp_path / "broken.zip"
    with zipfile.ZipFile(broken_archive, "w") as archive:
        archive.writestr("city/udx/bldg/first.gml", CITYGML_FIXTURE)
        archive.writestr("city/udx/bldg/second.gml", "<broken>")
    metadata = DatasetMetadata(
        city_id=failed_city,
        city_name="Atomic Failure",
        dataset_year=2025,
        dataset_name="failure fixture",
        product_specification_version="5.0",
        ade_schema_version="3.2",
    )
    with pytest.raises(ParseError):
        ingest_archive(broken_archive, database_url, metadata)
    failed_hash = archive_sha256(broken_archive)
    with psycopg.connect(database_url) as connection:
        current_after_failure = connection.execute(
            "SELECT id FROM city_dataset_versions WHERE city_id=%s AND is_current",
            (failed_city,),
        ).fetchone()
        assert current_after_failure is not None
        assert str(current_after_failure[0]) == previous_id
        failed = connection.execute(
            """SELECT version.is_current, ingestion.status,
                      ingestion.processed_features,
                      (SELECT count(*) FROM plateau_city_objects AS object
                       WHERE object.dataset_version_id=version.id)
               FROM city_dataset_versions AS version
               JOIN ingestion_runs AS ingestion ON ingestion.dataset_version_id=version.id
               WHERE version.archive_sha256=%s""",
            (failed_hash,),
        ).fetchone()
        assert failed == (False, "failed", 1, 1)
    assert PostGISRepository(database_url).readiness(failed_city)["checks"][
        "required_dataset"
    ] is False

    success_city = "99002"
    with psycopg.connect(database_url) as connection:
        old_success_id = _seed_current_version(connection, success_city, "2" * 64)
        connection.commit()
    valid_archive = tmp_path / "valid.zip"
    with zipfile.ZipFile(valid_archive, "w") as archive:
        archive.writestr("city/udx/bldg/only.gml", CITYGML_FIXTURE)
    success_metadata = DatasetMetadata(
        city_id=success_city,
        city_name="Atomic Success",
        dataset_year=2025,
        dataset_name="success fixture",
        product_specification_version="5.0",
        ade_schema_version="3.2",
    )
    first = ingest_archive(valid_archive, database_url, success_metadata)
    repeated = ingest_archive(valid_archive, database_url, success_metadata)
    assert first["reused"] is False
    assert repeated["reused"] is True
    assert repeated["ingestion_run_id"] == first["ingestion_run_id"]
    with psycopg.connect(database_url) as connection:
        current = connection.execute(
            "SELECT id FROM city_dataset_versions WHERE city_id=%s AND is_current",
            (success_city,),
        ).fetchone()[0]
        assert str(current) == first["dataset_version_id"]
        assert str(current) != old_success_id
        assert connection.execute(
            "SELECT count(*) FROM ingestion_runs WHERE dataset_version_id=%s",
            (current,),
        ).fetchone() == (1,)


def test_official_network_adapter_persists_exact_source_and_audit(
    database_url: str, tmp_path: Path
) -> None:
    import psycopg

    nodes_path = tmp_path / "official-nodes.geojson"
    edges_path = tmp_path / "official-edges.geojson"
    gpd.GeoDataFrame(
        {"node_id": ["n1", "n2"]},
        geometry=[Point(139.46, 35.34), Point(139.47, 35.34)],
        crs="EPSG:4326",
    ).to_file(nodes_path, driver="GeoJSON")
    gpd.GeoDataFrame(
        {"link_id": ["e1"], "start_id": ["n1"], "end_id": ["n2"]},
        geometry=[LineString([(139.46, 35.34), (139.47, 35.34)])],
        crs="EPSG:4326",
    ).to_file(edges_path, driver="GeoJSON")
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """INSERT INTO cities (
                   city_code, city_key, name, prefecture_code, prefecture_name, analysis_crs
               ) VALUES ('99003','official-city','Official City','99','Integration','EPSG:6677')"""
        )
        dataset_id = connection.execute(
            """INSERT INTO city_dataset_versions (
                   city_id, city_name, dataset_year, dataset_name,
                   product_specification_version, archive_file_name,
                   archive_sha256, archive_size_bytes
               ) VALUES ('99003','Official City',2025,'official fixture',
                         '5.0','official.zip',repeat('3',64),1) RETURNING id"""
        ).fetchone()[0]
        connection.commit()
    adapter = OfficialRoadNetworkAdapter(
        nodes_path,
        edges_path,
        source_type="official_walk",
        fields=OfficialNetworkFieldMap(length_m=None),
        analysis_crs="EPSG:6677",
    )
    result = load_official_network(
        database_url,
        str(dataset_id),
        adapter,
        generator_commit="5f8d7662a01f58761c98bade02fd065884679b42",
        software_commit="integration-test",
    )
    with psycopg.connect(database_url) as connection:
        network = connection.execute(
            """SELECT source_type, pedestrian_network, node_count, edge_count
               FROM road_network_versions WHERE id=%s""",
            (result["network_version_id"],),
        ).fetchone()
        assert network == ("official_walk", True, 2, 1)
        assert connection.execute(
            """SELECT array_agg(DISTINCT ST_SRID(geom))
               FROM road_network_nodes WHERE network_version_id=%s""",
            (result["network_version_id"],),
        ).fetchone() == ([6677],)
        assert connection.execute(
            """SELECT count(*) FROM audit_log
               WHERE action='network.official.import' AND resource_id=%s""",
            (result["network_version_id"],),
        ).fetchone() == (1,)
