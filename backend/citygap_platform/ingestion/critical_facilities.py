"""Verified official evacuation-shelter adapter; no missing capacity is inferred."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path

from backend.citygap_platform.ingestion.adapters import GeoJsonSourceAdapter

SHELTER_COLUMNS = (
    "名称",
    "住所",
    "施設の種類",
    "収容人数",
    "対象とする災害の分類",
    "行政区域",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class OfficialShelterRecord:
    facility_key: str
    city_code: str
    name: str
    address: str
    facility_type: str
    capacity: int | None
    hazard_applicability: tuple[str, ...]
    longitude: float
    latitude: float
    source_year: int
    source_url: str
    source_sha256: str
    source_verified: bool = True


@dataclass(frozen=True, slots=True)
class OfficialShelterInspection:
    city_code: str
    feature_count: int
    capacity_available_count: int
    capacity_missing_count: int
    declared_capacity_total: int
    facility_types: tuple[str, ...]
    hazard_applicability_values: tuple[str, ...]
    source_year: int
    source_url: str
    source_sha256: str


class OfficialShelterAdapter:
    def __init__(
        self,
        path: str | Path,
        *,
        city_code: str,
        source_year: int,
        source_url: str,
        expected_sha256: str,
    ) -> None:
        if not re.fullmatch(r"\d{5}", city_code):
            raise ValueError("Shelter source requires a five-digit municipality code")
        if not source_url.startswith("https://"):
            raise ValueError("Shelter source requires an HTTPS provenance URL")
        self.path = Path(path).resolve(strict=True)
        actual_hash = _sha256(self.path)
        if actual_hash != expected_sha256:
            raise ValueError("Shelter source SHA-256 does not match registered provenance")
        self.city_code = city_code
        self.source_year = source_year
        self.source_url = source_url
        self.source_sha256 = actual_hash
        self._adapter = GeoJsonSourceAdapter(
            self.path,
            required_columns=SHELTER_COLUMNS,
            declared_crs="EPSG:4326",
        )

    @staticmethod
    def _capacity(value: object) -> int | None:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        text = str(value).strip()
        if not text:
            return None
        if not text.isdigit():
            raise ValueError("Shelter capacity must be an official non-negative integer")
        return int(text)

    @staticmethod
    def _hazards(value: object) -> tuple[str, ...]:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return ()
        text = str(value).strip()
        if not text:
            return ()
        return tuple(part.strip() for part in re.split(r"[・、,]", text) if part.strip())

    def records(self) -> tuple[OfficialShelterRecord, ...]:
        frame = self._adapter.dataframe().to_crs(4326)
        records = []
        for row in frame.itertuples(index=False):
            row_city = str(row.行政区域)
            if row_city != self.city_code:
                raise ValueError("Shelter record municipality does not match the registered city")
            name = str(row.名称).strip()
            address = str(row.住所).strip()
            facility_type = str(row.施設の種類).strip()
            if not name or not facility_type or row.geometry.geom_type != "Point":
                raise ValueError("Shelter records require a name, type and point geometry")
            stable = "\0".join(
                (
                    self.city_code,
                    name,
                    address,
                    f"{row.geometry.x:.8f}",
                    f"{row.geometry.y:.8f}",
                )
            ).encode()
            records.append(
                OfficialShelterRecord(
                    facility_key=f"shelter::{hashlib.sha256(stable).hexdigest()[:20]}",
                    city_code=self.city_code,
                    name=name,
                    address=address,
                    facility_type=facility_type,
                    capacity=self._capacity(row.収容人数),
                    hazard_applicability=self._hazards(row.対象とする災害の分類),
                    longitude=float(row.geometry.x),
                    latitude=float(row.geometry.y),
                    source_year=self.source_year,
                    source_url=self.source_url,
                    source_sha256=self.source_sha256,
                )
            )
        keys = [record.facility_key for record in records]
        if len(keys) != len(set(keys)):
            raise ValueError("Shelter stable keys must be unique")
        return tuple(sorted(records, key=lambda record: record.facility_key))

    def inspect(self) -> OfficialShelterInspection:
        records = self.records()
        capacities = [record.capacity for record in records if record.capacity is not None]
        return OfficialShelterInspection(
            city_code=self.city_code,
            feature_count=len(records),
            capacity_available_count=len(capacities),
            capacity_missing_count=len(records) - len(capacities),
            declared_capacity_total=sum(capacities),
            facility_types=tuple(sorted({record.facility_type for record in records})),
            hazard_applicability_values=tuple(
                sorted({value for record in records for value in record.hazard_applicability})
            ),
            source_year=self.source_year,
            source_url=self.source_url,
            source_sha256=self.source_sha256,
        )
