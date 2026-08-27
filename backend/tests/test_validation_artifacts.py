from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from backend.citygap_platform.domain.validation import EVIDENCE_DIMENSIONS

ROOT = Path(__file__).resolve().parents[2]


def test_validation_evidence_package_is_complete_hashed_and_non_aggregated() -> None:
    package_dir = ROOT / "analysis/outputs/real/validation/evidence_package"
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    package = json.loads((package_dir / "validation_evidence.json").read_text(encoding="utf-8"))
    assert package["ground_truth_claimed"] is False
    assert package["confidence_percentage_used"] is False
    assert len(package["claims"]) == 9
    for claim in package["claims"]:
        assert set(claim["evidence_strength"]) == set(EVIDENCE_DIMENSIONS)
        assert set(claim["evidence_strength"].values()) <= {"YES", "NO", "NOT_AVAILABLE"}
    for artifact in manifest["artifacts"]:
        path = package_dir / artifact["file"]
        assert path.stat().st_size == artifact["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    with (package_dir / "validation_evidence.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        assert sum(row["record_type"] == "claim" for row in rows) == 9
        assert {row["record_type"] for row in rows} >= {
            "claim", "network_metric", "coverage", "provenance",
            "disagreement", "assumption_sensitivity",
        }


def test_reproducibility_bundle_has_pinned_sources_commands_and_expected_hashes() -> None:
    manifest = json.loads(
        (ROOT / "analysis/outputs/real/validation/reproducibility/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["raw_data_included"] is False
    assert set(manifest["expected_city_metric_sha256"]) == {"maizuru", "fujisawa"}
    assert all(len(source["sha256"]) == 64 for source in manifest["source_manifest"])
    assert "citygap validate reproduce" in manifest["commands"]["maizuru"]


def test_validation_cost_reports_both_real_cities_and_synthetic_500k() -> None:
    artifact = json.loads(
        (ROOT / "analysis/outputs/benchmarks/validation_cost.json").read_text(encoding="utf-8")
    )
    assert set(artifact["real_city_components"]) == {"maizuru", "fujisawa"}
    scale = artifact["synthetic_500k"]
    assert scale["records"] == 500_000
    assert scale["processed_count"] == 500_000
    assert scale["generated_from_synthetic_data"] is True
    assert scale["real_city_result"] is False
    assert scale["combined_confidence_score_created"] is False


def test_real_network_cross_validation_keeps_samples_metrics_and_disagreements() -> None:
    artifact = json.loads(
        (ROOT / "analysis/outputs/real/validation/network_cross_validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["official_plateau_network"]["status"] == "NOT_AVAILABLE"
    assert artifact["official_plateau_network"]["comparison_performed"] is False
    assert artifact["reference_warning"].lower().count("ground truth") == 1
    for city in artifact["cities"]:
        assert city["sample_rule"]["selected_routes"] >= 100
        assert len(city["sample_rule"]["stratum_counts"]) == 9
        assert city["reference_network"]["license"].endswith("(ODbL)")
        assert city["reference_network"]["replacement_for_production_network"] is False
        assert city["metrics"]["connectivity_disagreement_count"] > 0
        assert city["major_disagreements"]
    routes = json.loads(
        (ROOT / "frontend/public/data/validation/network_disagreement_routes.geojson").read_text(
            encoding="utf-8"
        )
    )
    route_models = {feature["properties"]["route_model"] for feature in routes["features"]}
    assert route_models == {"primary_model", "reference_model"}


def test_real_sensitivity_and_temporal_outputs_preserve_claim_boundaries() -> None:
    sensitivity = json.loads(
        (ROOT / "analysis/outputs/real/validation/sensitivity_validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert sensitivity["confidence_percentage_used"] is False
    for city in sensitivity["cities"].values():
        hazards: dict[str, set[str]] = {}
        for row in city["hazard_assumption_matrix"]:
            hazards.setdefault(row["hazard_type"], set()).add(row["assumption"])
            assert row["probability_claimed"] is False
        assert all(len(assumptions) == 5 for assumptions in hazards.values())
        assert len(city["criticality_sensitivity"]["models"]) == 5
        assert city["future_population_sensitivity"]["best_projection_selected"] is False

    temporal = json.loads(
        (ROOT / "analysis/outputs/real/validation/kunitachi_real_temporal_validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert temporal["city"]["product_city"] is False
    assert set(temporal["themes"]) == {"bldg", "tran", "luse", "urf"}
    assert temporal["incremental_vs_full_overall"]["all_theme_count_and_hash_agreement"] is True
    for theme in temporal["themes"].values():
        assert theme["incremental_vs_full"]["count_agreement"] is True
        assert theme["incremental_vs_full"]["hash_agreement"] is True
