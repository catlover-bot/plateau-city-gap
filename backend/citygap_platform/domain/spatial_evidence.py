"""Contracts for reproducible, tenant-scoped spatial evidence delivery.

The contracts deliberately keep source objects, model relations and scenario
changes distinct.  A public pack is also checked for building-level model
fields before it can be published.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class SpatialPackStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    BUILDING = "building"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


PACK_STAGE_ORDER = (
    SpatialPackStatus.QUEUED,
    SpatialPackStatus.EXTRACTING,
    SpatialPackStatus.BUILDING,
    SpatialPackStatus.VALIDATING,
    SpatialPackStatus.READY,
)


@dataclass(frozen=True, slots=True)
class SpatialEvidencePack:
    pack_id: str
    organization_id: str
    city_id: str
    urban_state_id: str
    investigation_id: str
    geometry_geojson: dict[str, Any]
    bbox: tuple[float, float, float, float]
    buffer_m: float
    status: SpatialPackStatus
    data_classification: DataClassification
    source_dataset_versions: tuple[str, ...]
    network_version_id: str | None
    analysis_run_ids: tuple[str, ...]
    created_by: str
    created_at: datetime
    superseded_by: str | None = None
    content_hash: str | None = None
    manifest_hash: str | None = None

    def __post_init__(self) -> None:
        west, south, east, north = self.bbox
        if not all(math.isfinite(value) for value in self.bbox) or west >= east or south >= north:
            raise ValueError("Spatial pack bbox must be finite west,south,east,north")
        if not math.isfinite(self.buffer_m) or self.buffer_m < 0:
            raise ValueError("Spatial pack buffer must be a finite non-negative distance")
        if self.geometry_geojson.get("type") not in {
            "Polygon", "MultiPolygon", "LineString", "MultiLineString"
        }:
            raise ValueError("Spatial pack geometry must be a bounded polygon or line")
        if not self.source_dataset_versions:
            raise ValueError("Spatial pack requires source dataset versions")
        for value in (self.content_hash, self.manifest_hash):
            if value is not None and not _is_sha256(value):
                raise ValueError("Spatial pack hashes must be lowercase SHA-256")
        if self.status is SpatialPackStatus.READY and not (self.content_hash and self.manifest_hash):
            raise ValueError("A ready spatial pack requires content and manifest hashes")
        if self.status is SpatialPackStatus.SUPERSEDED and not self.superseded_by:
            raise ValueError("A superseded spatial pack requires its successor")


@dataclass(frozen=True, slots=True)
class UrbanTransect:
    transect_id: str
    pack_id: str
    organization_id: str
    geometry_geojson: dict[str, Any]
    buffer_m: float
    sample_interval_m: float
    vertical_datum: str
    terrain_source: str
    created_by: str
    created_at: datetime

    def __post_init__(self) -> None:
        coordinates = self.geometry_geojson.get("coordinates")
        if self.geometry_geojson.get("type") != "LineString" or not isinstance(coordinates, list):
            raise ValueError("Urban transect must be a GeoJSON LineString")
        if len(coordinates) < 2 or any(not _coordinate_ok(point) for point in coordinates):
            raise ValueError("Urban transect requires at least two finite lon/lat coordinates")
        if self.buffer_m < 0 or not math.isfinite(self.buffer_m):
            raise ValueError("Urban transect buffer must be non-negative")
        if self.sample_interval_m <= 0 or not math.isfinite(self.sample_interval_m):
            raise ValueError("Urban transect sample interval must be positive")
        if not self.vertical_datum or not self.terrain_source:
            raise ValueError("Urban transect must record vertical datum and terrain source")


def transition_pack(current: SpatialPackStatus, proposed: SpatialPackStatus) -> None:
    """Validate the durable pack lifecycle; retry starts a new pack/version."""

    if current in {SpatialPackStatus.FAILED, SpatialPackStatus.SUPERSEDED}:
        raise ValueError(f"Terminal spatial pack cannot transition from {current.value}")
    if current is SpatialPackStatus.READY:
        if proposed is not SpatialPackStatus.SUPERSEDED:
            raise ValueError("A ready spatial pack can only be superseded")
        return
    if proposed is SpatialPackStatus.FAILED:
        return
    expected = PACK_STAGE_ORDER[PACK_STAGE_ORDER.index(current) + 1]
    if proposed is not expected:
        raise ValueError(f"Spatial pack transition must advance to {expected.value}")


PUBLIC_BUILDING_MODEL_FIELDS = frozenset(
    {
        "estimated_population",
        "estimated_elderly_population",
        "estimated_households",
        "population_model_value",
        "model_population",
        "allocated_population",
        "allocation_weight",
    }
)


def assert_public_pack_safe(objects: Iterable[dict[str, Any]]) -> None:
    """Reject public objects containing per-building demographic model output."""

    leaks: list[str] = []

    def inspect(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else key
                if key.casefold() in PUBLIC_BUILDING_MODEL_FIELDS:
                    leaks.append(child_path)
                inspect(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                inspect(child, f"{path}[{index}]")

    for index, item in enumerate(objects):
        inspect(item, f"objects[{index}]")
    if leaks:
        raise ValueError("Public spatial pack contains restricted model fields: " + ", ".join(leaks))


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _coordinate_ok(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(isinstance(part, (int, float)) and math.isfinite(part) for part in value[:2])
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
