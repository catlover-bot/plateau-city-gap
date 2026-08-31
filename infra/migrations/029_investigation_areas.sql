-- Versioned Investigation Areas and deterministic Known/Unknown evidence.
-- P0 point_radius geometries are simple projected-radius buffers. They are
-- explicitly not pedestrian-network isochrones or actual walking-time areas.

BEGIN;

CREATE TABLE investigation_areas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    area_series_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    supersedes_area_id uuid,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    investigation_id uuid NOT NULL,
    urban_state_id uuid NOT NULL,
    geometry_kind text NOT NULL CHECK (
        geometry_kind IN ('point_radius','source_boundary','mesh')
    ),
    origin_kind text NOT NULL CHECK (
        origin_kind IN ('map_point','station','source_feature','none')
    ),
    label text NOT NULL CHECK (length(label) BETWEEN 1 AND 500),
    requested_geometry geometry(Geometry, 4326) NOT NULL,
    effective_geometry geometry(Geometry, 4326) NOT NULL,
    origin_point geometry(Point, 4326),
    radius_m integer CHECK (radius_m BETWEEN 100 AND 3000),
    radius_methodology text CHECK (
        radius_methodology IN (
            'mlit_elderly_walk_reference_500m',
            'mlit_general_walk_reference_800m',
            'broad_context_1000m',
            'custom_radius'
        )
    ),
    methodology_source jsonb NOT NULL CHECK (
        jsonb_typeof(methodology_source) = 'object'
    ),
    source_boundary_kind text CHECK (
        source_boundary_kind IN ('census_2020_small_area')
    ),
    source_dataset_version_id uuid,
    source_feature_id text,
    clipped_area_ratio double precision NOT NULL DEFAULT 1 CHECK (
        clipped_area_ratio > 0 AND clipped_area_ratio <= 1
    ),
    geometry_sha256 char(64) NOT NULL CHECK (geometry_sha256 ~ '^[0-9a-f]{64}$'),
    rule_version text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    UNIQUE (organization_id, area_series_id, version),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, urban_state_id)
        REFERENCES urban_states(organization_id, id),
    FOREIGN KEY (organization_id, source_dataset_version_id)
        REFERENCES dataset_versions(organization_id, id),
    FOREIGN KEY (organization_id, supersedes_area_id)
        REFERENCES investigation_areas(organization_id, id),
    CHECK (
        geometry_kind <> 'point_radius'
        OR (
            origin_kind IN ('map_point','station')
            AND origin_point IS NOT NULL
            AND radius_m IS NOT NULL
            AND radius_methodology IS NOT NULL
            AND source_boundary_kind IS NULL
        )
    ),
    CHECK (
        origin_kind <> 'station'
        OR (source_dataset_version_id IS NOT NULL AND length(source_feature_id) > 0)
    ),
    CHECK (
        geometry_kind <> 'source_boundary'
        OR (
            origin_kind = 'source_feature'
            AND source_boundary_kind IS NOT NULL
            AND source_dataset_version_id IS NOT NULL
            AND length(source_feature_id) > 0
            AND radius_m IS NULL
            AND radius_methodology IS NULL
        )
    ),
    CHECK (
        (radius_methodology = 'mlit_elderly_walk_reference_500m' AND radius_m = 500)
        OR (radius_methodology = 'mlit_general_walk_reference_800m' AND radius_m = 800)
        OR (radius_methodology = 'broad_context_1000m' AND radius_m = 1000)
        OR (
            radius_methodology = 'custom_radius'
            AND radius_m NOT IN (500,800,1000)
        )
        OR radius_methodology IS NULL
    ),
    CHECK (
        ST_IsValid(requested_geometry) AND NOT ST_IsEmpty(requested_geometry)
        AND ST_IsValid(effective_geometry) AND NOT ST_IsEmpty(effective_geometry)
    )
);
CREATE INDEX investigation_areas_scope_idx
    ON investigation_areas (
        organization_id, city_id, investigation_id, area_series_id, version DESC
    );
CREATE INDEX investigation_areas_effective_geometry_idx
    ON investigation_areas USING gist (effective_geometry);

CREATE FUNCTION citygap_validate_investigation_area_version() RETURNS trigger AS $$
DECLARE
    previous_area investigation_areas;
BEGIN
    IF NEW.version = 1 THEN
        IF NEW.supersedes_area_id IS NOT NULL OR NEW.area_series_id <> NEW.id THEN
            RAISE EXCEPTION 'first area version must use its own id as series and supersede nothing';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.supersedes_area_id IS NULL THEN
        RAISE EXCEPTION 'area version % requires supersedes_area_id', NEW.version;
    END IF;
    SELECT * INTO previous_area
      FROM investigation_areas
     WHERE organization_id = NEW.organization_id
       AND id = NEW.supersedes_area_id;
    IF NOT FOUND
       OR previous_area.area_series_id <> NEW.area_series_id
       OR previous_area.version <> NEW.version - 1
       OR previous_area.city_id <> NEW.city_id
       OR previous_area.investigation_id <> NEW.investigation_id THEN
        RAISE EXCEPTION 'invalid Investigation Area version chain';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION citygap_reject_investigation_area_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Investigation Areas are immutable; create a new version';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER investigation_areas_validate_version
    BEFORE INSERT ON investigation_areas
    FOR EACH ROW EXECUTE FUNCTION citygap_validate_investigation_area_version();
CREATE TRIGGER investigation_areas_immutable_update
    BEFORE UPDATE OR DELETE ON investigation_areas
    FOR EACH ROW EXECUTE FUNCTION citygap_reject_investigation_area_mutation();

CREATE TABLE area_analysis_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    investigation_area_id uuid NOT NULL,
    analysis_run_id uuid,
    schema_version text NOT NULL DEFAULT 'citygap.area-summary@1' CHECK (
        schema_version = 'citygap.area-summary@1'
    ),
    rule_version text NOT NULL,
    input_sha256 char(64) NOT NULL CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL DEFAULT 'queued' CHECK (
        status IN ('queued','running','succeeded','failed')
    ),
    source_dataset_version_ids uuid[] NOT NULL CHECK (
        cardinality(source_dataset_version_ids) > 0
    ),
    started_at timestamptz,
    completed_at timestamptz,
    failure_reason text,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    UNIQUE (organization_id, investigation_area_id, input_sha256),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, investigation_area_id)
        REFERENCES investigation_areas(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, analysis_run_id)
        REFERENCES analysis_runs(organization_id, id),
    CHECK (
        (status IN ('queued','running') AND completed_at IS NULL)
        OR (status IN ('succeeded','failed') AND completed_at IS NOT NULL)
    )
);
CREATE INDEX area_analysis_runs_scope_idx
    ON area_analysis_runs (organization_id, city_id, investigation_area_id, created_at DESC);

CREATE TABLE area_metric_results (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    area_analysis_run_id uuid NOT NULL,
    metric_key text NOT NULL,
    display_group text NOT NULL CHECK (
        display_group IN (
            'population','age_distribution','building_use','establishments',
            'urban_planning','transport','secondary'
        )
    ),
    knowledge_status text NOT NULL CHECK (
        knowledge_status IN ('known','partial','unknown','unavailable')
    ),
    value jsonb NOT NULL CHECK (jsonb_typeof(value) = 'object'),
    calculation_semantics text NOT NULL CHECK (
        calculation_semantics IN (
            'exact','area_weighted_estimate','modelled','observation_count'
        )
    ),
    source_dataset_version_id uuid NOT NULL,
    source_date date,
    aggregation_rule_version text NOT NULL,
    coverage_ratio double precision CHECK (coverage_ratio BETWEEN 0 AND 1),
    freshness text NOT NULL,
    source_limitation text NOT NULL,
    result_sha256 char(64) NOT NULL CHECK (result_sha256 ~ '^[0-9a-f]{64}$'),
    display_order smallint NOT NULL CHECK (display_order > 0),
    UNIQUE (organization_id, area_analysis_run_id, metric_key),
    FOREIGN KEY (organization_id, area_analysis_run_id)
        REFERENCES area_analysis_runs(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, source_dataset_version_id)
        REFERENCES dataset_versions(organization_id, id)
);
CREATE INDEX area_metric_results_group_idx
    ON area_metric_results (organization_id, area_analysis_run_id, display_order);

CREATE TABLE area_knowledge_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    area_analysis_run_id uuid NOT NULL,
    finding_id uuid,
    knowledge_key text NOT NULL,
    title text NOT NULL,
    known_summary text NOT NULL,
    unknown_summary text NOT NULL,
    importance text NOT NULL,
    knowledge_status text NOT NULL CHECK (
        knowledge_status IN ('known','partial','unknown','unavailable')
    ),
    action_type text NOT NULL CHECK (
        action_type IN ('none','data_acquisition','field_verification','expert_review')
    ),
    reason_code text NOT NULL CHECK (
        reason_code IN (
            'no_source','coverage_gap','privacy_suppressed','source_time_limit',
            'model_limit','object_semantics_limit','requires_field_observation',
            'requires_expert_judgment'
        )
    ),
    source_boundary text NOT NULL,
    source_references text[] NOT NULL CHECK (cardinality(source_references) > 0),
    coverage_ratio double precision CHECK (coverage_ratio BETWEEN 0 AND 1),
    decision_impact smallint NOT NULL CHECK (decision_impact BETWEEN 0 AND 100),
    display_order smallint NOT NULL CHECK (display_order BETWEEN 1 AND 4),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    UNIQUE (organization_id, area_analysis_run_id, knowledge_key),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, area_analysis_run_id)
        REFERENCES area_analysis_runs(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, finding_id)
        REFERENCES findings(organization_id, id),
    CHECK (
        action_type <> 'field_verification'
        OR knowledge_status IN ('partial','unknown')
    ),
    CHECK (
        knowledge_status <> 'known'
        OR coverage_ratio IS NULL
        OR coverage_ratio = 1
    )
);
CREATE INDEX area_knowledge_items_action_idx
    ON area_knowledge_items (
        organization_id, city_id, area_analysis_run_id, action_type, display_order
    );

ALTER TABLE spatial_evidence_packs
    ADD COLUMN investigation_area_id uuid,
    ADD CONSTRAINT spatial_evidence_packs_investigation_area_fk
        FOREIGN KEY (organization_id, investigation_area_id)
        REFERENCES investigation_areas(organization_id, id);

ALTER TABLE field_verification_tasks
    ADD COLUMN area_knowledge_item_id uuid,
    ADD CONSTRAINT field_verification_tasks_area_knowledge_item_fk
        FOREIGN KEY (organization_id, area_knowledge_item_id)
        REFERENCES area_knowledge_items(organization_id, id);

COMMENT ON COLUMN investigation_areas.radius_m IS
    'Simple radius in metres; never a pedestrian-network or walking-time isochrone.';
COMMENT ON COLUMN investigation_areas.radius_methodology IS
    'Versioned policy-analysis reference. 800m does not mean ten minutes actual walking.';
COMMENT ON TABLE area_metric_results IS
    'Deterministic evidence; missing and suppressed inputs must never be replaced by zero.';
COMMENT ON TABLE area_knowledge_items IS
    'Only field_verification items may be converted into verification tasks.';

COMMIT;
