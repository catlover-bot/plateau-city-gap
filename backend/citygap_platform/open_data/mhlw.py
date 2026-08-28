"""Official MHLW medical and care manifest adapters.

The Ministry pages are treated as version manifests, not as live analysis APIs.  A
discovered resource is downloaded once into immutable content-addressed storage and
then inspected with bounded CSV/ZIP readers.  Only the newest explicitly dated
section is discovered; older snapshots remain addressable at their original URLs but
are never silently mixed into the current snapshot.
"""

from __future__ import annotations

import csv
import hashlib
import re
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from html.parser import HTMLParser
from io import TextIOWrapper
from pathlib import PurePosixPath
from typing import Any, BinaryIO, TextIO
from urllib.parse import urljoin, urlsplit

from backend.citygap_platform.domain.open_data import (
    DiscoveredResource,
    DiscoveryRequest,
    OpenDataAdapterDefinition,
    RawResourceReceipt,
    SchemaInspection,
)
from backend.citygap_platform.open_data.http import SafeHttpClient
from backend.citygap_platform.open_data.registry import OFFICIAL_SOURCE_REGISTRY
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore

MEDICAL_MANIFEST_URL = (
    "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html"
)
CARE_MANIFEST_URL = "https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html"

_MEDICAL_DATE = re.compile(r"(?P<year>\d{4})年\s*(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日時点")
_CARE_DATE = re.compile(r"(?P<year>\d{4})年\s*(?P<month>\d{1,2})月末時点")
_MEDICAL_FILE = re.compile(
    r"(?P<code>0[1-5](?:-[12])?)_(?P<kind>[a-z0-9_]+)_(?P<stamp>\d{8})\.csv\.zip$",
    re.IGNORECASE,
)
_CARE_FILE = re.compile(r"jigyosho_(?P<code>\d{3})_all_(?P<stamp>\d{14})\.csv$", re.IGNORECASE)


class _SectionLinkParser(HTMLParser):
    """Collect links under h3 headings without relying on provider CSS."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[tuple[str, list[tuple[str, str]]]] = []
        self._heading: list[str] | None = None
        self._active_section: int | None = None
        self._link_href: str | None = None
        self._link_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "h3":
            self._heading = []
        elif tag.lower() == "a" and self._active_section is not None:
            href = dict(attrs).get("href")
            if href:
                self._link_href = href
                self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._heading is not None:
            self._heading.append(data)
        if self._link_text is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "h3" and self._heading is not None:
            heading = " ".join("".join(self._heading).split())
            self.sections.append((heading, []))
            self._active_section = len(self.sections) - 1
            self._heading = None
        elif tag.lower() == "a" and self._link_href is not None:
            assert self._active_section is not None
            text = " ".join("".join(self._link_text or ()).split())
            self.sections[self._active_section][1].append((self._link_href, text))
            self._link_href = None
            self._link_text = None


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1).fromordinal(date(year, month + 1, 1).toordinal() - 1)


def _dated_section(html: str, *, family: str) -> tuple[str, list[tuple[str, str]], str]:
    parser = _SectionLinkParser()
    parser.feed(html)
    pattern = _MEDICAL_DATE if family == "medical" else _CARE_DATE
    candidates: list[tuple[date, str, list[tuple[str, str]]]] = []
    for heading, links in parser.sections:
        match = pattern.search(heading)
        if match is None:
            continue
        year = int(match.group("year"))
        month = int(match.group("month"))
        if family == "medical":
            reference = date(year, month, int(match.group("day")))
        else:
            reference = _last_day_of_month(year, month)
        candidates.append((reference, heading, links))
    if candidates:
        reference, heading, links = max(candidates, key=lambda item: item[0])
        return heading, links, reference.isoformat()
    raise ValueError(f"MHLW {family} manifest has no explicitly dated section")


def _safe_resource_url(client: SafeHttpClient, manifest_url: str, href: str) -> str:
    url = urljoin(manifest_url, href)
    parsed = urlsplit(url)
    if parsed.query or parsed.fragment:
        raise ValueError("MHLW resource links must be stable files without query or fragment")
    return client.validate_url(url)


class _MhlwManifestAdapter:
    definition: OpenDataAdapterDefinition
    family: str
    manifest_url: str
    license_id: str

    def __init__(
        self,
        *,
        client: SafeHttpClient,
        object_store: ContentAddressedObjectStore,
        max_manifest_bytes: int = 8 * 1024 * 1024,
        max_rows: int = 2_000_000,
        max_uncompressed_bytes: int = 512 * 1024 * 1024,
        max_compression_ratio: float = 200.0,
    ) -> None:
        self.client = client
        self.object_store = object_store
        self.max_manifest_bytes = max_manifest_bytes
        self.max_rows = max_rows
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.max_compression_ratio = max_compression_ratio
        self.client.validate_url(self.manifest_url)

    def discover(self, request: DiscoveryRequest) -> tuple[DiscoveredResource, ...]:
        if len(request.municipality_code) != 5 or not request.municipality_code.isdigit():
            raise ValueError("MHLW discovery requires a five-digit municipality code")
        payload, headers = self.client.get_bytes(
            self.manifest_url, max_bytes=self.max_manifest_bytes
        )
        try:
            html = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("MHLW manifest is not UTF-8 HTML") from error
        heading, links, reference_date = _dated_section(html, family=self.family)
        manifest_sha256 = hashlib.sha256(payload).hexdigest()
        resources: list[DiscoveredResource] = []
        for href, label in links:
            url = _safe_resource_url(self.client, self.manifest_url, href)
            filename = PurePosixPath(urlsplit(url).path).name
            parsed = self._parse_filename(filename)
            if parsed is None:
                continue
            resources.append(
                DiscoveredResource(
                    external_dataset_id=f"mhlw-{self.family}-{parsed['dataset_key']}",
                    external_resource_id=filename,
                    title=label or parsed["dataset_key"],
                    resource_url=url,
                    format=parsed["format"],
                    license_id=self.license_id,
                    reference_date=reference_date,
                    version_signals=(
                        reference_date,
                        parsed["version_stamp"],
                        manifest_sha256,
                    ),
                    source_metadata={
                        "manifest_url": self.manifest_url,
                        "manifest_heading": heading,
                        "manifest_sha256": manifest_sha256,
                        "manifest_etag": headers.get("etag"),
                        "manifest_last_modified": headers.get("last-modified"),
                        "resource_scope": "national",
                        "discovery_context_municipality_code": request.municipality_code,
                        **parsed,
                    },
                )
            )
        if not resources:
            raise ValueError(f"MHLW {self.family} current manifest contains no supported resources")
        return tuple(
            sorted(resources, key=lambda item: (item.external_dataset_id, item.resource_url))
        )

    def _parse_filename(self, filename: str) -> dict[str, str] | None:
        raise NotImplementedError

    def download(self, resource: DiscoveredResource, *, max_bytes: int) -> RawResourceReceipt:
        return self.object_store.fetch(self.client, resource.resource_url, max_bytes=max_bytes)

    @contextmanager
    def _csv_text(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> Iterator[TextIO]:
        path = self.object_store.path_for_key(receipt.object_key)
        binary: BinaryIO
        archive: zipfile.ZipFile | None = None
        if resource.format == "ZIP":
            if not zipfile.is_zipfile(path):
                raise ValueError("MHLW ZIP resource is not a valid ZIP archive")
            archive = zipfile.ZipFile(path)
            members = []
            total = 0
            for info in archive.infolist():
                member = PurePosixPath(info.filename.replace("\\", "/"))
                if member.is_absolute() or ".." in member.parts:
                    archive.close()
                    raise ValueError("MHLW archive contains an unsafe member path")
                if info.flag_bits & 0x1:
                    archive.close()
                    raise ValueError("Encrypted MHLW archive members are not supported")
                if info.is_dir():
                    continue
                total += info.file_size
                if total > self.max_uncompressed_bytes:
                    archive.close()
                    raise ValueError("MHLW archive exceeds the uncompressed byte limit")
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > self.max_compression_ratio:
                    archive.close()
                    raise ValueError("MHLW archive exceeds the compression-ratio limit")
                if member.suffix.lower() == ".csv":
                    members.append(info)
            if len(members) != 1 or len(archive.infolist()) > 4:
                archive.close()
                raise ValueError("MHLW ZIP must contain exactly one bounded CSV member")
            binary = archive.open(members[0])
        elif resource.format == "CSV":
            binary = path.open("rb")
        else:
            raise ValueError(f"Unsupported MHLW resource format: {resource.format}")
        text = TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        try:
            yield text
        except UnicodeDecodeError as error:
            raise ValueError("MHLW CSV is not UTF-8 with an optional BOM") from error
        finally:
            text.close()
            if archive is not None:
                archive.close()

    def inspect_schema(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> SchemaInspection:
        row_count = 0
        formula_like_cells = 0
        with self._csv_text(resource, receipt) as stream:
            reader = csv.reader(stream, strict=True)
            try:
                header = next(reader)
            except StopIteration as error:
                raise ValueError("MHLW CSV is empty") from error
            field_names = tuple(value.strip() for value in header)
            if not field_names or any(not value for value in field_names):
                raise ValueError("MHLW CSV has blank header names")
            if len(set(field_names)) != len(field_names):
                raise ValueError("MHLW CSV has duplicate header names")
            for row in reader:
                row_count += 1
                if row_count > self.max_rows:
                    raise ValueError("MHLW CSV exceeds the row limit")
                if len(row) != len(field_names):
                    raise ValueError(f"Malformed MHLW CSV row: {row_count + 1}")
                formula_like_cells += sum(
                    value.lstrip().startswith(("=", "+", "-", "@")) for value in row
                )
        fingerprint = hashlib.sha256("\0".join(field_names).encode("utf-8")).hexdigest()
        return SchemaInspection(
            schema_version=f"mhlw-{self.family}-columns:{fingerprint}",
            field_names=field_names,
            encoding="utf-8-sig",
            source_crs=None,
            row_count=row_count,
            quality_results=(
                {"gate": "non_empty_unique_schema", "status": "passed"},
                {"gate": "bounded_row_shape", "status": "passed", "rows": row_count},
                {
                    "gate": "formula_injection_boundary",
                    "status": "passed",
                    "formula_like_cells": formula_like_cells,
                    "handling": "preserve raw; escape only when exporting spreadsheet CSV",
                },
                {
                    "gate": "coordinate_reference",
                    "status": "requires_review",
                    "reason": "horizontal datum is not declared on the distribution page",
                },
            ),
        )

    def normalize(
        self,
        resource: DiscoveredResource,
        receipt: RawResourceReceipt,
        inspection: SchemaInspection,
    ) -> Iterator[dict[str, Any]]:
        if not inspection.field_names:
            raise ValueError("MHLW resource must be inspected before normalization")
        with self._csv_text(resource, receipt) as stream:
            reader = csv.DictReader(stream, strict=True)
            if tuple(reader.fieldnames or ()) != inspection.field_names:
                raise ValueError("MHLW schema changed between inspection and normalization")
            for index, row in enumerate(reader, start=2):
                if None in row:
                    raise ValueError(f"Malformed MHLW CSV row: {index}")
                yield {
                    "source_row_locator": f"{resource.external_resource_id}:row:{index}",
                    "values": {str(key): str(value or "") for key, value in row.items()},
                }


class MhlwMedicalAdapter(_MhlwManifestAdapter):
    definition = OFFICIAL_SOURCE_REGISTRY.adapter("mhlw-medical@2026-06")
    family = "medical"
    manifest_url = MEDICAL_MANIFEST_URL
    license_id = "pdl-1.0"

    def _parse_filename(self, filename: str) -> dict[str, str] | None:
        match = _MEDICAL_FILE.fullmatch(filename)
        if match is None:
            return None
        return {
            "dataset_key": f"{match.group('code')}-{match.group('kind').replace('_', '-')}",
            "medical_resource_code": match.group("code"),
            "medical_resource_kind": match.group("kind"),
            "version_stamp": match.group("stamp"),
            "format": "ZIP",
            "availability_semantics": "published facility/schedule information; not real-time availability",
        }


class MhlwCareAdapter(_MhlwManifestAdapter):
    definition = OFFICIAL_SOURCE_REGISTRY.adapter("mhlw-care@2026-06")
    family = "care"
    manifest_url = CARE_MANIFEST_URL
    license_id = "cc-by-4.0"

    def _parse_filename(self, filename: str) -> dict[str, str] | None:
        match = _CARE_FILE.fullmatch(filename)
        if match is None:
            return None
        return {
            "dataset_key": f"service-{match.group('code')}",
            "official_service_code": match.group("code"),
            "version_stamp": match.group("stamp"),
            "format": "CSV",
            "availability_semantics": "published establishment information; not current capacity or eligibility",
        }
