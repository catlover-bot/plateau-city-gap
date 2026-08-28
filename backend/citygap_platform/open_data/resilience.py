"""Official surface-ground and historical traffic-accident adapters.

Both sources are contextual evidence.  J-SHIS V4 values are model attributes,
not site measurements, and the NPA main table is a historical injury/fatality
accident register, not a prediction or a complete road-safety risk surface.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, TextIO
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
from backend.citygap_platform.open_data.storage import ContentAddressedObjectStore

JSHIS_RULES_URL = (
    "https://www.j-shis.bosai.go.jp/map/JSHIS2/data/DOC/DataFileRule/A-RULES.pdf"
)
JSHIS_TERMS_URL = "https://www.j-shis.bosai.go.jp/agreement"
JSHIS_ARCHIVE_TEMPLATE = (
    "https://www.j-shis.bosai.go.jp/map/JSHIS2/data/Z/V4/JAPAN/AMP/VS400_M250/"
    "Z-V4-JAPAN-AMP-VS400_M250-{first_mesh}.zip"
)
NPA_INDEX_URL = (
    "https://www.npa.go.jp/publications/statistics/koutsuu/opendata/index_opendata.html"
)
NPA_TERMS_URL = "https://www.npa.go.jp/rules/index.html"

JSHIS_FIELDS = ("CODE", "JCODE", "AVS", "ARV", "AVS_EB", "AVS_REF")
JSHIS_LANDFORM_NAMES = {
    0: "coastal_water",
    1: "mountain",
    2: "mountain_footslope",
    3: "hill",
    4: "volcano",
    5: "volcanic_footslope",
    6: "volcanic_hill",
    7: "rocky_strath_terrace",
    8: "gravelly_terrace",
    9: "volcanic_ash_terrace",
    10: "valley_bottom_lowland",
    11: "alluvial_fan",
    12: "natural_levee",
    13: "back_marsh",
    14: "abandoned_river_or_former_pond",
    15: "delta_or_coastal_lowland",
    16: "marine_sand_or_gravel_bars",
    17: "sand_dune",
    18: "lowland_between_dunes_or_bars",
    19: "reclaimed_land",
    20: "filled_land",
    21: "rock_shore_or_reef",
    22: "dry_river_bed",
    23: "river_bed",
    24: "lake",
}

NPA_FIELDS = (
    "資料区分",
    "都道府県コード",
    "警察署等コード",
    "本票番号",
    "事故内容",
    "死者数",
    "負傷者数",
    "路線コード",
    "地点コード",
    "市区町村コード",
    "発生日時　　年",
    "発生日時　　月",
    "発生日時　　日",
    "発生日時　　時",
    "発生日時　　分",
    "昼夜",
    "日の出時刻　　時",
    "日の出時刻　　分",
    "日の入り時刻　　時",
    "日の入り時刻　　分",
    "天候",
    "地形",
    "路面状態",
    "道路形状",
    "信号機",
    "一時停止規制　標識（当事者A）",
    "一時停止規制　表示（当事者A）",
    "一時停止規制　標識（当事者B）",
    "一時停止規制　表示（当事者B）",
    "車道幅員",
    "道路線形",
    "衝突地点",
    "ゾーン規制",
    "中央分離帯施設等",
    "歩車道区分",
    "事故類型",
    "年齢（当事者A）",
    "年齢（当事者B）",
    "当事者種別（当事者A）",
    "当事者種別（当事者B）",
    "用途別（当事者A）",
    "用途別（当事者B）",
    "車両形状等（当事者A）",
    "車両形状等（当事者B）",
    "オートマチック車（当事者A）",
    "オートマチック車（当事者B）",
    "サポカー（当事者A）",
    "サポカー（当事者B）",
    "速度規制（指定のみ）（当事者A）",
    "速度規制（指定のみ）（当事者B）",
    "車両の衝突部位（当事者A）",
    "車両の衝突部位（当事者B）",
    "車両の損壊程度（当事者A）",
    "車両の損壊程度（当事者B）",
    "エアバッグの装備（当事者A）",
    "エアバッグの装備（当事者B）",
    "サイドエアバッグの装備（当事者A）",
    "サイドエアバッグの装備（当事者B）",
    "人身損傷程度（当事者A）",
    "人身損傷程度（当事者B）",
    "地点　緯度（北緯）",
    "地点　経度（東経）",
    "曜日(発生年月日)",
    "祝日(発生年月日)",
    "認知機能検査経過日数（当事者A）",
    "認知機能検査経過日数（当事者B）",
    "運転練習の方法（当事者A）",
    "運転練習の方法（当事者B）",
)

_NPA_YEAR_LINK = re.compile(
    r"href=[\"'](?P<href>(?:[^\"']*/)?(?P<year>20\d{2})/opendata_(?P=year)\.html)"
)
_NPA_MAIN_LINK = re.compile(r"href=[\"'](?P<href>[^\"']*honhyo_(?P<year>20\d{2})\.csv)[\"']")
_NPA_SCHEMA_LINK = re.compile(r"href=[\"'](?P<href>[^\"']*fileteigisyo_(?P<year>20\d{2})\.xlsx)[\"']")
_NPA_CODEBOOK_LINK = re.compile(r"href=[\"'](?P<href>[^\"']*codebook_(?P<year>20\d{2})\.xlsx)[\"']")
_JSHIS_VERSION = re.compile(r"^#\s*VER\.\s*=\s*(?P<value>.+?)\s*$")
_JSHIS_DATE = re.compile(r"^#\s*DATE\s*=\s*(?P<value>\d{4}-\d{2}-\d{2})\s*$")
JST = timezone(timedelta(hours=9))


def _safe_member(info: zipfile.ZipInfo) -> PurePosixPath:
    member = PurePosixPath(info.filename.replace("\\", "/"))
    if member.is_absolute() or ".." in member.parts:
        raise ValueError("Official archive contains an unsafe member path")
    if info.flag_bits & 0x1:
        raise ValueError("Encrypted official archive members are not supported")
    return member


def _single_bounded_csv(path: Path) -> zipfile.ZipInfo:
    if not zipfile.is_zipfile(path):
        raise ValueError("J-SHIS resource is not a valid ZIP archive")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > 8:
            raise ValueError("J-SHIS archive exceeds the member limit")
        selected: list[zipfile.ZipInfo] = []
        total = 0
        for info in infos:
            member = _safe_member(info)
            if info.is_dir():
                continue
            total += info.file_size
            if total > 16 * 1024 * 1024:
                raise ValueError("J-SHIS archive exceeds the uncompressed byte limit")
            if info.file_size / max(info.compress_size, 1) > 100:
                raise ValueError("J-SHIS archive exceeds the compression-ratio limit")
            if member.suffix.lower() == ".csv":
                selected.append(info)
    if len(selected) != 1:
        raise ValueError("J-SHIS archive must contain exactly one CSV")
    return selected[0]


def _formula_like(value: str) -> bool:
    text = value.lstrip()
    return text.startswith(("=", "+", "@")) or (
        text.startswith("-") and len(text) > 1 and not text[1].isdigit()
    )


def _optional_number(value: str, *, field: str, maximum: float) -> float | None:
    text = value.strip()
    if text in {"", "-"}:
        return None
    try:
        result = float(text)
    except ValueError as error:
        raise ValueError(f"J-SHIS {field} is not numeric") from error
    if not 0 <= result <= maximum:
        raise ValueError(f"J-SHIS {field} is outside the supported range")
    return result


def npa_dms_to_decimal(value: str, *, longitude: bool) -> float:
    """Convert the NPA world-geodetic DD(D)MMSSsss fixed-width encoding."""

    text = value.strip()
    expected = 10 if longitude else 9
    degree_digits = 3 if longitude else 2
    if len(text) != expected or not text.isdigit():
        raise ValueError("NPA coordinate does not match fixed-width DMS")
    degrees = int(text[:degree_digits])
    minutes = int(text[degree_digits : degree_digits + 2])
    seconds = int(text[degree_digits + 2 :]) / 1000
    if minutes >= 60 or seconds >= 60:
        raise ValueError("NPA coordinate contains an invalid minute or second")
    result = degrees + minutes / 60 + seconds / 3600
    maximum = 180 if longitude else 90
    if not 0 <= result <= maximum:
        raise ValueError("NPA coordinate is outside the world-geodetic range")
    return result


def npa_occurrence_time(row: dict[str, str]) -> str:
    try:
        value = datetime(
            int(row["発生日時　　年"]),
            int(row["発生日時　　月"]),
            int(row["発生日時　　日"]),
            int(row["発生日時　　時"]),
            int(row["発生日時　　分"]),
            tzinfo=JST,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("NPA occurrence timestamp is invalid") from error
    return value.isoformat(timespec="minutes")


class JShisSurfaceGroundAdapter:
    definition: OpenDataAdapterDefinition = OFFICIAL_SOURCE_REGISTRY.adapter(
        "jshis-surface-ground-v4@2020"
    )

    def __init__(
        self,
        *,
        client: SafeHttpClient,
        object_store: ContentAddressedObjectStore,
        first_mesh_by_municipality: dict[str, str],
    ) -> None:
        self.client = client
        self.object_store = object_store
        self.first_mesh_by_municipality = dict(first_mesh_by_municipality)

    def discover(self, request: DiscoveryRequest) -> tuple[DiscoveredResource, ...]:
        first_mesh = self.first_mesh_by_municipality.get(request.municipality_code)
        if first_mesh is None or len(first_mesh) != 4 or not first_mesh.isdigit():
            raise ValueError("J-SHIS discovery requires a reviewed four-digit first mesh")
        resource_url = self.client.validate_url(
            JSHIS_ARCHIVE_TEMPLATE.format(first_mesh=first_mesh)
        )
        fingerprint = hashlib.sha256(
            json.dumps(
                {"dataset_version": "V4", "first_mesh": first_mesh, "url": resource_url},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return (
            DiscoveredResource(
                external_dataset_id="jshis-2020-surface-ground-v4-250m",
                external_resource_id=f"Z-V4-JAPAN-AMP-VS400_M250-{first_mesh}.zip",
                title=f"J-SHIS 2020年版 表層地盤250mメッシュ {first_mesh}",
                resource_url=resource_url,
                format="ZIP",
                license_id="jshis-terms-2025-03",
                reference_date=None,
                version_signals=("V4", first_mesh, fingerprint),
                source_metadata={
                    "first_mesh": first_mesh,
                    "dataset_version": "V4",
                    "model_reference_year": 2020,
                    "official_rules_url": JSHIS_RULES_URL,
                    "terms_url": JSHIS_TERMS_URL,
                    "selected_resource_fingerprint": fingerprint,
                    "source_datum": "JGD2000",
                    "source_epsg": 4612,
                    "model_semantics": "surface-ground model attributes, not site measurements",
                    "raw_redistribution": False,
                },
            ),
        )

    def download(self, resource: DiscoveredResource, *, max_bytes: int) -> RawResourceReceipt:
        return self.object_store.fetch(self.client, resource.resource_url, max_bytes=max_bytes)

    def _path_member(self, receipt: RawResourceReceipt) -> tuple[Path, zipfile.ZipInfo]:
        path = self.object_store.path_for_key(receipt.object_key)
        return path, _single_bounded_csv(path)

    @contextmanager
    def _text(self, receipt: RawResourceReceipt) -> Iterator[TextIO]:
        path, member = self._path_member(receipt)
        with (
            zipfile.ZipFile(path) as archive,
            archive.open(member) as binary,
            io.TextIOWrapper(binary, encoding="utf-8", newline="") as text,
        ):
            yield text

    def inspect_schema(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> SchemaInspection:
        version: str | None = None
        source_date: str | None = None
        row_count = 0
        jcodes: set[int] = set()
        with self._text(receipt) as stream:
            data_lines: list[str] = []
            for line in stream:
                if line.startswith("#"):
                    if match := _JSHIS_VERSION.match(line.rstrip()):
                        version = match["value"]
                    if match := _JSHIS_DATE.match(line.rstrip()):
                        source_date = match["value"]
                    continue
                data_lines.append(line)
            for row in csv.reader(data_lines, skipinitialspace=True):
                if len(row) != len(JSHIS_FIELDS):
                    raise ValueError("J-SHIS row does not match the six-field schema")
                if any(_formula_like(value) for value in row):
                    raise ValueError("J-SHIS row contains spreadsheet formula-like content")
                code = row[0].strip()
                if len(code) != 10 or not code.isdigit() or code[-1] not in "1234":
                    raise ValueError("J-SHIS CODE is not a 250 m mesh identifier")
                try:
                    jcode = int(row[1])
                except ValueError as error:
                    raise ValueError("J-SHIS JCODE is not an integer") from error
                if jcode not in JSHIS_LANDFORM_NAMES:
                    raise ValueError("J-SHIS JCODE is outside the official dictionary")
                avs = _optional_number(row[2], field="AVS", maximum=2000)
                arv = _optional_number(row[3], field="ARV", maximum=10)
                _optional_number(row[4], field="AVS_EB", maximum=2000)
                _optional_number(row[5], field="AVS_REF", maximum=1)
                if jcode == 0 and (avs != 0 or arv != 0):
                    raise ValueError("J-SHIS coastal-water cells must retain encoded zero values")
                jcodes.add(jcode)
                row_count += 1
        if version is None or source_date is None or row_count == 0:
            raise ValueError("J-SHIS metadata or data rows are missing")
        return SchemaInspection(
            schema_version=f"J-SHIS-Z-V4-AMP-VS400-M250@{version}",
            field_names=JSHIS_FIELDS,
            encoding="UTF-8",
            source_crs="EPSG:4612",
            row_count=row_count,
            quality_results=(
                {"gate": "archive_security", "status": "pass"},
                {"gate": "exact_fields", "status": "pass", "count": 6},
                {"gate": "source_date", "status": "pass", "value": source_date},
                {"gate": "jcode_dictionary", "status": "pass", "codes": sorted(jcodes)},
                {"gate": "formula_boundary", "status": "pass"},
            ),
        )

    def normalize(
        self,
        resource: DiscoveredResource,
        receipt: RawResourceReceipt,
        inspection: SchemaInspection,
    ) -> Iterator[dict[str, Any]]:
        if inspection.field_names != JSHIS_FIELDS:
            raise ValueError("J-SHIS inspection does not match this adapter")
        with self._text(receipt) as stream:
            rows = csv.reader((line for line in stream if not line.startswith("#")), skipinitialspace=True)
            for values in rows:
                if len(values) != 6:
                    raise ValueError("J-SHIS row width changed after inspection")
                row = dict(zip(JSHIS_FIELDS, (value.strip() for value in values), strict=True))
                jcode = int(row["JCODE"])
                encoded_avs = _optional_number(row["AVS"], field="AVS", maximum=2000)
                encoded_arv = _optional_number(row["ARV"], field="ARV", maximum=10)
                yield {
                    "mesh_code_250m": row["CODE"],
                    "parent_500m_mesh_code": row["CODE"][:9],
                    "microtopography_code": jcode,
                    "microtopography": JSHIS_LANDFORM_NAMES[jcode],
                    "average_shear_wave_velocity_m_s": None if jcode == 0 else encoded_avs,
                    "amplification_ratio": None if jcode == 0 else encoded_arv,
                    "engineering_bedrock_velocity_m_s": _optional_number(
                        row["AVS_EB"], field="AVS_EB", maximum=2000
                    ),
                    "engineering_bedrock_reference": int(row["AVS_REF"]),
                    "source_encoded_values": {"AVS": encoded_avs, "ARV": encoded_arv},
                    "value_status": "coastal_water_not_ground" if jcode == 0 else "modeled",
                }


class NpaTrafficAccidentAdapter:
    definition: OpenDataAdapterDefinition = OFFICIAL_SOURCE_REGISTRY.adapter(
        "npa-traffic-accident@2024"
    )
    index_url = NPA_INDEX_URL

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
        self.client.validate_url(self.index_url)

    def _html(self, url: str) -> tuple[str, dict[str, str]]:
        payload, headers = self.client.get_bytes(url, max_bytes=self.max_manifest_bytes)
        for encoding in ("utf-8", "cp932"):
            try:
                return payload.decode(encoding), headers
            except UnicodeDecodeError:
                pass
        raise ValueError("NPA manifest encoding is unsupported")

    def discover(self, request: DiscoveryRequest) -> tuple[DiscoveredResource, ...]:
        if len(request.municipality_code) != 5 or not request.municipality_code.isdigit():
            raise ValueError("NPA discovery requires a five-digit municipality code")
        index, _ = self._html(self.index_url)
        year_links = [
            (int(match["year"]), match["href"]) for match in _NPA_YEAR_LINK.finditer(index)
        ]
        if not year_links:
            raise ValueError("NPA index contains no annual open-data page")
        year, relative_page = max(year_links)
        annual_url = self.client.validate_url(urljoin(self.index_url, relative_page))
        annual, headers = self._html(annual_url)

        def required(pattern: re.Pattern[str], label: str) -> str:
            matches = [match for match in pattern.finditer(annual) if int(match["year"]) == year]
            if len(matches) != 1:
                raise ValueError(f"NPA annual page must expose exactly one {label}")
            return self.client.validate_url(urljoin(annual_url, matches[0]["href"]))

        main_url = required(_NPA_MAIN_LINK, "main table")
        schema_url = required(_NPA_SCHEMA_LINK, "schema workbook")
        codebook_url = required(_NPA_CODEBOOK_LINK, "codebook workbook")
        fingerprint = hashlib.sha256(
            json.dumps(
                {"year": year, "main": main_url, "schema": schema_url, "codebook": codebook_url},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return (
            DiscoveredResource(
                external_dataset_id=f"npa-traffic-accident-{year}-main",
                external_resource_id=f"honhyo_{year}.csv",
                title=f"交通事故統計情報オープンデータ {year}年 本票",
                resource_url=main_url,
                format="CSV",
                license_id="pdl-1.0",
                reference_date=None,
                version_signals=(str(year), fingerprint),
                source_metadata={
                    "annual_file_year": year,
                    "annual_page_url": annual_url,
                    "schema_url": schema_url,
                    "codebook_url": codebook_url,
                    "terms_url": NPA_TERMS_URL,
                    "annual_page_etag": headers.get("etag"),
                    "annual_page_last_modified": headers.get("last-modified"),
                    "selected_resource_fingerprint": fingerprint,
                    "scope": "injury_and_fatal_accidents; property-only accidents excluded",
                    "revision_note": "annual open data are not retroactively revised",
                },
            ),
        )

    def download(self, resource: DiscoveredResource, *, max_bytes: int) -> RawResourceReceipt:
        return self.object_store.fetch(self.client, resource.resource_url, max_bytes=max_bytes)

    @contextmanager
    def _text(self, receipt: RawResourceReceipt) -> Iterator[TextIO]:
        path = self.object_store.path_for_key(receipt.object_key)
        with (
            path.open("rb") as binary,
            io.TextIOWrapper(binary, encoding="cp932", newline="") as text,
        ):
            yield text

    def inspect_schema(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> SchemaInspection:
        row_count = 0
        occurrence_years: set[int] = set()
        with self._text(receipt) as stream:
            reader = csv.reader(stream)
            try:
                fields = tuple(next(reader))
            except StopIteration as error:
                raise ValueError("NPA main table is empty") from error
            if fields != NPA_FIELDS:
                raise ValueError("NPA main table does not match the exact 68-field schema")
            for values in reader:
                if len(values) != len(NPA_FIELDS):
                    raise ValueError("NPA row does not match the 68-field schema")
                if any(_formula_like(value) for value in values):
                    raise ValueError("NPA row contains spreadsheet formula-like content")
                row = dict(zip(NPA_FIELDS, values, strict=True))
                npa_dms_to_decimal(row["地点　緯度（北緯）"], longitude=False)
                npa_dms_to_decimal(row["地点　経度（東経）"], longitude=True)
                npa_occurrence_time(row)
                for field in ("死者数", "負傷者数"):
                    if not row[field].isdigit() or int(row[field]) < 0:
                        raise ValueError(f"NPA {field} is invalid")
                occurrence_years.add(int(row["発生日時　　年"]))
                row_count += 1
        if row_count == 0:
            raise ValueError("NPA main table contains no rows")
        return SchemaInspection(
            schema_version=f"npa-traffic-accident-main-table@{resource.source_metadata['annual_file_year']}",
            field_names=NPA_FIELDS,
            encoding="cp932",
            source_crs="EPSG:4326 (published world-geodetic DMS)",
            row_count=row_count,
            quality_results=(
                {"gate": "exact_fields", "status": "pass", "count": len(NPA_FIELDS)},
                {"gate": "coordinate_dms", "status": "pass"},
                {"gate": "event_time", "status": "pass", "years": sorted(occurrence_years)},
                {"gate": "formula_boundary", "status": "pass"},
            ),
        )

    def normalize(
        self,
        resource: DiscoveredResource,
        receipt: RawResourceReceipt,
        inspection: SchemaInspection,
    ) -> Iterator[dict[str, Any]]:
        if inspection.field_names != NPA_FIELDS:
            raise ValueError("NPA inspection does not match this adapter")
        with self._text(receipt) as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                if tuple(row) != NPA_FIELDS or None in row:
                    raise ValueError("NPA row shape changed after inspection")
                yield {
                    "external_record_id": "-".join(
                        (
                            str(resource.source_metadata["annual_file_year"]),
                            row["都道府県コード"],
                            row["警察署等コード"],
                            row["本票番号"],
                        )
                    ),
                    "annual_file_year": int(resource.source_metadata["annual_file_year"]),
                    "prefecture_code_npa": row["都道府県コード"],
                    "municipality_code_npa": row["市区町村コード"],
                    "occurred_at": npa_occurrence_time(row),
                    "longitude": npa_dms_to_decimal(
                        row["地点　経度（東経）"], longitude=True
                    ),
                    "latitude": npa_dms_to_decimal(
                        row["地点　緯度（北緯）"], longitude=False
                    ),
                    "fatalities": int(row["死者数"]),
                    "injuries": int(row["負傷者数"]),
                    "codes": {
                        "accident_severity": row["事故内容"],
                        "weather": row["天候"],
                        "terrain": row["地形"],
                        "road_surface": row["路面状態"],
                        "road_shape": row["道路形状"],
                        "pedestrian_road_separation": row["歩車道区分"],
                        "accident_type": row["事故類型"],
                        "party_a": row["当事者種別（当事者A）"],
                        "party_b": row["当事者種別（当事者B）"],
                    },
                    "scope": "historical injury/fatal accident record; property-only excluded",
                }
