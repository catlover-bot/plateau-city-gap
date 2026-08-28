import json
import zipfile
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from analysis.scripts.build_building_demographics import _buffer_features, _coverage
from analysis.src.building_demographics import (
    allocate_by_mesh,
    assign_capacity,
    building_mesh_crosswalk,
    classify_usage,
    nearest_facility,
    numeric_values,
    valid_area,
    weighted_quantile,
    weighted_statistics,
)
from analysis.src.plateau_buildings import iter_buildings, read_gml_dictionary


def test_official_usage_groups_remain_separate() -> None:
    assert classify_usage("411") == "residential"
    assert classify_usage("412") == "residential"
    assert classify_usage("413") == "mixed_residential"
    assert classify_usage("415") == "mixed_residential"
    assert classify_usage("461") == "uncertain"
    assert classify_usage("402") == "non_residential"


def test_capacity_hierarchy_does_not_clamp_invalid_area() -> None:
    buildings = pd.DataFrame(
        {
            "totalFloorArea": [120, -9999, None, -2],
            "buildingFootprintArea": [60, 50, 40, -3],
            "storeysAboveGround": [2, 3, 9999, 2],
        }
    )
    result = assign_capacity(buildings)
    assert result["allocation_weight_source"].tolist() == [
        "total_floor_area",
        "footprint_times_storeys",
        "footprint_only",
        "not_allocatable",
    ]
    assert result["allocation_weight"].iloc[:3].tolist() == [120, 150, 40]
    assert pd.isna(result["allocation_weight"].iloc[3])


def test_floor_area_numeric_parsing_and_invalid_values() -> None:
    values = pd.Series(["120.5", "0", "-9999", "not-a-number", None])
    assert numeric_values(values).iloc[0] == pytest.approx(120.5)
    assert valid_area(values).tolist() == [True, False, False, False, False]


def test_package_local_gml_usage_dictionary_mapping(tmp_path: Path) -> None:
    xml = """<gml:Dictionary xmlns:gml="http://www.opengis.net/gml">
      <gml:dictionaryEntry><gml:Definition>
        <gml:description>住宅</gml:description><gml:name>411</gml:name>
      </gml:Definition></gml:dictionaryEntry>
      <gml:dictionaryEntry><gml:Definition>
        <gml:description>店舗等併用住宅</gml:description><gml:name>413</gml:name>
      </gml:Definition></gml:dictionaryEntry>
    </gml:Dictionary>"""
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("codelists/Building_usage.xml", xml)
    mapping = read_gml_dictionary(archive, "codelists/Building_usage.xml")
    assert mapping == [
        {"usage_code": "411", "official_label": "住宅"},
        {"usage_code": "413", "official_label": "店舗等併用住宅"},
    ]
    assert [classify_usage(row["usage_code"]) for row in mapping] == [
        "residential",
        "mixed_residential",
    ]


def test_citygml_footprint_preserves_polygon_interior_ring() -> None:
    xml = b"""<core:CityModel
      xmlns:core="http://www.opengis.net/citygml/2.0"
      xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
      xmlns:gml="http://www.opengis.net/gml">
      <core:cityObjectMember><bldg:Building gml:id="with-hole">
        <bldg:usage>411</bldg:usage><bldg:lod0RoofEdge><gml:MultiSurface>
          <gml:surfaceMember><gml:Polygon>
            <gml:exterior><gml:LinearRing><gml:posList>
              0 0 0 0 10 0 10 10 0 10 0 0 0 0 0
            </gml:posList></gml:LinearRing></gml:exterior>
            <gml:interior><gml:LinearRing><gml:posList>
              3 3 0 3 7 0 7 7 0 7 3 0 3 3 0
            </gml:posList></gml:LinearRing></gml:interior>
          </gml:Polygon></gml:surfaceMember>
        </gml:MultiSurface></bldg:lod0RoofEdge>
      </bldg:Building></core:cityObjectMember>
    </core:CityModel>"""
    records = list(
        iter_buildings(BytesIO(xml), source_member="fixture.gml", source_member_crc32="0")
    )
    assert len(records) == 1
    assert records[0]["geometry"].area == pytest.approx(84)
    assert len(records[0]["geometry"].interiors) == 1


def test_crosswalk_splits_a_building_crossing_two_meshes() -> None:
    buildings = gpd.GeoDataFrame(
        {"gml_id": ["b1"]}, geometry=[box(5, 0, 15, 10)], crs="EPSG:6674"
    )
    meshes = gpd.GeoDataFrame(
        {"mesh_code": ["left", "right"]},
        geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)],
        crs="EPSG:6674",
    )
    result = building_mesh_crosswalk(buildings, meshes).sort_values("mesh_code")
    assert result["intersection_area"].tolist() == [50, 50]
    assert result["intersection_fraction"].tolist() == [0.5, 0.5]


def _allocation_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    crosswalk = pd.DataFrame(
        {
            "gml_id": ["r1", "r2", "mixed", "commercial", "suppressed"],
            "mesh_code": ["safe", "safe", "safe", "safe", "hidden"],
            "usage_code": ["411", "412", "413", "402", "411"],
            "allocation_weight": [100.0, 300.0, 400.0, 900.0, 100.0],
            "intersection_fraction": [1.0, 1.0, 0.5, 1.0, 1.0],
        }
    )
    meshes = pd.DataFrame(
        {
            "mesh_code": ["safe", "hidden"],
            "population": [80.0, 50.0],
            "elderly_population": [20.0, float("nan")],
            "primary_eligible_disclosure": [True, False],
        }
    )
    return crosswalk, meshes


def test_strict_allocation_conserves_population_and_protects_suppression() -> None:
    crosswalk, meshes = _allocation_fixture()
    rows, conservation = allocate_by_mesh(crosswalk, meshes, policy="strict_residential")
    assert set(rows["gml_id"]) == {"r1", "r2"}
    assert rows["estimated_population"].sum() == pytest.approx(80)
    assert rows["estimated_elderly_population"].sum() == pytest.approx(20)
    assert "suppressed" not in rows["gml_id"].tolist()
    safe = conservation.set_index("mesh_code").loc["safe"]
    assert safe["population_error"] == pytest.approx(0)
    assert safe["elderly_error"] == pytest.approx(0)


def test_mixed_sensitivity_uses_full_area_without_inventing_a_share() -> None:
    crosswalk, meshes = _allocation_fixture()
    rows, _ = allocate_by_mesh(crosswalk, meshes, policy="residential_plus_mixed")
    mixed = rows.set_index("gml_id").loc["mixed"]
    assert mixed["effective_floor_area_in_mesh"] == 200
    assert mixed["estimated_population"] == pytest.approx(80 * 200 / 600)


def test_no_residential_and_no_plateau_meshes_fall_back_without_forced_allocation() -> None:
    meshes = pd.DataFrame(
        {
            "mesh_code": ["commercial", "empty", "hidden"],
            "primary_eligible_disclosure": [True, True, False],
        }
    )
    crosswalk = pd.DataFrame(
        {"mesh_code": ["commercial"], "gml_id": ["shop"], "usage_code": ["402"]}
    )
    allocated = pd.DataFrame(columns=["mesh_code", "gml_id"])
    coverage = _coverage(meshes, crosswalk, allocated).set_index("mesh_code")
    assert coverage.loc["commercial", "population_resolution"] == (
        "mesh_fallback_no_residential_building"
    )
    assert coverage.loc["empty", "population_resolution"] == "mesh_fallback_no_plateau"
    assert coverage.loc["hidden", "population_resolution"] == "mesh_fallback_suppression"


def test_cross_border_buffer_policy_includes_nearby_but_not_distant_facilities() -> None:
    boundary = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100)], crs="EPSG:6674")
    facilities = gpd.GeoDataFrame(
        {"name": ["inside", "near outside", "far outside"]},
        geometry=[Point(50, 50), Point(150, 50), Point(2201, 50)],
        crs="EPSG:6674",
    )
    buffered = _buffer_features(facilities, boundary)
    assert buffered["name"].tolist() == ["inside", "near outside"]


def test_weighted_mean_median_and_p90() -> None:
    values = pd.Series([100.0, 200.0, 900.0])
    weights = pd.Series([8.0, 1.0, 1.0])
    assert weighted_quantile(values, weights, 0.5) == 100
    assert weighted_quantile(values, weights, 0.9) == 200
    stats = weighted_statistics(values, weights)
    assert stats["mean"] == pytest.approx(190)
    assert stats["median"] == 100
    assert stats["p90"] == 200


def test_representative_point_and_nearest_facility() -> None:
    polygon = box(0, 0, 10, 10).difference(box(2, 2, 8, 8))
    origin = polygon.representative_point()
    assert polygon.covers(origin)
    origins = gpd.GeoDataFrame(geometry=[origin], crs="EPSG:6674")
    facilities = gpd.GeoDataFrame(
        {"name": ["far", "near"]},
        geometry=[Point(100, 100), Point(11, origin.y)],
        crs="EPSG:6674",
    )
    result = nearest_facility(origins, facilities, name_column="name")
    assert result.loc[0, "name"] == "near"
    assert result.loc[0, "distance_m"] == pytest.approx(10)


def test_real_summary_records_required_provenance_when_generated() -> None:
    path = Path("analysis/outputs/real/maizuru_building_demographics_summary.json")
    if not path.exists():
        pytest.skip(
            "ENVIRONMENT_SPECIFIC: real output is generated by the canonical Priority 2 pipeline"
        )
    summary = json.loads(path.read_text(encoding="utf-8"))
    provenance = summary["provenance"]
    assert provenance["dataset_archive_sha256"]
    assert provenance["citygml_specification"] == "5.0"
    assert provenance["population_year"] == 2020
    assert provenance["usage_mapping_version"]
    assert provenance["crs"] == "EPSG:6674"
    assert provenance["software"]["commit"]
