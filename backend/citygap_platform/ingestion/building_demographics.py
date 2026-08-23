"""Load canonical Priority 2 Parquet records into PostGIS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

DEMOGRAPHIC_COLUMNS = (
    "gml_id",
    "mesh_code",
    "estimated_population",
    "estimated_elderly_population",
    "allocation_method",
    "allocation_weight_source",
    "allocation_weight",
    "allocation_fraction",
    "population_resolution",
    "source_population_year",
)
ACCESSIBILITY_COLUMNS = (
    "gml_id",
    "facility_policy",
    "nearest_public_transport_type",
    "nearest_public_transport_name",
    "nearest_public_transport_distance_m",
    "nearest_medical_name",
    "nearest_medical_distance_m",
    "origin_method",
)
CONSERVATIVE_ACCESSIBILITY_COLUMNS = (
    "gml_id",
    "conservative_facility_policy",
    "nearest_conservative_public_transport_type",
    "nearest_conservative_public_transport_name",
    "nearest_conservative_public_transport_distance_m",
    "nearest_conservative_medical_name",
    "nearest_conservative_medical_distance_m",
    "origin_method",
)

DEMOGRAPHIC_UPSERT = """INSERT INTO building_demographics (
    dataset_version_id, building_gml_id, mesh_code, estimated_population,
    estimated_elderly_population, allocation_method, allocation_weight_source,
    allocation_weight, allocation_fraction, population_resolution, source_population_year
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (dataset_version_id, building_gml_id, mesh_code) DO UPDATE SET
    estimated_population = EXCLUDED.estimated_population,
    estimated_elderly_population = EXCLUDED.estimated_elderly_population,
    allocation_method = EXCLUDED.allocation_method,
    allocation_weight_source = EXCLUDED.allocation_weight_source,
    allocation_weight = EXCLUDED.allocation_weight,
    allocation_fraction = EXCLUDED.allocation_fraction,
    population_resolution = EXCLUDED.population_resolution,
    source_population_year = EXCLUDED.source_population_year,
    created_at = now()"""

ACCESSIBILITY_UPSERT = """INSERT INTO building_accessibility (
    dataset_version_id, building_gml_id, facility_policy, nearest_transport_type,
    nearest_transport_name, nearest_transport_distance_m, nearest_medical_name,
    nearest_medical_distance_m, origin_method
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (dataset_version_id, building_gml_id, facility_policy) DO UPDATE SET
    nearest_transport_type = EXCLUDED.nearest_transport_type,
    nearest_transport_name = EXCLUDED.nearest_transport_name,
    nearest_transport_distance_m = EXCLUDED.nearest_transport_distance_m,
    nearest_medical_name = EXCLUDED.nearest_medical_name,
    nearest_medical_distance_m = EXCLUDED.nearest_medical_distance_m,
    origin_method = EXCLUDED.origin_method,
    calculated_at = now()"""


def _none(value: Any) -> Any:
    return None if pd.isna(value) else value


def load_building_demographics(
    parquet_path: str | Path,
    database_url: str,
    *,
    dataset_version_id: str,
    batch_size: int = 2_000,
) -> dict[str, int]:
    """Load one canonical Parquet with identical values; no recalculation occurs."""

    import psycopg

    frame = pd.read_parquet(parquet_path)
    missing = (
        set(DEMOGRAPHIC_COLUMNS)
        | set(ACCESSIBILITY_COLUMNS)
        | set(CONSERVATIVE_ACCESSIBILITY_COLUMNS)
    ) - set(frame.columns)
    if missing:
        raise ValueError(f"Parquet lacks required columns: {', '.join(sorted(missing))}")
    demographic_rows = [
        (dataset_version_id, *(_none(row[column]) for column in DEMOGRAPHIC_COLUMNS))
        for _, row in frame.iterrows()
    ]
    accessibility = frame.drop_duplicates("gml_id")
    accessibility_rows = [
        (dataset_version_id, *(_none(row[column]) for column in ACCESSIBILITY_COLUMNS))
        for _, row in accessibility.iterrows()
    ]
    accessibility_rows.extend(
        (dataset_version_id, *(_none(row[column]) for column in CONSERVATIVE_ACCESSIBILITY_COLUMNS))
        for _, row in accessibility.iterrows()
    )
    with psycopg.connect(database_url) as connection:
        for start in range(0, len(demographic_rows), batch_size):
            connection.executemany(DEMOGRAPHIC_UPSERT, demographic_rows[start : start + batch_size])
        for start in range(0, len(accessibility_rows), batch_size):
            connection.executemany(
                ACCESSIBILITY_UPSERT, accessibility_rows[start : start + batch_size]
            )
        connection.commit()
    return {
        "demographic_records": len(demographic_rows),
        "accessibility_records": len(accessibility_rows),
    }
