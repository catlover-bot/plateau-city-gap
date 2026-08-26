"""Load canonical scenario Parquets into the version-matched PostGIS workspace."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

TABLE_NAMES = (
    "scenario_runs",
    "scenario_sites",
    "scenario_objectives",
    "scenario_constraints",
    "scenario_impacts",
    "scenario_context",
    "scenario_evidence",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_scenario_files(output: str | Path) -> tuple[dict[str, Any], dict[str, Path]]:
    directory = Path(output)
    manifest_path = directory / "maizuru_scenario_canonical_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("database_executed") is not False:
        raise ValueError("Canonical manifest must not pre-claim database execution")
    paths = {}
    for table in TABLE_NAMES:
        artifact = manifest["canonical_tables"][table]
        path = directory / artifact["file"]
        if not path.exists():
            raise FileNotFoundError(path)
        if path.stat().st_size != artifact["size_bytes"] or _sha256(path) != artifact["sha256"]:
            raise ValueError(f"Canonical scenario artifact does not match manifest: {path.name}")
        paths[table] = path
    return manifest, paths


def _value(value: Any) -> Any:
    return None if pd.isna(value) else value


def _json(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    return json.loads(str(value))


def load_scenario_artifacts(database_url: str, output: str | Path) -> dict[str, Any]:
    """Persist the exact canonical run versions; no implicit latest-version selection is used."""

    import psycopg

    manifest, paths = canonical_scenario_files(output)
    frames = {name: pd.read_parquet(path) for name, path in paths.items()}
    expected = {name: int(manifest["canonical_tables"][name]["row_count"]) for name in TABLE_NAMES}
    if {name: len(frame) for name, frame in frames.items()} != expected:
        raise ValueError("Canonical scenario row counts do not match the manifest")

    counts = {name: 0 for name in TABLE_NAMES}
    with psycopg.connect(database_url) as connection:
        dataset = connection.execute(
            """SELECT id FROM city_dataset_versions
               WHERE city_id = %s AND dataset_year = %s AND archive_sha256 = %s""",
            (
                manifest["city"]["city_id"],
                int(manifest["dataset_version_key"].split(":", 2)[1]),
                manifest["dataset_version_key"].split(":", 2)[2],
            ),
        ).fetchone()
        if dataset is None:
            raise RuntimeError("Exact scenario dataset version is not loaded")
        dataset_version_id = dataset[0]
        network = connection.execute(
            """SELECT id FROM road_network_versions
               WHERE dataset_version_id = %s AND graph_version = %s""",
            (dataset_version_id, manifest["network_version"]),
        ).fetchone()
        if network is None:
            raise RuntimeError("Exact scenario network version is not loaded")
        network_version_id = network[0]
        context = connection.execute(
            """SELECT id FROM spatial_context_runs
               WHERE dataset_version_id = %s AND network_version_id = %s
                 AND algorithm_version = %s AND config_hash = %s AND status = 'succeeded'""",
            (
                dataset_version_id,
                network_version_id,
                manifest["context_version"],
                manifest["context_config_hash"],
            ),
        ).fetchone()
        if context is None:
            raise RuntimeError("Exact succeeded spatial-context version is not loaded")
        context_run_id = context[0]

        for row in frames["scenario_runs"].itertuples(index=False):
            connection.execute(
                """INSERT INTO scenario_runs (
                       id, scenario_key, dataset_version_id, network_version_id,
                       context_run_id, plateau_product_specification_version,
                       algorithm_version, objective_mode, objective_definition,
                       site_count, candidate_count, algorithm_kind, config_hash,
                       generated_at, runtime_seconds, lifecycle_status, metadata
                   ) VALUES (
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, 'draft', %s
                   ) ON CONFLICT (id) DO UPDATE SET
                       objective_definition = EXCLUDED.objective_definition,
                       runtime_seconds = EXCLUDED.runtime_seconds,
                       metadata = EXCLUDED.metadata, updated_at = now()""",
                (
                    row.scenario_run_id,
                    row.scenario_key,
                    dataset_version_id,
                    network_version_id,
                    context_run_id,
                    row.plateau_product_specification_version,
                    row.algorithm_version,
                    row.objective_mode,
                    row.objective_definition,
                    int(row.site_count),
                    int(row.candidate_count),
                    row.algorithm_kind,
                    row.config_hash,
                    row.generated_at,
                    float(row.runtime_seconds),
                    json.dumps(_json(row.metadata_json), ensure_ascii=False),
                ),
            )
            connection.execute(
                """INSERT INTO scenario_lifecycle_events (
                       scenario_run_id, from_status, to_status, note
                   ) SELECT %s, NULL, 'draft', 'canonical scenario import'
                     WHERE NOT EXISTS (
                       SELECT 1 FROM scenario_lifecycle_events WHERE scenario_run_id = %s
                     )""",
                (row.scenario_run_id, row.scenario_run_id),
            )
            counts["scenario_runs"] += 1

        for row in frames["scenario_sites"].itertuples(index=False):
            connection.execute(
                """INSERT INTO scenario_sites (
                       scenario_run_id, site_order, candidate_id, network_node_id,
                       road_gml_id, road_surface_id, road_name,
                       existing_transport_distance_m, component_id,
                       candidate_to_graph_connector_m, siting_feasibility, geom
                   ) VALUES (
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                   ) ON CONFLICT (scenario_run_id, site_order) DO UPDATE SET
                       candidate_id = EXCLUDED.candidate_id,
                       network_node_id = EXCLUDED.network_node_id,
                       road_gml_id = EXCLUDED.road_gml_id,
                       road_surface_id = EXCLUDED.road_surface_id,
                       road_name = EXCLUDED.road_name,
                       existing_transport_distance_m = EXCLUDED.existing_transport_distance_m,
                       component_id = EXCLUDED.component_id,
                       candidate_to_graph_connector_m = EXCLUDED.candidate_to_graph_connector_m,
                       siting_feasibility = EXCLUDED.siting_feasibility,
                       geom = EXCLUDED.geom""",
                (
                    row.scenario_run_id,
                    int(row.site_order),
                    row.candidate_id,
                    row.network_node_id,
                    row.road_gml_id,
                    row.road_surface_id,
                    _value(row.road_name),
                    float(row.existing_transport_distance_m),
                    row.component_id,
                    float(row.candidate_to_graph_connector_m),
                    row.siting_feasibility,
                    float(row.longitude),
                    float(row.latitude),
                ),
            )
            counts["scenario_sites"] += 1

        for run_id in frames["scenario_constraints"].scenario_run_id.unique():
            connection.execute(
                "DELETE FROM scenario_constraints WHERE scenario_run_id = %s", (run_id,)
            )
        for row in frames["scenario_constraints"].itertuples(index=False):
            connection.execute(
                """INSERT INTO scenario_constraints (
                       scenario_run_id, site_order, constraint_name, threshold,
                       observed, satisfied, interpretation
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    row.scenario_run_id,
                    None if pd.isna(row.site_order) else int(row.site_order),
                    row.constraint_name,
                    json.dumps(_json(row.threshold_json), ensure_ascii=False),
                    json.dumps(_json(row.observed_json), ensure_ascii=False),
                    _value(row.satisfied),
                    row.interpretation,
                ),
            )
            counts["scenario_constraints"] += 1

        for row in frames["scenario_objectives"].itertuples(index=False):
            connection.execute(
                """INSERT INTO scenario_objectives (
                       scenario_run_id, objective_name, objective_role, value,
                       unit, definition, metadata
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (scenario_run_id, objective_name) DO UPDATE SET
                       objective_role = EXCLUDED.objective_role, value = EXCLUDED.value,
                       unit = EXCLUDED.unit, definition = EXCLUDED.definition,
                       metadata = EXCLUDED.metadata""",
                (
                    row.scenario_run_id,
                    row.objective_name,
                    row.objective_role,
                    _value(row.value),
                    row.unit,
                    row.definition,
                    json.dumps(_json(row.metadata_json), ensure_ascii=False),
                ),
            )
            counts["scenario_objectives"] += 1

        for row in frames["scenario_impacts"].itertuples(index=False):
            connection.execute(
                """INSERT INTO scenario_impacts (
                       scenario_run_id, metric_name, value, unit, interpretation
                   ) VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (scenario_run_id, metric_name) DO UPDATE SET
                       value = EXCLUDED.value, unit = EXCLUDED.unit,
                       interpretation = EXCLUDED.interpretation""",
                (
                    row.scenario_run_id,
                    row.metric_name,
                    float(row.value),
                    row.unit,
                    _value(row.interpretation),
                ),
            )
            counts["scenario_impacts"] += 1

        for row in frames["scenario_context"].itertuples(index=False):
            connection.execute(
                """INSERT INTO scenario_context (
                       scenario_run_id, site_order, context_type, label,
                       feature_count, review_status, siting_feasibility, source_payload
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (scenario_run_id, site_order, context_type) DO UPDATE SET
                       label = EXCLUDED.label, feature_count = EXCLUDED.feature_count,
                       review_status = EXCLUDED.review_status,
                       siting_feasibility = EXCLUDED.siting_feasibility,
                       source_payload = EXCLUDED.source_payload""",
                (
                    row.scenario_run_id,
                    int(row.site_order),
                    row.context_type,
                    _value(row.label),
                    None if pd.isna(row.feature_count) else int(row.feature_count),
                    _value(row.review_status),
                    row.siting_feasibility,
                    json.dumps(_json(row.source_payload_json), ensure_ascii=False),
                ),
            )
            counts["scenario_context"] += 1

        for row in frames["scenario_evidence"].itertuples(index=False):
            connection.execute(
                """INSERT INTO scenario_evidence (
                       scenario_run_id, representative_building_gml_id,
                       virtual_candidate_id, route_semantics, evidence
                   ) VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (scenario_run_id) DO UPDATE SET
                       representative_building_gml_id = EXCLUDED.representative_building_gml_id,
                       virtual_candidate_id = EXCLUDED.virtual_candidate_id,
                       route_semantics = EXCLUDED.route_semantics,
                       evidence = EXCLUDED.evidence""",
                (
                    row.scenario_run_id,
                    row.representative_building_gml_id,
                    row.virtual_candidate_id,
                    row.route_semantics,
                    json.dumps(_json(row.evidence_json), ensure_ascii=False),
                ),
            )
            counts["scenario_evidence"] += 1

        if counts != expected:
            raise RuntimeError(f"PostGIS row-count mismatch: expected={expected}, actual={counts}")
        connection.commit()

    return {
        "database_executed": True,
        "dataset_version_id": str(dataset_version_id),
        "network_version_id": str(network_version_id),
        "context_run_id": str(context_run_id),
        "loaded_rows": counts,
    }
