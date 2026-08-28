from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from backend.citygap_platform.domain.open_data import (
    DiscoveredResource,
    DiscoveryRequest,
    RawResourceReceipt,
)
from backend.citygap_platform.open_data.mhlw import MhlwCareAdapter, MhlwMedicalAdapter
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore


class FakeManifestClient:
    def __init__(self, html: str) -> None:
        self.html = html

    def validate_url(self, url: str) -> str:
        if not url.startswith("https://www.mhlw.go.jp/"):
            raise ValueError("not allowlisted")
        return url

    def get_bytes(self, url: str, *, max_bytes: int) -> tuple[bytes, dict[str, str]]:
        payload = self.html.encode()
        assert len(payload) <= max_bytes
        return payload, {"etag": '"manifest-v1"'}


def test_medical_manifest_discovers_only_newest_explicit_snapshot(tmp_path: Path) -> None:
    html = """
    <h3>2026年６月１日時点</h3>
    <a href="/content/11121000/01-1_hospital_facility_info_20260601.csv.zip">病院</a>
    <a href="/content/11121000/02-1_clinic_facility_info_20260601.csv.zip">診療所</a>
    <h3>2025年12月１日時点</h3>
    <a href="/content/11121000/01-1_hospital_facility_info_20251201.csv.zip">旧病院</a>
    """
    adapter = MhlwMedicalAdapter(
        client=FakeManifestClient(html),  # type: ignore[arg-type]
        object_store=ContentAddressedObjectStore(tmp_path),
    )
    resources = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))
    assert len(resources) == 2
    assert {item.reference_date for item in resources} == {"2026-06-01"}
    assert all("20251201" not in item.resource_url for item in resources)
    assert all(item.license_id == "pdl-1.0" for item in resources)
    assert all(item.source_metadata["resource_scope"] == "national" for item in resources)
    assert all(
        item.source_metadata["discovery_context_municipality_code"] == "26202"
        for item in resources
    )
    assert all(
        item.source_metadata["availability_semantics"].endswith("not real-time availability")
        for item in resources
    )


def test_medical_manifest_selects_newest_date_even_when_page_order_changes(tmp_path: Path) -> None:
    html = """
    <h3>2025年12月１日時点</h3>
    <a href="/content/11121000/01-1_hospital_facility_info_20251201.csv.zip">旧病院</a>
    <h3>2026年６月１日時点</h3>
    <a href="/content/11121000/01-1_hospital_facility_info_20260601.csv.zip">病院</a>
    """
    adapter = MhlwMedicalAdapter(
        client=FakeManifestClient(html),  # type: ignore[arg-type]
        object_store=ContentAddressedObjectStore(tmp_path),
    )

    resources = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))

    assert len(resources) == 1
    assert resources[0].reference_date == "2026-06-01"
    assert "20260601" in resources[0].resource_url


def test_care_manifest_preserves_official_service_codes_and_month_end(tmp_path: Path) -> None:
    html = """
    <h3>2026年６月末時点</h3>
    <a href="/content/12300000/jigyosho_110_all_20260709180319.csv">110_訪問介護</a>
    <a href="/content/12300000/jigyosho_780_all_20260709180927.csv">780_地域密着型通所介護</a>
    <h3>2025年12月末時点</h3>
    <a href="/content/12300000/jigyosho_110_all_20260114120000.csv">旧訪問介護</a>
    """
    adapter = MhlwCareAdapter(
        client=FakeManifestClient(html),  # type: ignore[arg-type]
        object_store=ContentAddressedObjectStore(tmp_path),
    )
    resources = adapter.discover(DiscoveryRequest("14205", "藤沢市"))
    assert {item.source_metadata["official_service_code"] for item in resources} == {
        "110",
        "780",
    }
    assert {item.reference_date for item in resources} == {"2026-06-30"}
    assert all(item.license_id == "cc-by-4.0" for item in resources)


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


def _resource(*, format: str = "ZIP") -> DiscoveredResource:
    suffix = "csv.zip" if format == "ZIP" else "csv"
    return DiscoveredResource(
        external_dataset_id="mhlw-test",
        external_resource_id=f"test.{suffix}",
        title="test",
        resource_url=f"https://www.mhlw.go.jp/content/test.{suffix}",
        format=format,
        license_id="pdl-1.0",
        reference_date="2026-06-01",
        version_signals=("2026-06-01",),
        source_metadata={},
    )


def test_mhlw_zip_schema_is_bounded_and_stream_normalization_preserves_raw_cells(
    tmp_path: Path,
) -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "medical.csv",
            "\ufeffID,正式名称,市区町村コード\r\n001,公式病院,202\r\n002,=要確認,205\r\n",
        )
    store = ContentAddressedObjectStore(tmp_path)
    receipt = _stored_receipt(store, payload.getvalue(), "application/zip")
    adapter = MhlwMedicalAdapter(
        client=FakeManifestClient(""),  # type: ignore[arg-type]
        object_store=store,
    )
    resource = _resource()
    inspection = adapter.inspect_schema(resource, receipt)
    assert inspection.field_names == ("ID", "正式名称", "市区町村コード")
    assert inspection.row_count == 2
    formula_gate = next(
        item for item in inspection.quality_results if item["gate"] == "formula_injection_boundary"
    )
    assert formula_gate["formula_like_cells"] == 1
    rows = list(adapter.normalize(resource, receipt, inspection))
    assert rows[1]["values"]["正式名称"] == "=要確認"


def test_mhlw_archive_rejects_traversal_member(tmp_path: Path) -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../outside.csv", "ID,正式名称\n001,test\n")
    store = ContentAddressedObjectStore(tmp_path)
    receipt = _stored_receipt(store, payload.getvalue(), "application/zip")
    adapter = MhlwMedicalAdapter(
        client=FakeManifestClient(""),  # type: ignore[arg-type]
        object_store=store,
    )
    with pytest.raises(ValueError, match="unsafe member"):
        adapter.inspect_schema(_resource(), receipt)


def test_direct_care_csv_uses_same_bounded_schema_contract(tmp_path: Path) -> None:
    payload = (
        "\ufeff都道府県コード又は市町村コード,事業所番号,事業所名\r\n"
        "262021,2670000001,舞鶴介護事業所\r\n"
    ).encode()
    store = ContentAddressedObjectStore(tmp_path)
    receipt = _stored_receipt(store, payload, "text/csv")
    adapter = MhlwCareAdapter(
        client=FakeManifestClient(""),  # type: ignore[arg-type]
        object_store=store,
    )
    inspection = adapter.inspect_schema(_resource(format="CSV"), receipt)
    assert inspection.row_count == 1
    row = next(adapter.normalize(_resource(format="CSV"), receipt, inspection))
    assert row["values"]["事業所番号"] == "2670000001"
