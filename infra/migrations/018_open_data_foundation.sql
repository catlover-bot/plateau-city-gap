BEGIN;

CREATE TABLE open_data_license_policies (
    license_id text PRIMARY KEY,
    license_name text NOT NULL,
    license_url text NOT NULL CHECK (license_url ~ '^https://'),
    commercial_use boolean,
    redistribution boolean,
    attribution_required boolean,
    share_alike boolean,
    derivative_allowed boolean,
    unknown_terms boolean NOT NULL,
    policy_version text NOT NULL,
    verified_at timestamptz,
    CHECK (unknown_terms OR redistribution IS NOT NULL)
);

INSERT INTO open_data_license_policies (
    license_id, license_name, license_url, commercial_use, redistribution,
    attribution_required, share_alike, derivative_allowed, unknown_terms,
    policy_version, verified_at
) VALUES
('cc-by-4.0', 'Creative Commons Attribution 4.0 International',
 'https://creativecommons.org/licenses/by/4.0/', true, true, true, false, true,
 false, '4.0', '2026-08-28T00:00:00Z'),
('pdl-1.0', '公共データ利用規約 第1.0版',
 'https://www.digital.go.jp/resources/open_data/public_data_license_v1.0', true, true,
 true, false, true, false, '1.0', '2026-08-28T00:00:00Z'),
('government-standard-terms-2.0', '政府標準利用規約 第2.0版',
 'https://www.digital.go.jp/resources/open_data/government-standard-terms-of-use', true,
 true, true, false, true, false, '2.0', '2026-08-28T00:00:00Z'),
('unknown', '条件未確認', 'https://www.digital.go.jp/resources/open_data/', NULL, NULL,
 NULL, NULL, NULL, true, 'unverified', NULL);

CREATE TABLE open_data_adapters (
    adapter_id text PRIMARY KEY,
    provider text NOT NULL,
    dataset_family text NOT NULL,
    official_source_url text NOT NULL CHECK (official_source_url ~ '^https://'),
    discovery_method text NOT NULL CHECK (
        discovery_method IN ('static_catalog', 'ckan_api', 'official_api', 'official_manifest')
    ),
    download_method text NOT NULL CHECK (
        download_method IN ('https', 'ckan_resource', 'api_export')
    ),
    schema_version text NOT NULL,
    license_model text NOT NULL,
    supported_formats text[] NOT NULL CHECK (cardinality(supported_formats) > 0),
    spatial_granularity text NOT NULL,
    temporal_granularity text NOT NULL,
    crs_handling text NOT NULL,
    version_detection text[] NOT NULL CHECK (cardinality(version_detection) > 0),
    quality_rules jsonb NOT NULL CHECK (jsonb_typeof(quality_rules) = 'array'),
    capabilities_provided text[] NOT NULL,
    active boolean NOT NULL DEFAULT true,
    definition_updated_at timestamptz NOT NULL
);

INSERT INTO open_data_adapters (
    adapter_id, provider, dataset_family, official_source_url, discovery_method,
    download_method, schema_version, license_model, supported_formats,
    spatial_granularity, temporal_granularity, crs_handling, version_detection,
    quality_rules, capabilities_provided, definition_updated_at
) VALUES
('municipal-standard-ods@2026-08', 'デジタル庁', 'municipal_standard_ods',
 'https://www.digital.go.jp/resources/open_data/municipal-standard-data-set-test',
 'static_catalog', 'https', 'definition-a-b@2026-08-01',
 'resource licence must be verified independently', ARRAY['CSV','XLSX'],
 'dataset dependent', 'dataset dependent',
 'latitude/longitude or address fields are schema-declared; never inferred',
 ARRAY['schema version','resource Last-Modified','content SHA-256'],
 '["required fields","known aliases","encoding","coordinate semantics","reference date"]',
 ARRAY['population','facilities','medical','care','education','childcare','shelter','aed'],
 '2026-08-10T00:00:00Z'),
('ckan-v3@1', 'CKAN', 'catalog', 'https://docs.ckan.org/en/2.11/api/',
 'ckan_api', 'ckan_resource', 'ckan-package-v3',
 'package/resource licence metadata retained without override', ARRAY['CSV','GeoJSON','ZIP'],
 'resource dependent', 'resource modified timestamp',
 'resource CRS must be declared by schema or validated content',
 ARRAY['package metadata_modified','resource last_modified','ETag','content SHA-256'],
 '["package identity","resource URL","format","licence","modified timestamp"]',
 ARRAY[]::text[], '2026-08-28T00:00:00Z'),
('mhlw-medical@2026-06', '厚生労働省 医療情報ネット', 'medical',
 'https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html',
 'official_manifest', 'https', 'medical-information-network@2026-06-01', 'PDL 1.0',
 ARRAY['CSV','ZIP'], 'facility/address/coordinate', 'semiannual snapshot',
 'published coordinate fields only', ARRAY['reference date','resource URL','content SHA-256'],
 '["facility identifier","facility type","address","coordinates","reported reference date"]',
 ARRAY['medical'], '2026-06-01T00:00:00Z'),
('mhlw-care@2026-06', '厚生労働省 介護サービス情報公表システム', 'care',
 'https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html', 'official_manifest', 'https',
 'care-service-open-data@2026-06-30', 'CC BY 4.0', ARRAY['CSV','ZIP'],
 'service establishment/address', 'semiannual snapshot', 'published fields only',
 ARRAY['reference date','resource URL','content SHA-256'],
 '["establishment identifier","official service code","address","reference date"]',
 ARRAY['care'], '2026-07-09T00:00:00Z');

CREATE TABLE open_data_source_catalog (
    source_key text PRIMARY KEY,
    adapter_id text NOT NULL REFERENCES open_data_adapters(adapter_id),
    provider text NOT NULL,
    source_title text NOT NULL,
    official_url text NOT NULL CHECK (official_url ~ '^https://'),
    source_priority smallint NOT NULL CHECK (source_priority BETWEEN 1 AND 4),
    default_license_id text NOT NULL REFERENCES open_data_license_policies(license_id),
    catalog_scope text NOT NULL CHECK (catalog_scope IN ('national', 'prefectural', 'municipal')),
    municipality_code text CHECK (municipality_code IS NULL OR municipality_code ~ '^[0-9]{5}$'),
    metadata jsonb NOT NULL DEFAULT '{}',
    verified_at timestamptz NOT NULL
);

INSERT INTO open_data_source_catalog (
    source_key, adapter_id, provider, source_title, official_url, source_priority,
    default_license_id, catalog_scope, municipality_code, metadata, verified_at
) VALUES
('digital-agency-municipal-standard-ods', 'municipal-standard-ods@2026-08', 'デジタル庁',
 '自治体標準オープンデータセット（正式版）',
 'https://www.digital.go.jp/resources/open_data/municipal-standard-data-set-test', 1,
 'unknown', 'national', NULL,
 '{"definition_date":"2026-08-01","dataset_count":31}', '2026-08-28T00:00:00Z'),
('bodik-maizuru', 'ckan-v3@1', '舞鶴市 / BODIK', '舞鶴市オープンデータカタログ',
 'https://data.bodik.jp/organization/262021', 1, 'cc-by-4.0', 'municipal', '26202',
 '{"ckan_api":"https://data.bodik.jp/api/3/action/package_search","organization":"262021"}',
 '2026-08-28T00:00:00Z'),
('fujisawa-open-data-library', 'municipal-standard-ods@2026-08', '藤沢市',
 '藤沢市オープンデータライブラリ',
 'https://www.city.fujisawa.kanagawa.jp/kyoso/shise/kekaku/kakushu/datalibrary.html',
 1, 'cc-by-4.0', 'municipal', '14205',
 '{"catalog_kind":"official_static_library","updated":"2026-06-09"}',
 '2026-08-28T00:00:00Z'),
('mhlw-medical-information-network', 'mhlw-medical@2026-06', '厚生労働省',
 '医療情報ネットのオープンデータ',
 'https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html',
 1, 'pdl-1.0', 'national', NULL, '{"reference_date":"2026-06-01"}',
 '2026-08-28T00:00:00Z'),
('mhlw-care-service', 'mhlw-care@2026-06', '厚生労働省',
 '介護サービス情報公表システム オープンデータ',
 'https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html', 1, 'cc-by-4.0',
 'national', NULL, '{"reference_date":"2026-06-30","output_date":"2026-07-09"}',
 '2026-08-28T00:00:00Z');

CREATE TABLE city_open_data_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    source_key text NOT NULL REFERENCES open_data_source_catalog(source_key),
    external_dataset_id text NOT NULL,
    dataset_family text NOT NULL,
    title text NOT NULL,
    source_url text NOT NULL CHECK (source_url ~ '^https://'),
    availability text NOT NULL CHECK (
        availability IN ('available','partial','unavailable','unknown','requires_review')
    ),
    unavailable_reason text CHECK (
        unavailable_reason IS NULL OR unavailable_reason IN (
            'not_published','outside_coverage','license_blocked','schema_unsupported',
            'retrieval_failed','requires_credentials','temporal_mismatch','not_verified'
        )
    ),
    review_status text NOT NULL DEFAULT 'discovered' CHECK (
        review_status IN ('discovered','reviewed','selected','disabled')
    ),
    license_id text NOT NULL REFERENCES open_data_license_policies(license_id),
    metadata jsonb NOT NULL DEFAULT '{}',
    published_at timestamptz,
    reference_date date,
    update_frequency text,
    etag text,
    last_modified timestamptz,
    discovered_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    reviewed_by text,
    UNIQUE (organization_id, id),
    UNIQUE (organization_id, city_id, source_key, external_dataset_id),
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id),
    CHECK (
        (availability IN ('unavailable','requires_review') AND unavailable_reason IS NOT NULL)
        OR (availability NOT IN ('unavailable','requires_review') AND unavailable_reason IS NULL)
    )
);
CREATE INDEX city_open_data_sources_inventory_idx
    ON city_open_data_sources (organization_id, city_id, dataset_family, availability);

CREATE TABLE open_data_raw_blobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    content_type text NOT NULL,
    storage_provider text NOT NULL CHECK (storage_provider IN ('local','s3_compatible')),
    object_key text NOT NULL UNIQUE,
    reuse_scope text NOT NULL CHECK (reuse_scope IN ('public_verified','tenant_only')),
    first_retrieved_at timestamptz NOT NULL,
    UNIQUE NULLS NOT DISTINCT (sha256, owner_organization_id),
    CHECK (
        (reuse_scope = 'public_verified' AND owner_organization_id IS NULL)
        OR (reuse_scope = 'tenant_only' AND owner_organization_id IS NOT NULL)
    )
);

CREATE TABLE open_data_resources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_source_id uuid NOT NULL,
    dataset_version_id uuid,
    raw_blob_id uuid REFERENCES open_data_raw_blobs(id),
    external_resource_id text NOT NULL,
    resource_title text NOT NULL,
    resource_url text NOT NULL CHECK (resource_url ~ '^https://'),
    format text NOT NULL,
    content_length bigint CHECK (content_length IS NULL OR content_length >= 0),
    raw_checksum char(64) CHECK (raw_checksum IS NULL OR raw_checksum ~ '^[0-9a-f]{64}$'),
    retrieved_at timestamptz,
    published_at timestamptz,
    reference_date date,
    update_frequency text,
    source_crs text,
    horizontal_datum text,
    vertical_datum text,
    transformation_method text,
    source_schema_version text,
    adapter_version text NOT NULL,
    source_headers jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    UNIQUE (organization_id, city_source_id, external_resource_id),
    FOREIGN KEY (organization_id, city_source_id)
        REFERENCES city_open_data_sources(organization_id, id),
    FOREIGN KEY (organization_id, dataset_version_id)
        REFERENCES dataset_versions(organization_id, id),
    CHECK (raw_blob_id IS NULL OR raw_checksum IS NOT NULL)
);
CREATE INDEX open_data_resources_version_idx
    ON open_data_resources (organization_id, dataset_version_id, reference_date DESC);
CREATE INDEX open_data_resources_checksum_idx ON open_data_resources (raw_checksum);

CREATE TABLE open_data_resource_processing (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_id uuid NOT NULL,
    state text NOT NULL CHECK (
        state IN ('discovered','downloaded','validating','quarantined','validated',
                  'normalizing','canonicalized','linked','analysis_ready','failed')
    ),
    status_reason text,
    row_count bigint CHECK (row_count IS NULL OR row_count >= 0),
    feature_count bigint CHECK (feature_count IS NULL OR feature_count >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, resource_id),
    FOREIGN KEY (organization_id, resource_id)
        REFERENCES open_data_resources(organization_id, id) ON DELETE CASCADE
);

CREATE TABLE open_data_quality_results (
    id bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_id uuid NOT NULL,
    gate_key text NOT NULL,
    status text NOT NULL CHECK (status IN ('passed','failed','requires_review','not_applicable')),
    observed_value jsonb NOT NULL,
    explanation text NOT NULL,
    checked_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, resource_id, gate_key),
    FOREIGN KEY (organization_id, resource_id)
        REFERENCES open_data_resources(organization_id, id) ON DELETE CASCADE
);

CREATE TABLE open_data_transformation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_id uuid NOT NULL,
    adapter_id text NOT NULL REFERENCES open_data_adapters(adapter_id),
    adapter_version text NOT NULL,
    transformation_version text NOT NULL,
    canonical_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('running','succeeded','failed','quarantined')),
    input_row_count bigint CHECK (input_row_count IS NULL OR input_row_count >= 0),
    output_record_count bigint CHECK (output_record_count IS NULL OR output_record_count >= 0),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    error_message text,
    metadata jsonb NOT NULL DEFAULT '{}',
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, resource_id)
        REFERENCES open_data_resources(organization_id, id),
    CHECK ((status = 'running' AND completed_at IS NULL) OR
           (status <> 'running' AND completed_at IS NOT NULL))
);

CREATE TABLE canonical_open_data_records (
    id bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    dataset_version_id uuid NOT NULL,
    source_resource_id uuid NOT NULL,
    transformation_run_id uuid NOT NULL,
    record_type text NOT NULL CHECK (record_type IN (
        'population_observation','activity_observation','facility','service_offering',
        'transport_node','transport_observation','road_observation','hazard_area',
        'ground_observation','planning_area','mobility_observation'
    )),
    external_record_id text NOT NULL,
    display_name text,
    source_row_locator text NOT NULL,
    reference_date date,
    valid_from date,
    valid_to date,
    attributes jsonb NOT NULL,
    geom geometry(Geometry, 4326),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    UNIQUE (organization_id, transformation_run_id, record_type, external_record_id),
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, dataset_version_id)
        REFERENCES dataset_versions(organization_id, id),
    FOREIGN KEY (organization_id, source_resource_id)
        REFERENCES open_data_resources(organization_id, id),
    FOREIGN KEY (organization_id, transformation_run_id)
        REFERENCES open_data_transformation_runs(organization_id, id),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_from <= valid_to)
);
CREATE INDEX canonical_open_data_records_tenant_type_idx
    ON canonical_open_data_records (organization_id, city_id, record_type, reference_date DESC);
CREATE INDEX canonical_open_data_records_geom_idx
    ON canonical_open_data_records USING gist (geom);

CREATE TABLE open_data_spatial_links (
    id bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    canonical_record_id bigint NOT NULL,
    link_type text NOT NULL CHECK (
        link_type IN ('city','mesh','plateau_building','road','facility','urban_state')
    ),
    target_id text,
    match_method text NOT NULL CHECK (
        match_method IN ('exact','deterministic','ambiguous','unmatched')
    ),
    rule_version text NOT NULL,
    distance_m numeric CHECK (distance_m IS NULL OR distance_m >= 0),
    explanation text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, canonical_record_id)
        REFERENCES canonical_open_data_records(organization_id, id) ON DELETE CASCADE,
    CHECK ((match_method = 'unmatched' AND target_id IS NULL) OR
           (match_method <> 'unmatched' AND target_id IS NOT NULL))
);
CREATE INDEX open_data_spatial_links_target_idx
    ON open_data_spatial_links (organization_id, link_type, target_id);

CREATE TABLE city_data_coverage (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    dataset_family text NOT NULL,
    status text NOT NULL CHECK (
        status IN ('available','partial','unavailable','unknown','requires_review')
    ),
    unavailable_reason text CHECK (
        unavailable_reason IS NULL OR unavailable_reason IN (
            'not_published','outside_coverage','license_blocked','schema_unsupported',
            'retrieval_failed','requires_credentials','temporal_mismatch','not_verified'
        )
    ),
    city_source_id uuid,
    temporal_alignment text NOT NULL DEFAULT 'unknown' CHECK (
        temporal_alignment IN ('aligned','mixed','stale','unknown')
    ),
    explanation text NOT NULL,
    assessed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, city_id, dataset_family),
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, city_source_id)
        REFERENCES city_open_data_sources(organization_id, id),
    CHECK (
        (status IN ('unavailable','requires_review') AND unavailable_reason IS NOT NULL)
        OR (status NOT IN ('unavailable','requires_review') AND unavailable_reason IS NULL)
    )
);
CREATE INDEX city_data_coverage_status_idx
    ON city_data_coverage (organization_id, status, dataset_family);

CREATE TABLE open_data_update_checks (
    id bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_source_id uuid NOT NULL,
    checked_at timestamptz NOT NULL DEFAULT now(),
    result text NOT NULL CHECK (result IN ('unchanged','update_available','failed','rate_limited')),
    observed_etag text,
    observed_last_modified timestamptz,
    observed_resource_url text,
    observed_checksum char(64) CHECK (
        observed_checksum IS NULL OR observed_checksum ~ '^[0-9a-f]{64}$'
    ),
    next_check_after timestamptz NOT NULL,
    detail text NOT NULL,
    FOREIGN KEY (organization_id, city_source_id)
        REFERENCES city_open_data_sources(organization_id, id)
);
CREATE INDEX open_data_update_checks_due_idx
    ON open_data_update_checks (organization_id, next_check_after DESC);

CREATE TABLE analysis_dataset_requirements (
    analysis_id text NOT NULL,
    analysis_version text NOT NULL,
    dataset_family text NOT NULL,
    requirement_level text NOT NULL CHECK (
        requirement_level IN ('required','optional','enhancement')
    ),
    source_selection_rule jsonb NOT NULL,
    rule_version text NOT NULL,
    PRIMARY KEY (analysis_id, analysis_version, dataset_family),
    FOREIGN KEY (analysis_id, analysis_version)
        REFERENCES analysis_definitions(id, version) ON DELETE CASCADE
);

CREATE TABLE local_data_overrides (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    canonical_record_id bigint NOT NULL,
    override_patch jsonb NOT NULL CHECK (jsonb_typeof(override_patch) = 'object'),
    reason text NOT NULL,
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) IN ('object','array')),
    effective_date date NOT NULL,
    review_status text NOT NULL CHECK (
        review_status IN ('draft','in_review','reviewed','rejected','superseded')
    ),
    expires_at date,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, canonical_record_id)
        REFERENCES canonical_open_data_records(organization_id, id),
    CHECK (expires_at IS NULL OR effective_date <= expires_at)
);

CREATE TABLE open_data_override_reconciliations (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    override_id uuid NOT NULL,
    candidate_canonical_record_id bigint NOT NULL,
    status text NOT NULL CHECK (status IN ('candidate','still_needed','resolved','not_comparable')),
    explanation text NOT NULL,
    reviewed_by text,
    reviewed_at timestamptz,
    PRIMARY KEY (organization_id, override_id, candidate_canonical_record_id),
    FOREIGN KEY (organization_id, override_id)
        REFERENCES local_data_overrides(organization_id, id),
    FOREIGN KEY (organization_id, candidate_canonical_record_id)
        REFERENCES canonical_open_data_records(organization_id, id)
);

ALTER TABLE datasets DROP CONSTRAINT datasets_dataset_category_check;
ALTER TABLE datasets ADD CONSTRAINT datasets_dataset_category_check CHECK (
    dataset_category IN (
        'plateau','population','facilities','transport','hazard','planning',
        'medical','care','welfare','education','childcare','economic_activity',
        'traffic_safety','ground','mobility','reference','municipal_custom'
    )
);

ALTER TABLE city_capabilities DROP CONSTRAINT city_capabilities_capability_check;
ALTER TABLE city_capabilities ADD CONSTRAINT city_capabilities_capability_check CHECK (
    capability IN (
        'screening','building_detail','road_network','terrain','land_use',
        'urban_planning','hazard','gtfs','scenario','field','future_population',
        'temporal_diff','resilience','medical','care','social_participation',
        'economic_activity','traffic_accident','ground','official_pedestrian',
        'traffic_volume','station_usage','mobility','hazard_stress_test','criticality',
        'field_mode','outcome_monitoring','evacuation_reachability','planning_monitoring'
    )
);

ALTER TABLE job_runs DROP CONSTRAINT job_runs_job_type_check;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_job_type_check CHECK (
    job_type IN (
        'plateau_ingestion','building_demographics','road_network','network_generation',
        'terrain','terrain_enrichment','spatial_context','context_generation',
        'scenario_optimization','evidence_export','dataset_diff','incremental_recompute',
        'future_population','stress_test','criticality_analysis','outcome_evaluation',
        'validation_run','validation_reproduce','pilot_rehearsal','analysis_run',
        'report_generation','source_discovery','metadata_refresh','resource_download',
        'source_validation','schema_normalization','canonicalization','spatial_linkage',
        'capability_refresh','dependent_analysis_recompute'
    )
);

COMMENT ON TABLE open_data_adapters IS
    'Versioned official-source contracts; discovery never implies acceptance or promotion.';
COMMENT ON TABLE open_data_raw_blobs IS
    'Content-addressed bytes. Only verified public bytes may be deduplicated across tenants.';
COMMENT ON TABLE canonical_open_data_records IS
    'Normalized canonical records with row-level lineage to immutable source resources.';
COMMENT ON TABLE city_data_coverage IS
    'Evidence-backed availability including explicit absence/review reasons and temporal alignment.';
COMMENT ON TABLE local_data_overrides IS
    'Reviewed municipal corrections layered over, never written into, official canonical records.';

COMMIT;
