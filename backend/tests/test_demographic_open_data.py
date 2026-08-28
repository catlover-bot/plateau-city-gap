from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from backend.citygap_platform.domain.open_data import (
    DiscoveredResource,
    DiscoveryRequest,
    RawResourceReceipt,
)
from backend.citygap_platform.open_data.demographics import (
    EStatEconomicCensusAdapter,
    MlitFuturePopulationAdapter,
)
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore


class FakeOfficialClient:
    def __init__(self, *, mlit_html: str = "", estat_detail: str = "") -> None:
        self.mlit_html = mlit_html
        self.estat_detail = estat_detail

    def validate_url(self, url: str) -> str:
        if not url.startswith(("https://nlftp.mlit.go.jp/", "https://www.e-stat.go.jp/")):
            raise ValueError("not allowlisted")
        return url

    def get_bytes(self, url: str, *, max_bytes: int) -> tuple[bytes, dict[str, str]]:
        if url.startswith("https://nlftp.mlit.go.jp/"):
            payload = self.mlit_html.encode()
        else:
            payload = json.dumps({"detail": self.estat_detail}).encode()
        assert len(payload) <= max_bytes
        return payload, {"etag": '"manifest-v1"', "last-modified": "current"}


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


def _resource(resource_id: str) -> DiscoveredResource:
    return DiscoveredResource(
        external_dataset_id="official-test",
        external_resource_id=resource_id,
        title="test",
        resource_url=f"https://www.e-stat.go.jp/{resource_id}",
        format="ZIP",
        license_id="government-standard-terms-2.0",
        reference_date="2021-06-01",
        version_signals=("test",),
        source_metadata={},
    )


def test_future_population_discovers_latest_prefectural_geojson(tmp_path: Path) -> None:
    manifest = """
    <a onclick="DownLd('10MB', '250m_mesh_2023_26_GEOJSON.zip',
      '../data/old.zip')">old</a>
    <a onclick="DownLd('16MB', '250m_mesh_2024_26_GEOJSON.zip',
      '../data/250m_mesh_2024_26_GEOJSON.zip')">current</a>
    <a onclick="DownLd('30MB', '250m_mesh_2024_14_GEOJSON.zip',
      '../data/250m_mesh_2024_14_GEOJSON.zip')">other prefecture</a>
    """
    adapter = MlitFuturePopulationAdapter(
        client=FakeOfficialClient(mlit_html=manifest),  # type: ignore[arg-type]
        object_store=ContentAddressedObjectStore(tmp_path),
    )

    resource = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))[0]

    assert resource.external_resource_id == "250m_mesh_2024_26_GEOJSON.zip"
    assert resource.license_id == "cc-by-4.0"
    assert resource.reference_date == "2020-10-01"
    assert resource.source_metadata["projection_years"] == list(range(2025, 2071, 5))
    assert resource.source_metadata["resource_scope"].startswith("prefectural_extract")
    assert len(resource.source_metadata["selected_resource_fingerprint"]) == 64


def test_future_population_geojson_schema_and_normalization(tmp_path: Path) -> None:
    feature_collection = {
        "type": "FeatureCollection",
        "name": "future_population",
        "crs": {"type": "name", "properties": {"name": "EPSG:6668"}},
        "features": [
            {
                "type": "Feature",
                "properties": {"MESH_ID": "5335700011", "PTN_2025": 12.0},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[135.0, 35.0], [135.01, 35.0], [135.01, 35.01], [135.0, 35.0]]
                    ],
                },
            }
        ],
    }
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("future.geojson", json.dumps(feature_collection))
    store = ContentAddressedObjectStore(tmp_path)
    receipt = _stored_receipt(store, payload.getvalue(), "application/zip")
    adapter = MlitFuturePopulationAdapter(
        client=FakeOfficialClient(),  # type: ignore[arg-type]
        object_store=store,
    )
    resource = _resource("future.zip")

    inspection = adapter.inspect_schema(resource, receipt)
    rows = list(adapter.normalize(resource, receipt, inspection))

    assert inspection.field_names == ("MESH_ID", "PTN_2025")
    assert inspection.row_count == 1
    assert inspection.source_crs == "EPSG:6668"
    assert rows[0]["values"] == {"MESH_ID": "5335700011", "PTN_2025": 12.0}
    assert rows[0]["geometry"]["type"] == "Polygon"


def test_estat_discovers_exact_prefecture_resource_and_release(tmp_path: Path) -> None:
    detail = """
    <article class="stat-resorce_list-item">
      <a href="/gis/statmap-search/data?statsId=T001162&amp;code=26&amp;downloadType=2">
        京都府
      </a>
      <li class="align-center-data">2025-10-09</li>
    </article>
    """
    adapter = EStatEconomicCensusAdapter(
        client=FakeOfficialClient(estat_detail=detail),  # type: ignore[arg-type]
        object_store=ContentAddressedObjectStore(tmp_path),
    )

    resource = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))[0]

    assert resource.external_resource_id == "tblT001162H26.zip"
    assert resource.resource_url.endswith("statsId=T001162&code=26&downloadType=2")
    assert resource.license_id == "government-standard-terms-2.0"
    assert resource.reference_date == "2021-06-01"
    assert resource.source_metadata["release_date"] == "2025-10-09"
    assert len(resource.source_metadata["selected_resource_fingerprint"]) == 64
    assert resource.version_signals[2].endswith("code=26&downloadType=2")


def test_estat_cp932_schema_preserves_suppression_and_formula_cells(tmp_path: Path) -> None:
    text = (
        "KEY_CODE,事業所数,従業者数\r\n"
        ",Ａ～Ｓ全産業,Ａ～Ｓ全産業\r\n"
        "533570001,12,X\r\n"
        "533570002,=確認,4\r\n"
    )
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("tblT001162H26.txt", text.encode("cp932"))
    store = ContentAddressedObjectStore(tmp_path)
    receipt = _stored_receipt(store, payload.getvalue(), "application/zip")
    adapter = EStatEconomicCensusAdapter(
        client=FakeOfficialClient(),  # type: ignore[arg-type]
        object_store=store,
    )
    resource = _resource("tblT001162H26.zip")

    inspection = adapter.inspect_schema(resource, receipt)
    rows = list(adapter.normalize(resource, receipt, inspection))

    assert inspection.encoding == "cp932"
    assert inspection.row_count == 2
    label_gate = next(
        item for item in inspection.quality_results if item["gate"] == "official_label_row"
    )
    assert label_gate["rows"] == 1
    assert rows[0]["values"]["従業者数"] == "X"
    formula_gate = next(
        item for item in inspection.quality_results if item["gate"] == "formula_injection_boundary"
    )
    assert formula_gate["formula_like_cells"] == 1


def test_estat_archive_rejects_traversal_member(tmp_path: Path) -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../tbl.txt", "KEY_CODE,value\n1,2\n")
    store = ContentAddressedObjectStore(tmp_path)
    receipt = _stored_receipt(store, payload.getvalue(), "application/zip")
    adapter = EStatEconomicCensusAdapter(
        client=FakeOfficialClient(),  # type: ignore[arg-type]
        object_store=store,
    )

    with pytest.raises(ValueError, match="unsafe member"):
        adapter.inspect_schema(_resource("tbl.zip"), receipt)
