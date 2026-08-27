"""Build a small, provenance-preserving PLATEAU DEM terrain tile for the web UI.

The public 3D scene uses the official streamed PLATEAU building tiles and the
official PLATEAU-Terrain service for broad context.  This script adds a local
Deep Dive surface built directly from Maizuru's 2025 ``dem:TINRelief``.  It
does not interpolate, exaggerate, smooth, or invent a height.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from pyproj import CRS, Transformer
from pyproj import network as proj_network
from pyproj.transformer import TransformerGroup

from analysis.src.plateau_terrain import _member_envelope, iter_dem_triangles

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE = (
    REPOSITORY_ROOT
    / "data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip"
)
DEFAULT_OUTPUT = REPOSITORY_ROOT / "frontend/public/data/plateau-terrain"

# Verified PLATEAU-covered Deep Dive around the 500 m mesh 533513314 and the
# three bundled fallback building tiles.  The quality boundary is explicit:
# the generated terrain is not a whole-city terrain replacement.
DEFAULT_BOUNDS = (135.3925, 35.4447, 135.4052, 35.4510)
SOURCE_CRS = CRS.from_epsg(6697)
WEB_CRS = CRS.from_epsg(4979)
ECEF_CRS = CRS.from_epsg(4978)
GEOID_GRID = "jp_gsi_gsigeo2011.tif"
GEOID_GRID_URL = f"https://cdn.proj.org/{GEOID_GRID}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _intersects(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    return not (
        first[2] < second[0]
        or first[0] > second[2]
        or first[3] < second[1]
        or first[1] > second[3]
    )


def _triangle_intersects(
    triangle: tuple[tuple[float, float, float], ...],
    bounds: tuple[float, float, float, float],
) -> bool:
    longitudes = [point[0] for point in triangle]
    latitudes = [point[1] for point in triangle]
    return _intersects(
        (min(longitudes), min(latitudes), max(longitudes), max(latitudes)),
        bounds,
    )


def _select_triangles(
    archive: Path,
    bounds: tuple[float, float, float, float],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    selected: list[tuple[tuple[float, float, float], ...]] = []
    sources: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as package:
        members = [
            info
            for info in package.infolist()
            if "/dem/" in info.filename and info.filename.endswith(".gml")
        ]
        for info in members:
            with package.open(info) as stream:
                envelope = _member_envelope(stream)
            if not _intersects(envelope, bounds):
                continue
            scanned = 0
            before = len(selected)
            with package.open(info) as stream:
                for _, triangle in iter_dem_triangles(stream):
                    scanned += 1
                    if _triangle_intersects(triangle, bounds):
                        selected.append(triangle)
            sources.append(
                {
                    "member": info.filename,
                    "member_crc32": f"{info.CRC:08x}",
                    "member_uncompressed_bytes": info.file_size,
                    "envelope": envelope,
                    "triangles_scanned": scanned,
                    "triangles_selected": len(selected) - before,
                }
            )
    if not selected:
        raise ValueError("No PLATEAU DEM triangles intersect the requested quality boundary")
    return np.asarray(selected, dtype=np.float64), sources


def _vertical_transformer() -> Transformer:
    # EPSG:6697 stores JGD2011 gravity-related heights.  Cesium and the official
    # building 3D Tiles use ellipsoidal heights, so the published GSIGEO2011
    # grid is required.  A ballpark/no-grid transform is rejected.
    proj_network.set_network_enabled(True)
    group = TransformerGroup(SOURCE_CRS, WEB_CRS, always_xy=True)
    if not group.best_available:
        raise RuntimeError(f"Required vertical grid is unavailable: {GEOID_GRID_URL}")
    transformer = group.transformers[0]
    if "ballpark" in transformer.description.lower():
        raise RuntimeError("Refusing a ballpark PLATEAU DEM vertical transformation")
    return transformer


def _to_local_enu(
    triangles: np.ndarray,
) -> tuple[np.ndarray, list[float], tuple[float, float, float]]:
    flat = triangles.reshape(-1, 3)
    vertical = _vertical_transformer()
    longitude, latitude, ellipsoid_height = vertical.transform(
        flat[:, 0], flat[:, 1], flat[:, 2]
    )
    geodetic = np.column_stack((longitude, latitude, ellipsoid_height))
    center_lon = float((longitude.min() + longitude.max()) / 2)
    center_lat = float((latitude.min() + latitude.max()) / 2)
    center_height = float((ellipsoid_height.min() + ellipsoid_height.max()) / 2)

    to_ecef = Transformer.from_crs(WEB_CRS, ECEF_CRS, always_xy=True)
    x, y, z = to_ecef.transform(longitude, latitude, ellipsoid_height)
    center = np.asarray(to_ecef.transform(center_lon, center_lat, center_height))
    ecef = np.column_stack((x, y, z))

    lon_radians = math.radians(center_lon)
    lat_radians = math.radians(center_lat)
    east = np.asarray((-math.sin(lon_radians), math.cos(lon_radians), 0.0))
    north = np.asarray(
        (
            -math.sin(lat_radians) * math.cos(lon_radians),
            -math.sin(lat_radians) * math.sin(lon_radians),
            math.cos(lat_radians),
        )
    )
    up = np.asarray(
        (
            math.cos(lat_radians) * math.cos(lon_radians),
            math.cos(lat_radians) * math.sin(lon_radians),
            math.sin(lat_radians),
        )
    )
    basis = np.column_stack((east, north, up))
    local = (ecef - center) @ basis
    transform = [
        float(east[0]), float(east[1]), float(east[2]), 0.0,
        float(north[0]), float(north[1]), float(north[2]), 0.0,
        float(up[0]), float(up[1]), float(up[2]), 0.0,
        float(center[0]), float(center[1]), float(center[2]), 1.0,
    ]
    return local.reshape(-1, 3, 3), transform, (
        float(flat[:, 2].min()),
        float(flat[:, 2].max()),
        float(np.asarray(ellipsoid_height).min()),
        float(np.asarray(ellipsoid_height).max()),
    )


def _triangle_normals(local: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    oriented = local.copy()
    first = oriented[:, 1] - oriented[:, 0]
    second = oriented[:, 2] - oriented[:, 0]
    normals = np.cross(first, second)
    flip = normals[:, 2] < 0
    oriented[flip, 1], oriented[flip, 2] = (
        oriented[flip, 2].copy(),
        oriented[flip, 1].copy(),
    )
    first = oriented[:, 1] - oriented[:, 0]
    second = oriented[:, 2] - oriented[:, 0]
    normals = np.cross(first, second)
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-8
    if not valid.all():
        oriented = oriented[valid]
        normals = normals[valid]
        lengths = lengths[valid]
    normals /= lengths[:, None]
    return oriented, np.repeat(normals[:, None, :], 3, axis=1)


def _pad(value: bytes, *, byte: bytes) -> bytes:
    return value + byte * ((4 - len(value) % 4) % 4)


def _write_glb(path: Path, local: np.ndarray) -> dict[str, Any]:
    triangles, normal_triangles = _triangle_normals(local)
    # CityGML TIN repeats the same coordinates for adjacent triangles.  Keep
    # every source triangle but share identical vertices through a glTF index
    # buffer.  This is lossless geometry compaction: no resampling, smoothing,
    # interpolation, or elevation exaggeration is performed.
    flat_positions = np.ascontiguousarray(triangles.reshape(-1, 3), dtype=np.float64)
    unique_positions, inverse = np.unique(flat_positions, axis=0, return_inverse=True)
    positions = np.ascontiguousarray(unique_positions, dtype="<f4")
    indices = np.ascontiguousarray(inverse, dtype="<u4")
    face_normals = normal_triangles[:, 0, :]
    vertex_normals = np.zeros_like(unique_positions)
    np.add.at(vertex_normals, inverse, np.repeat(face_normals, 3, axis=0))
    normal_lengths = np.linalg.norm(vertex_normals, axis=1)
    normal_lengths[normal_lengths <= 1e-8] = 1
    normals = np.ascontiguousarray(vertex_normals / normal_lengths[:, None], dtype="<f4")
    position_bytes = positions.tobytes()
    normal_bytes = normals.tobytes()
    index_bytes = indices.tobytes()
    binary = _pad(position_bytes, byte=b"\x00") + _pad(normal_bytes, byte=b"\x00") + index_bytes
    minimum = positions.min(axis=0).tolist()
    maximum = positions.max(axis=0).tolist()
    document = {
        "asset": {"version": "2.0", "generator": "CITY GAP PLATEAU DEM TIN web tile"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "PLATEAU DEM 2025 · 常団地前 Deep Dive"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2, "material": 0, "mode": 4}]}],
        "materials": [{
            "name": "PLATEAU DEM neutral terrain",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.68, 0.72, 0.66, 0.72],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.92,
            },
            "doubleSided": True,
            "alphaMode": "BLEND",
        }],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(_pad(position_bytes, byte=b"\x00")), "byteLength": len(normal_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(_pad(position_bytes, byte=b"\x00")) + len(_pad(normal_bytes, byte=b"\x00")), "byteLength": len(index_bytes), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3", "min": minimum, "max": maximum},
            {"bufferView": 1, "componentType": 5126, "count": len(normals), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5125, "count": len(indices), "type": "SCALAR", "min": [0], "max": [len(indices) - 1]},
        ],
    }
    json_chunk = _pad(json.dumps(document, separators=(",", ":")).encode("utf-8"), byte=b" ")
    binary_chunk = _pad(binary, byte=b"\x00")
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    glb = (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(binary_chunk), b"BIN\x00")
        + binary_chunk
    )
    path.write_bytes(glb)
    return {
        "triangles": len(triangles),
        "vertices": len(positions),
        "source_vertex_references": int(len(flat_positions)),
        "indexed_without_resampling": True,
        "local_min": minimum,
        "local_max": maximum,
        "bytes": len(glb),
        "sha256": hashlib.sha256(glb).hexdigest(),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(
    archive: Path,
    output: Path,
    bounds: tuple[float, float, float, float],
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    triangles, members = _select_triangles(archive, bounds)
    local, transform, heights = _to_local_enu(triangles)
    glb_report = _write_glb(output / "terrain.glb", local)
    minimum = np.asarray(glb_report["local_min"], dtype=float)
    maximum = np.asarray(glb_report["local_max"], dtype=float)
    center = (minimum + maximum) / 2
    half = (maximum - minimum) / 2
    tileset = {
        "asset": {"version": "1.1", "tilesetVersion": "maizuru-dem-2025-deep-dive-v1"},
        "geometricError": 256,
        "root": {
            "boundingVolume": {"box": [
                float(center[0]), float(center[1]), float(center[2]),
                float(half[0]), 0, 0,
                0, float(half[1]), 0,
                0, 0, float(half[2]),
            ]},
            "transform": transform,
            "geometricError": 256,
            "refine": "REPLACE",
            "content": {"uri": "terrain.glb"},
        },
    }
    _write_json(output / "tileset.json", tileset)
    report = {
        "schema_version": "1.0.0",
        "dataset": "Project PLATEAU 舞鶴市2025 DEM TIN Deep Dive terrain",
        "theme": "dem",
        "source_crs": "EPSG:6697 (JGD2011 + JGD2011 gravity-related height)",
        "render_crs": "EPSG:4979/4978 (WGS84 ellipsoidal height/ECEF)",
        "vertical_transform": {
            "method": "PROJ inverse JGD2011 vertical grid transformation",
            "grid": GEOID_GRID,
            "grid_url": GEOID_GRID_URL,
            "interpolation_or_exaggeration": False,
        },
        "quality_boundary": {
            "kind": "verified Deep Dive region only",
            "mesh_code": "533513314",
            "area_label": "常団地前バス停周辺",
            "bounds_wgs84": bounds,
            "whole_city_terrain_claimed": False,
        },
        "source_archive": {
            "path": str(archive.relative_to(REPOSITORY_ROOT)),
            "bytes": archive.stat().st_size,
            "sha256": _sha256(archive),
            "members": members,
        },
        "source_triangles_selected": len(triangles),
        "rendered_triangles": glb_report["triangles"],
        "rendered_vertices": glb_report["vertices"],
        "orthometric_height_m": {"minimum": heights[0], "maximum": heights[1]},
        "ellipsoidal_height_m": {"minimum": heights[2], "maximum": heights[3]},
        "terrain_glb": glb_report,
    }
    _write_json(output / "metadata.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bounds", type=float, nargs=4, default=DEFAULT_BOUNDS)
    arguments = parser.parse_args()
    report = build(arguments.archive, arguments.output, tuple(arguments.bounds))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
