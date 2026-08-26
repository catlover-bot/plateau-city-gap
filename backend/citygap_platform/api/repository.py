"""Small query boundary that keeps HTTP and PostGIS concerns separate."""

from __future__ import annotations

import json
from typing import Any, Protocol

from backend.citygap_platform.domain.scenarios import validate_status_transition


class PlatformRepository(Protocol):
    def health(self) -> bool: ...

    def cities(self) -> list[dict[str, Any]]: ...

    def layers(self, city_id: str) -> list[dict[str, Any]]: ...

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
                          network.network_type, network.official_generator_executed,
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
                         AND (%s IS NULL OR network.graph_version = %s)
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
                       ST_MakeEnvelope(%s, %s, %s, %s, 4326), 6674
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
                     AND (%s IS NULL OR network.graph_version = %s)
                     AND run.status = 'succeeded'
                   ORDER BY network.generated_at DESC, object.gml_id""",
                (city_id, edge_id, graph_version, graph_version),
            ).fetchall()
        return self._context_rows(rows)

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
                     AND (%s IS NULL OR scenario.lifecycle_status = %s)
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
                          check_row.checked_at, check_row.updated_at
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
            connection.execute(
                """INSERT INTO scenario_field_checks (
                       scenario_run_id, site_order, site_access, road_safety,
                       land_ownership_unknown, existing_service, facility_condition,
                       hazard_confirmation, operator_consultation, notes, checked_at
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                   ON CONFLICT (scenario_run_id, site_order) DO UPDATE SET
                       site_access = EXCLUDED.site_access,
                       road_safety = EXCLUDED.road_safety,
                       land_ownership_unknown = EXCLUDED.land_ownership_unknown,
                       existing_service = EXCLUDED.existing_service,
                       facility_condition = EXCLUDED.facility_condition,
                       hazard_confirmation = EXCLUDED.hazard_confirmation,
                       operator_consultation = EXCLUDED.operator_consultation,
                       notes = EXCLUDED.notes, checked_at = now(), updated_at = now()""",
                (
                    scenario_id,
                    site_order,
                    *(checklist[name] for name in fields),
                    checklist["notes"],
                ),
            )
            connection.commit()
        return self.field_check(city_id, scenario_id, site_order)
