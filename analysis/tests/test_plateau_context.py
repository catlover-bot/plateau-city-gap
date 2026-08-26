from __future__ import annotations

import io
import zipfile
from pathlib import Path

from analysis.src.plateau_context import (
    PackageCodelists,
    first_attribute,
    iter_lod1_polygon_features,
    resolved_attribute,
)

GML = b"""<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
 xmlns:gml="http://www.opengis.net/gml"
 xmlns:luse="http://www.opengis.net/citygml/landuse/2.0"
 xmlns:uro="https://www.geospatial.jp/iur/uro/3.2">
 <core:cityObjectMember><luse:LandUse gml:id="land-1">
  <luse:class codeSpace="../../codelists/Common_landUseType.xml">201</luse:class>
  <luse:lod1MultiSurface><gml:MultiSurface srsDimension="2"><gml:surfaceMember>
   <gml:Polygon><gml:exterior><gml:LinearRing>
    <gml:posList>35.0 135.0 35.0 135.1 35.1 135.1 35.1 135.0 35.0 135.0</gml:posList>
   </gml:LinearRing></gml:exterior><gml:interior><gml:LinearRing>
    <gml:posList>35.02 135.02 35.02 135.04 35.04 135.04 35.04 135.02 35.02 135.02</gml:posList>
   </gml:LinearRing></gml:interior></gml:Polygon>
  </gml:surfaceMember></gml:MultiSurface></luse:lod1MultiSurface>
  <luse:lod2MultiSurface><gml:MultiSurface srsDimension="2"><gml:surfaceMember>
   <gml:Polygon><gml:exterior><gml:LinearRing>
    <gml:posList>35 135 35 136 36 136 36 135 35 135</gml:posList>
   </gml:LinearRing></gml:exterior></gml:Polygon>
  </gml:surfaceMember></gml:MultiSurface></luse:lod2MultiSurface>
  <uro:landUseDetailAttribute><uro:LandUseDetailAttribute>
   <uro:areaInSquareMeter uom="m2">100.5</uro:areaInSquareMeter>
   <uro:surveyYear>2024</uro:surveyYear>
  </uro:LandUseDetailAttribute></uro:landUseDetailAttribute>
 </luse:LandUse></core:cityObjectMember>
</core:CityModel>"""


def test_polygon_parser_keeps_lod1_hole_attributes_and_lineage() -> None:
    rows = list(
        iter_lod1_polygon_features(
            io.BytesIO(GML),
            source_member="udx/luse/example.gml",
            source_member_crc32="12abcdef",
            feature_types={"LandUse"},
        )
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["gml_id"] == "land-1"
    assert row["source_member_crc32"] == "12abcdef"
    assert row["surface_part_count"] == 1
    assert len(row["geometry"].interiors) == 1
    assert row["geometry"].bounds == (135.0, 35.0, 135.1, 35.1)
    assert first_attribute(row, "class")["value"] == "201"
    assert first_attribute(row, "areaInSquareMeter") == {
        "path": "landUseDetailAttribute/LandUseDetailAttribute/areaInSquareMeter",
        "value": "100.5",
        "unit": "m2",
    }


def test_coverage_geometry_unions_source_triangles() -> None:
    triangle_gml = GML.replace(
        b"<gml:interior><gml:LinearRing>\n    <gml:posList>35.02 135.02 35.02 135.04 35.04 135.04 35.04 135.02 35.02 135.02</gml:posList>\n   </gml:LinearRing></gml:interior>",
        b"",
    ).replace(
        b"</gml:surfaceMember></gml:MultiSurface></luse:lod1MultiSurface>",
        b"</gml:surfaceMember><gml:surfaceMember><gml:Polygon><gml:exterior>"
        b"<gml:LinearRing><gml:posList>35.1 135.0 35.1 135.1 35.2 135.1 "
        b"35.2 135.0 35.1 135.0</gml:posList></gml:LinearRing></gml:exterior>"
        b"</gml:Polygon></gml:surfaceMember></gml:MultiSurface></luse:lod1MultiSurface>",
        1,
    )
    [row] = list(
        iter_lod1_polygon_features(
            io.BytesIO(triangle_gml),
            source_member="fixture.gml",
            source_member_crc32="00000000",
            coverage_geometry=True,
            union_chunk_size=1,
        )
    )
    assert row["surface_part_count"] == 2
    assert row["geometry"].area > 0


def test_package_codelist_is_the_only_label_source(tmp_path: Path) -> None:
    archive = tmp_path / "plateau.zip"
    dictionary = """<gml:Dictionary xmlns:gml="http://www.opengis.net/gml">
      <gml:dictionaryEntry><gml:Definition><gml:description>田</gml:description>
      <gml:name>201</gml:name></gml:Definition></gml:dictionaryEntry></gml:Dictionary>"""
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("codelists/Common_landUseType.xml", dictionary)

    resolver = PackageCodelists(archive)
    [row] = list(
        iter_lod1_polygon_features(
            io.BytesIO(GML),
            source_member="fixture.gml",
            source_member_crc32="00000000",
        )
    )
    assert resolved_attribute(row, "class", resolver) == {
        "path": "class",
        "value": "201",
        "code_space": "../../codelists/Common_landUseType.xml",
        "official_label": "田",
        "codelist": "Common_landUseType.xml",
    }
    assert resolver.resolve("999", "../../codelists/Common_landUseType.xml") is None
