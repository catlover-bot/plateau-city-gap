from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from analysis.src.mesh import decode_250m_mesh
from backend.citygap_platform.domain.open_data import (
    DiscoveredResource,
    DiscoveryRequest,
    RawResourceReceipt,
)
from backend.citygap_platform.open_data.resilience import (
    JSHIS_FIELDS,
    NPA_FIELDS,
    JShisSurfaceGroundAdapter,
    NpaTrafficAccidentAdapter,
    npa_dms_to_decimal,
)
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore


class FakeOfficialClient:
    def __init__(self, payloads: dict[str, bytes] | None = None) -> None:
        self.payloads = payloads or {}

    def validate_url(self, url: str) -> str:
        if not url.startswith(
            ("https://www.j-shis.bosai.go.jp/", "https://www.npa.go.jp/")
        ):
            raise ValueError("not allowlisted")
        return url

    def get_bytes(self, url: str, *, max_bytes: int) -> tuple[bytes, dict[str, str]]:
        payload = self.payloads[url]
        assert len(payload) <= max_bytes
        return payload, {"etag": '"official-v1"'}


def _stored_receipt(
    store: ContentAddressedObjectStore, payload: bytes, content_type: str
) -> RawResourceReceipt:
    digest = hashlib.sha256(payload).hexdigest()
    object_key = f"sha256/{digest[:2]}/{digest}"
    path = store.path_for_key(object_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return RawResourceReceipt(
        digest, len(payload), content_type, object_key, "2026-08-28T00:00:00Z"
    )


def _jshis_resource() -> DiscoveredResource:
    return DiscoveredResource(
        external_dataset_id="jshis-2020-surface-ground-v4-250m",
        external_resource_id="Z-V4-JAPAN-AMP-VS400_M250-5335.zip",
        title="test",
        resource_url=(
            "https://www.j-shis.bosai.go.jp/map/JSHIS2/data/Z/V4/JAPAN/AMP/"
            "VS400_M250/Z-V4-JAPAN-AMP-VS400_M250-5335.zip"
        ),
        format="ZIP",
        license_id="jshis-terms-2025-03",
        reference_date="2020-01-01",
        version_signals=("V4",),
        source_metadata={"first_mesh": "5335"},
    )


def _jshis_zip(rows: str, *, name: str = "surface.csv") -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            name,
            "#\n# VER. = 1.0\n# DATE = 2022-05-30\n#\n"
            "# CODE, JCODE, AVS, ARV, AVS_EB, AVS_REF\n"
            + rows,
        )
    return payload.getvalue()


def test_250m_mesh_decode_stays_inside_parent_500m() -> None:
    south_west = decode_250m_mesh("5335000011")
    north_east = decode_250m_mesh("5335000014")
    assert south_west.south < north_east.south
    assert south_west.west < north_east.west
    assert south_west.north == north_east.south
    assert south_west.east == north_east.west
    with pytest.raises(ValueError, match="250 m"):
        decode_250m_mesh("5335000019")


def test_jshis_discovery_is_deterministic_and_requires_reviewed_first_mesh(
    tmp_path: Path,
) -> None:
    adapter = JShisSurfaceGroundAdapter(
        client=FakeOfficialClient(),  # type: ignore[arg-type]
        object_store=ContentAddressedObjectStore(tmp_path),
        first_mesh_by_municipality={"26202": "5335"},
    )
    resource = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))[0]
    assert resource.external_resource_id.endswith("-5335.zip")
    assert resource.source_metadata["source_epsg"] == 4612
    assert resource.source_metadata["raw_redistribution"] is False
    with pytest.raises(ValueError, match="reviewed"):
        adapter.discover(DiscoveryRequest("14205", "藤沢市"))


def test_jshis_schema_and_normalization_keep_coastal_zero_as_not_ground(
    tmp_path: Path,
) -> None:
    store = ContentAddressedObjectStore(tmp_path)
    receipt = _stored_receipt(
        store,
        _jshis_zip("5335000011, 0,0.0,0.0,-,0\n5335000012,10,367.4,1.0752,-,0\n"),
        "application/zip",
    )
    adapter = JShisSurfaceGroundAdapter(
        client=FakeOfficialClient(),  # type: ignore[arg-type]
        object_store=store,
        first_mesh_by_municipality={"26202": "5335"},
    )
    resource = _jshis_resource()
    inspection = adapter.inspect_schema(resource, receipt)
    assert inspection.field_names == JSHIS_FIELDS
    assert inspection.source_crs == "EPSG:4612"
    assert inspection.row_count == 2
    coastal, ground = list(adapter.normalize(resource, receipt, inspection))
    assert coastal["average_shear_wave_velocity_m_s"] is None
    assert coastal["amplification_ratio"] is None
    assert coastal["source_encoded_values"] == {"AVS": 0.0, "ARV": 0.0}
    assert coastal["value_status"] == "coastal_water_not_ground"
    assert ground["average_shear_wave_velocity_m_s"] == 367.4
    assert ground["value_status"] == "modeled"


def test_jshis_rejects_archive_traversal_and_formula_content(tmp_path: Path) -> None:
    store = ContentAddressedObjectStore(tmp_path)
    adapter = JShisSurfaceGroundAdapter(
        client=FakeOfficialClient(),  # type: ignore[arg-type]
        object_store=store,
        first_mesh_by_municipality={"26202": "5335"},
    )
    traversal = _stored_receipt(
        store,
        _jshis_zip("5335000011,10,367.4,1.0,-,0\n", name="../surface.csv"),
        "application/zip",
    )
    with pytest.raises(ValueError, match="unsafe member"):
        adapter.inspect_schema(_jshis_resource(), traversal)
    formula = _stored_receipt(
        store,
        _jshis_zip("5335000011,10,=367.4,1.0,-,0\n"),
        "application/zip",
    )
    with pytest.raises(ValueError, match="formula-like"):
        adapter.inspect_schema(_jshis_resource(), formula)


def test_npa_discovery_selects_latest_annual_main_and_supporting_workbooks(
    tmp_path: Path,
) -> None:
    index_url = NpaTrafficAccidentAdapter.index_url
    annual_url = (
        "https://www.npa.go.jp/publications/statistics/koutsuu/opendata/2024/"
        "opendata_2024.html"
    )
    payloads = {
        index_url: (
            b'<a href="2023/opendata_2023.html">2023</a>'
            b'<a href="2024/opendata_2024.html">2024</a>'
        ),
        annual_url: (
            b'<a href="honhyo_2024.csv">main</a>'
            b'<a href="fileteigisyo_2024.xlsx">schema</a>'
            b'<a href="codebook_2024.xlsx">codebook</a>'
        ),
    }
    adapter = NpaTrafficAccidentAdapter(
        client=FakeOfficialClient(payloads),  # type: ignore[arg-type]
        object_store=ContentAddressedObjectStore(tmp_path),
    )
    resource = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))[0]
    assert resource.external_dataset_id == "npa-traffic-accident-2024-main"
    assert resource.resource_url.endswith("/2024/honhyo_2024.csv")
    assert resource.source_metadata["schema_url"].endswith("fileteigisyo_2024.xlsx")
    assert resource.source_metadata["codebook_url"].endswith("codebook_2024.xlsx")


def _npa_csv(*, formula: bool = False) -> bytes:
    row = dict.fromkeys(NPA_FIELDS, "0")
    row.update(
        {
            "都道府県コード": "61",
            "警察署等コード": "123",
            "本票番号": "0001",
            "市区町村コード": "202",
            "発生日時　　年": "2023",
            "発生日時　　月": "12",
            "発生日時　　日": "27",
            "発生日時　　時": "15",
            "発生日時　　分": "42",
            "死者数": "000",
            "負傷者数": "001",
            "地点　緯度（北緯）": "352700000",
            "地点　経度（東経）": "1352000000",
            "天候": "=2" if formula else "2",
        }
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=NPA_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerow(row)
    return stream.getvalue().encode("cp932")


def _npa_resource() -> DiscoveredResource:
    return DiscoveredResource(
        external_dataset_id="npa-traffic-accident-2024-main",
        external_resource_id="honhyo_2024.csv",
        title="test",
        resource_url=(
            "https://www.npa.go.jp/publications/statistics/koutsuu/opendata/2024/"
            "honhyo_2024.csv"
        ),
        format="CSV",
        license_id="pdl-1.0",
        reference_date="2024-12-31",
        version_signals=("2024",),
        source_metadata={"annual_file_year": 2024},
    )


def test_npa_stream_contract_preserves_occurrence_year_separate_from_file_year(
    tmp_path: Path,
) -> None:
    store = ContentAddressedObjectStore(tmp_path)
    receipt = _stored_receipt(store, _npa_csv(), "text/csv")
    adapter = NpaTrafficAccidentAdapter(
        client=FakeOfficialClient(),  # type: ignore[arg-type]
        object_store=store,
    )
    resource = _npa_resource()
    inspection = adapter.inspect_schema(resource, receipt)
    assert inspection.row_count == 1
    assert inspection.field_names == NPA_FIELDS
    row = next(adapter.normalize(resource, receipt, inspection))
    assert row["annual_file_year"] == 2024
    assert row["occurred_at"] == "2023-12-27T15:42+09:00"
    assert row["prefecture_code_npa"] == "61"
    assert row["municipality_code_npa"] == "202"
    assert row["injuries"] == 1
    assert row["scope"].startswith("historical")


def test_npa_rejects_formula_content_and_invalid_dms(tmp_path: Path) -> None:
    store = ContentAddressedObjectStore(tmp_path)
    adapter = NpaTrafficAccidentAdapter(
        client=FakeOfficialClient(),  # type: ignore[arg-type]
        object_store=store,
    )
    receipt = _stored_receipt(store, _npa_csv(formula=True), "text/csv")
    with pytest.raises(ValueError, match="formula-like"):
        adapter.inspect_schema(_npa_resource(), receipt)
    with pytest.raises(ValueError, match="fixed-width"):
        npa_dms_to_decimal("35270000", longitude=False)
    with pytest.raises(ValueError, match="minute or second"):
        npa_dms_to_decimal("356100000", longitude=False)
