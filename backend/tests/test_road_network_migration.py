from pathlib import Path


def test_road_network_migration_models_versions_terrain_and_provenance() -> None:
    sql = Path("infra/migrations/003_road_network_terrain.sql").read_text(encoding="utf-8")
    for required in (
        "CREATE TABLE road_network_versions",
        "CREATE TABLE road_network_nodes",
        "CREATE TABLE road_network_edges",
        "CREATE TABLE facility_registry",
        "CREATE TABLE building_network_accessibility",
        "CREATE VIEW road_network_provenance",
        "pedestrian_network",
        "official_generator_executed",
        "terrain_node_coverage",
        "elevation_delta_source_to_target_m",
        "route_ascent_m",
        "route_descent_m",
        "USING gist",
    ):
        assert required in sql


def test_network_edges_keep_pgrouting_columns_and_referential_integrity() -> None:
    sql = Path("infra/migrations/003_road_network_terrain.sql").read_text(encoding="utf-8")
    assert "source_node_id text NOT NULL" in sql
    assert "target_node_id text NOT NULL" in sql
    assert "length_m double precision NOT NULL CHECK (length_m > 0)" in sql
    assert "REFERENCES road_network_nodes(network_version_id, node_id)" in sql
