from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.citygap_platform.domain.open_data import DiscoveryRequest
from backend.citygap_platform.open_data.ckan import CkanCatalogAdapter
from backend.citygap_platform.open_data.http import DownloadResult, validate_public_https_url
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore


def public_resolver(*args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
    return [(2, 1, 6, "", ("8.8.8.8", 443))]


@pytest.mark.parametrize(
    "url",
    (
        "http://data.example.test/resource.csv",
        "https://user:secret@data.example.test/resource.csv",
        "https://other.example.test/resource.csv",
        "https://data.example.test:8443/resource.csv",
    ),
)
def test_external_url_policy_rejects_unsafe_endpoint_variants(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_https_url(
            url, allowed_hosts={"data.example.test"}, resolver=public_resolver
        )


def test_external_url_policy_rejects_private_dns_answers() -> None:
    def private_resolver(*args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    with pytest.raises(ValueError, match="non-public"):
        validate_public_https_url(
            "https://data.example.test/resource.csv",
            allowed_hosts={"data.example.test"},
            resolver=private_resolver,
        )


def test_external_url_policy_accepts_allowlisted_public_https() -> None:
    url = "https://data.example.test/resource.csv"
    assert (
        validate_public_https_url(
            url, allowed_hosts={"data.example.test"}, resolver=public_resolver
        )
        == url
    )


class FakeCkanClient:
    def validate_url(self, url: str) -> str:
        if not url.startswith("https://data.example.test/"):
            raise ValueError("not allowlisted")
        return url

    def get_json(self, url: str) -> dict[str, Any]:
        assert "organization%3A262021" in url
        return {
            "success": True,
            "result": {
                "count": 1,
                "results": [
                    {
                        "id": "package-uuid",
                        "name": "262021_hospital",
                        "title": "医療機関一覧",
                        "notes": "official",
                        "license_id": "cc-by-40-intl",
                        "license_title": "Creative Commons Attribution 4.0",
                        "metadata_modified": "2026-08-04T02:46:04",
                        "resources": [
                            {
                                "id": "resource-uuid",
                                "name": "医療機関一覧",
                                "url": "https://data.example.test/hospital.csv",
                                "format": "CSV",
                                "last_modified": "2026-08-04T02:45:00",
                                "size": 21472,
                            }
                        ],
                    }
                ],
            },
        }


def test_ckan_discovery_preserves_identity_license_and_version_signals(tmp_path: Path) -> None:
    adapter = CkanCatalogAdapter(
        api_url="https://data.example.test/api/3/action/package_search",
        organization_id="262021",
        municipality_code="26202",
        client=FakeCkanClient(),  # type: ignore[arg-type]
        object_store=ContentAddressedObjectStore(tmp_path),
    )
    resources = adapter.discover(DiscoveryRequest("26202", "舞鶴市"))
    assert len(resources) == 1
    resource = resources[0]
    assert resource.external_dataset_id == "262021_hospital"
    assert resource.external_resource_id == "resource-uuid"
    assert resource.license_id == "cc-by-4.0"
    assert resource.reference_date is None
    assert resource.source_metadata["source_license_id"] == "cc-by-40-intl"
    assert resource.version_signals == (
        "2026-08-04T02:46:04",
        "2026-08-04T02:45:00",
    )


class FakeDownloadClient:
    def download_to(self, url: str, destination: Path, *, max_bytes: int) -> DownloadResult:
        payload = b"official-resource"
        assert max_bytes >= len(payload)
        destination.write_bytes(payload)
        return DownloadResult(
            sha256="df7d0849539e85d2bcd5113121795f134a1c3e2b707e911923093cdc8f8d69a6",
            size_bytes=len(payload),
            content_type="text/csv",
            etag=None,
            last_modified=None,
            final_url=url,
        )


def test_object_store_deduplicates_by_sha_and_rejects_path_escape(tmp_path: Path) -> None:
    store = ContentAddressedObjectStore(tmp_path)
    first = store.fetch(
        FakeDownloadClient(),  # type: ignore[arg-type]
        "https://data.example.test/resource.csv",
        max_bytes=1024,
    )
    second = store.fetch(
        FakeDownloadClient(),  # type: ignore[arg-type]
        "https://data.example.test/resource.csv",
        max_bytes=1024,
    )
    assert first.sha256 == second.sha256
    assert store.path_for_key(first.object_key).read_bytes() == b"official-resource"
    with pytest.raises(ValueError, match="escapes"):
        store.path_for_key("../outside")
