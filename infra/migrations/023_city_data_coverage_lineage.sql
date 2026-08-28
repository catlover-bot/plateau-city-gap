BEGIN;

-- CITY GAP Data Hub V2.  Source dates are reference periods, not silently
-- normalised to invented January 1 dates, and source preference is policy-
-- versioned rather than inferred from recency.

INSERT INTO open_data_license_policies (
    license_id, license_name, license_url, commercial_use, redistribution,
    attribution_required, share_alike, derivative_allowed, unknown_terms,
    policy_version, verified_at
) VALUES
(
    'mlit-ksj-terms-review', '国土数値情報利用約款',
    'https://nlftp.mlit.go.jp/ksj/other/agreement_01.html', NULL, NULL, true,
    NULL, NULL, true, 'reviewed-2026-08-28', '2026-08-28T12:00:00Z'
),
(
    'plateau-site-policy-2025', 'PLATEAU Site Policy',
    'https://www.mlit.go.jp/plateau/site-policy/', NULL, NULL, true, NULL, NULL,
    true, 'reviewed-2026-08-28', '2026-08-28T12:00:00Z'
);

INSERT INTO open_data_adapters (
    adapter_id, provider, dataset_family, official_source_url, discovery_method,
    download_method, schema_version, license_model, supported_formats,
    spatial_granularity, temporal_granularity, crs_handling, version_detection,
    quality_rules, capabilities_provided, definition_updated_at
) VALUES
(
    'estat-census-500m@2020', '総務省統計局 / e-Stat', 'census_population_500m',
    'https://www.e-stat.go.jp/gis/statmap-search?statsId=T001192',
    'official_api', 'api_export', 'estat-T001192-JGD2011-500m@2020',
    '政府標準利用規約 第2.0版', ARRAY['CSV','ZIP'], '500 m standard regional mesh',
    '2020-10-01 census snapshot', 'JGD2011 mesh code and JIS X 0410 geometry',
    ARRAY['statistics ID','reference date','resource URL','content SHA-256'],
    '["KEY_CODE","population fields","suppression semantics","mesh identity"]',
    ARRAY['population','elderly_population'], '2026-08-28T12:00:00Z'
),
(
    'mlit-ksj-p11@2022', '国土交通省 国土数値情報', 'transport_points',
    'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html',
    'official_manifest', 'https', 'ksj-P11@2022', '国土数値情報利用約款',
    ARRAY['GML','SHP','ZIP'], 'bus stop point', '2022 snapshot',
    'JGD2011 geographic coordinates (EPSG:6668)',
    ARRAY['dataset year','prefecture package','content SHA-256'],
    '["stop identity","operator","point geometry","prefecture package scope"]',
    ARRAY['transport_points'], '2026-08-28T12:00:00Z'
),
(
    'mlit-ksj-p04@2020', '国土交通省 国土数値情報', 'medical_legacy',
    'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html',
    'official_manifest', 'https', 'ksj-P04@2020', '国土数値情報利用約款',
    ARRAY['GML','ZIP'], 'medical facility point', '2020-07 snapshot',
    'JGD2011 geographic coordinates (EPSG:6668)',
    ARRAY['dataset year','prefecture package','content SHA-256'],
    '["facility type","name","address","point geometry","institutional-access flag"]',
    ARRAY['medical_legacy_comparison'], '2026-08-28T12:00:00Z'
),
(
    'plateau-city-model@2025', 'Project PLATEAU', 'plateau_city_model',
    'https://www.mlit.go.jp/plateau/open-data/', 'official_manifest', 'https',
    'CityGML-2.0 / PLATEAU product specification city release@2025',
    'PLATEAU Site Policy', ARRAY['CityGML','3D Tiles','MVT','GeoJSON','ZIP'],
    'city model feature', '2025 city release',
    'source-declared JGD2011 vertical and horizontal reference; web products EPSG:4326',
    ARRAY['municipality release','product specification','archive URL','content SHA-256'],
    '["municipality code","theme inventory","feature count","LOD","declared CRS"]',
    ARRAY['plateau_buildings','road_network','terrain','land_use','urban_planning','hazard'],
    '2026-08-28T12:00:00Z'
);

INSERT INTO open_data_source_catalog (
    source_key, adapter_id, provider, source_title, official_url, source_priority,
    default_license_id, catalog_scope, municipality_code, metadata, verified_at
) VALUES
(
    'estat-census-2020-500m', 'estat-census-500m@2020', '総務省統計局 / e-Stat',
    '令和2年国勢調査 500mメッシュ 5歳階級別人口',
    'https://www.e-stat.go.jp/gis/statmap-search?statsId=T001192', 1,
    'government-standard-terms-2.0', 'national', NULL,
    '{"statistics_id":"T001192","reference_date":"2020-10-01","mesh":"500m"}',
    '2026-08-28T12:00:00Z'
),
(
    'mlit-ksj-p11-2022', 'mlit-ksj-p11@2022', '国土交通省 国土数値情報',
    'バス停留所 P11 2022',
    'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html', 1,
    'mlit-ksj-terms-review', 'national', NULL,
    '{"dataset":"P11","reference_year":2022,"horizontal_datum":"JGD2011"}',
    '2026-08-28T12:00:00Z'
),
(
    'mlit-ksj-p04-2020', 'mlit-ksj-p04@2020', '国土交通省 国土数値情報',
    '医療機関 P04 2020',
    'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html', 2,
    'mlit-ksj-terms-review', 'national', NULL,
    '{"dataset":"P04","reference_period":"2020-07","legacy_comparison_only":true}',
    '2026-08-28T12:00:00Z'
),
(
    'plateau-city-model-2025', 'plateau-city-model@2025', 'Project PLATEAU',
    '3D都市モデル 2025年度', 'https://www.mlit.go.jp/plateau/open-data/', 1,
    'plateau-site-policy-2025', 'national', NULL,
    '{"release_year":2025,"primary_spatial_model":true,"road_graph_is_experimental":true}',
    '2026-08-28T12:00:00Z'
);

CREATE TABLE city_source_timeline_entries (
    id bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    city_source_id uuid,
    dataset_family text NOT NULL,
    reference_period text NOT NULL CHECK (length(reference_period) BETWEEN 4 AND 100),
    temporal_kind text NOT NULL CHECK (
        temporal_kind IN ('observation','survey','model','projection','release','events')
    ),
    label text NOT NULL,
    temporal_note text NOT NULL,
    display_order smallint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, city_id, dataset_family, reference_period),
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, city_source_id)
        REFERENCES city_open_data_sources(organization_id, id)
);
CREATE INDEX city_source_timeline_city_idx
    ON city_source_timeline_entries (organization_id, city_id, display_order);

CREATE TABLE open_data_dataset_comparisons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    comparison_key text NOT NULL,
    left_city_source_id uuid NOT NULL,
    right_city_source_id uuid NOT NULL,
    comparison_version text NOT NULL,
    dimensions jsonb NOT NULL CHECK (jsonb_typeof(dimensions) = 'object'),
    conclusion text NOT NULL,
    automatic_selection boolean NOT NULL DEFAULT false CHECK (NOT automatic_selection),
    compared_at timestamptz NOT NULL,
    UNIQUE (organization_id, city_id, comparison_key, comparison_version),
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, left_city_source_id)
        REFERENCES city_open_data_sources(organization_id, id),
    FOREIGN KEY (organization_id, right_city_source_id)
        REFERENCES city_open_data_sources(organization_id, id)
);

CREATE TABLE open_data_source_conflicts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    dataset_family text NOT NULL,
    conflict_key text NOT NULL,
    source_ids uuid[] NOT NULL CHECK (cardinality(source_ids) >= 2),
    status text NOT NULL CHECK (status IN ('unresolved','reviewed','resolved','not_comparable')),
    conflict_count integer CHECK (conflict_count IS NULL OR conflict_count >= 0),
    explanation text NOT NULL,
    resolution text,
    automatic_truth_selection boolean NOT NULL DEFAULT false
        CHECK (NOT automatic_truth_selection),
    detected_at timestamptz NOT NULL,
    reviewed_at timestamptz,
    UNIQUE (organization_id, city_id, conflict_key),
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id)
);

CREATE TABLE analysis_source_selection_policies (
    analysis_id text NOT NULL,
    analysis_version text NOT NULL,
    dataset_family text NOT NULL,
    policy_version text NOT NULL,
    selection_policy jsonb NOT NULL CHECK (jsonb_typeof(selection_policy) = 'object'),
    automatic_newer_wins boolean NOT NULL DEFAULT false CHECK (NOT automatic_newer_wins),
    effective_at timestamptz NOT NULL,
    PRIMARY KEY (analysis_id, analysis_version, dataset_family, policy_version),
    FOREIGN KEY (analysis_id, analysis_version, dataset_family)
        REFERENCES analysis_dataset_requirements(analysis_id, analysis_version, dataset_family)
        ON DELETE CASCADE
);

CREATE TABLE dataset_family_quality_gate_policies (
    dataset_family text NOT NULL,
    gate_key text NOT NULL,
    policy_version text NOT NULL,
    dimension text NOT NULL CHECK (
        dimension IN ('identity','schema','spatial','temporal','licence','completeness','lineage')
    ),
    requirement text NOT NULL,
    failure_action text NOT NULL CHECK (
        failure_action IN ('quarantine','requires_review','reject','context_only')
    ),
    effective_at timestamptz NOT NULL,
    PRIMARY KEY (dataset_family, gate_key, policy_version)
);

-- Preserve the original requirement text while making the actual selection rule
-- explicit: reference-state fit, identity, licence and passed gates precede recency.
UPDATE analysis_dataset_requirements
SET source_selection_rule = jsonb_build_object(
        'policy', source_selection_rule ->> 'policy',
        'selection_order', jsonb_build_array(
            'reference_state_compatibility', 'official_identity',
            'licence_compatibility', 'family_quality_gates', 'declared_recency'
        ),
        'automatic_newer_wins', false,
        'conflict_action', 'requires_human_review'
    ),
    rule_version = 'open-data-source-preference@2';

INSERT INTO analysis_source_selection_policies (
    analysis_id, analysis_version, dataset_family, policy_version,
    selection_policy, automatic_newer_wins, effective_at
)
SELECT analysis_id, analysis_version, dataset_family, rule_version,
       source_selection_rule, false, '2026-08-28T12:00:00Z'
FROM analysis_dataset_requirements;

INSERT INTO dataset_family_quality_gate_policies (
    dataset_family, gate_key, policy_version, dimension, requirement,
    failure_action, effective_at
) VALUES
('census_population_500m','official-mesh-identity','family-gates@1','identity','Official statistics ID and unique 500m KEY_CODE are required.','quarantine','2026-08-28T12:00:00Z'),
('census_elderly_population_500m','suppression-semantics','family-gates@1','completeness','Suppressed and aggregated cells must remain explicit.','requires_review','2026-08-28T12:00:00Z'),
('plateau_buildings','city-model-inventory','family-gates@1','schema','Municipality, product specification, themes, LOD and CRS must be inventoried.','quarantine','2026-08-28T12:00:00Z'),
('transport_points','published-point-semantics','family-gates@1','spatial','Published P11 points remain stops only; frequency and GTFS service are not inferred.','context_only','2026-08-28T12:00:00Z'),
('mhlw_medical','facility-identity-and-datum','family-gates@1','identity','Facility identity and coordinate datum ambiguity must be retained for review.','requires_review','2026-08-28T12:00:00Z'),
('mhlw_care','official-service-code','family-gates@1','identity','Official establishment and service codes are required.','quarantine','2026-08-28T12:00:00Z'),
('mlit_future_population_250m','projection-series','family-gates@1','temporal','All named official projection years remain separate from observations.','quarantine','2026-08-28T12:00:00Z'),
('economic_census_500m','employee-semantics','family-gates@1','schema','Employees and establishments must not be relabelled as daytime population.','quarantine','2026-08-28T12:00:00Z'),
('jshis_surface_ground','model-and-crs','family-gates@1','spatial','V4 model identity and EPSG:4612 transformation must be recorded.','requires_review','2026-08-28T12:00:00Z'),
('npa_traffic_accident','event-and-scope','family-gates@1','temporal','Occurrence timestamp and injury/fatal scope must be retained.','quarantine','2026-08-28T12:00:00Z'),
('official_pedestrian_network','city-coverage','family-gates@1','completeness','An official graph must cover the audited city before routing use.','reject','2026-08-28T12:00:00Z'),
('traffic_volume','stable-denominator','family-gates@1','temporal','A stable period and matching coverage are required for denominator use.','context_only','2026-08-28T12:00:00Z'),
('gtfs','feed-semantics','family-gates@1','schema','A real official GTFS feed is required; P11 conversion is forbidden.','reject','2026-08-28T12:00:00Z'),
('gsi_foundation_map','retrieval-and-survey-act','family-gates@1','licence','Credentials, declared datum and Survey Act review must complete before use.','requires_review','2026-08-28T12:00:00Z'),
('social_participation','qualified-official-source','family-gates@1','lineage','A spatially and temporally documented official source is required.','reject','2026-08-28T12:00:00Z');

-- City source inventory.  INSERT ... SELECT means no city is fabricated merely
-- because the static pilot analysis has an artifact for it.
CREATE FUNCTION seed_pilot_city_data_hub(
    p_organization_id uuid, p_city_id uuid, p_city_code text
) RETURNS void AS $$
BEGIN
IF p_city_code NOT IN ('26202', '14205') THEN
    RETURN;
END IF;

WITH source_rows (
    city_code, source_key, external_dataset_id, dataset_family, title, source_url,
    availability, unavailable_reason, review_status, license_id, metadata,
    reference_date, update_frequency
) AS (VALUES
('26202','bodik-maizuru','organization-262021','municipal_catalog','舞鶴市オープンデータカタログ','https://data.bodik.jp/organization/262021','available',NULL,'reviewed','cc-by-4.0','{"catalog_only":true}'::jsonb,NULL::date,'catalog dependent'),
('14205','fujisawa-open-data-library','official-library','municipal_catalog','藤沢市オープンデータライブラリ','https://www.city.fujisawa.kanagawa.jp/kyoso/shise/kekaku/kakushu/datalibrary.html','available',NULL,'reviewed','cc-by-4.0','{"catalog_only":true,"linked_resource_terms_require_review":true}'::jsonb,NULL::date,'catalog dependent'),
('26202','plateau-city-model-2025','plateau-26202-2025','plateau_city_model','3D都市モデル（舞鶴市）2025年度','https://www.geospatial.jp/ckan/dataset/plateau-26202-maizuru-shi-2025','available',NULL,'selected','plateau-site-policy-2025','{"reference_period":"2025","feature_count":97140,"building_count":44640,"primary_spatial_model":true,"experimental_road_graph_not_pedestrian":true}'::jsonb,NULL::date,'annual release'),
('14205','plateau-city-model-2025','plateau-14205-2025','plateau_city_model','3D都市モデル（藤沢市）2025年度','https://www.geospatial.jp/ckan/dataset/plateau-14205-fujisawa-shi-2025','available',NULL,'selected','plateau-site-policy-2025','{"reference_period":"2025","feature_count":399271,"building_count":169856,"primary_spatial_model":true,"experimental_road_graph_not_pedestrian":true}'::jsonb,NULL::date,'annual release'),
('26202','estat-census-2020-500m','T001192-26','census_population_500m','令和2年国勢調査 500mメッシュ（京都府）','https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=26&downloadType=2','available',NULL,'selected','government-standard-terms-2.0','{"city_mesh_count":495,"suppression_aware":true}'::jsonb,'2020-10-01','census cycle'),
('14205','estat-census-2020-500m','T001192-14','census_population_500m','令和2年国勢調査 500mメッシュ（神奈川県）','https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001192&code=14&downloadType=2','available',NULL,'selected','government-standard-terms-2.0','{"city_mesh_count":327,"suppression_aware":true}'::jsonb,'2020-10-01','census cycle'),
('26202','mlit-ksj-p11-2022','P11-22-26','transport_points','バス停留所 P11 2022（京都府）','https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html','available',NULL,'selected','mlit-ksj-terms-review','{"reference_period":"2022","city_feature_count":151,"not_gtfs":true,"frequency_not_available":true}'::jsonb,NULL::date,'dataset release'),
('14205','mlit-ksj-p11-2022','P11-22-14','transport_points','バス停留所 P11 2022（神奈川県）','https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html','available',NULL,'selected','mlit-ksj-terms-review','{"reference_period":"2022","city_feature_count":446,"not_gtfs":true,"frequency_not_available":true}'::jsonb,NULL::date,'dataset release'),
('26202','mlit-ksj-p04-2020','P04-20-26','medical_legacy','医療機関 P04 2020（京都府）','https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html','available',NULL,'reviewed','mlit-ksj-terms-review','{"reference_period":"2020-07","city_feature_count":105,"distance_candidate_count":71,"legacy_comparison_only":true}'::jsonb,NULL::date,'dataset release'),
('14205','mlit-ksj-p04-2020','P04-20-14','medical_legacy','医療機関 P04 2020（神奈川県）','https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html','available',NULL,'reviewed','mlit-ksj-terms-review','{"reference_period":"2020-07","city_feature_count":718,"distance_candidate_count":436,"legacy_comparison_only":true}'::jsonb,NULL::date,'dataset release'),
('26202','mhlw-medical-information-network','mhlw-medical-26202-2026-06','mhlw_medical','医療情報ネット 2026-06 舞鶴市','https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html','partial',NULL,'reviewed','pdl-1.0','{"city_feature_count":83,"coordinate_datum_requires_review":true,"identity_merge_automatic":false}'::jsonb,'2026-06-01','semiannual'),
('14205','mhlw-medical-information-network','mhlw-medical-14205-2026-06','mhlw_medical','医療情報ネット 2026-06 藤沢市','https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html','partial',NULL,'reviewed','pdl-1.0','{"city_feature_count":835,"coordinate_datum_requires_review":true,"identity_merge_automatic":false}'::jsonb,'2026-06-01','semiannual'),
('26202','mhlw-care-service','mhlw-care-26202-2026-06','mhlw_care','介護サービス情報 2026-06 舞鶴市','https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html','partial',NULL,'reviewed','cc-by-4.0','{"source_rows_retained":true,"coordinate_coverage_partial":true}'::jsonb,'2026-06-30','semiannual'),
('14205','mhlw-care-service','mhlw-care-14205-2026-06','mhlw_care','介護サービス情報 2026-06 藤沢市','https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html','partial',NULL,'reviewed','cc-by-4.0','{"source_rows_retained":true,"coordinate_coverage_partial":true}'::jsonb,'2026-06-30','semiannual'),
('26202','mlit-future-population-250m-r6','future-population-r6-26202','mlit_future_population_250m','250mメッシュ別将来推計人口 R6 舞鶴市','https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html','available',NULL,'selected','cc-by-4.0','{"production_year":2024,"projection_years":[2025,2050,2070],"official_trial_projection":true,"best_scenario_selected":false}'::jsonb,NULL::date,'official release'),
('14205','mlit-future-population-250m-r6','future-population-r6-14205','mlit_future_population_250m','250mメッシュ別将来推計人口 R6 藤沢市','https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh250r6.html','available',NULL,'selected','cc-by-4.0','{"production_year":2024,"projection_years":[2025,2050,2070],"official_trial_projection":true,"best_scenario_selected":false}'::jsonb,NULL::date,'official release'),
('26202','estat-economic-census-2021-500m','T001162-26','economic_census_500m','令和3年経済センサス 500mメッシュ（京都府）','https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&serveyId=H002005112021&statsId=T001162','available',NULL,'selected','government-standard-terms-2.0','{"employees_are_not_daytime_population":true}'::jsonb,'2021-06-01','census cycle'),
('14205','estat-economic-census-2021-500m','T001162-14','economic_census_500m','令和3年経済センサス 500mメッシュ（神奈川県）','https://www.e-stat.go.jp/gis/statmap-search?aggregateUnit=H&datum=2011&serveyId=H002005112021&statsId=T001162','available',NULL,'selected','government-standard-terms-2.0','{"employees_are_not_daytime_population":true}'::jsonb,'2021-06-01','census cycle'),
('26202','jshis-surface-ground-v4','jshis-v4-26202','jshis_surface_ground','J-SHIS V4 表層地盤 舞鶴市','https://www.j-shis.bosai.go.jp/api-sstruct-meshinfo','available',NULL,'selected','jshis-terms-2025-03','{"reference_period":"2020 model","model_not_site_observation":true,"raw_redistribution":false}'::jsonb,NULL::date,'model release'),
('14205','jshis-surface-ground-v4','jshis-v4-14205','jshis_surface_ground','J-SHIS V4 表層地盤 藤沢市','https://www.j-shis.bosai.go.jp/api-sstruct-meshinfo','available',NULL,'selected','jshis-terms-2025-03','{"reference_period":"2020 model","model_not_site_observation":true,"raw_redistribution":false}'::jsonb,NULL::date,'model release'),
('26202','npa-traffic-accident-2024','npa-2024-26202','npa_traffic_accident','警察庁 人身事故履歴 2024年ファイル 舞鶴市','https://www.npa.go.jp/publications/statistics/koutsuu/opendata/2024/opendata_2024.html','available',NULL,'selected','pdl-1.0','{"reference_period":"2023/2024 occurrence dates in 2024 annual file","historical_context_only":true}'::jsonb,NULL::date,'annual'),
('14205','npa-traffic-accident-2024','npa-2024-14205','npa_traffic_accident','警察庁 人身事故履歴 2024年ファイル 藤沢市','https://www.npa.go.jp/publications/statistics/koutsuu/opendata/2024/opendata_2024.html','available',NULL,'selected','pdl-1.0','{"reference_period":"2023/2024 occurrence dates in 2024 annual file","historical_context_only":true}'::jsonb,NULL::date,'annual'),
('26202','mlit-pedestrian-network-catalog','pedestrian-audit-26202','official_pedestrian_network','公式歩行空間ネットワーク 舞鶴市カバレッジ調査','https://ckan.hokonavi.go.jp/dataset/','unavailable','outside_coverage','reviewed','pdl-1.0','{"catalog_dataset_count":31,"pilot_city_coverage":false}'::jsonb,NULL::date,'metadata review'),
('14205','mlit-pedestrian-network-catalog','pedestrian-audit-14205','official_pedestrian_network','公式歩行空間ネットワーク 藤沢市カバレッジ調査','https://ckan.hokonavi.go.jp/dataset/','unavailable','outside_coverage','reviewed','pdl-1.0','{"catalog_dataset_count":31,"pilot_city_coverage":false}'::jsonb,NULL::date,'metadata review'),
('26202','xroad-open-traffic-api','xroad-probe-26202','traffic_volume','道路交通情報提供API 舞鶴市参照','https://www.jartic-open-traffic.org/','partial',NULL,'reviewed','xroad-api-terms-2025-05','{"rolling_reference_only":true,"stable_snapshot_ingested":false,"official_survey_result":false}'::jsonb,NULL::date,'rolling API'),
('14205','xroad-open-traffic-api','xroad-probe-14205','traffic_volume','道路交通情報提供API 藤沢市参照','https://www.jartic-open-traffic.org/','unknown',NULL,'reviewed','xroad-api-terms-2025-05','{"rolling_reference_only":true,"stable_snapshot_ingested":false,"official_survey_result":false}'::jsonb,NULL::date,'rolling API'),
('26202','gsi-fundamental-geospatial-data','gsi-audit-26202','gsi_foundation_map','基盤地図情報 舞鶴市取得レビュー','https://service.gsi.go.jp/kiban/app/help/','requires_review','requires_credentials','reviewed','gsi-survey-act-review','{"specification_version":"5.3","plateau_comparison_performed":false}'::jsonb,NULL::date,'specification update'),
('14205','gsi-fundamental-geospatial-data','gsi-audit-14205','gsi_foundation_map','基盤地図情報 藤沢市取得レビュー','https://service.gsi.go.jp/kiban/app/help/','requires_review','requires_credentials','reviewed','gsi-survey-act-review','{"specification_version":"5.3","plateau_comparison_performed":false}'::jsonb,NULL::date,'specification update'),
('26202','maizuru-official-gtfs-research','gtfs-audit-26202','gtfs','舞鶴市公式GTFS公開状況調査','https://data.bodik.jp/organization/262021','unavailable','not_published','reviewed','unknown','{"p11_conversion":false}'::jsonb,NULL::date,'metadata review'),
('14205','fujisawa-official-gtfs-research','gtfs-audit-14205','gtfs','藤沢市公式GTFS公開状況調査','https://www.city.fujisawa.kanagawa.jp/bus/','unavailable','not_published','reviewed','unknown','{"p11_conversion":false}'::jsonb,NULL::date,'metadata review')
)
INSERT INTO city_open_data_sources (
    organization_id, city_id, source_key, external_dataset_id, dataset_family,
    title, source_url, availability, unavailable_reason, review_status,
    license_id, metadata, reference_date, update_frequency, discovered_at,
    reviewed_at, reviewed_by
)
SELECT city.organization_id, city.id, source.source_key, source.external_dataset_id,
       source.dataset_family, source.title, source.source_url, source.availability,
       source.unavailable_reason, source.review_status, source.license_id,
       source.metadata, source.reference_date, source.update_frequency,
       '2026-08-28T12:00:00Z', '2026-08-28T12:00:00Z', 'CITY GAP source audit'
FROM source_rows AS source
JOIN cities AS city ON city.city_code = source.city_code
WHERE city.organization_id = p_organization_id AND city.id = p_city_id
ON CONFLICT (organization_id, city_id, source_key, external_dataset_id) DO NOTHING;

-- Coverage is a multi-dimensional inventory.  It deliberately has no score.
WITH coverage_rows (
    city_code, dataset_family, status, unavailable_reason, source_key,
    temporal_alignment, explanation
) AS (VALUES
('26202','plateau_buildings','available',NULL,'plateau-city-model-2025','aligned','PLATEAU 2025 is the primary spatial model; building inventory is verified.'),
('14205','plateau_buildings','available',NULL,'plateau-city-model-2025','aligned','PLATEAU 2025 is the primary spatial model; building inventory is verified.'),
('26202','census_population_500m','available',NULL,'estat-census-2020-500m','stale','Official 2020 census observation; mixed-year analyses must show the 2020 reference.'),
('14205','census_population_500m','available',NULL,'estat-census-2020-500m','stale','Official 2020 census observation; mixed-year analyses must show the 2020 reference.'),
('26202','census_elderly_population_500m','available',NULL,'estat-census-2020-500m','stale','Derived only from disclosed official age fields with suppression retained.'),
('14205','census_elderly_population_500m','available',NULL,'estat-census-2020-500m','stale','Derived only from disclosed official age fields with suppression retained.'),
('26202','transport_points','available',NULL,'mlit-ksj-p11-2022','mixed','P11 2022 stop points are available; frequency and GTFS service are absent.'),
('14205','transport_points','available',NULL,'mlit-ksj-p11-2022','mixed','P11 2022 stop points are available; frequency and GTFS service are absent.'),
('26202','mhlw_medical','partial',NULL,'mhlw-medical-information-network','mixed','MHLW 2026 facilities are retained separately; datum and P04 identity links require review.'),
('14205','mhlw_medical','partial',NULL,'mhlw-medical-information-network','mixed','MHLW 2026 facilities are retained separately; datum and P04 identity links require review.'),
('26202','mhlw_care','partial',NULL,'mhlw-care-service','mixed','MHLW 2026 care records are available but usable-coordinate coverage is partial.'),
('14205','mhlw_care','partial',NULL,'mhlw-care-service','mixed','MHLW 2026 care records are available but usable-coordinate coverage is partial.'),
('26202','mlit_future_population_250m','available',NULL,'mlit-future-population-250m-r6','mixed','Official R6 trial projections are available and kept separate from observed census values.'),
('14205','mlit_future_population_250m','available',NULL,'mlit-future-population-250m-r6','mixed','Official R6 trial projections are available and kept separate from observed census values.'),
('26202','future_population','available',NULL,'mlit-future-population-250m-r6','mixed','Official named projection series; no best scenario is selected.'),
('14205','future_population','available',NULL,'mlit-future-population-250m-r6','mixed','Official named projection series; no best scenario is selected.'),
('26202','economic_census_500m','available',NULL,'estat-economic-census-2021-500m','mixed','2021 employees and establishments are activity context, not daytime population.'),
('14205','economic_census_500m','available',NULL,'estat-economic-census-2021-500m','mixed','2021 employees and establishments are activity context, not daytime population.'),
('26202','jshis_surface_ground','available',NULL,'jshis-surface-ground-v4','stale','J-SHIS V4 2020 is a surface-ground model, not a site observation or risk score.'),
('14205','jshis_surface_ground','available',NULL,'jshis-surface-ground-v4','stale','J-SHIS V4 2020 is a surface-ground model, not a site observation or risk score.'),
('26202','npa_traffic_accident','available',NULL,'npa-traffic-accident-2024','mixed','2023/2024 injury and fatal accident events are historical context only.'),
('14205','npa_traffic_accident','available',NULL,'npa-traffic-accident-2024','mixed','2023/2024 injury and fatal accident events are historical context only.'),
('26202','official_pedestrian_network','unavailable','outside_coverage','mlit-pedestrian-network-catalog','unknown','The reviewed official catalog has no city-covering network; PLATEAU roads are not substituted.'),
('14205','official_pedestrian_network','unavailable','outside_coverage','mlit-pedestrian-network-catalog','unknown','The reviewed official catalog has no city-covering network; PLATEAU roads are not substituted.'),
('26202','traffic_volume','partial',NULL,'xroad-open-traffic-api','unknown','Rolling API reference values exist, but no stable matching denominator snapshot was ingested.'),
('14205','traffic_volume','unknown',NULL,'xroad-open-traffic-api','unknown','Coverage was not established and no stable denominator snapshot was ingested.'),
('26202','gtfs','unavailable','not_published','maizuru-official-gtfs-research','unknown','No verified official GTFS feed was found; P11 is not converted into GTFS.'),
('14205','gtfs','unavailable','not_published','fujisawa-official-gtfs-research','unknown','No verified official GTFS feed was found; P11 is not converted into GTFS.'),
('26202','gsi_foundation_map','requires_review','requires_credentials','gsi-fundamental-geospatial-data','unknown','Credentialed retrieval and Survey Act/use-condition review are incomplete.'),
('14205','gsi_foundation_map','requires_review','requires_credentials','gsi-fundamental-geospatial-data','unknown','Credentialed retrieval and Survey Act/use-condition review are incomplete.'),
('26202','social_participation','unavailable','not_verified',NULL,'unknown','No qualified official spatial and temporal source has been verified.'),
('14205','social_participation','unavailable','not_verified',NULL,'unknown','No qualified official spatial and temporal source has been verified.'),
('26202','road_network','partial',NULL,'plateau-city-model-2025','aligned','PLATEAU roads support an experimental graph; pedestrian semantics are not claimed.'),
('14205','road_network','partial',NULL,'plateau-city-model-2025','aligned','PLATEAU roads support an experimental graph; pedestrian semantics are not claimed.'),
('26202','hazard','available',NULL,'plateau-city-model-2025','aligned','Applicable official PLATEAU hazard themes are inventoried by city release.'),
('14205','hazard','available',NULL,'plateau-city-model-2025','aligned','Applicable official PLATEAU hazard themes are inventoried by city release.'),
('26202','facilities','partial',NULL,'mlit-ksj-p04-2020','mixed','Verified registries cover selected facility domains, not every municipal service.'),
('14205','facilities','partial',NULL,'mlit-ksj-p04-2020','mixed','Verified registries cover selected facility domains, not every municipal service.'),
('26202','versioned_dataset_pair','unknown',NULL,NULL,'unknown','Availability depends on the selected immutable dataset identity and pair.'),
('14205','versioned_dataset_pair','unknown',NULL,NULL,'unknown','Availability depends on the selected immutable dataset identity and pair.')
)
INSERT INTO city_data_coverage (
    organization_id, city_id, dataset_family, status, unavailable_reason,
    city_source_id, temporal_alignment, explanation, assessed_at
)
SELECT city.organization_id, city.id, coverage.dataset_family, coverage.status,
       coverage.unavailable_reason, source.id, coverage.temporal_alignment,
       coverage.explanation, '2026-08-28T12:00:00Z'
FROM coverage_rows AS coverage
JOIN cities AS city ON city.city_code = coverage.city_code
LEFT JOIN city_open_data_sources AS source
 ON source.organization_id = city.organization_id
 AND source.city_id = city.id
 AND source.source_key = coverage.source_key
WHERE city.organization_id = p_organization_id AND city.id = p_city_id
ON CONFLICT (organization_id, city_id, dataset_family) DO NOTHING;

WITH timeline_rows (city_code, source_key, dataset_family, reference_period,
                    temporal_kind, label, temporal_note, display_order) AS (VALUES
('26202','estat-census-2020-500m','census_population_500m','2020-10-01','observation','国勢調査 2020','観測人口。将来推計へ補間しない。',10),
('14205','estat-census-2020-500m','census_population_500m','2020-10-01','observation','国勢調査 2020','観測人口。将来推計へ補間しない。',10),
('26202','jshis-surface-ground-v4','jshis_surface_ground','2020 model','model','J-SHIS V4 2020','表層地盤モデルであり現地観測ではない。',20),
('14205','jshis-surface-ground-v4','jshis_surface_ground','2020 model','model','J-SHIS V4 2020','表層地盤モデルであり現地観測ではない。',20),
('26202','estat-economic-census-2021-500m','economic_census_500m','2021-06-01','survey','経済センサス 2021','従業者数は昼間人口ではない。',30),
('14205','estat-economic-census-2021-500m','economic_census_500m','2021-06-01','survey','経済センサス 2021','従業者数は昼間人口ではない。',30),
('26202','mlit-ksj-p11-2022','transport_points','2022','release','P11 バス停 2022','停留所点。運行頻度やGTFSを表さない。',40),
('14205','mlit-ksj-p11-2022','transport_points','2022','release','P11 バス停 2022','停留所点。運行頻度やGTFSを表さない。',40),
('26202','npa-traffic-accident-2024','npa_traffic_accident','2023/2024 occurrence dates in 2024 annual file','events','交通事故履歴','人身事故の履歴文脈。現在の危険度ではない。',50),
('14205','npa-traffic-accident-2024','npa_traffic_accident','2023/2024 occurrence dates in 2024 annual file','events','交通事故履歴','人身事故の履歴文脈。現在の危険度ではない。',50),
('26202','plateau-city-model-2025','plateau_city_model','2025 release','release','PLATEAU 2025','現在の主空間モデル。',60),
('14205','plateau-city-model-2025','plateau_city_model','2025 release','release','PLATEAU 2025','現在の主空間モデル。',60),
('26202','mlit-future-population-250m-r6','mlit_future_population_250m','2025 / 2050 / 2070 projections (R6 2024 production)','projection','将来推計人口 R6','公式試算。観測値や保証された予測ではない。',70),
('14205','mlit-future-population-250m-r6','mlit_future_population_250m','2025 / 2050 / 2070 projections (R6 2024 production)','projection','将来推計人口 R6','公式試算。観測値や保証された予測ではない。',70),
('26202','mhlw-medical-information-network','mhlw_medical','2026-06-01','release','医療情報ネット 2026-06','P04 2020と同一とは自動判定しない。',80),
('14205','mhlw-medical-information-network','mhlw_medical','2026-06-01','release','医療情報ネット 2026-06','P04 2020と同一とは自動判定しない。',80),
('26202','mhlw-care-service','mhlw_care','2026-06-30','release','介護サービス情報 2026-06','座標利用可能範囲は部分的。',90),
('14205','mhlw-care-service','mhlw_care','2026-06-30','release','介護サービス情報 2026-06','座標利用可能範囲は部分的。',90)
)
INSERT INTO city_source_timeline_entries (
    organization_id, city_id, city_source_id, dataset_family, reference_period,
    temporal_kind, label, temporal_note, display_order
)
SELECT city.organization_id, city.id, source.id, timeline.dataset_family,
       timeline.reference_period, timeline.temporal_kind, timeline.label,
       timeline.temporal_note, timeline.display_order
FROM timeline_rows AS timeline
JOIN cities AS city ON city.city_code = timeline.city_code
JOIN city_open_data_sources AS source
 ON source.organization_id = city.organization_id
 AND source.city_id = city.id
 AND source.source_key = timeline.source_key
WHERE city.organization_id = p_organization_id AND city.id = p_city_id
ON CONFLICT (organization_id, city_id, dataset_family, reference_period) DO NOTHING;

WITH comparison_rows (
    city_code, dimensions, conclusion
) AS (VALUES
('26202','{"record_counts":{"p04_2020":105,"mhlw_2026":83},"coverage":{"p04":"prefecture package clipped to city","mhlw":"national release filtered by municipality"},"coordinate_difference":{"datum_status":"MHLW undeclared; requires review","candidate_distance_m":{"count":52,"min":2.161,"median":8.058,"max":73.192}},"attribute_richness":{"p04":"facility class, name, address, point","mhlw":"facility, department and service attributes retained separately"},"identity":{"matched":0,"probable":17,"ambiguous":18,"unmatched":48},"automatic_merge":false}'::jsonb,'Sources differ in date, scope, attributes and identity; neither automatically replaces the other.'),
('14205','{"record_counts":{"p04_2020":718,"mhlw_2026":835},"coverage":{"p04":"prefecture package clipped to city","mhlw":"national release filtered by municipality"},"coordinate_difference":{"datum_status":"MHLW undeclared; requires review","candidate_distance_m":{"count":464,"min":0.331,"median":8.235,"max":234.29}},"attribute_richness":{"p04":"facility class, name, address, point","mhlw":"facility, department and service attributes retained separately"},"identity":{"matched":0,"probable":464,"ambiguous":0,"unmatched":371},"automatic_merge":false}'::jsonb,'Sources differ in date, scope, attributes and identity; neither automatically replaces the other.')
)
INSERT INTO open_data_dataset_comparisons (
    organization_id, city_id, comparison_key, left_city_source_id,
    right_city_source_id, comparison_version, dimensions, conclusion,
    automatic_selection, compared_at
)
SELECT city.organization_id, city.id, 'p04-2020-vs-mhlw-medical-2026',
       p04.id, mhlw.id, 'medical-identity-comparison@1', comparison.dimensions,
       comparison.conclusion, false, '2026-08-28T12:00:00Z'
FROM comparison_rows AS comparison
JOIN cities AS city ON city.city_code = comparison.city_code
JOIN city_open_data_sources AS p04
  ON p04.organization_id = city.organization_id AND p04.city_id = city.id
 AND p04.source_key = 'mlit-ksj-p04-2020'
JOIN city_open_data_sources AS mhlw
  ON mhlw.organization_id = city.organization_id AND mhlw.city_id = city.id
 AND mhlw.source_key = 'mhlw-medical-information-network'
WHERE city.organization_id = p_organization_id AND city.id = p_city_id
ON CONFLICT (organization_id, city_id, comparison_key, comparison_version) DO NOTHING;

INSERT INTO open_data_source_conflicts (
    organization_id, city_id, dataset_family, conflict_key, source_ids, status,
    conflict_count, explanation, automatic_truth_selection, detected_at
)
SELECT city.organization_id, city.id, 'medical', 'medical-facility-identity-ambiguity',
       ARRAY[p04.id, mhlw.id], 'unresolved', 18,
       '18 Maizuru MHLW/P04 candidates have multiple or conflicting identity evidence; review is required.',
       false, '2026-08-28T12:00:00Z'
FROM cities AS city
JOIN city_open_data_sources AS p04
  ON p04.organization_id = city.organization_id AND p04.city_id = city.id
 AND p04.source_key = 'mlit-ksj-p04-2020'
JOIN city_open_data_sources AS mhlw
  ON mhlw.organization_id = city.organization_id AND mhlw.city_id = city.id
 AND mhlw.source_key = 'mhlw-medical-information-network'
WHERE city.city_code = '26202'
  AND city.organization_id = p_organization_id AND city.id = p_city_id
ON CONFLICT (organization_id, city_id, conflict_key) DO NOTHING;

END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION seed_pilot_city_data_hub_after_insert() RETURNS trigger AS $$
BEGIN
    PERFORM seed_pilot_city_data_hub(NEW.organization_id, NEW.id, NEW.city_code);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER city_seed_pilot_data_hub
AFTER INSERT ON cities
FOR EACH ROW EXECUTE FUNCTION seed_pilot_city_data_hub_after_insert();

SELECT seed_pilot_city_data_hub(city.organization_id, city.id, city.city_code)
FROM cities AS city
WHERE city.city_code IN ('26202', '14205');

CREATE VIEW service_search_documents_v2 AS
SELECT organization_id, city_id, entity_type, entity_id, title, subtitle, updated_at
FROM service_search_documents
UNION ALL
SELECT dataset.organization_id, dataset.city_id, 'dataset'::text, dataset.id::text,
       dataset.title, dataset.provider || ' · ' || dataset.dataset_key, dataset.created_at
FROM datasets AS dataset
UNION ALL
SELECT source.organization_id, source.city_id, 'source'::text, source.id::text,
       source.title, catalog.provider || ' · ' || source.dataset_family,
       source.discovered_at
FROM city_open_data_sources AS source
JOIN open_data_source_catalog AS catalog ON catalog.source_key = source.source_key;

COMMENT ON TABLE city_source_timeline_entries IS
    'Mixed source periods exactly as published; year-only values are text to avoid fabricated dates.';
COMMENT ON TABLE open_data_dataset_comparisons IS
    'Dimension-by-dimension comparison with no aggregate quality score or automatic winner.';
COMMENT ON TABLE open_data_source_conflicts IS
    'Persisted unresolved source conflicts; database rejects automatic truth selection.';
COMMENT ON TABLE analysis_source_selection_policies IS
    'Versioned source selection rules. Recency alone never selects a source.';
COMMENT ON TABLE dataset_family_quality_gate_policies IS
    'Family-specific gates; failed resources follow quarantine/review/reject/context-only policy.';
COMMENT ON VIEW service_search_documents_v2 IS
    'Tenant-scoped service search extended with human dataset and source names.';
COMMENT ON FUNCTION seed_pilot_city_data_hub(uuid, uuid, text) IS
    'Idempotently attaches verified pilot metadata after a real city row exists; never registers a city.';

COMMIT;
