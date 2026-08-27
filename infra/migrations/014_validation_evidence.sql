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
        'stress_test', 'criticality_analysis', 'outcome_evaluation',
        'validation_run', 'validation_reproduce', 'pilot_rehearsal'
    )
);

CREATE TYPE validation_status AS ENUM (
    'unvalidated', 'internally_verified', 'cross_validated',
    'externally_validated', 'municipally_reviewed'
);

CREATE TYPE municipal_feedback AS ENUM (
    'confirmed', 'contradicted', 'partially_supported',
    'needs_more_data', 'not_reviewed'
);

CREATE TABLE validation_claims (
    claim_key text PRIMARY KEY,
    what_it_means text NOT NULL,
    what_it_does_not_mean text NOT NULL,
    required_data jsonb NOT NULL CHECK (jsonb_typeof(required_data) = 'array'),
    validation_method jsonb NOT NULL CHECK (jsonb_typeof(validation_method) = 'array'),
    current_validation_status validation_status NOT NULL DEFAULT 'unvalidated',
    status_changed_by text,
    status_changed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (current_validation_status = 'unvalidated' AND status_changed_by IS NULL AND status_changed_at IS NULL)
        OR current_validation_status <> 'unvalidated'
    )
);

CREATE TABLE validation_methods (
    method_key text PRIMARY KEY,
    title text NOT NULL,
    method_version text NOT NULL,
    independent_of_primary_model boolean NOT NULL,
    reference_semantics text NOT NULL CHECK (reference_semantics <> 'ground_truth'),
    algorithm_description text NOT NULL,
    limitations jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (method_key, method_version)
);

INSERT INTO validation_claims (
    claim_key, what_it_means, what_it_does_not_mean,
    required_data, validation_method, current_validation_status
) VALUES
('building_population_allocation', 'Census mesh totals are deterministically allocated under a named rule.', 'Not an observed person count for an individual building.', '["official_500m_census","plateau_buildings"]', '["mass_conservation","allocation_rule_sensitivity"]', 'internally_verified'),
('building_euclidean_accessibility', 'Straight-line distance to a versioned facility point is reproducible.', 'Not a walking route, travel time, or facility availability observation.', '["plateau_buildings","public_facilities"]', '["independent_geometry_certificate"]', 'internally_verified'),
('experimental_network_accessibility', 'A shortest path exists on the experimental road-surface adjacency graph.', 'Not an official or field-verified pedestrian route.', '["plateau_tran_lod1","public_facilities","reference_network"]', '["shortest_path_certificate","independent_reference_network_comparison"]', 'cross_validated'),
('hazard_stress_test', 'Reachability changes under a named edge-closure assumption.', 'Not a disaster probability, forecast, or observed road passability.', '["network_version","official_hazard_geometry","closure_rule"]', '["assumption_matrix"]', 'internally_verified'),
('network_criticality', 'Graph edges are review candidates under a stated topology model.', 'Not proof that a real road is unsafe or a policy priority.', '["network_version","building_snap"]', '["topology_sensitivity","map_audit"]', 'internally_verified'),
('future_population_allocation', 'An official population scenario is allocated under a named fixed-service rule.', 'Not a building-level forecast or selection of a best projection.', '["official_population_projection","plateau_buildings"]', '["allocation_rule_sensitivity","official_series_comparison"]', 'internally_verified'),
('scenario_improvement', 'Scenario metrics differ from a declared baseline under fixed assumptions.', 'Not a causal effect, policy optimum, or guaranteed real-world improvement.', '["urban_state","scenario_definition"]', '["canonical_replay","assumption_comparison"]', 'internally_verified'),
('planning_context', 'Planning and land-use attributes are joined to review candidates.', 'Not legal advice, compliance, permission, or feasibility.', '["plateau_urf","plateau_luse"]', '["provenance_and_join_coverage"]', 'internally_verified'),
('shelter_reachability', 'A model path to a published shelter exists under named assumptions.', 'Not confirmation that the shelter is open or reachable during an event.', '["published_shelters","network_version"]', '["network_comparison","facility_availability_review"]', 'unvalidated');

INSERT INTO validation_methods (
    method_key, title, method_version, independent_of_primary_model,
    reference_semantics, algorithm_description, limitations
) VALUES
('osm_reference_comparison', 'Pinned OSM same-OD route comparison', '1.0.0', true, 'reference_network', 'Deterministic stratified origins are snapped separately and compared on distance, connectivity, destination and geometry overlap.', '["OSM is not field ground truth","network semantics differ"]'),
('assumption_matrix', 'Bounded assumption sensitivity matrix', '1.0.0', false, 'independent_rule_variants', 'Runs only named, published hazard and topology rules and retains ranges without a combined score.', '["counterfactual rules are not probabilities"]'),
('real_citygml_temporal_diff', 'Official multi-year CityGML diff', '1.0.0', true, 'official_version_reference', 'Matches same identifiers then unique geometry and bounded attribute fallbacks; ambiguous matches are not forced.', '["source-version production changes may appear as urban changes"]'),
('municipal_field_review', 'Municipal field observation comparison', '1.0.0', true, 'field_observation', 'Stores explicit observation, GPS, time, reviewer and attachment reference without automatic claim promotion.', '["awaiting real municipal observations"]');

CREATE TABLE validation_reference_datasets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    reference_key text NOT NULL,
    source_type text NOT NULL CHECK (
        source_type IN ('official_plateau', 'municipal_public', 'other_public', 'osm')
    ),
    source_url text NOT NULL,
    retrieval_date date NOT NULL,
    source_sha256 char(64) NOT NULL,
    license text NOT NULL,
    attribution text NOT NULL,
    extraction_rule text NOT NULL,
    coverage jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('available', 'not_available', 'manual_import_required')),
    limitations jsonb NOT NULL,
    registered_by text NOT NULL,
    registered_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (city_id, reference_key)
);

CREATE TABLE validation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_key text NOT NULL UNIQUE,
    claim_key text NOT NULL REFERENCES validation_claims(claim_key),
    method_key text NOT NULL REFERENCES validation_methods(method_key),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    urban_state_id uuid REFERENCES urban_states(id),
    dataset_versions jsonb NOT NULL CHECK (jsonb_typeof(dataset_versions) = 'object'),
    network_version_id uuid REFERENCES road_network_versions(id),
    algorithm_version text NOT NULL,
    reference_source jsonb NOT NULL CHECK (jsonb_typeof(reference_source) = 'object'),
    sample_rule jsonb NOT NULL CHECK (jsonb_typeof(sample_rule) = 'object'),
    metrics jsonb NOT NULL DEFAULT '{}',
    result jsonb NOT NULL DEFAULT '{}',
    limitations jsonb NOT NULL,
    validation_status validation_status NOT NULL DEFAULT 'unvalidated',
    run_status text NOT NULL CHECK (
        run_status IN ('queued', 'running', 'completed', 'completed_with_limitations', 'failed')
    ),
    generated_at timestamptz NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX validation_runs_city_generated_idx
    ON validation_runs (city_id, generated_at DESC);

CREATE TABLE validation_samples (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_run_id uuid NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
    sample_key text NOT NULL,
    strata text[] NOT NULL CHECK (cardinality(strata) > 0),
    origin_reference text NOT NULL,
    destination_reference text NOT NULL,
    origin_snap jsonb NOT NULL,
    destination_snap jsonb NOT NULL,
    sampling_rank integer NOT NULL CHECK (sampling_rank > 0),
    geometry geometry(Geometry, 4326),
    metadata jsonb NOT NULL DEFAULT '{}',
    UNIQUE (validation_run_id, sample_key)
);
CREATE INDEX validation_samples_geom_idx ON validation_samples USING gist (geometry);

CREATE TABLE validation_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_run_id uuid NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
    validation_sample_id uuid REFERENCES validation_samples(id) ON DELETE CASCADE,
    result_key text NOT NULL,
    primary_model text NOT NULL,
    reference_model text NOT NULL CHECK (reference_model <> 'ground_truth'),
    metrics jsonb NOT NULL,
    known_limitation text NOT NULL,
    sensitivity_evidence jsonb NOT NULL DEFAULT '{}',
    reference_agreement text NOT NULL CHECK (
        reference_agreement IN (
            'distance_similar', 'moderate_difference', 'large_difference',
            'connectivity_agreement', 'connectivity_disagreement', 'not_available'
        )
    ),
    coverage jsonb NOT NULL,
    validation_status validation_status NOT NULL,
    evidence_strength jsonb NOT NULL CHECK (
        evidence_strength ?& ARRAY[
            'source_verified', 'reproducible', 'independent_verifier',
            'reference_model_agreement', 'assumption_sensitive',
            'municipal_review', 'field_verified'
        ]
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (validation_run_id, result_key, validation_sample_id)
);

CREATE TABLE validation_disagreements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_run_id uuid NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
    validation_sample_id uuid NOT NULL REFERENCES validation_samples(id) ON DELETE CASCADE,
    disagreement_class text NOT NULL CHECK (
        disagreement_class IN ('moderate_difference', 'large_difference', 'connectivity_disagreement')
    ),
    primary_value jsonb NOT NULL,
    reference_value jsonb NOT NULL,
    cause_candidate text NOT NULL CHECK (
        cause_candidate IN (
            'topology', 'crossing', 'bridge', 'road_coverage', 'snap',
            'one_way', 'pedestrian_permission', 'geometry_resolution', 'undetermined'
        )
    ),
    cause_rule text NOT NULL,
    priority_rank integer CHECK (priority_rank > 0),
    geometry geometry(Geometry, 4326),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (validation_run_id, validation_sample_id)
);
CREATE INDEX validation_disagreements_geom_idx
    ON validation_disagreements USING gist (geometry);

CREATE TABLE validation_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_run_id uuid NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
    artifact_key text NOT NULL,
    artifact_format text NOT NULL CHECK (artifact_format IN ('json', 'csv', 'html', 'geojson', 'png')),
    artifact_uri text NOT NULL,
    sha256 char(64) NOT NULL,
    content_bytes bigint NOT NULL CHECK (content_bytes >= 0),
    public_safe boolean NOT NULL DEFAULT false,
    provenance jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (validation_run_id, artifact_key, artifact_format)
);

CREATE TABLE model_uncertainty (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_key text NOT NULL REFERENCES validation_claims(claim_key),
    validation_run_id uuid REFERENCES validation_runs(id) ON DELETE CASCADE,
    category text NOT NULL CHECK (
        category IN (
            'data_coverage', 'temporal_mismatch', 'model_approximation',
            'network_semantics', 'facility_availability', 'scenario_assumption',
            'population_allocation', 'optimization_approximation'
        )
    ),
    known_limitation text NOT NULL,
    sensitivity_evidence jsonb NOT NULL,
    reference_agreement text NOT NULL,
    coverage jsonb NOT NULL,
    validation_status validation_status NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE field_validation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_result_id uuid NOT NULL REFERENCES validation_results(id) ON DELETE CASCADE,
    observation_type text NOT NULL,
    observed_accessibility_issue text,
    road_passability text CHECK (
        road_passability IS NULL OR road_passability IN ('passable', 'not_passable', 'uncertain')
    ),
    facility_availability text CHECK (
        facility_availability IS NULL OR facility_availability IN ('available', 'unavailable', 'uncertain')
    ),
    gps geometry(Point, 4326),
    observed_at timestamptz NOT NULL,
    reviewer text NOT NULL,
    evidence_attachment_reference text,
    municipal_feedback municipal_feedback NOT NULL DEFAULT 'not_reviewed',
    review_note text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'awaiting_field_validation' CHECK (
        status IN ('awaiting_field_validation', 'submitted', 'reviewed', 'rejected')
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (status = 'awaiting_field_validation' AND municipal_feedback = 'not_reviewed')
        OR status <> 'awaiting_field_validation'
    )
);
CREATE INDEX field_validation_gps_idx ON field_validation USING gist (gps);

COMMIT;
