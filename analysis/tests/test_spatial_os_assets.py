import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend/public/data"


def test_real_plateau_dem_tile_preserves_quality_boundary() -> None:
    metadata = json.loads((PUBLIC / "plateau-terrain/metadata.json").read_text(encoding="utf-8"))
    tileset = json.loads((PUBLIC / "plateau-terrain/tileset.json").read_text(encoding="utf-8"))
    assert metadata["source_triangles_selected"] == metadata["rendered_triangles"] == 65_232
    assert metadata["terrain_glb"]["indexed_without_resampling"] is True
    assert metadata["vertical_transform"]["interpolation_or_exaggeration"] is False
    assert metadata["quality_boundary"]["whole_city_terrain_claimed"] is False
    assert metadata["terrain_glb"]["vertices"] < metadata["terrain_glb"]["source_vertex_references"]
    assert tileset["root"]["content"]["uri"] == "terrain.glb"
    assert (PUBLIC / "plateau-terrain/terrain.glb").stat().st_size == metadata["terrain_glb"]["bytes"]


def test_fast_start_is_official_lossless_b3dm() -> None:
    metadata = json.loads((PUBLIC / "plateau-fast/metadata.json").read_text(encoding="utf-8"))
    tile = PUBLIC / "plateau-fast/data/data287.b3dm"
    header = tile.read_bytes()[:28]
    magic, version, byte_length, *_ = struct.unpack("<4s6I", header)
    assert magic == b"b3dm" and version == 1 and byte_length == tile.stat().st_size
    assert metadata["batch_length"] == 15
    assert metadata["geometry_simplified"] is False
    assert metadata["height_estimated"] is False


def test_streaming_metadata_has_three_stage_buildings_and_real_terrain() -> None:
    metadata = json.loads((PUBLIC / "plateau_metadata.json").read_text(encoding="utf-8"))["streaming"]
    assert metadata["building_count"] == 44_640
    assert metadata["fast_start_tileset_url"].startswith("data/plateau-fast/")
    assert metadata["fallback_tileset_url"] == "data/plateau/tileset.json"
    assert metadata["building_tileset_url"].startswith("https://api.plateauview.mlit.go.jp/")
    assert metadata["local_dem_tileset_url"] == "data/plateau-terrain/tileset.json"
