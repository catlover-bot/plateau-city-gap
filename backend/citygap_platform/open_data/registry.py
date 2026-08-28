"""Versioned registry of reviewed official open-data entry points.

Registry membership only means that CITY GAP knows how to start discovery. Every
resource still needs an explicit licence decision, checksum, schema inspection and
promotion before an analysis can consume it.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.citygap_platform.domain.open_data import (
    CatalogScope,
    DiscoveryMethod,
    DownloadMethod,
    OpenDataAdapterDefinition,
    OpenDataSourceDefinition,
)


@dataclass(frozen=True, slots=True)
class OfficialSourceRegistry:
    adapters: tuple[OpenDataAdapterDefinition, ...]
    sources: tuple[OpenDataSourceDefinition, ...]

    def __post_init__(self) -> None:
        adapter_ids = [item.adapter_id for item in self.adapters]
        source_keys = [item.source_key for item in self.sources]
        if len(adapter_ids) != len(set(adapter_ids)):
            raise ValueError("Adapter identifiers must be unique")
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("Source keys must be unique")
        missing = {item.adapter_id for item in self.sources} - set(adapter_ids)
        if missing:
            raise ValueError(f"Sources reference unknown adapters: {sorted(missing)}")

    def adapter(self, adapter_id: str) -> OpenDataAdapterDefinition:
        return next(item for item in self.adapters if item.adapter_id == adapter_id)

    def source(self, source_key: str) -> OpenDataSourceDefinition:
        return next(item for item in self.sources if item.source_key == source_key)

    def sources_for_city(self, municipality_code: str) -> tuple[OpenDataSourceDefinition, ...]:
        return tuple(
            item for item in self.sources if item.municipality_code in (None, municipality_code)
        )


ADAPTERS = (
    OpenDataAdapterDefinition(
        adapter_id="municipal-standard-ods@2026-08",
        provider="デジタル庁",
        dataset_family="municipal_standard_ods",
        official_source=(
            "https://www.digital.go.jp/resources/open_data/municipal-standard-data-set-test"
        ),
        discovery_method=DiscoveryMethod.STATIC_CATALOG,
        download_method=DownloadMethod.HTTPS,
        schema_version="definition-a-b@2026-08-01",
        license_model="resource licence must be verified independently",
        supported_formats=("CSV", "XLSX"),
        spatial_granularity="dataset dependent",
        temporal_granularity="dataset dependent",
        crs_handling="schema-declared coordinates or address; never inferred",
        version_detection=("schema version", "Last-Modified", "SHA-256"),
        quality_rules=(
            "required fields",
            "known aliases",
            "encoding",
            "coordinate semantics",
            "reference date",
        ),
        capabilities_provided=(
            "population",
            "facilities",
            "medical",
            "care",
            "education",
            "childcare",
            "shelter",
            "aed",
        ),
    ),
    OpenDataAdapterDefinition(
        adapter_id="ckan-v3@1",
        provider="CKAN",
        dataset_family="catalog",
        official_source="https://docs.ckan.org/en/2.11/api/",
        discovery_method=DiscoveryMethod.CKAN_API,
        download_method=DownloadMethod.CKAN_RESOURCE,
        schema_version="ckan-package-v3",
        license_model="package/resource licence retained without override",
        supported_formats=("CSV", "GeoJSON", "XLSX", "ZIP"),
        spatial_granularity="resource dependent",
        temporal_granularity="resource modified timestamp",
        crs_handling="declared CRS or validated content",
        version_detection=("metadata_modified", "last_modified", "ETag", "SHA-256"),
        quality_rules=("package identity", "resource URL", "format", "licence", "modified"),
        capabilities_provided=(),
    ),
    OpenDataAdapterDefinition(
        adapter_id="official-static-catalog@1",
        provider="Municipality",
        dataset_family="catalog",
        official_source="https://www.city.fujisawa.kanagawa.jp/",
        discovery_method=DiscoveryMethod.STATIC_CATALOG,
        download_method=DownloadMethod.HTTPS,
        schema_version="section-link-catalog@1",
        license_model="linked resource licence must be verified independently",
        supported_formats=("HTML",),
        spatial_granularity="linked resource dependent",
        temporal_granularity="catalog page update",
        crs_handling="linked resource must declare CRS independently",
        version_detection=("catalog SHA-256", "linked URL", "resource metadata"),
        quality_rules=("official catalog", "section label", "HTTPS link", "resource terms"),
        capabilities_provided=(),
    ),
    OpenDataAdapterDefinition(
        adapter_id="mhlw-medical@2026-06",
        provider="厚生労働省 医療情報ネット",
        dataset_family="medical",
        official_source=(
            "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html"
        ),
        discovery_method=DiscoveryMethod.OFFICIAL_MANIFEST,
        download_method=DownloadMethod.HTTPS,
        schema_version="medical-information-network@2026-06-01",
        license_model="PDL 1.0",
        supported_formats=("CSV", "ZIP"),
        spatial_granularity="facility/address/coordinate",
        temporal_granularity="semiannual snapshot",
        crs_handling="published coordinate fields only",
        version_detection=("reference date", "resource URL", "SHA-256"),
        quality_rules=(
            "facility ID",
            "facility type",
            "address",
            "coordinate",
            "reference date",
        ),
        capabilities_provided=("medical",),
    ),
    OpenDataAdapterDefinition(
        adapter_id="mhlw-care@2026-06",
        provider="厚生労働省 介護サービス情報公表システム",
        dataset_family="care",
        official_source="https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html",
        discovery_method=DiscoveryMethod.OFFICIAL_MANIFEST,
        download_method=DownloadMethod.HTTPS,
        schema_version="care-service-open-data@2026-06-30",
        license_model="CC BY 4.0",
        supported_formats=("CSV", "ZIP"),
        spatial_granularity="service establishment/address",
        temporal_granularity="semiannual snapshot",
        crs_handling="published fields only",
        version_detection=("reference date", "resource URL", "SHA-256"),
        quality_rules=("establishment ID", "service code", "address", "reference date"),
        capabilities_provided=("care",),
    ),
    OpenDataAdapterDefinition(
        adapter_id="mlit-future-population-250m@2024",
        provider="国土交通省 国土政策局",
        dataset_family="future_population",
        official_source=(
            "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html"
        ),
        discovery_method=DiscoveryMethod.OFFICIAL_MANIFEST,
        download_method=DownloadMethod.HTTPS,
        schema_version="ksj-future-population-250m-r6@2024",
        license_model="CC BY 4.0",
        supported_formats=("GeoJSON", "ZIP"),
        spatial_granularity="250 m standard regional mesh",
        temporal_granularity="2020 baseline and 2025-2070 five-year projections",
        crs_handling="JGD2011 geographic coordinates (EPSG:6668)",
        version_detection=(
            "production year",
            "resource filename",
            "Last-Modified",
            "ETag",
            "SHA-256",
        ),
        quality_rules=(
            "mesh identifier",
            "administrative area code",
            "projection year coverage",
            "numeric and suppression semantics",
            "valid polygon geometry",
        ),
        capabilities_provided=("future_population",),
    ),
    OpenDataAdapterDefinition(
        adapter_id="estat-economic-census-500m@2021",
        provider="総務省・経済産業省 / e-Stat",
        dataset_family="economic_activity",
        official_source=(
            "https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&"
            "serveyId=H002005112021&statsId=T001162&toukeiCode=00200553&"
            "toukeiYear=2021&type=1"
        ),
        discovery_method=DiscoveryMethod.OFFICIAL_API,
        download_method=DownloadMethod.API_EXPORT,
        schema_version="estat-T001162-JGD2011-500m@2021",
        license_model="政府標準利用規約 第2.0版",
        supported_formats=("CSV", "ZIP"),
        spatial_granularity="500 m standard regional mesh",
        temporal_granularity="2021-06-01 census snapshot",
        crs_handling="JGD2011 mesh code and JIS X 0410 geometry",
        version_detection=("statistics ID", "release date", "resource URL", "SHA-256"),
        quality_rules=(
            "KEY_CODE",
            "official statistic field identifiers",
            "establishment and employee units",
            "suppression symbols",
            "500 m mesh identity",
        ),
        capabilities_provided=("economic_activity", "daytime_activity_context"),
    ),
)


SOURCES = (
    OpenDataSourceDefinition(
        source_key="digital-agency-municipal-standard-ods",
        adapter_id="municipal-standard-ods@2026-08",
        provider="デジタル庁",
        title="自治体標準オープンデータセット（正式版）",
        official_url=(
            "https://www.digital.go.jp/resources/open_data/municipal-standard-data-set-test"
        ),
        source_priority=1,
        default_license_id="unknown",
        catalog_scope=CatalogScope.NATIONAL,
    ),
    OpenDataSourceDefinition(
        source_key="bodik-maizuru",
        adapter_id="ckan-v3@1",
        provider="舞鶴市 / BODIK",
        title="舞鶴市オープンデータカタログ",
        official_url="https://data.bodik.jp/organization/262021",
        source_priority=1,
        default_license_id="cc-by-4.0",
        catalog_scope=CatalogScope.MUNICIPAL,
        municipality_code="26202",
    ),
    OpenDataSourceDefinition(
        source_key="fujisawa-open-data-library",
        adapter_id="official-static-catalog@1",
        provider="藤沢市",
        title="藤沢市オープンデータライブラリ",
        official_url=(
            "https://www.city.fujisawa.kanagawa.jp/kyoso/shise/kekaku/kakushu/datalibrary.html"
        ),
        source_priority=1,
        default_license_id="cc-by-4.0",
        catalog_scope=CatalogScope.MUNICIPAL,
        municipality_code="14205",
    ),
    OpenDataSourceDefinition(
        source_key="mhlw-medical-information-network",
        adapter_id="mhlw-medical@2026-06",
        provider="厚生労働省",
        title="医療情報ネットのオープンデータ",
        official_url=(
            "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html"
        ),
        source_priority=1,
        default_license_id="pdl-1.0",
        catalog_scope=CatalogScope.NATIONAL,
    ),
    OpenDataSourceDefinition(
        source_key="mhlw-care-service",
        adapter_id="mhlw-care@2026-06",
        provider="厚生労働省",
        title="介護サービス情報公表システム オープンデータ",
        official_url="https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html",
        source_priority=1,
        default_license_id="cc-by-4.0",
        catalog_scope=CatalogScope.NATIONAL,
    ),
    OpenDataSourceDefinition(
        source_key="mlit-future-population-250m-r6",
        adapter_id="mlit-future-population-250m@2024",
        provider="国土交通省 国土政策局",
        title="250mメッシュ別将来推計人口（R6国政局推計）",
        official_url=(
            "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html"
        ),
        source_priority=1,
        default_license_id="cc-by-4.0",
        catalog_scope=CatalogScope.NATIONAL,
    ),
    OpenDataSourceDefinition(
        source_key="estat-economic-census-2021-500m",
        adapter_id="estat-economic-census-500m@2021",
        provider="総務省・経済産業省 / e-Stat",
        title="令和3年経済センサス－活動調査 500mメッシュ（JGD2011）",
        official_url=(
            "https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&"
            "serveyId=H002005112021&statsId=T001162&toukeiCode=00200553&"
            "toukeiYear=2021&type=1"
        ),
        source_priority=1,
        default_license_id="government-standard-terms-2.0",
        catalog_scope=CatalogScope.NATIONAL,
    ),
)


OFFICIAL_SOURCE_REGISTRY = OfficialSourceRegistry(adapters=ADAPTERS, sources=SOURCES)
