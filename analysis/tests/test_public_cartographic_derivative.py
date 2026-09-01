from __future__ import annotations

import copy

import pytest

from analysis.scripts.build_public_cartographic_derivative import (
    SOURCE_SHA256,
    check,
    validate_collection,
)


def collection() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "building-1",
                "properties": {
                    "object_id": "building-1",
                    "object_type": "building",
                    "usage_code": "411",
                    "usage_label": "住宅",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[135.0, 35.0], [135.1, 35.0], [135.1, 35.1], [135.0, 35.1], [135.0, 35.0]]],
                },
            }
        ],
    }


def test_checked_in_display_derivative_has_exact_provenance() -> None:
    manifest = check()

    assert manifest["artifact_kind"] == "display_derivative"
    assert manifest["scope"]["origin"]["source_feature_id"] == "station-007"
    assert manifest["source"]["city_code"] == "26202"
    assert manifest["source"]["sha256"] == SOURCE_SHA256
    assert set(manifest["resolved_target_ids"]["buildings"]) == {
        "bldg_155e6675-6981-450f-8e73-df0b43418cc2"
    }
    assert set(manifest["resolved_target_ids"]["roads"]) == {
        "tran_46c7e1e5-07ba-424d-ba29-2ae7f0464a21"
    }
    assert {
        "no_external_data",
        "no_population_allocation",
        "no_usage_inference",
        "no_walking_semantics",
        "no_hazard_or_safety_meaning",
        "no_score",
    } == set(manifest["prohibitions"])


def test_checked_in_derivative_can_be_verified_without_untracked_raw_archive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "analysis.scripts.build_public_cartographic_derivative.ARCHIVE",
        tmp_path / "intentionally-untracked-citygml.zip",
    )

    manifest = check()

    assert manifest["source"]["sha256"] == SOURCE_SHA256


def test_display_collection_rejects_duplicate_feature_ids() -> None:
    value = collection()
    value["features"].append(copy.deepcopy(value["features"][0]))

    with pytest.raises(ValueError, match="Duplicate"):
        validate_collection("buildings", value)


def test_display_collection_rejects_unapproved_properties() -> None:
    value = collection()
    value["features"][0]["properties"]["score"] = 99

    with pytest.raises(ValueError, match="Unexpected display properties"):
        validate_collection("buildings", value)


def test_display_collection_rejects_invalid_geometry() -> None:
    value = collection()
    value["features"][0]["geometry"]["coordinates"] = [[
        [135.0, 35.0],
        [135.1, 35.1],
        [135.1, 35.0],
        [135.0, 35.1],
        [135.0, 35.0],
    ]]

    with pytest.raises(ValueError, match="Invalid display geometry"):
        validate_collection("buildings", value)
