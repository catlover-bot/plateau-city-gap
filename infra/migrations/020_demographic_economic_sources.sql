BEGIN;

INSERT INTO open_data_adapters (
    adapter_id, provider, dataset_family, official_source_url, discovery_method,
    download_method, schema_version, license_model, supported_formats,
    spatial_granularity, temporal_granularity, crs_handling, version_detection,
    quality_rules, capabilities_provided, definition_updated_at
) VALUES
(
    'mlit-future-population-250m@2024', '国土交通省 国土政策局', 'future_population',
    'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html',
    'official_manifest', 'https', 'ksj-future-population-250m-r6@2024', 'CC BY 4.0',
    ARRAY['GeoJSON','ZIP'], '250 m standard regional mesh',
    '2020 baseline and 2025-2070 five-year projections',
    'JGD2011 geographic coordinates (EPSG:6668)',
    ARRAY['production year','resource filename','Last-Modified','ETag','content SHA-256'],
    '["mesh identifier","administrative area code","projection year coverage",'
        '"numeric and suppression semantics","valid polygon geometry"]',
    ARRAY['future_population'], '2026-08-28T00:00:00Z'
),
(
    'estat-economic-census-500m@2021', '総務省・経済産業省 / e-Stat', 'economic_activity',
    'https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&'
        'serveyId=H002005112021&statsId=T001162&toukeiCode=00200553&'
        'toukeiYear=2021&type=1',
    'official_api', 'api_export', 'estat-T001162-JGD2011-500m@2021',
    '政府標準利用規約 第2.0版', ARRAY['CSV','ZIP'],
    '500 m standard regional mesh', '2021-06-01 census snapshot',
    'JGD2011 mesh code and JIS X 0410 geometry',
    ARRAY['statistics ID','release date','resource URL','content SHA-256'],
    '["KEY_CODE","official statistic field identifiers","establishment and employee units",'
        '"suppression symbols","500 m mesh identity"]',
    ARRAY['economic_activity','daytime_activity_context'], '2026-08-28T00:00:00Z'
);

INSERT INTO open_data_source_catalog (
    source_key, adapter_id, provider, source_title, official_url, source_priority,
    default_license_id, catalog_scope, municipality_code, metadata, verified_at
) VALUES
(
    'mlit-future-population-250m-r6', 'mlit-future-population-250m@2024',
    '国土交通省 国土政策局', '250mメッシュ別将来推計人口（R6国政局推計）',
    'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html', 1,
    'cc-by-4.0', 'national', NULL,
    '{"production_year":2024,"baseline_year":2020,"projection_end_year":2070,'
        '"horizontal_datum":"JGD2011","epsg":6668}',
    '2026-08-28T00:00:00Z'
),
(
    'estat-economic-census-2021-500m', 'estat-economic-census-500m@2021',
    '総務省・経済産業省 / e-Stat',
    '令和3年経済センサス－活動調査 500mメッシュ（JGD2011）',
    'https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&'
        'serveyId=H002005112021&statsId=T001162&toukeiCode=00200553&'
        'toukeiYear=2021&type=1',
    1, 'government-standard-terms-2.0', 'national', NULL,
    '{"statistics_id":"T001162","survey_date":"2021-06-01",'
        '"release_date":"2025-10-09","mesh":"500m","horizontal_datum":"JGD2011"}',
    '2026-08-28T00:00:00Z'
);

COMMIT;
