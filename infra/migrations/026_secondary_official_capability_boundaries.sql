BEGIN;

-- Current official catalogs that are useful to municipal analysis but are not
-- promoted for the pilot cities.  Registration records discoverability; it
-- does not invent city coverage, accept unknown terms, or create canonical rows.

INSERT INTO open_data_adapters (
    adapter_id, provider, dataset_family, official_source_url, discovery_method,
    download_method, schema_version, license_model, supported_formats,
    spatial_granularity, temporal_granularity, crs_handling, version_detection,
    quality_rules, capabilities_provided, definition_updated_at
) VALUES
(
    'mhlw-kayoi-no-ba@2026-06', '厚生労働省', 'social_participation',
    'https://www.mhlw.go.jp/stf/kayoinoba_opendata_00002.html',
    'official_manifest', 'https', 'mhlw-kayoi-no-ba@2026-06-30',
    '厚生労働省ホームページ利用規約', ARRAY['CSV'],
    'published community activity location', 'semiannual snapshot',
    'published latitude/longitude; datum requires review',
    ARRAY['reference date','output date','resource URL','content SHA-256'],
    '["municipality code","publication status","location identity",'
        '"coordinate","reference date"]',
    ARRAY['social_participation'], '2026-08-29T00:23:00+09:00'
),
(
    'wam-disability-welfare@2026-03', '独立行政法人福祉医療機構 WAM NET',
    'welfare', 'https://www.wam.go.jp/content/wamnet/pcpub/top/sfkopendata/',
    'official_manifest', 'https', 'wamnet-disability-welfare-open-data@2026-03',
    'WAM NET掲載条件・resource利用条件の確認が必要', ARRAY['CSV','ZIP'],
    'service establishment/address', 'published snapshot',
    'published fields only; coordinates are never inferred',
    ARRAY['release month','service package code','resource URL','content SHA-256'],
    '["service package identity","municipality code","facility identity",'
        '"licence review"]',
    ARRAY['welfare'], '2026-08-29T00:23:00+09:00'
),
(
    'mlit-station-passenger-s12@2021', '国土交通省 国土数値情報', 'station_usage',
    'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-S12-v3_1.html',
    'official_manifest', 'https', 'ksj-S12@3.1', '国土数値情報利用約款',
    ARRAY['GML','ZIP'], 'railway station point',
    '2021 station passenger-count snapshot',
    'JGD2011 geographic coordinates (EPSG:6668)',
    ARRAY['dataset year','product specification','resource URL','content SHA-256'],
    '["station identity","operator and line","observation year",'
        '"passenger-count unit","point geometry"]',
    ARRAY['station_usage_context'], '2026-08-29T00:23:00+09:00'
),
(
    'mlit-person-trip-catalog@2026-03', '国土交通省 都市局', 'mobility',
    'https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000031.html',
    'static_catalog', 'https', 'mlit-person-trip-study-area-list@2026-03',
    'published study metadata only; survey data terms require separate review',
    ARRAY['HTML','XLSX','PDF'], 'metropolitan study area metadata',
    'approximately decennial study', 'not applicable to catalog metadata',
    ARRAY['catalog as-of date','study year','resource URL'],
    '["study area","study year","published unit","licence","privacy"]',
    ARRAY['mobility_context'], '2026-08-29T00:23:00+09:00'
);

INSERT INTO open_data_source_catalog (
    source_key, adapter_id, provider, source_title, official_url, source_priority,
    default_license_id, catalog_scope, municipality_code, metadata, verified_at
) VALUES
(
    'mhlw-kayoi-no-ba', 'mhlw-kayoi-no-ba@2026-06', '厚生労働省',
    '通いの場のオープンデータ',
    'https://www.mhlw.go.jp/stf/kayoinoba_opendata_00002.html', 1,
    'unknown', 'national', NULL,
    '{"reference_date":"2026-06-30","output_date":"2026-07-09",'
        '"national_row_count":15486,"pilot_city_row_count":0,'
        '"raw_sha256":"d909b5a013756ed09cb0635e75acf9c65628588f26f2702ab2e6cbea6bcd31f1"}',
    '2026-08-29T00:23:00+09:00'
),
(
    'wam-disability-welfare-open-data', 'wam-disability-welfare@2026-03',
    '独立行政法人福祉医療機構 WAM NET',
    '障害福祉サービス等情報公表システムデータのオープンデータ',
    'https://www.wam.go.jp/content/wamnet/pcpub/top/sfkopendata/', 1,
    'unknown', 'national', NULL,
    '{"release_month":"2026-03","service_package_count":29,'
        '"raw_snapshot_ingested":false,"licence_review_required":true}',
    '2026-08-29T00:23:00+09:00'
),
(
    'mlit-station-passenger-count-s12', 'mlit-station-passenger-s12@2021',
    '国土交通省 国土数値情報', '駅別乗降客数データ S12',
    'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-S12-v3_1.html', 1,
    'mlit-ksj-terms-review', 'national', NULL,
    '{"dataset_year":2021,"product_specification":"3.1",'
        '"raw_snapshot_ingested":false,"station_usage_is_not_capacity":true}',
    '2026-08-29T00:23:00+09:00'
),
(
    'mlit-person-trip-study-catalog', 'mlit-person-trip-catalog@2026-03',
    '国土交通省 都市局', 'パーソントリップ調査 実施都市圏一覧',
    'https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000031.html', 1,
    'unknown', 'national', NULL,
    '{"catalog_as_of":"2026-03","pilot_public_spatial_package_verified":false,'
        '"individual_tracking_permitted":false}',
    '2026-08-29T00:23:00+09:00'
);

INSERT INTO dataset_family_quality_gate_policies (
    dataset_family, gate_key, policy_version, dimension, requirement,
    failure_action, effective_at
) VALUES
('social_participation','pilot-city-records','family-gates@2','completeness',
 'A published row in the selected city and a reviewed coordinate datum are required.',
 'reject','2026-08-29T00:23:00+09:00'),
('welfare','official-service-and-terms','family-gates@2','licence',
 'Official service package identity, city coverage and machine-readable terms are required.',
 'requires_review','2026-08-29T00:23:00+09:00'),
('station_usage','observation-year-and-unit','family-gates@2','temporal',
 'Station identity, observation year and passenger-count unit must remain explicit.',
 'requires_review','2026-08-29T00:23:00+09:00'),
('mobility','aggregate-study-boundary','family-gates@2','licence',
 'Only licensed aggregate study outputs may be used; individual trajectories are prohibited.',
 'reject','2026-08-29T00:23:00+09:00');

CREATE FUNCTION seed_secondary_official_capability_boundaries(
    p_organization_id uuid, p_city_id uuid, p_city_code text
) RETURNS void AS $$
BEGIN
IF p_city_code NOT IN ('26202', '14205') THEN
    RETURN;
END IF;

WITH source_rows (
    source_key, external_dataset_id, dataset_family, title, source_url,
    availability, unavailable_reason, license_id, metadata, reference_date,
    update_frequency
) AS (VALUES
('mhlw-kayoi-no-ba','kayoi-no-ba-2026-06','social_participation',
 '通いの場 2026-06 都市カバレッジ調査',
 'https://www.mhlw.go.jp/stf/kayoinoba_opendata_00002.html',
 'unavailable','outside_coverage','unknown',
 '{"national_row_count":15486,"city_feature_count":0,'
    '"missing_rows_are_not_zero":true}'::jsonb,'2026-06-30'::date,'semiannual'),
('wam-disability-welfare-open-data','wamnet-welfare-2026-03','welfare',
 'WAM NET 障害福祉オープンデータ取得レビュー',
 'https://www.wam.go.jp/content/wamnet/pcpub/top/sfkopendata/',
 'requires_review','not_verified','unknown',
 '{"service_package_count":29,"raw_snapshot_ingested":false,'
    '"availability_is_not_personal_eligibility":true}'::jsonb,NULL::date,'published release'),
('mlit-station-passenger-count-s12','S12-22','station_usage',
 '駅別乗降客数 S12 2021 導入レビュー',
 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-S12-v3_1.html',
 'requires_review','not_verified','mlit-ksj-terms-review',
 '{"dataset_year":2021,"product_specification":"3.1",'
    '"canonical_snapshot_ingested":false,"not_capacity_or_congestion":true}'::jsonb,
 NULL::date,'dataset release'),
('mlit-person-trip-study-catalog','person-trip-catalog-2026-03','mobility',
 'パーソントリップ調査 公開単位・利用条件レビュー',
 'https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000031.html',
 'requires_review','not_verified','unknown',
 '{"catalog_as_of":"2026-03","pilot_public_spatial_package_verified":false,'
    '"aggregate_statistics_only":true,"individual_tracking":false}'::jsonb,
 NULL::date,'study cycle')
)
INSERT INTO city_open_data_sources (
    organization_id, city_id, source_key, external_dataset_id, dataset_family,
    title, source_url, availability, unavailable_reason, review_status,
    license_id, metadata, reference_date, update_frequency, discovered_at,
    reviewed_at, reviewed_by
)
SELECT p_organization_id, p_city_id, source.source_key, source.external_dataset_id,
       source.dataset_family, source.title, source.source_url, source.availability,
       source.unavailable_reason, 'reviewed', source.license_id, source.metadata,
       source.reference_date, source.update_frequency,
       '2026-08-29T00:23:00+09:00', '2026-08-29T00:23:00+09:00',
       'CITY GAP source audit'
FROM source_rows AS source
ON CONFLICT (organization_id, city_id, source_key, external_dataset_id) DO NOTHING;

WITH coverage_rows (dataset_family, status, unavailable_reason, source_key,
                    temporal_alignment, explanation) AS (VALUES
('social_participation','unavailable','outside_coverage','mhlw-kayoi-no-ba','unknown',
 'The official 2026-06 file has no Maizuru or Fujisawa row; absence is not converted to zero.'),
('welfare','requires_review','not_verified','wam-disability-welfare-open-data','unknown',
 'The official WAM NET catalog exists, but city rows, schema and redistribution terms are not yet verified.'),
('station_usage','requires_review','not_verified','mlit-station-passenger-count-s12','stale',
 'Official S12 2021 exists; no version-pinned pilot canonical snapshot is promoted.'),
('mobility','requires_review','not_verified','mlit-person-trip-study-catalog','unknown',
 'The official study-area catalog exists; a licensed pilot spatial aggregate has not been verified.')
)
INSERT INTO city_data_coverage (
    organization_id, city_id, dataset_family, status, unavailable_reason,
    city_source_id, temporal_alignment, explanation, assessed_at
)
SELECT p_organization_id, p_city_id, coverage.dataset_family, coverage.status,
       coverage.unavailable_reason, source.id, coverage.temporal_alignment,
       coverage.explanation, '2026-08-29T00:23:00+09:00'
FROM coverage_rows AS coverage
JOIN city_open_data_sources AS source
  ON source.organization_id = p_organization_id AND source.city_id = p_city_id
 AND source.source_key = coverage.source_key
ON CONFLICT (organization_id, city_id, dataset_family) DO UPDATE
SET status = EXCLUDED.status,
    unavailable_reason = EXCLUDED.unavailable_reason,
    city_source_id = EXCLUDED.city_source_id,
    temporal_alignment = EXCLUDED.temporal_alignment,
    explanation = EXCLUDED.explanation,
    assessed_at = EXCLUDED.assessed_at;

WITH timeline_rows (source_key, dataset_family, reference_period, temporal_kind,
                    label, temporal_note, display_order) AS (VALUES
('mlit-station-passenger-count-s12','station_usage','2021','survey',
 '駅別乗降客数 S12 2021','利用者数文脈。capacityや混雑予測ではない。',35),
('mhlw-kayoi-no-ba','social_participation','2026-06-30','release',
 '通いの場 2026-06','公式全国fileに対象2市の行はない。',95),
('wam-disability-welfare-open-data','welfare','2026-03 catalog','release',
 'WAM NET 障害福祉 2026-03','catalog確認済み。city canonicalは未検証。',75),
('mlit-person-trip-study-catalog','mobility','2026-03 catalog','survey',
 'パーソントリップ実施状況 2026-03','個人軌跡ではなく集計調査の公開境界。',76)
)
INSERT INTO city_source_timeline_entries (
    organization_id, city_id, city_source_id, dataset_family, reference_period,
    temporal_kind, label, temporal_note, display_order
)
SELECT p_organization_id, p_city_id, source.id, timeline.dataset_family,
       timeline.reference_period, timeline.temporal_kind, timeline.label,
       timeline.temporal_note, timeline.display_order
FROM timeline_rows AS timeline
JOIN city_open_data_sources AS source
  ON source.organization_id = p_organization_id AND source.city_id = p_city_id
 AND source.source_key = timeline.source_key
ON CONFLICT (organization_id, city_id, dataset_family, reference_period) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION seed_secondary_official_capability_boundaries_after_insert()
RETURNS trigger AS $$
BEGIN
    PERFORM seed_secondary_official_capability_boundaries(
        NEW.organization_id, NEW.id, NEW.city_code
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER city_seed_secondary_official_capability_boundaries
AFTER INSERT ON cities
FOR EACH ROW EXECUTE FUNCTION seed_secondary_official_capability_boundaries_after_insert();

SELECT seed_secondary_official_capability_boundaries(
    city.organization_id, city.id, city.city_code
)
FROM cities AS city
WHERE city.city_code IN ('26202', '14205');

COMMENT ON FUNCTION seed_secondary_official_capability_boundaries(uuid, uuid, text) IS
    'Attaches current official capability audits only after a real pilot city exists; never fabricates city data.';

COMMIT;
