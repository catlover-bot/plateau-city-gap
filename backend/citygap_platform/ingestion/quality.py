"""Evidence-based dataset quality gate; failed inputs never become analysis-ready."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    minimum_feature_count: int = 1
    maximum_invalid_geometry_fraction: float = 0.0
    minimum_codelist_resolution: float = 0.95
    minimum_spatial_coverage: float = 0.95
    required_attribute_coverage: dict[str, float] = field(default_factory=dict)
    allowed_crs: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class QualityMeasurements:
    feature_count: int
    invalid_geometry_count: int
    crs: str | None
    resolved_code_count: int = 0
    coded_feature_count: int = 0
    spatial_coverage: float | None = None
    attribute_coverage: dict[str, float] = field(default_factory=dict)
    duplicate_id_count: int = 0


@dataclass(frozen=True, slots=True)
class QualityReport:
    status: str
    analysis_ready: bool
    reasons: tuple[str, ...]
    measurements: QualityMeasurements
    thresholds: QualityThresholds

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["thresholds"]["allowed_crs"] = sorted(self.thresholds.allowed_crs)
        return payload


def evaluate_quality(
    measurements: QualityMeasurements, thresholds: QualityThresholds | None = None
) -> QualityReport:
    thresholds = thresholds or QualityThresholds()
    reasons: list[str] = []
    count = measurements.feature_count
    if count < thresholds.minimum_feature_count:
        reasons.append("feature_count_below_minimum")
    invalid_fraction = measurements.invalid_geometry_count / count if count else 1.0
    if invalid_fraction > thresholds.maximum_invalid_geometry_fraction:
        reasons.append("invalid_geometry_fraction_exceeded")
    if measurements.crs is None:
        reasons.append("crs_missing")
    elif thresholds.allowed_crs and measurements.crs not in thresholds.allowed_crs:
        reasons.append("crs_not_allowed")
    if measurements.duplicate_id_count:
        reasons.append("duplicate_feature_ids")
    if measurements.coded_feature_count:
        resolution = measurements.resolved_code_count / measurements.coded_feature_count
        if resolution < thresholds.minimum_codelist_resolution:
            reasons.append("codelist_resolution_below_minimum")
    if (
        measurements.spatial_coverage is not None
        and measurements.spatial_coverage < thresholds.minimum_spatial_coverage
    ):
        reasons.append("spatial_coverage_below_minimum")
    for attribute, minimum in sorted(thresholds.required_attribute_coverage.items()):
        if measurements.attribute_coverage.get(attribute, 0.0) < minimum:
            reasons.append(f"required_attribute_coverage:{attribute}")
    passed = not reasons
    return QualityReport(
        status="passed" if passed else "failed",
        analysis_ready=False,
        reasons=tuple(reasons),
        measurements=measurements,
        thresholds=thresholds,
    )
