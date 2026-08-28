from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPEN_DATA = ROOT / "analysis/outputs/real/open_data"
SOURCE_REPORT = OPEN_DATA / "maizuru_p0_source_report.json"
CANONICAL = OPEN_DATA / "maizuru_p0_canonical.jsonl"
SUMMARY = OPEN_DATA / "maizuru_p0_canonical_summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records() -> list[dict]:
    return [json.loads(line) for line in CANONICAL.read_text(encoding="utf-8").splitlines()]


def test_real_p0_sources_have_checksums_schema_results_and_no_rejected_rows() -> None:
    report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    assert report["selected_dataset_count"] == 9
    assert report["promotion_status"] == "requires_review"
    assert report["license_attribution"]["license"] == "CC BY 4.0"
    assert sum(item["row_count"] for item in report["datasets"]) == 3546
    assert all(item["schema_audit"]["status"] == "passed" for item in report["datasets"])
    assert all(not item["canonical_quality"]["rejected_rows"] for item in report["datasets"])
    assert all(len(item["raw_sha256"]) == 64 for item in report["datasets"])
    encodings = {item["external_dataset_id"]: item["encoding"] for item in report["datasets"]}
    assert encodings["262021_aed"] == "cp932"
    assert set(encodings.values()) == {"utf-8-sig", "cp932"}


def test_real_canonical_rows_are_complete_private_contact_free_and_lineage_backed() -> None:
    records = _records()
    assert len(records) == 3546
    assert len({item["canonical_id"] for item in records}) == len(records)
    blocked_keys = {"電話番号", "連絡先メールアドレス", "連絡先FormURL", "画像", "備考"}
    assert all(not (set(item["attributes"]) & blocked_keys) for item in records)
    assert all(len(item["source"]["raw_sha256"]) == 64 for item in records)
    facilities = [item for item in records if item["record_type"] == "facility"]
    assert len(facilities) == 1076
    assert all(
        any(link["link_type"] == "plateau_building" for link in item["spatial_links"])
        for item in facilities
    )
    building_links = [
        link
        for item in facilities
        for link in item["spatial_links"]
        if link["link_type"] == "plateau_building" and link["target_id"] is not None
    ]
    assert building_links
    assert {link["match_method"] for link in building_links} == {"ambiguous"}


def test_real_canonical_summary_hashes_counts_and_plateau_version_match_artifacts() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["canonical_artifact_sha256"] == _sha256(CANONICAL)
    assert summary["source_report_sha256"] == _sha256(SOURCE_REPORT)
    assert summary["canonical_record_count"] == 3546
    assert summary["entity_kind_counts"]["administrative_area_population"] == 2120
    assert summary["record_type_counts"] == {
        "activity_observation": 350,
        "facility": 1076,
        "population_observation": 2120,
    }
    assert summary["spatial_link_counts"]["city_exact"] == 3546
    assert (
        summary["spatial_link_counts"]["plateau_building_candidate"]
        + summary["spatial_link_counts"]["plateau_building_unmatched"]
        == 1076
    )
    assert summary["plateau"]["building_count"] == 44640
    assert summary["analysis_readiness"] == "requires_review"
