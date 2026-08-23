"""Cross-city configuration and published Fujisawa output checks."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from analysis.src.city_config import load_city_config

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "analysis/outputs/real"
FUJISAWA_WEB = ROOT / "frontend/public/data/cities/fujisawa"


def test_city_configs_share_the_same_required_contract() -> None:
    maizuru = load_city_config(ROOT / "analysis/config/maizuru.yaml")
    fujisawa = load_city_config(ROOT / "analysis/config/fujisawa.yaml")

    assert maizuru.city_id == "maizuru"
    assert fujisawa.city_id == "fujisawa"
    assert maizuru.analysis_crs == "EPSG:6674"
    assert fujisawa.analysis_crs == "EPSG:6677"
    assert maizuru.population.year == fujisawa.population.year == 2020
    assert maizuru.minimum_population == fujisawa.minimum_population == 20


def test_fujisawa_population_boundary_and_ranking_outputs() -> None:
    metrics = gpd.read_file(OUTPUTS / "fujisawa_city_gap.geojson")
    top10 = pd.read_csv(
        OUTPUTS / "fujisawa_city_gap_top10.csv", dtype={"mesh_code": "string"}
    )

    assert len(metrics) == 327
    assert metrics.geometry.is_valid.all()
    assert metrics["mesh_code"].is_unique
    assert top10["rank"].tolist() == list(range(1, 11))
    assert top10.iloc[0]["mesh_code"] == "533913073"
    assert top10.iloc[0]["elderly_population"] == 921
    assert top10.iloc[0]["centroid_within_city"]


def test_fujisawa_ranking_is_stable_and_city_relative() -> None:
    summary = json.loads(
        (OUTPUTS / "fujisawa_summary.json").read_text(encoding="utf-8")
    )
    stability = summary["threshold_stability"]

    assert summary["record_counts"]["population_unaffected"] == 263
    assert all(item["overlap_with_primary_top10"] == 10 for item in stability.values())
    assert "cannot be compared across cities" in summary["primary_ranking"]["comparison_scope"]
    assert summary["validation_checks"]["top10_centroids_within_city"] is True


def test_fujisawa_web_manifest_has_no_cross_city_score_comparison() -> None:
    manifest = json.loads((FUJISAWA_WEB / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["city"]["id"] == "fujisawa"
    assert manifest["mode"] == "cross_city_validation"
    assert manifest["score_comparison"] == "within_city_only"
    assert {item["file"] for item in manifest["outputs"]} == {
        "mesh_metrics.geojson",
        "top10.json",
        "summary.json",
        "stations.geojson",
        "bus_stops.geojson",
        "medical_facilities.geojson",
        "boundary.geojson",
    }
