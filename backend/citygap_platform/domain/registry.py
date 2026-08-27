"""City, dataset and capability registry invariants."""

from __future__ import annotations

from enum import Enum
from typing import Any

CAPABILITIES = (
    "screening",
    "building_detail",
    "road_network",
    "terrain",
    "land_use",
    "urban_planning",
    "hazard",
    "gtfs",
    "scenario",
    "temporal_diff",
    "future_population",
    "hazard_stress_test",
    "criticality",
    "evacuation_reachability",
    "planning_monitoring",
    "field_mode",
    "outcome_monitoring",
)


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


def validate_platform_registry(registry: dict[str, Any]) -> None:
    cities = registry.get("cities")
    if not isinstance(cities, list) or not cities:
        raise ValueError("Registry requires at least one city")
    codes = [str(city.get("city_code", "")) for city in cities]
    if len(codes) != len(set(codes)) or any(not code for code in codes):
        raise ValueError("Registry city codes must be non-empty and unique")

    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, list):
        raise TypeError("Registry capabilities must be a list")
    by_city: dict[str, dict[str, dict[str, Any]]] = {code: {} for code in codes}
    for row in capabilities:
        city_code = str(row.get("city_code", ""))
        capability = str(row.get("capability", ""))
        if city_code not in by_city or capability not in CAPABILITIES:
            raise ValueError("Unknown city or capability in registry")
        if capability in by_city[city_code]:
            raise ValueError("Duplicate city capability")
        try:
            status = CapabilityStatus(row.get("status"))
        except ValueError as error:
            raise ValueError("Unknown capability status") from error
        evidence = row.get("evidence", [])
        if status is not CapabilityStatus.UNAVAILABLE and not evidence:
            raise ValueError("Available or partial capability requires evidence")
        by_city[city_code][capability] = row
    for city_code, rows in by_city.items():
        if set(rows) != set(CAPABILITIES):
            raise ValueError(f"City {city_code} must declare every capability")

    datasets = registry.get("datasets", [])
    dataset_ids = {row.get("dataset_id") for row in datasets}
    if None in dataset_ids or len(dataset_ids) != len(datasets):
        raise ValueError("Dataset IDs must be present and unique")
    versions = registry.get("dataset_versions", [])
    version_ids = {row.get("dataset_version_id") for row in versions}
    if None in version_ids or len(version_ids) != len(versions):
        raise ValueError("Dataset version IDs must be present and unique")
    if any(row.get("dataset_id") not in dataset_ids for row in versions):
        raise ValueError("Dataset version references an unknown dataset")

    gtfs_versions = {
        row["dataset_version_id"]
        for row in versions
        if str(row.get("format", "")).lower() == "gtfs"
    }
    for row in capabilities:
        if row["capability"] == "gtfs" and row["status"] != "unavailable":
            references = set(row.get("dataset_version_ids", []))
            if not references & gtfs_versions:
                raise ValueError("GTFS capability cannot be claimed without a GTFS dataset version")
