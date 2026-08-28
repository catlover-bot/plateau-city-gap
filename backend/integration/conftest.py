from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.citygap_platform.database.migrations import apply_migrations
from backend.citygap_platform.ingestion.scenarios import load_scenario_artifacts

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("CITYGAP_TEST_DATABASE_URL")


def _seed(database_url: str) -> dict[str, object]:
    import psycopg

    manifest = json.loads(
        (ROOT / "analysis/outputs/real/maizuru_scenario_canonical_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    archive_hash = manifest["dataset_version_key"].split(":", 2)[2]
    with psycopg.connect(database_url) as connection:
        city_uuid = connection.execute(
            """INSERT INTO cities (
                   city_code, city_key, name, prefecture_code, prefecture_name, analysis_crs
               ) VALUES ('26202', 'maizuru', '舞鶴市', '26', '京都府', 'EPSG:6674')
               ON CONFLICT (city_code) DO UPDATE SET name = EXCLUDED.name
               RETURNING id"""
        ).fetchone()[0]
        dataset_uuid = connection.execute(
            """INSERT INTO datasets (id, city_id, dataset_key, title, provider)
               VALUES ('10000000-0000-0000-0000-000000000001', %s, 'plateau-2025',
                       '舞鶴市 PLATEAU 2025', 'Project PLATEAU')
               ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title RETURNING id""",
            (city_uuid,),
        ).fetchone()[0]
        registry_version = connection.execute(
            """INSERT INTO dataset_versions (
                   id, dataset_id, version_key, dataset_year, data_format, source_url, license,
                   declared_source_crs, archive_file_name, archive_sha256,
                   verification_status, registered_at
               ) VALUES ('10000000-0000-0000-0000-000000000002', %s, '2025-fixture', 2025,
                   'CityGML', 'https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025',
                   'CC BY 4.0', 'EPSG:6697', '26202_maizuru-shi_2025_citygml.zip', %s,
                   'checksum_verified', now())
               ON CONFLICT (id) DO UPDATE SET archive_sha256 = EXCLUDED.archive_sha256
               RETURNING id""",
            (dataset_uuid, archive_hash),
        ).fetchone()[0]
        dataset_version = connection.execute(
            """INSERT INTO city_dataset_versions (
                   id, city_id, city_name, dataset_year, dataset_name,
                   product_specification_version, ade_schema_version, archive_file_name,
                   archive_sha256, archive_size_bytes, source_url, is_current,
                   registry_version_id
               ) VALUES ('20000000-0000-0000-0000-000000000001', '26202', '舞鶴市', 2025,
                   'PLATEAU 3D都市モデル', '3.5', '4.3',
                   '26202_maizuru-shi_2025_citygml.zip', %s, 1,
                   'https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025',
                   true, %s)
               ON CONFLICT (id) DO UPDATE SET archive_sha256 = EXCLUDED.archive_sha256
               RETURNING id""",
            (archive_hash, registry_version),
        ).fetchone()[0]
        ingestion = connection.execute(
            """INSERT INTO ingestion_runs (
                   id, dataset_version_id, parser_version, status, completed_at,
                   processed_members, processed_features, processed_geometry_parts
               ) VALUES ('30000000-0000-0000-0000-000000000001', %s,
                   'integration-fixture-1', 'completed', now(), 1, 1, 1)
               ON CONFLICT (id) DO UPDATE SET status = 'completed' RETURNING id""",
            (dataset_version,),
        ).fetchone()[0]
        city_object = connection.execute(
            """INSERT INTO plateau_city_objects (
                   dataset_version_id, ingestion_run_id, gml_id, theme, feature_type,
                   lods, source_crs, source_member, source_member_crc32, attributes,
                   geometry_envelope, representative_point
               ) VALUES (%s, %s, 'fixture-building-1', 'bldg', 'Building', ARRAY[1],
                   ARRAY['EPSG:6697'], 'official-derived-fixture.gml', 'a1b2c3d4', '{}',
                   ST_MakeEnvelope(135.32, 35.46, 135.321, 35.461, 4326),
                   ST_SetSRID(ST_MakePoint(135.3205, 35.4605), 4326))
               ON CONFLICT (dataset_version_id, gml_id) DO UPDATE SET
                   geometry_envelope = EXCLUDED.geometry_envelope
               RETURNING id""",
            (dataset_version, ingestion),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO plateau_buildings (city_object_id, usage_code, measured_height_m)
               VALUES (%s, '401', 8.5) ON CONFLICT (city_object_id) DO NOTHING""",
            (city_object,),
        )
        network = connection.execute(
            """INSERT INTO road_network_versions (
                   id, dataset_version_id, graph_version, graph_method, network_type,
                   official_generator_executed, pedestrian_network, route_semantics,
                   analysis_crs, topology_tolerance_m, config_hash, node_count, edge_count,
                   component_count, generated_at, software_commit, metadata
               ) VALUES ('40000000-0000-0000-0000-000000000001', %s, %s,
                   'PLATEAU LOD1 surface adjacency', 'surface_adjacency', false, false,
                   'experimental surface adjacency; not pedestrian routing', 'EPSG:6674', 0.5,
                   repeat('4', 64), 15684, 23437, 4, now(), 'integration-fixture', '{}')
               ON CONFLICT (id) DO UPDATE SET graph_version = EXCLUDED.graph_version
               RETURNING id""",
            (dataset_version, manifest["network_version"]),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO spatial_context_runs (
                   id, dataset_version_id, network_version_id, algorithm_version,
                   analysis_crs, config_hash, source_archive_sha256, status,
                   started_at, completed_at, metadata
               ) VALUES ('50000000-0000-0000-0000-000000000001', %s, %s, %s,
                   'EPSG:6674', %s, %s, 'succeeded', now(), now(), '{}')
               ON CONFLICT (id) DO UPDATE SET status = 'succeeded'""",
            (
                dataset_version,
                network,
                manifest["context_version"],
                manifest["context_config_hash"],
                archive_hash,
            ),
        )
        connection.commit()
    return load_scenario_artifacts(database_url, ROOT / "analysis/outputs/real")


@pytest.fixture(scope="session")
def database_url() -> str:
    if not DATABASE_URL:
        pytest.skip("ENVIRONMENT_SPECIFIC: CITYGAP_TEST_DATABASE_URL is required")
    apply_migrations(DATABASE_URL, ROOT / "infra/migrations")
    result = _seed(DATABASE_URL)
    assert result["loaded_rows"]["scenario_runs"] == 30
    return DATABASE_URL
