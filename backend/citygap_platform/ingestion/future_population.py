"""Official future-population adapters and PLATEAU capacity allocation boundary."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

ProjectionKind = Literal["official_demographic_projection", "municipal_official_projection"]
REQUIRED_COLUMNS = (
    "city_code",
    "city_name",
    "projection_series",
    "year",
    "total_population",
    "age_0_14",
    "age_15_64",
    "age_65_plus",
    "age_65_74",
    "age_75_plus",
    "publisher",
    "projection_kind",
    "source_url",
    "source_sha256",
    "published_date",
    "source_verified",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ProjectionRecord:
    city_code: str
    city_name: str
    projection_series: str
    year: int
    total_population: int
    age_0_14: int
    age_15_64: int
    age_65_plus: int
    age_65_74: int
    age_75_plus: int
    publisher: str
    projection_kind: ProjectionKind
    source_url: str
    source_sha256: str
    published_date: str
    source_verified: bool

    def __post_init__(self) -> None:
        if not re.fullmatch(r"\d{5}", self.city_code):
            raise ValueError("Projection city code must be five digits")
        if self.year < 2020 or self.year > 2200:
            raise ValueError("Projection year is outside the platform range")
        if min(
            self.total_population,
            self.age_0_14,
            self.age_15_64,
            self.age_65_plus,
            self.age_65_74,
            self.age_75_plus,
        ) < 0:
            raise ValueError("Official projection values cannot be negative")
        if self.age_0_14 + self.age_15_64 + self.age_65_plus != self.total_population:
            raise ValueError("Official projection age groups must conserve total population")
        if self.age_65_74 + self.age_75_plus != self.age_65_plus:
            raise ValueError("Official elderly age groups must conserve age 65+ population")
        if not self.source_verified:
            raise ValueError("Future state adapter accepts verified official sources only")
        if not self.source_url.startswith("https://") or not re.fullmatch(
            r"[0-9a-f]{64}", self.source_sha256
        ):
            raise ValueError("Projection requires HTTPS provenance and a SHA-256 source hash")


class OfficialFuturePopulationAdapter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve(strict=True)
        frame = pd.read_csv(self.path, dtype={"city_code": str})
        missing = set(REQUIRED_COLUMNS) - set(frame.columns)
        if missing:
            raise ValueError(f"Official projection CSV is missing columns: {sorted(missing)}")
        self._records = tuple(self._record(row) for row in frame.to_dict("records"))
        keys = [(row.city_code, row.projection_series, row.year) for row in self._records]
        if len(keys) != len(set(keys)):
            raise ValueError("Official projection city/series/year keys must be unique")

    @staticmethod
    def _record(row: dict[str, object]) -> ProjectionRecord:
        kind = str(row["projection_kind"])
        if kind not in {"official_demographic_projection", "municipal_official_projection"}:
            raise ValueError("Unsupported projection kind")
        return ProjectionRecord(
            city_code=str(row["city_code"]),
            city_name=str(row["city_name"]),
            projection_series=str(row["projection_series"]),
            year=int(row["year"]),
            total_population=int(row["total_population"]),
            age_0_14=int(row["age_0_14"]),
            age_15_64=int(row["age_15_64"]),
            age_65_plus=int(row["age_65_plus"]),
            age_65_74=int(row["age_65_74"]),
            age_75_plus=int(row["age_75_plus"]),
            publisher=str(row["publisher"]),
            projection_kind=kind,  # type: ignore[arg-type]
            source_url=str(row["source_url"]),
            source_sha256=str(row["source_sha256"]),
            published_date=str(row["published_date"]),
            source_verified=str(row["source_verified"]).strip().lower() == "true",
        )

    @property
    def normalized_sha256(self) -> str:
        return _sha256(self.path)

    def records(
        self, city_code: str, projection_series: str | None = None
    ) -> tuple[ProjectionRecord, ...]:
        rows = tuple(
            row
            for row in self._records
            if row.city_code == city_code
            and (projection_series is None or row.projection_series == projection_series)
        )
        if not rows:
            raise KeyError("No official projection rows match the requested city/series")
        return tuple(sorted(rows, key=lambda row: (row.projection_series, row.year)))


class IpssWorkbookAdapter:
    """Verify the official IPSS workbook and extract only published municipality years."""

    def __init__(self, path: str | Path, expected_sha256: str) -> None:
        self.path = Path(path).resolve(strict=True)
        if _sha256(self.path) != expected_sha256:
            raise ValueError("IPSS workbook SHA-256 does not match registered provenance")

    def municipality(self, city_code: str) -> tuple[dict[str, int], ...]:
        frame = pd.read_excel(self.path, sheet_name="Sheet1", header=None)
        rows = frame.loc[frame.iloc[:, 0].astype(str).eq(city_code)]
        if rows.empty:
            raise KeyError(f"Municipality is absent from IPSS workbook: {city_code}")
        result = []
        for row in rows.itertuples(index=False, name=None):
            year = int(str(row[4]).removesuffix("年"))
            result.append(
                {
                    "year": year,
                    "total_population": int(row[5]),
                    "age_0_14": int(row[73]),
                    "age_15_64": int(row[74]),
                    "age_65_plus": int(row[75]),
                    "age_65_74": int(row[76]),
                    "age_75_plus": int(row[77]),
                }
            )
        return tuple(result)


def allocate_projection_to_buildings(
    buildings: pd.DataFrame, projection: ProjectionRecord
) -> pd.DataFrame:
    """Allocate official city totals by declared residential capacity, without prediction."""

    required = {"building_id", "mesh_code", "capacity_weight"}
    missing = required - set(buildings.columns)
    if missing:
        raise ValueError(f"Building capacity input is missing columns: {sorted(missing)}")
    output = buildings.loc[:, ["building_id", "mesh_code", "capacity_weight"]].copy()
    output["capacity_weight"] = pd.to_numeric(output["capacity_weight"], errors="raise")
    if (~output["capacity_weight"].map(math.isfinite)).any() or (
        output["capacity_weight"] < 0
    ).any():
        raise ValueError("Building capacity weights must be finite and non-negative")
    total_weight = float(output["capacity_weight"].sum())
    if total_weight <= 0:
        raise ValueError("Building capacity weights must have a positive sum")
    fraction = output["capacity_weight"] / total_weight
    output["estimated_future_population"] = fraction * projection.total_population
    output["estimated_future_elderly_population"] = fraction * projection.age_65_plus
    output["projection_year"] = projection.year
    output["projection_series"] = projection.projection_series
    output["population_semantics"] = (
        "official demographic projection + CITY GAP PLATEAU residential-capacity allocation"
    )
    return output


def future_accessibility_summary(
    allocation: pd.DataFrame,
    accessibility: pd.DataFrame,
    *,
    transport_burden_m: float = 1000.0,
    medical_burden_m: float = 2000.0,
) -> dict[str, float | int | str]:
    required = {
        "building_id",
        "estimated_future_population",
        "estimated_future_elderly_population",
    }
    if required - set(allocation.columns):
        raise ValueError("Future allocation is missing required values")
    access_required = {"building_id", "transport_distance_m", "medical_distance_m"}
    if access_required - set(accessibility.columns):
        raise ValueError("Accessibility input is missing fixed-service distances")
    merged = allocation.merge(accessibility, on="building_id", how="left", validate="one_to_one")
    transport = pd.to_numeric(merged["transport_distance_m"], errors="coerce")
    medical = pd.to_numeric(merged["medical_distance_m"], errors="coerce")
    transport_burden = transport.isna() | transport.gt(transport_burden_m)
    medical_burden = medical.isna() | medical.gt(medical_burden_m)
    return {
        "projection_year": int(merged["projection_year"].iloc[0]),
        "projection_series": str(merged["projection_series"].iloc[0]),
        "fixed_service_assumption": True,
        "estimated_population_transport_burden": float(
            merged.loc[transport_burden, "estimated_future_population"].sum()
        ),
        "estimated_elderly_transport_burden": float(
            merged.loc[transport_burden, "estimated_future_elderly_population"].sum()
        ),
        "estimated_population_medical_burden": float(
            merged.loc[medical_burden, "estimated_future_population"].sum()
        ),
        "estimated_elderly_medical_burden": float(
            merged.loc[medical_burden, "estimated_future_elderly_population"].sum()
        ),
        "limitation": "official population scenario under fixed service assumptions",
    }
