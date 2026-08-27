BEGIN;

ALTER TABLE facility_registry
    ADD COLUMN critical_service_category text CHECK (
        critical_service_category IN (
            'medical', 'emergency', 'evacuation', 'administrative', 'transport_hub'
        )
    ),
    ADD COLUMN capacity integer CHECK (capacity IS NULL OR capacity >= 0),
    ADD COLUMN hazard_applicability text[] NOT NULL DEFAULT '{}',
    ADD COLUMN source_verified boolean NOT NULL DEFAULT false,
    ADD COLUMN source_url text,
    ADD COLUMN effective_from date,
    ADD COLUMN effective_to date,
    ADD CONSTRAINT facility_registry_effective_dates CHECK (
        effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from
    );
CREATE INDEX facility_registry_critical_idx
    ON facility_registry (dataset_version_id, critical_service_category)
    WHERE critical_service_category IS NOT NULL;

CREATE TABLE stress_test_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    base_urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id),
    stress_test_key text NOT NULL,
    title text NOT NULL,
    stress_test_type text NOT NULL CHECK (
        stress_test_type IN (
            'edge_closure', 'road_group_closure', 'area_closure',
            'hazard_counterfactual', 'service_change'
        )
    ),
    status text NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'queued', 'running', 'succeeded', 'failed', 'archived')
    ),
    assumption_hash char(64) NOT NULL,
    algorithm_version text NOT NULL,
    cache_key char(64) NOT NULL,
    route_semantics text NOT NULL,
    prediction_claimed boolean NOT NULL DEFAULT false CHECK (NOT prediction_claimed),
    limitation text NOT NULL CHECK (
        length(limitation) > 0
    ),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}',
    UNIQUE (city_id, stress_test_key),
    UNIQUE (cache_key),
    CHECK ((status IN ('draft', 'queued') AND completed_at IS NULL) OR
           (status = 'running' AND started_at IS NOT NULL AND completed_at IS NULL) OR
           (status IN ('succeeded', 'failed', 'archived') AND completed_at IS NOT NULL))
);
CREATE INDEX stress_test_runs_state_idx
    ON stress_test_runs (base_urban_state_id, created_at DESC);

CREATE TABLE stress_test_assumptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    stress_test_run_id uuid NOT NULL REFERENCES stress_test_runs(id) ON DELETE CASCADE,
    assumption_type text NOT NULL CHECK (
        assumption_type IN (
            'edge_closure', 'road_group_closure', 'area_closure',
            'hazard_overlap_closure', 'service_open', 'service_close',
            'service_relocate', 'service_temporary_unavailable'
        )
    ),
    hazard_dataset_version_id uuid REFERENCES dataset_versions(id),
    hazard_type text,
    hazard_class text,
    closure_assumption text NOT NULL,
    assumption_payload jsonb NOT NULL,
    assumption_source text NOT NULL,
    explicitly_confirmed boolean NOT NULL CHECK (explicitly_confirmed),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        assumption_type <> 'hazard_overlap_closure' OR
        (hazard_dataset_version_id IS NOT NULL AND hazard_type IS NOT NULL AND hazard_class IS NOT NULL)
    )
);
CREATE INDEX stress_test_assumptions_run_idx
    ON stress_test_assumptions (stress_test_run_id, assumption_type);

CREATE TABLE stress_test_edge_impacts (
    stress_test_run_id uuid NOT NULL REFERENCES stress_test_runs(id) ON DELETE CASCADE,
    edge_id text NOT NULL,
    road_gml_id text,
    impact_kind text NOT NULL CHECK (
        impact_kind IN ('closed_by_assumption', 'route_changed', 'criticality_candidate')
    ),
    baseline_component_id text,
    scenario_component_id text,
    affected_buildings integer NOT NULL DEFAULT 0 CHECK (affected_buildings >= 0),
    affected_estimated_elderly_population double precision NOT NULL DEFAULT 0 CHECK (
        affected_estimated_elderly_population >= 0
    ),
    evidence jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (stress_test_run_id, edge_id, impact_kind)
);
CREATE INDEX stress_test_edge_impacts_edge_idx
    ON stress_test_edge_impacts (edge_id, stress_test_run_id);

CREATE TABLE stress_test_building_impacts (
    stress_test_run_id uuid NOT NULL REFERENCES stress_test_runs(id) ON DELETE CASCADE,
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    building_gml_id text NOT NULL,
    service_category text NOT NULL CHECK (
        service_category IN (
            'medical', 'emergency', 'evacuation', 'administrative', 'transport_hub'
        )
    ),
    baseline_distance_m double precision CHECK (baseline_distance_m >= 0),
    scenario_distance_m double precision CHECK (scenario_distance_m >= 0),
    impact_status text NOT NULL CHECK (
        impact_status IN ('unchanged', 'increased', 'disconnected', 'already_unreachable')
    ),
    estimated_population double precision NOT NULL DEFAULT 0 CHECK (estimated_population >= 0),
    estimated_elderly_population double precision NOT NULL DEFAULT 0 CHECK (
        estimated_elderly_population >= 0
    ),
    evidence jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (stress_test_run_id, building_gml_id, service_category),
    FOREIGN KEY (dataset_version_id, building_gml_id)
        REFERENCES plateau_city_objects(dataset_version_id, gml_id) ON DELETE CASCADE,
    CHECK (
        (impact_status = 'disconnected' AND baseline_distance_m IS NOT NULL AND scenario_distance_m IS NULL) OR
        (impact_status = 'already_unreachable' AND baseline_distance_m IS NULL) OR
        (impact_status IN ('unchanged', 'increased') AND
         baseline_distance_m IS NOT NULL AND scenario_distance_m IS NOT NULL)
    )
);
CREATE INDEX stress_test_building_impacts_status_idx
    ON stress_test_building_impacts (stress_test_run_id, service_category, impact_status);

CREATE TABLE stress_test_facility_impacts (
    stress_test_run_id uuid NOT NULL REFERENCES stress_test_runs(id) ON DELETE CASCADE,
    facility_id uuid NOT NULL REFERENCES facility_registry(id),
    service_category text NOT NULL CHECK (
        service_category IN (
            'medical', 'emergency', 'evacuation', 'administrative', 'transport_hub'
        )
    ),
    change_action text CHECK (
        change_action IN ('open', 'close', 'relocate', 'temporary_unavailable')
    ),
    baseline_reachable_buildings integer CHECK (baseline_reachable_buildings >= 0),
    scenario_reachable_buildings integer CHECK (scenario_reachable_buildings >= 0),
    evidence jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (stress_test_run_id, facility_id)
);

CREATE TABLE stress_test_metrics (
    stress_test_run_id uuid NOT NULL REFERENCES stress_test_runs(id) ON DELETE CASCADE,
    metric_name text NOT NULL,
    service_category text,
    value double precision NOT NULL,
    unit text NOT NULL,
    definition text NOT NULL,
    PRIMARY KEY (stress_test_run_id, metric_name, service_category)
);

CREATE TABLE network_precomputations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    urban_state_id uuid NOT NULL REFERENCES urban_states(id) ON DELETE CASCADE,
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id) ON DELETE CASCADE,
    facility_version_key text NOT NULL,
    precomputation_type text NOT NULL CHECK (
        precomputation_type IN (
            'adjacency', 'components', 'bridges', 'biconnected_components',
            'service_seeds', 'demand_by_node'
        )
    ),
    algorithm_version text NOT NULL,
    input_hash char(64) NOT NULL,
    artifact_uri text,
    artifact_sha256 char(64),
    summary jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (
        urban_state_id, network_version_id, facility_version_key,
        precomputation_type, algorithm_version, input_hash
    ),
    CHECK ((artifact_uri IS NULL AND artifact_sha256 IS NULL) OR
           (artifact_uri IS NOT NULL AND artifact_sha256 IS NOT NULL))
);

CREATE TABLE stress_test_result_cache (
    cache_key char(64) PRIMARY KEY,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    urban_state_id uuid NOT NULL REFERENCES urban_states(id) ON DELETE CASCADE,
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id) ON DELETE CASCADE,
    assumption_hash char(64) NOT NULL,
    algorithm_version text NOT NULL,
    stress_test_run_id uuid NOT NULL UNIQUE REFERENCES stress_test_runs(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE network_criticality_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id),
    facility_version_key text NOT NULL,
    algorithm_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    runtime_seconds double precision CHECK (runtime_seconds >= 0),
    peak_rss_kib bigint CHECK (peak_rss_kib >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (urban_state_id, network_version_id, facility_version_key, algorithm_version),
    CHECK ((status = 'running' AND completed_at IS NULL) OR
           (status IN ('succeeded', 'failed') AND completed_at IS NOT NULL))
);

CREATE TABLE network_criticality_candidates (
    criticality_run_id uuid NOT NULL REFERENCES network_criticality_runs(id) ON DELETE CASCADE,
    rank integer NOT NULL CHECK (rank > 0),
    edge_id text NOT NULL,
    road_gml_ids text[] NOT NULL DEFAULT '{}',
    connected_component_id text NOT NULL,
    isolated_node_count integer NOT NULL CHECK (isolated_node_count >= 0),
    affected_buildings integer NOT NULL CHECK (affected_buildings >= 0),
    affected_estimated_elderly_population double precision NOT NULL CHECK (
        affected_estimated_elderly_population >= 0
    ),
    facility_reachability_change jsonb NOT NULL,
    candidate_label text NOT NULL DEFAULT 'network criticality candidate' CHECK (
        candidate_label = 'network criticality candidate'
    ),
    evidence jsonb NOT NULL,
    PRIMARY KEY (criticality_run_id, edge_id),
    UNIQUE (criticality_run_id, rank)
);
CREATE INDEX network_criticality_candidates_impact_idx
    ON network_criticality_candidates (
        criticality_run_id, affected_buildings DESC,
        affected_estimated_elderly_population DESC
    );

CREATE TABLE route_redundancy_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id),
    origin_key text NOT NULL,
    destination_key text NOT NULL,
    primary_distance_m double precision NOT NULL CHECK (primary_distance_m >= 0),
    alternative_route_available boolean NOT NULL,
    second_best_distance_m double precision CHECK (second_best_distance_m >= 0),
    primary_edge_ids text[] NOT NULL,
    second_best_edge_ids text[] NOT NULL DEFAULT '{}',
    algorithm_version text NOT NULL,
    route_semantics text NOT NULL,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (urban_state_id, network_version_id, origin_key, destination_key, algorithm_version),
    CHECK ((alternative_route_available AND second_best_distance_m IS NOT NULL AND
            cardinality(second_best_edge_ids) > 0) OR
           (NOT alternative_route_available AND second_best_distance_m IS NULL AND
            cardinality(second_best_edge_ids) = 0))
);

CREATE FUNCTION citygap_validate_stress_test_completion() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'succeeded' AND OLD.status <> 'succeeded' THEN
        IF NOT EXISTS (
            SELECT 1 FROM stress_test_assumptions AS assumption
            WHERE assumption.stress_test_run_id = NEW.id
              AND assumption.explicitly_confirmed
        ) THEN
            RAISE EXCEPTION 'succeeded stress test requires an explicit assumption';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM stress_test_metrics AS metric
            WHERE metric.stress_test_run_id = NEW.id
        ) THEN
            RAISE EXCEPTION 'succeeded stress test requires persisted metrics';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER stress_test_completion_gate
    BEFORE UPDATE OF status ON stress_test_runs
    FOR EACH ROW EXECUTE FUNCTION citygap_validate_stress_test_completion();

COMMENT ON TABLE stress_test_runs IS
    'Counterfactual service/network continuity analysis; prediction_claimed is permanently false.';
COMMENT ON TABLE stress_test_assumptions IS
    'Hazard overlap never closes a road without an explicit, persisted analyst assumption.';
COMMENT ON TABLE network_criticality_candidates IS
    'Candidates for municipal review, never an automatic dangerous-road classification.';
COMMENT ON TABLE route_redundancy_results IS
    'Selected-pair route redundancy on the declared network model; not evacuation simulation.';

COMMIT;
