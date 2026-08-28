"""Generic CKAN v3 discovery and bounded CSV normalization adapter."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from backend.citygap_platform.domain.open_data import (
    DiscoveredResource,
    DiscoveryRequest,
    OpenDataAdapterDefinition,
    RawResourceReceipt,
    SchemaInspection,
)
from backend.citygap_platform.ingestion.adapters import CsvSourceAdapter
from backend.citygap_platform.open_data.http import SafeHttpClient
from backend.citygap_platform.open_data.registry import OFFICIAL_SOURCE_REGISTRY
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore

CKAN_LICENSE_MAP = {"cc-by-40-intl": "cc-by-4.0"}


def _detect_csv_encoding(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "cp932"):
        try:
            payload.decode(encoding)
        except UnicodeDecodeError:
            continue
        return encoding
    raise ValueError("CSV encoding is neither UTF-8 with optional BOM nor CP932")


class CkanCatalogAdapter:
    definition: OpenDataAdapterDefinition = OFFICIAL_SOURCE_REGISTRY.adapter("ckan-v3@1")

    def __init__(
        self,
        *,
        api_url: str,
        organization_id: str,
        municipality_code: str,
        client: SafeHttpClient,
        object_store: ContentAddressedObjectStore,
        max_catalog_rows: int = 1000,
    ) -> None:
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]+", organization_id)
            or not municipality_code.isdigit()
            or len(municipality_code) != 5
        ):
            raise ValueError("CKAN organization and five-digit municipality code are required")
        self.api_url = client.validate_url(api_url)
        self.organization_id = organization_id
        self.municipality_code = municipality_code
        self.client = client
        self.object_store = object_store
        self.max_catalog_rows = max_catalog_rows

    def discover(self, request: DiscoveryRequest) -> tuple[DiscoveredResource, ...]:
        if request.municipality_code != self.municipality_code:
            raise ValueError("Discovery request municipality does not match adapter scope")
        query = urlencode(
            {"fq": f"organization:{self.organization_id}", "rows": self.max_catalog_rows}
        )
        payload = self.client.get_json(f"{self.api_url}?{query}")
        if payload.get("success") is not True or not isinstance(payload.get("result"), dict):
            raise ValueError("CKAN API reported an unsuccessful result")
        result = payload["result"]
        packages = result.get("results")
        if not isinstance(packages, list) or result.get("count") != len(packages):
            raise ValueError("CKAN result count does not match returned packages")
        discovered: list[DiscoveredResource] = []
        for package in packages:
            if not isinstance(package, dict) or not isinstance(package.get("resources"), list):
                raise TypeError("CKAN package has an invalid resource collection")
            package_id = str(package.get("name") or package.get("id") or "").strip()
            if not package_id:
                raise ValueError("CKAN package is missing an identity")
            license_id = CKAN_LICENSE_MAP.get(str(package.get("license_id")), "unknown")
            for resource in package["resources"]:
                if not isinstance(resource, dict) or not resource.get("url"):
                    continue
                resource_url = self.client.validate_url(str(resource["url"]))
                resource_id = str(resource.get("id") or "").strip()
                if not resource_id:
                    raise ValueError("CKAN resource is missing an identity")
                version_signals = tuple(
                    str(value)
                    for value in (
                        package.get("metadata_modified"),
                        resource.get("last_modified"),
                        resource.get("hash"),
                    )
                    if value
                )
                discovered.append(
                    DiscoveredResource(
                        external_dataset_id=package_id,
                        external_resource_id=resource_id,
                        title=str(resource.get("name") or package.get("title") or package_id),
                        resource_url=resource_url,
                        format=str(resource.get("format") or "unknown").upper(),
                        license_id=license_id,
                        reference_date=None,
                        version_signals=version_signals,
                        source_metadata={
                            "package_title": package.get("title"),
                            "package_notes": package.get("notes"),
                            "source_license_id": package.get("license_id"),
                            "source_license_title": package.get("license_title"),
                            "metadata_modified": package.get("metadata_modified"),
                            "resource_created": resource.get("created"),
                            "resource_last_modified": resource.get("last_modified"),
                            "resource_size": resource.get("size"),
                            "resource_description": resource.get("description"),
                        },
                    )
                )
        return tuple(
            sorted(
                discovered,
                key=lambda item: (item.external_dataset_id, item.external_resource_id),
            )
        )

    def download(self, resource: DiscoveredResource, *, max_bytes: int) -> RawResourceReceipt:
        return self.object_store.fetch(self.client, resource.resource_url, max_bytes=max_bytes)

    def inspect_schema(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> SchemaInspection:
        if resource.format != "CSV":
            raise ValueError(f"CKAN schema inspection is not implemented for {resource.format}")
        path = self.object_store.path_for_key(receipt.object_key)
        encoding = _detect_csv_encoding(path)
        inspection = CsvSourceAdapter(path, encoding=encoding, allow_extensionless=True).inspect()
        return SchemaInspection(
            schema_version=f"columns:{','.join(inspection.columns)}",
            field_names=inspection.columns,
            encoding=encoding,
            source_crs=None,
            row_count=inspection.row_count,
            quality_results=(
                {"gate": "non_empty_schema", "status": "passed"},
                {"gate": "sha256", "status": "passed", "value": inspection.sha256},
            ),
        )

    def normalize(
        self,
        resource: DiscoveredResource,
        receipt: RawResourceReceipt,
        inspection: SchemaInspection,
    ) -> Iterator[dict[str, Any]]:
        if resource.format != "CSV" or not inspection.field_names:
            raise ValueError("Only inspected CSV resources can be normalized")
        frame = CsvSourceAdapter(
            self.object_store.path_for_key(receipt.object_key),
            encoding=inspection.encoding,
            allow_extensionless=True,
        ).dataframe()
        for index, row in frame.iterrows():
            yield {
                "source_row_locator": f"row:{index + 2}",
                "values": {str(key): str(value) for key, value in row.items()},
            }
