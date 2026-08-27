from pathlib import Path


def test_resilience_migration_persists_explicit_assumptions_impacts_and_cache_versions() -> None:
    sql = Path("infra/migrations/012_network_resilience.sql").read_text(encoding="utf-8")
    for required in (
        "stress_test_runs",
        "stress_test_assumptions",
        "stress_test_edge_impacts",
        "stress_test_building_impacts",
        "stress_test_facility_impacts",
        "stress_test_metrics",
        "network_criticality_candidates",
        "route_redundancy_results",
        "network_precomputations",
        "stress_test_result_cache",
        "assumption_hash",
        "algorithm_version",
        "prediction_claimed boolean NOT NULL DEFAULT false CHECK (NOT prediction_claimed)",
        "network criticality candidate",
        "citygap_validate_stress_test_completion",
    ):
        assert required in sql


def test_critical_facility_fields_never_infer_missing_capacity() -> None:
    sql = Path("infra/migrations/012_network_resilience.sql").read_text(encoding="utf-8")
    assert "capacity integer CHECK (capacity IS NULL OR capacity >= 0)" in sql
    assert "hazard_applicability text[]" in sql
    assert "source_verified boolean" in sql
