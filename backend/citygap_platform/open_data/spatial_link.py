"""Versioned deterministic spatial links from canonical points to CITY GAP geography."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import geopandas as gpd
from shapely.geometry import Point


def _link(
    link_type: str,
    target_id: str | None,
    match_method: str,
    explanation: str,
    *,
    distance_m: float | None = None,
) -> dict[str, Any]:
    return {
        "link_type": link_type,
        "target_id": target_id,
        "match_method": match_method,
        "rule_version": "open-data-point-link@1",
        "distance_m": round(distance_m, 3) if distance_m is not None else None,
        "explanation": explanation,
    }


def link_canonical_points(
    records: list[dict[str, Any]],
    *,
    city_code: str,
    meshes: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    analysis_crs: str,
    max_building_candidate_distance_m: float = 30,
    city_link_explanation: str = (
        "Resource was selected from the reviewed city-scoped official catalog."
    ),
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Attach city, 500 m mesh and PLATEAU building-candidate links without identity claims."""

    if meshes.crs is None or buildings.crs is None:
        raise ValueError("Mesh and PLATEAU building inputs must declare CRS")
    if "mesh_code" not in meshes or "gml_id" not in buildings:
        raise ValueError("Mesh code and PLATEAU gml_id are required")
    output = deepcopy(records)
    counts = {
        "city_exact": 0,
        "mesh_linked": 0,
        "mesh_unmatched": 0,
        "plateau_building_candidate": 0,
        "plateau_building_unmatched": 0,
    }
    point_rows = []
    for index, record in enumerate(output):
        record["spatial_links"].append(
            _link(
                "city",
                city_code,
                "exact",
                city_link_explanation,
            )
        )
        counts["city_exact"] += 1
        geometry = record.get("geometry")
        if geometry and geometry.get("type") == "Point":
            longitude, latitude = geometry["coordinates"]
            point_rows.append(
                {"record_index": index, "geometry": Point(float(longitude), float(latitude))}
            )
        else:
            record["spatial_links"].append(
                _link(
                    "mesh",
                    None,
                    "unmatched",
                    "The official row did not publish a validated point geometry.",
                )
            )
            counts["mesh_unmatched"] += 1
            if record["record_type"] == "facility":
                record["spatial_links"].append(
                    _link(
                        "plateau_building",
                        None,
                        "unmatched",
                        "A PLATEAU building candidate cannot be evaluated without point geometry.",
                    )
                )
                counts["plateau_building_unmatched"] += 1
    if not point_rows:
        return output, counts

    points = gpd.GeoDataFrame(point_rows, geometry="geometry", crs="EPSG:4326")
    geographic_meshes = meshes.to_crs("EPSG:4326")[["mesh_code", "geometry"]]
    mesh_matches = gpd.sjoin(points, geographic_meshes, how="left", predicate="intersects")
    mesh_groups = {
        int(index): sorted({str(value) for value in group["mesh_code"].dropna()})
        for index, group in mesh_matches.groupby("record_index")
    }
    for item in point_rows:
        record = output[item["record_index"]]
        matches = mesh_groups.get(item["record_index"], [])
        if len(matches) == 1:
            record["spatial_links"].append(
                _link(
                    "mesh",
                    matches[0],
                    "deterministic",
                    "Published point intersects one audited 500 m mesh polygon.",
                )
            )
            counts["mesh_linked"] += 1
        elif matches:
            record["spatial_links"].append(
                _link(
                    "mesh",
                    matches[0],
                    "ambiguous",
                    f"Published point intersects mesh boundary candidates: {','.join(matches)}.",
                )
            )
            counts["mesh_linked"] += 1
        else:
            record["spatial_links"].append(
                _link(
                    "mesh",
                    None,
                    "unmatched",
                    "Published point does not intersect an audited city mesh polygon.",
                )
            )
            counts["mesh_unmatched"] += 1

    facility_indices = [
        item["record_index"]
        for item in point_rows
        if output[item["record_index"]]["record_type"] == "facility"
    ]
    if not facility_indices:
        return output, counts
    facility_points = points.loc[points["record_index"].isin(facility_indices)].to_crs(analysis_crs)
    projected_buildings = buildings.to_crs(analysis_crs)[["gml_id", "geometry"]]
    nearest = gpd.sjoin_nearest(
        facility_points,
        projected_buildings,
        how="left",
        max_distance=max_building_candidate_distance_m,
        distance_col="distance_m",
    )
    building_groups = {
        int(index): group.sort_values(["distance_m", "gml_id"])
        for index, group in nearest.groupby("record_index")
    }
    for record_index in facility_indices:
        record = output[record_index]
        candidates = building_groups.get(record_index)
        if candidates is None or candidates["gml_id"].dropna().empty:
            record["spatial_links"].append(
                _link(
                    "plateau_building",
                    None,
                    "unmatched",
                    f"No PLATEAU building is within {max_building_candidate_distance_m:g} m.",
                )
            )
            counts["plateau_building_unmatched"] += 1
            continue
        candidate = candidates.loc[candidates["gml_id"].notna()].iloc[0]
        distance = float(candidate["distance_m"])
        record["spatial_links"].append(
            _link(
                "plateau_building",
                str(candidate["gml_id"]),
                "ambiguous",
                (
                    "Nearest PLATEAU footprint candidate; official facility-to-building identity "
                    "has not been verified."
                ),
                distance_m=distance,
            )
        )
        counts["plateau_building_candidate"] += 1
    return output, counts
