"""Benchmark real API contracts against an explicitly synthetic municipal-scale fixture."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import time
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.api.repository import PostGISRepository
from backend.citygap_platform.api.tile_cache import VersionedTileCache

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"
SYNTHETIC_CITY = "benchmark-100k"
DATASET_ID = "90000000-0000-0000-0000-000000000001"
INGESTION_ID = "90000000-0000-0000-0000-000000000002"
NETWORK_ID = "90000000-0000-0000-0000-000000000003"


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _measure(operation: Callable[[], None], *, samples: int = 30) -> dict[str, float | int]:
    for _ in range(3):
        operation()
    durations = []
    for _ in range(samples):
        started = time.perf_counter()
        operation()
        durations.append((time.perf_counter() - started) * 1000)
    return {
        "samples": samples,
        "p50_ms": round(_percentile(durations, 0.50), 3),
        "p95_ms": round(_percentile(durations, 0.95), 3),
        "maximum_ms": round(max(durations), 3),
    }


def _seed(database_url: str, building_count: int, edge_count: int) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """INSERT INTO city_dataset_versions (
                   id, city_id, city_name, dataset_year, dataset_name,
                   product_specification_version, archive_file_name, archive_sha256,
                   archive_size_bytes, is_current
               ) VALUES (%s, %s, 'SYNTHETIC SCALE FIXTURE', 2025, 'synthetic benchmark',
                         'synthetic', 'synthetic-not-real.zip', repeat('9', 64), 1, true)""",
            (DATASET_ID, SYNTHETIC_CITY),
        )
        connection.execute(
            """INSERT INTO ingestion_runs (
                   id, dataset_version_id, parser_version, status, completed_at,
                   processed_members, processed_features, processed_geometry_parts
               ) VALUES (%s, %s, 'synthetic-benchmark-1', 'completed', now(),
                         1, %s, 0)""",
            (INGESTION_ID, DATASET_ID, building_count),
        )
        connection.execute(
            """INSERT INTO plateau_city_objects (
                   dataset_version_id, ingestion_run_id, gml_id, theme, feature_type,
                   lods, source_crs, source_member, source_member_crc32, attributes,
                   geometry_envelope, representative_point
               )
               SELECT %s, %s, 'synthetic-building-' || value, 'bldg', 'Building',
                      ARRAY[1], ARRAY['EPSG:4326'], 'synthetic-fixture.gml', '00000000',
                      jsonb_build_object('synthetic', true),
                      ST_Expand(ST_SetSRID(ST_MakePoint(
                          139.0 + (value %% 400) * 0.0001,
                          35.0 + floor(value / 400.0) * 0.0001
                      ), 4326), 0.00001),
                      ST_SetSRID(ST_MakePoint(
                          139.0 + (value %% 400) * 0.0001,
                          35.0 + floor(value / 400.0) * 0.0001
                      ), 4326)
               FROM generate_series(1, %s) AS value""",
            (DATASET_ID, INGESTION_ID, building_count),
        )
        connection.execute(
            """INSERT INTO plateau_buildings (city_object_id, usage_code, measured_height_m)
               SELECT id, '401', 8.0 FROM plateau_city_objects
               WHERE dataset_version_id = %s""",
            (DATASET_ID,),
        )
        connection.execute(
            """INSERT INTO building_demographics (
                   dataset_version_id, building_gml_id, mesh_code,
                   estimated_population, estimated_elderly_population,
                   allocation_method, allocation_weight_source, allocation_weight,
                   allocation_fraction, population_resolution, source_population_year
               )
               SELECT %s, 'synthetic-building-' || value, 'synthetic-' || (value %% 1000),
                      2.0, 0.5, 'synthetic_scale_only', 'synthetic', 1.0, 1.0,
                      'building_estimate', 2020
               FROM generate_series(1, %s) AS value""",
            (DATASET_ID, building_count),
        )
        connection.execute(
            """INSERT INTO road_network_versions (
                   id, dataset_version_id, graph_version, graph_method, network_type,
                   official_generator_executed, pedestrian_network, route_semantics,
                   analysis_crs, topology_tolerance_m, config_hash, node_count, edge_count,
                   component_count, generated_at, software_commit, metadata
               ) VALUES (%s, %s, 'synthetic-100k', 'synthetic scale fixture',
                         'surface_adjacency', false, false, 'not a real route', 'EPSG:6674',
                         0, repeat('8', 64), %s, %s, 1, now(), 'synthetic',
                         '{"synthetic":true}')""",
            (NETWORK_ID, DATASET_ID, edge_count + 1, edge_count),
        )
        connection.execute(
            """INSERT INTO road_network_nodes (
                   network_version_id, node_id, component_id, pedestrian_permission, geom
               )
               SELECT %s, 'synthetic-node-' || value, 'component-1', 'unknown',
                      ST_SetSRID(ST_MakePoint(value * 10.0, 0), 6674)
               FROM generate_series(0, %s) AS value""",
            (NETWORK_ID, edge_count),
        )
        connection.execute(
            """INSERT INTO road_network_edges (
                   network_version_id, edge_id, source_node_id, target_node_id,
                   length_m, topology_relation, pedestrian_permission, geom
               )
               SELECT %s, 'synthetic-edge-' || value,
                      'synthetic-node-' || (value - 1), 'synthetic-node-' || value,
                      10.0, 'synthetic', 'unknown',
                      ST_SetSRID(ST_MakeLine(
                          ST_MakePoint((value - 1) * 10.0, 0),
                          ST_MakePoint(value * 10.0, 0)
                      ), 6674)
               FROM generate_series(1, %s) AS value""",
            (NETWORK_ID, edge_count),
        )
        connection.execute(
            """INSERT INTO building_network_accessibility (
                   dataset_version_id, network_version_id, building_gml_id,
                   destination_class, destination_name, snapped_node_id,
                   building_to_surface_distance_m, building_to_node_connector_m,
                   network_distance_m, terrain_route_status, terrain_route_coverage,
                   route_semantics, algorithm, calculated_at, provenance
               ) VALUES (%s, %s, 'synthetic-building-1', 'transport', 'synthetic stop',
                         'synthetic-node-1', 1, 2, 100, 'unavailable', 0,
                         'not a real route', 'synthetic', now(), '{"synthetic":true}')""",
            (DATASET_ID, NETWORK_ID),
        )
        connection.commit()


def _cleanup(database_url: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        connection.execute(
            "DELETE FROM building_network_accessibility WHERE dataset_version_id = %s",
            (DATASET_ID,),
        )
        connection.execute("DELETE FROM road_network_versions WHERE id = %s", (NETWORK_ID,))
        connection.execute(
            "DELETE FROM plateau_city_objects WHERE dataset_version_id = %s", (DATASET_ID,)
        )
        connection.execute("DELETE FROM ingestion_runs WHERE id = %s", (INGESTION_ID,))
        connection.execute("DELETE FROM city_dataset_versions WHERE id = %s", (DATASET_ID,))
        connection.commit()


def _real_pipeline_measurements() -> dict[str, object]:
    result: dict[str, object] = {}
    for city in ("maizuru", "fujisawa"):
        city_result: dict[str, object] = {}
        for kind, name in (
            ("building_detail", f"{city}_building_demographics_summary.json"),
            ("road_network", f"{city}_road_network_summary.json"),
            ("terrain", f"{city}_terrain_network_summary.json"),
            ("spatial_context", f"{city}_plateau_context_summary.json"),
        ):
            path = REAL / name
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                city_result[kind] = payload.get("performance") or {
                    "runtime_seconds": payload.get("runtime_seconds")
                }
        result[city] = city_result
    return result


def benchmark(database_url: str, building_count: int, edge_count: int) -> dict[str, object]:
    _seed(database_url, building_count, edge_count)
    try:
        repository = PostGISRepository(database_url)
        app = create_app(repository)
        client = TestClient(app)

        def request(path: str, **kwargs) -> None:
            response = client.get(path, **kwargs)
            if response.status_code != 200:
                raise RuntimeError(f"benchmark request failed: {path} -> {response.status_code}")

        scenario_rows = client.get("/cities/26202/scenarios").json()["scenarios"]
        scenario_ids = [str(row["scenario_id"]) for row in scenario_rows[:3]]
        tile_path = f"/cities/{SYNTHETIC_CITY}/tiles/buildings/0/0/0.mvt"
        tile_params = {"dataset_version_id": DATASET_ID}
        results = {
            "cities": _measure(lambda: request("/cities")),
            "bbox_buildings": _measure(
                lambda: request(
                    f"/cities/{SYNTHETIC_CITY}/buildings",
                    params={"bbox": "139.0,35.0,139.01,35.01", "limit": 1000},
                )
            ),
            "mesh_detail": _measure(
                lambda: request(f"/cities/{SYNTHETIC_CITY}/meshes/synthetic-1/detail")
            ),
            "scenario_detail": _measure(
                lambda: request(f"/cities/26202/scenarios/{scenario_ids[0]}")
            ),
            "scenario_comparison": _measure(
                lambda: request(
                    "/cities/26202/scenario-comparison",
                    params={"scenario_ids": ",".join(scenario_ids)},
                )
            ),
            "route_detail": _measure(
                lambda: request(
                    f"/cities/{SYNTHETIC_CITY}/buildings/synthetic-building-1/network-accessibility"
                )
            ),
            "tile_cached": _measure(lambda: request(tile_path, params=tile_params)),
        }

        def uncached_tile() -> None:
            app.state.tile_cache = VersionedTileCache(1)
            request(tile_path, params=tile_params)

        results["tile_uncached"] = _measure(uncached_tile, samples=10)
        return {
            "schema_version": 1,
            "classification": {
                "api_database": "SYNTHETIC_SCALE",
                "real_pipeline": "REAL_MUNICIPAL_DATA",
                "production_sla_claimed": False,
            },
            "synthetic_scale": {
                "buildings": building_count,
                "road_edges": edge_count,
                "api_p50_p95": results,
            },
            "real_pipeline": _real_pipeline_measurements(),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "ci": os.getenv("CI") == "true",
            },
        }
    finally:
        _cleanup(database_url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("CITYGAP_DATABASE_URL"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--buildings", type=int, default=100_000)
    parser.add_argument("--road-edges", type=int, default=100_000)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or CITYGAP_DATABASE_URL is required")
    report = benchmark(args.database_url, args.buildings, args.road_edges)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["synthetic_scale"], ensure_ascii=False))


if __name__ == "__main__":
    main()
