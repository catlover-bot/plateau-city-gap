"""Small query boundary that keeps HTTP and PostGIS concerns separate."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from backend.citygap_platform.database.migrations import checksum, migration_files
from backend.citygap_platform.domain.jobs import (
    JobSnapshot,
    JobState,
    advance_job,
    fail_job,
    start_job,
    succeed_job,
)
from backend.citygap_platform.domain.scenarios import validate_status_transition
from backend.citygap_platform.observability import current_request_context


class PlatformRepository(Protocol):
    def health(self) -> bool: ...

    def readiness(self, required_city_id: str | None) -> dict[str, Any]: ...

    def cities(self) -> list[dict[str, Any]]: ...

    def layers(self, city_id: str) -> list[dict[str, Any]]: ...

    def urban_states(
        self, city_id: str, lifecycle_status: str | None, limit: int
    ) -> list[dict[str, Any]]: ...

    def urban_state_detail(self, city_id: str, state_id: str) -> dict[str, Any] | None: ...

    def state_changes(
        self,
        city_id: str,
        from_state_id: str,
        to_state_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> dict[str, Any]: ...

    def buildings(
        self, city_id: str, bbox: tuple[float, float, float, float], limit: int, offset: int
    ) -> list[dict[str, Any]]: ...

    def mesh_detail(self, city_id: str, mesh_code: str) -> dict[str, Any] | None: ...

    def building_detail(self, city_id: str, gml_id: str) -> dict[str, Any] | None: ...

    def building_accessibility(self, city_id: str, gml_id: str) -> dict[str, Any] | None: ...

    def networks(self, city_id: str) -> list[dict[str, Any]]: ...

    def road_edges(
        self,
        city_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
        graph_version: str | None,
    ) -> list[dict[str, Any]]: ...

    def building_network_accessibility(
        self, city_id: str, gml_id: str
    ) -> dict[str, Any] | None: ...

    def context_features(
        self,
        city_id: str,
        layer: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]: ...

    def mesh_context(self, city_id: str, mesh_code: str) -> list[dict[str, Any]]: ...

    def scenario_candidate_context(
        self, city_id: str, candidate_id: str
    ) -> list[dict[str, Any]]: ...

    def road_edge_hazards(
        self, city_id: str, edge_id: str, graph_version: str | None
    ) -> list[dict[str, Any]]: ...

    def scenarios(self, city_id: str, status: str | None, limit: int) -> list[dict[str, Any]]: ...

    def create_stress_test(
        self, city_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None: ...

    def stress_test_detail(self, stress_test_id: str) -> dict[str, Any] | None: ...

    def stress_test_impacts(
        self,
        stress_test_id: str,
        bbox: tuple[float, float, float, float],
        service_category: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]: ...

    def network_criticality(
        self, city_id: str, urban_state_id: str | None, limit: int
    ) -> list[dict[str, Any]]: ...

    def future_states(self, city_id: str) -> list[dict[str, Any]]: ...

    def outcomes(self, city_id: str, limit: int) -> list[dict[str, Any]]: ...

    def scenario_detail(self, city_id: str, scenario_id: str) -> dict[str, Any] | None: ...

    def transition_scenario(
        self,
        city_id: str,
        scenario_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ) -> dict[str, Any] | None: ...

    def field_check(
        self, city_id: str, scenario_id: str, site_order: int
    ) -> dict[str, Any] | None: ...

    def save_field_check(
        self,
        city_id: str,
        scenario_id: str,
        site_order: int,
        checklist: dict[str, Any],
    ) -> dict[str, Any] | None: ...

    def create_field_offline_package(
        self,
        city_id: str,
        urban_state_id: str,
        scenario_run_id: str,
        site_order: int,
        expires_at: str | None,
    ) -> dict[str, Any] | None: ...

    def sync_field_operation(
        self, city_id: str, operation: dict[str, Any]
    ) -> dict[str, Any] | None: ...

    def field_sync_conflict(self, conflict_id: str) -> dict[str, Any] | None: ...

    def resolve_field_sync_conflict(
        self, city_id: str, conflict_id: str, resolution: dict[str, Any]
    ) -> dict[str, Any] | None: ...

    def city_registry(self) -> list[dict[str, Any]]: ...

    def dataset_registry(self, city_id: str) -> list[dict[str, Any]]: ...

    def analysis_runs(self, city_id: str, limit: int) -> list[dict[str, Any]]: ...

    def create_job(
        self,
        city_id: str,
        job_type: str,
        dataset_version_ids: list[str],
        config_hash: str,
        algorithm_version: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any] | None: ...

    def job_detail(self, job_id: str) -> dict[str, Any] | None: ...

    def transition_job(
        self, job_id: str, action: str, stage: str | None, error: str | None
    ) -> dict[str, Any] | None: ...

    def audit_events(self, city_id: str | None, limit: int) -> list[dict[str, Any]]: ...

    def validation_claims(self) -> list[dict[str, Any]]: ...

    def city_validations(self, city_id: str, limit: int, offset: int) -> list[dict[str, Any]]: ...

    def create_validation_run(
        self, city_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None: ...

    def validation_detail(self, validation_id: str) -> dict[str, Any] | None: ...

    def validation_samples(
        self,
        validation_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> dict[str, Any]: ...

    def validation_disagreements(
        self,
        validation_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> dict[str, Any]: ...

    def validation_sensitivity(
        self, validation_id: str, limit: int, offset: int
    ) -> dict[str, Any]: ...

    def create_validation_field_review(
        self, validation_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None: ...

    def update_validation_status(
        self, validation_id: str, expected: str, proposed: str, note: str
    ) -> dict[str, Any] | None: ...

    def register_validation_reference(
        self, city_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None: ...

    def vector_tile(
        self,
        city_id: str,
        layer: str,
        z: int,
        x: int,
        y: int,
        dataset_version_id: str,
        network_version_id: str | None,
        scenario_id: str | None,
        algorithm_version: str | None,
    ) -> bytes: ...

    def admin_snapshot(self) -> dict[str, list[dict[str, Any]]]: ...


class PostGISRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    @staticmethod
    def _audit(
        connection,
        action: str,
        resource_type: str,
        resource_id: str,
        city_id: str | None,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        context = current_request_context()
        connection.execute(
            """INSERT INTO audit_log (
                   actor, action, resource_type, resource_id, city_id, request_id,
                   before_state, after_state
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                context.actor,
                action,
                resource_type,
                resource_id,
                city_id,
                context.request_id,
                json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
                json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
            ),
        )

    def health(self) -> bool:
        import psycopg

        try:
            with self._connect() as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except (psycopg.Error, OSError):
            return False

    def readiness(self, required_city_id: str | None) -> dict[str, Any]:
        import psycopg

        checks: dict[str, bool] = {
            "database": False,
            "migrations": False,
            "extensions": False,
            "required_dataset": False,
            "network_version": False,
            "scenario_store": False,
        }
        details: dict[str, Any] = {"required_city_id": required_city_id}
        try:
            with self._connect() as connection:
                checks["database"] = connection.execute("SELECT 1").fetchone() == (1,)
                expected_migrations = {
                    path.name: checksum(path) for path in migration_files("infra/migrations")
                }
                applied_migrations = {
                    str(row[0]): str(row[1]).strip()
                    for row in connection.execute(
                        "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY version"
                    ).fetchall()
                }
                migration_problems = [
                    f"missing:{name}"
                    for name in expected_migrations.keys() - applied_migrations.keys()
                ]
                migration_problems.extend(
                    f"unexpected:{name}"
                    for name in applied_migrations.keys() - expected_migrations.keys()
                )
                migration_problems.extend(
                    f"checksum:{name}"
                    for name in expected_migrations.keys() & applied_migrations.keys()
                    if expected_migrations[name] != applied_migrations[name]
                )
                checks["migrations"] = not migration_problems
                details["migration_count"] = {
                    "expected": len(expected_migrations),
                    "applied": len(applied_migrations),
                }
                details["migration_problems"] = sorted(migration_problems)
                extensions = {
                    row[0]
                    for row in connection.execute(
                        "SELECT extname FROM pg_extension WHERE extname IN ('postgis','pgrouting')"
                    ).fetchall()
                }
                checks["extensions"] = extensions == {"postgis", "pgrouting"}
                details["extensions"] = sorted(extensions)
                dataset = connection.execute(
                    """SELECT version.id FROM city_dataset_versions AS version
                       WHERE version.is_current
                         AND (CAST(%s AS text) IS NULL OR version.city_id = %s)
                         AND EXISTS (
                             SELECT 1 FROM ingestion_runs AS ingestion
                             WHERE ingestion.dataset_version_id=version.id
                               AND ingestion.status='completed'
                         )
                       ORDER BY version.created_at DESC LIMIT 1""",
                    (required_city_id, required_city_id),
                ).fetchone()
                checks["required_dataset"] = dataset is not None
                if dataset:
                    checks["network_version"] = (
                        connection.execute(
                            "SELECT EXISTS(SELECT 1 FROM road_network_versions WHERE dataset_version_id=%s)",
                            (dataset[0],),
                        ).fetchone()[0]
                        is True
                    )
                checks["scenario_store"] = connection.execute(
                    "SELECT to_regclass('public.scenario_runs') IS NOT NULL"
                ).fetchone()[0]
        except (psycopg.Error, OSError) as error:
            details["error"] = type(error).__name__
        return {
            "status": "ready" if all(checks.values()) else "not_ready",
            "ready": all(checks.values()),
            "checks": checks,
            "details": details,
        }

    def urban_states(
        self, city_id: str, lifecycle_status: str | None, limit: int
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT state.id, state.state_key, state.label, state.effective_date,
                          state.state_type, state.lifecycle_status, state.base_state_id,
                          state.primary_plateau_dataset_version_id, state.source_verified,
                          state.population_model, state.fixed_service_assumption,
                          state.validated_at, state.updated_at
                   FROM urban_states AS state
                   JOIN cities AS city ON city.id = state.city_id
                   WHERE (city.city_code = %s OR city.city_key = %s)
                     AND (CAST(%s AS text) IS NULL OR state.lifecycle_status = %s)
                   ORDER BY state.effective_date DESC, state.state_key
                   LIMIT %s""",
                (city_id, city_id, lifecycle_status, lifecycle_status, limit),
            ).fetchall()
        keys = (
            "urban_state_id",
            "state_key",
            "label",
            "effective_date",
            "state_type",
            "lifecycle_status",
            "base_urban_state_id",
            "primary_plateau_dataset_version_id",
            "source_verified",
            "population_model",
            "fixed_service_assumption",
            "validated_at",
            "updated_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def urban_state_detail(self, city_id: str, state_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT state.id, state.state_key, state.label, state.effective_date,
                          state.state_type, state.lifecycle_status, state.base_state_id,
                          state.primary_plateau_dataset_version_id, state.source_verified,
                          state.population_model, state.fixed_service_assumption,
                          state.validation_report, state.created_by, state.created_at,
                          state.validated_at, state.updated_at
                   FROM urban_states AS state
                   JOIN cities AS city ON city.id = state.city_id
                   WHERE (city.city_code = %s OR city.city_key = %s) AND state.id = %s""",
                (city_id, city_id, state_id),
            ).fetchone()
            if row is None:
                return None
            dataset_rows = connection.execute(
                """SELECT dataset_role, dataset_version_id, source_verified,
                          metadata, attached_at
                   FROM state_dataset_versions WHERE urban_state_id = %s
                   ORDER BY dataset_role, dataset_version_id""",
                (state_id,),
            ).fetchall()
            network_rows = connection.execute(
                """SELECT link.network_version_id, link.purpose, network.graph_version,
                          network.network_type, network.pedestrian_network,
                          network.route_semantics, network.node_count, network.edge_count
                   FROM state_network_versions AS link
                   JOIN road_network_versions AS network ON network.id = link.network_version_id
                   WHERE link.urban_state_id = %s
                   ORDER BY link.purpose, network.graph_version""",
                (state_id,),
            ).fetchall()
            analysis_rows = connection.execute(
                """SELECT link.analysis_run_id, link.result_role, run.analysis_type,
                          run.status, run.config_hash, run.output_sha256
                   FROM state_analysis_runs AS link
                   JOIN analysis_runs AS run ON run.id = link.analysis_run_id
                   WHERE link.urban_state_id = %s
                   ORDER BY run.analysis_type, link.analysis_run_id""",
                (state_id,),
            ).fetchall()
        state_keys = (
            "urban_state_id",
            "state_key",
            "label",
            "effective_date",
            "state_type",
            "lifecycle_status",
            "base_urban_state_id",
            "primary_plateau_dataset_version_id",
            "source_verified",
            "population_model",
            "fixed_service_assumption",
            "validation_report",
            "created_by",
            "created_at",
            "validated_at",
            "updated_at",
        )
        dataset_keys = (
            "dataset_role",
            "dataset_version_id",
            "source_verified",
            "metadata",
            "attached_at",
        )
        network_keys = (
            "network_version_id",
            "purpose",
            "graph_version",
            "network_type",
            "pedestrian_network",
            "route_semantics",
            "node_count",
            "edge_count",
        )
        analysis_keys = (
            "analysis_run_id",
            "result_role",
            "analysis_type",
            "status",
            "config_hash",
            "output_sha256",
        )
        return {
            "city_id": city_id,
            **dict(zip(state_keys, row, strict=True)),
            "dataset_versions": [
                dict(zip(dataset_keys, item, strict=True)) for item in dataset_rows
            ],
            "network_versions": [
                dict(zip(network_keys, item, strict=True)) for item in network_rows
            ],
            "analysis_runs": [
                dict(zip(analysis_keys, item, strict=True)) for item in analysis_rows
            ],
            "provenance": (
                "result -> urban_state -> dataset/PLATEAU/network versions -> algorithm"
            ),
        }

    def state_changes(
        self,
        city_id: str,
        from_state_id: str,
        to_state_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            change_set = connection.execute(
                """SELECT change_set.id, change_set.status, change_set.algorithm_version,
                          change_set.summary, change_set.completed_at
                   FROM urban_state_change_sets AS change_set
                   JOIN cities AS city ON city.id = change_set.city_id
                   WHERE (city.city_code = %s OR city.city_key = %s)
                     AND change_set.from_urban_state_id = %s
                     AND change_set.to_urban_state_id = %s
                   ORDER BY change_set.created_at DESC LIMIT 1""",
                (city_id, city_id, from_state_id, to_state_id),
            ).fetchone()
            if change_set is None:
                return {
                    "city_id": city_id,
                    "from_urban_state_id": from_state_id,
                    "to_urban_state_id": to_state_id,
                    "change_set": None,
                    "features": [],
                }
            rows = connection.execute(
                """SELECT change.feature_key, change.before_gml_id, change.after_gml_id,
                          change.feature_type, change.change_type, change.matched_by,
                          change.important_attribute_changes,
                          ST_AsGeoJSON(change.affected_envelope)::jsonb
                   FROM urban_state_feature_changes AS change
                   WHERE change.change_set_id = %s
                     AND change.affected_envelope IS NOT NULL
                     AND ST_Intersects(
                         change.affected_envelope,
                         ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                     )
                   ORDER BY change.feature_type, change.change_type, change.feature_key
                   LIMIT %s OFFSET %s""",
                (change_set[0], *bbox, limit, offset),
            ).fetchall()
        keys = (
            "feature_key",
            "before_gml_id",
            "after_gml_id",
            "feature_type",
            "change_type",
            "matched_by",
            "important_attribute_changes",
            "geometry",
        )
        return {
            "city_id": city_id,
            "from_urban_state_id": from_state_id,
            "to_urban_state_id": to_state_id,
            "bbox": bbox,
            "change_set": {
                "change_set_id": change_set[0],
                "status": change_set[1],
                "algorithm_version": change_set[2],
                "summary": change_set[3],
                "completed_at": change_set[4],
            },
            "features": [dict(zip(keys, row, strict=True)) for row in rows],
            "limit": limit,
            "offset": offset,
        }

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

    def mesh_detail(self, city_id: str, mesh_code: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT demographics.mesh_code,
                          count(DISTINCT demographics.building_gml_id),
                          sum(demographics.estimated_population),
                          sum(demographics.estimated_elderly_population),
                          min(demographics.source_population_year)
                   FROM building_demographics AS demographics
                   JOIN city_dataset_versions AS version
                     ON version.id = demographics.dataset_version_id
                   WHERE version.city_id = %s AND version.is_current
                     AND demographics.mesh_code = %s
                   GROUP BY demographics.mesh_code""",
                (city_id, mesh_code),
            ).fetchone()
        if row is None:
            return None
        keys = (
            "mesh_code",
            "residential_building_count",
            "estimated_population",
            "estimated_elderly_population",
            "source_population_year",
        )
        return dict(zip(keys, row, strict=True))

    def building_detail(self, city_id: str, gml_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT object.gml_id, building.usage_code, building.measured_height_m,
                          building.storeys_above_ground, building.storeys_below_ground,
                          building.building_area_m2, building.floor_area_m2, object.lods,
                          object.source_member, object.source_member_crc32,
                          version.dataset_year, version.product_specification_version,
                          version.archive_sha256,
                          COALESCE(jsonb_agg(jsonb_build_object(
                              'mesh_code', demographics.mesh_code,
                              'estimated_population', demographics.estimated_population,
                              'estimated_elderly_population',
                                  demographics.estimated_elderly_population,
                              'allocation_method', demographics.allocation_method,
                              'allocation_weight', demographics.allocation_weight,
                              'allocation_fraction', demographics.allocation_fraction,
                              'population_resolution', demographics.population_resolution
                          )) FILTER (WHERE demographics.mesh_code IS NOT NULL), '[]'::jsonb)
                   FROM plateau_city_objects AS object
                   JOIN plateau_buildings AS building ON building.city_object_id = object.id
                   JOIN city_dataset_versions AS version ON version.id = object.dataset_version_id
                   LEFT JOIN building_demographics AS demographics
                     ON demographics.dataset_version_id = object.dataset_version_id
                    AND demographics.building_gml_id = object.gml_id
                   WHERE version.city_id = %s AND version.is_current AND object.gml_id = %s
                   GROUP BY object.id, building.city_object_id, version.id""",
                (city_id, gml_id),
            ).fetchone()
        if row is None:
            return None
        keys = (
            "gml_id",
            "usage",
            "measured_height_m",
            "storeys_above_ground",
            "storeys_below_ground",
            "building_area_m2",
            "floor_area_m2",
            "lods",
            "source_file",
            "source_file_crc32",
            "dataset_year",
            "plateau_specification_version",
            "archive_sha256",
            "estimated_demographics",
        )
        return dict(zip(keys, row, strict=True))

    def building_accessibility(self, city_id: str, gml_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT accessibility.facility_policy,
                          accessibility.nearest_transport_type,
                          accessibility.nearest_transport_name,
                          accessibility.nearest_transport_distance_m,
                          accessibility.nearest_medical_name,
                          accessibility.nearest_medical_distance_m,
                          accessibility.origin_method, accessibility.calculated_at
                   FROM building_accessibility AS accessibility
                   JOIN city_dataset_versions AS version
                     ON version.id = accessibility.dataset_version_id
                   WHERE version.city_id = %s AND version.is_current
                     AND accessibility.building_gml_id = %s
                   ORDER BY accessibility.facility_policy""",
                (city_id, gml_id),
            ).fetchall()
        if not rows:
            return None
        keys = (
            "facility_policy",
            "nearest_transport_type",
            "nearest_transport_name",
            "nearest_transport_distance_m",
            "nearest_medical_name",
            "nearest_medical_distance_m",
            "origin_method",
            "calculated_at",
        )
        return {
            "gml_id": gml_id,
            "policies": [dict(zip(keys, row, strict=True)) for row in rows],
        }

    def networks(self, city_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT network.graph_version, network.graph_method,
                          network.network_type, network.source_type,
                          network.official_generator_executed,
                          network.pedestrian_network, network.route_semantics,
                          network.node_count, network.edge_count, network.component_count,
                          network.terrain_method, network.terrain_node_coverage,
                          network.generated_at, network.config_hash
                   FROM road_network_versions AS network
                   JOIN city_dataset_versions AS version
                     ON version.id = network.dataset_version_id
                   WHERE version.city_id = %s AND version.is_current
                   ORDER BY network.generated_at DESC, network.graph_version""",
                (city_id,),
            ).fetchall()
        keys = (
            "graph_version",
            "graph_method",
            "network_type",
            "source_type",
            "official_generator_executed",
            "pedestrian_network",
            "route_semantics",
            "node_count",
            "edge_count",
            "component_count",
            "terrain_method",
            "terrain_node_coverage",
            "generated_at",
            "config_hash",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def road_edges(
        self,
        city_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
        graph_version: str | None,
    ) -> list[dict[str, Any]]:
        min_x, min_y, max_x, max_y = bbox
        with self._connect() as connection:
            rows = connection.execute(
                """WITH selected_network AS (
                       SELECT network.id, network.graph_version, network.route_semantics,
                              network.pedestrian_network
                       FROM road_network_versions AS network
                       JOIN city_dataset_versions AS version
                         ON version.id = network.dataset_version_id
                       WHERE version.city_id = %s AND version.is_current
                         AND (CAST(%s AS text) IS NULL OR network.graph_version = %s)
                       ORDER BY network.generated_at DESC LIMIT 1
                   )
                   SELECT edge.edge_id, edge.source_node_id, edge.target_node_id,
                          edge.length_m, edge.topology_relation, edge.surface_gap_m,
                          edge.absolute_grade_percent, selected.graph_version,
                          selected.route_semantics, selected.pedestrian_network,
                          ST_AsGeoJSON(ST_Transform(edge.geom, 4326))
                   FROM road_network_edges AS edge
                   JOIN selected_network AS selected ON selected.id = edge.network_version_id
                   WHERE edge.geom && ST_Transform(
                       ST_MakeEnvelope(%s, %s, %s, %s, 4326), ST_SRID(edge.geom)
                   )
                   ORDER BY edge.edge_id LIMIT %s OFFSET %s""",
                (
                    city_id,
                    graph_version,
                    graph_version,
                    min_x,
                    min_y,
                    max_x,
                    max_y,
                    limit,
                    offset,
                ),
            ).fetchall()
        keys = (
            "edge_id",
            "source_node_id",
            "target_node_id",
            "length_m",
            "topology_relation",
            "surface_gap_m",
            "absolute_grade_percent",
            "graph_version",
            "route_semantics",
            "pedestrian_network",
            "geometry",
        )
        results = [dict(zip(keys, row, strict=True)) for row in rows]
        for result in results:
            result["geometry"] = json.loads(result["geometry"])
        return results

    def building_network_accessibility(self, city_id: str, gml_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT network.graph_version, network.graph_method,
                          network.pedestrian_network, network.route_semantics,
                          accessibility.destination_class,
                          accessibility.destination_facility_key,
                          accessibility.destination_name,
                          accessibility.road_surface_id,
                          accessibility.snapped_node_id,
                          accessibility.building_to_surface_distance_m,
                          accessibility.building_to_node_connector_m,
                          accessibility.network_distance_m,
                          accessibility.terrain_route_status,
                          accessibility.terrain_route_coverage,
                          accessibility.route_ascent_m,
                          accessibility.route_descent_m,
                          accessibility.maximum_absolute_grade_percent,
                          accessibility.algorithm, accessibility.provenance,
                          accessibility.calculated_at
                   FROM building_network_accessibility AS accessibility
                   JOIN road_network_versions AS network
                     ON network.id = accessibility.network_version_id
                   JOIN city_dataset_versions AS version
                     ON version.id = accessibility.dataset_version_id
                   WHERE version.city_id = %s AND version.is_current
                     AND accessibility.building_gml_id = %s
                   ORDER BY network.generated_at DESC, accessibility.destination_class""",
                (city_id, gml_id),
            ).fetchall()
        if not rows:
            return None
        keys = (
            "graph_version",
            "graph_method",
            "pedestrian_network",
            "route_semantics",
            "destination_class",
            "destination_facility_key",
            "destination_name",
            "road_surface_id",
            "snapped_node_id",
            "building_to_surface_distance_m",
            "building_to_node_connector_m",
            "network_distance_m",
            "terrain_route_status",
            "terrain_route_coverage",
            "route_ascent_m",
            "route_descent_m",
            "maximum_absolute_grade_percent",
            "algorithm",
            "provenance",
            "calculated_at",
        )
        return {
            "gml_id": gml_id,
            "routes": [dict(zip(keys, row, strict=True)) for row in rows],
        }

    @staticmethod
    def _context_rows(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        keys = (
            "context_type",
            "gml_id",
            "feature_type",
            "label",
            "code",
            "codelist",
            "measure",
            "review_status",
            "siting_feasibility",
            "source_member",
            "source_member_crc32",
            "geometry_envelope",
        )
        results = [dict(zip(keys, row, strict=True)) for row in rows]
        for result in results:
            geometry = result["geometry_envelope"]
            result["geometry_envelope"] = json.loads(geometry) if geometry else None
        return results

    def context_features(
        self,
        city_id: str,
        layer: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        themes = {
            "landuse": ["luse"],
            "planning": ["urf"],
            "hazards": ["lsld", "fld", "tnm"],
        }[layer]
        min_x, min_y, max_x, max_y = bbox
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT CASE
                              WHEN object.theme = 'luse' THEN 'landuse'
                              WHEN object.theme = 'urf' THEN 'planning'
                              ELSE 'hazard'
                          END,
                          object.gml_id, object.feature_type,
                          COALESCE(landuse.class_label, planning.function_label,
                                   planning.urban_plan_type_label, hazard.rank_description),
                          COALESCE(landuse.class_code, planning.function_code,
                                   planning.urban_plan_type_code, hazard.rank_code),
                          COALESCE(landuse.class_codelist, planning.function_codelist,
                                   planning.urban_plan_type_codelist, hazard.rank_codelist),
                          NULL::double precision, hazard.overlap_policy,
                          CASE WHEN hazard.city_object_id IS NOT NULL
                               THEN 'not_determined' END,
                          object.source_member, object.source_member_crc32,
                          ST_AsGeoJSON(object.geometry_envelope)
                   FROM plateau_city_objects AS object
                   JOIN city_dataset_versions AS version
                     ON version.id = object.dataset_version_id
                   LEFT JOIN plateau_landuse AS landuse
                     ON landuse.city_object_id = object.id
                   LEFT JOIN plateau_urban_planning AS planning
                     ON planning.city_object_id = object.id
                   LEFT JOIN plateau_hazards AS hazard
                     ON hazard.city_object_id = object.id
                   WHERE version.city_id = %s AND version.is_current
                     AND object.theme = ANY(%s)
                     AND object.geometry_envelope &&
                         ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                   ORDER BY object.theme, object.gml_id LIMIT %s OFFSET %s""",
                (city_id, themes, min_x, min_y, max_x, max_y, limit, offset),
            ).fetchall()
        return self._context_rows(rows)

    def mesh_context(self, city_id: str, mesh_code: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT context.context_type, object.gml_id, object.feature_type,
                          COALESCE(landuse.class_label, planning.function_label,
                                   planning.urban_plan_type_label, hazard.rank_description),
                          COALESCE(landuse.class_code, planning.function_code,
                                   planning.urban_plan_type_code, hazard.rank_code),
                          COALESCE(landuse.class_codelist, planning.function_codelist,
                                   planning.urban_plan_type_codelist, hazard.rank_codelist),
                          context.intersection_area_m2, context.review_status,
                          context.siting_feasibility, object.source_member,
                          object.source_member_crc32, NULL::text
                   FROM mesh_spatial_context AS context
                   JOIN spatial_context_runs AS run ON run.id = context.context_run_id
                   JOIN city_dataset_versions AS version
                     ON version.id = run.dataset_version_id
                   JOIN plateau_city_objects AS object
                     ON object.id = context.context_city_object_id
                   LEFT JOIN plateau_landuse AS landuse ON landuse.city_object_id = object.id
                   LEFT JOIN plateau_urban_planning AS planning
                     ON planning.city_object_id = object.id
                   LEFT JOIN plateau_hazards AS hazard ON hazard.city_object_id = object.id
                   WHERE version.city_id = %s AND version.is_current
                     AND context.mesh_code = %s AND run.status = 'succeeded'
                   ORDER BY context.context_type, object.gml_id""",
                (city_id, mesh_code),
            ).fetchall()
        return self._context_rows(rows)

    def scenario_candidate_context(self, city_id: str, candidate_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT context.context_type, object.gml_id, object.feature_type,
                          COALESCE(landuse.class_label, planning.function_label,
                                   planning.urban_plan_type_label, hazard.rank_description),
                          COALESCE(landuse.class_code, planning.function_code,
                                   planning.urban_plan_type_code, hazard.rank_code),
                          COALESCE(landuse.class_codelist, planning.function_codelist,
                                   planning.urban_plan_type_codelist, hazard.rank_codelist),
                          NULL::double precision, context.review_status,
                          context.siting_feasibility, object.source_member,
                          object.source_member_crc32,
                          ST_AsGeoJSON(ST_Transform(context.candidate_geom, 4326))
                   FROM scenario_candidate_spatial_context AS context
                   JOIN spatial_context_runs AS run ON run.id = context.context_run_id
                   JOIN city_dataset_versions AS version
                     ON version.id = run.dataset_version_id
                   JOIN plateau_city_objects AS object
                     ON object.id = context.context_city_object_id
                   LEFT JOIN plateau_landuse AS landuse ON landuse.city_object_id = object.id
                   LEFT JOIN plateau_urban_planning AS planning
                     ON planning.city_object_id = object.id
                   LEFT JOIN plateau_hazards AS hazard ON hazard.city_object_id = object.id
                   WHERE version.city_id = %s AND version.is_current
                     AND context.candidate_id = %s AND run.status = 'succeeded'
                   ORDER BY context.context_type, object.gml_id""",
                (city_id, candidate_id),
            ).fetchall()
        return self._context_rows(rows)

    def road_edge_hazards(
        self, city_id: str, edge_id: str, graph_version: str | None
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT 'hazard', object.gml_id, object.feature_type,
                          hazard.rank_description, hazard.rank_code, hazard.rank_codelist,
                          context.intersection_length_m, context.review_status,
                          context.siting_feasibility, object.source_member,
                          object.source_member_crc32, NULL::text
                   FROM road_hazard_context AS context
                   JOIN spatial_context_runs AS run ON run.id = context.context_run_id
                   JOIN road_network_versions AS network
                     ON network.id = context.network_version_id
                   JOIN city_dataset_versions AS version
                     ON version.id = network.dataset_version_id
                   JOIN plateau_city_objects AS object
                     ON object.id = context.hazard_city_object_id
                   JOIN plateau_hazards AS hazard ON hazard.city_object_id = object.id
                   WHERE version.city_id = %s AND version.is_current
                     AND context.edge_id = %s
                     AND (CAST(%s AS text) IS NULL OR network.graph_version = %s)
                     AND run.status = 'succeeded'
                   ORDER BY network.generated_at DESC, object.gml_id""",
                (city_id, edge_id, graph_version, graph_version),
            ).fetchall()
        return self._context_rows(rows)

    def create_stress_test(
        self, city_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        assumptions = sorted(
            request["assumptions"],
            key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True),
        )
        assumption_payload = json.dumps(
            assumptions, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        assumption_hash = hashlib.sha256(assumption_payload.encode()).hexdigest()
        cache_payload = json.dumps(
            {
                "city": city_id,
                "urban_state": request["base_urban_state_id"],
                "network_version": request["network_version_id"],
                "assumption_hash": assumption_hash,
                "algorithm_version": request["algorithm_version"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        cache_key = hashlib.sha256(cache_payload.encode()).hexdigest()
        context = current_request_context()
        with self._connect() as connection:
            city = connection.execute(
                """SELECT city.id
                   FROM cities AS city
                   JOIN urban_states AS state ON state.city_id = city.id
                   JOIN road_network_versions AS network ON network.id = %s
                   JOIN state_network_versions AS state_network
                     ON state_network.urban_state_id = state.id
                    AND state_network.network_version_id = network.id
                   JOIN city_dataset_versions AS dataset
                     ON dataset.id = network.dataset_version_id
                   WHERE (city.city_code = %s OR city.city_key = %s)
                     AND state.id = %s
                     AND state.lifecycle_status IN ('validated', 'current')
                     AND dataset.city_id = city.city_code""",
                (
                    request["network_version_id"],
                    city_id,
                    city_id,
                    request["base_urban_state_id"],
                ),
            ).fetchone()
            if city is None:
                return None
            hazard_version_ids = {
                assumption.get("hazard_dataset_version_id")
                for assumption in assumptions
                if assumption.get("hazard_dataset_version_id") is not None
            }
            if hazard_version_ids:
                verified_count = connection.execute(
                    """SELECT count(DISTINCT version.id)
                       FROM dataset_versions AS version
                       JOIN datasets AS dataset ON dataset.id = version.dataset_id
                       WHERE dataset.city_id = %s AND version.id = ANY(%s::uuid[])""",
                    (city[0], list(hazard_version_ids)),
                ).fetchone()[0]
                if int(verified_count) != len(hazard_version_ids):
                    raise ValueError(
                        "stress-test hazard datasets must belong to the selected city"
                    )
            cached = connection.execute(
                "SELECT stress_test_run_id FROM stress_test_result_cache WHERE cache_key = %s",
                (cache_key,),
            ).fetchone()
            if cached is not None:
                cached_id = str(cached[0])
            else:
                row = connection.execute(
                    """INSERT INTO stress_test_runs (
                           city_id, base_urban_state_id, network_version_id,
                           stress_test_key, title, stress_test_type, status,
                           assumption_hash, algorithm_version, cache_key,
                           route_semantics, prediction_claimed, limitation, created_by
                       ) VALUES (%s, %s, %s, %s, %s, %s, 'queued', %s, %s, %s, %s,
                                 false, %s, %s)
                       RETURNING id""",
                    (
                        city[0],
                        request["base_urban_state_id"],
                        request["network_version_id"],
                        request["stress_test_key"],
                        request["title"],
                        request["stress_test_type"],
                        assumption_hash,
                        request["algorithm_version"],
                        cache_key,
                        request["route_semantics"],
                        (
                            "This is a counterfactual stress test, not a prediction of "
                            "disaster damage or actual road passability."
                        ),
                        context.actor,
                    ),
                ).fetchone()
                stress_test_id = str(row[0])
                for assumption in assumptions:
                    connection.execute(
                        """INSERT INTO stress_test_assumptions (
                               stress_test_run_id, assumption_type,
                               hazard_dataset_version_id, hazard_type, hazard_class,
                               closure_assumption, assumption_payload,
                               assumption_source, explicitly_confirmed
                           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)""",
                        (
                            stress_test_id,
                            assumption["assumption_type"],
                            assumption.get("hazard_dataset_version_id"),
                            assumption.get("hazard_type"),
                            assumption.get("hazard_class"),
                            assumption["closure_assumption"],
                            json.dumps(
                                assumption.get("assumption_payload", {}), ensure_ascii=False
                            ),
                            assumption["assumption_source"],
                        ),
                    )
                connection.execute(
                    """INSERT INTO stress_test_result_cache (
                           cache_key, city_id, urban_state_id, network_version_id,
                           assumption_hash, algorithm_version, stress_test_run_id
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        cache_key,
                        city[0],
                        request["base_urban_state_id"],
                        request["network_version_id"],
                        assumption_hash,
                        request["algorithm_version"],
                        stress_test_id,
                    ),
                )
                self._audit(
                    connection,
                    "stress_test.assumption.create",
                    "stress_test",
                    stress_test_id,
                    city_id,
                    None,
                    {
                        "status": "queued",
                        "assumption_hash": assumption_hash,
                        "explicit_assumption_count": len(assumptions),
                        "prediction_claimed": False,
                    },
                )
                connection.commit()
                cached_id = stress_test_id
        return self.stress_test_detail(cached_id)

    def stress_test_detail(self, stress_test_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT run.id, city.city_code, run.base_urban_state_id,
                          run.network_version_id, run.stress_test_key, run.title,
                          run.stress_test_type, run.status, run.assumption_hash,
                          run.algorithm_version, run.cache_key, run.route_semantics,
                          run.prediction_claimed, run.limitation, run.created_by,
                          run.created_at, run.started_at, run.completed_at, run.metadata
                   FROM stress_test_runs AS run
                   JOIN cities AS city ON city.id = run.city_id
                   WHERE run.id = %s""",
                (stress_test_id,),
            ).fetchone()
            if row is None:
                return None
            assumptions = connection.execute(
                """SELECT id, assumption_type, hazard_dataset_version_id,
                          hazard_type, hazard_class, closure_assumption,
                          assumption_payload, assumption_source,
                          explicitly_confirmed, created_at
                   FROM stress_test_assumptions WHERE stress_test_run_id = %s
                   ORDER BY created_at, id""",
                (stress_test_id,),
            ).fetchall()
            metrics = connection.execute(
                """SELECT metric_name, service_category, value, unit, definition
                   FROM stress_test_metrics WHERE stress_test_run_id = %s
                   ORDER BY metric_name, service_category""",
                (stress_test_id,),
            ).fetchall()
            impact_counts = connection.execute(
                """SELECT
                       (SELECT count(*) FROM stress_test_edge_impacts
                        WHERE stress_test_run_id = %s),
                       (SELECT count(*) FROM stress_test_building_impacts
                        WHERE stress_test_run_id = %s),
                       (SELECT count(*) FROM stress_test_facility_impacts
                        WHERE stress_test_run_id = %s)""",
                (stress_test_id, stress_test_id, stress_test_id),
            ).fetchone()
        run_keys = (
            "stress_test_id",
            "city_id",
            "base_urban_state_id",
            "network_version_id",
            "stress_test_key",
            "title",
            "stress_test_type",
            "status",
            "assumption_hash",
            "algorithm_version",
            "cache_key",
            "route_semantics",
            "prediction_claimed",
            "limitation",
            "created_by",
            "created_at",
            "started_at",
            "completed_at",
            "metadata",
        )
        assumption_keys = (
            "assumption_id",
            "assumption_type",
            "hazard_dataset_version_id",
            "hazard_type",
            "hazard_class",
            "closure_assumption",
            "assumption_payload",
            "assumption_source",
            "explicitly_confirmed",
            "created_at",
        )
        metric_keys = ("metric_name", "service_category", "value", "unit", "definition")
        return {
            **dict(zip(run_keys, row, strict=True)),
            "assumptions": [
                dict(zip(assumption_keys, item, strict=True)) for item in assumptions
            ],
            "metrics": [dict(zip(metric_keys, item, strict=True)) for item in metrics],
            "impact_counts": dict(
                zip(("edges", "buildings", "facilities"), impact_counts, strict=True)
            ),
        }

    def stress_test_impacts(
        self,
        stress_test_id: str,
        bbox: tuple[float, float, float, float],
        service_category: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT impact.building_gml_id, impact.service_category,
                          impact.baseline_distance_m, impact.scenario_distance_m,
                          impact.impact_status, impact.estimated_population,
                          impact.estimated_elderly_population, impact.evidence,
                          ST_AsGeoJSON(ST_Force2D(object.representative_point))::jsonb
                   FROM stress_test_building_impacts AS impact
                   JOIN plateau_city_objects AS object
                     ON object.dataset_version_id = impact.dataset_version_id
                    AND object.gml_id = impact.building_gml_id
                   WHERE impact.stress_test_run_id = %s
                     AND (CAST(%s AS text) IS NULL OR impact.service_category = %s)
                     AND object.representative_point &&
                         ST_Force3D(ST_MakeEnvelope(%s, %s, %s, %s, 4326))
                   ORDER BY impact.service_category, impact.building_gml_id
                   LIMIT %s OFFSET %s""",
                (
                    stress_test_id,
                    service_category,
                    service_category,
                    *bbox,
                    limit,
                    offset,
                ),
            ).fetchall()
        keys = (
            "building_gml_id",
            "service_category",
            "baseline_distance_m",
            "scenario_distance_m",
            "impact_status",
            "estimated_population",
            "estimated_elderly_population",
            "evidence",
            "geometry",
        )
        return {
            "stress_test_id": stress_test_id,
            "bbox": bbox,
            "service_category": service_category,
            "features": [dict(zip(keys, row, strict=True)) for row in rows],
            "limit": limit,
            "offset": offset,
            "delivery": "bounded_bbox",
        }

    def network_criticality(
        self, city_id: str, urban_state_id: str | None, limit: int
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """WITH selected AS (
                       SELECT run.id, run.algorithm_version, run.runtime_seconds,
                              run.peak_rss_kib, run.completed_at
                       FROM network_criticality_runs AS run
                       JOIN cities AS city ON city.id = run.city_id
                       WHERE (city.city_code = %s OR city.city_key = %s)
                         AND run.status = 'succeeded'
                         AND (%s::uuid IS NULL OR run.urban_state_id = %s::uuid)
                       ORDER BY run.completed_at DESC, run.id DESC LIMIT 1
                   )
                   SELECT candidate.rank, candidate.edge_id, candidate.road_gml_ids,
                          candidate.connected_component_id,
                          candidate.isolated_node_count, candidate.affected_buildings,
                          candidate.affected_estimated_elderly_population,
                          candidate.facility_reachability_change,
                          candidate.candidate_label, candidate.evidence,
                          selected.algorithm_version, selected.runtime_seconds,
                          selected.peak_rss_kib, selected.completed_at
                   FROM selected
                   JOIN network_criticality_candidates AS candidate
                     ON candidate.criticality_run_id = selected.id
                   ORDER BY candidate.rank LIMIT %s""",
                (city_id, city_id, urban_state_id, urban_state_id, limit),
            ).fetchall()
        keys = (
            "rank",
            "edge_id",
            "road_gml_ids",
            "connected_component_id",
            "isolated_node_count",
            "affected_buildings",
            "affected_estimated_elderly_population",
            "facility_reachability_change",
            "candidate_label",
            "evidence",
            "algorithm_version",
            "runtime_seconds",
            "peak_rss_kib",
            "completed_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def future_states(self, city_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT state.id, state.state_key, state.effective_date,
                          state.lifecycle_status, future.projection_series,
                          future.projection_year, future.total_population,
                          future.age_65_plus, future.source_verified,
                          future.allocation_algorithm_version,
                          future.allocation_assumption,
                          future.fixed_service_assumption
                   FROM future_population_states AS future
                   JOIN urban_states AS state ON state.id = future.urban_state_id
                   JOIN cities AS city ON city.id = state.city_id
                   WHERE city.city_code = %s OR city.city_key = %s
                   ORDER BY future.projection_series, future.projection_year""",
                (city_id, city_id),
            ).fetchall()
        keys = (
            "urban_state_id",
            "state_key",
            "effective_date",
            "lifecycle_status",
            "projection_series",
            "projection_year",
            "official_total_population",
            "official_age_65_plus",
            "source_verified",
            "allocation_algorithm_version",
            "allocation_assumption",
            "fixed_service_assumption",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def outcomes(self, city_id: str, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT outcome.id, outcome.implementation_record_id,
                          implementation.status, outcome.baseline_urban_state_id,
                          outcome.expected_scenario_run_id,
                          outcome.observed_urban_state_id, outcome.status,
                          outcome.causal_effect_claimed, outcome.planned_effect,
                          outcome.observed_change, outcome.reviewer_note,
                          outcome.created_by, outcome.created_at, outcome.reviewed_at
                   FROM outcome_evaluations AS outcome
                   JOIN implementation_records AS implementation
                     ON implementation.id = outcome.implementation_record_id
                   JOIN portfolio_interventions AS intervention
                     ON intervention.id = implementation.portfolio_intervention_id
                   JOIN policy_portfolios AS portfolio ON portfolio.id = intervention.portfolio_id
                   JOIN cities AS city ON city.id = portfolio.city_id
                   WHERE city.city_code = %s OR city.city_key = %s
                   ORDER BY outcome.created_at DESC, outcome.id DESC LIMIT %s""",
                (city_id, city_id, limit),
            ).fetchall()
        keys = (
            "outcome_evaluation_id",
            "implementation_record_id",
            "implementation_status",
            "baseline_urban_state_id",
            "expected_scenario_run_id",
            "observed_urban_state_id",
            "review_status",
            "causal_effect_claimed",
            "planned_effect",
            "observed_change",
            "reviewer_note",
            "created_by",
            "created_at",
            "reviewed_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def scenarios(self, city_id: str, status: str | None, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT scenario.id, scenario.scenario_key, scenario.objective_mode,
                          scenario.site_count, scenario.algorithm_kind,
                          scenario.lifecycle_status, scenario.generated_at,
                          scenario.runtime_seconds, dataset.dataset_year,
                          dataset.archive_sha256, network.graph_version,
                          scenario.algorithm_version
                   FROM scenario_runs AS scenario
                   JOIN city_dataset_versions AS dataset
                     ON dataset.id = scenario.dataset_version_id
                   JOIN road_network_versions AS network
                     ON network.id = scenario.network_version_id
                   WHERE dataset.city_id = %s
                     AND (CAST(%s AS text) IS NULL OR scenario.lifecycle_status = %s)
                   ORDER BY scenario.generated_at DESC, scenario.scenario_key
                   LIMIT %s""",
                (city_id, status, status, limit),
            ).fetchall()
        keys = (
            "scenario_id",
            "scenario_key",
            "objective_mode",
            "site_count",
            "algorithm_kind",
            "lifecycle_status",
            "generated_at",
            "runtime_seconds",
            "dataset_year",
            "dataset_archive_sha256",
            "network_version",
            "algorithm_version",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def scenario_detail(self, city_id: str, scenario_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            run = connection.execute(
                """SELECT scenario.id, scenario.scenario_key, scenario.objective_mode,
                          scenario.objective_definition, scenario.site_count,
                          scenario.candidate_count, scenario.algorithm_kind,
                          scenario.algorithm_version, scenario.config_hash,
                          scenario.generated_at, scenario.runtime_seconds,
                          scenario.lifecycle_status, scenario.metadata,
                          dataset.dataset_year, dataset.archive_sha256,
                          dataset.product_specification_version, network.graph_version,
                          network.route_semantics, network.pedestrian_network
                   FROM scenario_runs AS scenario
                   JOIN city_dataset_versions AS dataset
                     ON dataset.id = scenario.dataset_version_id
                   JOIN road_network_versions AS network
                     ON network.id = scenario.network_version_id
                   WHERE dataset.city_id = %s AND scenario.id = %s""",
                (city_id, scenario_id),
            ).fetchone()
            if run is None:
                return None
            run_keys = (
                "scenario_id",
                "scenario_key",
                "objective_mode",
                "objective_definition",
                "site_count",
                "candidate_count",
                "algorithm_kind",
                "algorithm_version",
                "config_hash",
                "generated_at",
                "runtime_seconds",
                "lifecycle_status",
                "metadata",
                "dataset_year",
                "dataset_archive_sha256",
                "plateau_product_specification_version",
                "network_version",
                "route_semantics",
                "pedestrian_network",
            )
            detail = dict(zip(run_keys, run, strict=True))
            site_rows = connection.execute(
                """SELECT site_order, candidate_id, network_node_id, road_gml_id,
                          road_surface_id, road_name, existing_transport_distance_m,
                          component_id, candidate_to_graph_connector_m,
                          siting_feasibility, ST_X(geom), ST_Y(geom)
                   FROM scenario_sites WHERE scenario_run_id = %s ORDER BY site_order""",
                (scenario_id,),
            ).fetchall()
            site_keys = (
                "site_order",
                "candidate_id",
                "network_node_id",
                "road_gml_id",
                "road_surface_id",
                "road_name",
                "existing_transport_distance_m",
                "component_id",
                "candidate_to_graph_connector_m",
                "siting_feasibility",
                "longitude",
                "latitude",
            )
            detail["sites"] = [dict(zip(site_keys, row, strict=True)) for row in site_rows]
            detail["objectives"] = [
                {
                    "name": row[0],
                    "role": row[1],
                    "value": row[2],
                    "unit": row[3],
                    "definition": row[4],
                    "metadata": row[5],
                }
                for row in connection.execute(
                    """SELECT objective_name, objective_role, value, unit, definition, metadata
                       FROM scenario_objectives WHERE scenario_run_id = %s
                       ORDER BY objective_role DESC, objective_name""",
                    (scenario_id,),
                ).fetchall()
            ]
            detail["impacts"] = {
                row[0]: {"value": row[1], "unit": row[2], "interpretation": row[3]}
                for row in connection.execute(
                    """SELECT metric_name, value, unit, interpretation
                       FROM scenario_impacts WHERE scenario_run_id = %s
                       ORDER BY metric_name""",
                    (scenario_id,),
                ).fetchall()
            }
            detail["contexts"] = [
                {
                    "site_order": row[0],
                    "type": row[1],
                    "label": row[2],
                    "feature_count": row[3],
                    "review_status": row[4],
                    "siting_feasibility": row[5],
                    "source": row[6],
                }
                for row in connection.execute(
                    """SELECT site_order, context_type, label, feature_count,
                              review_status, siting_feasibility, source_payload
                       FROM scenario_context WHERE scenario_run_id = %s
                       ORDER BY site_order, context_type""",
                    (scenario_id,),
                ).fetchall()
            ]
            evidence = connection.execute(
                """SELECT evidence FROM scenario_evidence WHERE scenario_run_id = %s""",
                (scenario_id,),
            ).fetchone()
            detail["representative_evidence"] = evidence[0] if evidence else None
            detail["lifecycle_events"] = [
                {
                    "from_status": row[0],
                    "to_status": row[1],
                    "note": row[2],
                    "changed_at": row[3],
                }
                for row in connection.execute(
                    """SELECT from_status, to_status, note, changed_at
                       FROM scenario_lifecycle_events WHERE scenario_run_id = %s
                       ORDER BY changed_at, id""",
                    (scenario_id,),
                ).fetchall()
            ]
        return detail

    def transition_scenario(
        self,
        city_id: str,
        scenario_id: str,
        expected_status: str,
        proposed_status: str,
        note: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT scenario.lifecycle_status
                   FROM scenario_runs AS scenario
                   JOIN city_dataset_versions AS dataset
                     ON dataset.id = scenario.dataset_version_id
                   WHERE dataset.city_id = %s AND scenario.id = %s FOR UPDATE""",
                (city_id, scenario_id),
            ).fetchone()
            if row is None:
                return None
            current = str(row[0])
            if current != expected_status:
                raise ValueError(
                    f"Scenario status changed: expected {expected_status}, found {current}"
                )
            validate_status_transition(current, proposed_status)
            updated = connection.execute(
                """UPDATE scenario_runs SET lifecycle_status = %s,
                          reviewed_at = CASE WHEN %s = 'reviewed' THEN now() ELSE NULL END,
                          updated_at = now()
                   WHERE id = %s RETURNING lifecycle_status, updated_at""",
                (proposed_status, proposed_status, scenario_id),
            ).fetchone()
            connection.execute(
                """INSERT INTO scenario_lifecycle_events (
                       scenario_run_id, from_status, to_status, note
                   ) VALUES (%s, %s, %s, %s)""",
                (scenario_id, current, proposed_status, note),
            )
            self._audit(
                connection,
                "scenario.status.transition",
                "scenario",
                scenario_id,
                city_id,
                {"lifecycle_status": current},
                {"lifecycle_status": proposed_status, "note": note},
            )
            connection.commit()
        return {
            "scenario_id": scenario_id,
            "lifecycle_status": updated[0],
            "updated_at": updated[1],
        }

    def field_check(self, city_id: str, scenario_id: str, site_order: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT check_row.site_access, check_row.road_safety,
                          check_row.land_ownership_unknown, check_row.existing_service,
                          check_row.facility_condition, check_row.hazard_confirmation,
                          check_row.operator_consultation, check_row.notes,
                          check_row.photo_urls, check_row.location_context,
                          check_row.gps_confirmation, check_row.record_version,
                          check_row.updated_by, check_row.checked_at, check_row.updated_at
                   FROM scenario_field_checks AS check_row
                   JOIN scenario_runs AS scenario ON scenario.id = check_row.scenario_run_id
                   JOIN city_dataset_versions AS dataset
                     ON dataset.id = scenario.dataset_version_id
                   WHERE dataset.city_id = %s AND scenario.id = %s
                     AND check_row.site_order = %s""",
                (city_id, scenario_id, site_order),
            ).fetchone()
        if row is None:
            return None
        keys = (
            "site_access",
            "road_safety",
            "land_ownership_unknown",
            "existing_service",
            "facility_condition",
            "hazard_confirmation",
            "operator_consultation",
            "notes",
            "photo_urls",
            "location_context",
            "gps_confirmation",
            "record_version",
            "updated_by",
            "checked_at",
            "updated_at",
        )
        return {
            "scenario_id": scenario_id,
            "site_order": site_order,
            **dict(zip(keys, row, strict=True)),
        }

    def save_field_check(
        self,
        city_id: str,
        scenario_id: str,
        site_order: int,
        checklist: dict[str, Any],
    ) -> dict[str, Any] | None:
        fields = (
            "site_access",
            "road_safety",
            "land_ownership_unknown",
            "existing_service",
            "facility_condition",
            "hazard_confirmation",
            "operator_consultation",
        )
        with self._connect() as connection:
            site = connection.execute(
                """SELECT 1 FROM scenario_sites AS site
                   JOIN scenario_runs AS scenario ON scenario.id = site.scenario_run_id
                   JOIN city_dataset_versions AS dataset
                     ON dataset.id = scenario.dataset_version_id
                   WHERE dataset.city_id = %s AND scenario.id = %s AND site.site_order = %s""",
                (city_id, scenario_id, site_order),
            ).fetchone()
            if site is None:
                return None
            existing = connection.execute(
                """SELECT site_access, road_safety, land_ownership_unknown,
                          existing_service, facility_condition, hazard_confirmation,
                          operator_consultation, notes, photo_urls, location_context
                   FROM scenario_field_checks
                   WHERE scenario_run_id = %s AND site_order = %s""",
                (scenario_id, site_order),
            ).fetchone()
            connection.execute(
                """INSERT INTO scenario_field_checks (
                       scenario_run_id, site_order, site_access, road_safety,
                       land_ownership_unknown, existing_service, facility_condition,
                       hazard_confirmation, operator_consultation, notes, photo_urls,
                       location_context, checked_at, updated_by
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
                   ON CONFLICT (scenario_run_id, site_order) DO UPDATE SET
                       site_access = EXCLUDED.site_access,
                       road_safety = EXCLUDED.road_safety,
                       land_ownership_unknown = EXCLUDED.land_ownership_unknown,
                       existing_service = EXCLUDED.existing_service,
                       facility_condition = EXCLUDED.facility_condition,
                       hazard_confirmation = EXCLUDED.hazard_confirmation,
                       operator_consultation = EXCLUDED.operator_consultation,
                       notes = EXCLUDED.notes, photo_urls = EXCLUDED.photo_urls,
                       location_context = EXCLUDED.location_context,
                       checked_at = now(), updated_at = now(), updated_by = EXCLUDED.updated_by""",
                (
                    scenario_id,
                    site_order,
                    *(checklist[name] for name in fields),
                    checklist["notes"],
                    checklist.get("photo_urls", []),
                    json.dumps(checklist.get("location_context", {}), ensure_ascii=False),
                    current_request_context().actor,
                ),
            )
            before_keys = (*fields, "notes", "photo_urls", "location_context")
            self._audit(
                connection,
                "field_check.upsert",
                "scenario_site",
                f"{scenario_id}:{site_order}",
                city_id,
                dict(zip(before_keys, existing, strict=True)) if existing else None,
                {key: checklist.get(key) for key in before_keys},
            )
            connection.commit()
        return self.field_check(city_id, scenario_id, site_order)

    def create_field_offline_package(
        self,
        city_id: str,
        urban_state_id: str,
        scenario_run_id: str,
        site_order: int,
        expires_at: str | None,
    ) -> dict[str, Any] | None:
        actor = current_request_context().actor
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO scenario_field_checks (
                       scenario_run_id, site_order, updated_by
                   )
                   SELECT site.scenario_run_id, site.site_order, %s
                   FROM scenario_sites AS site
                   JOIN scenario_runs AS scenario ON scenario.id = site.scenario_run_id
                   JOIN urban_states AS state ON state.id = scenario.base_urban_state_id
                   JOIN cities AS city ON city.id = state.city_id
                   WHERE (city.city_code = %s OR city.city_key = %s)
                     AND state.id = %s AND scenario.id = %s AND site.site_order = %s
                   ON CONFLICT DO NOTHING""",
                (actor, city_id, city_id, urban_state_id, scenario_run_id, site_order),
            )
            site = connection.execute(
                """SELECT scenario.scenario_key, scenario.lifecycle_status,
                          state.state_key, state.effective_date,
                          site.candidate_id, site.network_node_id, site.road_gml_id,
                          site.road_surface_id, site.road_name,
                          site.existing_transport_distance_m, site.component_id,
                          site.candidate_to_graph_connector_m, site.siting_feasibility,
                          ST_AsGeoJSON(site.geom)::jsonb,
                          check_row.site_access, check_row.road_safety,
                          check_row.land_ownership_unknown, check_row.existing_service,
                          check_row.facility_condition, check_row.hazard_confirmation,
                          check_row.operator_consultation, check_row.notes,
                          check_row.gps_confirmation, check_row.record_version,
                          check_row.updated_by, check_row.updated_at
                   FROM scenario_sites AS site
                   JOIN scenario_runs AS scenario ON scenario.id = site.scenario_run_id
                   JOIN urban_states AS state ON state.id = scenario.base_urban_state_id
                   JOIN cities AS city ON city.id = state.city_id
                   JOIN scenario_field_checks AS check_row
                     ON check_row.scenario_run_id = site.scenario_run_id
                    AND check_row.site_order = site.site_order
                   WHERE (city.city_code = %s OR city.city_key = %s)
                     AND state.id = %s AND scenario.id = %s AND site.site_order = %s""",
                (city_id, city_id, urban_state_id, scenario_run_id, site_order),
            ).fetchone()
            if site is None:
                return None
            contexts = connection.execute(
                """SELECT context_type, label, feature_count, review_status,
                          siting_feasibility, source_payload
                   FROM scenario_context
                   WHERE scenario_run_id = %s AND site_order = %s
                   ORDER BY context_type""",
                (scenario_run_id, site_order),
            ).fetchall()
            evidence = connection.execute(
                "SELECT evidence FROM scenario_evidence WHERE scenario_run_id = %s",
                (scenario_run_id,),
            ).fetchone()
            site_keys = (
                "scenario_key",
                "scenario_lifecycle_status",
                "urban_state_key",
                "effective_date",
                "candidate_id",
                "network_node_id",
                "road_gml_id",
                "road_surface_id",
                "road_name",
                "existing_transport_distance_m",
                "component_id",
                "candidate_to_graph_connector_m",
                "siting_feasibility",
                "geometry",
            )
            field_keys = (
                "site_access",
                "road_safety",
                "land_ownership_unknown",
                "existing_service",
                "facility_condition",
                "hazard_confirmation",
                "operator_consultation",
                "notes",
                "gps_confirmation",
                "record_version",
                "updated_by",
                "updated_at",
            )
            content = {
                "package_scope": "single_selected_site",
                "city_id": city_id,
                "urban_state_id": urban_state_id,
                "scenario_run_id": scenario_run_id,
                "site_order": site_order,
                "site": dict(zip(site_keys, site[: len(site_keys)], strict=True)),
                "field_record": dict(zip(field_keys, site[len(site_keys) :], strict=True)),
                "contexts": [
                    dict(
                        zip(
                            (
                                "context_type",
                                "label",
                                "feature_count",
                                "review_status",
                                "siting_feasibility",
                                "source_payload",
                            ),
                            row,
                            strict=True,
                        )
                    )
                    for row in contexts
                ],
                "evidence_summary": evidence[0] if evidence else {},
            }
            canonical = json.dumps(
                content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
            )
            content_hash = hashlib.sha256(canonical.encode()).hexdigest()
            version = connection.execute(
                """SELECT COALESCE(max(package_version), 0) + 1
                   FROM field_offline_packages
                   WHERE scenario_run_id = %s AND site_order = %s""",
                (scenario_run_id, site_order),
            ).fetchone()[0]
            package = connection.execute(
                """INSERT INTO field_offline_packages (
                       city_id, urban_state_id, scenario_run_id, site_order,
                       package_version, content, content_sha256, expires_at, created_by
                   )
                   SELECT city.id, %s, %s, %s, %s, %s, %s, %s, %s
                   FROM cities AS city
                   WHERE city.city_code = %s OR city.city_key = %s
                   RETURNING id, package_version, content_sha256, expires_at, created_at""",
                (
                    urban_state_id,
                    scenario_run_id,
                    site_order,
                    version,
                    canonical,
                    content_hash,
                    expires_at,
                    actor,
                    city_id,
                    city_id,
                ),
            ).fetchone()
            self._audit(
                connection,
                "field.offline_package.create",
                "scenario_site",
                f"{scenario_run_id}:{site_order}",
                city_id,
                None,
                {
                    "offline_package_id": str(package[0]),
                    "package_version": package[1],
                    "content_sha256": package[2],
                    "scope": "single_selected_site",
                },
            )
            connection.commit()
        return {
            "offline_package_id": package[0],
            "package_version": package[1],
            "content_sha256": package[2],
            "expires_at": package[3],
            "created_at": package[4],
            "content": content,
        }

    def sync_field_operation(
        self, city_id: str, operation: dict[str, Any]
    ) -> dict[str, Any] | None:
        actor = current_request_context().actor
        field_names = (
            "site_access",
            "road_safety",
            "land_ownership_unknown",
            "existing_service",
            "facility_condition",
            "hazard_confirmation",
            "operator_consultation",
            "notes",
            "gps_confirmation",
        )
        with self._connect() as connection:
            prior = connection.execute(
                """SELECT operation.status, conflict.id
                   FROM field_sync_operations AS operation
                   LEFT JOIN field_sync_conflicts AS conflict
                     ON conflict.field_sync_operation_id = operation.id
                   WHERE operation.client_operation_id = %s""",
                (operation["client_operation_id"],),
            ).fetchone()
            if prior is not None:
                return {
                    "client_operation_id": operation["client_operation_id"],
                    "status": prior[0],
                    "conflict_id": prior[1],
                    "idempotent_replay": True,
                }
            package = connection.execute(
                """SELECT package.id
                   FROM field_offline_packages AS package
                   JOIN cities AS city ON city.id = package.city_id
                   WHERE package.id = %s AND package.scenario_run_id = %s
                     AND package.site_order = %s
                     AND (city.city_code = %s OR city.city_key = %s)
                     AND (package.expires_at IS NULL OR package.expires_at > now())""",
                (
                    operation["offline_package_id"],
                    operation["scenario_run_id"],
                    operation["site_order"],
                    city_id,
                    city_id,
                ),
            ).fetchone()
            if package is None:
                return None
            connection.execute(
                """INSERT INTO scenario_field_checks (
                       scenario_run_id, site_order, updated_by
                   ) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                (operation["scenario_run_id"], operation["site_order"], actor),
            )
            current = connection.execute(
                """SELECT site_access, road_safety, land_ownership_unknown,
                          existing_service, facility_condition, hazard_confirmation,
                          operator_consultation, notes, gps_confirmation,
                          record_version, updated_by, updated_at
                   FROM scenario_field_checks
                   WHERE scenario_run_id = %s AND site_order = %s FOR UPDATE""",
                (operation["scenario_run_id"], operation["site_order"]),
            ).fetchone()
            server_state = dict(
                zip((*field_names, "record_version", "actor", "updated_at"), current, strict=True)
            )
            sync_row = connection.execute(
                """INSERT INTO field_sync_operations (
                       client_operation_id, offline_package_id, scenario_run_id,
                       site_order, actor, base_record_version, client_updated_at, payload
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    operation["client_operation_id"],
                    operation["offline_package_id"],
                    operation["scenario_run_id"],
                    operation["site_order"],
                    actor,
                    operation["base_record_version"],
                    operation["client_updated_at"],
                    json.dumps(operation["payload"], ensure_ascii=False),
                ),
            ).fetchone()
            if int(current[9]) != int(operation["base_record_version"]):
                connection.execute(
                    "UPDATE field_sync_operations SET status = 'conflict' WHERE id = %s",
                    (sync_row[0],),
                )
                conflict = connection.execute(
                    """INSERT INTO field_sync_conflicts (
                           field_sync_operation_id, server_record_version,
                           server_state, client_state
                       ) VALUES (%s, %s, %s, %s) RETURNING id, created_at""",
                    (
                        sync_row[0],
                        current[9],
                        json.dumps(server_state, ensure_ascii=False, default=str),
                        json.dumps(operation["payload"], ensure_ascii=False),
                    ),
                ).fetchone()
                self._audit(
                    connection,
                    "field.sync.conflict",
                    "scenario_site",
                    f"{operation['scenario_run_id']}:{operation['site_order']}",
                    city_id,
                    server_state,
                    {
                        "client_operation_id": operation["client_operation_id"],
                        "base_record_version": operation["base_record_version"],
                        "resolution_status": "unresolved",
                    },
                )
                connection.commit()
                return {
                    "client_operation_id": operation["client_operation_id"],
                    "status": "conflict",
                    "conflict_id": conflict[0],
                    "server_record_version": current[9],
                    "server_state": server_state,
                    "client_state": operation["payload"],
                    "created_at": str(conflict[1]),
                    "silent_last_write_wins": False,
                }
            values = {name: current[index] for index, name in enumerate(field_names)}
            values.update(operation["payload"])
            updated = connection.execute(
                """UPDATE scenario_field_checks SET
                       site_access = %s, road_safety = %s, land_ownership_unknown = %s,
                       existing_service = %s, facility_condition = %s,
                       hazard_confirmation = %s, operator_consultation = %s,
                       notes = %s, gps_confirmation = %s, updated_by = %s
                   WHERE scenario_run_id = %s AND site_order = %s
                   RETURNING record_version, updated_by, updated_at""",
                (
                    *(values[name] for name in field_names[:-1]),
                    json.dumps(values["gps_confirmation"], ensure_ascii=False),
                    actor,
                    operation["scenario_run_id"],
                    operation["site_order"],
                ),
            ).fetchone()
            connection.execute(
                """UPDATE field_sync_operations
                   SET status = 'applied', applied_at = now() WHERE id = %s""",
                (sync_row[0],),
            )
            self._audit(
                connection,
                "field.sync.apply",
                "scenario_site",
                f"{operation['scenario_run_id']}:{operation['site_order']}",
                city_id,
                server_state,
                {
                    **values,
                    "record_version": updated[0],
                    "actor": updated[1],
                    "updated_at": updated[2],
                },
            )
            connection.commit()
        return {
            "client_operation_id": operation["client_operation_id"],
            "status": "applied",
            "record_version": updated[0],
            "actor": updated[1],
            "updated_at": updated[2],
        }

    def field_sync_conflict(self, conflict_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT conflict.id, operation.client_operation_id,
                          operation.scenario_run_id, operation.site_order,
                          operation.actor, operation.base_record_version,
                          conflict.server_record_version, conflict.server_state,
                          conflict.client_state, conflict.resolution_status,
                          conflict.resolved_state, conflict.resolved_by,
                          conflict.resolved_at, conflict.created_at
                   FROM field_sync_conflicts AS conflict
                   JOIN field_sync_operations AS operation
                     ON operation.id = conflict.field_sync_operation_id
                   WHERE conflict.id = %s""",
                (conflict_id,),
            ).fetchone()
        if row is None:
            return None
        keys = (
            "conflict_id",
            "client_operation_id",
            "scenario_run_id",
            "site_order",
            "operation_actor",
            "base_record_version",
            "server_record_version",
            "server_state",
            "client_state",
            "resolution_status",
            "resolved_state",
            "resolved_by",
            "resolved_at",
            "created_at",
        )
        return {**dict(zip(keys, row, strict=True)), "silent_last_write_wins": False}

    def resolve_field_sync_conflict(
        self, city_id: str, conflict_id: str, resolution: dict[str, Any]
    ) -> dict[str, Any] | None:
        actor = current_request_context().actor
        field_names = (
            "site_access",
            "road_safety",
            "land_ownership_unknown",
            "existing_service",
            "facility_condition",
            "hazard_confirmation",
            "operator_consultation",
            "notes",
            "gps_confirmation",
        )
        with self._connect() as connection:
            conflict = connection.execute(
                """SELECT conflict.field_sync_operation_id,
                          conflict.server_record_version, conflict.server_state,
                          conflict.client_state, conflict.resolution_status,
                          operation.scenario_run_id, operation.site_order
                   FROM field_sync_conflicts AS conflict
                   JOIN field_sync_operations AS operation
                     ON operation.id = conflict.field_sync_operation_id
                   JOIN scenario_runs AS scenario ON scenario.id = operation.scenario_run_id
                   JOIN urban_states AS state ON state.id = scenario.base_urban_state_id
                   JOIN cities AS city ON city.id = state.city_id
                   WHERE conflict.id = %s
                     AND (city.city_code = %s OR city.city_key = %s)
                   FOR UPDATE OF conflict""",
                (conflict_id, city_id, city_id),
            ).fetchone()
            if conflict is None:
                return None
            if conflict[4] != "unresolved":
                raise ValueError("Field sync conflict was already explicitly resolved")
            current = connection.execute(
                """SELECT site_access, road_safety, land_ownership_unknown,
                          existing_service, facility_condition, hazard_confirmation,
                          operator_consultation, notes, gps_confirmation,
                          record_version, updated_by, updated_at
                   FROM scenario_field_checks
                   WHERE scenario_run_id = %s AND site_order = %s FOR UPDATE""",
                (conflict[5], conflict[6]),
            ).fetchone()
            if current is None:
                return None
            current_state = dict(
                zip((*field_names, "record_version", "actor", "updated_at"), current, strict=True)
            )
            status = resolution["resolution_status"]
            if status == "use_server":
                resolved_state = current_state
                operation_status = "rejected"
            else:
                if int(current[9]) != int(conflict[1]):
                    raise ValueError(
                        "Server record changed again; refresh before explicit conflict resolution"
                    )
                selected = conflict[3] if status == "use_client" else resolution["resolved_state"]
                values = {name: current[index] for index, name in enumerate(field_names)}
                values.update(selected)
                updated = connection.execute(
                    """UPDATE scenario_field_checks SET
                           site_access = %s, road_safety = %s, land_ownership_unknown = %s,
                           existing_service = %s, facility_condition = %s,
                           hazard_confirmation = %s, operator_consultation = %s,
                           notes = %s, gps_confirmation = %s, updated_by = %s
                       WHERE scenario_run_id = %s AND site_order = %s
                       RETURNING record_version, updated_by, updated_at""",
                    (
                        *(values[name] for name in field_names[:-1]),
                        json.dumps(values["gps_confirmation"], ensure_ascii=False),
                        actor,
                        conflict[5],
                        conflict[6],
                    ),
                ).fetchone()
                resolved_state = {
                    **values,
                    "record_version": updated[0],
                    "actor": updated[1],
                    "updated_at": updated[2],
                }
                operation_status = "applied"
            connection.execute(
                """UPDATE field_sync_conflicts SET
                       resolution_status = %s, resolved_state = %s,
                       resolved_by = %s, resolved_at = now()
                   WHERE id = %s""",
                (
                    status,
                    json.dumps(resolved_state, ensure_ascii=False, default=str),
                    actor,
                    conflict_id,
                ),
            )
            connection.execute(
                """UPDATE field_sync_operations SET status = %s,
                       applied_at = CASE WHEN %s = 'applied' THEN now() ELSE NULL END
                   WHERE id = %s""",
                (operation_status, operation_status, conflict[0]),
            )
            self._audit(
                connection,
                "field.sync.conflict.resolve",
                "scenario_site",
                f"{conflict[5]}:{conflict[6]}",
                city_id,
                {"resolution_status": "unresolved", "server_state": conflict[2]},
                {
                    "resolution_status": status,
                    "resolved_state": resolved_state,
                    "resolved_by": actor,
                },
            )
            connection.commit()
        return self.field_sync_conflict(conflict_id)

    def city_registry(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            city_rows = connection.execute(
                """SELECT id, city_code, city_key, name, prefecture_code,
                          prefecture_name, analysis_crs
                   FROM cities ORDER BY city_code"""
            ).fetchall()
            capability_rows = connection.execute(
                """SELECT city.city_code, capability.capability, capability.status,
                          capability.note, capability.evidence, capability.updated_at
                   FROM city_capabilities AS capability
                   JOIN cities AS city ON city.id = capability.city_id
                   ORDER BY city.city_code, capability.capability"""
            ).fetchall()
        capabilities: dict[str, list[dict[str, Any]]] = {}
        for row in capability_rows:
            capabilities.setdefault(row[0], []).append(
                {
                    "capability": row[1],
                    "status": row[2],
                    "note": row[3],
                    "evidence": row[4],
                    "updated_at": row[5],
                }
            )
        keys = (
            "registry_city_id",
            "city_code",
            "city_id",
            "name",
            "prefecture_code",
            "prefecture_name",
            "analysis_crs",
        )
        return [
            {
                **dict(zip(keys, row, strict=True)),
                "capabilities": capabilities.get(row[1], []),
            }
            for row in city_rows
        ]

    def dataset_registry(self, city_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT dataset.id, dataset.dataset_key, dataset.title, dataset.provider,
                          version.id, version.version_key, version.dataset_year,
                          version.data_format, version.source_url, version.license,
                          version.declared_source_crs, version.archive_file_name,
                          version.archive_sha256, version.verification_status,
                          version.registered_at
                   FROM datasets AS dataset
                   JOIN dataset_versions AS version ON version.dataset_id = dataset.id
                   JOIN cities AS city ON city.id = dataset.city_id
                   WHERE city.city_code = %s OR city.city_key = %s
                   ORDER BY dataset.dataset_key, version.dataset_year, version.version_key""",
                (city_id, city_id),
            ).fetchall()
        keys = (
            "dataset_id",
            "dataset_key",
            "title",
            "provider",
            "dataset_version_id",
            "version_key",
            "year",
            "format",
            "source_url",
            "license",
            "declared_source_crs",
            "archive_file",
            "archive_sha256",
            "verification_status",
            "registered_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def analysis_runs(self, city_id: str, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT run.id, run.analysis_type, run.status, run.config_hash,
                          run.output_artifact, run.output_sha256, run.started_at,
                          run.completed_at,
                          array_agg(input.dataset_version_id ORDER BY input.dataset_version_id)
                   FROM analysis_runs AS run
                   JOIN cities AS city ON city.id = run.city_id
                   LEFT JOIN analysis_run_dataset_versions AS input
                     ON input.analysis_run_id = run.id
                   WHERE city.city_code = %s OR city.city_key = %s
                   GROUP BY run.id
                   ORDER BY run.started_at DESC, run.analysis_type
                   LIMIT %s""",
                (city_id, city_id, limit),
            ).fetchall()
        keys = (
            "analysis_run_id",
            "analysis_type",
            "status",
            "config_hash",
            "output_artifact",
            "output_sha256",
            "started_at",
            "completed_at",
            "dataset_version_ids",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def create_job(
        self,
        city_id: str,
        job_type: str,
        dataset_version_ids: list[str],
        config_hash: str,
        algorithm_version: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            city = connection.execute(
                "SELECT id FROM cities WHERE city_code = %s OR city_key = %s",
                (city_id, city_id),
            ).fetchone()
            if city is None:
                return None
            valid_versions = connection.execute(
                """SELECT version.id FROM dataset_versions AS version
                   JOIN datasets AS dataset ON dataset.id = version.dataset_id
                   WHERE dataset.city_id = %s AND version.id = ANY(%s::uuid[])""",
                (city[0], dataset_version_ids),
            ).fetchall()
            if {str(row[0]) for row in valid_versions} != set(dataset_version_ids):
                raise ValueError("Every job dataset version must belong to the selected city")
            idempotency_payload = {
                "city": city_id,
                "datasets": sorted(set(dataset_version_ids)),
                "job_type": job_type,
                "algorithm_version": algorithm_version,
                "config_hash": config_hash,
            }
            idempotency_key = hashlib.sha256(
                json.dumps(idempotency_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            job_id = connection.execute(
                """INSERT INTO job_runs (
                       city_id, job_type, state, config_hash, algorithm_version,
                       idempotency_key, parameters
                   ) VALUES (%s, %s, 'queued', %s, %s, %s, %s)
                   ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL
                   DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
                   RETURNING id, (xmax = 0) AS inserted""",
                (
                    city[0],
                    job_type,
                    config_hash,
                    algorithm_version,
                    idempotency_key,
                    json.dumps(parameters, ensure_ascii=False),
                ),
            ).fetchone()[0]
            existing_inputs = connection.execute(
                "SELECT count(*) FROM job_dataset_versions WHERE job_run_id = %s", (job_id,)
            ).fetchone()[0]
            if existing_inputs == 0:
                for version_id in sorted(set(dataset_version_ids)):
                    connection.execute(
                        """INSERT INTO job_dataset_versions (job_run_id, dataset_version_id)
                           VALUES (%s, %s)""",
                        (job_id, version_id),
                    )
                connection.execute(
                    """INSERT INTO job_events (job_run_id, state, message)
                       VALUES (%s, 'queued', 'job registered; no work has started')""",
                    (job_id,),
                )
                self._audit(
                    connection,
                    "job.create",
                    "job",
                    str(job_id),
                    city_id,
                    None,
                    {**idempotency_payload, "state": "queued"},
                )
            connection.commit()
        return self.job_detail(str(job_id))

    def job_detail(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT job.id, city.city_code, city.city_key, job.job_type,
                          job.state, job.current_stage, job.config_hash,
                          job.algorithm_version, job.idempotency_key, job.parameters,
                          job.retry_count, job.max_retries, job.queued_at, job.started_at,
                          job.finished_at, job.error_message
                   FROM job_runs AS job JOIN cities AS city ON city.id = job.city_id
                   WHERE job.id = %s""",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            keys = (
                "job_id",
                "city_code",
                "city_id",
                "job_type",
                "state",
                "current_stage",
                "config_hash",
                "algorithm_version",
                "idempotency_key",
                "parameters",
                "retry_count",
                "max_retries",
                "queued_at",
                "started_at",
                "finished_at",
                "error",
            )
            result = dict(zip(keys, row, strict=True))
            result["dataset_version_ids"] = [
                str(value[0])
                for value in connection.execute(
                    """SELECT dataset_version_id FROM job_dataset_versions
                       WHERE job_run_id = %s ORDER BY dataset_version_id""",
                    (job_id,),
                ).fetchall()
            ]
            result["events"] = [
                {
                    "state": event[0],
                    "stage": event[1],
                    "message": event[2],
                    "recorded_at": event[3],
                }
                for event in connection.execute(
                    """SELECT state, stage, message, recorded_at FROM job_events
                       WHERE job_run_id = %s ORDER BY recorded_at, id""",
                    (job_id,),
                ).fetchall()
            ]
        return result

    def transition_job(
        self, job_id: str, action: str, stage: str | None, error: str | None
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT job_type, state, current_stage FROM job_runs
                   WHERE id = %s FOR UPDATE""",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            event_stages = [
                value[0]
                for value in connection.execute(
                    """SELECT stage FROM job_events
                       WHERE job_run_id = %s AND stage IS NOT NULL ORDER BY id""",
                    (job_id,),
                ).fetchall()
            ]
            completed = tuple(value for value in event_stages if value != row[2])
            snapshot = JobSnapshot(
                job_type=str(row[0]),
                state=JobState(str(row[1])),
                current_stage=row[2],
                completed_stages=completed,
                error=None,
            )
            if action == "start":
                updated = start_job(snapshot)
            elif action == "advance":
                if stage is None:
                    raise ValueError("advance requires the next real stage")
                updated = advance_job(snapshot, stage)
            elif action == "succeed":
                updated = succeed_job(snapshot)
            elif action == "fail":
                updated = fail_job(snapshot, error or "")
            else:
                raise ValueError("Unknown job transition action")
            connection.execute(
                """UPDATE job_runs SET state = %s, current_stage = %s,
                          started_at = CASE
                              WHEN %s = 'running' THEN COALESCE(started_at, now())
                              ELSE started_at END,
                          completed_at = CASE
                              WHEN %s IN ('succeeded', 'failed') THEN now() ELSE NULL END,
                          finished_at = CASE
                              WHEN %s IN ('succeeded', 'failed') THEN now() ELSE NULL END,
                          error_message = %s
                   WHERE id = %s""",
                (
                    updated.state.value,
                    updated.current_stage,
                    updated.state.value,
                    updated.state.value,
                    updated.state.value,
                    updated.error,
                    job_id,
                ),
            )
            connection.execute(
                """INSERT INTO job_events (job_run_id, state, stage, message)
                   VALUES (%s, %s, %s, %s)""",
                (
                    job_id,
                    updated.state.value,
                    updated.current_stage,
                    updated.error or action,
                ),
            )
            self._audit(
                connection,
                f"job.{action}",
                "job",
                job_id,
                None,
                {"state": row[1], "stage": row[2]},
                {"state": updated.state.value, "stage": updated.current_stage},
            )
            connection.commit()
        return self.job_detail(job_id)

    def vector_tile(
        self,
        city_id: str,
        layer: str,
        z: int,
        x: int,
        y: int,
        dataset_version_id: str,
        network_version_id: str | None,
        scenario_id: str | None,
        algorithm_version: str | None,
    ) -> bytes:
        bounds = (z, x, y)
        if layer == "buildings":
            query = """WITH bounds AS (SELECT ST_TileEnvelope(%s, %s, %s) AS geom),
                tile AS (
                    SELECT object.gml_id, building.usage_code,
                           ST_AsMVTGeom(
                               ST_Transform(object.representative_point, 3857),
                               bounds.geom, 4096, 64, true
                           ) AS geom
                    FROM bounds, plateau_city_objects AS object
                    JOIN plateau_buildings AS building ON building.city_object_id = object.id
                    JOIN city_dataset_versions AS dataset
                      ON dataset.id = object.dataset_version_id
                    WHERE dataset.id = %s::uuid AND dataset.city_id = %s
                      AND object.representative_point IS NOT NULL
                      AND object.representative_point && ST_Transform(bounds.geom, 4326)
                    ORDER BY object.gml_id LIMIT 50000
                )
                SELECT COALESCE(ST_AsMVT(tile, 'buildings', 4096, 'geom'), ''::bytea)
                FROM tile"""
            parameters: tuple[Any, ...] = (*bounds, dataset_version_id, city_id)
        elif layer == "road_edges":
            if network_version_id is None:
                raise ValueError("road_edges tiles require network_version_id")
            query = """WITH bounds AS (SELECT ST_TileEnvelope(%s, %s, %s) AS geom),
                tile AS (
                    SELECT edge.edge_id, edge.length_m, edge.pedestrian_permission,
                           ST_AsMVTGeom(
                               ST_Transform(edge.geom, 3857),
                               bounds.geom, 4096, 64, true
                           ) AS geom
                    FROM bounds, road_network_edges AS edge
                    JOIN road_network_versions AS network ON network.id = edge.network_version_id
                    JOIN city_dataset_versions AS dataset
                      ON dataset.id = network.dataset_version_id
                    WHERE dataset.id = %s::uuid AND dataset.city_id = %s
                      AND network.id = %s::uuid
                      AND edge.geom && ST_Transform(bounds.geom, ST_SRID(edge.geom))
                    ORDER BY edge.edge_id LIMIT 50000
                )
                SELECT COALESCE(ST_AsMVT(tile, 'road_edges', 4096, 'geom'), ''::bytea)
                FROM tile"""
            parameters = (*bounds, dataset_version_id, city_id, network_version_id)
        elif layer == "hazards":
            query = """WITH bounds AS (SELECT ST_TileEnvelope(%s, %s, %s) AS geom),
                tile AS (
                    SELECT object.gml_id, hazard.hazard_type, hazard.rank_code,
                           ST_AsMVTGeom(
                               ST_Transform(ST_Force2D(part.geom), 3857),
                               bounds.geom, 4096, 64, true
                           ) AS geom
                    FROM bounds, plateau_hazards AS hazard
                    JOIN plateau_city_objects AS object ON object.id = hazard.city_object_id
                    JOIN plateau_geometry_parts AS part ON part.city_object_id = object.id
                    JOIN city_dataset_versions AS dataset
                      ON dataset.id = object.dataset_version_id
                    WHERE dataset.id = %s::uuid AND dataset.city_id = %s
                      AND part.geom && ST_Force3D(ST_Transform(bounds.geom, 4326))
                    ORDER BY object.gml_id, part.part_order LIMIT 50000
                )
                SELECT COALESCE(ST_AsMVT(tile, 'hazards', 4096, 'geom'), ''::bytea)
                FROM tile"""
            parameters = (*bounds, dataset_version_id, city_id)
        elif layer == "scenario_impacts":
            if network_version_id is None or scenario_id is None or algorithm_version is None:
                raise ValueError(
                    "scenario_impacts tiles require network, scenario, and algorithm versions"
                )
            query = """WITH bounds AS (SELECT ST_TileEnvelope(%s, %s, %s) AS geom),
                tile AS (
                    SELECT impact.building_gml_id, impact.distance_reduction_m,
                           impact.impact_band,
                           ST_AsMVTGeom(
                               ST_Transform(object.representative_point, 3857),
                               bounds.geom, 4096, 64, true
                           ) AS geom
                    FROM bounds, scenario_building_impacts AS impact
                    JOIN scenario_runs AS scenario ON scenario.id = impact.scenario_run_id
                    JOIN plateau_city_objects AS object
                      ON object.dataset_version_id = impact.dataset_version_id
                     AND object.gml_id = impact.building_gml_id
                    JOIN city_dataset_versions AS dataset
                      ON dataset.id = impact.dataset_version_id
                    WHERE dataset.id = %s::uuid AND dataset.city_id = %s
                      AND scenario.id = %s::uuid
                      AND scenario.network_version_id = %s::uuid
                      AND scenario.algorithm_version = %s
                      AND object.representative_point && ST_Transform(bounds.geom, 4326)
                    ORDER BY impact.building_gml_id LIMIT 50000
                )
                SELECT COALESCE(ST_AsMVT(tile, 'scenario_impacts', 4096, 'geom'), ''::bytea)
                FROM tile"""
            parameters = (
                *bounds,
                dataset_version_id,
                city_id,
                scenario_id,
                network_version_id,
                algorithm_version,
            )
        else:
            raise ValueError(f"Unsupported vector tile layer: {layer}")
        with self._connect() as connection:
            row = connection.execute(query, parameters).fetchone()
        return bytes(row[0]) if row and row[0] else b""

    def admin_snapshot(self) -> dict[str, list[dict[str, Any]]]:
        with self._connect() as connection:
            cities = connection.execute(
                """SELECT city_code, city_key, name, prefecture_name, analysis_crs, updated_at
                   FROM cities ORDER BY city_code"""
            ).fetchall()
            datasets = connection.execute(
                """SELECT city.city_code, dataset.dataset_key, dataset.title,
                          version.id, version.version_key, version.dataset_year,
                          version.verification_status, version.lifecycle_status,
                          version.quality_status, version.analysis_ready, version.registered_at
                   FROM dataset_versions AS version
                   JOIN datasets AS dataset ON dataset.id=version.dataset_id
                   JOIN cities AS city ON city.id=dataset.city_id
                   ORDER BY city.city_code, dataset.dataset_key, version.registered_at DESC"""
            ).fetchall()
            capabilities = connection.execute(
                """SELECT city.city_code, capability.capability, capability.status,
                          capability.note, capability.updated_at
                   FROM city_capabilities AS capability
                   JOIN cities AS city ON city.id=capability.city_id
                   ORDER BY city.city_code, capability.capability"""
            ).fetchall()
            networks = connection.execute(
                """SELECT dataset.city_id, network.id, network.graph_version,
                          network.source_type, network.network_type,
                          network.pedestrian_network, network.node_count,
                          network.edge_count, network.generated_at
                   FROM road_network_versions AS network
                   JOIN city_dataset_versions AS dataset
                     ON dataset.id=network.dataset_version_id
                   ORDER BY dataset.city_id, network.generated_at DESC"""
            ).fetchall()
            jobs = connection.execute(
                """SELECT city.city_code, job.id, job.job_type, job.state,
                          job.current_stage, job.retry_count, job.max_retries,
                          job.queued_at, job.started_at, job.finished_at
                   FROM job_runs AS job JOIN cities AS city ON city.id=job.city_id
                   ORDER BY job.queued_at DESC LIMIT 200"""
            ).fetchall()
            users = connection.execute(
                """SELECT user_record.id, user_record.display_name, user_record.email,
                          user_record.issuer, user_record.active,
                          COALESCE(jsonb_agg(jsonb_build_object(
                              'city_code', city.city_code, 'role', role.role
                          )) FILTER (WHERE role.role IS NOT NULL), '[]'::jsonb) AS roles
                   FROM platform_users AS user_record
                   LEFT JOIN platform_user_roles AS role ON role.user_id=user_record.id
                   LEFT JOIN cities AS city ON city.id=role.city_id
                   GROUP BY user_record.id ORDER BY user_record.display_name"""
            ).fetchall()

        def records(keys: tuple[str, ...], rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
            return [dict(zip(keys, row, strict=True)) for row in rows]

        return {
            "cities": records(
                ("city_code", "city_key", "name", "prefecture", "analysis_crs", "updated_at"),
                cities,
            ),
            "datasets": records(
                (
                    "city_code",
                    "dataset_key",
                    "title",
                    "dataset_version_id",
                    "version_key",
                    "year",
                    "verification_status",
                    "lifecycle_status",
                    "quality_status",
                    "analysis_ready",
                    "registered_at",
                ),
                datasets,
            ),
            "capabilities": records(
                ("city_code", "capability", "status", "note", "updated_at"), capabilities
            ),
            "networks": records(
                (
                    "city_code",
                    "network_version_id",
                    "graph_version",
                    "source_type",
                    "network_type",
                    "pedestrian_network",
                    "node_count",
                    "edge_count",
                    "generated_at",
                ),
                networks,
            ),
            "jobs": records(
                (
                    "city_code",
                    "job_id",
                    "job_type",
                    "state",
                    "stage",
                    "retry_count",
                    "max_retries",
                    "queued_at",
                    "started_at",
                    "finished_at",
                ),
                jobs,
            ),
            "users": records(
                ("user_id", "display_name", "email", "issuer", "active", "roles"), users
            ),
        }

    @staticmethod
    def _validation_city(connection, city_id: str) -> tuple[Any, ...] | None:
        return connection.execute(
            """SELECT id, city_code, city_key, name FROM cities
               WHERE CAST(id AS text) = %s OR city_code = %s OR city_key = %s
               ORDER BY city_code LIMIT 1""",
            (city_id, city_id, city_id),
        ).fetchone()

    def validation_claims(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT claim_key, what_it_means, what_it_does_not_mean,
                          required_data, validation_method,
                          current_validation_status, status_changed_at, updated_at
                   FROM validation_claims ORDER BY claim_key"""
            ).fetchall()
        keys = (
            "claim_key",
            "what_it_means",
            "what_it_does_not_mean",
            "required_data",
            "validation_method",
            "current_validation_status",
            "status_changed_at",
            "updated_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def city_validations(self, city_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            city = self._validation_city(connection, city_id)
            if city is None:
                return []
            rows = connection.execute(
                """SELECT run.id, run.run_key, run.claim_key, run.method_key,
                          run.urban_state_id, run.dataset_versions,
                          run.network_version_id, run.algorithm_version,
                          run.reference_source, run.sample_rule, run.metrics,
                          run.result, run.limitations, run.validation_status,
                          run.run_status, run.generated_at
                   FROM validation_runs AS run WHERE run.city_id = %s
                   ORDER BY run.generated_at DESC, run.id LIMIT %s OFFSET %s""",
                (city[0], limit, offset),
            ).fetchall()
        keys = (
            "validation_id", "run_key", "claim_key", "method_key", "urban_state_id",
            "dataset_versions", "network_version_id", "algorithm_version",
            "reference_source", "sample_rule", "metrics", "result", "limitations",
            "validation_status", "run_status", "generated_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def create_validation_run(
        self, city_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        serialized = json.dumps(request, ensure_ascii=False, sort_keys=True, default=str)
        if "ground_truth" in serialized.lower() or "confidence_percentage" in serialized.lower():
            raise ValueError("Validation references cannot claim ground truth or confidence percentages")
        context = current_request_context()
        with self._connect() as connection:
            city = self._validation_city(connection, city_id)
            if city is None:
                return None
            digest = hashlib.sha256(f"{city[0]}|{serialized}".encode()).hexdigest()
            run_key = f"validation:{city[1]}:{request['claim_key']}:{digest[:24]}"
            row = connection.execute(
                """INSERT INTO validation_runs (
                       run_key, claim_key, method_key, city_id, urban_state_id,
                       dataset_versions, network_version_id, algorithm_version,
                       reference_source, sample_rule, limitations,
                       validation_status, run_status, generated_at, created_by
                   ) VALUES (
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       'unvalidated', 'queued', now(), %s
                   ) ON CONFLICT (run_key) DO UPDATE SET run_key=EXCLUDED.run_key
                   RETURNING id, run_key, validation_status, run_status, generated_at""",
                (
                    run_key,
                    request["claim_key"],
                    request["method_key"],
                    city[0],
                    request.get("urban_state_id"),
                    json.dumps(request["dataset_versions"], ensure_ascii=False),
                    request.get("network_version_id"),
                    request["algorithm_version"],
                    json.dumps(request["reference_source"], ensure_ascii=False),
                    json.dumps(request["sample_rule"], ensure_ascii=False),
                    json.dumps(request["limitations"], ensure_ascii=False),
                    context.actor,
                ),
            ).fetchone()
            self._audit(
                connection,
                "validation.run.create",
                "validation_run",
                str(row[0]),
                str(city[0]),
                None,
                {"run_key": row[1], "validation_status": row[2], "run_status": row[3]},
            )
            connection.commit()
        return {
            "validation_id": row[0],
            "run_key": row[1],
            "validation_status": row[2],
            "run_status": row[3],
            "generated_at": row[4],
        }

    def validation_detail(self, validation_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT run.id, run.run_key, city.city_code, city.city_key,
                          run.claim_key, claim.what_it_means, claim.what_it_does_not_mean,
                          run.method_key, run.urban_state_id, run.dataset_versions,
                          run.network_version_id, run.algorithm_version,
                          run.reference_source, run.sample_rule, run.metrics,
                          run.result, run.limitations, run.validation_status,
                          run.run_status, run.generated_at,
                          (SELECT count(*) FROM validation_samples sample
                           WHERE sample.validation_run_id=run.id),
                          (SELECT count(*) FROM validation_disagreements disagreement
                           WHERE disagreement.validation_run_id=run.id)
                   FROM validation_runs AS run
                   JOIN cities AS city ON city.id=run.city_id
                   JOIN validation_claims AS claim ON claim.claim_key=run.claim_key
                   WHERE run.id=%s""",
                (validation_id,),
            ).fetchone()
        if row is None:
            return None
        keys = (
            "validation_id", "run_key", "city_code", "city_id", "claim_key",
            "what_it_means", "what_it_does_not_mean", "method_key", "urban_state_id",
            "dataset_versions", "network_version_id", "algorithm_version",
            "reference_source", "sample_rule", "metrics", "result", "limitations",
            "validation_status", "run_status", "generated_at", "sample_count",
            "disagreement_count",
        )
        return dict(zip(keys, row, strict=True))

    def validation_samples(
        self,
        validation_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, sample_key, strata, origin_reference,
                          destination_reference, origin_snap, destination_snap,
                          sampling_rank, metadata, ST_AsGeoJSON(geometry)::jsonb
                   FROM validation_samples
                   WHERE validation_run_id=%s AND geometry IS NOT NULL
                     AND ST_Intersects(geometry, ST_MakeEnvelope(%s,%s,%s,%s,4326))
                   ORDER BY sampling_rank, sample_key LIMIT %s OFFSET %s""",
                (validation_id, *bbox, limit, offset),
            ).fetchall()
        keys = (
            "validation_sample_id", "sample_key", "strata", "origin_reference",
            "destination_reference", "origin_snap", "destination_snap", "sampling_rank",
            "metadata", "geometry",
        )
        return {
            "validation_id": validation_id,
            "bbox": bbox,
            "limit": limit,
            "offset": offset,
            "features": [dict(zip(keys, row, strict=True)) for row in rows],
        }

    def validation_disagreements(
        self,
        validation_id: str,
        bbox: tuple[float, float, float, float],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT disagreement.id, sample.sample_key,
                          disagreement.disagreement_class,
                          disagreement.primary_value, disagreement.reference_value,
                          disagreement.cause_candidate, disagreement.cause_rule,
                          disagreement.priority_rank,
                          ST_AsGeoJSON(disagreement.geometry)::jsonb
                   FROM validation_disagreements AS disagreement
                   JOIN validation_samples AS sample
                     ON sample.id=disagreement.validation_sample_id
                   WHERE disagreement.validation_run_id=%s
                     AND disagreement.geometry IS NOT NULL
                     AND ST_Intersects(
                         disagreement.geometry, ST_MakeEnvelope(%s,%s,%s,%s,4326)
                     )
                   ORDER BY disagreement.priority_rank NULLS LAST, sample.sample_key
                   LIMIT %s OFFSET %s""",
                (validation_id, *bbox, limit, offset),
            ).fetchall()
        keys = (
            "disagreement_id", "sample_key", "disagreement_class", "primary_value",
            "reference_value", "cause_candidate", "cause_rule", "priority_rank", "geometry",
        )
        return {
            "validation_id": validation_id,
            "bbox": bbox,
            "limit": limit,
            "offset": offset,
            "features": [dict(zip(keys, row, strict=True)) for row in rows],
        }

    def validation_sensitivity(
        self, validation_id: str, limit: int, offset: int
    ) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, category, known_limitation, sensitivity_evidence,
                          reference_agreement, coverage, validation_status, created_at
                   FROM model_uncertainty WHERE validation_run_id=%s
                   ORDER BY category, id LIMIT %s OFFSET %s""",
                (validation_id, limit, offset),
            ).fetchall()
        keys = (
            "uncertainty_id", "category", "known_limitation", "sensitivity_evidence",
            "reference_agreement", "coverage", "validation_status", "created_at",
        )
        return {
            "validation_id": validation_id,
            "aggregation_score": None,
            "limit": limit,
            "offset": offset,
            "uncertainties": [dict(zip(keys, row, strict=True)) for row in rows],
        }

    def create_validation_field_review(
        self, validation_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        longitude = request.get("longitude")
        latitude = request.get("latitude")
        if (longitude is None) != (latitude is None):
            raise ValueError("Field review GPS requires both longitude and latitude")
        context = current_request_context()
        with self._connect() as connection:
            result = connection.execute(
                """SELECT result.id, run.city_id FROM validation_results AS result
                   JOIN validation_runs AS run ON run.id=result.validation_run_id
                   WHERE result.id=%s AND run.id=%s""",
                (request["validation_result_id"], validation_id),
            ).fetchone()
            if result is None:
                return None
            status = (
                "submitted"
                if request["municipal_feedback"] == "not_reviewed"
                else "reviewed"
            )
            row = connection.execute(
                """INSERT INTO field_validation (
                       validation_result_id, observation_type,
                       observed_accessibility_issue, road_passability,
                       facility_availability, gps, observed_at, reviewer,
                       evidence_attachment_reference, municipal_feedback,
                       review_note, status
                   ) VALUES (
                       %s,%s,%s,%s,%s,
                       CASE WHEN %s IS NULL THEN NULL ELSE
                           ST_SetSRID(ST_MakePoint(%s,%s),4326) END,
                       %s,%s,%s,%s,%s,%s
                   ) RETURNING id, municipal_feedback, status, created_at""",
                (
                    result[0], request["observation_type"],
                    request.get("observed_accessibility_issue"),
                    request.get("road_passability"), request.get("facility_availability"),
                    longitude, longitude, latitude, request["observed_at"], context.actor,
                    request.get("evidence_attachment_reference"),
                    request["municipal_feedback"], request.get("review_note", ""), status,
                ),
            ).fetchone()
            self._audit(
                connection,
                "validation.field_review.create",
                "field_validation",
                str(row[0]),
                str(result[1]),
                None,
                {"municipal_feedback": row[1], "status": row[2]},
            )
            connection.commit()
        return {
            "field_validation_id": row[0],
            "municipal_feedback": row[1],
            "status": row[2],
            "created_at": row[3],
        }

    def update_validation_status(
        self, validation_id: str, expected: str, proposed: str, note: str
    ) -> dict[str, Any] | None:
        context = current_request_context()
        with self._connect() as connection:
            current = connection.execute(
                """SELECT id, city_id, validation_status FROM validation_runs
                   WHERE id=%s FOR UPDATE""",
                (validation_id,),
            ).fetchone()
            if current is None:
                return None
            if str(current[2]) != expected:
                raise ValueError(f"Validation status is {current[2]}, expected {expected}")
            updated = connection.execute(
                """UPDATE validation_runs SET validation_status=%s
                   WHERE id=%s RETURNING validation_status, generated_at""",
                (proposed, validation_id),
            ).fetchone()
            self._audit(
                connection,
                "validation.status.change",
                "validation_run",
                validation_id,
                str(current[1]),
                {"validation_status": expected},
                {"validation_status": proposed, "note": note, "changed_by": context.actor},
            )
            connection.commit()
        return {
            "validation_id": validation_id,
            "validation_status": updated[0],
            "generated_at": updated[1],
            "automatic_promotion": False,
        }

    def register_validation_reference(
        self, city_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        context = current_request_context()
        with self._connect() as connection:
            city = self._validation_city(connection, city_id)
            if city is None:
                return None
            row = connection.execute(
                """INSERT INTO validation_reference_datasets (
                       city_id, reference_key, source_type, source_url,
                       retrieval_date, source_sha256, license, attribution,
                       extraction_rule, coverage, status, limitations, registered_by
                   ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (city_id, reference_key) DO UPDATE SET
                       source_type=EXCLUDED.source_type,
                       source_url=EXCLUDED.source_url,
                       retrieval_date=EXCLUDED.retrieval_date,
                       source_sha256=EXCLUDED.source_sha256,
                       license=EXCLUDED.license,
                       attribution=EXCLUDED.attribution,
                       extraction_rule=EXCLUDED.extraction_rule,
                       coverage=EXCLUDED.coverage,
                       status=EXCLUDED.status,
                       limitations=EXCLUDED.limitations,
                       registered_by=EXCLUDED.registered_by,
                       registered_at=now()
                   RETURNING id, reference_key, status, registered_at""",
                (
                    city[0], request["reference_key"], request["source_type"],
                    request["source_url"], request["retrieval_date"],
                    request["source_sha256"], request["license"], request["attribution"],
                    request["extraction_rule"], json.dumps(request["coverage"], ensure_ascii=False),
                    request["status"], json.dumps(request["limitations"], ensure_ascii=False),
                    context.actor,
                ),
            ).fetchone()
            self._audit(
                connection,
                "validation.reference.register",
                "validation_reference_dataset",
                str(row[0]),
                str(city[0]),
                None,
                {"reference_key": row[1], "status": row[2]},
            )
            connection.commit()
        return {
            "validation_reference_id": row[0],
            "reference_key": row[1],
            "status": row[2],
            "registered_at": row[3],
        }

    def audit_events(self, city_id: str | None, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT actor, action, resource_type, resource_id, city_id,
                          request_id, before_state, after_state, occurred_at
                   FROM audit_log WHERE (CAST(%s AS text) IS NULL OR city_id = %s)
                   ORDER BY occurred_at DESC, id DESC LIMIT %s""",
                (city_id, city_id, limit),
            ).fetchall()
        keys = (
            "actor",
            "action",
            "resource_type",
            "resource_id",
            "city_id",
            "request_id",
            "before",
            "after",
            "timestamp",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]
