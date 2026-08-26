"""Transactional PostGIS loader for streaming CityGML events."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.citygap_platform import __version__

from .citygml import FeatureEnd, FeatureStart, GeometryPart, iter_citygml_events
from .inventory import THEME_PATTERN


@dataclass(frozen=True)
class DatasetMetadata:
    city_id: str
    city_name: str
    dataset_year: int
    dataset_name: str
    product_specification_version: str
    ade_schema_version: str | None
    source_url: str | None = None
    published_at: str | None = None


def archive_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first(attributes: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = attributes.get(key)
        if isinstance(value, list):
            return str(value[0]) if value else None
        if value is not None:
            return str(value)
    return None


def _number(attributes: dict[str, Any], *keys: str) -> float | None:
    value = _first(attributes, *keys)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _integer(attributes: dict[str, Any], *keys: str) -> int | None:
    value = _number(attributes, *keys)
    return int(value) if value is not None else None


def _insert_typed_row(
    connection: Any,
    theme: str,
    object_id: int,
    feature_type: str,
    end: FeatureEnd,
) -> None:
    attributes = end.attributes
    if theme == "bldg":
        connection.execute(
            """INSERT INTO plateau_buildings (
                   city_object_id, usage_code, measured_height_m,
                   storeys_above_ground, storeys_below_ground,
                   building_area_m2, floor_area_m2
               ) VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (city_object_id) DO UPDATE SET
                   usage_code = EXCLUDED.usage_code,
                   measured_height_m = EXCLUDED.measured_height_m,
                   storeys_above_ground = EXCLUDED.storeys_above_ground,
                   storeys_below_ground = EXCLUDED.storeys_below_ground,
                   building_area_m2 = EXCLUDED.building_area_m2,
                   floor_area_m2 = EXCLUDED.floor_area_m2""",
            (
                object_id,
                _first(attributes, "usage"),
                _number(attributes, "measuredHeight"),
                _integer(attributes, "storeysAboveGround"),
                _integer(attributes, "storeysBelowGround"),
                _number(attributes, "buildingArea", "buildingFootprintArea"),
                _number(attributes, "floorArea", "totalFloorArea"),
            ),
        )
    elif theme == "tran":
        connection.execute(
            """INSERT INTO plateau_roads
                   (city_object_id, road_class, function_code, usage_code, name)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (city_object_id) DO UPDATE SET
                   road_class = EXCLUDED.road_class,
                   function_code = EXCLUDED.function_code,
                   usage_code = EXCLUDED.usage_code,
                   name = EXCLUDED.name""",
            (
                object_id,
                _first(attributes, "class"),
                _first(attributes, "function"),
                _first(attributes, "usage"),
                _first(attributes, "name"),
            ),
        )
    elif theme == "dem":
        connection.execute(
            """INSERT INTO plateau_terrain (city_object_id, relief_component_type)
               VALUES (%s, %s) ON CONFLICT (city_object_id) DO UPDATE SET
               relief_component_type = EXCLUDED.relief_component_type""",
            (object_id, _first(attributes, "lod")),
        )
    elif theme == "luse":
        connection.execute(
            """INSERT INTO plateau_landuse
                   (city_object_id, class_code, function_code, usage_code, area_m2)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (city_object_id) DO UPDATE SET
                   class_code = EXCLUDED.class_code,
                   function_code = EXCLUDED.function_code,
                   usage_code = EXCLUDED.usage_code,
                   area_m2 = EXCLUDED.area_m2""",
            (
                object_id,
                _first(attributes, "class"),
                _first(attributes, "function"),
                _first(attributes, "usage"),
                _number(attributes, "areaInSquareMeter"),
            ),
        )
    elif theme == "urf":
        connection.execute(
            """INSERT INTO plateau_urban_planning
                   (city_object_id, planning_type, function_code, usage_code, name)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (city_object_id) DO UPDATE SET
                   planning_type = EXCLUDED.planning_type,
                   function_code = EXCLUDED.function_code,
                   usage_code = EXCLUDED.usage_code,
                   name = EXCLUDED.name""",
            (
                object_id,
                feature_type,
                _first(attributes, "function"),
                _first(attributes, "usage"),
                _first(attributes, "name"),
            ),
        )
    elif theme in {"fld", "tnm", "lsld"}:
        rank_code = (
            _first(attributes, "areaType") if theme == "lsld" else _first(attributes, "rankOrg")
        )
        connection.execute(
            """INSERT INTO plateau_hazards
                   (city_object_id, hazard_type, rank_code, rank_description, depth_m)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (city_object_id) DO UPDATE SET
                   hazard_type = EXCLUDED.hazard_type,
                   rank_code = EXCLUDED.rank_code,
                   rank_description = EXCLUDED.rank_description,
                   depth_m = EXCLUDED.depth_m""",
            (
                object_id,
                {"fld": "flood", "tnm": "tsunami", "lsld": "landslide"}[theme],
                rank_code,
                None,
                _number(attributes, "depth", "maxDepth"),
            ),
        )


def _finish_feature(
    connection: Any,
    object_id: int,
    theme: str,
    feature_type: str,
    end: FeatureEnd,
) -> None:
    from psycopg.types.json import Jsonb

    connection.execute(
        """UPDATE plateau_city_objects AS object SET
               lods = %s,
               source_crs = %s,
               attributes = %s,
               geometry_envelope = aggregate.envelope,
               representative_point = CASE
                   WHEN aggregate.envelope IS NULL THEN NULL
                   ELSE ST_PointOnSurface(aggregate.envelope)
               END
           FROM (
               SELECT ST_Envelope(ST_Collect(ST_Force2D(geom))) AS envelope
               FROM plateau_geometry_parts WHERE city_object_id = %s
           ) AS aggregate
           WHERE object.id = %s""",
        (list(end.lods), list(end.source_crs), Jsonb(end.attributes), object_id, object_id),
    )
    _insert_typed_row(connection, theme, object_id, feature_type, end)


def _flush_geometry_parts(connection: Any, rows: list[tuple]) -> None:
    if not rows:
        return
    with connection.cursor().copy(
        """COPY plateau_geometry_parts
               (city_object_id, part_order, role, geometry_type, lod, source_crs, geom)
           FROM STDIN"""
    ) as copy:
        for row in rows:
            copy.write_row(row)
    rows.clear()


def _finish_pending_features(
    connection: Any, pending: list[tuple[int, str, str, FeatureEnd]]
) -> None:
    for object_id, theme, feature_type, end in pending:
        _finish_feature(connection, object_id, theme, feature_type, end)
    pending.clear()


def ingest_archive(
    archive_path: str | Path,
    database_url: str,
    metadata: DatasetMetadata,
) -> dict[str, int | str]:
    """Ingest an archive, committing each source member as a restart boundary."""

    import psycopg

    archive = Path(archive_path)
    digest = archive_sha256(archive)
    counts = {"members": 0, "features": 0, "geometry_parts": 0}

    with psycopg.connect(database_url) as connection:
        version_id = connection.execute(
            """INSERT INTO city_dataset_versions (
                   city_id, city_name, dataset_year, dataset_name,
                   product_specification_version, ade_schema_version,
                   archive_file_name, archive_sha256, archive_size_bytes,
                   source_url, published_at, is_current
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false)
               ON CONFLICT (city_id, dataset_year, archive_sha256) DO UPDATE SET
                   dataset_name = EXCLUDED.dataset_name,
                   product_specification_version = EXCLUDED.product_specification_version,
                   ade_schema_version = EXCLUDED.ade_schema_version
               RETURNING id""",
            (
                metadata.city_id,
                metadata.city_name,
                metadata.dataset_year,
                metadata.dataset_name,
                metadata.product_specification_version,
                metadata.ade_schema_version,
                archive.name,
                digest,
                archive.stat().st_size,
                metadata.source_url,
                metadata.published_at,
            ),
        ).fetchone()[0]
        connection.execute(
            "UPDATE city_dataset_versions SET is_current = false WHERE city_id = %s AND id <> %s",
            (metadata.city_id, version_id),
        )
        connection.execute(
            "UPDATE city_dataset_versions SET is_current = true WHERE id = %s", (version_id,)
        )
        run_id = connection.execute(
            """INSERT INTO ingestion_runs
                   (dataset_version_id, parser_version, status)
               VALUES (%s, %s, 'running') RETURNING id""",
            (version_id, __version__),
        ).fetchone()[0]
        connection.commit()

        try:
            with zipfile.ZipFile(archive) as source_zip:
                for info in source_zip.infolist():
                    normalized = "/" + info.filename.replace("\\", "/")
                    match = THEME_PATTERN.search(normalized)
                    if not match:
                        continue
                    theme = match.group(1).lower()
                    object_id: int | None = None
                    feature_type: str | None = None
                    part_order = 0
                    geometry_rows: list[tuple] = []
                    pending_features: list[tuple[int, str, str, FeatureEnd]] = []
                    with source_zip.open(info) as stream:
                        for event in iter_citygml_events(
                            stream,
                            theme=theme,
                            source_member=info.filename,
                            source_member_crc32=f"{info.CRC:08x}",
                        ):
                            if isinstance(event, FeatureStart):
                                feature_type = event.feature_type
                                object_id = connection.execute(
                                    """INSERT INTO plateau_city_objects (
                                           dataset_version_id, ingestion_run_id, gml_id,
                                           theme, feature_type, source_member, source_member_crc32
                                       ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                       ON CONFLICT (dataset_version_id, gml_id) DO UPDATE SET
                                           ingestion_run_id = EXCLUDED.ingestion_run_id,
                                           theme = EXCLUDED.theme,
                                           feature_type = EXCLUDED.feature_type,
                                           source_member = EXCLUDED.source_member,
                                           source_member_crc32 = EXCLUDED.source_member_crc32
                                       RETURNING id""",
                                    (
                                        version_id,
                                        run_id,
                                        event.gml_id,
                                        event.theme,
                                        event.feature_type,
                                        event.source_member,
                                        event.source_member_crc32,
                                    ),
                                ).fetchone()[0]
                                connection.execute(
                                    "DELETE FROM plateau_geometry_parts WHERE city_object_id = %s",
                                    (object_id,),
                                )
                                counts["features"] += 1
                                part_order = 0
                            elif isinstance(event, GeometryPart) and object_id is not None:
                                geometry_rows.append(
                                    (
                                        object_id,
                                        part_order,
                                        event.role,
                                        event.geometry_type,
                                        event.lod,
                                        event.source_crs,
                                        event.ewkt,
                                    )
                                )
                                counts["geometry_parts"] += 1
                                part_order += 1
                                if len(geometry_rows) >= 10_000:
                                    _flush_geometry_parts(connection, geometry_rows)
                                    _finish_pending_features(connection, pending_features)
                            elif (
                                isinstance(event, FeatureEnd)
                                and object_id is not None
                                and feature_type is not None
                            ):
                                pending_features.append((object_id, theme, feature_type, event))
                                object_id = None
                                feature_type = None
                    _flush_geometry_parts(connection, geometry_rows)
                    _finish_pending_features(connection, pending_features)
                    counts["members"] += 1
                    connection.execute(
                        """UPDATE ingestion_runs SET
                               processed_members = %s, processed_features = %s,
                               processed_geometry_parts = %s WHERE id = %s""",
                        (counts["members"], counts["features"], counts["geometry_parts"], run_id),
                    )
                    connection.commit()

            connection.execute(
                """UPDATE ingestion_runs SET status = 'completed', completed_at = now(),
                       processed_members = %s, processed_features = %s,
                       processed_geometry_parts = %s WHERE id = %s""",
                (counts["members"], counts["features"], counts["geometry_parts"], run_id),
            )
            connection.commit()
        except Exception as error:
            connection.rollback()
            connection.execute(
                """UPDATE ingestion_runs SET status = 'failed', completed_at = now(),
                       error_message = %s WHERE id = %s""",
                (str(error)[:4000], run_id),
            )
            connection.commit()
            raise

    return {**counts, "dataset_version_id": str(version_id), "ingestion_run_id": str(run_id)}
