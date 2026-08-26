BEGIN;

CREATE TABLE scenario_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_key text NOT NULL,
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id),
    context_run_id uuid REFERENCES spatial_context_runs(id),
    plateau_product_specification_version text NOT NULL,
    algorithm_version text NOT NULL,
    objective_mode text NOT NULL CHECK (
        objective_mode IN (
            'overall', 'elderly', 'worst_served', 'robust', 'balanced', 'reachability'
        )
    ),
    objective_definition text NOT NULL,
    site_count integer NOT NULL CHECK (site_count BETWEEN 1 AND 20),
    candidate_count integer NOT NULL CHECK (candidate_count > 0),
    algorithm_kind text NOT NULL CHECK (
        algorithm_kind IN ('exact', 'deterministic_greedy_approximation')
    ),
    config_hash text NOT NULL CHECK (config_hash ~ '^[0-9a-f]{64}$'),
    generated_at timestamptz NOT NULL,
    runtime_seconds double precision NOT NULL CHECK (runtime_seconds >= 0),
    lifecycle_status text NOT NULL DEFAULT 'draft' CHECK (
        lifecycle_status IN (
            'draft', 'under_review', 'field_check_required', 'reviewed', 'archived'
        )
    ),
    reviewed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_version_id, network_version_id, scenario_key, config_hash),
    CHECK (
        (lifecycle_status = 'reviewed' AND reviewed_at IS NOT NULL) OR
        (lifecycle_status <> 'reviewed' AND reviewed_at IS NULL)
    )
);
CREATE INDEX scenario_runs_city_version_idx
    ON scenario_runs (dataset_version_id, network_version_id, lifecycle_status);
CREATE INDEX scenario_runs_objective_idx
    ON scenario_runs (objective_mode, site_count);

CREATE FUNCTION citygap_enforce_scenario_transition() RETURNS trigger AS $$
BEGIN
    IF NEW.lifecycle_status = OLD.lifecycle_status THEN
        RETURN NEW;
    END IF;
    IF (OLD.lifecycle_status = 'draft' AND
        NEW.lifecycle_status IN ('under_review', 'archived')) OR
       (OLD.lifecycle_status = 'under_review' AND
        NEW.lifecycle_status IN ('field_check_required', 'reviewed', 'archived')) OR
       (OLD.lifecycle_status = 'field_check_required' AND
        NEW.lifecycle_status IN ('under_review', 'reviewed', 'archived')) OR
       (OLD.lifecycle_status = 'reviewed' AND
        NEW.lifecycle_status IN ('under_review', 'archived')) THEN
        NEW.updated_at = now();
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid scenario lifecycle transition: % -> %',
        OLD.lifecycle_status, NEW.lifecycle_status;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER scenario_runs_lifecycle_transition
    BEFORE UPDATE OF lifecycle_status ON scenario_runs
    FOR EACH ROW EXECUTE FUNCTION citygap_enforce_scenario_transition();

CREATE TABLE scenario_sites (
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id) ON DELETE CASCADE,
    site_order integer NOT NULL CHECK (site_order > 0),
    candidate_id text NOT NULL,
    network_node_id text NOT NULL,
    road_gml_id text NOT NULL,
    road_surface_id text NOT NULL,
    road_name text,
    existing_transport_distance_m double precision CHECK (existing_transport_distance_m >= 0),
    component_id text NOT NULL,
    candidate_to_graph_connector_m double precision NOT NULL CHECK (
        candidate_to_graph_connector_m >= 0
    ),
    siting_feasibility text NOT NULL DEFAULT 'not_determined' CHECK (
        siting_feasibility = 'not_determined'
    ),
    geom geometry(Point, 4326) NOT NULL,
    PRIMARY KEY (scenario_run_id, site_order),
    UNIQUE (scenario_run_id, candidate_id)
);
CREATE INDEX scenario_sites_candidate_idx ON scenario_sites (candidate_id);
CREATE INDEX scenario_sites_geom_idx ON scenario_sites USING gist (geom);

CREATE TABLE scenario_objectives (
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id) ON DELETE CASCADE,
    objective_name text NOT NULL,
    objective_role text NOT NULL CHECK (objective_role IN ('selection', 'evaluation')),
    value double precision,
    unit text,
    definition text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (scenario_run_id, objective_name)
);

CREATE TABLE scenario_constraints (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id) ON DELETE CASCADE,
    site_order integer,
    constraint_name text NOT NULL,
    threshold jsonb,
    observed jsonb NOT NULL,
    satisfied boolean,
    interpretation text NOT NULL,
    FOREIGN KEY (scenario_run_id, site_order)
        REFERENCES scenario_sites(scenario_run_id, site_order)
);

CREATE TABLE scenario_impacts (
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id) ON DELETE CASCADE,
    metric_name text NOT NULL,
    value double precision NOT NULL,
    unit text NOT NULL,
    interpretation text,
    PRIMARY KEY (scenario_run_id, metric_name)
);

CREATE TABLE scenario_context (
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id) ON DELETE CASCADE,
    site_order integer NOT NULL,
    context_type text NOT NULL CHECK (
        context_type IN ('landuse', 'planning', 'hazard', 'terrain', 'road')
    ),
    label text,
    feature_count integer CHECK (feature_count >= 0),
    review_status text,
    siting_feasibility text NOT NULL DEFAULT 'not_determined' CHECK (
        siting_feasibility = 'not_determined'
    ),
    source_payload jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (scenario_run_id, site_order, context_type),
    FOREIGN KEY (scenario_run_id, site_order)
        REFERENCES scenario_sites(scenario_run_id, site_order)
);

CREATE TABLE scenario_evidence (
    scenario_run_id uuid PRIMARY KEY REFERENCES scenario_runs(id) ON DELETE CASCADE,
    representative_building_gml_id text NOT NULL,
    virtual_candidate_id text NOT NULL,
    route_semantics text NOT NULL,
    evidence jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX scenario_evidence_payload_idx ON scenario_evidence USING gin (evidence);

CREATE TABLE scenario_field_checks (
    scenario_run_id uuid NOT NULL,
    site_order integer NOT NULL,
    site_access text NOT NULL DEFAULT 'unknown',
    road_safety text NOT NULL DEFAULT 'unknown',
    land_ownership_unknown text NOT NULL DEFAULT 'unknown',
    existing_service text NOT NULL DEFAULT 'unknown',
    facility_condition text NOT NULL DEFAULT 'unknown',
    hazard_confirmation text NOT NULL DEFAULT 'unknown',
    operator_consultation text NOT NULL DEFAULT 'unknown',
    notes text NOT NULL DEFAULT '',
    checked_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scenario_run_id, site_order),
    FOREIGN KEY (scenario_run_id, site_order)
        REFERENCES scenario_sites(scenario_run_id, site_order) ON DELETE CASCADE,
    CHECK (site_access IN ('unknown', 'confirmed', 'attention', 'not_applicable')),
    CHECK (road_safety IN ('unknown', 'confirmed', 'attention', 'not_applicable')),
    CHECK (land_ownership_unknown IN ('unknown', 'confirmed', 'attention', 'not_applicable')),
    CHECK (existing_service IN ('unknown', 'confirmed', 'attention', 'not_applicable')),
    CHECK (facility_condition IN ('unknown', 'confirmed', 'attention', 'not_applicable')),
    CHECK (hazard_confirmation IN ('unknown', 'confirmed', 'attention', 'not_applicable')),
    CHECK (operator_consultation IN ('unknown', 'confirmed', 'attention', 'not_applicable'))
);

CREATE TABLE scenario_lifecycle_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id) ON DELETE CASCADE,
    from_status text,
    to_status text NOT NULL CHECK (
        to_status IN ('draft', 'under_review', 'field_check_required', 'reviewed', 'archived')
    ),
    note text NOT NULL DEFAULT '',
    changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX scenario_lifecycle_events_run_idx
    ON scenario_lifecycle_events (scenario_run_id, changed_at);

COMMENT ON TABLE scenario_field_checks IS
    'Human municipal review checklist. Values are observations, never optimizer decisions.';
COMMENT ON COLUMN scenario_context.review_status IS
    'Hazard overlap requires additional confirmation and never determines feasibility.';

COMMIT;
