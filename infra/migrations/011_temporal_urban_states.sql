BEGIN;

CREATE TABLE urban_states (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    state_key text NOT NULL,
    label text NOT NULL,
    effective_date date NOT NULL,
    state_type text NOT NULL CHECK (state_type IN ('observed', 'future', 'scenario')),
    lifecycle_status text NOT NULL DEFAULT 'draft' CHECK (
        lifecycle_status IN ('draft', 'validated', 'current', 'superseded', 'archived')
    ),
    base_state_id uuid REFERENCES urban_states(id),
    primary_plateau_dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    source_verified boolean NOT NULL DEFAULT false,
    population_model text,
    fixed_service_assumption boolean NOT NULL DEFAULT false,
    validation_report jsonb NOT NULL DEFAULT '{}',
    created_by text NOT NULL DEFAULT 'migration',
    created_at timestamptz NOT NULL DEFAULT now(),
    validated_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (city_id, state_key),
    CHECK (base_state_id IS NULL OR base_state_id <> id),
    CHECK (state_type = 'observed' OR base_state_id IS NOT NULL),
    CHECK ((lifecycle_status IN ('validated', 'current') AND validated_at IS NOT NULL) OR
           lifecycle_status NOT IN ('validated', 'current')),
    CHECK (state_type <> 'future' OR population_model IS NOT NULL)
);
CREATE UNIQUE INDEX urban_states_one_current_kind_idx
    ON urban_states (city_id, state_type) WHERE lifecycle_status = 'current';
CREATE INDEX urban_states_city_time_idx
    ON urban_states (city_id, effective_date DESC, lifecycle_status);
CREATE INDEX urban_states_plateau_idx
    ON urban_states (primary_plateau_dataset_version_id);

INSERT INTO urban_states (
    city_id, state_key, label, effective_date, state_type, lifecycle_status,
    primary_plateau_dataset_version_id, source_verified, validation_report,
    validated_at
)
SELECT
    city.id,
    'observed-' || version.dataset_year || '-' || left(version.archive_sha256, 12),
    city.name || ' ' || version.dataset_year || ' observed',
    make_date(version.dataset_year, 1, 1),
    'observed',
    CASE WHEN version.is_current THEN 'current' ELSE 'validated' END,
    version.id,
    true,
    jsonb_build_object(
        'migration', '011_temporal_urban_states',
        'archive_sha256', version.archive_sha256,
        'source_boundary', 'registered PLATEAU dataset version'
    ),
    now()
FROM city_dataset_versions AS version
JOIN cities AS city ON city.city_code = version.city_id
ON CONFLICT (city_id, state_key) DO NOTHING;

CREATE TABLE state_dataset_versions (
    urban_state_id uuid NOT NULL REFERENCES urban_states(id) ON DELETE CASCADE,
    dataset_role text NOT NULL CHECK (
        dataset_role IN (
            'plateau', 'population', 'future_population', 'facility', 'transport',
            'network_source', 'land_use', 'planning', 'hazard', 'municipal_target', 'other'
        )
    ),
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    source_verified boolean NOT NULL,
    attached_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (urban_state_id, dataset_role, dataset_version_id)
);
CREATE INDEX state_dataset_versions_version_idx
    ON state_dataset_versions (dataset_version_id, urban_state_id);

INSERT INTO state_dataset_versions (
    urban_state_id, dataset_role, dataset_version_id, source_verified, metadata
)
SELECT
    state.id,
    'plateau',
    version.registry_version_id,
    true,
    jsonb_build_object('legacy_dataset_version_id', version.id)
FROM urban_states AS state
JOIN city_dataset_versions AS version
  ON version.id = state.primary_plateau_dataset_version_id
WHERE version.registry_version_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE TABLE state_network_versions (
    urban_state_id uuid NOT NULL REFERENCES urban_states(id) ON DELETE CASCADE,
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id),
    purpose text NOT NULL DEFAULT 'baseline' CHECK (
        purpose IN ('baseline', 'future_fixed_service', 'scenario', 'stress_test')
    ),
    attached_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (urban_state_id, network_version_id, purpose)
);
CREATE INDEX state_network_versions_network_idx
    ON state_network_versions (network_version_id, urban_state_id);

INSERT INTO state_network_versions (urban_state_id, network_version_id, purpose)
SELECT state.id, network.id, 'baseline'
FROM urban_states AS state
JOIN road_network_versions AS network
  ON network.dataset_version_id = state.primary_plateau_dataset_version_id
ON CONFLICT DO NOTHING;

CREATE TABLE state_analysis_runs (
    urban_state_id uuid NOT NULL REFERENCES urban_states(id) ON DELETE CASCADE,
    analysis_run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    result_role text NOT NULL DEFAULT 'derived',
    attached_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (urban_state_id, analysis_run_id, result_role)
);

CREATE FUNCTION citygap_enforce_urban_state_lifecycle() RETURNS trigger AS $$
DECLARE
    unverified_inputs integer;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.lifecycle_status <> OLD.lifecycle_status THEN
        IF NOT (
            (OLD.lifecycle_status = 'draft' AND NEW.lifecycle_status IN ('validated', 'archived')) OR
            (OLD.lifecycle_status = 'validated' AND NEW.lifecycle_status IN ('current', 'draft', 'archived')) OR
            (OLD.lifecycle_status = 'current' AND NEW.lifecycle_status IN ('superseded', 'archived')) OR
            (OLD.lifecycle_status = 'superseded' AND NEW.lifecycle_status IN ('archived', 'validated'))
        ) THEN
            RAISE EXCEPTION 'invalid urban state lifecycle transition: % -> %',
                OLD.lifecycle_status, NEW.lifecycle_status;
        END IF;
    END IF;
    IF NEW.lifecycle_status IN ('validated', 'current') THEN
        IF NOT NEW.source_verified THEN
            RAISE EXCEPTION 'validated/current urban state requires verified source';
        END IF;
        SELECT count(*) INTO unverified_inputs
        FROM state_dataset_versions AS input
        WHERE input.urban_state_id = NEW.id AND NOT input.source_verified;
        IF unverified_inputs > 0 THEN
            RAISE EXCEPTION 'validated/current urban state has unverified dataset inputs';
        END IF;
        IF NEW.state_type = 'future' AND NOT EXISTS (
            SELECT 1 FROM state_dataset_versions AS input
            WHERE input.urban_state_id = NEW.id
              AND input.dataset_role = 'future_population'
              AND input.source_verified
        ) THEN
            RAISE EXCEPTION 'future urban state requires a verified future population source';
        END IF;
        NEW.validated_at = COALESCE(NEW.validated_at, now());
    END IF;
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER urban_states_lifecycle_transition
    BEFORE INSERT OR UPDATE OF lifecycle_status ON urban_states
    FOR EACH ROW EXECUTE FUNCTION citygap_enforce_urban_state_lifecycle();

ALTER TABLE scenario_runs ADD COLUMN base_urban_state_id uuid REFERENCES urban_states(id);
UPDATE scenario_runs AS scenario
SET base_urban_state_id = state.id
FROM urban_states AS state
WHERE state.primary_plateau_dataset_version_id = scenario.dataset_version_id
  AND state.state_type = 'observed';
ALTER TABLE scenario_runs ALTER COLUMN base_urban_state_id SET NOT NULL;
CREATE INDEX scenario_runs_base_state_idx
    ON scenario_runs (base_urban_state_id, lifecycle_status, generated_at DESC);

ALTER TABLE dataset_version_diffs
    DROP CONSTRAINT IF EXISTS dataset_version_diffs_change_type_check;
ALTER TABLE dataset_version_diffs
    ADD COLUMN from_gml_id text,
    ADD COLUMN to_gml_id text,
    ADD COLUMN from_geometry_sha256 char(64),
    ADD COLUMN to_geometry_sha256 char(64),
    ADD COLUMN from_attributes_sha256 char(64),
    ADD COLUMN to_attributes_sha256 char(64),
    ADD COLUMN matched_by text NOT NULL DEFAULT 'gml_id' CHECK (
        matched_by IN ('gml_id', 'geometry_hash', 'important_attribute_hash')
    );
UPDATE dataset_version_diffs
SET from_gml_id = CASE WHEN change_type <> 'added' THEN gml_id END,
    to_gml_id = CASE WHEN change_type <> 'removed' THEN gml_id END;
UPDATE dataset_version_diffs AS diff
SET from_geometry_sha256 = fingerprint.geometry_sha256,
    from_attributes_sha256 = fingerprint.attributes_sha256
FROM dataset_feature_fingerprints AS fingerprint
WHERE fingerprint.dataset_version_id = diff.from_dataset_version_id
  AND fingerprint.gml_id = diff.gml_id;
UPDATE dataset_version_diffs AS diff
SET to_geometry_sha256 = fingerprint.geometry_sha256,
    to_attributes_sha256 = fingerprint.attributes_sha256
FROM dataset_feature_fingerprints AS fingerprint
WHERE fingerprint.dataset_version_id = diff.to_dataset_version_id
  AND fingerprint.gml_id = diff.gml_id;
UPDATE dataset_version_diffs
SET change_type = CASE
    WHEN change_type <> 'changed' THEN change_type
    WHEN from_geometry_sha256 IS DISTINCT FROM to_geometry_sha256
     AND from_attributes_sha256 IS DISTINCT FROM to_attributes_sha256
        THEN 'geometry_and_attribute_changed'
    WHEN from_geometry_sha256 IS DISTINCT FROM to_geometry_sha256
        THEN 'geometry_changed'
    ELSE 'attribute_changed'
END;
ALTER TABLE dataset_version_diffs ADD CONSTRAINT dataset_version_diffs_change_type_check CHECK (
    change_type IN (
        'added', 'removed', 'geometry_changed', 'attribute_changed',
        'geometry_and_attribute_changed', 'unchanged'
    )
);
ALTER TABLE dataset_version_diffs ADD CONSTRAINT dataset_version_diffs_temporal_hash_check CHECK (
    (change_type = 'added' AND from_gml_id IS NULL AND to_gml_id IS NOT NULL) OR
    (change_type = 'removed' AND from_gml_id IS NOT NULL AND to_gml_id IS NULL) OR
    (change_type NOT IN ('added', 'removed') AND from_gml_id IS NOT NULL AND to_gml_id IS NOT NULL)
);

CREATE TABLE urban_state_change_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    from_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    to_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    status text NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'succeeded', 'failed')
    ),
    algorithm_version text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}',
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (from_urban_state_id, to_urban_state_id, algorithm_version),
    CHECK (from_urban_state_id <> to_urban_state_id),
    CHECK ((status = 'running' AND started_at IS NOT NULL AND completed_at IS NULL) OR
           (status IN ('succeeded', 'failed') AND started_at IS NOT NULL AND completed_at IS NOT NULL) OR
           status = 'pending')
);

CREATE TABLE urban_state_feature_changes (
    change_set_id uuid NOT NULL REFERENCES urban_state_change_sets(id) ON DELETE CASCADE,
    feature_key text NOT NULL,
    before_gml_id text,
    after_gml_id text,
    feature_type text NOT NULL,
    change_type text NOT NULL CHECK (
        change_type IN (
            'added', 'removed', 'geometry_changed', 'attribute_changed',
            'geometry_and_attribute_changed', 'unchanged'
        )
    ),
    matched_by text NOT NULL CHECK (
        matched_by IN ('gml_id', 'geometry_hash', 'important_attribute_hash')
    ),
    affected_envelope geometry(Geometry, 4326),
    important_attribute_changes jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (change_set_id, feature_key)
);
CREATE INDEX urban_state_feature_changes_kind_idx
    ON urban_state_feature_changes (change_set_id, feature_type, change_type);
CREATE INDEX urban_state_feature_changes_geom_idx
    ON urban_state_feature_changes USING gist (affected_envelope);

ALTER TABLE analysis_dependencies
    DROP CONSTRAINT IF EXISTS analysis_dependencies_dependent_type_check;
ALTER TABLE analysis_dependencies
    DROP CONSTRAINT IF EXISTS analysis_dependencies_dependency_type_check;
ALTER TABLE analysis_dependencies ADD CONSTRAINT analysis_dependencies_dependent_type_check CHECK (
    dependent_type IN (
        'analysis', 'network', 'scenario', 'urban_state', 'stress_test', 'evidence', 'outcome'
    )
);
ALTER TABLE analysis_dependencies ADD CONSTRAINT analysis_dependencies_dependency_type_check CHECK (
    dependency_type IN (
        'dataset_version', 'network_version', 'context_run', 'feature_type',
        'urban_state', 'population_version', 'facility_version', 'transport_version',
        'hazard_version', 'planning_version'
    )
);

CREATE TABLE recomputation_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_set_id uuid NOT NULL REFERENCES urban_state_change_sets(id) ON DELETE CASCADE,
    target_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    algorithm_version text NOT NULL,
    correctness_mode text NOT NULL DEFAULT 'conservative' CHECK (
        correctness_mode IN ('conservative', 'verified_incremental', 'full_rebuild_required')
    ),
    status text NOT NULL DEFAULT 'planned' CHECK (
        status IN ('planned', 'running', 'verified', 'failed')
    ),
    reason jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (change_set_id, target_urban_state_id, algorithm_version)
);

CREATE TABLE recomputation_scopes (
    recomputation_plan_id uuid NOT NULL REFERENCES recomputation_plans(id) ON DELETE CASCADE,
    analysis_type text NOT NULL,
    scope_type text NOT NULL CHECK (
        scope_type IN ('building', 'mesh', 'network_component', 'network_region', 'city')
    ),
    scope_key text NOT NULL,
    trigger_feature_types text[] NOT NULL,
    rationale text NOT NULL,
    PRIMARY KEY (recomputation_plan_id, analysis_type, scope_type, scope_key)
);

CREATE TABLE incremental_recompute_validations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recomputation_plan_id uuid NOT NULL REFERENCES recomputation_plans(id) ON DELETE CASCADE,
    analysis_type text NOT NULL,
    fixture_or_state text NOT NULL,
    incremental_result_sha256 char(64) NOT NULL,
    full_rebuild_result_sha256 char(64) NOT NULL,
    matched boolean GENERATED ALWAYS AS (
        incremental_result_sha256 = full_rebuild_result_sha256
    ) STORED,
    compared_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (recomputation_plan_id, analysis_type, fixture_or_state)
);

ALTER TABLE city_capabilities DROP CONSTRAINT IF EXISTS city_capabilities_capability_check;
ALTER TABLE city_capabilities ADD CONSTRAINT city_capabilities_capability_check CHECK (
    capability IN (
        'screening', 'building_detail', 'road_network', 'terrain', 'land_use',
        'urban_planning', 'hazard', 'gtfs', 'scenario', 'temporal_diff',
        'future_population', 'hazard_stress_test', 'criticality', 'field_mode',
        'outcome_monitoring', 'evacuation_reachability', 'planning_monitoring'
    )
);

CREATE VIEW temporal_result_provenance AS
SELECT
    state.id AS urban_state_id,
    city.city_code,
    state.state_key,
    state.effective_date,
    state.state_type,
    state.lifecycle_status,
    state.primary_plateau_dataset_version_id,
    plateau.archive_sha256 AS plateau_archive_sha256,
    network.network_version_id,
    road.graph_version,
    road.source_type AS network_source_type,
    analysis.analysis_run_id,
    run.analysis_type,
    run.config_hash,
    run.output_sha256
FROM urban_states AS state
JOIN cities AS city ON city.id = state.city_id
JOIN city_dataset_versions AS plateau
  ON plateau.id = state.primary_plateau_dataset_version_id
LEFT JOIN state_network_versions AS network ON network.urban_state_id = state.id
LEFT JOIN road_network_versions AS road ON road.id = network.network_version_id
LEFT JOIN state_analysis_runs AS analysis ON analysis.urban_state_id = state.id
LEFT JOIN analysis_runs AS run ON run.id = analysis.analysis_run_id;

COMMENT ON TABLE urban_states IS
    'Time-aware city state. Future rows are official source scenarios plus explicit CITY GAP allocation assumptions, never predictions.';
COMMENT ON TABLE urban_state_feature_changes IS
    'Version-aware feature comparison using gml:id and geometry/important-attribute hash fallbacks.';
COMMENT ON TABLE recomputation_plans IS
    'Conservative affected-scope plan; incremental output must match a full rebuild on validation fixtures.';
COMMENT ON VIEW temporal_result_provenance IS
    'Trace result -> urban state -> PLATEAU/network/dataset versions -> algorithm configuration.';

COMMIT;
