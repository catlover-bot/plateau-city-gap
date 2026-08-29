import json
from pathlib import Path

from analysis.scripts.build_spatial_evidence_pack import PACK_ID, build
from backend.citygap_platform.domain.spatial_evidence import assert_public_pack_safe


OUTPUT = Path("frontend/public/data/spatial-packs") / PACK_ID


def test_canonical_pack_reproduces_296_actual_buildings() -> None:
    first = build()
    first_manifest = (OUTPUT / "manifest.json").read_bytes()
    second = build()
    assert first["buildings"] == second["buildings"] == 296
    assert first["content_sha256"] == second["content_sha256"]
    assert (OUTPUT / "manifest.json").read_bytes() == first_manifest
    manifest = json.loads(first_manifest)
    assert manifest["objects"]["target_coverage_ratio"] == 1
    assert manifest["terrain_contract"]["elevation_exaggeration"] == 1
    assert manifest["section"]["terrain_samples_with_coverage"] > 0


def test_public_pack_has_no_per_building_population_model() -> None:
    if not (OUTPUT / "objects.json").exists():
        build()
    objects = json.loads((OUTPUT / "objects.json").read_text(encoding="utf-8"))["objects"]
    assert_public_pack_safe(objects)
    assert all("estimated_population" not in json.dumps(item) for item in objects)
