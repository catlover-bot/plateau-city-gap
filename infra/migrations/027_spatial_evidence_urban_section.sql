BEGIN;

-- Spatial Evidence Packs are immutable delivery units. Geometry is bounded;
-- large geometry bodies live in content-addressed artifacts, not JSON rows.
CREATE TABLE spatial_evidence_packs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_key text NOT NULL,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    urban_state_id uuid NOT NULL,
    finding_id uuid,
    investigation_id uuid NOT NULL,
    geometry geometry(Geometry, 4326) NOT NULL,
    bbox geometry(Polygon, 4326) NOT NULL,
    buffer_m double precision NOT NULL DEFAULT 0 CHECK (buffer_m >= 0),
    status text NOT NULL DEFAULT 'queued' CHECK (
        status IN ('queued','extracting','building','validating','ready','failed','superseded')
    ),
    data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public','internal','restricted')
    ),
    source_dataset_version_ids uuid[] NOT NULL CHECK (
        cardinality(source_dataset_version_ids) > 0
    ),
    network_version_id uuid,
    analysis_run_ids uuid[] NOT NULL DEFAULT '{}',
    content_sha256 char(64),
    manifest_sha256 char(64),
    object_counts jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(object_counts) = 'object'),
    failure_reason text,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    ready_at timestamptz,
    superseded_by_id uuid,
    UNIQUE (organization_id, id),
    UNIQUE (organization_id, pack_key, content_sha256),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, urban_state_id)
        REFERENCES urban_states(organization_id, id),
    FOREIGN KEY (organization_id, finding_id)
        REFERENCES findings(organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, network_version_id)
        REFERENCES road_network_versions(organization_id, id),
    FOREIGN KEY (organization_id, superseded_by_id)
        REFERENCES spatial_evidence_packs(organization_id, id),
    CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (manifest_sha256 IS NULL OR manifest_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (status <> 'ready' OR (
        content_sha256 IS NOT NULL AND manifest_sha256 IS NOT NULL AND ready_at IS NOT NULL
    )),
    CHECK (status <> 'superseded' OR superseded_by_id IS NOT NULL),
    CHECK (ST_IsValid(geometry) AND NOT ST_IsEmpty(geometry)),
    CHECK (ST_IsValid(bbox) AND NOT ST_IsEmpty(bbox))
);
CREATE INDEX spatial_evidence_packs_scope_idx
    ON spatial_evidence_packs (organization_id, city_id, investigation_id, created_at DESC);
CREATE INDEX spatial_evidence_packs_geometry_idx
    ON spatial_evidence_packs USING gist (geometry);

CREATE TABLE spatial_pack_objects (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    pack_id uuid NOT NULL,
    object_type text NOT NULL CHECK (object_type IN (
        'building','road','terrain','landuse','planning','hazard','facility',
        'route_relation','analysis_relation','finding','scenario'
    )),
    source_object_id text NOT NULL,
    source_dataset_version_id uuid,
    geometry geometry(Geometry, 4326),
    attributes jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(attributes) = 'object'),
    relation_semantics text,
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    UNIQUE (organization_id, pack_id, object_type, source_object_id),
    FOREIGN KEY (organization_id, pack_id)
        REFERENCES spatial_evidence_packs(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, source_dataset_version_id)
        REFERENCES dataset_versions(organization_id, id)
);
CREATE INDEX spatial_pack_objects_lookup_idx
    ON spatial_pack_objects (organization_id, pack_id, object_type, id);
CREATE INDEX spatial_pack_objects_geometry_idx
    ON spatial_pack_objects USING gist (geometry);

CREATE TABLE spatial_pack_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    pack_id uuid NOT NULL,
    artifact_type text NOT NULL CHECK (artifact_type IN (
        'manifest','objects','section','tileset','terrain','report','offline_assignment'
    )),
    media_type text NOT NULL,
    storage_uri text NOT NULL,
    byte_length bigint NOT NULL CHECK (byte_length >= 0),
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    etag text NOT NULL,
    cache_control text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, pack_id, artifact_type, content_sha256),
    FOREIGN KEY (organization_id, pack_id)
        REFERENCES spatial_evidence_packs(organization_id, id) ON DELETE CASCADE
);

CREATE TABLE urban_transects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    pack_id uuid NOT NULL,
    investigation_id uuid NOT NULL,
    title text NOT NULL,
    geometry geometry(LineString, 4326) NOT NULL,
    buffer_m double precision NOT NULL DEFAULT 12 CHECK (buffer_m >= 0),
    sample_interval_m double precision NOT NULL DEFAULT 5 CHECK (sample_interval_m > 0),
    vertical_datum text NOT NULL,
    terrain_source text NOT NULL,
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, pack_id)
        REFERENCES spatial_evidence_packs(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE,
    CHECK (ST_IsValid(geometry) AND NOT ST_IsEmpty(geometry))
);
CREATE INDEX urban_transects_geometry_idx ON urban_transects USING gist (geometry);

CREATE TABLE urban_section_samples (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    transect_id uuid NOT NULL,
    sample_order integer NOT NULL CHECK (sample_order >= 0),
    distance_m double precision NOT NULL CHECK (distance_m >= 0),
    elevation_m double precision,
    source_triangle_id text,
    quality text NOT NULL CHECK (quality IN ('direct_tin','boundary','no_coverage')),
    position geometry(PointZ, 4326) NOT NULL,
    UNIQUE (organization_id, transect_id, sample_order),
    FOREIGN KEY (organization_id, transect_id)
        REFERENCES urban_transects(organization_id, id) ON DELETE CASCADE
);

CREATE TABLE urban_section_objects (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    transect_id uuid NOT NULL,
    object_type text NOT NULL CHECK (object_type IN (
        'building_direct','building_nearby','road','facility','planning_band',
        'hazard_band','route_relation','scenario_change'
    )),
    source_object_id text NOT NULL,
    start_distance_m double precision NOT NULL,
    end_distance_m double precision NOT NULL,
    offset_distance_m double precision,
    attributes jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(attributes) = 'object'),
    UNIQUE (organization_id, transect_id, object_type, source_object_id),
    FOREIGN KEY (organization_id, transect_id)
        REFERENCES urban_transects(organization_id, id) ON DELETE CASCADE,
    CHECK (start_distance_m >= 0 AND end_distance_m >= start_distance_m)
);

CREATE TABLE investigation_spatial_states (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    investigation_id uuid NOT NULL,
    saved_view_id uuid,
    pack_id uuid NOT NULL,
    transect_id uuid,
    selected_object_ids text[] NOT NULL DEFAULT '{}',
    camera_state jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(camera_state) = 'object'),
    layer_state jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(layer_state) = 'object'),
    scenario_state jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(scenario_state) = 'object'),
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, pack_id)
        REFERENCES spatial_evidence_packs(organization_id, id),
    FOREIGN KEY (organization_id, transect_id)
        REFERENCES urban_transects(organization_id, id),
    FOREIGN KEY (organization_id, saved_view_id)
        REFERENCES saved_views(organization_id, id)
);

-- The worker uses real stage events and never exposes invented percentages.
ALTER TABLE job_runs DROP CONSTRAINT job_runs_job_type_check;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_job_type_check CHECK (
    job_type IN (
        'plateau_ingestion', 'building_demographics',
        'road_network', 'network_generation', 'terrain', 'terrain_enrichment',
        'spatial_context', 'context_generation', 'scenario_optimization',
        'evidence_export', 'dataset_diff', 'incremental_recompute',
        'future_population', 'stress_test', 'criticality_analysis',
        'outcome_evaluation', 'validation_run', 'validation_reproduce',
        'pilot_rehearsal', 'analysis_run', 'report_generation',
        'source_discovery', 'metadata_refresh', 'resource_download',
        'source_validation', 'schema_normalization', 'canonicalization',
        'spatial_linkage', 'capability_refresh', 'dependent_analysis_recompute',
        'spatial_evidence_pack'
    )
);

COMMENT ON TABLE spatial_evidence_packs IS
    'Immutable tenant-scoped evidence delivery units; geometry payloads are bounded artifacts.';
COMMENT ON TABLE urban_section_samples IS
    'Exact PLATEAU DEM TIN samples with source-triangle lineage; NULL means no coverage.';

COMMIT;
