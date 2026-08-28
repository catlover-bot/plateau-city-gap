from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "analysis/outputs/real/open_data/municipal_catalog_inventory.json"


def test_real_municipal_catalog_inventory_is_official_and_truthful() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    assert inventory["schema_version"] == "citygap-municipal-open-data-inventory@1"
    assert inventory["official_sources_only"] is True
    assert inventory["analysis_ready_dataset_count"] == 0
    cities = {item["city_code"]: item for item in inventory["cities"]}
    assert cities["26202"]["dataset_count"] == 30
    assert cities["26202"]["resource_count"] == 31
    assert cities["14205"]["dataset_count"] == 9
    assert cities["14205"]["linked_resource_license_id"] == "unknown"
    assert {item["license_id"] for item in cities["26202"]["datasets"]} == {"cc-by-4.0"}
    assert all(
        item["analysis_readiness"] == "requires_review"
        for city in cities.values()
        for item in city["datasets"]
    )


def test_real_inventory_has_explicit_coverage_reasons_and_no_private_urls() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    assert all(item["unavailable_reason"] for item in inventory["coverage"])
    serialized = INVENTORY.read_text(encoding="utf-8")
    assert "http://" not in serialized
    assert "localhost" not in serialized
    assert "127.0.0.1" not in serialized
