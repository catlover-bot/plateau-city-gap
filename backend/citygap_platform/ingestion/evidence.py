"""Validate generated evidence artifacts and register them against exact scenarios."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_evidence_manifest(
    manifest_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Path], str, tuple[str, ...]]:
    """Resolve only same-directory files whose bytes match the declared manifest."""

    path = Path(manifest_path).resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Evidence manifest must be a regular non-symlink file")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    formats = manifest.get("formats")
    if not isinstance(formats, dict) or not formats:
        raise ValueError("Evidence manifest has no declared formats")
    artifacts: dict[str, Path] = {}
    for export_format, detail in formats.items():
        if export_format not in {"json", "csv", "html"} or not isinstance(detail, dict):
            raise ValueError(f"Unsupported evidence format: {export_format}")
        expected_size = detail.get("size_bytes", detail.get("bytes"))
        expected_hash = detail.get("sha256")
        if not isinstance(expected_size, int) or expected_size <= 0:
            raise ValueError(f"Evidence size is invalid: {export_format}")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ValueError(f"Evidence SHA-256 is invalid: {export_format}")
        matches = [
            candidate.resolve()
            for candidate in path.parent.iterdir()
            if candidate.is_file()
            and not candidate.is_symlink()
            and candidate != path
            and candidate.stat().st_size == expected_size
            and _sha256(candidate) == expected_hash
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Evidence manifest must resolve exactly one {export_format} artifact"
            )
        artifacts[export_format] = matches[0]

    plan_ids = manifest.get("plan_ids")
    if plan_ids is None and manifest.get("plan_id"):
        plan_ids = [manifest["plan_id"]]
    if (
        not isinstance(plan_ids, list)
        or not plan_ids
        or any(not isinstance(value, str) or not value for value in plan_ids)
        or len(plan_ids) != len(set(plan_ids))
    ):
        raise ValueError("Evidence manifest requires distinct scenario plan IDs")

    if "json" not in artifacts:
        raise ValueError("Evidence manifest requires a JSON artifact")
    json_artifact = json.loads(artifacts["json"].read_text(encoding="utf-8"))
    if "comparison" in json_artifact:
        version_keys = {
            item["versions"]["dataset_version_key"] for item in json_artifact["comparison"]
        }
    else:
        version_keys = {json_artifact["versions"]["dataset_version_key"]}
    if len(version_keys) != 1:
        raise ValueError("Evidence scenarios must use one exact dataset version")
    dataset_version_key = str(version_keys.pop())
    parts = dataset_version_key.split(":", 2)
    if len(parts) != 3 or not parts[1].isdigit() or len(parts[2]) != 64:
        raise ValueError("Evidence dataset version key is invalid")
    return manifest, artifacts, dataset_version_key, tuple(plan_ids)


def register_evidence_manifest(database_url: str, manifest_path: str | Path) -> dict[str, Any]:
    """Register verified artifact bytes and audit newly persisted exports atomically."""

    import psycopg

    from backend.citygap_platform.api.repository import PostGISRepository

    manifest, artifacts, dataset_key, plan_ids = validate_evidence_manifest(manifest_path)
    city_id, dataset_year, archive_sha256 = dataset_key.split(":", 2)
    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            """SELECT scenario.id, scenario.scenario_key
               FROM scenario_runs AS scenario
               JOIN city_dataset_versions AS version
                 ON version.id=scenario.dataset_version_id
               WHERE version.city_id=%s AND version.dataset_year=%s
                 AND version.archive_sha256=%s
                 AND scenario.scenario_key=ANY(%s)
               ORDER BY scenario.scenario_key""",
            (city_id, int(dataset_year), archive_sha256, list(plan_ids)),
        ).fetchall()
        found = {str(row[1]): row[0] for row in rows}
        if set(found) != set(plan_ids):
            raise RuntimeError("Exact evidence scenarios are not loaded in PostGIS")

        inserted = 0
        reused = 0
        manifest_digest = _sha256(Path(manifest_path).resolve())
        for plan_id in plan_ids:
            scenario_id = found[plan_id]
            for export_format, artifact in sorted(artifacts.items()):
                artifact_digest = _sha256(artifact)
                export_id = connection.execute(
                    """INSERT INTO evidence_exports (
                           scenario_run_id, export_format, artifact_path,
                           artifact_sha256, generated_at, metadata
                       ) VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (scenario_run_id, export_format, artifact_sha256)
                       DO NOTHING RETURNING id""",
                    (
                        scenario_id,
                        export_format,
                        str(artifact),
                        artifact_digest,
                        manifest["generated_at"],
                        json.dumps(
                            {
                                "schema_version": manifest.get("schema_version"),
                                "manifest_sha256": manifest_digest,
                                "plan_ids": list(plan_ids),
                            },
                            ensure_ascii=False,
                        ),
                    ),
                ).fetchone()
                if export_id is None:
                    reused += 1
                    continue
                inserted += 1
                PostGISRepository._audit(
                    connection,
                    "evidence.export",
                    "evidence_export",
                    str(export_id[0]),
                    city_id,
                    None,
                    {
                        "scenario_id": str(scenario_id),
                        "scenario_key": plan_id,
                        "format": export_format,
                        "artifact_sha256": artifact_digest,
                        "manifest_sha256": manifest_digest,
                    },
                )
        connection.commit()
    return {
        "database_executed": True,
        "dataset_version_key": dataset_key,
        "scenario_count": len(plan_ids),
        "artifact_formats": sorted(artifacts),
        "inserted_rows": inserted,
        "reused_rows": reused,
    }
