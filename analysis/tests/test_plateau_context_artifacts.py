from __future__ import annotations

import json
from pathlib import Path

OUTPUT = Path("analysis/outputs/real")


def test_real_context_artifact_matches_official_inventory_and_has_no_guessed_labels() -> None:
    report = json.loads(
        (OUTPUT / "maizuru_plateau_context_summary.json").read_text(encoding="utf-8")
    )
    assert report["feature_counts"] == {
        "land_use": 31_067,
        "urban_planning": 394,
        "landslide": 4_643,
        "flood": 666,
        "tsunami": 23,
    }
    assert report["targets"]["scenario_candidates"] == 11_460
    assert all(row["class_label"] for row in report["landuse_classes"])
    assert all(row["rank_label"] for row in report["hazard_rank_counts"])
    assert report["hazard_interpretation"]["overlap_means"] == ("additional_confirmation_required")
    assert report["hazard_interpretation"]["overlap_does_not_mean"] == ("siting_impossible")
    assert report["lineage"]["labels"] == "package-local official GML codelists only"


def test_independent_context_verification_passed_every_check() -> None:
    report = json.loads(
        (OUTPUT / "maizuru_plateau_context_verification.json").read_text(encoding="utf-8")
    )
    assert report["passed"] is True
    assert all(report["checks"].values())
    assert report["evidence"]["road_max_length_residual_m"] == 0
    assert report["evidence"]["deep_mesh_max_area_residual_m2"] == 0
