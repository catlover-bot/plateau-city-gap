from pathlib import Path

from backend.citygap_platform.database.migrations import checksum, migration_files


def test_migrations_have_an_immutable_order_and_sha256_checksums() -> None:
    files = migration_files("infra/migrations")
    assert [path.name for path in files] == sorted(path.name for path in files)
    assert [path.name[:3] for path in files] == [f"{number:03d}" for number in range(1, 21)]
    assert all(len(checksum(path)) == 64 for path in files)
    assert all(path.stat().st_size > 0 for path in files)


def test_migration_runner_is_not_mounted_as_untracked_initdb_magic() -> None:
    source = Path("backend/citygap_platform/database/migrations.py").read_text(encoding="utf-8")
    assert "schema_migrations" in source
    assert "Applied migration checksum changed" in source
    assert "autocommit=True" in source


def test_spatial_delivery_removes_city_specific_network_srid_typmods() -> None:
    sql = Path("infra/migrations/010_spatial_delivery.sql").read_text(encoding="utf-8")
    assert "ALTER COLUMN geom TYPE geometry(Point) USING geom" in sql
    assert "ALTER COLUMN geom TYPE geometry(LineString) USING geom" in sql
    assert "ST_SRID(geom) > 0" in sql


def test_activity_event_extension_preserves_existing_types_and_adds_saved_views() -> None:
    sql = Path("infra/migrations/016_activity_event_extensions.sql").read_text(encoding="utf-8")
    for event_type in (
        "dataset_updated",
        "decision_recorded",
        "analysis_started",
        "saved_view_created",
    ):
        assert f"'{event_type}'" in sql


def test_annual_update_activity_extension_preserves_existing_types() -> None:
    sql = Path("infra/migrations/017_annual_update_activity.sql").read_text(encoding="utf-8")
    for event_type in (
        "dataset_updated",
        "decision_recorded",
        "saved_view_created",
        "annual_update_queued",
    ):
        assert f"'{event_type}'" in sql


def test_open_data_foundation_is_tenant_scoped_and_forward_only() -> None:
    sql = Path("infra/migrations/018_open_data_foundation.sql").read_text(encoding="utf-8")
    for table in (
        "open_data_adapters",
        "open_data_source_catalog",
        "city_open_data_sources",
        "open_data_raw_blobs",
        "open_data_resources",
        "canonical_open_data_records",
        "open_data_spatial_links",
        "city_data_coverage",
        "local_data_overrides",
    ):
        assert f"CREATE TABLE {table}" in sql
    assert "REFERENCES cities(organization_id, id)" in sql
    assert "REFERENCES dataset_versions(organization_id, id)" in sql
    assert "UNIQUE NULLS NOT DISTINCT (sha256, owner_organization_id)" in sql
    assert "redistribution boolean" in sql
    assert "unknown_terms boolean NOT NULL" in sql
    for preserved_capability in (
        "hazard_stress_test",
        "criticality",
        "field_mode",
        "outcome_monitoring",
        "evacuation_reachability",
        "planning_monitoring",
    ):
        assert f"'{preserved_capability}'" in sql


def test_static_catalog_extension_is_forward_only_and_keeps_terms_unverified() -> None:
    sql = Path("infra/migrations/019_official_static_catalog.sql").read_text(encoding="utf-8")
    assert "official-static-catalog@1" in sql
    assert "linked resource licence must be verified independently" in sql
    assert "linked_resource_terms_require_review" in sql
    assert "ARRAY['CSV','GeoJSON','XLSX','ZIP']" in sql


def test_demographic_economic_sources_are_added_by_forward_only_migration() -> None:
    sql = Path("infra/migrations/020_demographic_economic_sources.sql").read_text(
        encoding="utf-8"
    )
    assert "mlit-future-population-250m@2024" in sql
    assert "estat-economic-census-500m@2021" in sql
    assert "government-standard-terms-2.0" in sql
    assert "JGD2011" in sql
