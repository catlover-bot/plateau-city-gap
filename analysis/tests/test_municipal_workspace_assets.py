import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "frontend/public/data/network_scenario_map.geojson"
POINTS_PATH = ROOT / "frontend/public/data/network_scenario_building_points.json"
STORY_PATH = ROOT / "frontend/public/data/municipal_workspace_story.json"
COMPETITION_STORY_PATH = ROOT / "frontend/public/data/network_scenario_story.json"
MANIFEST_PATH = ROOT / "analysis/outputs/real/maizuru_municipal_workspace_manifest.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_workspace_map_is_real_two_plan_privacy_safe_subset():
    workspace = _load(MAP_PATH)
    points = _load(POINTS_PATH)
    story = _load(STORY_PATH)
    competition_story = _load(COMPETITION_STORY_PATH)
    features = workspace["features"]

    assert workspace["type"] == "FeatureCollection"
    assert {item["story_id"] for item in competition_story["scenario_story"]} == {
        "scenario_a",
        "scenario_b",
    }
    assert {item["story_id"] for item in story["scenario_story"]} == {
        "scenario_a",
        "scenario_b",
        "scenario_c",
    }
    assert {feature["properties"]["story_id"] for feature in features} == {
        "scenario_a",
        "scenario_b",
        "scenario_c",
    }

    for plan in story["scenario_story"]:
        plan_features = [
            feature
            for feature in features
            if feature["properties"]["story_id"] == plan["story_id"]
        ]
        layer_counts = {}
        for feature in plan_features:
            layer = feature["properties"]["layer_type"]
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
        assert layer_counts["scenario_site"] == 3
        assert len(points["stories"][plan["story_id"]]) == plan["impact"]["improved_building_count"]
        assert layer_counts["representative_route"] == 2
        assert layer_counts["representative_building"] == 1
        assert layer_counts["landuse_context"] >= 1
        assert layer_counts["planning_context"] >= 1
        assert layer_counts["hazard_context"] >= 1

    assert "affected_building" not in workspace["layer_counts"]
    assert set(points["band_codes"].values()) == {"under_250", "250_499", "500_plus"}
    assert all(
        len(point) == 3 and point[2] in {0, 1, 2}
        for story_points in points["stories"].values()
        for point in story_points
    )
    serialized = json.dumps(points, ensure_ascii=False)
    assert "estimated_population" not in serialized
    assert "building_gml_id" not in serialized
    assert "distance_reduction_m" not in serialized


def test_workspace_manifest_matches_public_asset():
    manifest = _load(MANIFEST_PATH)
    workspace = _load(MAP_PATH)
    points = _load(POINTS_PATH)
    digest = hashlib.sha256(MAP_PATH.read_bytes()).hexdigest()

    assert manifest["public_map"]["sha256"] == digest
    assert manifest["public_map"]["feature_count"] == len(workspace["features"])
    assert manifest["public_map"]["layer_counts"] == workspace["layer_counts"]
    assert manifest["public_building_points"]["sha256"] == hashlib.sha256(
        POINTS_PATH.read_bytes()
    ).hexdigest()
    assert manifest["public_building_points"]["point_count"] == sum(
        len(value) for value in points["stories"].values()
    )
    assert manifest["database_loaded"] is False
