"""Official future-population and economic-census adapters."""

from __future__ import annotations

import csv
import hashlib
import html as html_module
import json
import re
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, TextIO
from urllib.parse import urlencode, urljoin

import geopandas as gpd
import pyogrio

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

FUTURE_POPULATION_MANIFEST = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html"
ESTAT_SEARCH_URL = "https://www.e-stat.go.jp/gis/statmap-search/search_detail"
ESTAT_PUBLIC_URL = (
    "https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&"
    "serveyId=H002005112021&statsId=T001162&toukeiCode=00200553&"
    "toukeiYear=2021&type=1"
)
ESTAT_STATS_ID = "T001162"

_FUTURE_RESOURCE = re.compile(
    r"DownLd\(\s*'(?P<size>[^']+)'\s*,\s*"
    r"'(?P<filename>250m_mesh_(?P<year>\d{4})_(?P<prefecture>\d{2})_GEOJSON\.zip)'"
    r"\s*,\s*'(?P<path>[^']+)'",
    re.IGNORECASE,
)
_ESTAT_ARTICLE = re.compile(
    r'<article class="stat-resorce_list-item">(?P<body>.*?)</article>', re.DOTALL
)
_RELEASE_DATE = re.compile(r'align-center-data">\s*(?P<date>\d{4}-\d{2}-\d{2})\s*</li>')


def _safe_member_name(info: zipfile.ZipInfo) -> PurePosixPath:
    member = PurePosixPath(info.filename.replace("\\", "/"))
    if member.is_absolute() or ".." in member.parts:
        raise ValueError("Official archive contains an unsafe member path")
    if info.flag_bits & 0x1:
        raise ValueError("Encrypted official archive members are not supported")
    return member


def _bounded_archive_members(
    path: Path,
    *,
    suffixes: tuple[str, ...],
    max_members: int,
    max_uncompressed_bytes: int,
    max_compression_ratio: float,
) -> tuple[zipfile.ZipInfo, ...]:
    if not zipfile.is_zipfile(path):
        raise ValueError("Official ZIP resource is not a valid ZIP archive")
    selected = []
    total = 0
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > max_members:
            raise ValueError("Official archive exceeds the member limit")
        for info in infos:
            member = _safe_member_name(info)
            if info.is_dir():
                continue
            total += info.file_size
            if total > max_uncompressed_bytes:
                raise ValueError("Official archive exceeds the uncompressed byte limit")
            if info.file_size / max(info.compress_size, 1) > max_compression_ratio:
                raise ValueError("Official archive exceeds the compression-ratio limit")
            if member.suffix.lower() in suffixes:
                selected.append(info)
    if len(selected) != 1:
        raise ValueError("Official archive must contain exactly one supported data member")
    return tuple(selected)


def _vsi_zip(path: Path, member: str) -> str:
    return f"/vsizip/{{{path.as_posix()}}}/{member}"


class MlitFuturePopulationAdapter:
    """Discover a prefectural R6 250 m future-population GeoJSON package."""

    definition: OpenDataAdapterDefinition = OFFICIAL_SOURCE_REGISTRY.adapter(
        "mlit-future-population-250m@2024"
    )
    manifest_url = FUTURE_POPULATION_MANIFEST

    def __init__(
        self,
        *,
        client: SafeHttpClient,
        object_store: ContentAddressedObjectStore,
        max_manifest_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self.client = client
        self.object_store = object_store
        self.max_manifest_bytes = max_manifest_bytes
        self.client.validate_url(self.manifest_url)

    def discover(self, request: DiscoveryRequest) -> tuple[DiscoveredResource, ...]:
        if len(request.municipality_code) != 5 or not request.municipality_code.isdigit():
            raise ValueError("Future-population discovery requires a five-digit municipality code")
        prefecture = request.municipality_code[:2]
        payload, headers = self.client.get_bytes(
            self.manifest_url, max_bytes=self.max_manifest_bytes
        )
        try:
            manifest = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("MLIT future-population manifest is not UTF-8") from error
        candidates = [
            match
            for match in _FUTURE_RESOURCE.finditer(manifest)
            if match["prefecture"] == prefecture
        ]
        if not candidates:
            raise ValueError(
                f"No current 250 m future-population GeoJSON for prefecture {prefecture}"
            )
        selected = max(candidates, key=lambda match: (int(match["year"]), match["filename"]))
        resource_url = self.client.validate_url(urljoin(self.manifest_url, selected["path"]))
        selected_resource_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "prefecture_code": prefecture,
                    "production_year": int(selected["year"]),
                    "filename": selected["filename"],
                    "resource_path": selected["path"],
                    "declared_download_size": selected["size"],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return (
            DiscoveredResource(
                external_dataset_id="mlit-ksj-future-population-250m-r6",
                external_resource_id=selected["filename"],
                title=f"250mメッシュ別将来推計人口（{prefecture}）",
                resource_url=resource_url,
                format="ZIP",
                license_id="cc-by-4.0",
                reference_date="2020-10-01",
                version_signals=(
                    selected["year"],
                    selected["filename"],
                    selected_resource_fingerprint,
                ),
                source_metadata={
                    "manifest_url": self.manifest_url,
                    "selected_resource_fingerprint": selected_resource_fingerprint,
                    "selected_resource_fingerprint_fields": [
                        "prefecture_code",
                        "production_year",
                        "filename",
                        "resource_path",
                        "declared_download_size",
                    ],
                    "manifest_etag": headers.get("etag"),
                    "manifest_last_modified": headers.get("last-modified"),
                    "prefecture_code": prefecture,
                    "production_year": int(selected["year"]),
                    "declared_download_size": selected["size"],
                    "baseline_reference_date": "2020-10-01",
                    "projection_years": list(range(2025, 2071, 5)),
                    "horizontal_datum": "JGD2011",
                    "epsg": 6668,
                    "resource_scope": "prefectural_extract_of_national_dataset",
                },
            ),
        )

    def download(self, resource: DiscoveredResource, *, max_bytes: int) -> RawResourceReceipt:
        return self.object_store.fetch(self.client, resource.resource_url, max_bytes=max_bytes)

    def _member(self, receipt: RawResourceReceipt) -> tuple[Path, zipfile.ZipInfo]:
        path = self.object_store.path_for_key(receipt.object_key)
        member = _bounded_archive_members(
            path,
            suffixes=(".geojson", ".json"),
            max_members=8,
            max_uncompressed_bytes=768 * 1024 * 1024,
            max_compression_ratio=200,
        )[0]
        return path, member

    def inspect_schema(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> SchemaInspection:
        path, member = self._member(receipt)
        info = pyogrio.read_info(_vsi_zip(path, member.filename))
        fields = tuple(str(value) for value in info["fields"])
        if not fields:
            raise ValueError("Future-population GeoJSON has no attributes")
        geometry_type = str(info.get("geometry_type"))
        if "Polygon" not in geometry_type:
            raise ValueError("Future-population resource is not polygon geometry")
        crs = str(info.get("crs") or "")
        if crs not in {"EPSG:6668", "EPSG:4326"}:
            raise ValueError(f"Unexpected future-population CRS: {crs}")
        row_count = int(info["features"])
        if row_count <= 0 or row_count > 2_000_000:
            raise ValueError("Future-population feature count is outside the accepted bounds")
        fingerprint = hashlib.sha256("\0".join(fields).encode()).hexdigest()
        return SchemaInspection(
            schema_version=f"mlit-future-population-250m-columns:{fingerprint}",
            field_names=fields,
            encoding="UTF-8",
            source_crs=crs,
            row_count=row_count,
            quality_results=(
                {"gate": "bounded_archive", "status": "passed"},
                {"gate": "polygon_geometry", "status": "passed", "type": geometry_type},
                {"gate": "declared_crs", "status": "passed", "crs": crs},
                {"gate": "bounded_feature_count", "status": "passed", "rows": row_count},
            ),
        )

    def read_frame(
        self, receipt: RawResourceReceipt, inspection: SchemaInspection
    ) -> gpd.GeoDataFrame:
        path, member = self._member(receipt)
        frame = gpd.read_file(_vsi_zip(path, member.filename), engine="pyogrio")
        if tuple(str(value) for value in frame.columns if value != frame.geometry.name) != (
            inspection.field_names
        ):
            raise ValueError(
                "Future-population schema changed between inspection and normalization"
            )
        return frame

    def normalize(
        self,
        resource: DiscoveredResource,
        receipt: RawResourceReceipt,
        inspection: SchemaInspection,
    ) -> Iterator[dict[str, Any]]:
        frame = self.read_frame(receipt, inspection)
        for index, row in frame.iterrows():
            yield {
                "source_row_locator": f"{resource.external_resource_id}:feature:{index}",
                "values": {
                    str(field): None if row[field] is None else row[field]
                    for field in inspection.field_names
                },
                "geometry": row.geometry.__geo_interface__ if row.geometry is not None else None,
            }


class EStatEconomicCensusAdapter:
    """Discover the prefectural 2021 500 m JGD2011 economic-census table."""

    definition: OpenDataAdapterDefinition = OFFICIAL_SOURCE_REGISTRY.adapter(
        "estat-economic-census-500m@2021"
    )
    public_url = ESTAT_PUBLIC_URL
    search_url = ESTAT_SEARCH_URL

    def __init__(
        self,
        *,
        client: SafeHttpClient,
        object_store: ContentAddressedObjectStore,
        max_rows: int = 1_000_000,
    ) -> None:
        self.client = client
        self.object_store = object_store
        self.max_rows = max_rows
        self.client.validate_url(self.public_url)
        self.client.validate_url(self.search_url)

    def discover(self, request: DiscoveryRequest) -> tuple[DiscoveredResource, ...]:
        if len(request.municipality_code) != 5 or not request.municipality_code.isdigit():
            raise ValueError("Economic-census discovery requires a five-digit municipality code")
        prefecture = request.municipality_code[:2]
        page = str((int(prefecture) - 1) // 20 + 1)
        query = {
            "type": "1",
            "toukeiCode": "00200553",
            "toukeiYear": "2021",
            "aggregateUnit": "H",
            "serveyId": "H002005112021",
            "statsId": ESTAT_STATS_ID,
            "datum": "2011",
            "by_prefecture_flg": "1",
            "download_disp_flg": "1",
            "page": page,
        }
        manifest_url = f"{self.search_url}?{urlencode(query)}"
        payload, headers = self.client.get_bytes(manifest_url, max_bytes=32 * 1024 * 1024)
        try:
            manifest = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("e-Stat search endpoint did not return valid JSON") from error
        detail = manifest.get("detail") if isinstance(manifest, dict) else None
        if not isinstance(detail, str):
            raise TypeError("e-Stat search response does not contain download detail")
        resource_path = (
            f"/gis/statmap-search/data?statsId={ESTAT_STATS_ID}&code={prefecture}&downloadType=2"
        )
        release_date = None
        for article in _ESTAT_ARTICLE.finditer(detail):
            body = html_module.unescape(article["body"])
            if resource_path not in body:
                continue
            match = _RELEASE_DATE.search(body)
            if match is None:
                raise ValueError("e-Stat resource has no release date")
            release_date = match["date"]
            break
        if release_date is None:
            raise ValueError(f"e-Stat current manifest has no prefecture {prefecture} resource")
        resource_url = self.client.validate_url(urljoin(self.search_url, resource_path))
        selected_resource_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "statistics_id": ESTAT_STATS_ID,
                    "release_date": release_date,
                    "prefecture_code": prefecture,
                    "resource_path": resource_path,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return (
            DiscoveredResource(
                external_dataset_id="estat-economic-census-2021-500m-jgd2011",
                external_resource_id=f"tbl{ESTAT_STATS_ID}H{prefecture}.zip",
                title=f"令和3年経済センサス 500mメッシュ（{prefecture}）",
                resource_url=resource_url,
                format="ZIP",
                license_id="government-standard-terms-2.0",
                reference_date="2021-06-01",
                version_signals=(
                    ESTAT_STATS_ID,
                    release_date,
                    resource_path,
                    selected_resource_fingerprint,
                ),
                source_metadata={
                    "manifest_url": manifest_url,
                    "selected_resource_fingerprint": selected_resource_fingerprint,
                    "selected_resource_fingerprint_fields": [
                        "statistics_id",
                        "release_date",
                        "prefecture_code",
                        "resource_path",
                    ],
                    "manifest_etag": headers.get("etag"),
                    "manifest_last_modified": headers.get("last-modified"),
                    "statistics_id": ESTAT_STATS_ID,
                    "survey_id": "H002005112021",
                    "survey_reference_date": "2021-06-01",
                    "release_date": release_date,
                    "prefecture_code": prefecture,
                    "aggregate_unit": "500m_mesh",
                    "horizontal_datum": "JGD2011",
                    "resource_scope": "prefectural_extract_of_national_statistics",
                },
            ),
        )

    def download(self, resource: DiscoveredResource, *, max_bytes: int) -> RawResourceReceipt:
        return self.object_store.fetch(self.client, resource.resource_url, max_bytes=max_bytes)

    def _member(self, receipt: RawResourceReceipt) -> tuple[Path, zipfile.ZipInfo]:
        path = self.object_store.path_for_key(receipt.object_key)
        member = _bounded_archive_members(
            path,
            suffixes=(".txt", ".csv"),
            max_members=8,
            max_uncompressed_bytes=256 * 1024 * 1024,
            max_compression_ratio=200,
        )[0]
        return path, member

    @contextmanager
    def _csv_text(self, receipt: RawResourceReceipt) -> Iterator[tuple[TextIO, str]]:
        path, member = self._member(receipt)
        archive = zipfile.ZipFile(path)
        binary: BinaryIO = archive.open(member)
        prefix = binary.read(4)
        binary.close()
        if prefix.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            with archive.open(member) as candidate:
                sample = candidate.read(64 * 1024)
            try:
                sample.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                try:
                    sample.decode("cp932")
                    encoding = "cp932"
                except UnicodeDecodeError as error:
                    archive.close()
                    raise ValueError("e-Stat CSV encoding is neither UTF-8 nor CP932") from error
        text = TextIOWrapper(archive.open(member), encoding=encoding, newline="")
        try:
            yield text, encoding
        finally:
            text.close()
            archive.close()

    def inspect_schema(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> SchemaInspection:
        row_count = 0
        label_row_count = 0
        formula_like_cells = 0
        with self._csv_text(receipt) as (stream, encoding):
            reader = csv.reader(stream, strict=True)
            try:
                header = next(reader)
            except StopIteration as error:
                raise ValueError("e-Stat CSV is empty") from error
            fields = tuple(value.strip() for value in header)
            if not fields or any(not value for value in fields) or len(fields) != len(set(fields)):
                raise ValueError("e-Stat CSV requires non-empty unique headers")
            for row in reader:
                if len(row) != len(fields):
                    raise ValueError(f"Malformed e-Stat CSV row: {row_count + 1}")
                if not row[0].strip():
                    if (
                        row_count != 0
                        or label_row_count
                        or any(not value.strip() for value in row[1:])
                    ):
                        raise ValueError("e-Stat CSV has an invalid official label row")
                    label_row_count = 1
                    continue
                row_count += 1
                if row_count > self.max_rows:
                    raise ValueError("e-Stat CSV exceeds the row limit")
                if re.fullmatch(r"\d{9}", row[0].strip()) is None:
                    raise ValueError(f"Invalid e-Stat 500 m mesh code at data row {row_count}")
                formula_like_cells += sum(
                    value.lstrip().startswith(("=", "+", "-", "@")) for value in row
                )
        if row_count == 0:
            raise ValueError("e-Stat CSV contains no data rows")
        fingerprint = hashlib.sha256("\0".join(fields).encode()).hexdigest()
        return SchemaInspection(
            schema_version=f"estat-{ESTAT_STATS_ID}-columns:{fingerprint}",
            field_names=fields,
            encoding=encoding,
            source_crs="JGD2011 mesh code",
            row_count=row_count,
            quality_results=(
                {"gate": "bounded_archive", "status": "passed"},
                {"gate": "non_empty_unique_schema", "status": "passed"},
                {
                    "gate": "official_label_row",
                    "status": "passed",
                    "rows": label_row_count,
                    "handling": "validated and excluded from normalized data rows",
                },
                {"gate": "bounded_row_shape", "status": "passed", "rows": row_count},
                {
                    "gate": "suppression_boundary",
                    "status": "passed",
                    "handling": "suppression symbols remain null-with-reason; never coerced to zero",
                },
                {
                    "gate": "formula_injection_boundary",
                    "status": "passed",
                    "formula_like_cells": formula_like_cells,
                    "handling": "preserve raw; escape only when exporting spreadsheet CSV",
                },
            ),
        )

    def normalize(
        self,
        resource: DiscoveredResource,
        receipt: RawResourceReceipt,
        inspection: SchemaInspection,
    ) -> Iterator[dict[str, Any]]:
        with self._csv_text(receipt) as (stream, _):
            reader = csv.DictReader(stream, strict=True)
            if tuple(reader.fieldnames or ()) != inspection.field_names:
                raise ValueError("e-Stat schema changed between inspection and normalization")
            for index, row in enumerate(reader, start=2):
                if None in row:
                    raise ValueError(f"Malformed e-Stat CSV row: {index}")
                if not str(row.get("KEY_CODE") or "").strip():
                    if index != 2 or any(
                        not str(value or "").strip()
                        for key, value in row.items()
                        if key != "KEY_CODE"
                    ):
                        raise ValueError("e-Stat CSV has an invalid official label row")
                    continue
                yield {
                    "source_row_locator": f"{resource.external_resource_id}:row:{index}",
                    "values": {str(key): str(value or "") for key, value in row.items()},
                }
