from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from analysis.scripts.export_scenario_evidence import export
from backend.citygap_platform.domain.gtfs import validate_gtfs_adapter
from backend.citygap_platform.domain.jobs import (
    JOB_STAGES,
    JobSnapshot,
    JobState,
    advance_job,
    fail_job,
    start_job,
    succeed_job,
)


class SyntheticGtfsAdapter:
    source_identifier = "synthetic-unit-test-only"

    def __init__(self) -> None:
        self.tables = {
            "stops": pd.DataFrame(
                [
                    {"stop_id": "s1", "stop_name": "A", "stop_lat": 35.4, "stop_lon": 135.3},
                    {"stop_id": "s2", "stop_name": "B", "stop_lat": 35.5, "stop_lon": 135.4},
                ]
            ),
            "routes": pd.DataFrame(
                [
                    {
                        "route_id": "r1",
                        "route_short_name": "R1",
                        "route_long_name": "Test route",
                        "route_type": 3,
                    }
                ]
            ),
            "trips": pd.DataFrame([{"route_id": "r1", "service_id": "weekday", "trip_id": "t1"}]),
            "stop_times": pd.DataFrame(
                [
                    {
                        "trip_id": "t1",
                        "arrival_time": "23:55:00",
                        "departure_time": "23:55:00",
                        "stop_id": "s1",
                        "stop_sequence": 1,
                    },
                    {
                        "trip_id": "t1",
                        "arrival_time": "24:10:00",
                        "departure_time": "24:11:00",
                        "stop_id": "s2",
                        "stop_sequence": 2,
                    },
                ]
            ),
            "calendar": pd.DataFrame(
                [
                    {
                        "service_id": "weekday",
                        "monday": 1,
                        "tuesday": 1,
                        "wednesday": 1,
                        "thursday": 1,
                        "friday": 1,
                        "saturday": 0,
                        "sunday": 0,
                        "start_date": "20260101",
                        "end_date": "20261231",
                    }
                ]
            ),
            "calendar_dates": pd.DataFrame(columns=["service_id", "date", "exception_type"]),
        }

    def table(self, name: str) -> pd.DataFrame:
        return self.tables[name]


def test_gtfs_ready_adapter_validates_all_six_tables_and_times_after_midnight() -> None:
    counts = validate_gtfs_adapter(SyntheticGtfsAdapter())
    assert counts == {
        "stops": 2,
        "routes": 1,
        "trips": 1,
        "stop_times": 2,
        "calendar": 1,
        "calendar_dates": 0,
    }


def test_gtfs_adapter_rejects_unknown_stop_without_fabricating_it() -> None:
    adapter = SyntheticGtfsAdapter()
    adapter.tables["stop_times"].loc[1, "stop_id"] = "missing"
    with pytest.raises(ValueError, match="unknown stop"):
        validate_gtfs_adapter(adapter)


def test_job_state_machine_uses_declared_real_stages_and_no_percentages() -> None:
    snapshot = start_job(JobSnapshot("scenario_optimization"))
    assert snapshot.state is JobState.RUNNING
    assert snapshot.current_stage == "prepare_candidates"
    for stage in JOB_STAGES["scenario_optimization"][1:]:
        snapshot = advance_job(snapshot, stage)
    snapshot = succeed_job(snapshot)
    assert snapshot.state is JobState.SUCCEEDED
    assert snapshot.completed_stages == JOB_STAGES["scenario_optimization"]
    assert not hasattr(snapshot, "progress_percent")

    with pytest.raises(ValueError, match="declared order"):
        advance_job(start_job(JobSnapshot("scenario_optimization")), "persist_artifacts")
    failed = fail_job(start_job(JobSnapshot("context_generation")), "source parse failed")
    assert failed.state is JobState.FAILED
    assert failed.error == "source parse failed"


def test_gtfs_job_and_evidence_migration_has_contracts_without_fake_progress() -> None:
    sql = Path("infra/migrations/007_gtfs_jobs_evidence.sql").read_text(encoding="utf-8")
    for required in (
        "CREATE TABLE gtfs_feeds",
        "CREATE TABLE gtfs_stops",
        "CREATE TABLE gtfs_routes",
        "CREATE TABLE gtfs_trips",
        "CREATE TABLE gtfs_stop_times",
        "CREATE TABLE gtfs_calendar",
        "CREATE TABLE gtfs_calendar_dates",
        "CREATE TABLE job_runs",
        "CREATE TABLE job_dataset_versions",
        "CREATE TABLE job_events",
        "CREATE TABLE evidence_exports",
        "P11 points are not GTFS",
        "Synthetic percentages are prohibited",
    ):
        assert required in sql
    assert "progress_percent" not in sql


def test_real_scenario_exports_complete_json_csv_and_print_html(tmp_path: Path) -> None:
    manifest = export("network-overall-3", tmp_path)
    assert set(manifest["formats"]) == {"json", "csv", "html"}
    assert all(row["size_bytes"] > 0 for row in manifest["formats"].values())

    package = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    assert package["scenario"]["plan_id"] == "network-overall-3"
    assert "mesh_results" not in package["scenario"]
    assert len(package["scenario"]["sites"]) == 3
    assert all(site["road_gml_id"] for site in package["scenario"]["sites"])
    assert {source["year"] for source in package["source_datasets"]} >= {2020, 2022, 2025}
    assert all(check["site_access"] == "unknown" for check in package["field_check_items"])
    assert package["review_boundary"]["recommendation"] is None
    assert package["review_boundary"]["siting_feasibility"] == "not_determined"

    with (tmp_path / "evidence.csv").open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    assert {row["record_type"] for row in records} >= {
        "scenario",
        "metric",
        "site",
        "review_flag",
        "source_dataset",
        "field_check",
    }
    rendered = (tmp_path / "print.html").read_text(encoding="utf-8")
    assert "@media print" in rendered
    assert "自動推奨ではありません" in rendered
    assert "gradient" not in rendered
