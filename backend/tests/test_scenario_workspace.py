from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from analysis.scripts.build_scenario_canonical import build
from backend.citygap_platform.domain.scenarios import FieldCheck, ScenarioStatus
from backend.citygap_platform.ingestion.scenarios import canonical_scenario_files


def test_scenario_lifecycle_never_skips_human_review() -> None:
    from backend.citygap_platform.domain.scenarios import validate_status_transition

    assert validate_status_transition("draft", "under_review") == (
        ScenarioStatus.DRAFT,
        ScenarioStatus.UNDER_REVIEW,
    )
    assert validate_status_transition("under_review", "field_check_required") == (
        ScenarioStatus.UNDER_REVIEW,
        ScenarioStatus.FIELD_CHECK_REQUIRED,
    )
    assert validate_status_transition("field_check_required", "reviewed") == (
        ScenarioStatus.FIELD_CHECK_REQUIRED,
        ScenarioStatus.REVIEWED,
    )
    with pytest.raises(ValueError, match="Invalid scenario transition"):
        validate_status_transition("draft", "reviewed")
    with pytest.raises(ValueError, match="Invalid scenario transition"):
        validate_status_transition("archived", "draft")


def test_field_check_defaults_to_unknown_and_validates_values() -> None:
    checklist = FieldCheck.from_mapping({"road_safety": "attention", "notes": "  要確認  "})
    assert checklist.as_dict()["site_access"] == "unknown"
    assert checklist.as_dict()["road_safety"] == "attention"
    assert checklist.notes == "要確認"
    with pytest.raises(ValueError):
        FieldCheck.from_mapping({"site_access": "optimizer_approved"})


def test_scenario_workspace_migration_has_normalized_tables_and_review_guards() -> None:
    sql = Path("infra/migrations/005_scenario_workspace.sql").read_text(encoding="utf-8")
    for required in (
        "CREATE TABLE scenario_runs",
        "CREATE TABLE scenario_sites",
        "CREATE TABLE scenario_objectives",
        "CREATE TABLE scenario_constraints",
        "CREATE TABLE scenario_impacts",
        "CREATE TABLE scenario_context",
        "CREATE TABLE scenario_evidence",
        "CREATE TABLE scenario_field_checks",
        "CREATE TABLE scenario_lifecycle_events",
        "citygap_enforce_scenario_transition",
        "deterministic_greedy_approximation",
        "additional confirmation",
        "siting_feasibility = 'not_determined'",
        "land_ownership_unknown",
        "operator_consultation",
        "USING gist",
        "USING gin",
    ):
        assert required in sql
    assert "NEW.lifecycle_status IN ('under_review', 'archived')" in sql
    assert "NEW.lifecycle_status IN ('reviewed'" not in sql


def test_real_scenarios_normalize_to_versioned_canonical_parquets(tmp_path: Path) -> None:
    manifest = build(tmp_path)
    assert manifest["database_executed"] is False
    assert manifest["lifecycle_initial_status"] == "draft"
    assert manifest["canonical_tables"]["scenario_runs"]["row_count"] == 30
    assert manifest["canonical_tables"]["scenario_sites"]["row_count"] == 90
    assert manifest["canonical_tables"]["scenario_evidence"]["row_count"] == 30

    loaded_manifest, paths = canonical_scenario_files(tmp_path)
    assert loaded_manifest["config_hash"] == manifest["config_hash"]
    runs = pd.read_parquet(paths["scenario_runs"])
    assert runs.scenario_run_id.nunique() == 30
    assert set(runs.lifecycle_status) == {"draft"}
    assert set(runs.algorithm_kind) == {"exact", "deterministic_greedy_approximation"}
    assert runs.dataset_version_key.nunique() == 1
    assert runs.network_version.nunique() == 1
    for table in ("scenario_context", "scenario_evidence", "scenario_runs"):
        frame = pd.read_parquet(paths[table])
        json_columns = [column for column in frame.columns if column.endswith("_json")]
        assert all("NaN" not in str(value) for column in json_columns for value in frame[column])

    constraints = pd.read_parquet(paths["scenario_constraints"])
    attention = constraints.loc[constraints.constraint_name.str.endswith("_attention")]
    assert len(attention) == 90 * 6
    assert attention.satisfied.isna().all()


def test_canonical_loader_rejects_an_artifact_changed_after_manifest(tmp_path: Path) -> None:
    build(tmp_path)
    path = tmp_path / "scenario_impacts.parquet"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="does not match manifest"):
        canonical_scenario_files(tmp_path)
