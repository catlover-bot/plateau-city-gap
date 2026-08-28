from dataclasses import replace

import pytest

from backend.citygap_platform.domain.open_data import (
    CatalogScope,
    CoverageStatus,
    DiscoveryMethod,
    DownloadMethod,
    LicensePolicy,
    OpenDataAdapterDefinition,
    OpenDataSourceDefinition,
    TemporalAlignment,
    UnavailableReason,
    classify_temporal_alignment,
    validate_coverage_reason,
)
from backend.citygap_platform.open_data.registry import OFFICIAL_SOURCE_REGISTRY


def test_unknown_license_never_permits_raw_publication() -> None:
    policy = LicensePolicy(
        "unknown",
        "条件未確認",
        "https://example.invalid/terms",
        None,
        None,
        None,
        None,
        None,
        True,
    )
    assert policy.permits_raw_publication is False


def test_redistribution_requires_explicit_true_and_known_terms() -> None:
    policy = LicensePolicy(
        "cc-by-4.0",
        "CC BY 4.0",
        "https://creativecommons.org/licenses/by/4.0/",
        True,
        True,
        True,
        False,
        True,
        False,
    )
    assert policy.permits_raw_publication is True


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (CoverageStatus.UNAVAILABLE, UnavailableReason.NOT_PUBLISHED),
        (CoverageStatus.REQUIRES_REVIEW, UnavailableReason.NOT_VERIFIED),
        (CoverageStatus.AVAILABLE, None),
        (CoverageStatus.PARTIAL, None),
        (CoverageStatus.UNKNOWN, None),
    ],
)
def test_coverage_reason_contract_accepts_only_consistent_pairs(
    status: CoverageStatus, reason: UnavailableReason | None
) -> None:
    validate_coverage_reason(status, reason)


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (CoverageStatus.UNAVAILABLE, None),
        (CoverageStatus.AVAILABLE, UnavailableReason.NOT_PUBLISHED),
    ],
)
def test_coverage_reason_contract_rejects_hidden_or_spurious_reasons(
    status: CoverageStatus, reason: UnavailableReason | None
) -> None:
    with pytest.raises(ValueError):
        validate_coverage_reason(status, reason)


def test_temporal_alignment_does_not_hide_mixed_or_unknown_years() -> None:
    assert classify_temporal_alignment((2025, 2025), 2026) is TemporalAlignment.ALIGNED
    assert classify_temporal_alignment((2020, 2026), 2026) is TemporalAlignment.MIXED
    assert classify_temporal_alignment((2020,), 2026) is TemporalAlignment.STALE
    assert classify_temporal_alignment((None, 2026), 2026) is TemporalAlignment.UNKNOWN


def test_adapter_requires_explicit_official_contract() -> None:
    adapter = OpenDataAdapterDefinition(
        adapter_id="municipal-standard-ods@2026-08",
        provider="デジタル庁",
        dataset_family="municipal_standard_ods",
        official_source=(
            "https://www.digital.go.jp/resources/open_data/municipal-standard-data-set-test"
        ),
        discovery_method=DiscoveryMethod.STATIC_CATALOG,
        download_method=DownloadMethod.HTTPS,
        schema_version="definition-a-b@2026-08-01",
        license_model="resource licence verified independently",
        supported_formats=("CSV", "XLSX"),
        spatial_granularity="dataset dependent",
        temporal_granularity="dataset dependent",
        crs_handling="schema declared",
        version_detection=("schema version", "SHA-256"),
        quality_rules=("required fields", "reference date"),
        capabilities_provided=("medical", "care"),
    )
    assert adapter.adapter_id.endswith("2026-08")


def test_adapter_rejects_non_official_transport_or_missing_rules() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        OpenDataAdapterDefinition(
            adapter_id="unsafe",
            provider="unknown",
            dataset_family="unknown",
            official_source="http://example.invalid",
            discovery_method=DiscoveryMethod.STATIC_CATALOG,
            download_method=DownloadMethod.HTTPS,
            schema_version="1",
            license_model="unknown",
            supported_formats=("CSV",),
            spatial_granularity="unknown",
            temporal_granularity="unknown",
            crs_handling="unknown",
            version_detection=("checksum",),
            quality_rules=("schema",),
            capabilities_provided=(),
        )


def test_source_contract_validates_scope_priority_and_municipality_code() -> None:
    source = OpenDataSourceDefinition(
        source_key="city-source",
        adapter_id="adapter@1",
        provider="Municipality",
        title="Official catalog",
        official_url="https://example.invalid/catalog",
        source_priority=1,
        default_license_id="cc-by-4.0",
        catalog_scope=CatalogScope.MUNICIPAL,
        municipality_code="26202",
    )
    assert source.municipality_code == "26202"
    with pytest.raises(ValueError, match="five-digit"):
        replace(source, municipality_code="262021")


def test_official_registry_is_unique_and_city_scoped() -> None:
    assert len(OFFICIAL_SOURCE_REGISTRY.adapters) == 7
    assert len(OFFICIAL_SOURCE_REGISTRY.sources) == 7
    maizuru = OFFICIAL_SOURCE_REGISTRY.sources_for_city("26202")
    fujisawa = OFFICIAL_SOURCE_REGISTRY.sources_for_city("14205")
    assert "bodik-maizuru" in {item.source_key for item in maizuru}
    assert "bodik-maizuru" not in {item.source_key for item in fujisawa}
    assert OFFICIAL_SOURCE_REGISTRY.adapter("ckan-v3@1").dataset_family == "catalog"
    assert (
        OFFICIAL_SOURCE_REGISTRY.source("fujisawa-open-data-library").adapter_id
        == "official-static-catalog@1"
    )
    assert (
        OFFICIAL_SOURCE_REGISTRY.adapter("mlit-future-population-250m@2024").dataset_family
        == "future_population"
    )
    assert (
        OFFICIAL_SOURCE_REGISTRY.source("estat-economic-census-2021-500m").default_license_id
        == "government-standard-terms-2.0"
    )
