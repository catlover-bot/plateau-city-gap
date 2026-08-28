"""Generic discovery for an official HTML section containing labelled resource links."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

from backend.citygap_platform.domain.open_data import (
    DiscoveredResource,
    DiscoveryRequest,
    OpenDataAdapterDefinition,
    RawResourceReceipt,
    SchemaInspection,
)
from backend.citygap_platform.open_data.http import SafeHttpClient
from backend.citygap_platform.open_data.registry import OFFICIAL_SOURCE_REGISTRY


@dataclass(frozen=True, slots=True)
class CatalogLink:
    label: str
    url: str


class _SectionLinkParser(HTMLParser):
    def __init__(self, *, base_url: str, section_heading: str, stop_heading: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.section_heading = section_heading
        self.stop_heading = stop_heading
        self.in_target = False
        self.current_tag: str | None = None
        self.current_text: list[str] = []
        self.current_plain_text: list[str] = []
        self.current_links: list[str] = []
        self.in_anchor = False
        self.pending_label: str | None = None
        self.links: list[CatalogLink] = []

    @staticmethod
    def _clean(parts: list[str]) -> str:
        return " ".join("".join(parts).replace("\u3000", " ").split()).lstrip("・")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h2", "p"}:
            self.current_tag = tag
            self.current_text = []
            self.current_plain_text = []
            self.current_links = []
        elif tag == "a" and self.current_tag == "p":
            self.in_anchor = True
            href = dict(attrs).get("href")
            if href:
                self.current_links.append(urljoin(self.base_url, href))

    def handle_data(self, data: str) -> None:
        if self.current_tag is not None:
            self.current_text.append(data)
            if not self.in_anchor:
                self.current_plain_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.in_anchor = False
            return
        if tag != self.current_tag:
            return
        text = self._clean(self.current_text)
        plain_text = self._clean(self.current_plain_text)
        if tag == "h2":
            if text == self.section_heading:
                self.in_target = True
            elif self.in_target and text == self.stop_heading:
                self.in_target = False
        elif self.in_target and tag == "p":
            unique_links = tuple(dict.fromkeys(self.current_links))
            if unique_links:
                label = self.pending_label or plain_text or text
                for link in unique_links:
                    self.links.append(CatalogLink(label=label, url=link))
                self.pending_label = None
            elif text:
                self.pending_label = text
        self.current_tag = None
        self.current_text = []
        self.current_plain_text = []
        self.current_links = []


class StaticSectionCatalogAdapter:
    definition: OpenDataAdapterDefinition = OFFICIAL_SOURCE_REGISTRY.adapter(
        "official-static-catalog@1"
    )

    def __init__(
        self,
        *,
        catalog_url: str,
        municipality_code: str,
        section_heading: str,
        stop_heading: str,
        client: SafeHttpClient,
    ) -> None:
        if not municipality_code.isdigit() or len(municipality_code) != 5:
            raise ValueError("A five-digit municipality code is required")
        self.catalog_url = client.validate_url(catalog_url)
        self.municipality_code = municipality_code
        self.section_heading = section_heading
        self.stop_heading = stop_heading
        self.client = client

    def discover(self, request: DiscoveryRequest) -> tuple[DiscoveredResource, ...]:
        if request.municipality_code != self.municipality_code:
            raise ValueError("Discovery request municipality does not match adapter scope")
        payload, headers = self.client.get_bytes(self.catalog_url, max_bytes=8 * 1024 * 1024)
        parser = _SectionLinkParser(
            base_url=self.catalog_url,
            section_heading=self.section_heading,
            stop_heading=self.stop_heading,
        )
        parser.feed(payload.decode("utf-8", errors="strict"))
        catalog_sha256 = hashlib.sha256(payload).hexdigest()
        resources: list[DiscoveredResource] = []
        for link in parser.links:
            resource_url = self.client.validate_url(link.url)
            identity = hashlib.sha256(resource_url.encode()).hexdigest()[:24]
            resources.append(
                DiscoveredResource(
                    external_dataset_id=f"static-{identity}",
                    external_resource_id=identity,
                    title=link.label,
                    resource_url=resource_url,
                    format="HTML_OR_PORTAL",
                    license_id="unknown",
                    reference_date=None,
                    version_signals=(catalog_sha256, resource_url),
                    source_metadata={
                        "catalog_url": self.catalog_url,
                        "catalog_sha256": catalog_sha256,
                        "catalog_last_modified": headers.get("last-modified"),
                        "discovery_kind": "official_linked_page",
                        "availability": "requires_review",
                        "unavailable_reason": "not_verified",
                    },
                )
            )
        return tuple(sorted(resources, key=lambda item: (item.title, item.resource_url)))

    def download(self, resource: DiscoveredResource, *, max_bytes: int) -> RawResourceReceipt:
        raise ValueError(
            "Static catalog links require resource-specific terms and format review before download"
        )

    def inspect_schema(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> SchemaInspection:
        raise ValueError("Static linked pages do not provide a verified resource schema")

    def normalize(
        self,
        resource: DiscoveredResource,
        receipt: RawResourceReceipt,
        inspection: SchemaInspection,
    ) -> Iterator[dict[str, object]]:
        raise ValueError("Static linked pages cannot be normalized before resource review")
