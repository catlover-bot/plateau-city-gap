from __future__ import annotations

from analysis.scripts.build_guided_area_contexts import (
    SECTION_MESH_CODE,
    SOURCE_SHA256,
    check,
)


def test_checked_in_guided_area_contexts_are_citywide_and_provenanced() -> None:
    catalog = check()

    assert len(catalog["items"]) == 495
    assert catalog["source"]["sha256"] == SOURCE_SHA256
    assert catalog["mesh_source"]["area_count"] == 495
    assert set(catalog["prohibitions"]) == {
        "no_population_allocation",
        "no_walking_semantics",
        "no_risk_or_recommendation",
        "no_inferred_use",
        "no_fake_geometry",
    }


def test_only_the_verified_area_advertises_an_urban_section() -> None:
    catalog = check()

    available = [
        item["mesh_code"]
        for item in catalog["items"]
        if item["capabilities"]["urban_section"]["status"] == "available"
    ]
    assert available == [SECTION_MESH_CODE]


def test_light_catalog_contains_no_area_object_ids_or_geometry_payloads() -> None:
    catalog = check()

    assert "layers" not in catalog
    assert all("layers" not in item for item in catalog["items"])
    assert all("object_ids" not in item for item in catalog["items"])
    assert all(
        "path" not in capability and "pack_id" not in capability
        for item in catalog["items"]
        for capability in item["capabilities"].values()
    )
