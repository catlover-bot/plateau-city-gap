from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPEN_DATA = ROOT / "analysis/outputs/real/open_data"
SOURCE_REPORT = OPEN_DATA / "mhlw_health_source_report.json"
CANONICAL = OPEN_DATA / "mhlw_health_canonical.jsonl"
IDENTITY = OPEN_DATA / "mhlw_medical_identity_comparison.json"
SUMMARY = OPEN_DATA / "mhlw_health_summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records() -> list[dict]:
    return [json.loads(line) for line in CANONICAL.read_text(encoding="utf-8").splitlines()]


def test_real_mhlw_sources_are_current_versioned_and_schema_checked() -> None:
    report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    medical = report["resources"]["medical"]
    care = report["resources"]["care"]
    resources = medical + care

    assert report["providers"]["medical"] == {
        "provider": "厚生労働省 医療情報ネット",
        "manifest_url": (
            "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/"
            "newpage_43373.html"
        ),
        "reference_date": "2026-06-01",
        "license_id": "pdl-1.0",
        "resource_count": 8,
    }
    assert report["providers"]["care"] == {
        "provider": "厚生労働省 介護サービス情報公表システム",
        "manifest_url": "https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html",
        "reference_date": "2026-06-30",
        "output_date": "2026-07-09",
        "license_id": "cc-by-4.0",
        "resource_count": 35,
    }
    assert len(resources) == 43
    assert len({item["raw_sha256"] for item in resources}) == 43
    assert all(len(item["raw_sha256"]) == 64 for item in resources)
    assert all(item["resource_url"].startswith("https://www.mhlw.go.jp/") for item in resources)
    assert all(item["source_url"] == item["resource_url"] for item in resources)
    assert all(item["retrieved_at"] == report["observed_at"] for item in resources)
    assert all(item["content_length"] == item["raw_size_bytes"] for item in resources)
    assert all(item["update_frequency"] == "not_declared" for item in resources)
    assert all(item["source_metadata"]["resource_scope"] == "national" for item in resources)
    assert all(item["schema_audit"]["status"] == "passed" for item in resources)
    assert all(item["analysis_readiness"] == "requires_review" for item in resources)
    assert all(
        count == 0
        for city in report["rejected_rows"].values()
        for family in city.values()
        for count in family.values()
    )
    assert report["promotion_status"] == "requires_review"
    assert "not establish current acceptance" in report["claim_boundary"]


def test_real_mhlw_canonical_rows_preserve_claim_privacy_and_lineage_boundaries() -> None:
    records = _records()
    assert len(records) == 7923
    assert len({item["canonical_id"] for item in records}) == len(records)
    assert Counter(item["city_code"] for item in records) == {"14205": 7182, "26202": 741}
    assert {item["reference_date"] for item in records} == {"2026-06-01", "2026-06-30"}
    assert all(len(item["source"]["raw_sha256"]) == 64 for item in records)
    assert all(item["source"]["reference_date"] == item["reference_date"] for item in records)

    blocked_keys = {
        "電話番号",
        "FAX番号",
        "URL",
        "備考",
        "利用可能曜日特記事項",
        "法人番号",
        "法人の名称",
        "案内用ホームページアドレス",
        "薬局のホームページアドレス",
    }
    assert all(not (set(item["attributes"]) & blocked_keys) for item in records)
    for item in records:
        attributes = item["attributes"]
        for field in (
            "current_acceptance",
            "current_availability",
            "appointment_availability",
            "emergency_acceptance",
            "real_time_occupancy",
            "current_capacity",
            "user_eligibility",
        ):
            if field in attributes:
                assert attributes[field] == "unknown"

    facilities = [item for item in records if item["record_type"] == "facility"]
    assert len(facilities) == 1650
    assert all(
        len([link for link in item["spatial_links"] if link["link_type"] == "plateau_building"])
        == 1
        for item in facilities
    )
    building_candidates = [
        link
        for item in facilities
        for link in item["spatial_links"]
        if link["link_type"] == "plateau_building" and link["target_id"] is not None
    ]
    assert len(building_candidates) == 1582
    assert {link["match_method"] for link in building_candidates} == {"ambiguous"}

    medical_facilities = [
        item
        for item in facilities
        if item["attributes"]["entity_kind"] == "medical_facility"
    ]
    pharmacies = [
        item for item in medical_facilities if item["attributes"]["medical_category"] == "pharmacy"
    ]
    maternity_homes = [
        item
        for item in medical_facilities
        if item["attributes"]["medical_category"] == "maternity_home"
    ]
    assert len(pharmacies) == 274
    assert len(maternity_homes) == 4
    assert sum(bool(item["attributes"].get("published_schedule")) for item in pharmacies) == 273
    assert all(item["attributes"].get("published_schedule") for item in maternity_homes)
    assert all(item["attributes"]["current_acceptance"] == "unknown" for item in pharmacies)


def test_real_mhlw_identity_comparison_never_promotes_a_candidate_without_official_id() -> None:
    report = json.loads(IDENTITY.read_text(encoding="utf-8"))
    comparisons = [item for city in report["cities"].values() for item in city]
    assert len(comparisons) == 918
    assert Counter(item["status"] for item in comparisons) == {
        "ambiguous": 18,
        "probable": 481,
        "unmatched": 419,
    }
    assert report["automatic_merge"] is False
    for comparison in comparisons:
        if comparison["status"] == "matched":
            assert len(comparison["candidates"]) == 1
            assert comparison["candidates"][0]["evidence"] == "official_id"
        else:
            assert not (
                len(comparison["candidates"]) == 1
                and comparison["candidates"][0]["evidence"] == "official_id"
            )


def test_real_mhlw_summary_hashes_counts_and_mixed_time_are_exact() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["source_report_sha256"] == _sha256(SOURCE_REPORT)
    assert summary["canonical_artifact_sha256"] == _sha256(CANONICAL)
    assert summary["identity_report_sha256"] == _sha256(IDENTITY)
    assert summary["raw_resource_count"] == 43
    assert summary["raw_unique_sha256_count"] == 43
    assert summary["canonical_record_count"] == 7923
    assert summary["analysis_readiness"] == "requires_review"
    assert summary["unavailable_reason"] == "not_verified"
    assert summary["cities"]["maizuru"]["plateau"] == {
        "archive_sha256": "13f4020ade066dc7139b7653c47a55a09af0093dee743f6b9cca5d3177a71cff",
        "building_count": 44640,
        "product_specification_version": "5.0",
    }
    assert summary["cities"]["fujisawa"]["plateau"] == {
        "archive_sha256": "7e85ff8e1642b9c2cc627f356acedbe792e95fac25febe2ee70c9312d6c415ea",
        "building_count": 169856,
        "product_specification_version": "5.0",
    }
    for city in summary["cities"].values():
        assert city["temporal_alignment"] == {
            "status": "mixed",
            "plateau_reference_year": 2025,
            "medical_reference_date": "2026-06-01",
            "care_reference_date": "2026-06-30",
            "hidden_as_single_year": False,
        }
        spatial = city["spatial_link_counts"]
        assert spatial["city_exact"] == city["canonical_record_count"]
        assert spatial["mesh_linked"] + spatial["mesh_unmatched"] == city[
            "canonical_record_count"
        ]
        assert spatial["plateau_building_candidate"] + spatial[
            "plateau_building_unmatched"
        ] == city["record_type_counts"]["facility"]
