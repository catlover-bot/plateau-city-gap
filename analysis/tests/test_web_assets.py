import hashlib
import json
import struct
from copy import deepcopy
from pathlib import Path

import pytest

from analysis.scripts.build_plateau_web_subset import (
    _building_summary,
    _read_buildings,
    _validate_output_target,
)
from analysis.scripts.build_web_assets import (
    MESH_PROPERTIES,
    validate_geojson_geometry,
    validate_mesh_assets,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WEB_DATA = REPOSITORY_ROOT / "frontend/public/data"


def _mesh_properties(rank: int) -> dict[str, object]:
    code = f"533512{rank:03d}"
    properties = {
        "mesh_code": code,
        "rank": rank,
        "population": 100,
        "elderly_population": 40.0,
        "centroid_lat": 35.4 + rank / 1000,
        "centroid_lon": 135.3 + rank / 1000,
    }
    for column in (
        "nearest_station_distance_m",
        "nearest_bus_stop_distance_m",
        "nearest_public_transport_distance_m",
        "nearest_medical_distance_m",
        "nearest_hospital_distance_m",
    ):
        properties[column] = 1000.0
    return properties


def _valid_assets() -> tuple[dict[str, object], dict[str, object]]:
    features = []
    items = []
    for rank in range(1, 11):
        properties = _mesh_properties(rank)
        longitude = properties["centroid_lon"]
        latitude = properties["centroid_lat"]
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [longitude - 0.001, latitude - 0.001],
                            [longitude + 0.001, latitude - 0.001],
                            [longitude + 0.001, latitude + 0.001],
                            [longitude - 0.001, latitude + 0.001],
                            [longitude - 0.001, latitude - 0.001],
                        ]
                    ],
                },
            }
        )
        items.append(deepcopy(properties))
    return (
        {"type": "FeatureCollection", "features": features},
        {"count": 10, "items": items},
    )


def test_mesh_validation_accepts_consistent_assets() -> None:
    meshes, top10 = _valid_assets()

    validate_mesh_assets(meshes, top10)


def test_mesh_validation_rejects_elderly_population_above_population() -> None:
    meshes, top10 = _valid_assets()
    meshes["features"][0]["properties"]["elderly_population"] = 101

    with pytest.raises(ValueError, match="elderly population above population"):
        validate_mesh_assets(meshes, top10)


def test_mesh_validation_rejects_top10_not_in_full_dataset() -> None:
    meshes, top10 = _valid_assets()
    top10["items"][0]["mesh_code"] = "999999999"

    with pytest.raises(ValueError, match="missing from the full dataset"):
        validate_mesh_assets(meshes, top10)


def test_geometry_validation_rejects_invalid_longitude() -> None:
    points = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Point", "coordinates": [200, 35]},
            }
        ],
    }

    with pytest.raises(ValueError, match="outside valid lon/lat"):
        validate_geojson_geometry(points, expected_types={"Point"})


def test_published_web_assets_are_valid_and_traceable() -> None:
    manifest = json.loads((WEB_DATA / "manifest.json").read_text(encoding="utf-8"))
    meshes = json.loads(
        (WEB_DATA / "mesh_metrics.geojson").read_text(encoding="utf-8")
    )
    top10 = json.loads((WEB_DATA / "top10.json").read_text(encoding="utf-8"))
    validate_mesh_assets(meshes, top10)

    assert len(meshes["features"]) == 495
    assert set(meshes["features"][0]["properties"]) == set(MESH_PROPERTIES)
    assert manifest["crs"] == {"analysis": "EPSG:6674", "web": "EPSG:4326"}
    assert manifest["data_years"] == {
        "population": 2020,
        "medical": 2020,
        "bus_stops": 2022,
        "plateau_related": 2025,
    }
    assert manifest["record_counts"] == {
        "mesh_metrics": 495,
        "top10": 10,
        "stations": 7,
        "bus_stops": 151,
        "medical_facilities": 105,
        "administrative_boundary": 1,
        "plateau_top10_buildings": 0,
        "plateau_reference_buildings": 2_152,
    }
    assert manifest["limitations"]
    assert all(item["sha256"] for item in manifest["lineage"]["inputs"])

    point_layers = {
        "stations.geojson": 7,
        "bus_stops.geojson": 151,
        "medical_facilities.geojson": 105,
    }
    for filename, expected_count in point_layers.items():
        collection = json.loads((WEB_DATA / filename).read_text(encoding="utf-8"))
        validate_geojson_geometry(collection, expected_types={"Point"})
        assert len(collection["features"]) == expected_count

    output_by_name = {item["file"]: item for item in manifest["outputs"]}
    for filename, output in output_by_name.items():
        path = WEB_DATA / filename
        assert path.stat().st_size == output["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == output["sha256"]

    plateau_metadata = json.loads(
        (WEB_DATA / "plateau_metadata.json").read_text(encoding="utf-8")
    )
    plateau_buildings = json.loads(
        (WEB_DATA / "plateau_buildings.geojson").read_text(encoding="utf-8")
    )
    assert plateau_metadata["building_layer"]["status"] == "verified_empty_for_top10"
    assert plateau_metadata["building_layer"]["records"] == 0
    assert plateau_buildings["features"] == []

    reference_outputs = {
        item["file"]: item for item in manifest["plateau_reference_outputs"]
    }
    assert {"plateau/metadata.json", "plateau/tileset.json"} <= set(
        reference_outputs
    )
    assert len([name for name in reference_outputs if name.endswith(".b3dm")]) == 5
    for filename, output in reference_outputs.items():
        path = WEB_DATA / filename
        assert path.stat().st_size == output["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == output["sha256"]


def test_published_plateau_reference_tiles_are_official_and_consistent() -> None:
    plateau_dir = WEB_DATA / "plateau"
    metadata = json.loads((plateau_dir / "metadata.json").read_text(encoding="utf-8"))
    tileset = json.loads((plateau_dir / "tileset.json").read_text(encoding="utf-8"))
    root_metadata = json.loads(
        (WEB_DATA / "plateau_metadata.json").read_text(encoding="utf-8")
    )
    inspection = json.loads(
        (
            REPOSITORY_ROOT
            / "analysis/outputs/real/maizuru_plateau_building_inspection.json"
        ).read_text(encoding="utf-8")
    )

    assert metadata["status"] == "reference_subset_available"
    assert metadata["source"]["url"].startswith(
        "https://assets.cms.plateau.reearth.io/"
    )
    assert metadata["city_gap_top10"] == {
        "status": "outside_official_building_coverage",
        "building_centers": 0,
        "building_bbox_intersections": 0,
        "official_distribution_unique_buildings": 44_640,
    }
    assert metadata["selection"]["tiles"] == 5
    assert metadata["buildings"]["records"] == 2_152
    assert metadata["buildings"]["geometry_lod"] == {"1": 1_215, "2": 937}
    assert inspection["whole_city_lod1_attributes"]["lod2_source_populated"] == 1_504
    assert inspection["whole_city_lod2_attributes"]["lod2_source_populated"] == 1_504

    children = tileset["root"]["children"]
    uris = [child["content"]["uri"] for child in children]
    assert len(uris) == len(set(uris)) == metadata["selection"]["tiles"]
    file_metadata = {item["uri"]: item for item in metadata["files"]}
    assert set(uris) == set(file_metadata)

    batch_records = 0
    b3dm_bytes = 0
    for uri in uris:
        path = plateau_dir / uri
        header = path.read_bytes()[:28]
        assert header[:4] == b"b3dm"
        version, byte_length, feature_json_length = struct.unpack("<III", header[4:16])
        assert version == 1
        assert byte_length == path.stat().st_size
        feature_table = json.loads(
            path.read_bytes()[28 : 28 + feature_json_length].decode("utf-8")
        )
        batch_records += int(feature_table["BATCH_LENGTH"])
        b3dm_bytes += byte_length
        assert hashlib.sha256(path.read_bytes()).hexdigest() == file_metadata[uri][
            "sha256"
        ]

    assert batch_records == metadata["buildings"]["records"]
    assert b3dm_bytes == metadata["selection"]["b3dm_bytes"]
    assert root_metadata["reference_layer"]["records"] == batch_records
    assert root_metadata["reference_layer"]["tileset_url"] == (
        "data/plateau/tileset.json"
    )

    buildings = [
        building
        for uri in uris
        for building in _read_buildings(plateau_dir / uri)
    ]
    assert _building_summary(buildings) == metadata["buildings"]


def test_plateau_output_target_must_be_disjoint_and_not_symlinked(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(ValueError, match="disjoint"):
        _validate_output_target(source, source)
    with pytest.raises(ValueError, match="disjoint"):
        _validate_output_target(source, source / "nested")

    output = tmp_path / "output"
    output.mkdir()
    (output / "data").symlink_to(tmp_path / "unrelated", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        _validate_output_target(source, output)
