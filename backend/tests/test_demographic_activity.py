from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Polygon, mapping

from backend.citygap_platform.open_data.demographic_activity import (
    BROAD_AGE_FIELDS,
    BROAD_AGE_RATIO_FIELDS,
    ECONOMIC_METRICS,
    FIVE_YEAR_AGE_FIELDS,
    PROJECTION_YEARS,
    canonicalize_economic_activity,
    canonicalize_future_population,
    economic_metric_dictionary,
)


def _future_row() -> dict[str, object]:
    row: dict[str, object] = {
        "MESH_ID": "5335700011",
        "SHICODE": "26202",
        "PTN_2020": 10.5,
    }
    for year in PROJECTION_YEARS:
        row[f"HITOKU{year}"] = "*" if year == 2025 else None
        row[f"GASSAN{year}"] = "5335700012" if year == 2025 else None
        row[f"PTN_{year}"] = 9.5
        row[f"PT00_{year}"] = 0.0 if year == 2025 else 9.5
        for field in FIVE_YEAR_AGE_FIELDS:
            row[f"{field}_{year}"] = 0.4
        for field in BROAD_AGE_FIELDS:
            row[f"{field}_{year}"] = 1.0
        for field in BROAD_AGE_RATIO_FIELDS:
            row[f"{field}_{year}"] = 0.1
    return row


def test_future_population_preserves_model_and_privacy_semantics() -> None:
    first = _future_row()
    second = _future_row()
    second["MESH_ID"] = "5335700012"
    second["HITOKU2025"] = "@"
    second["GASSAN2025"] = None
    frame = gpd.GeoDataFrame(
        [first, second],
        geometry=[
            Polygon([(135.0, 35.0), (135.01, 35.0), (135.01, 35.01)]),
            Polygon([(135.01, 35.0), (135.02, 35.0), (135.02, 35.01)]),
        ],
        crs="EPSG:6668",
    )
    context = {
        "533570001": {
            "geometry": mapping(frame.geometry.iloc[0]),
            "city_area_fraction": 1.0,
            "plateau_aggregate": {"residential_building_count": 2},
        }
    }

    records, quality = canonicalize_future_population(
        frame,
        city_code="26202",
        city_name="舞鶴市",
        resource_id="future.zip",
        raw_sha256="a" * 64,
        reference_date="2020-10-01",
        mesh_context=context,
    )

    assert len(records) == 2
    assert records[0]["attributes"]["baseline"]["status"].startswith("modeled_baseline")
    projection = records[0]["attributes"]["projections"][0]
    assert projection["status"] == "official_trial_projection_not_observation"
    assert projection["total_population_before_privacy_aggregation"] == 9.5
    assert projection["published_privacy_adjusted_total_population"] == 0.0
    assert projection["broad_age_ratio_unit"] == "proportion_0_to_1"
    assert projection["privacy_aggregation"]["target_250m_mesh_code"] == "5335700012"
    assert records[0]["spatial_links"]["parent_500m_mesh"]["mesh_code"] == "533570001"
    assert quality["privacy_aggregation_targets_outside_city_count"] == 0


def test_future_population_preserves_privacy_target_outside_city_without_fake_total() -> None:
    row = _future_row()
    row["GASSAN2025"] = "5335700099"
    frame = gpd.GeoDataFrame(
        [row],
        geometry=[Polygon([(135.0, 35.0), (135.01, 35.0), (135.01, 35.01)])],
        crs="EPSG:6668",
    )
    context = {
        "533570001": {
            "geometry": mapping(frame.geometry.iloc[0]),
            "city_area_fraction": 1.0,
        }
    }

    records, quality = canonicalize_future_population(
        frame,
        city_code="26202",
        city_name="舞鶴市",
        resource_id="future.zip",
        raw_sha256="a" * 64,
        reference_date="2020-10-01",
        mesh_context=context,
    )

    privacy = records[0]["attributes"]["projections"][0]["privacy_aggregation"]
    assert privacy["target_scope"] == "outside_exact_city_code_extract"
    assert quality["privacy_aggregation_targets_outside_city"] == ["5335700099"]
    assert "unavailable" in quality["city_published_total_semantics"]


def test_economic_dictionary_covers_all_official_fields() -> None:
    dictionary = economic_metric_dictionary()
    assert len(dictionary) == 46
    assert len({item["source_field"] for item in dictionary}) == 46
    assert dictionary[0]["source_field"] == "T001162001"
    assert dictionary[-1]["source_field"] == "T001162046"
    assert dictionary[0]["public_entity_semantics"].endswith("included")
    assert dictionary[1]["public_entity_semantics"].startswith("private")


def test_economic_activity_keeps_suppressed_null_and_never_fills_missing_mesh() -> None:
    values = {metric.source_field: "1" for metric in ECONOMIC_METRICS}
    values.update({"KEY_CODE": "533570001", "T001162022": "X"})
    context = {
        "533570001": {
            "geometry": mapping(Polygon([(135.0, 35.0), (135.01, 35.0), (135.01, 35.01)])),
            "city_area_fraction": 1.0,
            "plateau_aggregate": None,
        },
        "533570002": {
            "geometry": mapping(Polygon([(135.01, 35.0), (135.02, 35.0), (135.02, 35.01)])),
            "city_area_fraction": 0.5,
            "plateau_aggregate": None,
        },
    }

    records, quality = canonicalize_economic_activity(
        [{"source_row_locator": "row:2", "values": values}],
        city_code="26202",
        city_name="舞鶴市",
        resource_id="economic.zip",
        raw_sha256="b" * 64,
        reference_date="2021-06-01",
        mesh_context=context,
    )

    assert len(records) == 1
    assert records[0]["attributes"]["metrics"]["employees_all_a_s"] is None
    assert records[0]["attributes"]["null_reasons"]["employees_all_a_s"] == {
        "reason": "official_suppression_or_missing_symbol",
        "raw_value": "X",
    }
    assert quality["audited_500m_meshes_without_published_row"] == ["533570002"]
    assert "never imputed as zero" in quality["missing_row_semantics"]
