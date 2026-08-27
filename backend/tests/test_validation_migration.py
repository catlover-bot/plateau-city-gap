from pathlib import Path


def test_validation_is_a_first_class_persisted_domain() -> None:
    sql = Path("infra/migrations/014_validation_evidence.sql").read_text(encoding="utf-8")
    for table in (
        "validation_claims",
        "validation_methods",
        "validation_reference_datasets",
        "validation_runs",
        "validation_samples",
        "validation_results",
        "validation_disagreements",
        "validation_evidence",
        "model_uncertainty",
        "field_validation",
    ):
        assert f"CREATE TABLE {table}" in sql
    for status in (
        "unvalidated",
        "internally_verified",
        "cross_validated",
        "externally_validated",
        "municipally_reviewed",
    ):
        assert status in sql


def test_migration_forbids_ground_truth_and_confidence_theater() -> None:
    sql = Path("infra/migrations/014_validation_evidence.sql").read_text(encoding="utf-8")
    assert "reference_semantics <> 'ground_truth'" in sql
    assert "reference_model <> 'ground_truth'" in sql
    assert "evidence_strength" in sql
    assert "confidence_percentage" not in sql
    assert "magic_score" not in sql
