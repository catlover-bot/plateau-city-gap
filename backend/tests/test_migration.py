from pathlib import Path


def test_platform_migration_has_versioning_provenance_and_spatial_indexes() -> None:
    sql = Path("infra/migrations/001_platform_core.sql").read_text(encoding="utf-8")
    for required in (
        "CREATE EXTENSION IF NOT EXISTS postgis",
        "CREATE EXTENSION IF NOT EXISTS pgrouting",
        "CREATE TABLE city_dataset_versions",
        "CREATE TABLE plateau_city_objects",
        "CREATE TABLE plateau_geometry_parts",
        "CREATE TABLE plateau_buildings",
        "CREATE TABLE plateau_roads",
        "CREATE TABLE plateau_terrain",
        "CREATE TABLE plateau_landuse",
        "CREATE TABLE plateau_urban_planning",
        "CREATE TABLE plateau_hazards",
        "CREATE VIEW plateau_feature_provenance",
        "USING gist",
        "archive_sha256",
        "gml_id",
    ):
        assert required in sql
