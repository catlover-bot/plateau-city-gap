import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "analysis/outputs/real"


def _load(name: str) -> dict:
    return json.loads((REAL / name).read_text(encoding="utf-8"))


def test_maizuru_and_fujisawa_use_the_same_plateau_native_stage_contracts() -> None:
    expected = {
        "maizuru": {"city_id": "26202", "features": 97_140, "buildings": 44_640,
                    "roads": 15_684, "strict_residential": 29_674, "crs": "EPSG:6674"},
        "fujisawa": {"city_id": "14205", "features": 399_271, "buildings": 169_856,
                     "roads": 53_658, "strict_residential": 107_573, "crs": "EPSG:6677"},
    }
    for city, facts in expected.items():
        inventory = _load(f"{city}_plateau_inventory.json")
        demographics = _load(f"{city}_building_demographics_summary.json")
        network = _load(f"{city}_road_network_summary.json")
        terrain = _load(f"{city}_terrain_network_summary.json")
        context = _load(f"{city}_plateau_context_summary.json")
        config = yaml.safe_load((ROOT / f"analysis/config/{city}.yaml").read_text(encoding="utf-8"))

        assert inventory["dataset"]["city_id"] == facts["city_id"]
        assert inventory["totals"]["feature_count"] == facts["features"]
        assert inventory["themes"]["bldg"]["feature_count"] == facts["buildings"]
        assert inventory["themes"]["tran"]["feature_count"] == facts["roads"]
        assert demographics["counts"]["strict_residential_buildings_citywide"] == facts["strict_residential"]
        assert network["graph"]["nodes"] == facts["roads"]
        assert network["graph"]["pedestrian_network"] is False
        assert terrain["graph_version"] == network["graph"]["graph_version"]
        assert context["dataset"]["archive_sha256"] == inventory["archive"]["sha256"]
        assert context["dataset"]["analysis_crs"] == config["analysis_crs"] == facts["crs"]
        assert context["targets"]["strict_residential_buildings"] > 0


def test_platform_core_has_no_maizuru_conditional_branch() -> None:
    conditional = re.compile(r"\b(?:if|elif|match|case)\b[^\n]*(?:maizuru|26202)", re.IGNORECASE)
    roots = (ROOT / "analysis/src", ROOT / "backend/citygap_platform")
    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            match = conditional.search(path.read_text(encoding="utf-8"))
            if match:
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
    assert offenders == []


def test_capability_matrix_never_substitutes_unavailable_fujisawa_features() -> None:
    registry = _load("platform_registry.json")
    capabilities = {
        (item["city_code"], item["capability"]): item["status"]
        for item in registry["capabilities"]
    }
    for capability in ("building_detail", "road_network", "terrain", "land_use", "urban_planning", "hazard"):
        assert capabilities[("14205", capability)] in {"available", "partial"}
    assert capabilities[("14205", "scenario")] == "unavailable"
    assert capabilities[("14205", "gtfs")] == "unavailable"
