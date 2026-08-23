from pathlib import Path

from backend.citygap_platform.ingestion.building_demographics import (
    ACCESSIBILITY_UPSERT,
    CONSERVATIVE_ACCESSIBILITY_COLUMNS,
    DEMOGRAPHIC_UPSERT,
)


def test_priority2_migration_has_privacy_safe_tables_and_indexes() -> None:
    sql = Path("infra/migrations/002_building_demographics.sql").read_text(encoding="utf-8")
    for required in (
        "CREATE TABLE building_demographics",
        "CREATE TABLE building_accessibility",
        "dataset_version_id",
        "building_gml_id",
        "mesh_code",
        "source_population_year",
        "population_resolution = 'building_estimate'",
        "building_demographics_mesh_idx",
        "building_accessibility_gml_idx",
    ):
        assert required in sql


def test_loader_contract_upserts_canonical_values_without_recalculation() -> None:
    assert "ON CONFLICT (dataset_version_id, building_gml_id, mesh_code)" in DEMOGRAPHIC_UPSERT
    assert "estimated_population" in DEMOGRAPHIC_UPSERT
    assert "ON CONFLICT (dataset_version_id, building_gml_id, facility_policy)" in (
        ACCESSIBILITY_UPSERT
    )
    assert "nearest_transport_distance_m" in ACCESSIBILITY_UPSERT
    assert "conservative_facility_policy" in CONSERVATIVE_ACCESSIBILITY_COLUMNS
    assert "nearest_conservative_medical_distance_m" in CONSERVATIVE_ACCESSIBILITY_COLUMNS
