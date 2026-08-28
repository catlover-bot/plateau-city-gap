from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.citygap_platform.ingestion.critical_facilities import OfficialShelterAdapter


@pytest.mark.parametrize(
    ("city_code", "path", "expected_hash", "count", "facility_type"),
    (
        (
            "26202",
            "data/raw/plateau_related/26202_maizuru-shi_city_2025_shelter.geojson",
            "faa9e4523f1f268cc833d0a8a78da841d6b6e37be0525bb315a3683750e8bcdd",
            126,
            "地域避難所",
        ),
        (
            "14205",
            "data/raw/plateau_related_fujisawa/14205_fujisawa-shi_city_2025_shelter.geojson",
            "d06294e9a72739a574a21b0b1fd12086d03b279043342f4c86f80dd6b60a6124",
            81,
            "避難所",
        ),
    ),
)
def test_real_official_shelter_sources_are_bounded_and_never_infer_capacity(
    city_code: str,
    path: str,
    expected_hash: str,
    count: int,
    facility_type: str,
) -> None:
    source = Path(path)
    if not source.exists():
        pytest.skip("EXPECTED_EXTERNAL: ignored official shelter source is not present")
    adapter = OfficialShelterAdapter(
        source,
        city_code=city_code,
        source_year=2025,
        source_url=f"https://www.geospatial.jp/ckan/dataset/plateau-{city_code}",
        expected_sha256=expected_hash,
    )
    records = adapter.records()
    inspection = adapter.inspect()
    assert len(records) == count
    assert facility_type in inspection.facility_types
    assert inspection.capacity_available_count + inspection.capacity_missing_count == count
    assert all(record.source_verified for record in records)


def test_shelter_adapter_rejects_unregistered_capacity_instead_of_guessing(tmp_path: Path) -> None:
    source = tmp_path / "shelter.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [135.3, 35.4]},
                        "properties": {
                            "名称": "test",
                            "住所": "address",
                            "施設の種類": "避難所",
                            "収容人数": "about 100",
                            "対象とする災害の分類": "水害",
                            "行政区域": "26202",
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    adapter = OfficialShelterAdapter(
        source,
        city_code="26202",
        source_year=2025,
        source_url="https://example.invalid/official",
        expected_sha256=digest,
    )
    with pytest.raises(ValueError, match="official non-negative integer"):
        adapter.records()
