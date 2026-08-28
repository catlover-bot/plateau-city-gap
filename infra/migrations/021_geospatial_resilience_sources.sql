BEGIN;

INSERT INTO open_data_license_policies (
    license_id, license_name, license_url, commercial_use, redistribution,
    attribution_required, share_alike, derivative_allowed, unknown_terms,
    policy_version, verified_at
) VALUES
(
    'jshis-terms-2025-03', 'J-SHIS利用規約',
    'https://www.j-shis.bosai.go.jp/agreement', NULL, false, true, NULL, true,
    true, '2025-03', '2026-08-28T12:00:00Z'
),
(
    'gsi-survey-act-review', '基盤地図情報利用条件・測量法手続レビュー',
    'https://service.gsi.go.jp/kiban/app/help/', NULL, NULL, NULL, NULL, NULL,
    true, 'file-spec-5.3', '2026-08-28T12:00:00Z'
),
(
    'xroad-api-terms-2025-05', '道路交通情報提供API利用規約',
    'https://www.jartic-open-traffic.org/', NULL, NULL, true, NULL, true,
    true, '2025-05-12', '2026-08-28T12:00:00Z'
);

INSERT INTO open_data_adapters (
    adapter_id, provider, dataset_family, official_source_url, discovery_method,
    download_method, schema_version, license_model, supported_formats,
    spatial_granularity, temporal_granularity, crs_handling, version_detection,
    quality_rules, capabilities_provided, definition_updated_at
) VALUES
(
    'gsi-foundation-map@5.3', '国土地理院', 'geospatial_reference',
    'https://service.gsi.go.jp/kiban/app/help/', 'static_catalog', 'https',
    'fundamental-geospatial-data-download-file-spec@5.3',
    '測量法上の手続と個別利用条件の確認が必要', ARRAY['GML','ZIP'],
    'feature dependent', 'current download package',
    'JGD2024/current official specification; never inferred',
    ARRAY['specification version','package metadata','content SHA-256'],
    '["registered-user retrieval","Survey Act review","declared datum","feature schema"]',
    ARRAY['geospatial_reference'], '2026-08-28T12:00:00Z'
),
(
    'jshis-surface-ground-v4@2020', '防災科学技術研究所 J-SHIS', 'surface_ground',
    'https://www.j-shis.bosai.go.jp/api-sstruct-meshinfo', 'official_manifest', 'https',
    'J-SHIS-Z-V4-AMP-VS400-M250@2020',
    'J-SHIS利用規約（派生物のみ条件付き利用）', ARRAY['CSV','ZIP'],
    '250 m standard regional mesh', '2020 national seismic hazard map model',
    'JGD2000 geographic coordinates (EPSG:4612) to EPSG:4326',
    ARRAY['V4','archive first mesh','CSV DATE','content SHA-256'],
    '["CODE","JCODE","AVS","ARV","AVS_EB","AVS_REF"]',
    ARRAY['surface_ground_context'], '2026-08-28T12:00:00Z'
),
(
    'npa-traffic-accident@2024', '警察庁', 'traffic_accident',
    'https://www.npa.go.jp/publications/statistics/koutsuu/opendata/index_opendata.html',
    'official_manifest', 'https', 'npa-traffic-accident-main-table@2024',
    '公共データ利用規約 第1.0版', ARRAY['CSV','XLSX'],
    'injury/fatal traffic-accident point',
    'annual file with event occurrence timestamp',
    'published world-geodetic DMS point to EPSG:4326',
    ARRAY['latest published year','resource URL','content SHA-256'],
    '["68-field main table","prefecture and municipality code","event timestamp",'
        '"DMS coordinate","fatality and injury counts"]',
    ARRAY['historical_traffic_accident_context'], '2026-08-28T12:00:00Z'
),
(
    'mlit-pedestrian-ckan@2024',
    '国土交通省 歩行空間ナビ・データプラットフォーム', 'pedestrian_network',
    'https://ckan.hokonavi.go.jp/dataset/', 'ckan_api', 'ckan_resource',
    'pedestrian-space-network-spec@2024-07', '公共データ利用規約 第1.0版',
    ARRAY['GeoJSON','GML','ZIP'], 'published walking network coverage',
    'catalog resource revision', 'resource-declared CRS only',
    ARRAY['package metadata_modified','resource URL','content SHA-256'],
    '["network dataset identity","coverage","schema","licence"]',
    ARRAY['official_pedestrian_network'], '2026-08-28T12:00:00Z'
),
(
    'xroad-traffic-api@2026-01', '国土交通省 / 日本道路交通情報センター',
    'traffic_observation', 'https://www.jartic-open-traffic.org/', 'official_api',
    'api_export', 'jartic-open-traffic-wfs@2026-01',
    '道路交通情報提供API利用規約（2025-05-12）', ARRAY['GeoJSON'],
    'published observation station or CCTV section',
    'rolling 5-minute/hourly reference observations', 'requested EPSG:4326 output',
    ARRAY['API specification','layer name','observation time'],
    '["bounded query","observation time","station identity","coverage"]',
    ARRAY['live_traffic_reference'], '2026-08-28T12:00:00Z'
);

INSERT INTO open_data_source_catalog (
    source_key, adapter_id, provider, source_title, official_url, source_priority,
    default_license_id, catalog_scope, municipality_code, metadata, verified_at
) VALUES
(
    'gsi-fundamental-geospatial-data', 'gsi-foundation-map@5.3', '国土地理院',
    '基盤地図情報ダウンロードサービス', 'https://service.gsi.go.jp/kiban/app/help/',
    1, 'gsi-survey-act-review', 'national', NULL,
    '{"status":"requires_review","unavailable_reason":"requires_credentials",'
        '"specification_version":"5.3","datum":"JGD2024",'
        '"plateau_comparison_performed":false}',
    '2026-08-28T12:00:00Z'
),
(
    'jshis-surface-ground-v4', 'jshis-surface-ground-v4@2020',
    '防災科学技術研究所 J-SHIS', '2020年版250mメッシュ微地形区分・表層地盤',
    'https://www.j-shis.bosai.go.jp/api-sstruct-meshinfo', 1,
    'jshis-terms-2025-03', 'national', NULL,
    '{"dataset_version":"V4","reference_year":2020,"source_epsg":4612,'
        '"raw_redistribution":false,"model_not_site_observation":true}',
    '2026-08-28T12:00:00Z'
),
(
    'npa-traffic-accident-2024', 'npa-traffic-accident@2024', '警察庁',
    '交通事故統計情報のオープンデータ 2024年本票',
    'https://www.npa.go.jp/publications/statistics/koutsuu/opendata/2024/opendata_2024.html',
    1, 'pdl-1.0', 'national', NULL,
    '{"annual_file_year":2024,"scope":"injury_and_fatal_accidents",'
        '"property_only_excluded":true,"historical_context_only":true}',
    '2026-08-28T12:00:00Z'
),
(
    'mlit-pedestrian-network-catalog', 'mlit-pedestrian-ckan@2024', '国土交通省',
    '歩行空間ネットワークデータ カタログ', 'https://ckan.hokonavi.go.jp/dataset/',
    1, 'pdl-1.0', 'national', NULL,
    '{"checked_at":"2026-08-28","catalog_dataset_count":31,'
        '"pilot_city_network_coverage":false}',
    '2026-08-28T12:00:00Z'
),
(
    'xroad-open-traffic-api', 'xroad-traffic-api@2026-01',
    '国土交通省 / 日本道路交通情報センター', '道路交通情報提供API',
    'https://www.jartic-open-traffic.org/', 2, 'xroad-api-terms-2025-05',
    'national', NULL,
    '{"rolling_reference_values":true,"stable_snapshot_ingested":false,'
        '"not_official_survey_result":true}',
    '2026-08-28T12:00:00Z'
),
(
    'maizuru-official-gtfs-research', 'official-static-catalog@1', '舞鶴市',
    '舞鶴市公式GTFS公開状況調査', 'https://data.bodik.jp/organization/262021',
    2, 'unknown', 'municipal', '26202',
    '{"status":"unavailable","unavailable_reason":"not_published",'
        '"checked_at":"2026-08-28","p11_conversion":false}',
    '2026-08-28T12:00:00Z'
),
(
    'fujisawa-official-gtfs-research', 'official-static-catalog@1', '藤沢市',
    '藤沢市公式GTFS公開状況調査', 'https://www.city.fujisawa.kanagawa.jp/bus/',
    2, 'unknown', 'municipal', '14205',
    '{"status":"unavailable","unavailable_reason":"not_published",'
        '"checked_at":"2026-08-28","p11_conversion":false}',
    '2026-08-28T12:00:00Z'
);

COMMIT;
