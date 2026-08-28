"""Municipal open-data domain contracts.

The registry describes how an official source can be discovered and validated.  It
does not make a discovered resource analysis-ready, choose between competing official
sources, or treat an unknown licence as permission to redistribute bytes.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class DiscoveryMethod(str, Enum):
    STATIC_CATALOG = "static_catalog"
    CKAN_API = "ckan_api"
    OFFICIAL_API = "official_api"
    OFFICIAL_MANIFEST = "official_manifest"


class DownloadMethod(str, Enum):
    HTTPS = "https"
    CKAN_RESOURCE = "ckan_resource"
    API_EXPORT = "api_export"


class CoverageStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    REQUIRES_REVIEW = "requires_review"


class UnavailableReason(str, Enum):
    NOT_PUBLISHED = "not_published"
    OUTSIDE_COVERAGE = "outside_coverage"
    LICENSE_BLOCKED = "license_blocked"
    SCHEMA_UNSUPPORTED = "schema_unsupported"
    RETRIEVAL_FAILED = "retrieval_failed"
    REQUIRES_CREDENTIALS = "requires_credentials"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    NOT_VERIFIED = "not_verified"


class TemporalAlignment(str, Enum):
    ALIGNED = "aligned"
    MIXED = "mixed"
    STALE = "stale"
    UNKNOWN = "unknown"


class CanonicalRecordType(str, Enum):
    POPULATION_OBSERVATION = "population_observation"
    ACTIVITY_OBSERVATION = "activity_observation"
    FACILITY = "facility"
    SERVICE_OFFERING = "service_offering"
    TRANSPORT_NODE = "transport_node"
    TRANSPORT_OBSERVATION = "transport_observation"
    ROAD_OBSERVATION = "road_observation"
    HAZARD_AREA = "hazard_area"
    GROUND_OBSERVATION = "ground_observation"
    PLANNING_AREA = "planning_area"
    MOBILITY_OBSERVATION = "mobility_observation"


class SpatialMatchMethod(str, Enum):
    EXACT = "exact"
    DETERMINISTIC = "deterministic"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


class CatalogScope(str, Enum):
    NATIONAL = "national"
    PREFECTURAL = "prefectural"
    MUNICIPAL = "municipal"


@dataclass(frozen=True, slots=True)
class LicensePolicy:
    license_id: str
    license_name: str
    license_url: str
    commercial_use: bool | None
    redistribution: bool | None
    attribution_required: bool | None
    share_alike: bool | None
    derivative_allowed: bool | None
    unknown_terms: bool

    @property
    def permits_raw_publication(self) -> bool:
        return self.redistribution is True and not self.unknown_terms


@dataclass(frozen=True, slots=True)
class OpenDataAdapterDefinition:
    adapter_id: str
    provider: str
    dataset_family: str
    official_source: str
    discovery_method: DiscoveryMethod
    download_method: DownloadMethod
    schema_version: str
    license_model: str
    supported_formats: tuple[str, ...]
    spatial_granularity: str
    temporal_granularity: str
    crs_handling: str
    version_detection: tuple[str, ...]
    quality_rules: tuple[str, ...]
    capabilities_provided: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.adapter_id or not self.provider or not self.dataset_family:
            raise ValueError("Adapter identity, provider and dataset family are required")
        if not self.official_source.startswith("https://"):
            raise ValueError("Official source must use HTTPS")
        if not self.supported_formats or not self.quality_rules:
            raise ValueError("Adapters require declared formats and quality rules")
        if not self.version_detection:
            raise ValueError("Adapters require an explicit version detection contract")


@dataclass(frozen=True, slots=True)
class OpenDataSourceDefinition:
    source_key: str
    adapter_id: str
    provider: str
    title: str
    official_url: str
    source_priority: int
    default_license_id: str
    catalog_scope: CatalogScope
    municipality_code: str | None = None

    def __post_init__(self) -> None:
        if not self.source_key or not self.adapter_id or not self.provider or not self.title:
            raise ValueError("Source identity, adapter, provider and title are required")
        if not self.official_url.startswith("https://"):
            raise ValueError("Official source must use HTTPS")
        if not 1 <= self.source_priority <= 4:
            raise ValueError("Source priority must be between 1 and 4")
        if self.municipality_code is not None and (
            len(self.municipality_code) != 5 or not self.municipality_code.isdigit()
        ):
            raise ValueError("Municipality code must be a five-digit code")


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    municipality_code: str
    city_name: str


@dataclass(frozen=True, slots=True)
class DiscoveredResource:
    external_dataset_id: str
    external_resource_id: str
    title: str
    resource_url: str
    format: str
    license_id: str
    reference_date: str | None
    version_signals: tuple[str, ...]
    source_metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RawResourceReceipt:
    sha256: str
    size_bytes: int
    content_type: str
    object_key: str
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class SchemaInspection:
    schema_version: str
    field_names: tuple[str, ...]
    encoding: str
    source_crs: str | None
    row_count: int | None
    quality_results: tuple[dict[str, Any], ...]


@runtime_checkable
class OpenDataAdapter(Protocol):
    """Executable boundary for one immutable, versioned adapter definition."""

    definition: OpenDataAdapterDefinition

    def discover(self, request: DiscoveryRequest) -> tuple[DiscoveredResource, ...]: ...

    def download(self, resource: DiscoveredResource, *, max_bytes: int) -> RawResourceReceipt: ...

    def inspect_schema(
        self, resource: DiscoveredResource, receipt: RawResourceReceipt
    ) -> SchemaInspection: ...

    def normalize(
        self,
        resource: DiscoveredResource,
        receipt: RawResourceReceipt,
        inspection: SchemaInspection,
    ) -> Iterator[dict[str, Any]]: ...


def validate_coverage_reason(status: CoverageStatus, reason: UnavailableReason | None) -> None:
    requires_reason = status in {CoverageStatus.UNAVAILABLE, CoverageStatus.REQUIRES_REVIEW}
    if requires_reason != (reason is not None):
        raise ValueError("Unavailable/review coverage requires exactly one explicit reason")


def classify_temporal_alignment(
    reference_years: tuple[int | None, ...], current_year: int
) -> TemporalAlignment:
    if not reference_years or any(year is None for year in reference_years):
        return TemporalAlignment.UNKNOWN
    years = {int(year) for year in reference_years if year is not None}
    if len(years) > 1:
        return TemporalAlignment.MIXED
    year = next(iter(years))
    if current_year - year > 5:
        return TemporalAlignment.STALE
    return TemporalAlignment.ALIGNED
