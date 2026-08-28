BEGIN;

UPDATE open_data_adapters
SET supported_formats = ARRAY['CSV','GeoJSON','XLSX','ZIP'],
    definition_updated_at = '2026-08-28T00:00:00Z'
WHERE adapter_id = 'ckan-v3@1';

INSERT INTO open_data_adapters (
    adapter_id, provider, dataset_family, official_source_url, discovery_method,
    download_method, schema_version, license_model, supported_formats,
    spatial_granularity, temporal_granularity, crs_handling, version_detection,
    quality_rules, capabilities_provided, definition_updated_at
) VALUES (
    'official-static-catalog@1', 'Municipality', 'catalog',
    'https://www.city.fujisawa.kanagawa.jp/', 'static_catalog', 'https',
    'section-link-catalog@1',
    'linked resource licence must be verified independently', ARRAY['HTML'],
    'linked resource dependent', 'catalog page update',
    'linked resource must declare CRS independently',
    ARRAY['catalog SHA-256','linked URL','resource metadata'],
    '["official catalog","section label","HTTPS link","resource terms"]',
    ARRAY[]::text[], '2026-08-28T00:00:00Z'
);

UPDATE open_data_source_catalog
SET adapter_id = 'official-static-catalog@1',
    metadata = metadata || '{"linked_resource_terms_require_review":true}'::jsonb,
    verified_at = '2026-08-28T00:00:00Z'
WHERE source_key = 'fujisawa-open-data-library';

COMMIT;
