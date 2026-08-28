import json
from pathlib import Path

from backend.citygap_platform.open_data.registry import OFFICIAL_SOURCE_REGISTRY

AUDIT_PATH = Path("analysis/outputs/real/open_data/official_capability_audit.json")


def test_secondary_official_capability_audit_is_truthful_and_registry_backed() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["schema_version"] == "citygap.official-capability-audit@1"
    assert audit["result"] == {
        "status": "passed",
        "registered_source_count": 4,
        "promoted_canonical_source_count": 0,
        "synthetic_record_count": 0,
        "public_raw_resource_count": 0,
        "meaning": (
            "The official capability boundary audit passed. It does not claim that the four "
            "sources are analysis-ready."
        ),
    }
    sources = {item["source_key"]: item for item in audit["sources"]}
    assert set(sources) == {
        "mhlw-kayoi-no-ba",
        "wam-disability-welfare-open-data",
        "mlit-station-passenger-count-s12",
        "mlit-person-trip-study-catalog",
    }
    for source_key, item in sources.items():
        registered = OFFICIAL_SOURCE_REGISTRY.source(source_key)
        assert item["official_page"] == registered.official_url
        assert item["coverage_status"] in {"unavailable", "requires_review"}
        assert item["unavailable_reason"] in {"outside_coverage", "not_verified"}


def test_kayoi_receipt_and_secondary_source_safety_boundaries_are_explicit() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    sources = {item["source_key"]: item for item in audit["sources"]}
    kayoi = sources["mhlw-kayoi-no-ba"]
    assert kayoi["raw_receipt"]["data_row_count"] == 15486
    assert kayoi["raw_receipt"]["sha256"] == (
        "d909b5a013756ed09cb0635e75acf9c65628588f26f2702ab2e6cbea6bcd31f1"
    )
    assert kayoi["pilot_city_match"]["matching_rows"] == 0
    assert kayoi["canonical_snapshot_ingested"] is False
    assert sources["wam-disability-welfare-open-data"]["raw_snapshot_ingested"] is False
    assert sources["mlit-station-passenger-count-s12"]["canonical_snapshot_ingested"] is False
    assert (
        sources["mlit-person-trip-study-catalog"]["pilot_public_spatial_package_verified"] is False
    )
