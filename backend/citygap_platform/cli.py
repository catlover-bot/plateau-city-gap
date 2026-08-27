"""Municipal import and operation CLI backed by the same platform core."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from backend.citygap_platform.api.repository import PostGISRepository
from backend.citygap_platform.ingestion.official_network import (
    OfficialNetworkFieldMap,
    OfficialRoadNetworkAdapter,
    load_official_network,
)
from backend.citygap_platform.ingestion.quality import (
    QualityMeasurements,
    QualityThresholds,
    evaluate_quality,
)
from backend.citygap_platform.ingestion.uploads import inspect_upload
from backend.citygap_platform.observability import operation_context
from backend.citygap_platform.readiness import PilotReadinessService

NAMESPACE = uuid.UUID("b58bf5a8-29c0-5da0-8d90-00cc8c581721")


def _database_url(args: argparse.Namespace) -> str:
    value = args.database_url or os.getenv("CITYGAP_DATABASE_URL")
    if not value:
        raise ValueError("--database-url or CITYGAP_DATABASE_URL is required")
    return value


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _hash(parameters: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _city_init(args: argparse.Namespace) -> dict[str, Any]:
    repository = PostGISRepository(_database_url(args))
    with repository._connect() as connection:
        before = connection.execute(
            "SELECT city_key, name, prefecture_code, prefecture_name, analysis_crs FROM cities WHERE city_code=%s",
            (args.city_code,),
        ).fetchone()
        row = connection.execute(
            """INSERT INTO cities (
                   city_code, city_key, name, prefecture_code, prefecture_name, analysis_crs
               ) VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (city_code) DO UPDATE SET city_key=EXCLUDED.city_key,
                   name=EXCLUDED.name, prefecture_code=EXCLUDED.prefecture_code,
                   prefecture_name=EXCLUDED.prefecture_name, analysis_crs=EXCLUDED.analysis_crs,
                   updated_at=now()
               RETURNING id, city_code, city_key, name, analysis_crs""",
            (
                args.city_code,
                args.city_key,
                args.name,
                args.prefecture_code,
                args.prefecture_name,
                args.analysis_crs,
            ),
        ).fetchone()
        result = dict(zip(("id", "city_code", "city_key", "name", "analysis_crs"), row, strict=True))
        repository._audit(
            connection,
            "city.upsert",
            "city",
            args.city_code,
            args.city_code,
            {"record": before} if before else None,
            result,
        )
        connection.commit()
    return result


def _dataset_add(args: argparse.Namespace) -> dict[str, Any]:
    repository = PostGISRepository(_database_url(args))
    dataset_id = uuid.uuid5(NAMESPACE, f"dataset:{args.city}:{args.dataset_key}")
    version_id = uuid.uuid5(dataset_id, args.version_key)
    with repository._connect() as connection:
        city = connection.execute(
            "SELECT id, city_code FROM cities WHERE city_code=%s OR city_key=%s",
            (args.city, args.city),
        ).fetchone()
        if city is None:
            raise ValueError("City is not registered")
        connection.execute(
            """INSERT INTO datasets (id, city_id, dataset_key, title, provider)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, provider=EXCLUDED.provider""",
            (dataset_id, city[0], args.dataset_key, args.title, args.provider),
        )
        connection.execute(
            """INSERT INTO dataset_versions (
                   id, dataset_id, version_key, dataset_year, data_format, source_url,
                   license, declared_source_crs, archive_file_name, archive_sha256,
                   verification_status, registered_at
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
               ON CONFLICT (id) DO UPDATE SET source_url=EXCLUDED.source_url,
                   license=EXCLUDED.license, declared_source_crs=EXCLUDED.declared_source_crs,
                   archive_file_name=EXCLUDED.archive_file_name,
                   archive_sha256=EXCLUDED.archive_sha256,
                   verification_status=EXCLUDED.verification_status""",
            (
                version_id,
                dataset_id,
                args.version_key,
                args.year,
                args.format,
                args.source_url,
                args.license,
                args.crs,
                Path(args.file).name if args.file else None,
                args.sha256,
                "checksum_verified" if args.sha256 else "metadata_registered",
            ),
        )
        result = {
            "city_code": city[1],
            "dataset_id": str(dataset_id),
            "dataset_version_id": str(version_id),
            "lifecycle_status": "registered",
            "analysis_ready": False,
        }
        repository._audit(
            connection,
            "dataset.register",
            "dataset_version",
            str(version_id),
            city[1],
            None,
            result,
        )
        connection.commit()
    return result


def _validate(args: argparse.Namespace) -> dict[str, Any]:
    result = inspect_upload(args.format, args.path, theme=args.theme, layer=args.layer)
    report = evaluate_quality(
        QualityMeasurements(
            feature_count=result.feature_or_row_count,
            invalid_geometry_count=0,
            crs=result.crs,
        ),
        QualityThresholds(
            minimum_feature_count=args.minimum_features,
            allowed_crs=frozenset(args.allowed_crs),
        ),
    )
    payload = {"inspection": result.as_dict(), "quality_gate": report.as_dict()}
    if args.dataset_version_id:
        repository = PostGISRepository(_database_url(args))
        with repository._connect() as connection:
            updated = connection.execute(
                """UPDATE dataset_versions SET quality_status=%s, quality_report=%s,
                          lifecycle_status=CASE WHEN %s='passed' THEN 'validated' ELSE 'failed' END,
                          analysis_ready=false
                   WHERE id=%s RETURNING id""",
                (
                    report.status,
                    json.dumps(payload, ensure_ascii=False),
                    report.status,
                    args.dataset_version_id,
                ),
            ).fetchone()
            if updated is None:
                raise ValueError("Dataset version is not registered")
            repository._audit(
                connection,
                "dataset.validate",
                "dataset_version",
                args.dataset_version_id,
                None,
                None,
                {"quality_status": report.status, "analysis_ready": False},
            )
            connection.commit()
    return payload


def _enqueue(args: argparse.Namespace, job_type: str) -> dict[str, Any]:
    parameters = json.loads(args.parameters)
    config_hash = args.config_hash or _hash(parameters)
    repository = PostGISRepository(_database_url(args))
    result = repository.create_job(
        args.city,
        job_type,
        args.dataset_version,
        config_hash,
        args.algorithm_version,
        parameters,
    )
    if result is None:
        raise ValueError("City is not registered")
    return result


def _network_import(args: argparse.Namespace) -> dict[str, Any]:
    adapter = OfficialRoadNetworkAdapter(
        args.nodes,
        args.edges,
        source_type=args.source_type,
        fields=OfficialNetworkFieldMap(
            node_id=args.node_id,
            edge_id=args.edge_id,
            source_node_id=args.source_node_id,
            target_node_id=args.target_node_id,
            length_m=args.length_field,
        ),
        analysis_crs=args.analysis_crs,
    )
    return load_official_network(
        _database_url(args),
        args.dataset_version_id,
        adapter,
        generator_commit=args.generator_commit,
        software_commit=args.software_commit,
    )


def _readiness(args: argparse.Namespace) -> dict[str, Any]:
    repository = PostGISRepository(_database_url(args))
    return PilotReadinessService(repository).check(args.city)


def _add_database(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database-url")


def _add_job(parser: argparse.ArgumentParser) -> None:
    _add_database(parser)
    parser.add_argument("--city", required=True)
    parser.add_argument("--dataset-version", action="append", required=True)
    parser.add_argument("--algorithm-version", required=True)
    parser.add_argument("--config-hash")
    parser.add_argument("--parameters", default="{}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="citygap", description="CITY GAP municipal workflow")
    subcommands = parser.add_subparsers(dest="command", required=True)

    city = subcommands.add_parser("city-init")
    _add_database(city)
    city.add_argument("--city-code", required=True)
    city.add_argument("--city-key", required=True)
    city.add_argument("--name", required=True)
    city.add_argument("--prefecture-code", required=True)
    city.add_argument("--prefecture-name", required=True)
    city.add_argument("--analysis-crs", required=True)
    city.set_defaults(handler=_city_init)

    dataset = subcommands.add_parser("dataset-add")
    _add_database(dataset)
    dataset.add_argument("--city", required=True)
    dataset.add_argument("--dataset-key", required=True)
    dataset.add_argument("--title", required=True)
    dataset.add_argument("--provider", required=True)
    dataset.add_argument("--version-key", required=True)
    dataset.add_argument("--year", type=int, required=True)
    dataset.add_argument("--format", required=True)
    dataset.add_argument("--source-url")
    dataset.add_argument("--license")
    dataset.add_argument("--crs")
    dataset.add_argument("--file")
    dataset.add_argument("--sha256")
    dataset.set_defaults(handler=_dataset_add)

    validate = subcommands.add_parser("validate")
    _add_database(validate)
    validate.add_argument("--format", required=True, choices=(
        "csv", "geojson", "geopackage", "gtfs", "citygml", "citygml_zip"
    ))
    validate.add_argument("--path", required=True)
    validate.add_argument("--theme")
    validate.add_argument("--layer")
    validate.add_argument("--minimum-features", type=int, default=1)
    validate.add_argument("--allowed-crs", action="append", default=[])
    validate.add_argument("--dataset-version-id")
    validate.set_defaults(handler=_validate)

    ingest = subcommands.add_parser("ingest")
    _add_job(ingest)
    ingest.set_defaults(handler=lambda args: _enqueue(args, "plateau_ingestion"))
    analyze = subcommands.add_parser("analyze")
    _add_job(analyze)
    analyze.add_argument(
        "--job-type",
        choices=("building_demographics", "road_network", "terrain", "spatial_context"),
        required=True,
    )
    analyze.set_defaults(handler=lambda args: _enqueue(args, args.job_type))
    scenario = subcommands.add_parser("scenario")
    _add_job(scenario)
    scenario.set_defaults(handler=lambda args: _enqueue(args, "scenario_optimization"))
    export = subcommands.add_parser("export")
    _add_job(export)
    export.set_defaults(handler=lambda args: _enqueue(args, "evidence_export"))
    network = subcommands.add_parser("network-import")
    _add_database(network)
    network.add_argument("--dataset-version-id", required=True)
    network.add_argument("--nodes", required=True)
    network.add_argument("--edges", required=True)
    network.add_argument("--source-type", choices=("official_walk", "official_drive"), required=True)
    network.add_argument("--analysis-crs", required=True)
    network.add_argument("--generator-commit", required=True)
    network.add_argument("--software-commit", required=True)
    network.add_argument("--node-id", default="node_id")
    network.add_argument("--edge-id", default="link_id")
    network.add_argument("--source-node-id", default="start_id")
    network.add_argument("--target-node-id", default="end_id")
    network.add_argument("--length-field", default="distance")
    network.set_defaults(handler=_network_import)
    readiness = subcommands.add_parser("readiness")
    _add_database(readiness)
    readiness.add_argument("--city", required=True)
    readiness.set_defaults(handler=_readiness)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    actor = os.getenv("CITYGAP_ACTOR", "cli-operator")
    with operation_context(actor, f"cli-{uuid.uuid4()}"):
        try:
            _json(args.handler(args))
        except (ValueError, OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"citygap: {error}") from error


if __name__ == "__main__":
    main()
