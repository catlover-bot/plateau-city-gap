"""Regression checks for the evidence-backed final demo assets."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "analysis/outputs/real"
WEB_DATA = ROOT / "frontend/public/data"


def test_plateau_covered_candidates_use_the_required_schema_and_ranking() -> None:
    with (OUTPUTS / "plateau_covered_candidates.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)

    assert reader.fieldnames == [
        "mesh_code",
        "overall_rank",
        "population",
        "elderly_population",
        "elderly_ratio",
        "transport_distance",
        "medical_distance",
        "score_c",
        "plateau_building_count",
    ]
    assert len(rows) == 5
    assert [int(row["overall_rank"]) for row in rows] == [22, 23, 38, 39, 44]
    assert all(int(row["plateau_building_count"]) > 0 for row in rows)


def test_final_demo_separates_rank_one_deep_dive_and_placement_claims() -> None:
    report = json.loads(
        (OUTPUTS / "maizuru_final_demo.json").read_text(encoding="utf-8")
    )
    web = json.loads((WEB_DATA / "final_demo.json").read_text(encoding="utf-8"))
    assert report == web
    assert report["comparison_mesh_count"] == 286
    assert report["rank_one"] == {
        "mesh_code": "533512753",
        "area_label": "二尾バス停周辺",
        "plateau_building_count": 0,
        "road_gml_for_third_mesh": False,
    }
    deep = report["deep_dive"]
    assert deep["mesh_code"] == "533513314"
    assert deep["plateau_building_count"] == 296
    assert deep["plateau_road_surfaces_intersecting_mesh"] == 135
    assert deep["building_score_linkage"] is False

    placement = report["placement_optimization"]
    assert len(placement["candidates"]) == 3
    first = placement["candidates"][0]
    assert first["area_label"] == "常団地前バス停周辺"
    assert first["improved_mesh_count"] == 5
    assert first["affected_elderly_population"] == 241
    assert first["top_improvement"]["after_distance_m"] > 0
    assert report["offline"]["runtime_external_api_required"] is False


def test_deep_dive_road_subset_is_official_and_nonempty() -> None:
    roads = json.loads(
        (WEB_DATA / "plateau_roads.geojson").read_text(encoding="utf-8")
    )
    assert roads["type"] == "FeatureCollection"
    assert len(roads["features"]) == 135
    assert all(
        feature["properties"]["source"]
        == "Project PLATEAU 舞鶴市2025 道路LOD1"
        for feature in roads["features"]
    )
