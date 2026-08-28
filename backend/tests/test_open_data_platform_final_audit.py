import json
from pathlib import Path

from analysis.scripts.audit_open_data_platform import BOUNDARY_GOALS, build_audit

AUDIT_PATH = Path("analysis/outputs/real/open_data/open_data_platform_final_audit.json")


def test_open_data_platform_final_audit_reproduces_all_120_goals() -> None:
    tracked = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    rebuilt = build_audit()
    assert tracked == rebuilt
    assert tracked["passed"] is True
    assert tracked["check_count"] == 42
    assert tracked["goal_count"] == 120
    assert tracked["status_counts"] == {
        "verified": 107,
        "verified_boundary": 13,
        "failed": 0,
    }
    assert [goal["goal"] for goal in tracked["goals"]] == list(range(1, 121))
    assert len({goal["title"] for goal in tracked["goals"]}) == 120
    assert all(tracked["checks"].values())


def test_unavailable_official_capabilities_are_not_reported_as_analysis_ready() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    boundary_ids = {
        goal["goal"] for goal in audit["goals"] if goal["status"] == "verified_boundary"
    }
    assert boundary_ids == BOUNDARY_GOALS
    assert "this is not an analysis-ready claim" in audit["status_semantics"]["verified_boundary"]
    assert audit["real_data_metrics"]["canonical_records"]["total"] == 18_203
    assert len(audit["remaining_external_boundaries"]) == 6
