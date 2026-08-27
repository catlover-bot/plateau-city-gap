"""Build a fast first-frame PLATEAU building tile without changing geometry.

The official Deep Dive subset is Draco-compressed, which is efficient for
delivery but can delay the first visible building on low-power devices.  This
pipeline extracts one verified official b3dm leaf, losslessly decompresses its
embedded glTF, and re-wraps it with the original feature and batch tables.
The full bundled subset and official all-city camera stream remain the sources
of record after this first-frame tile is replaced.

Requires the pinned glTF-Transform CLI used by frontend development:
``frontend/node_modules/.bin/gltf-transform``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_TILESET = REPOSITORY_ROOT / "frontend/public/data/plateau/tileset.json"
DEFAULT_SOURCE_B3DM = REPOSITORY_ROOT / "frontend/public/data/plateau/data/data287.b3dm"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "frontend/public/data/plateau-fast"
DEFAULT_DECOMPRESSOR = REPOSITORY_ROOT / "frontend/scripts/decompress-gltf.mjs"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _parse_b3dm(value: bytes) -> tuple[tuple[bytes, bytes, bytes, bytes], bytes, int]:
    if len(value) < 28 or value[:4] != b"b3dm":
        raise ValueError("Source is not a b3dm 1.0 tile")
    version, byte_length, ft_json_length, ft_bin_length, bt_json_length, bt_bin_length = struct.unpack_from("<6I", value, 4)
    if version != 1 or byte_length != len(value):
        raise ValueError("Invalid b3dm header")
    offset = 28
    blocks: list[bytes] = []
    for length in (ft_json_length, ft_bin_length, bt_json_length, bt_bin_length):
        blocks.append(value[offset:offset + length])
        offset += length
    feature_table = json.loads(blocks[0].decode("utf-8"))
    batch_length = int(feature_table["BATCH_LENGTH"])
    glb = value[offset:]
    if glb[:4] != b"glTF":
        raise ValueError("b3dm does not contain an embedded binary glTF")
    return (blocks[0], blocks[1], blocks[2], blocks[3]), glb, batch_length


def _wrap_b3dm(blocks: tuple[bytes, bytes, bytes, bytes], glb: bytes) -> bytes:
    byte_length = 28 + sum(map(len, blocks)) + len(glb)
    header = struct.pack("<4s6I", b"b3dm", 1, byte_length, *(len(block) for block in blocks))
    return header + b"".join(blocks) + glb


def _content_region(tileset: dict[str, Any], uri: str) -> list[float]:
    queue = [tileset["root"]]
    while queue:
        tile = queue.pop()
        if tile.get("content", {}).get("uri") == uri:
            return tile["boundingVolume"]["region"]
        queue.extend(tile.get("children", []))
    raise ValueError(f"Verified source tile is absent from tileset: {uri}")


def build(source_tileset: Path, source_b3dm: Path, output: Path, decompressor: Path) -> dict[str, Any]:
    for required in (source_tileset, source_b3dm, decompressor):
        if not required.is_file():
            raise FileNotFoundError(required)
    original = source_b3dm.read_bytes()
    blocks, compressed_glb, batch_length = _parse_b3dm(original)
    with tempfile.TemporaryDirectory(prefix="city-gap-plateau-fast-") as raw_temp:
        temp = Path(raw_temp)
        compressed_path = temp / "compressed.glb"
        decompressed_path = temp / "decompressed.glb"
        compressed_path.write_bytes(compressed_glb)
        subprocess.run(
            ["node", str(decompressor), str(compressed_path), str(decompressed_path)],
            check=True,
            cwd=REPOSITORY_ROOT / "frontend",
        )
        decompressed_glb = decompressed_path.read_bytes()
    if b"KHR_draco_mesh_compression" in decompressed_glb:
        raise ValueError("Draco extension remains after lossless decompression")
    fast_b3dm = _wrap_b3dm(blocks, decompressed_glb)
    relative_uri = f"data/{source_b3dm.name}"
    region = _content_region(json.loads(source_tileset.read_text(encoding="utf-8")), relative_uri)
    output_data = output / "data"
    output_data.mkdir(parents=True, exist_ok=True)
    (output_data / source_b3dm.name).write_bytes(fast_b3dm)
    tileset = {
        "asset": {"version": "1.0", "tilesetVersion": "maizuru-fast-start-v2"},
        "geometricError": 64,
        "root": {
            "boundingVolume": {"region": region},
            "geometricError": 64,
            "refine": "REPLACE",
            "content": {"uri": f"{relative_uri}?v=maizuru-fast-start-v2"},
        },
    }
    metadata = {
        "schema_version": "1.0.0",
        "purpose": "first visible PLATEAU LOD1 buildings before full Deep Dive/all-city stream",
        "source": str(source_b3dm.relative_to(REPOSITORY_ROOT)),
        "source_format": "official Project PLATEAU b3dm; embedded glTF Draco decoded losslessly",
        "geometry_simplified": False,
        "height_estimated": False,
        "batch_length": batch_length,
        "compressed_bytes": len(original),
        "decompressed_bytes": len(fast_b3dm),
        "source_sha256": _sha256(original),
        "output_sha256": _sha256(fast_b3dm),
    }
    (output / "tileset.json").write_bytes(_json_bytes(tileset))
    (output / "metadata.json").write_bytes(_json_bytes(metadata))
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tileset", type=Path, default=DEFAULT_SOURCE_TILESET)
    parser.add_argument("--source-b3dm", type=Path, default=DEFAULT_SOURCE_B3DM)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--decompressor", type=Path, default=DEFAULT_DECOMPRESSOR)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.source_tileset, arguments.source_b3dm, arguments.output, arguments.decompressor), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
