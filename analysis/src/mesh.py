"""JIS X 0410 regional mesh decoding helpers."""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

GEOGRAPHIC_CRS = "EPSG:6668"  # JGD2011 geographic 2D


@dataclass(frozen=True)
class MeshBounds:
    south: float
    west: float
    north: float
    east: float


def decode_500m_mesh(mesh_code: str | int) -> MeshBounds:
    """Decode a nine-digit half (500 m) regional mesh code to JGD2011 bounds.

    The last digit follows the JIS quadrant convention: 1=south-west,
    2=south-east, 3=north-west, 4=north-east.
    """
    code = str(mesh_code).strip()
    if len(code) != 9 or not code.isdigit() or code[-1] not in "1234":
        raise ValueError(f"Invalid 500 m mesh code: {mesh_code!r}")

    south = int(code[0:2]) / 1.5
    west = int(code[2:4]) + 100.0
    south += int(code[4]) / 12.0
    west += int(code[5]) / 8.0
    south += int(code[6]) / 120.0
    west += int(code[7]) / 80.0

    quadrant = int(code[8])
    if quadrant in (3, 4):
        south += 1.0 / 240.0
    if quadrant in (2, 4):
        west += 1.0 / 160.0
    return MeshBounds(
        south=south,
        west=west,
        north=south + 1.0 / 240.0,
        east=west + 1.0 / 160.0,
    )


def mesh_polygon(mesh_code: str | int) -> Polygon:
    bounds = decode_500m_mesh(mesh_code)
    return Polygon(
        [
            (bounds.west, bounds.south),
            (bounds.east, bounds.south),
            (bounds.east, bounds.north),
            (bounds.west, bounds.north),
            (bounds.west, bounds.south),
        ]
    )


def decode_250m_mesh(mesh_code: str | int) -> MeshBounds:
    """Decode a ten-digit quarter (250 m) regional mesh code.

    The first nine digits identify the parent 500 m mesh.  The final digit uses
    the same south-west/south-east/north-west/north-east quadrant convention.
    Datum interpretation belongs to the source contract (for example J-SHIS V4
    publishes JGD2000); this helper only decodes the mesh grid.
    """

    code = str(mesh_code).strip()
    if len(code) != 10 or not code.isdigit() or code[-1] not in "1234":
        raise ValueError(f"Invalid 250 m mesh code: {mesh_code!r}")
    parent = decode_500m_mesh(code[:9])
    latitude_step = (parent.north - parent.south) / 2
    longitude_step = (parent.east - parent.west) / 2
    south = parent.south + (latitude_step if code[-1] in "34" else 0)
    west = parent.west + (longitude_step if code[-1] in "24" else 0)
    return MeshBounds(
        south=south,
        west=west,
        north=south + latitude_step,
        east=west + longitude_step,
    )


def mesh_polygon_250m(mesh_code: str | int) -> Polygon:
    bounds = decode_250m_mesh(mesh_code)
    return Polygon(
        [
            (bounds.west, bounds.south),
            (bounds.east, bounds.south),
            (bounds.east, bounds.north),
            (bounds.west, bounds.north),
            (bounds.west, bounds.south),
        ]
    )


def population_to_geodataframe(frame: pd.DataFrame) -> gpd.GeoDataFrame:
    """Build 500 m polygons and representative longitude/latitude columns."""
    if "mesh_code" not in frame:
        raise ValueError("population table requires mesh_code")
    result = gpd.GeoDataFrame(
        frame.copy(),
        geometry=[mesh_polygon(value) for value in frame["mesh_code"]],
        crs=GEOGRAPHIC_CRS,
    )
    bounds = [decode_500m_mesh(value) for value in frame["mesh_code"]]
    result["centroid_lon"] = [(value.west + value.east) / 2 for value in bounds]
    result["centroid_lat"] = [(value.south + value.north) / 2 for value in bounds]
    return result
