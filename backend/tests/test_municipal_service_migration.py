from pathlib import Path

SQL = Path("infra/migrations/015_municipal_service.sql").read_text(encoding="utf-8")


def test_municipal_service_schema_contains_required_product_entities() -> None:
    for table in (
        "organizations",
        "organization_memberships",
        "workspaces",
        "findings",
        "investigations",
        "review_requests",
        "decision_records",
        "assignments",
        "notifications",
        "activity_events",
        "field_observations",
        "saved_views",
        "analysis_definitions",
        "scenario_comparisons",
        "evidence_centers",
        "report_records",
        "attachment_objects",
        "backup_runs",
        "service_releases",
        "job_cancellation_requests",
        "service_worker_heartbeats",
    ):
        assert f"CREATE TABLE {table}" in SQL


def test_tenant_and_human_decision_guards_are_database_enforced() -> None:
    assert SQL.count("organization_id uuid NOT NULL") >= 30
    assert (
        "optimizer_generated boolean NOT NULL DEFAULT false CHECK (NOT optimizer_generated)" in SQL
    )
    assert "source text NOT NULL DEFAULT 'human_entry' CHECK (source = 'human_entry')" in SQL
    assert "CREATE TRIGGER audit_log_immutable" in SQL
    assert "export_scope <> 'public' OR data_classification = 'public'" in SQL
    assert SQL.count("FOREIGN KEY (organization_id,") >= 30


def test_dataset_upload_cannot_silently_promote() -> None:
    for status in (
        "registered",
        "validating",
        "validated",
        "accepted",
        "ingesting",
        "analysis_ready",
        "promoted",
    ):
        assert f"'{status}'" in SQL
    assert "dataset_versions_service_promotion_gate" in SQL
    assert "validate, accept and promote are explicit lifecycle actions" in SQL


def test_activity_audit_and_public_internal_exports_are_separate() -> None:
    assert "CREATE TABLE activity_events" in SQL
    assert "CREATE TRIGGER audit_log_immutable" in SQL
    assert "CREATE TABLE report_exports" in SQL
    assert "CREATE TABLE evidence_exports" not in SQL


def test_offline_field_and_attachment_records_have_composite_tenant_guards() -> None:
    for constraint in (
        "field_offline_packages_organization_city_fk",
        "field_offline_packages_organization_state_fk",
        "field_offline_packages_organization_scenario_fk",
        "field_sync_operations_organization_package_fk",
        "field_sync_operations_organization_scenario_fk",
        "field_sync_conflicts_organization_operation_fk",
    ):
        assert constraint in SQL
    assert "attachment_objects" in SQL
    assert "FOREIGN KEY (organization_id, city_id)" in SQL


def test_service_search_includes_real_spatial_identifiers() -> None:
    for entity_type in ("'facility'", "'building'", "'mesh'"):
        assert entity_type in SQL
    assert "object.gml_id" in SQL
    assert "demographic.mesh_code" in SQL
    assert "facility.facility_key" in SQL
