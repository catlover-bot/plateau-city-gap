from __future__ import annotations

import json
from pathlib import Path

from analysis.scripts.audit_municipal_platform import build_audit


def test_tracked_municipal_platform_audit_matches_live_contracts() -> None:
    tracked = json.loads(
        Path("analysis/outputs/real/municipal_platform_final_audit.json").read_text(
            encoding="utf-8"
        )
    )
    rebuilt = build_audit()
    assert tracked == rebuilt
    assert tracked["passed"] is True
    assert len(tracked["checks"]) == 18
    assert all(tracked["checks"].values())
    assert tracked["claim_boundaries"]["postgis_executed"] is False
    assert tracked["claim_boundaries"]["validated_pedestrian_network"] is False
    assert tracked["final_questions"] == {
        "A_plateau_removal_preserves_detailed_analysis": "NO",
        "B_plateau_is_analysis_foundation_not_only_3d": "YES",
        "C_results_trace_to_sources_and_methods": "YES",
        "D_new_city_requires_core_logic_rewrite": "NO",
        "E_closer_to_municipal_platform_than_hackathon_demo": "YES",
    }
