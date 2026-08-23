from __future__ import annotations

import zipfile
from pathlib import Path

from backend.citygap_platform.ingestion.inventory import build_archive_inventory

FIXTURE = """<?xml version='1.0' encoding='UTF-8'?>
<core:CityModel
 xmlns:core="http://www.opengis.net/citygml/2.0"
 xmlns:gml="http://www.opengis.net/gml"
 xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
 xmlns:uro="https://www.geospatial.jp/iur/uro/3.2">
 <core:cityObjectMember>
  <bldg:Building gml:id="b-1">
   <bldg:usage>住宅</bldg:usage>
   <bldg:measuredHeight uom="m">9.5</bldg:measuredHeight>
   <bldg:lod1Solid><gml:Solid srsName="http://www.opengis.net/def/crs/EPSG/0/6697">
    <gml:exterior><gml:CompositeSurface><gml:surfaceMember>
     <gml:Polygon gml:id="nested-polygon-id"><gml:exterior><gml:LinearRing>
      <gml:posList>35 135 0 35 135.1 0 35.1 135 0 35 135 0</gml:posList>
     </gml:LinearRing></gml:exterior></gml:Polygon>
    </gml:surfaceMember></gml:CompositeSurface></gml:exterior>
   </gml:Solid></bldg:lod1Solid>
   <uro:buildingDataQualityAttribute gml:id="nested-ade-id" />
  </bldg:Building>
 </core:cityObjectMember>
</core:CityModel>
"""


def test_inventory_counts_only_top_level_city_objects(tmp_path: Path) -> None:
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("fixture/udx/bldg/mesh.gml", FIXTURE)

    result = build_archive_inventory(
        archive,
        city_id="26202",
        dataset_year=2025,
        product_specification_version="5.0",
        ade_schema_version="3.2",
    )

    building = result["themes"]["bldg"]
    assert result["totals"]["feature_count"] == 1
    assert result["totals"]["unique_gml_id_count"] == 1
    assert building["feature_types"] == {"Building": 1}
    assert building["lod_feature_counts"] == {"1": 1}
    assert building["geometry_feature_counts"] == {
        "CompositeSurface": 1,
        "Polygon": 1,
        "Solid": 1,
    }
    assert building["attribute_feature_counts"]["usage"] == 1
    assert building["attribute_feature_counts"]["measuredHeight"] == 1
    assert building["crs_names"] == {"http://www.opengis.net/def/crs/EPSG/0/6697": 1}


def test_inventory_accepts_hazard_members_in_nested_theme_directories(tmp_path: Path) -> None:
    archive = tmp_path / "nested.zip"
    hazard = FIXTURE.replace("b-1", "hazard-1")
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("fixture/udx/fld/26/26202/mesh.gml", hazard)

    result = build_archive_inventory(
        archive,
        city_id="26202",
        dataset_year=2025,
        product_specification_version="5.0",
    )

    assert result["archive"]["citygml_file_count"] == 1
    assert result["themes"]["fld"]["feature_count"] == 1
