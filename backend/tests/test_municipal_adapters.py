from __future__ import annotations

import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from backend.citygap_platform.ingestion.adapters import (
    CityGmlSourceAdapter,
    CsvSourceAdapter,
    GeoJsonSourceAdapter,
    GeoPackageSourceAdapter,
    GtfsZipSourceAdapter,
    open_municipal_source,
)

CITYGML = """<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
 xmlns:gml="http://www.opengis.net/gml"
 xmlns:bldg="http://www.opengis.net/citygml/building/2.0">
 <core:cityObjectMember><bldg:Building gml:id="building-1">
  <bldg:lod1Solid><gml:Solid srsName="http://www.opengis.net/def/crs/EPSG/0/6697">
   <gml:exterior><gml:CompositeSurface><gml:surfaceMember><gml:Polygon>
    <gml:exterior><gml:LinearRing><gml:posList>
     35 135 0 35 135.1 0 35.1 135 0 35 135 0
    </gml:posList></gml:LinearRing></gml:exterior>
   </gml:Polygon></gml:surfaceMember></gml:CompositeSurface></gml:exterior>
  </gml:Solid></bldg:lod1Solid>
 </bldg:Building></core:cityObjectMember>
</core:CityModel>
"""

GTFS = {
    "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\ns1,A,35.4,135.3\ns2,B,35.5,135.4\n",
    "routes.txt": "route_id,route_short_name,route_long_name,route_type\nr1,R1,Test,3\n",
    "trips.txt": "route_id,service_id,trip_id\nr1,weekday,t1\n",
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "t1,23:55:00,23:55:00,s1,1\n"
        "t1,24:10:00,24:11:00,s2,2\n"
    ),
    "calendar.txt": (
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "weekday,1,1,1,1,1,0,0,20260101,20261231\n"
    ),
    "calendar_dates.txt": "service_id,date,exception_type\n",
}


def test_csv_adapter_preserves_identifiers_and_enforces_declared_columns(tmp_path: Path) -> None:
    path = tmp_path / "municipal.csv"
    path.write_text("mesh_code,value\n001234567,8\n", encoding="utf-8")
    adapter = CsvSourceAdapter(path, required_columns=("mesh_code", "value"))

    frame = adapter.dataframe()
    inspection = adapter.inspect()
    assert frame.loc[0, "mesh_code"] == "001234567"
    assert inspection.row_count == 1
    assert inspection.source_identifier == f"csv:{inspection.sha256}"
    with pytest.raises(ValueError, match="missing columns"):
        CsvSourceAdapter(path, required_columns=("unknown",)).inspect()


def test_csv_adapter_rejects_formula_cells_and_invalid_encoding(tmp_path: Path) -> None:
    formula = tmp_path / "formula.csv"
    formula.write_text('id,name\n1,=WEBSERVICE("https://example.invalid")\n', encoding="utf-8")
    with pytest.raises(ValueError, match="formula-like"):
        CsvSourceAdapter(formula).inspect()

    invalid = tmp_path / "invalid.csv"
    invalid.write_bytes(b"id,name\n1,\xff\n")
    with pytest.raises(UnicodeDecodeError):
        CsvSourceAdapter(invalid).inspect()


def test_geojson_and_geopackage_adapters_keep_crs_geometry_and_layer(tmp_path: Path) -> None:
    frame = gpd.GeoDataFrame(
        {"facility_id": ["f-1", "f-2"]},
        geometry=[Point(135.3, 35.4), Point(135.4, 35.5)],
        crs="EPSG:4326",
    )
    geojson_path = tmp_path / "facilities.geojson"
    gpkg_path = tmp_path / "facilities.gpkg"
    frame.to_file(geojson_path, driver="GeoJSON", engine="pyogrio")
    frame.to_file(gpkg_path, layer="facilities", driver="GPKG", engine="pyogrio")

    geojson = GeoJsonSourceAdapter(geojson_path, required_columns=("facility_id",)).inspect()
    geopackage = GeoPackageSourceAdapter(
        gpkg_path, layer="facilities", required_columns=("facility_id",)
    ).inspect()
    assert geojson.feature_count == geopackage.feature_count == 2
    assert geojson.geometry_types == geopackage.geometry_types == ("Point",)
    assert geojson.crs == geopackage.crs == "EPSG:4326"
    assert geopackage.layer == "facilities"
    with pytest.raises(ValueError, match="oversized geometry"):
        GeoJsonSourceAdapter(geojson_path, max_geometry_bytes=8).inspect()


def test_gtfs_zip_adapter_validates_real_tables_without_filling_gaps(tmp_path: Path) -> None:
    path = tmp_path / "feed.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in GTFS.items():
            archive.writestr(name, content)

    inspection = GtfsZipSourceAdapter(path).inspect()
    assert inspection.row_count == 7
    assert inspection.source_identifier == f"gtfs:{inspection.sha256}"

    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../stops.txt", GTFS["stops.txt"])
    with pytest.raises(ValueError, match="unsafe member path"):
        GtfsZipSourceAdapter(unsafe)

    formula = tmp_path / "formula.zip"
    with zipfile.ZipFile(formula, "w") as archive:
        for name, content in GTFS.items():
            archive.writestr(
                name,
                content.replace("s1,A,", "s1,=WEBSERVICE,", 1) if name == "stops.txt" else content,
            )
    with pytest.raises(ValueError, match="formula-like"):
        GtfsZipSourceAdapter(formula).inspect()


def test_citygml_adapter_reuses_stream_events_and_reports_provenance(tmp_path: Path) -> None:
    path = tmp_path / "building.gml"
    path.write_text(CITYGML, encoding="utf-8")

    adapter = CityGmlSourceAdapter(path, theme="bldg", source_member="udx/bldg/test.gml")
    inspection = adapter.inspect()
    assert inspection.feature_count == 1
    assert inspection.geometry_part_count == 1
    assert inspection.duplicate_id_count == 0
    assert inspection.layer == "bldg"
    assert inspection.source_identifier.endswith(":udx/bldg/test.gml")


def test_adapter_factory_requires_explicit_supported_format(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    assert isinstance(open_municipal_source("csv", path), CsvSourceAdapter)
    with pytest.raises(ValueError, match="Unsupported municipal source format"):
        open_municipal_source("shapefile", path)  # type: ignore[arg-type]


def test_geojson_adapter_rejects_missing_geometry(tmp_path: Path) -> None:
    path = tmp_path / "empty-geometry.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": None, "properties": {"id": "missing"}}
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing or invalid geometry"):
        GeoJsonSourceAdapter(path).inspect()
