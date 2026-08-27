"""Load canonical Parquet spatial-context artifacts into PostGIS."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


def context_config_hash(summary: dict[str, Any]) -> str:
    inputs = {
        "algorithm_version": summary["algorithm_version"],
        "archive_sha256": summary["dataset"]["archive_sha256"],
        "analysis_crs": summary["dataset"]["analysis_crs"],
        "targets": summary["targets"],
        "hazard_interpretation": summary["hazard_interpretation"],
    }
    canonical = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _rows(frame: pd.DataFrame, columns: list[str]):
    for row in frame[columns].itertuples(index=False, name=None):
        yield tuple(None if pd.isna(value) else value for value in row)


def _copy(connection: Any, table: str, columns: list[str], rows: Any) -> None:
    names = ", ".join(columns)
    with connection.cursor().copy(f"COPY {table} ({names}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def _require_files(output: Path, artifact_prefix: str) -> dict[str, Path]:
    files = {
        "summary": output / f"{artifact_prefix}_plateau_context_summary.json",
        "landuse": output / f"{artifact_prefix}_plateau_landuse.parquet",
        "planning": output / f"{artifact_prefix}_plateau_urban_planning.parquet",
        "hazards": output / f"{artifact_prefix}_plateau_hazards.parquet",
        "building": output / f"{artifact_prefix}_building_plateau_context.parquet",
        "mesh": output / f"{artifact_prefix}_mesh_plateau_context.parquet",
        "candidate": output / f"{artifact_prefix}_scenario_candidate_context.parquet",
        "road": output / f"{artifact_prefix}_road_hazard_context.parquet",
        "road_edges": output / f"{artifact_prefix}_road_graph_edges.parquet",
    }
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Build context and road-network artifacts before PostGIS load: " + ", ".join(missing)
        )
    return files


def load_context_artifacts(
    database_url: str,
    output_directory: str | Path,
    artifact_prefix: str = "maizuru",
) -> dict[str, Any]:
    """Load a verified context run; this does not claim DB execution until called."""

    import psycopg

    output = Path(output_directory)
    files = _require_files(output, artifact_prefix)
    summary = json.loads(files["summary"].read_text(encoding="utf-8"))
    config_hash = context_config_hash(summary)
    landuse = pd.read_parquet(files["landuse"])
    planning = pd.read_parquet(files["planning"])
    hazards = pd.read_parquet(files["hazards"])
    buildings = pd.read_parquet(files["building"])
    meshes = pd.read_parquet(files["mesh"])
    candidates = pd.read_parquet(files["candidate"])
    roads = pd.read_parquet(files["road"])
    road_edges = pd.read_parquet(files["road_edges"])
    graph_versions = set(road_edges.graph_version.dropna().astype(str))
    if len(graph_versions) != 1:
        raise ValueError("Road artifact must contain exactly one graph_version")
    graph_version = next(iter(graph_versions))

    counts: dict[str, int] = {}
    with psycopg.connect(database_url) as connection:
        dataset = connection.execute(
            """SELECT id FROM city_dataset_versions
               WHERE city_id = %s AND archive_sha256 = %s AND is_current""",
            (summary["city"]["city_id"], summary["dataset"]["archive_sha256"]),
        ).fetchone()
        if dataset is None:
            raise RuntimeError("Matching current CityGML dataset version is not loaded")
        dataset_version_id = dataset[0]
        network = connection.execute(
            """SELECT id FROM road_network_versions
               WHERE dataset_version_id = %s AND graph_version = %s""",
            (dataset_version_id, graph_version),
        ).fetchone()
        if network is None:
            raise RuntimeError("Matching road-network version is not loaded")
        network_version_id = network[0]
        run_id = connection.execute(
            """INSERT INTO spatial_context_runs (
                   dataset_version_id, network_version_id, algorithm_version,
                   analysis_crs, config_hash, source_archive_sha256,
                   status, started_at, metadata
               ) VALUES (%s, %s, %s, %s, %s, %s, 'running', now(), %s)
               ON CONFLICT (dataset_version_id, algorithm_version, config_hash)
               DO UPDATE SET network_version_id = EXCLUDED.network_version_id,
                   status = 'running', started_at = now(), completed_at = NULL,
                   metadata = EXCLUDED.metadata
               RETURNING id""",
            (
                dataset_version_id,
                network_version_id,
                summary["algorithm_version"],
                summary["dataset"]["analysis_crs"],
                config_hash,
                summary["dataset"]["archive_sha256"],
                json.dumps({"artifact_summary": files["summary"].name}),
            ),
        ).fetchone()[0]
        connection.commit()

        try:
            connection.execute(
                """CREATE TEMP TABLE context_landuse (
                       gml_id text, class_code text, class_label text, class_codelist text,
                       source_area_m2 double precision, survey_year integer
                   ) ON COMMIT DROP"""
            )
            _copy(
                connection,
                "context_landuse",
                [
                    "gml_id",
                    "class_code",
                    "class_label",
                    "class_codelist",
                    "source_area_m2",
                    "survey_year",
                ],
                _rows(
                    landuse,
                    [
                        "gml_id",
                        "class_code",
                        "class_label",
                        "class_codelist",
                        "source_area_m2",
                        "survey_year",
                    ],
                ),
            )
            counts["landuse"] = connection.execute(
                """UPDATE plateau_landuse AS target SET
                       class_code = source.class_code,
                       class_label = source.class_label,
                       class_codelist = source.class_codelist,
                       source_area_m2 = source.source_area_m2,
                       survey_year = source.survey_year
                   FROM context_landuse AS source, plateau_city_objects AS object
                   WHERE target.city_object_id = object.id
                     AND object.dataset_version_id = %s AND object.gml_id = source.gml_id""",
                (dataset_version_id,),
            ).rowcount

            connection.execute(
                """CREATE TEMP TABLE context_planning (
                       gml_id text, planning_type text, function_code text,
                       function_label text, function_codelist text,
                       urban_plan_type_code text, urban_plan_type_label text,
                       urban_plan_type_codelist text, building_coverage_rate double precision,
                       floor_area_rate double precision, valid_from date, custodian text
                   ) ON COMMIT DROP"""
            )
            planning_columns = [
                "gml_id",
                "planning_type",
                "function_code",
                "function_label",
                "function_codelist",
                "urban_plan_type_code",
                "urban_plan_type_label",
                "urban_plan_type_codelist",
                "building_coverage_rate",
                "floor_area_rate",
                "valid_from",
                "custodian",
            ]
            _copy(
                connection,
                "context_planning",
                planning_columns,
                _rows(planning, planning_columns),
            )
            counts["planning"] = connection.execute(
                """UPDATE plateau_urban_planning AS target SET
                       planning_type = source.planning_type,
                       function_code = source.function_code,
                       function_label = source.function_label,
                       function_codelist = source.function_codelist,
                       urban_plan_type_code = source.urban_plan_type_code,
                       urban_plan_type_label = source.urban_plan_type_label,
                       urban_plan_type_codelist = source.urban_plan_type_codelist,
                       building_coverage_rate = source.building_coverage_rate,
                       floor_area_rate = source.floor_area_rate,
                       valid_from = source.valid_from, custodian = source.custodian
                   FROM context_planning AS source, plateau_city_objects AS object
                   WHERE target.city_object_id = object.id
                     AND object.dataset_version_id = %s AND object.gml_id = source.gml_id""",
                (dataset_version_id,),
            ).rowcount

            connection.execute(
                """CREATE TEMP TABLE context_hazard (
                       gml_id text, hazard_type text, rank_code text, rank_label text,
                       rank_codelist text, description_code text, description_label text,
                       disaster_type_code text, disaster_type_label text,
                       area_type_code text, area_type_label text, valid_from date,
                       location text, zone_number text, zone_name text
                   ) ON COMMIT DROP"""
            )
            hazard_columns = [
                "gml_id",
                "hazard_type",
                "rank_code",
                "rank_label",
                "rank_codelist",
                "description_code",
                "description_label",
                "disaster_type_code",
                "disaster_type_label",
                "area_type_code",
                "area_type_label",
                "valid_from",
                "location",
                "zone_number",
                "zone_name",
            ]
            _copy(connection, "context_hazard", hazard_columns, _rows(hazards, hazard_columns))
            counts["hazards"] = connection.execute(
                """UPDATE plateau_hazards AS target SET
                       hazard_type = source.hazard_type, rank_code = source.rank_code,
                       rank_description = source.rank_label,
                       rank_codelist = source.rank_codelist,
                       description_code = source.description_code,
                       description_label = source.description_label,
                       disaster_type_code = source.disaster_type_code,
                       disaster_type_label = source.disaster_type_label,
                       area_type_code = source.area_type_code,
                       area_type_label = source.area_type_label,
                       valid_from = source.valid_from, location = source.location,
                       zone_number = source.zone_number, zone_name = source.zone_name,
                       depth_m = NULL
                   FROM context_hazard AS source, plateau_city_objects AS object
                   WHERE target.city_object_id = object.id
                     AND object.dataset_version_id = %s AND object.gml_id = source.gml_id""",
                (dataset_version_id,),
            ).rowcount

            connection.execute(
                """CREATE TEMP TABLE context_building_relation (
                       building_gml_id text, context_gml_id text, context_type text,
                       review_status text, siting_feasibility text
                   ) ON COMMIT DROP"""
            )
            building_columns = [
                "gml_id",
                "context_gml_id",
                "context_type",
                "review_status",
                "siting_feasibility",
            ]
            _copy(
                connection,
                "context_building_relation",
                [
                    "building_gml_id",
                    "context_gml_id",
                    "context_type",
                    "review_status",
                    "siting_feasibility",
                ],
                _rows(buildings, building_columns),
            )
            connection.execute(
                "DELETE FROM building_spatial_context WHERE context_run_id = %s", (run_id,)
            )
            counts["building_relations"] = connection.execute(
                """INSERT INTO building_spatial_context (
                       context_run_id, building_city_object_id, context_city_object_id,
                       context_type, review_status, siting_feasibility
                   ) SELECT %s, building.id, context.id, source.context_type,
                            source.review_status, source.siting_feasibility
                     FROM context_building_relation AS source
                     JOIN plateau_city_objects AS building
                       ON building.dataset_version_id = %s
                      AND building.gml_id = source.building_gml_id
                     JOIN plateau_city_objects AS context
                       ON context.dataset_version_id = %s
                      AND context.gml_id = source.context_gml_id""",
                (run_id, dataset_version_id, dataset_version_id),
            ).rowcount

            connection.execute(
                """CREATE TEMP TABLE context_mesh_relation (
                       mesh_code text, context_gml_id text, context_type text,
                       intersection_area_m2 double precision, review_status text,
                       siting_feasibility text
                   ) ON COMMIT DROP"""
            )
            mesh_columns = [
                "mesh_code",
                "gml_id",
                "context_type",
                "intersection_area_m2",
                "review_status",
                "siting_feasibility",
            ]
            _copy(
                connection,
                "context_mesh_relation",
                [
                    "mesh_code",
                    "context_gml_id",
                    "context_type",
                    "intersection_area_m2",
                    "review_status",
                    "siting_feasibility",
                ],
                _rows(meshes, mesh_columns),
            )
            connection.execute(
                "DELETE FROM mesh_spatial_context WHERE context_run_id = %s", (run_id,)
            )
            counts["mesh_relations"] = connection.execute(
                """INSERT INTO mesh_spatial_context (
                       context_run_id, mesh_code, context_city_object_id, context_type,
                       intersection_area_m2, review_status, siting_feasibility
                   ) SELECT %s, source.mesh_code, context.id, source.context_type,
                            source.intersection_area_m2, source.review_status,
                            source.siting_feasibility
                     FROM context_mesh_relation AS source
                     JOIN plateau_city_objects AS context
                       ON context.dataset_version_id = %s
                      AND context.gml_id = source.context_gml_id""",
                (run_id, dataset_version_id),
            ).rowcount

            connection.execute(
                """CREATE TEMP TABLE context_candidate_relation (
                       candidate_id text, context_gml_id text, context_type text,
                       candidate_x double precision, candidate_y double precision,
                       review_status text, siting_feasibility text
                   ) ON COMMIT DROP"""
            )
            candidate_columns = [
                "candidate_id",
                "gml_id",
                "context_type",
                "candidate_x",
                "candidate_y",
                "review_status",
                "siting_feasibility",
            ]
            _copy(
                connection,
                "context_candidate_relation",
                [
                    "candidate_id",
                    "context_gml_id",
                    "context_type",
                    "candidate_x",
                    "candidate_y",
                    "review_status",
                    "siting_feasibility",
                ],
                _rows(candidates, candidate_columns),
            )
            connection.execute(
                "DELETE FROM scenario_candidate_spatial_context WHERE context_run_id = %s",
                (run_id,),
            )
            counts["candidate_relations"] = connection.execute(
                """INSERT INTO scenario_candidate_spatial_context (
                       context_run_id, candidate_id, context_city_object_id, context_type,
                       candidate_geom, review_status, siting_feasibility
                   ) SELECT %s, source.candidate_id, context.id, source.context_type,
                            ST_SetSRID(ST_MakePoint(source.candidate_x, source.candidate_y), 6674),
                            source.review_status, source.siting_feasibility
                     FROM context_candidate_relation AS source
                     JOIN plateau_city_objects AS context
                       ON context.dataset_version_id = %s
                      AND context.gml_id = source.context_gml_id""",
                (run_id, dataset_version_id),
            ).rowcount

            connection.execute(
                """CREATE TEMP TABLE context_road_relation (
                       edge_id text, hazard_gml_id text, intersection_length_m double precision
                   ) ON COMMIT DROP"""
            )
            _copy(
                connection,
                "context_road_relation",
                ["edge_id", "hazard_gml_id", "intersection_length_m"],
                _rows(roads, ["edge_id", "gml_id", "intersection_length_m"]),
            )
            connection.execute(
                "DELETE FROM road_hazard_context WHERE context_run_id = %s", (run_id,)
            )
            counts["road_relations"] = connection.execute(
                """INSERT INTO road_hazard_context (
                       context_run_id, network_version_id, edge_id,
                       hazard_city_object_id, intersection_length_m
                   ) SELECT %s, %s, source.edge_id, hazard.id,
                            source.intersection_length_m
                     FROM context_road_relation AS source
                     JOIN plateau_city_objects AS hazard
                       ON hazard.dataset_version_id = %s
                      AND hazard.gml_id = source.hazard_gml_id""",
                (run_id, network_version_id, dataset_version_id),
            ).rowcount

            expected = {
                "landuse": len(landuse),
                "planning": len(planning),
                "hazards": len(hazards),
                "building_relations": len(buildings),
                "mesh_relations": len(meshes),
                "candidate_relations": len(candidates),
                "road_relations": len(roads),
            }
            if counts != expected:
                raise RuntimeError(
                    f"PostGIS row-count mismatch: expected={expected}, actual={counts}"
                )
            connection.execute(
                """UPDATE spatial_context_runs SET status = 'succeeded', completed_at = now(),
                       metadata = metadata || %s::jsonb WHERE id = %s""",
                (json.dumps({"loaded_rows": counts}), run_id),
            )
            connection.commit()
        except Exception as error:
            connection.rollback()
            connection.execute(
                """UPDATE spatial_context_runs SET status = 'failed', completed_at = now(),
                       metadata = metadata || %s::jsonb WHERE id = %s""",
                (json.dumps({"error": str(error)[:4000]}), run_id),
            )
            connection.commit()
            raise

    return {
        "context_run_id": str(run_id),
        "dataset_version_id": str(dataset_version_id),
        "network_version_id": str(network_version_id),
        "config_hash": config_hash,
        "loaded_rows": counts,
        "database_executed": True,
    }
