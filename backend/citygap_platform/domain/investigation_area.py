"""Deterministic Investigation Area domain rules.

P0 deliberately models a walking *reference radius*, not a pedestrian
network isochrone. Geometry calculations use Maizuru's projected CRS and
persist GeoJSON in EPSG:4326.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform

AREA_RULE_VERSION = "citygap-investigation-area@1.0.0"
AREA_SUMMARY_SCHEMA_VERSION = "citygap.area-summary@1"
AREA_STORAGE_CRS = "EPSG:4326"
AREA_ANALYSIS_CRS = "EPSG:6674"
MIN_RADIUS_M = 100
MAX_RADIUS_M = 3000


class AreaGeometryKind(StrEnum):
    POINT_RADIUS = "point_radius"
    SOURCE_BOUNDARY = "source_boundary"
    MESH = "mesh"
    POLYGON = "polygon"  # P1
    PLATEAU_OBJECT_GROUP = "plateau_object_group"  # P1
    PEDESTRIAN_ISOCHRONE = "pedestrian_isochrone"  # P1, validated network only


class AreaOriginKind(StrEnum):
    MAP_POINT = "map_point"
    STATION = "station"
    FACILITY = "facility"
    SOURCE_FEATURE = "source_feature"
    NONE = "none"


class RadiusMethodology(StrEnum):
    MLIT_ELDERLY_WALK_REFERENCE_500M = "mlit_elderly_walk_reference_500m"
    MLIT_GENERAL_WALK_REFERENCE_800M = "mlit_general_walk_reference_800m"
    BROAD_CONTEXT_1000M = "broad_context_1000m"
    CUSTOM_RADIUS = "custom_radius"


class SourceBoundaryKind(StrEnum):
    CENSUS_2020_SMALL_AREA = "census_2020_small_area"


class AreaKnowledgeStatus(StrEnum):
    KNOWN = "known"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class AreaActionType(StrEnum):
    NONE = "none"
    DATA_ACQUISITION = "data_acquisition"
    FIELD_VERIFICATION = "field_verification"
    EXPERT_REVIEW = "expert_review"


class KnowledgeReason(StrEnum):
    NO_SOURCE = "no_source"
    COVERAGE_GAP = "coverage_gap"
    PRIVACY_SUPPRESSED = "privacy_suppressed"
    SOURCE_TIME_LIMIT = "source_time_limit"
    MODEL_LIMIT = "model_limit"
    OBJECT_SEMANTICS_LIMIT = "object_semantics_limit"
    REQUIRES_FIELD_OBSERVATION = "requires_field_observation"
    REQUIRES_EXPERT_JUDGMENT = "requires_expert_judgment"


_PRESET_RADIUS_BY_METHODOLOGY = {
    RadiusMethodology.MLIT_ELDERLY_WALK_REFERENCE_500M: 500,
    RadiusMethodology.MLIT_GENERAL_WALK_REFERENCE_800M: 800,
    RadiusMethodology.BROAD_CONTEXT_1000M: 1000,
}


def validate_radius(radius_m: object, methodology: RadiusMethodology) -> int:
    """Validate the intentionally small P0 radius contract."""

    if isinstance(radius_m, bool) or not isinstance(radius_m, int):
        raise TypeError("radius_m must be an integer number of metres")
    if not MIN_RADIUS_M <= radius_m <= MAX_RADIUS_M:
        raise ValueError(f"radius_m must be between {MIN_RADIUS_M} and {MAX_RADIUS_M}")
    expected = _PRESET_RADIUS_BY_METHODOLOGY.get(methodology)
    if expected is not None and radius_m != expected:
        raise ValueError(f"{methodology.value} requires radius_m={expected}")
    if methodology is RadiusMethodology.CUSTOM_RADIUS and radius_m in {500, 800, 1000}:
        raise ValueError("preset radii must use their versioned methodology")
    return radius_m


@dataclass(frozen=True)
class PointRadiusDefinition:
    origin_kind: AreaOriginKind
    longitude: float
    latitude: float
    radius_m: int
    radius_methodology: RadiusMethodology
    source_dataset_version_id: str | None = None
    source_feature_id: str | None = None

    def __post_init__(self) -> None:
        validate_radius(self.radius_m, self.radius_methodology)
        if self.origin_kind not in {AreaOriginKind.MAP_POINT, AreaOriginKind.STATION}:
            raise ValueError("P0 point_radius origin must be map_point or station")
        if self.origin_kind is AreaOriginKind.STATION and (
            not self.source_dataset_version_id or not self.source_feature_id
        ):
            raise ValueError("station origins require a versioned official source feature")
        if not -180 <= self.longitude <= 180 or not -90 <= self.latitude <= 90:
            raise ValueError("origin coordinates are outside EPSG:4326 bounds")


@dataclass(frozen=True)
class PointRadiusGeometry:
    requested_geometry: dict[str, Any]
    effective_geometry: dict[str, Any]
    clipped_area_ratio: float
    geometry_sha256: str


def build_point_radius_geometry(
    definition: PointRadiusDefinition,
    *,
    city_boundary: dict[str, Any] | None = None,
) -> PointRadiusGeometry:
    """Buffer in EPSG:6674 and optionally clip to a city boundary."""

    to_analysis = Transformer.from_crs(AREA_STORAGE_CRS, AREA_ANALYSIS_CRS, always_xy=True)
    to_storage = Transformer.from_crs(AREA_ANALYSIS_CRS, AREA_STORAGE_CRS, always_xy=True)
    projected_origin = transform(to_analysis.transform, Point(definition.longitude, definition.latitude))
    requested_projected = projected_origin.buffer(definition.radius_m, quad_segs=64)
    effective_projected = requested_projected
    if city_boundary is not None:
        boundary_projected = transform(to_analysis.transform, shape(city_boundary))
        effective_projected = requested_projected.intersection(boundary_projected)
        if effective_projected.is_empty:
            raise ValueError("Investigation Area is entirely outside the city boundary")
    clipped_ratio = effective_projected.area / requested_projected.area
    requested = mapping(transform(to_storage.transform, requested_projected))
    effective = mapping(transform(to_storage.transform, effective_projected))
    return PointRadiusGeometry(
        requested_geometry=requested,
        effective_geometry=effective,
        clipped_area_ratio=clipped_ratio,
        geometry_sha256=_canonical_sha256(effective),
    )


@dataclass(frozen=True)
class WeightedObservation:
    value: float | None
    overlap_ratio: float
    suppressed: bool = False


@dataclass(frozen=True)
class WeightedEstimate:
    value: float
    coverage_ratio: float
    contributing_records: int


def area_weighted_estimate(observations: Iterable[WeightedObservation]) -> WeightedEstimate:
    """Area weight available values without replacing missing/suppressed cells."""

    total = 0.0
    coverage = 0.0
    count = 0
    for observation in observations:
        ratio = max(0.0, min(1.0, observation.overlap_ratio))
        if observation.value is None or observation.suppressed:
            continue
        total += observation.value * ratio
        coverage += ratio
        count += 1
    return WeightedEstimate(total, min(1.0, coverage), count)


@dataclass(frozen=True)
class AreaKnowledgeItem:
    key: str
    status: AreaKnowledgeStatus
    action_type: AreaActionType
    reason_code: KnowledgeReason
    importance: str
    decision_impact: int
    source_references: tuple[str, ...]
    coverage_ratio: float | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.decision_impact <= 100:
            raise ValueError("decision_impact must be between 0 and 100")
        if not self.source_references:
            raise ValueError("source_references must preserve the source boundary")
        if self.coverage_ratio is not None and not 0 <= self.coverage_ratio <= 1:
            raise ValueError("coverage_ratio must be between 0 and 1")
        if self.status is AreaKnowledgeStatus.KNOWN and self.coverage_ratio not in {None, 1.0}:
            raise ValueError("known items cannot claim partial coverage")
        if self.action_type is AreaActionType.FIELD_VERIFICATION and self.status not in {
            AreaKnowledgeStatus.PARTIAL,
            AreaKnowledgeStatus.UNKNOWN,
        }:
            raise ValueError("only partial/unknown knowledge can require field verification")


def select_important_unknowns(
    items: Iterable[AreaKnowledgeItem], *, limit: int = 4
) -> tuple[AreaKnowledgeItem, ...]:
    """Select only field-verifiable unknowns; never inflate other gaps into tasks."""

    if not 1 <= limit <= 4:
        raise ValueError("public unknown limit must be between 1 and 4")
    eligible = (
        item
        for item in items
        if item.status in {AreaKnowledgeStatus.PARTIAL, AreaKnowledgeStatus.UNKNOWN}
        and item.action_type is AreaActionType.FIELD_VERIFICATION
    )
    return tuple(sorted(eligible, key=lambda item: (-item.decision_impact, item.key))[:limit])


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
