from pathlib import Path

from backend.citygap_platform.database.migrations import checksum, migration_files


def test_migrations_have_an_immutable_order_and_sha256_checksums() -> None:
    files = migration_files("infra/migrations")
    assert [path.name for path in files] == sorted(path.name for path in files)
    assert [path.name[:3] for path in files] == [f"{number:03d}" for number in range(1, 24)]
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
    sql = Path("infra/migrations/020_demographic_economic_sources.sql").read_text(encoding="utf-8")
    assert "mlit-future-population-250m@2024" in sql
    assert "estat-economic-census-500m@2021" in sql
    assert "government-standard-terms-2.0" in sql
    assert "JGD2011" in sql


def test_geospatial_resilience_sources_are_added_by_forward_only_migration() -> None:
    sql = Path("infra/migrations/021_geospatial_resilience_sources.sql").read_text(encoding="utf-8")
    for adapter_id in (
        "gsi-foundation-map@5.3",
        "jshis-surface-ground-v4@2020",
        "npa-traffic-accident@2024",
        "mlit-pedestrian-ckan@2024",
        "xroad-traffic-api@2026-01",
    ):
        assert adapter_id in sql
    assert "jshis-terms-2025-03" in sql
    assert "gsi-survey-act-review" in sql
    assert "xroad-api-terms-2025-05" in sql
    assert '"raw_redistribution":false' in sql
    assert '"property_only_excluded":true' in sql
    assert '"pilot_city_network_coverage":false' in sql
    assert '"p11_conversion":false' in sql


def test_municipal_open_data_analyses_are_added_by_forward_only_migration() -> None:
    sql = Path("infra/migrations/022_municipal_open_data_analyses.sql").read_text(encoding="utf-8")
    for analysis_id in (
        "medical-access-v2",
        "care-access",
        "future-population-spatial",
        "daytime-activity-context",
        "earthquake-ground-context",
        "historical-traffic-safety-context",
    ):
        assert analysis_id in sql
    assert "care_access_review_candidate" in sql
    assert "activity_service_gap_candidate" in sql
    assert "analysis_dataset_requirements" in sql
    for level in ("required", "optional", "enhancement"):
        assert f"'{level}'" in sql


def test_city_data_coverage_and_lineage_are_forward_only_and_non_ranking() -> None:
    sql = Path("infra/migrations/023_city_data_coverage_lineage.sql").read_text(encoding="utf-8")
    for table in (
        "city_source_timeline_entries",
        "open_data_dataset_comparisons",
        "open_data_source_conflicts",
        "analysis_source_selection_policies",
        "dataset_family_quality_gate_policies",
    ):
        assert f"CREATE TABLE {table}" in sql
    assert "CREATE VIEW service_search_documents_v2" in sql
    assert "automatic_newer_wins boolean NOT NULL DEFAULT false" in sql
    assert "automatic_truth_selection boolean NOT NULL DEFAULT false" in sql
    assert "automatic_selection boolean NOT NULL DEFAULT false" in sql
    assert "aggregate quality score" in sql
    assert "reference_period text NOT NULL" in sql
    assert "CREATE TRIGGER city_seed_pilot_data_hub" in sql
    assert "never registers a city" in sql
    assert "2025-01-01" not in sql
    assert "2022-01-01" not in sql
    assert "PLATEAU roads are not substituted" in sql
    assert '"p11_conversion":false' in sql
