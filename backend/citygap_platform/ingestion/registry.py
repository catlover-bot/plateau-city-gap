"""Persist the explicit multi-city registry without selecting implicit latest versions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.citygap_platform.domain.registry import validate_platform_registry


def load_platform_registry(database_url: str, registry_path: str | Path) -> dict[str, Any]:
    import psycopg

    path = Path(registry_path)
    registry = json.loads(path.read_text(encoding="utf-8"))
    validate_platform_registry(registry)
    counts = {
        "cities": 0,
        "datasets": 0,
        "dataset_versions": 0,
        "analysis_runs": 0,
        "analysis_run_dataset_versions": 0,
        "city_capabilities": 0,
    }
    with psycopg.connect(database_url) as connection:
        city_ids = {}
        for city in registry["cities"]:
            city_id = connection.execute(
                """INSERT INTO cities (
                       city_code, city_key, name, prefecture_code,
                       prefecture_name, analysis_crs, updated_at
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (city_code) DO UPDATE SET
                       city_key = EXCLUDED.city_key, name = EXCLUDED.name,
                       prefecture_code = EXCLUDED.prefecture_code,
                       prefecture_name = EXCLUDED.prefecture_name,
                       analysis_crs = EXCLUDED.analysis_crs,
                       updated_at = EXCLUDED.updated_at
                   RETURNING id""",
                (
                    city["city_code"],
                    city["city_id"],
                    city["name"],
                    city["prefecture_code"],
                    city["prefecture_name"],
                    city["analysis_crs"],
                    registry["generated_at"],
                ),
            ).fetchone()[0]
            city_ids[city["city_code"]] = city_id
            counts["cities"] += 1

        for dataset in registry["datasets"]:
            connection.execute(
                """INSERT INTO datasets (id, city_id, dataset_key, title, provider)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title,
                       provider = EXCLUDED.provider""",
                (
                    dataset["dataset_id"],
                    city_ids[dataset["city_code"]],
                    dataset["dataset_key"],
                    dataset["title"],
                    dataset["provider"],
                ),
            )
            counts["datasets"] += 1

        for version in registry["dataset_versions"]:
            connection.execute(
                """INSERT INTO dataset_versions (
                       id, dataset_id, version_key, dataset_year, data_format,
                       source_url, license, declared_source_crs, archive_file_name,
                       archive_sha256, verification_status, registered_at
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                       source_url = EXCLUDED.source_url, license = EXCLUDED.license,
                       declared_source_crs = EXCLUDED.declared_source_crs,
                       archive_file_name = EXCLUDED.archive_file_name,
                       archive_sha256 = EXCLUDED.archive_sha256,
                       verification_status = EXCLUDED.verification_status,
                       registered_at = EXCLUDED.registered_at""",
                (
                    version["dataset_version_id"],
                    version["dataset_id"],
                    version["version_key"],
                    version["year"],
                    version["format"],
                    version["source_url"],
                    version["license"],
                    version["declared_source_crs"],
                    version["archive_file"],
                    version["archive_sha256"],
                    version["verification_status"],
                    registry["generated_at"],
                ),
            )
            counts["dataset_versions"] += 1

        connection.execute(
            """UPDATE city_dataset_versions AS legacy
               SET registry_version_id = version.id
               FROM dataset_versions AS version
               JOIN datasets AS dataset ON dataset.id = version.dataset_id
               JOIN cities AS city ON city.id = dataset.city_id
               WHERE dataset.dataset_key = 'plateau'
                 AND legacy.city_id = city.city_code
                 AND legacy.dataset_year = version.dataset_year
                 AND (version.archive_sha256 IS NULL OR
                      legacy.archive_sha256 = version.archive_sha256)"""
        )

        for run in registry["analysis_runs"]:
            connection.execute(
                """INSERT INTO analysis_runs (
                       id, city_id, analysis_type, status, config_hash,
                       output_artifact, output_sha256, started_at, completed_at, metadata
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                       status = EXCLUDED.status, output_artifact = EXCLUDED.output_artifact,
                       output_sha256 = EXCLUDED.output_sha256,
                       completed_at = EXCLUDED.completed_at, metadata = EXCLUDED.metadata""",
                (
                    run["analysis_run_id"],
                    city_ids[run["city_code"]],
                    run["analysis_type"],
                    run["status"],
                    run["config_hash"],
                    run["output_artifact"],
                    run["output_sha256"],
                    registry["generated_at"],
                    registry["generated_at"],
                    json.dumps({"registry_source": path.name}),
                ),
            )
            counts["analysis_runs"] += 1
            connection.execute(
                "DELETE FROM analysis_run_dataset_versions WHERE analysis_run_id = %s",
                (run["analysis_run_id"],),
            )
            for dataset_version_id in run["dataset_version_ids"]:
                connection.execute(
                    """INSERT INTO analysis_run_dataset_versions (
                           analysis_run_id, dataset_version_id, input_role
                       ) VALUES (%s, %s, 'source')""",
                    (run["analysis_run_id"], dataset_version_id),
                )
                counts["analysis_run_dataset_versions"] += 1

        for capability in registry["capabilities"]:
            connection.execute(
                """INSERT INTO city_capabilities (
                       city_id, capability, status, note, evidence, updated_at
                   ) VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (city_id, capability) DO UPDATE SET
                       status = EXCLUDED.status, note = EXCLUDED.note,
                       evidence = EXCLUDED.evidence, updated_at = EXCLUDED.updated_at""",
                (
                    city_ids[capability["city_code"]],
                    capability["capability"],
                    capability["status"],
                    capability["note"],
                    json.dumps(capability["evidence"], ensure_ascii=False),
                    registry["generated_at"],
                ),
            )
            counts["city_capabilities"] += 1
        connection.commit()
    return {"database_executed": True, "loaded_rows": counts}
