from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPEN_DATA = ROOT / "analysis/outputs/real/open_data"
SOURCE_REPORT = OPEN_DATA / "geospatial_resilience_source_report.json"
CANONICAL = OPEN_DATA / "geospatial_resilience_canonical.jsonl"
SUMMARY = OPEN_DATA / "geospatial_resilience_summary.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records() -> list[dict]:
    with CANONICAL.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def test_real_geospatial_resilience_sources_are_exact_official_snapshots() -> None:
    report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    resources = report["resources"]
    assert {
        (
            item["external_resource_id"],
            item["raw_sha256"],
            item["raw_size_bytes"],
            item["source_row_count"],
            len(item["field_names"]),
            item["license_id"],
        )
        for item in resources
    } == {
        (
            "Z-V4-JAPAN-AMP-VS400_M250-5335.zip",
            "272dce70436267076b7ae7f0d66a43683675c058c5b6943597d1cdfc09da2dd9",
            166684,
            44747,
            6,
            "jshis-terms-2025-03",
        ),
        (
            "Z-V4-JAPAN-AMP-VS400_M250-5339.zip",
            "e5d137f29745065c7e3928210b8b6051058904a09a1ff4a29b10f63129e14717",
            871840,
            93474,
            6,
            "jshis-terms-2025-03",
        ),
        (
            "honhyo_2024.csv",
            "b1d91bb65daaa3554026fcdc6426f7440356018fc0e6e18042c40ff9f54ac2f5",
            62252803,
            290895,
            68,
            "pdl-1.0",
        ),
    }
    assert len(resources) == 3
    assert all(item["resource_url"].startswith("https://") for item in resources)
    assert all(item["retrieved_at"] == report["observed_at"] for item in resources)
    assert all(item["raw_publication"] is False for item in resources)
    assert all(item["raw_object_key"].startswith("sha256/") for item in resources)

    assert {
        (item["kind"], item["raw_sha256"], item["raw_size_bytes"])
        for item in report["supporting_resources"]
    } == {
        (
            "schema_workbook",
            "c78a295d9a7a196ffcd5a6b722ce31d2c9797806c40fbdbf6c62ac299999bad0",
            19928,
        ),
        (
            "codebook_workbook",
            "bf42ee25f8db17533d299464eb268dd6d3246bdcd63dce7f475912714034b837",
            334659,
        ),
    }
    assert all(item["raw_publication"] is False for item in report["supporting_resources"])
    assert report["promotion_status"] == "analysis_ready_for_jshis_and_npa_only"


def test_real_canonical_ground_and_accidents_preserve_claim_boundaries() -> None:
    records = _records()
    assert len(records) == 4105
    assert len({item["canonical_id"] for item in records}) == len(records)
    assert Counter((item["city_code"], item["record_type"]) for item in records) == {
        ("26202", "ground_observation"): 1980,
        ("14205", "ground_observation"): 1084,
        ("26202", "road_observation"): 59,
        ("14205", "road_observation"): 982,
    }

    coastal = []
    occurrence_years: Counter[tuple[str, str]] = Counter()
    mesh_links: Counter[tuple[str, str]] = Counter()
    for item in records:
        assert len(item["provenance"]["raw_sha256"]) == 64
        if item["record_type"] == "ground_observation":
            assert item["geometry"]["type"] == "Polygon"
            assert item["provenance"]["source_crs"].startswith("JGD2000")
            assert item["spatial_links"]["audited_500m_mesh"]["scope"].startswith(
                "published 250m"
            )
            assert "not an in-situ observation" in item["attributes"]["claim_boundary"]
            if item["attributes"]["microtopography_code"] == 0:
                coastal.append(item)
        else:
            assert item["geometry"]["type"] == "Point"
            assert item["attributes"]["annual_file_year"] == 2024
            assert item["provenance"]["occurrence_time_preserved_separately"] is True
            assert "no frequency denominator" in item["attributes"]["claim_boundary"]
            occurrence_years[(item["city_code"], item["reference_date"][:4])] += 1
            mesh_links[
                (
                    item["city_code"],
                    item["spatial_links"]["audited_500m_mesh"]["method"],
                )
            ] += 1

    assert len(coastal) == 16
    assert all(
        item["attributes"]["average_shear_wave_velocity_m_s"] is None
        and item["attributes"]["amplification_ratio"] is None
        and item["attributes"]["source_encoded_values"] == {"ARV": 0.0, "AVS": 0.0}
        and item["attributes"]["value_status"] == "coastal_water_not_ground"
        for item in coastal
    )
    assert occurrence_years == {
        ("26202", "2023"): 9,
        ("26202", "2024"): 50,
        ("14205", "2023"): 8,
        ("14205", "2024"): 974,
    }
    assert mesh_links == {
        ("26202", "point_in_audited_mesh"): 58,
        ("26202", "unmatched"): 1,
        ("14205", "point_in_audited_mesh"): 978,
        ("14205", "unmatched"): 4,
    }


def test_real_coverage_audit_never_fabricates_unavailable_sources() -> None:
    report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    reference = report["reference_coverage"]
    assert reference["gsi_foundation_map"]["status"] == "requires_review"
    assert reference["gsi_foundation_map"]["comparison_with_plateau_performed"] is False
    assert reference["pedestrian_network"]["catalog_dataset_count"] == 31
    assert "not a walking network" in reference["pedestrian_network"]["finding"]
    assert "not a stable snapshot" in reference["xroad_traffic"]["finding"]

    coverage = report["coverage_by_city"]
    for city in coverage.values():
        assert city["gsi_foundation_map"] == {
            "status": "requires_review",
            "unavailable_reason": "requires_credentials",
        }
        assert city["pedestrian_network"] == {
            "status": "unavailable",
            "unavailable_reason": "outside_coverage",
        }
        assert city["gtfs"] == {
            "status": "unavailable",
            "unavailable_reason": "not_published",
        }
        assert city["xroad_traffic"]["stable_snapshot_ingested"] is False
    assert coverage["maizuru"]["xroad_traffic"]["status"] == "partial"
    assert coverage["maizuru"]["xroad_traffic"]["cctv_points_within_context"] == 3
    assert coverage["fujisawa"]["xroad_traffic"]["status"] == "unknown"

    # Only J-SHIS and NPA records are promoted; research-only sources create no rows.
    assert {
        item["provenance"]["provider"] for item in _records()
    } == {"防災科学技術研究所 J-SHIS", "警察庁"}


def test_real_summary_fixes_hashes_counts_and_non_prediction_contract() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["source_report_sha256"] == _sha256(SOURCE_REPORT)
    assert summary["canonical_artifact_sha256"] == _sha256(CANONICAL)
    assert summary["canonical_record_count"] == 4105
    assert summary["raw_primary_resource_count"] == 3
    assert summary["raw_supporting_resource_count"] == 2
    assert summary["raw_unique_sha256_count"] == 5
    assert summary["prediction_generated"] is False
    assert summary["risk_probability_generated"] is False
    assert summary["unavailable_sources_fabricated_as_rows"] is False

    maizuru = summary["cities"]["maizuru"]
    fujisawa = summary["cities"]["fujisawa"]
    assert maizuru["jshis_surface_ground"]["published_250m_cell_count"] == 1980
    assert maizuru["jshis_surface_ground"]["linked_parent_500m_mesh_count"] == 495
    assert fujisawa["jshis_surface_ground"]["published_250m_cell_count"] == 1084
    assert (
        fujisawa["jshis_surface_ground"][
            "audited_parent_meshes_without_published_cell_count"
        ]
        == 56
    )
    assert maizuru["historical_traffic_accidents"]["record_count"] == 59
    assert maizuru["historical_traffic_accidents"]["fatalities_sum"] == 2
    assert maizuru["historical_traffic_accidents"]["injuries_sum"] == 66
    assert fujisawa["historical_traffic_accidents"]["record_count"] == 982
    assert fujisawa["historical_traffic_accidents"]["fatalities_sum"] == 6
    assert fujisawa["historical_traffic_accidents"]["injuries_sum"] == 1127
