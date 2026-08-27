BEGIN;

ALTER TABLE job_runs DROP CONSTRAINT job_runs_job_type_check;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_job_type_check CHECK (
    job_type IN (
        'plateau_ingestion', 'building_demographics',
        'road_network', 'network_generation',
        'terrain', 'terrain_enrichment',
        'spatial_context', 'context_generation',
        'scenario_optimization', 'evidence_export',
        'dataset_diff', 'incremental_recompute', 'future_population',
        'stress_test', 'criticality_analysis', 'outcome_evaluation'
    )
);

CREATE TABLE future_population_states (
    urban_state_id uuid PRIMARY KEY REFERENCES urban_states(id) ON DELETE CASCADE,
    official_dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    projection_series text NOT NULL,
    projection_year integer NOT NULL CHECK (projection_year BETWEEN 2020 AND 2200),
    total_population integer NOT NULL CHECK (total_population >= 0),
    age_0_14 integer NOT NULL CHECK (age_0_14 >= 0),
    age_15_64 integer NOT NULL CHECK (age_15_64 >= 0),
    age_65_plus integer NOT NULL CHECK (age_65_plus >= 0),
    age_65_74 integer NOT NULL CHECK (age_65_74 >= 0),
    age_75_plus integer NOT NULL CHECK (age_75_plus >= 0),
    source_verified boolean NOT NULL CHECK (source_verified),
    allocation_algorithm_version text NOT NULL,
    allocation_assumption text NOT NULL CHECK (length(allocation_assumption) > 0),
    fixed_service_assumption boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (age_0_14 + age_15_64 + age_65_plus = total_population),
    CHECK (age_65_74 + age_75_plus = age_65_plus)
);

CREATE TABLE future_building_allocations (
    urban_state_id uuid NOT NULL REFERENCES future_population_states(urban_state_id)
        ON DELETE CASCADE,
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    building_gml_id text NOT NULL,
    mesh_code text NOT NULL,
    residential_capacity_weight double precision NOT NULL CHECK (
        residential_capacity_weight >= 0
    ),
    estimated_future_population double precision NOT NULL CHECK (
        estimated_future_population >= 0
    ),
    estimated_future_elderly_population double precision NOT NULL CHECK (
        estimated_future_elderly_population >= 0
    ),
    population_semantics text NOT NULL CHECK (
        population_semantics =
        'official demographic projection + CITY GAP PLATEAU residential-capacity allocation'
    ),
    PRIMARY KEY (urban_state_id, building_gml_id, mesh_code),
    FOREIGN KEY (dataset_version_id, building_gml_id)
        REFERENCES plateau_city_objects(dataset_version_id, gml_id) ON DELETE CASCADE
);
CREATE INDEX future_building_allocations_mesh_idx
    ON future_building_allocations (urban_state_id, mesh_code);

CREATE TABLE future_accessibility_metrics (
    urban_state_id uuid NOT NULL REFERENCES future_population_states(urban_state_id)
        ON DELETE CASCADE,
    metric_name text NOT NULL,
    value double precision NOT NULL,
    unit text NOT NULL,
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id),
    facility_version_key text NOT NULL,
    fixed_service_assumption boolean NOT NULL CHECK (fixed_service_assumption),
    limitation text NOT NULL CHECK (
        limitation = 'official population scenario under fixed service assumptions'
    ),
    PRIMARY KEY (urban_state_id, metric_name)
);

CREATE TABLE planning_context_comparisons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    urban_state_id uuid NOT NULL REFERENCES urban_states(id) ON DELETE CASCADE,
    planning_dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    landuse_dataset_version_id uuid REFERENCES dataset_versions(id),
    comparison_key text NOT NULL,
    planning_designation text NOT NULL,
    current_building_use_composition jsonb NOT NULL,
    current_demographic_context jsonb NOT NULL DEFAULT '{}',
    candidate_label text NOT NULL DEFAULT 'planning-context mismatch candidate' CHECK (
        candidate_label IN ('planning-context mismatch candidate', 'review candidate')
    ),
    legal_compliance_claimed boolean NOT NULL DEFAULT false CHECK (NOT legal_compliance_claimed),
    evidence jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (urban_state_id, comparison_key)
);

CREATE TABLE municipal_target_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    target_set_key text NOT NULL,
    title text NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    source_verified boolean NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (city_id, target_set_key),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE municipal_targets (
    target_set_id uuid NOT NULL REFERENCES municipal_target_sets(id) ON DELETE CASCADE,
    target_key text NOT NULL,
    target_type text NOT NULL CHECK (
        target_type IN ('population', 'facility_coverage', 'urban_function', 'custom_numeric')
    ),
    target_year integer NOT NULL CHECK (target_year BETWEEN 1900 AND 2200),
    target_value double precision NOT NULL,
    unit text NOT NULL,
    area_key text,
    geometry geometry(Geometry, 4326),
    source_record_id text,
    metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (target_set_id, target_key),
    CHECK (area_key IS NOT NULL OR geometry IS NOT NULL)
);
CREATE INDEX municipal_targets_geom_idx ON municipal_targets USING gist (geometry);

CREATE TABLE policy_portfolios (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    base_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    portfolio_key text NOT NULL,
    title text NOT NULL,
    lifecycle_status text NOT NULL DEFAULT 'draft' CHECK (
        lifecycle_status IN ('draft', 'under_review', 'reviewed', 'archived')
    ),
    budget_constraint_enabled boolean NOT NULL DEFAULT false,
    currency text,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (city_id, portfolio_key),
    CHECK ((budget_constraint_enabled AND currency IS NOT NULL) OR
           (NOT budget_constraint_enabled))
);

CREATE TABLE portfolio_interventions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id uuid NOT NULL REFERENCES policy_portfolios(id) ON DELETE CASCADE,
    intervention_key text NOT NULL,
    intervention_type text NOT NULL CHECK (
        intervention_type IN (
            'transit_support', 'facility_opening', 'facility_closure',
            'facility_relocation', 'road_resilience_action', 'service_change'
        )
    ),
    implementation_year integer NOT NULL CHECK (implementation_year BETWEEN 2000 AND 2200),
    site_id text NOT NULL,
    effect_model text NOT NULL,
    effect_parameters jsonb NOT NULL,
    source_scenario_run_id uuid REFERENCES scenario_runs(id),
    sequence integer NOT NULL CHECK (sequence > 0),
    UNIQUE (portfolio_id, intervention_key),
    UNIQUE (portfolio_id, sequence)
);

CREATE TABLE external_cost_inputs (
    portfolio_intervention_id uuid PRIMARY KEY REFERENCES portfolio_interventions(id)
        ON DELETE CASCADE,
    cost double precision NOT NULL CHECK (cost >= 0),
    currency text NOT NULL,
    cost_year integer NOT NULL CHECK (cost_year BETWEEN 1900 AND 2200),
    category text NOT NULL,
    source_dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    source_record_id text NOT NULL,
    source_verified boolean NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE implementation_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_intervention_id uuid NOT NULL REFERENCES portfolio_interventions(id),
    status text NOT NULL CHECK (
        status IN ('planned', 'approved', 'implemented', 'cancelled', 'unknown')
    ),
    effective_date date,
    recorded_by text NOT NULL,
    note text NOT NULL DEFAULT '',
    evidence jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX implementation_records_intervention_idx
    ON implementation_records (portfolio_intervention_id, created_at DESC);

CREATE TABLE outcome_evaluations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation_record_id uuid NOT NULL REFERENCES implementation_records(id),
    baseline_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    expected_scenario_run_id uuid REFERENCES scenario_runs(id),
    observed_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    status text NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'under_review', 'reviewed', 'archived')
    ),
    causal_effect_claimed boolean NOT NULL DEFAULT false CHECK (NOT causal_effect_claimed),
    planned_effect jsonb NOT NULL,
    observed_change jsonb NOT NULL,
    reviewer_note text NOT NULL DEFAULT '',
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    CHECK (baseline_urban_state_id <> observed_urban_state_id),
    CHECK ((status = 'reviewed' AND reviewed_at IS NOT NULL) OR status <> 'reviewed')
);

ALTER TABLE scenario_field_checks
    ADD COLUMN record_version bigint NOT NULL DEFAULT 1 CHECK (record_version > 0),
    ADD COLUMN updated_by text NOT NULL DEFAULT 'migration',
    ADD COLUMN gps_confirmation jsonb NOT NULL DEFAULT '{}',
    ADD CONSTRAINT scenario_field_checks_gps_bounded CHECK (
        octet_length(gps_confirmation::text) <= 8192
    );

CREATE FUNCTION citygap_increment_field_record_version() RETURNS trigger AS $$
BEGIN
    IF NEW IS DISTINCT FROM OLD THEN
        NEW.record_version = OLD.record_version + 1;
        NEW.updated_at = now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER scenario_field_checks_record_version
    BEFORE UPDATE ON scenario_field_checks
    FOR EACH ROW EXECUTE FUNCTION citygap_increment_field_record_version();

CREATE TABLE field_offline_packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id),
    site_order integer NOT NULL,
    package_version integer NOT NULL DEFAULT 1 CHECK (package_version > 0),
    content jsonb NOT NULL,
    content_sha256 char(64) NOT NULL,
    expires_at timestamptz,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scenario_run_id, site_order, package_version),
    FOREIGN KEY (scenario_run_id, site_order)
        REFERENCES scenario_sites(scenario_run_id, site_order) ON DELETE CASCADE,
    CHECK (octet_length(content::text) <= 2097152)
);

CREATE TABLE field_sync_operations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_operation_id uuid NOT NULL UNIQUE,
    offline_package_id uuid NOT NULL REFERENCES field_offline_packages(id),
    scenario_run_id uuid NOT NULL,
    site_order integer NOT NULL,
    actor text NOT NULL,
    base_record_version bigint NOT NULL CHECK (base_record_version > 0),
    client_updated_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'applied', 'conflict', 'rejected')
    ),
    received_at timestamptz NOT NULL DEFAULT now(),
    applied_at timestamptz,
    FOREIGN KEY (scenario_run_id, site_order)
        REFERENCES scenario_field_checks(scenario_run_id, site_order),
    CHECK ((status = 'applied' AND applied_at IS NOT NULL) OR
           (status <> 'applied' AND applied_at IS NULL)),
    CHECK (octet_length(payload::text) <= 65536)
);

CREATE TABLE field_sync_conflicts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    field_sync_operation_id uuid NOT NULL UNIQUE REFERENCES field_sync_operations(id)
        ON DELETE CASCADE,
    server_record_version bigint NOT NULL CHECK (server_record_version > 0),
    server_state jsonb NOT NULL,
    client_state jsonb NOT NULL,
    resolution_status text NOT NULL DEFAULT 'unresolved' CHECK (
        resolution_status IN ('unresolved', 'use_server', 'use_client', 'merged')
    ),
    resolved_state jsonb,
    resolved_by text,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((resolution_status = 'unresolved' AND resolved_state IS NULL AND
            resolved_by IS NULL AND resolved_at IS NULL) OR
           (resolution_status <> 'unresolved' AND resolved_state IS NOT NULL AND
            resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
);

CREATE TABLE temporal_evidence_packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    comparison_state_ids uuid[] NOT NULL DEFAULT '{}',
    stress_test_run_id uuid REFERENCES stress_test_runs(id),
    criticality_run_id uuid REFERENCES network_criticality_runs(id),
    portfolio_id uuid REFERENCES policy_portfolios(id),
    outcome_evaluation_id uuid REFERENCES outcome_evaluations(id),
    package_key text NOT NULL,
    schema_version text NOT NULL DEFAULT 'evidence-v3.0.0',
    limitations jsonb NOT NULL,
    manifest_sha256 char(64) NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (city_id, package_key)
);

CREATE TABLE temporal_evidence_artifacts (
    evidence_package_id uuid NOT NULL REFERENCES temporal_evidence_packages(id)
        ON DELETE CASCADE,
    artifact_format text NOT NULL CHECK (artifact_format IN ('json', 'csv', 'html')),
    artifact_uri text NOT NULL,
    artifact_sha256 char(64) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    PRIMARY KEY (evidence_package_id, artifact_format)
);

CREATE TABLE municipal_annual_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    from_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    to_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    report_year integer NOT NULL CHECK (report_year BETWEEN 1900 AND 2200),
    structured_metrics jsonb NOT NULL,
    charts_manifest jsonb NOT NULL DEFAULT '[]',
    maps_manifest jsonb NOT NULL DEFAULT '[]',
    deterministic_generator_version text NOT NULL,
    artifact_uri text NOT NULL,
    artifact_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (city_id, from_urban_state_id, to_urban_state_id),
    CHECK (from_urban_state_id <> to_urban_state_id)
);

COMMENT ON TABLE future_population_states IS
    'Official demographic projection inputs only; CITY GAP allocation is explicit and is not a building-resident prediction.';
COMMENT ON TABLE planning_context_comparisons IS
    'Review candidates only. Automated legal compliance or zoning-violation claims are forbidden.';
COMMENT ON TABLE external_cost_inputs IS
    'Budget comparison uses only municipality-supplied, versioned costs; missing costs are never generated.';
COMMENT ON TABLE outcome_evaluations IS
    'Planned effect and observed change are separated; causal_effect_claimed is permanently false.';
COMMENT ON TABLE field_sync_conflicts IS
    'Offline conflicts require explicit resolution; silent last-write-wins is not permitted.';

COMMIT;
