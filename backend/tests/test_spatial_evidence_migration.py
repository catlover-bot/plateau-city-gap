from pathlib import Path

MIGRATION = Path("infra/migrations/027_spatial_evidence_urban_section.sql")


def test_spatial_evidence_migration_has_tenant_composite_foreign_keys() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "spatial_evidence_packs",
        "spatial_pack_objects",
        "spatial_pack_artifacts",
        "urban_transects",
        "urban_section_samples",
        "urban_section_objects",
        "investigation_spatial_states",
    ):
        assert f"CREATE TABLE {table}" in sql
    assert sql.count("FOREIGN KEY (organization_id") >= 17
    assert "'spatial_evidence_pack'" in sql
    assert "estimated_population" not in sql
