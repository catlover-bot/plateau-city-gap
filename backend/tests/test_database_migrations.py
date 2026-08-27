from pathlib import Path

from backend.citygap_platform.database.migrations import checksum, migration_files


def test_migrations_have_an_immutable_order_and_sha256_checksums() -> None:
    files = migration_files("infra/migrations")
    assert [path.name for path in files] == sorted(path.name for path in files)
    assert [path.name[:3] for path in files] == [f"{number:03d}" for number in range(1, 14)]
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
