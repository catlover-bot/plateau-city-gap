from __future__ import annotations

from backend.citygap_platform.domain.open_data import DiscoveryRequest
from backend.citygap_platform.open_data.static_catalog import StaticSectionCatalogAdapter


class FakeStaticClient:
    def validate_url(self, url: str) -> str:
        if not url.startswith(("https://city.example.test/", "https://portal.example.test/")):
            raise ValueError("not allowlisted")
        return url

    def get_bytes(self, url: str, *, max_bytes: int) -> tuple[bytes, dict[str, str]]:
        assert url == "https://city.example.test/open-data"
        payload = b"""<!doctype html><html><body>
        <h2>Before</h2><p>ignore</p><p><a href='/ignore'>ignore</a></p>
        <h2>Published datasets</h2>
        <p>Population and households</p>
        <p><a href='/population'>population page</a></p>
        <p>Evacuation facilities<br><a href='https://portal.example.test/shelters'>portal</a>
        <a href='https://portal.example.test/shelters'>duplicate label</a></p>
        <h2>Related links</h2><p><a href='/not-a-dataset'>related</a></p>
        </body></html>"""
        assert len(payload) < max_bytes
        return payload, {"last-modified": "Fri, 28 Aug 2026 00:00:00 GMT"}


def test_static_section_adapter_discovers_only_labelled_official_section() -> None:
    adapter = StaticSectionCatalogAdapter(
        catalog_url="https://city.example.test/open-data",
        municipality_code="14205",
        section_heading="Published datasets",
        stop_heading="Related links",
        client=FakeStaticClient(),  # type: ignore[arg-type]
    )
    resources = adapter.discover(DiscoveryRequest("14205", "藤沢市"))
    assert [item.title for item in resources] == [
        "Evacuation facilities",
        "Population and households",
    ]
    assert all(item.license_id == "unknown" for item in resources)
    assert all(item.source_metadata["availability"] == "requires_review" for item in resources)
    assert len({item.external_resource_id for item in resources}) == 2
