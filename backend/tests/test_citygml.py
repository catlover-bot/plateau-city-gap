from __future__ import annotations

from io import BytesIO

import pytest
from shapely import from_wkt

from backend.citygap_platform.ingestion.citygml import (
    FeatureEnd,
    FeatureStart,
    GeometryPart,
    iter_citygml_events,
)

GML = b"""<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
 xmlns:gml="http://www.opengis.net/gml"
 xmlns:bldg="http://www.opengis.net/citygml/building/2.0">
 <core:cityObjectMember><bldg:Building gml:id="b-1">
  <bldg:measuredHeight uom="m">12.5</bldg:measuredHeight>
  <bldg:lod1Solid><gml:Solid srsName="http://www.opengis.net/def/crs/EPSG/0/6697">
   <gml:exterior><gml:CompositeSurface><gml:surfaceMember><gml:Polygon>
    <gml:exterior><gml:LinearRing><gml:posList>
      35 135 0 35 135.1 0 35.1 135 0 35 135 0
    </gml:posList></gml:LinearRing></gml:exterior>
   </gml:Polygon></gml:surfaceMember></gml:CompositeSurface></gml:exterior>
  </gml:Solid></bldg:lod1Solid>
 </bldg:Building></core:cityObjectMember>
</core:CityModel>"""

DEM_GML = b"""<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
 xmlns:gml="http://www.opengis.net/gml"
 xmlns:dem="http://www.opengis.net/citygml/relief/2.0">
 <core:cityObjectMember><dem:ReliefFeature gml:id="dem-1">
  <dem:lod>1</dem:lod><dem:reliefComponent><dem:TINRelief>
   <dem:tin><gml:TriangulatedSurface srsName="http://www.opengis.net/def/crs/EPSG/0/6697">
    <gml:trianglePatches><gml:Triangle><gml:exterior><gml:LinearRing>
     <gml:posList>35 135 1 35 135.1 2 35.1 135 3 35 135 1</gml:posList>
    </gml:LinearRing></gml:exterior></gml:Triangle></gml:trianglePatches>
   </gml:TriangulatedSurface></dem:tin>
  </dem:TINRelief></dem:reliefComponent>
 </dem:ReliefFeature></core:cityObjectMember>
</core:CityModel>"""


def test_event_reader_preserves_provenance_and_swaps_axis_order() -> None:
    events = list(
        iter_citygml_events(
            BytesIO(GML),
            theme="bldg",
            source_member="udx/bldg/mesh.gml",
            source_member_crc32="0123abcd",
        )
    )

    assert isinstance(events[0], FeatureStart)
    assert events[0].gml_id == "b-1"
    geometry = next(event for event in events if isinstance(event, GeometryPart))
    assert geometry.lod == 1
    assert geometry.geometry_type == "POLYGON"
    assert geometry.ewkt.startswith("SRID=4326;POLYGON Z((135 35 0")
    assert from_wkt(geometry.ewkt.split(";", 1)[1]).is_valid
    end = next(event for event in events if isinstance(event, FeatureEnd))
    assert end.lods == (1,)
    assert end.attributes["measuredHeight"] == "12.5"
    assert end.attributes["_xml_attributes"]["measuredHeight"] == [{"uom": "m"}]


def test_event_reader_does_not_emit_nested_gml_ids_as_features() -> None:
    events = list(
        iter_citygml_events(
            BytesIO(GML),
            theme="bldg",
            source_member="mesh.gml",
            source_member_crc32="0123abcd",
        )
    )
    assert sum(isinstance(event, FeatureStart) for event in events) == 1


def test_declared_terrain_lod_applies_to_streamed_triangle() -> None:
    events = list(
        iter_citygml_events(
            BytesIO(DEM_GML),
            theme="dem",
            source_member="dem.gml",
            source_member_crc32="0123abcd",
        )
    )

    geometry = next(event for event in events if isinstance(event, GeometryPart))
    end = next(event for event in events if isinstance(event, FeatureEnd))
    assert geometry.lod == 1
    assert end.lods == (1,)


def test_event_reader_rejects_dtd_and_entity_declarations() -> None:
    unsafe = b'''<?xml version="1.0"?>
    <!DOCTYPE CityModel [<!ENTITY unsafe "expanded">]>
    <CityModel>&unsafe;</CityModel>'''
    with pytest.raises(ValueError, match="DTD and entity declarations are prohibited"):
        list(
            iter_citygml_events(
                BytesIO(unsafe),
                theme="bldg",
                source_member="unsafe.gml",
                source_member_crc32="00000000",
            )
        )
