from datetime import datetime, timezone

import pytest

from backend.citygap_platform.domain.spatial_evidence import (
    DataClassification,
    SpatialEvidencePack,
    SpatialPackStatus,
    UrbanTransect,
    assert_public_pack_safe,
    canonical_sha256,
    transition_pack,
)


def test_pack_lifecycle_has_explicit_real_stages() -> None:
    transition_pack(SpatialPackStatus.QUEUED, SpatialPackStatus.EXTRACTING)
    transition_pack(SpatialPackStatus.EXTRACTING, SpatialPackStatus.BUILDING)
    transition_pack(SpatialPackStatus.BUILDING, SpatialPackStatus.VALIDATING)
    transition_pack(SpatialPackStatus.VALIDATING, SpatialPackStatus.READY)
    transition_pack(SpatialPackStatus.READY, SpatialPackStatus.SUPERSEDED)
    with pytest.raises(ValueError):
        transition_pack(SpatialPackStatus.QUEUED, SpatialPackStatus.READY)


def test_ready_pack_requires_reproducibility_hashes() -> None:
    digest = canonical_sha256({"records": 296})
    pack = SpatialEvidencePack(
        pack_id="pack-533513314-v1",
        organization_id="org",
        city_id="26202",
        urban_state_id="maizuru-2025",
        investigation_id="investigation",
        geometry_geojson={"type": "Polygon", "coordinates": []},
        bbox=(135.39375, 35.445833, 135.4, 35.45),
        buffer_m=100,
        status=SpatialPackStatus.READY,
        data_classification=DataClassification.PUBLIC,
        source_dataset_versions=("plateau-maizuru-2025",),
        network_version_id=None,
        analysis_run_ids=(),
        created_by="test",
        created_at=datetime.now(timezone.utc),
        content_hash=digest,
        manifest_hash=digest,
    )
    assert pack.status is SpatialPackStatus.READY


def test_public_pack_rejects_per_building_population_model() -> None:
    assert_public_pack_safe([{"object_type": "building", "measured_height_m": 8.5}])
    with pytest.raises(ValueError, match="estimated_population"):
        assert_public_pack_safe([{"properties": {"estimated_population": 3.4}}])


def test_transect_requires_actual_source_and_datum() -> None:
    transect = UrbanTransect(
        transect_id="transect-1",
        pack_id="pack-1",
        organization_id="org",
        geometry_geojson={
            "type": "LineString",
            "coordinates": [[135.394, 35.447], [135.399, 35.448]],
        },
        buffer_m=12,
        sample_interval_m=5,
        vertical_datum="WGS 84 ellipsoidal height (EPSG:4979)",
        terrain_source="PLATEAU Maizuru 2025 dem:TINRelief",
        created_by="test",
        created_at=datetime.now(timezone.utc),
    )
    assert transect.sample_interval_m == 5
