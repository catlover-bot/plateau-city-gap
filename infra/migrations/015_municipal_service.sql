BEGIN;

-- ---------------------------------------------------------------------------
-- Organization and tenant boundary
-- ---------------------------------------------------------------------------

CREATE TABLE organizations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_key text NOT NULL UNIQUE CHECK (
        organization_key ~ '^[a-z0-9][a-z0-9-]{1,62}$'
    ),
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 300),
    organization_type text NOT NULL CHECK (
        organization_type IN ('municipality', 'prefecture', 'consultant', 'research')
    ),
    status text NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'suspended', 'archived')
    ),
    default_data_classification text NOT NULL DEFAULT 'internal' CHECK (
        default_data_classification IN ('public', 'internal', 'restricted')
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO organizations (
    id, organization_key, name, organization_type, default_data_classification
) VALUES (
    '00000000-0000-0000-0000-000000000001',
    'municipal-default',
    '既存自治体データ移行テナント',
    'municipality',
    'internal'
);

ALTER TABLE cities
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN service_status text NOT NULL DEFAULT 'active' CHECK (
        service_status IN ('onboarding', 'active', 'paused', 'archived')
    );
CREATE INDEX cities_organization_idx ON cities (organization_id, service_status, name);
ALTER TABLE cities ADD CONSTRAINT cities_organization_id_id_unique
    UNIQUE (organization_id, id);

CREATE TABLE organization_memberships (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (
        role IN (
            'viewer', 'analyst', 'planner', 'field_staff',
            'data_manager', 'administrator'
        )
    ),
    active boolean NOT NULL DEFAULT true,
    granted_by uuid REFERENCES platform_users(id),
    granted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, user_id, role)
);

ALTER TABLE platform_user_roles DROP CONSTRAINT platform_user_roles_role_check;
ALTER TABLE platform_user_roles
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD CONSTRAINT platform_user_roles_role_check CHECK (
        role IN (
            'viewer', 'analyst', 'planner', 'field_staff',
            'data_manager', 'administrator'
        )
    );
CREATE INDEX platform_user_roles_tenant_idx
    ON platform_user_roles (organization_id, user_id, role);

ALTER TABLE city_dataset_versions
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE datasets
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    ),
    ADD COLUMN dataset_category text NOT NULL DEFAULT 'municipal_custom' CHECK (
        dataset_category IN (
            'plateau', 'population', 'facilities', 'transport', 'hazard',
            'planning', 'municipal_custom'
        )
    );
UPDATE datasets SET dataset_category = CASE
    WHEN dataset_key ILIKE '%plateau%' THEN 'plateau'
    WHEN dataset_key ILIKE '%population%' OR dataset_key ILIKE '%census%' THEN 'population'
    WHEN dataset_key ILIKE '%facility%' THEN 'facilities'
    WHEN dataset_key ILIKE '%gtfs%' OR dataset_key ILIKE '%transport%' THEN 'transport'
    WHEN dataset_key ILIKE '%hazard%' OR dataset_key ILIKE '%flood%'
         OR dataset_key ILIKE '%tsunami%' THEN 'hazard'
    WHEN dataset_key ILIKE '%planning%' OR dataset_key ILIKE '%landuse%' THEN 'planning'
    ELSE dataset_category
END;
ALTER TABLE dataset_versions
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    ),
    ADD COLUMN service_status text NOT NULL DEFAULT 'registered' CHECK (
        service_status IN (
            'registered', 'validating', 'validated', 'accepted', 'ingesting',
            'analysis_ready', 'promoted', 'rejected', 'failed'
        )
    ),
    ADD COLUMN accepted_by text,
    ADD COLUMN accepted_at timestamptz,
    ADD COLUMN promoted_by text,
    ADD COLUMN promoted_at timestamptz;
UPDATE dataset_versions
SET service_status = CASE
    WHEN analysis_ready THEN 'promoted'
    WHEN lifecycle_status = 'available' AND quality_status = 'passed' THEN 'analysis_ready'
    WHEN lifecycle_status = 'validated' THEN 'validated'
    WHEN lifecycle_status = 'failed' THEN 'failed'
    ELSE 'registered'
END;
ALTER TABLE dataset_versions ADD CONSTRAINT dataset_versions_service_promotion_gate CHECK (
    service_status <> 'promoted' OR (
        analysis_ready AND quality_status = 'passed' AND lifecycle_status = 'available'
    )
);
CREATE INDEX dataset_versions_tenant_status_idx
    ON dataset_versions (organization_id, service_status, registered_at DESC);
ALTER TABLE datasets ADD CONSTRAINT datasets_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE dataset_versions ADD CONSTRAINT dataset_versions_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE datasets ADD CONSTRAINT datasets_organization_city_fk
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id);
ALTER TABLE dataset_versions ADD CONSTRAINT dataset_versions_organization_dataset_fk
    FOREIGN KEY (organization_id, dataset_id) REFERENCES datasets(organization_id, id);

ALTER TABLE urban_states
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN primary_dataset_version_id uuid REFERENCES dataset_versions(id);
UPDATE urban_states AS state
SET primary_dataset_version_id = version.registry_version_id
FROM city_dataset_versions AS version
WHERE version.id = state.primary_plateau_dataset_version_id
  AND version.registry_version_id IS NOT NULL;
ALTER TABLE urban_states ALTER COLUMN primary_plateau_dataset_version_id DROP NOT NULL;
ALTER TABLE urban_states ADD CONSTRAINT urban_states_primary_version_required CHECK (
    primary_dataset_version_id IS NOT NULL OR primary_plateau_dataset_version_id IS NOT NULL
);
ALTER TABLE urban_states ADD CONSTRAINT urban_states_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE urban_states ADD CONSTRAINT urban_states_organization_city_fk
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id);
ALTER TABLE urban_states ADD CONSTRAINT urban_states_organization_dataset_fk
    FOREIGN KEY (organization_id, primary_dataset_version_id)
        REFERENCES dataset_versions(organization_id, id);
CREATE INDEX urban_states_tenant_time_idx
    ON urban_states (organization_id, city_id, effective_date DESC, lifecycle_status);
ALTER TABLE urban_state_change_sets
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE recomputation_plans
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);

ALTER TABLE road_network_versions
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE road_network_versions ADD CONSTRAINT road_network_versions_org_id_unique
    UNIQUE (organization_id, id);

ALTER TABLE stress_test_runs
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
CREATE INDEX stress_test_runs_tenant_state_idx
    ON stress_test_runs (organization_id, city_id, base_urban_state_id, created_at DESC);

ALTER TABLE network_criticality_runs
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);

ALTER TABLE municipal_target_sets
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE policy_portfolios
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE outcome_evaluations
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);

ALTER TABLE analysis_runs
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN created_by text NOT NULL DEFAULT 'migration',
    ADD COLUMN algorithm_version text NOT NULL DEFAULT 'legacy-version-recorded-in-metadata',
    ADD COLUMN result_hash char(64),
    ADD COLUMN parameters jsonb NOT NULL DEFAULT '{}',
    ADD CONSTRAINT analysis_runs_result_hash_check CHECK (
        result_hash IS NULL OR result_hash ~ '^[0-9a-f]{64}$'
    );
ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_organization_city_fk
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id);
ALTER TABLE job_runs
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
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
        'validation_run', 'validation_reproduce', 'pilot_rehearsal',
        'analysis_run', 'report_generation'
    )
);
CREATE INDEX job_runs_tenant_state_idx
    ON job_runs (organization_id, state, queued_at, id);
ALTER TABLE job_runs ADD CONSTRAINT job_runs_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE job_runs ADD CONSTRAINT job_runs_organization_city_fk
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id);

CREATE TABLE job_cancellation_requests (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    job_run_id uuid NOT NULL,
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 4000),
    requested_by text NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, job_run_id),
    FOREIGN KEY (organization_id, job_run_id)
        REFERENCES job_runs(organization_id, id) ON DELETE CASCADE
);
COMMENT ON TABLE job_cancellation_requests IS
    'Durable cancellation for queued work. Running processes are never killed unsafely by the API.';
ALTER TABLE audit_log
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    );
CREATE INDEX audit_log_tenant_occurred_idx
    ON audit_log (organization_id, occurred_at DESC, id DESC);

ALTER TABLE upload_inspections
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN city_id uuid REFERENCES cities(id);
ALTER TABLE scenario_runs
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN title text,
    ADD COLUMN parent_scenario_run_id uuid REFERENCES scenario_runs(id),
    ADD COLUMN assumptions jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN review_status text NOT NULL DEFAULT 'not_requested' CHECK (
        review_status IN (
            'not_requested', 'requested', 'in_review', 'changes_requested', 'reviewed'
        )
    );
UPDATE scenario_runs SET title = scenario_key WHERE title IS NULL;
ALTER TABLE scenario_runs ALTER COLUMN title SET NOT NULL;
ALTER TABLE scenario_runs ADD CONSTRAINT scenario_runs_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE scenario_runs ADD CONSTRAINT scenario_runs_organization_base_state_fk
    FOREIGN KEY (organization_id, base_urban_state_id)
        REFERENCES urban_states(organization_id, id);
ALTER TABLE scenario_runs ADD CONSTRAINT scenario_runs_organization_parent_fk
    FOREIGN KEY (organization_id, parent_scenario_run_id)
        REFERENCES scenario_runs(organization_id, id);

ALTER TABLE field_offline_packages
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE field_offline_packages ADD CONSTRAINT field_offline_packages_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE field_offline_packages ADD CONSTRAINT field_offline_packages_organization_city_fk
    FOREIGN KEY (organization_id, city_id) REFERENCES cities(organization_id, id);
ALTER TABLE field_offline_packages ADD CONSTRAINT field_offline_packages_organization_state_fk
    FOREIGN KEY (organization_id, urban_state_id)
        REFERENCES urban_states(organization_id, id);
ALTER TABLE field_offline_packages ADD CONSTRAINT field_offline_packages_organization_scenario_fk
    FOREIGN KEY (organization_id, scenario_run_id)
        REFERENCES scenario_runs(organization_id, id);
ALTER TABLE field_sync_operations
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE field_sync_operations ADD CONSTRAINT field_sync_operations_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE field_sync_operations ADD CONSTRAINT field_sync_operations_organization_package_fk
    FOREIGN KEY (organization_id, offline_package_id)
        REFERENCES field_offline_packages(organization_id, id);
ALTER TABLE field_sync_operations ADD CONSTRAINT field_sync_operations_organization_scenario_fk
    FOREIGN KEY (organization_id, scenario_run_id)
        REFERENCES scenario_runs(organization_id, id);
ALTER TABLE field_sync_conflicts
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE field_sync_conflicts ADD CONSTRAINT field_sync_conflicts_organization_id_id_unique
    UNIQUE (organization_id, id);
ALTER TABLE field_sync_conflicts ADD CONSTRAINT field_sync_conflicts_organization_operation_fk
    FOREIGN KEY (organization_id, field_sync_operation_id)
        REFERENCES field_sync_operations(organization_id, id);
ALTER TABLE validation_runs
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id);
ALTER TABLE validation_evidence
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    );
ALTER TABLE temporal_evidence_packages
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    );
ALTER TABLE municipal_annual_reports
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    );
ALTER TABLE evidence_exports
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN export_scope text NOT NULL DEFAULT 'internal' CHECK (
        export_scope IN ('public', 'internal')
    ),
    ADD COLUMN data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    ),
    ADD CONSTRAINT evidence_exports_public_boundary CHECK (
        export_scope <> 'public' OR data_classification = 'public'
    );

-- ---------------------------------------------------------------------------
-- Municipal work loop: Finding -> Investigation -> Review -> Field -> Decision
-- ---------------------------------------------------------------------------

CREATE TABLE workspaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    workspace_key text NOT NULL,
    title text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, city_id, workspace_key),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id)
);

CREATE TABLE findings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    urban_state_id uuid REFERENCES urban_states(id),
    finding_type text NOT NULL CHECK (
        finding_type IN (
            'accessibility_gap', 'network_criticality', 'planning_context',
            'temporal_change', 'resilience_impact', 'data_quality_issue'
        )
    ),
    title text NOT NULL,
    summary text NOT NULL,
    geometry geometry(Geometry, 4326),
    status text NOT NULL DEFAULT 'new' CHECK (
        status IN (
            'new', 'triaged', 'investigating', 'review_required',
            'resolved', 'dismissed', 'archived'
        )
    ),
    source_analysis_run_id uuid REFERENCES analysis_runs(id),
    validation_status text NOT NULL DEFAULT 'unvalidated',
    assigned_to uuid REFERENCES platform_users(id),
    dismissal_reason text,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'dismissed' AND length(dismissal_reason) > 0) OR status <> 'dismissed'),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, urban_state_id)
        REFERENCES urban_states(organization_id, id),
    FOREIGN KEY (organization_id, source_analysis_run_id)
        REFERENCES analysis_runs(organization_id, id)
);
ALTER TABLE findings ADD CONSTRAINT findings_organization_id_id_unique
    UNIQUE (organization_id, id);
CREATE INDEX findings_tenant_queue_idx
    ON findings (organization_id, city_id, status, created_at DESC);
CREATE INDEX findings_geometry_idx ON findings USING gist (geometry);

CREATE FUNCTION citygap_enforce_finding_transition() RETURNS trigger AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    IF (OLD.status = 'new' AND NEW.status IN ('triaged', 'dismissed', 'archived')) OR
       (OLD.status = 'triaged' AND NEW.status IN ('investigating', 'dismissed', 'archived')) OR
       (OLD.status = 'investigating' AND NEW.status IN (
            'review_required', 'resolved', 'dismissed', 'archived'
       )) OR
       (OLD.status = 'review_required' AND NEW.status IN (
            'investigating', 'resolved', 'dismissed', 'archived'
       )) OR
       (OLD.status IN ('resolved', 'dismissed') AND NEW.status IN (
            'investigating', 'archived'
       )) THEN
        NEW.updated_at = now();
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid finding transition: % -> %', OLD.status, NEW.status;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER findings_lifecycle_transition
    BEFORE UPDATE OF status ON findings
    FOR EACH ROW EXECUTE FUNCTION citygap_enforce_finding_transition();

CREATE TABLE investigations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    workspace_id uuid REFERENCES workspaces(id),
    urban_state_id uuid NOT NULL REFERENCES urban_states(id),
    title text NOT NULL,
    objective text NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (
        status IN ('open', 'in_review', 'field_check', 'decision_pending', 'closed', 'archived')
    ),
    assigned_to uuid REFERENCES platform_users(id),
    due_date date,
    spatial_state jsonb NOT NULL DEFAULT '{}',
    active_analysis_run_id uuid REFERENCES analysis_runs(id),
    notes text NOT NULL DEFAULT '',
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, urban_state_id)
        REFERENCES urban_states(organization_id, id),
    FOREIGN KEY (organization_id, workspace_id)
        REFERENCES workspaces(organization_id, id),
    FOREIGN KEY (organization_id, active_analysis_run_id)
        REFERENCES analysis_runs(organization_id, id)
);
ALTER TABLE investigations ADD CONSTRAINT investigations_organization_id_id_unique
    UNIQUE (organization_id, id);
CREATE INDEX investigations_tenant_status_idx
    ON investigations (organization_id, city_id, status, updated_at DESC);

CREATE FUNCTION citygap_enforce_investigation_transition() RETURNS trigger AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    IF (OLD.status = 'open' AND NEW.status IN ('in_review', 'field_check', 'archived')) OR
       (OLD.status = 'in_review' AND NEW.status IN (
            'open', 'field_check', 'decision_pending'
       )) OR
       (OLD.status = 'field_check' AND NEW.status IN (
            'open', 'in_review', 'decision_pending'
       )) OR
       (OLD.status = 'decision_pending' AND NEW.status IN (
            'in_review', 'field_check', 'closed'
       )) OR
       (OLD.status = 'closed' AND NEW.status IN ('open', 'archived')) THEN
        NEW.updated_at = now();
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid investigation transition: % -> %', OLD.status, NEW.status;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER investigations_lifecycle_transition
    BEFORE UPDATE OF status ON investigations
    FOR EACH ROW EXECUTE FUNCTION citygap_enforce_investigation_transition();

CREATE TABLE investigation_findings (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    finding_id uuid NOT NULL REFERENCES findings(id) ON DELETE RESTRICT,
    added_by text NOT NULL,
    added_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, investigation_id, finding_id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, finding_id)
        REFERENCES findings(organization_id, id) ON DELETE RESTRICT
);

CREATE TABLE investigation_entities (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    entity_type text NOT NULL CHECK (
        entity_type IN ('mesh', 'building', 'road', 'facility', 'hazard', 'scenario_site')
    ),
    entity_id text NOT NULL,
    label text,
    geometry geometry(Geometry, 4326),
    source text NOT NULL,
    source_year integer,
    attributes jsonb NOT NULL DEFAULT '{}',
    evidence jsonb NOT NULL DEFAULT '[]',
    added_by text NOT NULL,
    added_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, investigation_id, entity_type, entity_id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE
);
CREATE INDEX investigation_entities_geometry_idx
    ON investigation_entities USING gist (geometry);

CREATE TABLE saved_views (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    investigation_id uuid REFERENCES investigations(id) ON DELETE CASCADE,
    title text NOT NULL,
    spatial_state jsonb NOT NULL,
    share_token text NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(24), 'hex'),
    data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    ),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE
);
CREATE INDEX saved_views_tenant_idx
    ON saved_views (organization_id, city_id, updated_at DESC);

CREATE TABLE review_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_type text NOT NULL CHECK (
        resource_type IN ('finding', 'investigation', 'scenario', 'review', 'field_observation')
    ),
    resource_id uuid NOT NULL,
    parent_note_id uuid REFERENCES review_notes(id),
    body text NOT NULL CHECK (length(body) BETWEEN 1 AND 10000),
    author_id uuid REFERENCES platform_users(id),
    author_label text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    edited_at timestamptz
);
CREATE INDEX review_notes_resource_idx
    ON review_notes (organization_id, resource_type, resource_id, created_at);

CREATE TABLE review_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    investigation_id uuid REFERENCES investigations(id) ON DELETE CASCADE,
    scenario_run_id uuid REFERENCES scenario_runs(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'requested' CHECK (
        status IN ('requested', 'in_review', 'changes_requested', 'reviewed')
    ),
    requested_by uuid REFERENCES platform_users(id),
    reviewer_id uuid REFERENCES platform_users(id),
    request_note text NOT NULL DEFAULT '',
    review_note text NOT NULL DEFAULT '',
    external_approval_reference text,
    requested_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    CHECK ((investigation_id IS NOT NULL)::integer + (scenario_run_id IS NOT NULL)::integer = 1),
    CHECK ((status = 'reviewed' AND reviewed_at IS NOT NULL) OR status <> 'reviewed'),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, scenario_run_id)
        REFERENCES scenario_runs(organization_id, id) ON DELETE CASCADE
);
ALTER TABLE review_requests ADD CONSTRAINT review_requests_organization_id_id_unique
    UNIQUE (organization_id, id);
CREATE INDEX review_requests_tenant_status_idx
    ON review_requests (organization_id, status, requested_at DESC);

CREATE TABLE assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    assignment_type text NOT NULL CHECK (
        assignment_type IN ('investigation', 'review', 'field_check')
    ),
    resource_id uuid NOT NULL,
    assigned_to uuid NOT NULL REFERENCES platform_users(id),
    assigned_by uuid REFERENCES platform_users(id),
    status text NOT NULL DEFAULT 'assigned' CHECK (
        status IN ('assigned', 'in_progress', 'completed', 'cancelled')
    ),
    due_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE INDEX assignments_assignee_idx
    ON assignments (organization_id, assigned_to, status, due_date);

CREATE TABLE decision_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE RESTRICT,
    review_request_id uuid NOT NULL REFERENCES review_requests(id) ON DELETE RESTRICT,
    decision text NOT NULL CHECK (
        decision IN ('adopted', 'on_hold', 'rejected', 'additional_investigation')
    ),
    reason text NOT NULL CHECK (length(reason) > 0),
    actor_id uuid REFERENCES platform_users(id),
    actor_label text NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT now(),
    related_scenario_run_id uuid REFERENCES scenario_runs(id),
    related_evidence_ids uuid[] NOT NULL CHECK (cardinality(related_evidence_ids) > 0),
    review_status text NOT NULL CHECK (review_status = 'reviewed'),
    source text NOT NULL DEFAULT 'human_entry' CHECK (source = 'human_entry'),
    optimizer_generated boolean NOT NULL DEFAULT false CHECK (NOT optimizer_generated),
    official_approval_reference text,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id),
    FOREIGN KEY (organization_id, review_request_id)
        REFERENCES review_requests(organization_id, id),
    FOREIGN KEY (organization_id, related_scenario_run_id)
        REFERENCES scenario_runs(organization_id, id)
);
CREATE INDEX decision_records_city_idx
    ON decision_records (organization_id, city_id, decided_at DESC);

ALTER TABLE implementation_records
    ADD COLUMN organization_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'
        REFERENCES organizations(id),
    ADD COLUMN decision_record_id uuid REFERENCES decision_records(id);

CREATE TABLE field_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    related_finding_id uuid REFERENCES findings(id),
    related_scenario_run_id uuid REFERENCES scenario_runs(id),
    observation_type text NOT NULL,
    status text NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'submitted', 'reviewed', 'rejected')
    ),
    notes text NOT NULL DEFAULT '',
    gps geometry(Point, 4326),
    observed_at timestamptz NOT NULL,
    actor_id uuid REFERENCES platform_users(id),
    actor_label text NOT NULL,
    attachment_ids uuid[] NOT NULL DEFAULT '{}',
    synced_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, related_finding_id)
        REFERENCES findings(organization_id, id),
    FOREIGN KEY (organization_id, related_scenario_run_id)
        REFERENCES scenario_runs(organization_id, id)
);
CREATE INDEX field_observations_tenant_status_idx
    ON field_observations (organization_id, city_id, status, observed_at DESC);
CREATE INDEX field_observations_gps_idx ON field_observations USING gist (gps);

-- ---------------------------------------------------------------------------
-- Collaboration, human-readable activity and notifications
-- ---------------------------------------------------------------------------

CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    notification_type text NOT NULL CHECK (
        notification_type IN (
            'review_requested', 'field_check_assigned', 'dataset_failed',
            'dataset_updated', 'analysis_finished', 'conflict_found',
            'assignment_assigned'
        )
    ),
    title text NOT NULL,
    body text NOT NULL,
    resource_type text,
    resource_id text,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX notifications_inbox_idx
    ON notifications (organization_id, user_id, read_at, created_at DESC);

CREATE TABLE activity_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid REFERENCES cities(id) ON DELETE CASCADE,
    investigation_id uuid REFERENCES investigations(id) ON DELETE CASCADE,
    event_type text NOT NULL CHECK (
        event_type IN (
            'dataset_updated', 'finding_created', 'investigation_started',
            'scenario_compared', 'review_submitted', 'field_check_added',
            'decision_recorded', 'urban_state_promoted',
            'finding_status_changed', 'review_status_changed',
            'investigation_status_changed', 'analysis_started'
        )
    ),
    title text NOT NULL,
    description text NOT NULL,
    actor_label text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id)
);
CREATE INDEX activity_events_city_idx
    ON activity_events (organization_id, city_id, occurred_at DESC, id DESC);
CREATE INDEX activity_events_investigation_idx
    ON activity_events (organization_id, investigation_id, occurred_at DESC, id DESC);

CREATE FUNCTION citygap_audit_log_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is immutable';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION citygap_audit_log_immutable();

-- ---------------------------------------------------------------------------
-- Data Hub, onboarding, capability and PLATEAU Model
-- ---------------------------------------------------------------------------

CREATE TABLE dataset_onboarding_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    from_status text,
    to_status text NOT NULL CHECK (
        to_status IN (
            'registered', 'validating', 'validated', 'accepted', 'ingesting',
            'analysis_ready', 'promoted', 'rejected', 'failed'
        )
    ),
    note text NOT NULL DEFAULT '',
    actor text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, dataset_version_id)
        REFERENCES dataset_versions(organization_id, id) ON DELETE CASCADE
);
CREATE INDEX dataset_onboarding_events_version_idx
    ON dataset_onboarding_events (organization_id, dataset_version_id, occurred_at);

CREATE TABLE dataset_quality_checks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    check_key text NOT NULL CHECK (
        check_key IN (
            'geometry_valid', 'crs_resolved', 'attribute_coverage', 'feature_count',
            'missing_values', 'code_list', 'temporal_consistency', 'privacy_constraints'
        )
    ),
    status text NOT NULL CHECK (status IN ('passed', 'warning', 'failed', 'not_applicable')),
    observed_value jsonb NOT NULL DEFAULT '{}',
    explanation text NOT NULL,
    checked_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_version_id, check_key, checked_at),
    FOREIGN KEY (organization_id, dataset_version_id)
        REFERENCES dataset_versions(organization_id, id) ON DELETE CASCADE
);
CREATE INDEX dataset_quality_checks_version_idx
    ON dataset_quality_checks (organization_id, dataset_version_id, status);

CREATE TABLE city_capability_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    capability text NOT NULL,
    from_status text,
    to_status text NOT NULL CHECK (to_status IN ('available', 'partial', 'unavailable')),
    reason text NOT NULL,
    changed_by text NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE VIEW plateau_model_inventory AS
SELECT
    version.organization_id,
    city.id AS city_id,
    city.city_code,
    city.city_key,
    city.name AS city_name,
    version.id AS plateau_dataset_version_id,
    version.dataset_year,
    version.product_specification_version,
    version.ade_schema_version,
    version.archive_sha256 AS source_hash,
    object.theme,
    count(*) AS feature_count,
    ARRAY(
        SELECT DISTINCT lod
        FROM plateau_city_objects AS lod_object
        CROSS JOIN LATERAL unnest(lod_object.lods) AS lod
        WHERE lod_object.dataset_version_id = version.id
          AND lod_object.theme IS NOT DISTINCT FROM object.theme
        ORDER BY lod
    ) AS available_lods,
    count(*) FILTER (WHERE object.geometry_envelope IS NOT NULL) AS geometry_count,
    count(*) FILTER (WHERE object.attributes <> '{}') AS attribute_record_count
FROM city_dataset_versions AS version
JOIN cities AS city ON city.city_code = version.city_id
LEFT JOIN plateau_city_objects AS object ON object.dataset_version_id = version.id
WHERE version.is_current
GROUP BY
    version.organization_id, city.id, city.city_code, city.city_key, city.name,
    version.id, version.dataset_year, version.product_specification_version,
    version.ade_schema_version, version.archive_sha256, object.theme;

-- ---------------------------------------------------------------------------
-- Analysis catalog, scenarios, Evidence Center and deterministic reports
-- ---------------------------------------------------------------------------

CREATE TABLE analysis_definitions (
    id text NOT NULL,
    version text NOT NULL,
    name text NOT NULL,
    purpose text NOT NULL,
    required_capabilities text[] NOT NULL,
    input_contract jsonb NOT NULL,
    output_contract jsonb NOT NULL,
    algorithm_description text NOT NULL,
    claim_boundary text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, version)
);

CREATE TABLE analysis_parameter_definitions (
    analysis_id text NOT NULL,
    analysis_version text NOT NULL,
    parameter_key text NOT NULL,
    value_type text NOT NULL CHECK (
        value_type IN ('integer', 'number', 'string', 'boolean', 'enum')
    ),
    description text NOT NULL,
    default_value jsonb NOT NULL,
    minimum numeric,
    maximum numeric,
    allowed_values jsonb,
    PRIMARY KEY (analysis_id, analysis_version, parameter_key),
    FOREIGN KEY (analysis_id, analysis_version)
        REFERENCES analysis_definitions(id, version) ON DELETE CASCADE,
    CHECK (minimum IS NULL OR maximum IS NULL OR minimum <= maximum)
);

INSERT INTO analysis_definitions (
    id, version, name, purpose, required_capabilities,
    input_contract, output_contract, algorithm_description, claim_boundary
) VALUES
('accessibility-gap', '1.0.0', '生活サービスへのアクセス候補抽出',
 '500mメッシュ単位で追加調査候補を抽出する', ARRAY['screening','building_detail'],
 '{"required":["urban_state","population","facilities","plateau_buildings"],"context_roles":["urban_state"],"dataset_roles":["population","facilities","plateau_buildings"]}',
 '{"produces":["finding","mesh_metrics"]}', 'CITY GAP screening',
 '候補は政策上の問題認定、危険度、優先順位ではない。'),
('building-accessibility', '2.0.0', '建物アクセシビリティ',
 'PLATEAU建物を起点に施設へのモデル距離を確認する', ARRAY['building_detail'],
 '{"required":["plateau_buildings","facilities"],"context_roles":[],"dataset_roles":["plateau_buildings","facilities"]}',
 '{"produces":["building_accessibility_metrics"]}', 'Versioned deterministic distance model',
 '建物別推計人口は観測値ではなく、公開出力へ含めない。'),
('network-criticality', '1.0.0', '道路ネットワーク確認候補',
 '道路graph上で接続性の確認候補を抽出する', ARRAY['road_network'],
 '{"required":["network_version","building_snap"],"context_roles":[],"dataset_roles":["network_version","building_snap"]}',
 '{"produces":["criticality_finding"]}', 'Bounded graph candidate analysis',
 '道路の危険性、行政上の重要度、実際の通行可否を断定しない。'),
('stress-test', '1.0.0', '仮定条件によるStress Test',
 '明示した利用不可仮定でサービス継続性を比較する', ARRAY['road_network','hazard'],
 '{"required":["network_version","closure_assumptions"],"context_roles":["closure_assumptions"],"dataset_roles":["network_version"]}',
 '{"produces":["stress_test_result"]}', 'Counterfactual graph comparison',
 '災害予測や実際の通行止めではない。'),
('future-accessibility', '1.0.0', '将来人口シナリオ比較',
 '公式人口シナリオを固定サービス仮定で比較する', ARRAY['future_population','scenario'],
 '{"required":["future_urban_state","fixed_service_assumption","population_scenario"],"context_roles":["future_urban_state","fixed_service_assumption"],"dataset_roles":["population_scenario"]}',
 '{"produces":["future_accessibility_metrics"]}', 'Fixed-service comparison',
 '建物別人口予測や最良シナリオの選定ではない。'),
('temporal-diff', '1.0.0', '年度差分',
 'version間の追加・削除・形状・属性差分を分類する', ARRAY['temporal_diff'],
 '{"required":["from_dataset_version","to_dataset_version"],"context_roles":[],"dataset_roles":["from_dataset_version","to_dataset_version"]}',
 '{"produces":["change_set","impacted_analyses"]}', 'Hash-based deterministic diff',
 'source仕様変更が都市変化として現れる可能性をEvidenceへ残す。');

INSERT INTO analysis_parameter_definitions (
    analysis_id, analysis_version, parameter_key, value_type,
    description, default_value, minimum, maximum
) VALUES (
    'accessibility-gap', '1.0.0', 'candidate_limit', 'integer',
    '表示する追加調査候補数', '10', 1, 100
);

CREATE TABLE scenario_comparisons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    investigation_id uuid REFERENCES investigations(id) ON DELETE CASCADE,
    title text NOT NULL,
    scenario_run_ids uuid[] NOT NULL CHECK (
        cardinality(scenario_run_ids) BETWEEN 2 AND 3
    ),
    comparison_dimensions jsonb NOT NULL CHECK (
        jsonb_typeof(comparison_dimensions) = 'array'
    ),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id)
);

CREATE TABLE evidence_centers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    investigation_id uuid REFERENCES investigations(id) ON DELETE CASCADE,
    scenario_run_id uuid REFERENCES scenario_runs(id) ON DELETE CASCADE,
    source_manifest jsonb NOT NULL,
    algorithm_manifest jsonb NOT NULL,
    validation_manifest jsonb NOT NULL,
    field_evidence_manifest jsonb NOT NULL DEFAULT '[]',
    decision_manifest jsonb NOT NULL DEFAULT '[]',
    manifest_sha256 char(64) NOT NULL,
    data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    ),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((investigation_id IS NOT NULL)::integer + (scenario_run_id IS NOT NULL)::integer <= 1),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id),
    FOREIGN KEY (organization_id, scenario_run_id)
        REFERENCES scenario_runs(organization_id, id)
);

CREATE TABLE report_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    investigation_id uuid REFERENCES investigations(id),
    scenario_comparison_id uuid REFERENCES scenario_comparisons(id),
    report_type text NOT NULL CHECK (
        report_type IN (
            'investigation', 'scenario_comparison', 'annual_change',
            'resilience_review', 'data_quality'
        )
    ),
    title text NOT NULL,
    structured_content jsonb NOT NULL,
    generator_version text NOT NULL,
    artifact_uri text NOT NULL,
    artifact_sha256 char(64) NOT NULL,
    data_classification text NOT NULL DEFAULT 'internal' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    ),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id),
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id),
    FOREIGN KEY (organization_id, scenario_comparison_id)
        REFERENCES scenario_comparisons(organization_id, id)
);

CREATE TABLE report_exports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    report_id uuid NOT NULL REFERENCES report_records(id) ON DELETE CASCADE,
    export_scope text NOT NULL CHECK (export_scope IN ('public', 'internal')),
    data_classification text NOT NULL CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    ),
    artifact_uri text NOT NULL,
    artifact_sha256 char(64) NOT NULL,
    exported_by text NOT NULL,
    exported_at timestamptz NOT NULL DEFAULT now(),
    CHECK (export_scope <> 'public' OR data_classification = 'public'),
    FOREIGN KEY (organization_id, report_id)
        REFERENCES report_records(organization_id, id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Object storage, configuration, operations, retention and releases
-- ---------------------------------------------------------------------------

CREATE TABLE attachment_objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid REFERENCES cities(id) ON DELETE CASCADE,
    storage_provider text NOT NULL CHECK (storage_provider IN ('local', 's3_compatible')),
    object_key text NOT NULL,
    original_file_name text NOT NULL,
    content_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes BETWEEN 1 AND 104857600),
    sha256 char(64) NOT NULL,
    data_classification text NOT NULL DEFAULT 'restricted' CHECK (
        data_classification IN ('public', 'internal', 'restricted')
    ),
    retention_class text NOT NULL DEFAULT 'municipal_record',
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, storage_provider, object_key),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id)
);

CREATE TABLE organization_configuration (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    config_key text NOT NULL,
    config_value jsonb NOT NULL,
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, config_key),
    CHECK (config_key !~* '(secret|password|token|credential|private_key)')
);

CREATE TABLE notification_provider_boundaries (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider_type text NOT NULL CHECK (provider_type IN ('in_app', 'email', 'webhook')),
    enabled boolean NOT NULL DEFAULT false,
    non_secret_configuration jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (organization_id, provider_type)
);

CREATE TABLE retention_policies (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_type text NOT NULL CHECK (
        resource_type IN ('audit', 'field_observation', 'attachment', 'job')
    ),
    retention_days integer CHECK (retention_days IS NULL OR retention_days > 0),
    legal_hold_supported boolean NOT NULL DEFAULT false,
    configured_by text NOT NULL,
    configured_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, resource_type)
);

CREATE TABLE service_metric_samples (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
    metric_name text NOT NULL CHECK (
        metric_name IN (
            'api_request_duration_ms', 'api_error', 'job_runtime_seconds',
            'db_pool_in_use', 'tile_latency_ms', 'interactive_map_load_ms'
        )
    ),
    metric_value double precision NOT NULL,
    labels jsonb NOT NULL DEFAULT '{}',
    observed_at timestamptz NOT NULL DEFAULT now(),
    CHECK (octet_length(labels::text) <= 4096)
);
CREATE INDEX service_metric_samples_time_idx
    ON service_metric_samples (metric_name, observed_at DESC);

CREATE TABLE service_worker_heartbeats (
    worker_id text PRIMARY KEY,
    application_version text NOT NULL,
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE backup_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
    backup_type text NOT NULL CHECK (
        backup_type IN ('database', 'evidence', 'attachments', 'configuration', 'full')
    ),
    status text NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    artifact_uri text,
    artifact_sha256 char(64),
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    initiated_by text NOT NULL,
    error_message text,
    CHECK ((status IN ('succeeded', 'failed') AND completed_at IS NOT NULL) OR
           (status IN ('queued', 'running') AND completed_at IS NULL))
);

CREATE TABLE restore_validations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    backup_run_id uuid NOT NULL REFERENCES backup_runs(id),
    status text NOT NULL CHECK (status IN ('running', 'passed', 'failed')),
    integrity_report jsonb NOT NULL DEFAULT '{}',
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    validated_by text NOT NULL,
    CHECK ((status IN ('passed', 'failed') AND completed_at IS NOT NULL) OR status = 'running')
);

CREATE TABLE service_releases (
    version text PRIMARY KEY,
    application_commit char(40) NOT NULL,
    migration_version text NOT NULL,
    frontend_asset_version text NOT NULL,
    analysis_versions jsonb NOT NULL,
    release_status text NOT NULL CHECK (
        release_status IN ('candidate', 'current', 'superseded', 'rolled_back')
    ),
    migration_plan_uri text NOT NULL,
    rollback_plan_uri text NOT NULL,
    released_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO service_releases (
    version, application_commit, migration_version, frontend_asset_version,
    analysis_versions, release_status, migration_plan_uri, rollback_plan_uri
) VALUES (
    '0.2.0-municipal-service', repeat('0', 40), '015_municipal_service.sql',
    'municipal-service-v1',
    '{"catalog":"analysis_definitions"}', 'candidate',
    'docs/release-management.md#migration', 'docs/release-management.md#rollback'
);

CREATE TABLE product_usage_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid REFERENCES cities(id) ON DELETE CASCADE,
    event_name text NOT NULL CHECK (
        event_name IN ('feature_used', 'workflow_completed', 'workflow_error')
    ),
    feature_key text NOT NULL,
    aggregate_count integer NOT NULL DEFAULT 1 CHECK (aggregate_count > 0),
    occurred_on date NOT NULL DEFAULT CURRENT_DATE,
    metadata jsonb NOT NULL DEFAULT '{}',
    CHECK (NOT (metadata ?| ARRAY['email', 'name', 'subject', 'user_id', 'ip_address']))
);

CREATE TABLE support_bundles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    request_id text,
    job_id uuid REFERENCES job_runs(id),
    dataset_version_id uuid REFERENCES dataset_versions(id),
    analysis_run_id uuid REFERENCES analysis_runs(id),
    scenario_run_id uuid REFERENCES scenario_runs(id),
    manifest jsonb NOT NULL,
    generated_by text NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (octet_length(manifest::text) <= 1048576)
);

CREATE VIEW service_search_documents AS
SELECT organization_id, id AS city_id, 'city'::text AS entity_type,
       id::text AS entity_id, name AS title, city_key AS subtitle, updated_at
FROM cities
UNION ALL
SELECT organization_id, city_id, 'finding', id::text, title, summary, updated_at
FROM findings
UNION ALL
SELECT organization_id, city_id, 'investigation', id::text, title, objective, updated_at
FROM investigations
UNION ALL
SELECT scenario.organization_id, city.id, 'scenario', scenario.id::text,
       scenario.title, scenario.objective_definition, scenario.updated_at
FROM scenario_runs AS scenario
JOIN city_dataset_versions AS version ON version.id = scenario.dataset_version_id
JOIN cities AS city
  ON city.city_code = version.city_id AND city.organization_id = scenario.organization_id
UNION ALL
SELECT city.organization_id, city.id, 'facility', facility.id::text,
       facility.name, facility.facility_type || ' · ' || facility.facility_key,
       version.created_at
FROM facility_registry AS facility
JOIN city_dataset_versions AS version ON version.id = facility.dataset_version_id
JOIN cities AS city ON city.city_code = version.city_id
UNION ALL
SELECT city.organization_id, city.id, 'building', object.id::text,
       object.gml_id, object.theme || ' · ' || object.feature_type, object.ingested_at
FROM plateau_city_objects AS object
JOIN city_dataset_versions AS version ON version.id = object.dataset_version_id
JOIN cities AS city ON city.city_code = version.city_id
UNION ALL
SELECT city.organization_id, city.id, 'mesh',
       version.id::text || ':' || demographic.mesh_code,
       demographic.mesh_code, '500m mesh · ' || version.dataset_year::text,
       max(demographic.created_at)
FROM building_demographics AS demographic
JOIN city_dataset_versions AS version ON version.id = demographic.dataset_version_id
JOIN cities AS city ON city.city_code = version.city_id
GROUP BY city.organization_id, city.id, version.id,
         demographic.mesh_code, version.dataset_year;

CREATE VIEW city_service_home AS
SELECT
    city.organization_id,
    city.id AS city_id,
    city.city_code,
    city.city_key,
    city.name,
    city.service_status,
    (SELECT count(*) FROM findings AS finding
     WHERE finding.city_id = city.id AND finding.status IN ('new', 'triaged')) AS open_findings,
    (SELECT count(*) FROM investigations AS investigation
     WHERE investigation.city_id = city.id AND investigation.status NOT IN ('closed', 'archived'))
        AS active_investigations,
    (SELECT count(*) FROM review_requests AS review
     JOIN investigations AS investigation ON investigation.id = review.investigation_id
     WHERE investigation.city_id = city.id AND review.status IN ('requested', 'in_review'))
        AS pending_reviews,
    (SELECT count(*) FROM assignments AS assignment
     WHERE assignment.organization_id = city.organization_id
       AND assignment.assignment_type = 'field_check'
       AND assignment.status IN ('assigned', 'in_progress')) AS pending_field_checks,
    (SELECT max(event.occurred_at) FROM activity_events AS event
     WHERE event.city_id = city.id) AS latest_activity_at
FROM cities AS city;

COMMENT ON TABLE organizations IS
    'Primary tenant boundary. Every municipal service query is scoped by organization_id.';
COMMENT ON TABLE findings IS
    'Investigation candidates only. Severity and automated policy priority are intentionally absent.';
COMMENT ON TABLE decision_records IS
    'Human-authored record after review. Optimizer output cannot create a decision.';
COMMENT ON TABLE activity_events IS
    'Human-readable service history; immutable audit_log remains a separate security record.';
COMMENT ON TABLE dataset_onboarding_events IS
    'validate, accept and promote are explicit lifecycle actions; upload alone never becomes current.';
COMMENT ON TABLE attachment_objects IS
    'Object-storage metadata boundary. File bytes live in local or S3-compatible storage.';
COMMENT ON VIEW service_search_documents IS
    'Tenant filter is mandatory in application queries; technical identifiers remain searchable.';

COMMIT;
