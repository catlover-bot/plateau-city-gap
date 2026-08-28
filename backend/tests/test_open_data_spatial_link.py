from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Polygon

from backend.citygap_platform.open_data.spatial_link import link_canonical_points


def test_canonical_point_links_are_versioned_and_building_identity_stays_ambiguous() -> None:
    records = [
        {
            "record_type": "facility",
            "geometry": {"type": "Point", "coordinates": [135.4, 35.4]},
            "spatial_links": [],
        },
        {"record_type": "population_observation", "geometry": None, "spatial_links": []},
    ]
    meshes = gpd.GeoDataFrame(
        {"mesh_code": ["mesh-1"]},
        geometry=[Polygon([(135.3, 35.3), (135.5, 35.3), (135.5, 35.5), (135.3, 35.5)])],
        crs="EPSG:4326",
    )
    buildings = gpd.GeoDataFrame(
        {"gml_id": ["bldg-1"]},
        geometry=[
            Polygon(
                [
                    (135.3999, 35.3999),
                    (135.4001, 35.3999),
                    (135.4001, 35.4001),
                    (135.3999, 35.4001),
                ]
            )
        ],
        crs="EPSG:4326",
    )
    linked, counts = link_canonical_points(
        records,
        city_code="26202",
        meshes=meshes,
        buildings=buildings,
        analysis_crs="EPSG:6674",
    )
    facility_links = {item["link_type"]: item for item in linked[0]["spatial_links"]}
    assert facility_links["city"]["match_method"] == "exact"
    assert facility_links["mesh"]["target_id"] == "mesh-1"
    assert facility_links["plateau_building"]["target_id"] == "bldg-1"
    assert facility_links["plateau_building"]["match_method"] == "ambiguous"
    assert counts["plateau_building_candidate"] == 1
    assert linked[1]["spatial_links"][1]["match_method"] == "unmatched"
