"""Small query boundary that keeps HTTP and PostGIS concerns separate."""

from __future__ import annotations

import json
from typing import Any, Protocol


class PlatformRepository(Protocol):
    def health(self) -> bool: ...

    def cities(self) -> list[dict[str, Any]]: ...

    def layers(self, city_id: str) -> list[dict[str, Any]]: ...

    def buildings(
        self, city_id: str, bbox: tuple[float, float, float, float], limit: int, offset: int
    ) -> list[dict[str, Any]]: ...


class PostGISRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    def health(self) -> bool:
        import psycopg

        try:
            with self._connect() as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except (psycopg.Error, OSError):
            return False

    def cities(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT city_id, city_name, dataset_year, dataset_name,
                          product_specification_version, ade_schema_version,
                          archive_sha256, created_at
                   FROM city_dataset_versions WHERE is_current
                   ORDER BY city_id"""
            ).fetchall()
        keys = (
            "city_id",
            "city_name",
            "dataset_year",
            "dataset_name",
            "product_specification_version",
            "ade_schema_version",
            "archive_sha256",
            "created_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def layers(self, city_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT object.theme, object.feature_type, count(*) AS feature_count,
                          count(object.geometry_envelope) AS geometry_count,
                          min(object.ingested_at) AS ingested_at
                   FROM plateau_city_objects AS object
                   JOIN city_dataset_versions AS version
                     ON version.id = object.dataset_version_id
                   WHERE version.city_id = %s AND version.is_current
                   GROUP BY object.theme, object.feature_type
                   ORDER BY object.theme, object.feature_type""",
                (city_id,),
            ).fetchall()
        keys = ("theme", "feature_type", "feature_count", "geometry_count", "ingested_at")
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def buildings(
        self,
        city_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        min_x, min_y, max_x, max_y = bbox
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT object.gml_id, building.usage_code,
                          building.measured_height_m, building.storeys_above_ground,
                          building.storeys_below_ground, building.building_area_m2,
                          building.floor_area_m2, object.lods,
                          ST_AsGeoJSON(object.representative_point),
                          object.source_member, object.source_member_crc32
                   FROM plateau_buildings AS building
                   JOIN plateau_city_objects AS object ON object.id = building.city_object_id
                   JOIN city_dataset_versions AS version
                     ON version.id = object.dataset_version_id
                   WHERE version.city_id = %s AND version.is_current
                     AND object.geometry_envelope && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                   ORDER BY object.gml_id LIMIT %s OFFSET %s""",
                (city_id, min_x, min_y, max_x, max_y, limit, offset),
            ).fetchall()
        keys = (
            "gml_id",
            "usage",
            "measured_height_m",
            "storeys_above_ground",
            "storeys_below_ground",
            "building_area_m2",
            "floor_area_m2",
            "lods",
            "representative_point",
            "source_file",
            "source_file_crc32",
        )
        results = [dict(zip(keys, row, strict=True)) for row in rows]
        for result in results:
            point = result["representative_point"]
            result["representative_point"] = json.loads(point) if point else None
        return results
