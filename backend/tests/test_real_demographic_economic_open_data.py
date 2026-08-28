from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPEN_DATA = ROOT / "analysis/outputs/real/open_data"
SOURCE_REPORT = OPEN_DATA / "demographic_economic_source_report.json"
CANONICAL = OPEN_DATA / "demographic_economic_canonical.jsonl"
MESH_CONTEXT = OPEN_DATA / "demographic_economic_mesh_context.geojson"
SUMMARY = OPEN_DATA / "demographic_economic_summary.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records() -> list[dict]:
    with CANONICAL.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def test_real_demographic_economic_sources_are_exact_official_snapshots() -> None:
    report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    resources = report["resources"]
    actual = {
        (
            item["city"],
            item["external_dataset_id"],
            item["raw_sha256"],
            item["raw_size_bytes"],
            item["source_row_count"],
            len(item["field_names"]),
            item["license_id"],
        )
        for item in resources
    }
    assert actual == {
        (
            "maizuru",
            "mlit-ksj-future-population-250m-r6",
            "139e6bf5ed47cc2ea5e3d8e85956fce52ffd0e9679b185f3ac801a07821c5117",
            16805431,
            15174,
            343,
            "cc-by-4.0",
        ),
        (
            "fujisawa",
            "mlit-ksj-future-population-250m-r6",
            "f795cbe93f5f25aecc2fccea7be872a2581085bd780c2edb4f045a948b3ebeb7",
            30757702,
            20880,
            343,
            "cc-by-4.0",
        ),
        (
            "maizuru",
            "estat-economic-census-2021-500m-jgd2011",
            "630bbbec80f9f2cafeb02a31727a6185e4617f20526a00d1f0580fefdbf841fc",
            133517,
            4828,
            47,
            "government-standard-terms-2.0",
        ),
        (
            "fujisawa",
            "estat-economic-census-2021-500m-jgd2011",
            "396d86dc90c82f2e9e8cbd7ea5b0a14f907464fe79183778f613f72f48b761ea",
            249155,
            6346,
            47,
            "government-standard-terms-2.0",
        ),
    }
    assert len(resources) == 4
    assert all(item["resource_url"].startswith("https://") for item in resources)
    assert all(item["retrieved_at"] == report["observed_at"] for item in resources)
    assert all(item["raw_publication"] is False for item in resources)
    assert all(item["raw_object_key"].startswith("sha256/") for item in resources)
    for resource in resources:
        gates = {item["gate"]: item for item in resource["quality_results"]}
        if resource["external_dataset_id"].startswith("estat-"):
            assert gates["official_label_row"]["rows"] == 1
            assert resource["encoding"] == "cp932"
        else:
            assert gates["declared_crs"]["crs"] == "EPSG:6668"
            assert resource["encoding"] == "UTF-8"
    assert len(report["economic_metric_dictionary"]) == 46
    assert report["economic_metric_dictionary"][0]["source_field"] == "T001162001"
    assert report["economic_metric_dictionary"][-1]["source_field"] == "T001162046"
    assert report["promotion_status"] == "analysis_ready_with_explicit_claim_boundaries"


def test_real_canonical_population_and_activity_keep_semantic_boundaries() -> None:
    records = _records()
    assert len(records) == 2629
    assert len({item["canonical_id"] for item in records}) == len(records)
    assert Counter((item["city_code"], item["record_type"]) for item in records) == {
        ("26202", "population_observation"): 1053,
        ("26202", "activity_observation"): 287,
        ("14205", "population_observation"): 963,
        ("14205", "activity_observation"): 326,
    }
    assert {item["reference_date"] for item in records} == {"2020-10-01", "2021-06-01"}
    for item in records:
        assert item["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        assert len(item["provenance"]["raw_sha256"]) == 64
        if item["record_type"] == "population_observation":
            attributes = item["attributes"]
            assert attributes["automatic_best_scenario_selected"] is False
            assert attributes["baseline"]["status"].startswith("modeled_baseline")
            assert len(attributes["projections"]) == 10
            assert all(
                projection["status"] == "official_trial_projection_not_observation"
                for projection in attributes["projections"]
            )
            assert (
                item["external_record_id"][:-1]
                == item["spatial_links"]["parent_500m_mesh"]["mesh_code"]
            )
            assert all(
                projection["privacy_aggregation"]["target_scope"]
                in {
                    "not_applicable",
                    "within_exact_city_code_extract",
                    "outside_exact_city_code_extract",
                }
                for projection in attributes["projections"]
            )
        else:
            attributes = item["attributes"]
            assert len(attributes["metrics"]) == 46
            assert attributes["null_reasons"] == {}
            assert item["spatial_links"]["audited_500m_mesh"]["method"] == "exact"
            assert "not a need" in attributes["claim_boundary"]


def test_real_summary_withholds_incomplete_city_totals_and_never_imputes_missing_rows() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["source_report_sha256"] == _sha256(SOURCE_REPORT)
    assert summary["canonical_artifact_sha256"] == _sha256(CANONICAL)
    assert summary["mesh_context_artifact_sha256"] == _sha256(MESH_CONTEXT)
    assert summary["canonical_record_count"] == 2629
    assert summary["mesh_context_feature_count"] == 822
    assert summary["raw_resource_count"] == 4
    assert summary["raw_unique_sha256_count"] == 4
    assert summary["automatic_best_projection_selected"] is False

    expected = {
        "maizuru": {
            "future": 1053,
            "economic": 287,
            "missing_economic": 208,
            "outside_targets": 2,
            "change_rate": -0.29073,
            "establishments": 3394,
            "employees": 33945,
        },
        "fujisawa": {
            "future": 963,
            "economic": 326,
            "missing_economic": 1,
            "outside_targets": 4,
            "change_rate": -0.023701,
            "establishments": 15061,
            "employees": 191307,
        },
    }
    for city_key, values in expected.items():
        city = summary["cities"][city_key]
        future = city["future_population"]
        economic = city["economic_activity"]
        assert future["quality"]["city_feature_count"] == values["future"]
        assert (
            future["quality"]["privacy_aggregation_targets_outside_city_count"]
            == values["outside_targets"]
        )
        assert all(
            item["published_privacy_adjusted_population"] is None
            and item["published_city_total_status"].startswith("unavailable")
            for item in future["analysis"]["series"]
        )
        assert math.isclose(
            future["analysis"]["change_2025_to_2050"]["rate"],
            values["change_rate"],
        )
        quality = economic["quality"]
        assert quality["city_published_mesh_row_count"] == values["economic"]
        assert (
            quality["audited_500m_meshes_without_published_row_count"] == values["missing_economic"]
        )
        assert "never imputed as zero" in quality["missing_row_semantics"]
        sums = economic["analysis"]["published_mesh_row_sums"]
        assert sums["establishments_all_a_s"]["value"] == values["establishments"]
        assert sums["employees_all_a_s"]["value"] == values["employees"]
        assert city["temporal_alignment"]["status"] == "mixed"
        assert city["temporal_alignment"]["hidden_as_single_year"] is False


def test_real_mesh_context_has_explicit_availability_not_fabricated_zeroes() -> None:
    artifact = json.loads(MESH_CONTEXT.read_text(encoding="utf-8"))
    features = artifact["features"]
    assert artifact["crs"]["properties"]["name"] == "EPSG:4326"
    assert len(features) == 822
    assert Counter(item["properties"]["city_code"] for item in features) == {
        "26202": 495,
        "14205": 327,
    }
    assert Counter(
        (item["properties"]["city_code"], item["properties"]["future_population_status"])
        for item in features
    ) == {
        ("26202", "available_official_projection"): 490,
        ("26202", "unavailable_not_published_for_city_code"): 5,
        ("14205", "available_official_projection"): 289,
        ("14205", "unavailable_not_published_for_city_code"): 38,
    }
    assert Counter(
        (item["properties"]["city_code"], item["properties"]["economic_activity_status"])
        for item in features
    ) == {
        ("26202", "available_published_row"): 287,
        ("26202", "unavailable_not_published_in_selected_table"): 208,
        ("14205", "available_published_row"): 326,
        ("14205", "unavailable_not_published_in_selected_table"): 1,
    }
    for feature in features:
        properties = feature["properties"]
        if properties["future_population_status"].startswith("unavailable"):
            assert properties["future_population_2025"] is None
            assert properties["future_population_2050"] is None
            assert properties["future_population_2070"] is None
        if properties["economic_activity_status"].startswith("unavailable"):
            assert properties["economic_establishments_all_a_s"] is None
            assert properties["economic_employees_all_a_s"] is None
        assert properties["temporal_alignment"] == "mixed"
