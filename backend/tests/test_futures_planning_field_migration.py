from pathlib import Path


def test_futures_planning_portfolio_outcome_and_field_contracts_are_persisted() -> None:
    sql = Path("infra/migrations/013_futures_planning_field.sql").read_text(encoding="utf-8")
    for required in (
        "future_population_states",
        "future_building_allocations",
        "future_accessibility_metrics",
        "planning_context_comparisons",
        "municipal_target_sets",
        "municipal_targets",
        "policy_portfolios",
        "portfolio_interventions",
        "external_cost_inputs",
        "implementation_records",
        "outcome_evaluations",
        "field_offline_packages",
        "field_sync_operations",
        "field_sync_conflicts",
        "temporal_evidence_packages",
        "temporal_evidence_artifacts",
        "municipal_annual_reports",
        "'dataset_diff', 'incremental_recompute', 'future_population'",
        "'stress_test', 'criticality_analysis', 'outcome_evaluation'",
    ):
        assert required in sql


def test_migration_encodes_no_fake_cost_legal_causal_or_silent_conflict_claims() -> None:
    sql = Path("infra/migrations/013_futures_planning_field.sql").read_text(encoding="utf-8")
    assert "legal_compliance_claimed boolean NOT NULL DEFAULT false CHECK" in sql
    assert "causal_effect_claimed boolean NOT NULL DEFAULT false CHECK" in sql
    assert "cost double precision NOT NULL" in sql
    assert "source_dataset_version_id uuid NOT NULL" in sql
    assert "resolution_status text NOT NULL DEFAULT 'unresolved'" in sql
    assert "official population scenario under fixed service assumptions" in sql
