"""Strict municipality-supplied target and external-cost input adapters."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from backend.citygap_platform.ingestion.adapters import CsvSourceAdapter

TARGET_TYPES = frozenset(
    {"population", "facility_coverage", "urban_function", "custom_numeric"}
)


@dataclass(frozen=True, slots=True)
class MunicipalTargetRecord:
    target_key: str
    target_type: str
    target_year: int
    target_value: float
    unit: str
    area_key: str
    source_record_id: str


@dataclass(frozen=True, slots=True)
class ExternalCostRecord:
    site_id: str
    cost: float
    year: int
    category: str
    currency: str
    source_record_id: str


def _year(value: str) -> int:
    if not re.fullmatch(r"\d{4}", value.strip()):
        raise ValueError("Municipal input year must contain four digits")
    year = int(value)
    if year < 1900 or year > 2200:
        raise ValueError("Municipal input year is outside the supported range")
    return year


def _non_negative_number(value: str, label: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{label} must be numeric") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return number


def load_municipal_targets(path: str | Path) -> tuple[MunicipalTargetRecord, ...]:
    adapter = CsvSourceAdapter(
        path,
        required_columns=(
            "target_key",
            "target_type",
            "target_year",
            "target_value",
            "unit",
            "area_key",
            "source_record_id",
        ),
    )
    records: list[MunicipalTargetRecord] = []
    for row in adapter.dataframe().itertuples(index=False):
        values = {
            name: str(getattr(row, name)).strip()
            for name in ("target_key", "target_type", "unit", "area_key", "source_record_id")
        }
        if not all(values.values()):
            raise ValueError("Municipal target identifiers, unit and area are required")
        if values["target_type"] not in TARGET_TYPES:
            raise ValueError("Municipal target type is unsupported")
        records.append(
            MunicipalTargetRecord(
                target_key=values["target_key"],
                target_type=values["target_type"],
                target_year=_year(str(row.target_year)),
                target_value=_non_negative_number(str(row.target_value), "target_value"),
                unit=values["unit"],
                area_key=values["area_key"],
                source_record_id=values["source_record_id"],
            )
        )
    keys = [record.target_key for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("Municipal target keys must be unique")
    return tuple(records)


def load_external_costs(path: str | Path) -> tuple[ExternalCostRecord, ...]:
    adapter = CsvSourceAdapter(
        path,
        required_columns=(
            "site_id",
            "cost",
            "year",
            "category",
            "currency",
            "source_record_id",
        ),
    )
    records: list[ExternalCostRecord] = []
    for row in adapter.dataframe().itertuples(index=False):
        values = {
            name: str(getattr(row, name)).strip()
            for name in ("site_id", "category", "currency", "source_record_id")
        }
        if not all(values.values()):
            raise ValueError("Cost site, category, currency and source record are required")
        records.append(
            ExternalCostRecord(
                site_id=values["site_id"],
                cost=_non_negative_number(str(row.cost), "cost"),
                year=_year(str(row.year)),
                category=values["category"],
                currency=values["currency"],
                source_record_id=values["source_record_id"],
            )
        )
    keys = [(record.site_id, record.year, record.category) for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("External cost site/year/category rows must be unique")
    return tuple(records)
