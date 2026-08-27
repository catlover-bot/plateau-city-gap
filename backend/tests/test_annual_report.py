from __future__ import annotations

from datetime import date

import pytest

from backend.citygap_platform.domain.annual_report import build_annual_report


def test_annual_report_is_structured_deterministic_and_noncausal() -> None:
    report = build_annual_report(
        city_id="26202",
        from_state_id="state-2025",
        to_state_id="state-2026",
        from_effective_date=date(2025, 1, 1),
        to_effective_date=date(2026, 1, 1),
        from_metrics={"reachable_buildings": 100.0},
        to_metrics={"reachable_buildings": 104.0},
        feature_change_counts={"added": 4, "removed": 1},
    )
    assert report["metric_changes"]["reachable_buildings"]["percentage_change"] == 4
    assert report["causal_effect_claimed"] is False
    assert "no generated narrative" in report["generator"]


def test_annual_report_requires_two_comparable_states() -> None:
    with pytest.raises(ValueError, match="chronologically distinct"):
        build_annual_report(
            city_id="26202",
            from_state_id="same",
            to_state_id="same",
            from_effective_date=date(2025, 1, 1),
            to_effective_date=date(2025, 1, 1),
            from_metrics={},
            to_metrics={},
            feature_change_counts={},
        )
