BEGIN;

ALTER TABLE plateau_landuse
    ADD COLUMN class_label text,
    ADD COLUMN class_codelist text,
    ADD COLUMN source_area_m2 double precision CHECK (source_area_m2 >= 0),
    ADD COLUMN survey_year integer CHECK (survey_year BETWEEN 1900 AND 2200);

ALTER TABLE plateau_urban_planning
    ADD COLUMN function_label text,
    ADD COLUMN function_codelist text,
    ADD COLUMN urban_plan_type_code text,
    ADD COLUMN urban_plan_type_label text,
    ADD COLUMN urban_plan_type_codelist text,
    ADD COLUMN building_coverage_rate double precision CHECK (building_coverage_rate >= 0),
    ADD COLUMN floor_area_rate double precision CHECK (floor_area_rate >= 0),
    ADD COLUMN valid_from date,
    ADD COLUMN custodian text;

ALTER TABLE plateau_hazards
    ADD COLUMN rank_codelist text,
    ADD COLUMN description_code text,
    ADD COLUMN description_label text,
    ADD COLUMN disaster_type_code text,
    ADD COLUMN disaster_type_label text,
    ADD COLUMN area_type_code text,
    ADD COLUMN area_type_label text,
    ADD COLUMN valid_from date,
    ADD COLUMN location text,
    ADD COLUMN zone_number text,
    ADD COLUMN zone_name text,
    ADD COLUMN overlap_policy text NOT NULL DEFAULT 'additional_confirmation_required'
        CHECK (overlap_policy = 'additional_confirmation_required');

COMMENT ON COLUMN plateau_hazards.depth_m IS
    'Nullable official numeric depth only. Never derive this from WaterBody geometry Z.';
COMMENT ON COLUMN plateau_hazards.overlap_policy IS
    'An overlap triggers municipal confirmation and does not determine siting feasibility.';

CREATE TABLE spatial_context_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    network_version_id uuid REFERENCES road_network_versions(id),
    algorithm_version text NOT NULL,
    analysis_crs text NOT NULL,
    config_hash text NOT NULL CHECK (config_hash ~ '^[0-9a-f]{64}$'),
    source_archive_sha256 text NOT NULL CHECK (source_archive_sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}',
    CHECK (
        (status = 'running' AND completed_at IS NULL) OR
        (status IN ('succeeded', 'failed') AND completed_at IS NOT NULL)
    ),
    UNIQUE (dataset_version_id, algorithm_version, config_hash)
);

CREATE TABLE building_spatial_context (
    context_run_id uuid NOT NULL REFERENCES spatial_context_runs(id) ON DELETE CASCADE,
    building_city_object_id bigint NOT NULL REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    context_city_object_id bigint NOT NULL REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    context_type text NOT NULL CHECK (context_type IN ('landuse', 'planning', 'hazard')),
    relation text NOT NULL DEFAULT 'intersects' CHECK (relation = 'intersects'),
    review_status text,
    siting_feasibility text,
    PRIMARY KEY (context_run_id, building_city_object_id, context_city_object_id),
    CHECK (
        context_type <> 'hazard' OR
        (review_status = 'additional_confirmation_required' AND
         siting_feasibility = 'not_determined')
    )
);
CREATE INDEX building_spatial_context_building_idx
    ON building_spatial_context (building_city_object_id, context_type);

CREATE TABLE mesh_spatial_context (
    context_run_id uuid NOT NULL REFERENCES spatial_context_runs(id) ON DELETE CASCADE,
    mesh_code text NOT NULL,
    context_city_object_id bigint NOT NULL REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    context_type text NOT NULL CHECK (context_type IN ('landuse', 'planning', 'hazard')),
    intersection_area_m2 double precision NOT NULL CHECK (intersection_area_m2 > 0),
    review_status text,
    siting_feasibility text,
    PRIMARY KEY (context_run_id, mesh_code, context_city_object_id),
    CHECK (
        context_type <> 'hazard' OR
        (review_status = 'additional_confirmation_required' AND
         siting_feasibility = 'not_determined')
    )
);
CREATE INDEX mesh_spatial_context_mesh_idx
    ON mesh_spatial_context (context_run_id, mesh_code, context_type);

CREATE TABLE scenario_candidate_spatial_context (
    context_run_id uuid NOT NULL REFERENCES spatial_context_runs(id) ON DELETE CASCADE,
    candidate_id text NOT NULL,
    context_city_object_id bigint NOT NULL REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    context_type text NOT NULL CHECK (context_type IN ('landuse', 'planning', 'hazard')),
    candidate_geom geometry(Point, 6674) NOT NULL,
    review_status text,
    siting_feasibility text NOT NULL DEFAULT 'not_determined'
        CHECK (siting_feasibility = 'not_determined'),
    PRIMARY KEY (context_run_id, candidate_id, context_city_object_id),
    CHECK (
        context_type <> 'hazard' OR review_status = 'additional_confirmation_required'
    )
);
CREATE INDEX scenario_candidate_context_candidate_idx
    ON scenario_candidate_spatial_context (context_run_id, candidate_id, context_type);
CREATE INDEX scenario_candidate_context_geom_idx
    ON scenario_candidate_spatial_context USING gist (candidate_geom);

CREATE TABLE road_hazard_context (
    context_run_id uuid NOT NULL REFERENCES spatial_context_runs(id) ON DELETE CASCADE,
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id) ON DELETE CASCADE,
    edge_id text NOT NULL,
    hazard_city_object_id bigint NOT NULL REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    intersection_length_m double precision NOT NULL CHECK (intersection_length_m > 0),
    review_status text NOT NULL DEFAULT 'additional_confirmation_required'
        CHECK (review_status = 'additional_confirmation_required'),
    siting_feasibility text NOT NULL DEFAULT 'not_determined'
        CHECK (siting_feasibility = 'not_determined'),
    PRIMARY KEY (context_run_id, network_version_id, edge_id, hazard_city_object_id),
    FOREIGN KEY (network_version_id, edge_id)
        REFERENCES road_network_edges(network_version_id, edge_id)
);
CREATE INDEX road_hazard_context_edge_idx
    ON road_hazard_context (network_version_id, edge_id);

CREATE VIEW spatial_context_provenance AS
SELECT
    run.id AS context_run_id,
    run.algorithm_version,
    run.analysis_crs,
    run.config_hash,
    run.source_archive_sha256,
    run.status,
    run.started_at,
    run.completed_at,
    dataset.city_id,
    dataset.city_name,
    dataset.dataset_year,
    dataset.product_specification_version,
    dataset.archive_file_name
FROM spatial_context_runs AS run
JOIN city_dataset_versions AS dataset ON dataset.id = run.dataset_version_id;

COMMIT;
