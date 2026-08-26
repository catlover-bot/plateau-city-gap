from pathlib import Path


def test_spatial_context_migration_models_all_targets_and_review_semantics() -> None:
    sql = Path("infra/migrations/004_spatial_context.sql").read_text(encoding="utf-8")
    for required in (
        "CREATE TABLE spatial_context_runs",
        "CREATE TABLE building_spatial_context",
        "CREATE TABLE mesh_spatial_context",
        "CREATE TABLE scenario_candidate_spatial_context",
        "CREATE TABLE road_hazard_context",
        "CREATE VIEW spatial_context_provenance",
        "class_codelist",
        "rank_codelist",
        "source_archive_sha256",
        "additional_confirmation_required",
        "siting_feasibility = 'not_determined'",
        "Never derive this from WaterBody geometry Z",
        "USING gist",
    ):
        assert required in sql


def test_hazard_context_does_not_encode_automatic_rejection() -> None:
    sql = Path("infra/migrations/004_spatial_context.sql").read_text(encoding="utf-8")
    assert "siting_impossible" not in sql
    assert "siting_feasibility text NOT NULL DEFAULT 'not_determined'" in sql
