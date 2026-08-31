-- M2 core: uncertainty-derived tasks and versioned PLATEAU/mesh targets.
-- PROVISIONAL_AFTER_M3: observation, review, offline, sync, conflict, activity,
-- and Finding projection structures below are retained but not value-validated.

BEGIN;

ALTER TABLE findings
    ADD COLUMN field_validation_status text NOT NULL DEFAULT 'not_reviewed' CHECK (
        field_validation_status IN (
            'not_reviewed','supported_by_field','contradicted_by_field',
            'partially_supported','needs_more_data'
        )
    );

ALTER TABLE spatial_pack_objects
    ADD CONSTRAINT spatial_pack_objects_organization_id_id_unique
    UNIQUE (organization_id, id);

CREATE TABLE field_verification_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    investigation_id uuid NOT NULL,
    related_finding_id uuid NOT NULL,
    verification_kind text NOT NULL CHECK (
        verification_kind IN (
            'gtfs_service','walking_connectivity','facility_availability',
            'plateau_coverage','local_service_context',
            'network_model_disagreement','terrain_access'
        )
    ),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 4000),
    known_summary text NOT NULL CHECK (length(known_summary) BETWEEN 1 AND 4000),
    unknown_summary text NOT NULL CHECK (length(unknown_summary) BETWEEN 1 AND 4000),
    source_boundary text NOT NULL CHECK (length(source_boundary) BETWEEN 1 AND 4000),
    source_references text[] NOT NULL DEFAULT '{}',
    template_version text NOT NULL,
    evidence_requirements jsonb NOT NULL CHECK (
        jsonb_typeof(evidence_requirements) = 'array'
        AND jsonb_array_length(evidence_requirements) BETWEEN 3 AND 5
    ),
    priority text NOT NULL CHECK (priority IN ('high','medium','low')),
    status text NOT NULL DEFAULT 'unverified' CHECK (
        status IN (
            'unverified','assigned','in_field','submitted',
            'under_review','needs_more_data','closed','cancelled'
        )
    ),
    assigned_to uuid REFERENCES platform_users(id),
    due_date date,
    record_version bigint NOT NULL DEFAULT 1 CHECK (record_version > 0),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    closed_at timestamptz,
    cancellation_reason text,
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, investigation_id)
        REFERENCES investigations(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, related_finding_id)
        REFERENCES findings(organization_id, id) ON DELETE RESTRICT,
    CHECK (
        (status = 'cancelled' AND length(cancellation_reason) > 0)
        OR status <> 'cancelled'
    ),
    CHECK (
        (status = 'closed' AND closed_at IS NOT NULL)
        OR status <> 'closed'
    )
);
CREATE INDEX field_verification_tasks_queue_idx
    ON field_verification_tasks (
        organization_id, city_id, assigned_to, status, due_date, created_at DESC
    );

CREATE FUNCTION citygap_enforce_verification_task_transition() RETURNS trigger AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    IF (OLD.status = 'unverified' AND NEW.status IN ('assigned','cancelled')) OR
       (OLD.status = 'assigned' AND NEW.status IN ('in_field','cancelled')) OR
       (OLD.status = 'in_field' AND NEW.status IN ('submitted','cancelled')) OR
       (OLD.status = 'submitted' AND NEW.status = 'under_review') OR
       (OLD.status = 'under_review' AND NEW.status IN ('closed','needs_more_data')) OR
       (OLD.status = 'needs_more_data' AND NEW.status IN ('assigned','cancelled')) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid verification task transition: % -> %', OLD.status, NEW.status;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION citygap_increment_verification_task_version() RETURNS trigger AS $$
BEGIN
    IF NEW IS DISTINCT FROM OLD THEN
        NEW.record_version = OLD.record_version + 1;
        NEW.updated_at = now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER field_verification_tasks_lifecycle
    BEFORE UPDATE OF status ON field_verification_tasks
    FOR EACH ROW EXECUTE FUNCTION citygap_enforce_verification_task_transition();
CREATE TRIGGER field_verification_tasks_record_version
    BEFORE UPDATE ON field_verification_tasks
    FOR EACH ROW EXECUTE FUNCTION citygap_increment_verification_task_version();

CREATE TABLE field_verification_targets (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    task_id uuid NOT NULL,
    target_scope text NOT NULL CHECK (
        target_scope IN ('mesh','plateau_object','plateau_object_group')
    ),
    object_type text NOT NULL CHECK (
        object_type IN (
            'mesh','building','road','terrain','landuse','planning','hazard','facility'
        )
    ),
    source_object_id text NOT NULL,
    source_dataset_version_id uuid,
    spatial_pack_id uuid,
    spatial_pack_object_id bigint,
    group_key text,
    target_role text NOT NULL DEFAULT 'primary' CHECK (
        target_role IN ('primary','context')
    ),
    label text,
    geometry geometry(Geometry, 4326),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, task_id, object_type, source_object_id, target_role),
    FOREIGN KEY (organization_id, task_id)
        REFERENCES field_verification_tasks(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, source_dataset_version_id)
        REFERENCES dataset_versions(organization_id, id),
    FOREIGN KEY (organization_id, spatial_pack_id)
        REFERENCES spatial_evidence_packs(organization_id, id),
    FOREIGN KEY (organization_id, spatial_pack_object_id)
        REFERENCES spatial_pack_objects(organization_id, id),
    CHECK (
        (target_scope = 'mesh' AND object_type = 'mesh'
            AND source_dataset_version_id IS NULL
            AND spatial_pack_id IS NULL
            AND spatial_pack_object_id IS NULL)
        OR
        (target_scope IN ('plateau_object','plateau_object_group')
            AND object_type <> 'mesh'
            AND source_dataset_version_id IS NOT NULL
            AND spatial_pack_id IS NOT NULL
            AND spatial_pack_object_id IS NOT NULL)
    ),
    CHECK (
        (target_scope = 'plateau_object_group' AND group_key IS NOT NULL)
        OR target_scope <> 'plateau_object_group'
    ),
    CHECK (geometry IS NULL OR (ST_IsValid(geometry) AND NOT ST_IsEmpty(geometry)))
);
CREATE INDEX field_verification_targets_geometry_idx
    ON field_verification_targets USING gist (geometry);

ALTER TABLE field_observations
    ADD CONSTRAINT field_observations_organization_id_id_unique
        UNIQUE (organization_id, id),
    ADD COLUMN verification_task_id uuid,
    ADD COLUMN response_schema_version text,
    ADD COLUMN structured_answers jsonb NOT NULL DEFAULT '[]' CHECK (
        jsonb_typeof(structured_answers) = 'array'
        AND octet_length(structured_answers::text) <= 65536
    ),
    ADD COLUMN gps_capture_state text NOT NULL DEFAULT 'not_attempted' CHECK (
        gps_capture_state IN (
            'captured','permission_denied','unavailable','not_attempted'
        )
    ),
    ADD COLUMN evidence_completeness text NOT NULL DEFAULT 'not_evaluated' CHECK (
        evidence_completeness IN ('complete','incomplete','not_evaluated')
    ),
    ADD COLUMN record_version bigint NOT NULL DEFAULT 1 CHECK (record_version > 0),
    ADD CONSTRAINT field_observations_verification_task_fk
        FOREIGN KEY (organization_id, verification_task_id)
        REFERENCES field_verification_tasks(organization_id, id),
    ADD CONSTRAINT field_observations_verification_shape_check CHECK (
        verification_task_id IS NULL
        OR (
            response_schema_version = 'citygap-verification-submission-1.0.0'
            AND status IN ('submitted','reviewed','rejected')
        )
    );

CREATE FUNCTION citygap_increment_verification_observation_version() RETURNS trigger AS $$
BEGIN
    IF OLD.verification_task_id IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
        NEW.record_version = OLD.record_version + 1;
        NEW.updated_at = now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER field_observations_verification_record_version
    BEFORE UPDATE ON field_observations
    FOR EACH ROW EXECUTE FUNCTION citygap_increment_verification_observation_version();

CREATE TABLE field_verification_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    task_id uuid NOT NULL,
    field_observation_id uuid NOT NULL,
    field_conclusion text NOT NULL CHECK (
        field_conclusion IN (
            'supported','contradicted','partially_supported',
            'needs_more_data','not_assessed'
        )
    ),
    municipal_disposition text NOT NULL CHECK (
        municipal_disposition IN (
            'continue_review','existing_measures','out_of_scope'
        )
    ),
    rationale text NOT NULL CHECK (length(rationale) BETWEEN 1 AND 10000),
    existing_measures text NOT NULL DEFAULT '',
    missing_data text NOT NULL DEFAULT '',
    supersedes_review_id uuid,
    resulting_field_validation_status text CHECK (
        resulting_field_validation_status IS NULL OR
        resulting_field_validation_status IN (
            'supported_by_field','contradicted_by_field',
            'partially_supported','needs_more_data'
        )
    ),
    reviewed_by text NOT NULL,
    reviewed_at timestamptz NOT NULL DEFAULT now(),
    source text NOT NULL DEFAULT 'human_entry' CHECK (source = 'human_entry'),
    automatic_confirmation boolean NOT NULL DEFAULT false CHECK (NOT automatic_confirmation),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, task_id)
        REFERENCES field_verification_tasks(organization_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id, field_observation_id)
        REFERENCES field_observations(organization_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id, supersedes_review_id)
        REFERENCES field_verification_reviews(organization_id, id) ON DELETE RESTRICT
);
CREATE INDEX field_verification_reviews_task_idx
    ON field_verification_reviews (organization_id, task_id, reviewed_at DESC);

CREATE FUNCTION citygap_field_verification_review_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'field verification reviews are append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER field_verification_reviews_immutable
    BEFORE UPDATE OR DELETE ON field_verification_reviews
    FOR EACH ROW EXECUTE FUNCTION citygap_field_verification_review_immutable();

CREATE TABLE field_verification_offline_packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    task_id uuid NOT NULL,
    package_version integer NOT NULL DEFAULT 1 CHECK (package_version > 0),
    base_record_version bigint NOT NULL CHECK (base_record_version > 0),
    content jsonb NOT NULL CHECK (
        jsonb_typeof(content) = 'object' AND octet_length(content::text) <= 2097152
    ),
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    expires_at timestamptz,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, task_id, package_version),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, task_id)
        REFERENCES field_verification_tasks(organization_id, id) ON DELETE CASCADE
);

CREATE TABLE field_verification_sync_operations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    client_operation_id uuid NOT NULL,
    offline_package_id uuid NOT NULL,
    task_id uuid NOT NULL,
    actor text NOT NULL,
    base_record_version bigint NOT NULL CHECK (base_record_version > 0),
    client_updated_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK (
        jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 65536
    ),
    status text NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending','applied','conflict','rejected')
    ),
    received_at timestamptz NOT NULL DEFAULT now(),
    applied_at timestamptz,
    UNIQUE (organization_id, client_operation_id),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, offline_package_id)
        REFERENCES field_verification_offline_packages(organization_id, id),
    FOREIGN KEY (organization_id, task_id)
        REFERENCES field_verification_tasks(organization_id, id),
    CHECK (
        (status = 'applied' AND applied_at IS NOT NULL)
        OR (status <> 'applied' AND applied_at IS NULL)
    )
);

CREATE TABLE field_verification_sync_conflicts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    sync_operation_id uuid NOT NULL,
    server_record_version bigint NOT NULL CHECK (server_record_version > 0),
    server_state jsonb NOT NULL CHECK (jsonb_typeof(server_state) = 'object'),
    client_state jsonb NOT NULL CHECK (jsonb_typeof(client_state) = 'object'),
    resolution_status text NOT NULL DEFAULT 'unresolved' CHECK (
        resolution_status IN ('unresolved','use_server','use_client','merged')
    ),
    resolved_state jsonb,
    resolved_by text,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, sync_operation_id),
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, sync_operation_id)
        REFERENCES field_verification_sync_operations(organization_id, id) ON DELETE CASCADE,
    CHECK (
        (resolution_status = 'unresolved'
            AND resolved_state IS NULL AND resolved_by IS NULL AND resolved_at IS NULL)
        OR
        (resolution_status <> 'unresolved'
            AND resolved_state IS NOT NULL AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)
    )
);

ALTER TABLE assignments DROP CONSTRAINT assignments_assignment_type_check;
ALTER TABLE assignments ADD CONSTRAINT assignments_assignment_type_check CHECK (
    assignment_type IN ('investigation','review','field_check','verification_task')
);

ALTER TABLE activity_events DROP CONSTRAINT activity_events_event_type_check;
ALTER TABLE activity_events ADD CONSTRAINT activity_events_event_type_check CHECK (
    event_type IN (
        'dataset_updated','finding_created','investigation_started',
        'scenario_compared','review_submitted','field_check_added',
        'decision_recorded','urban_state_promoted','finding_status_changed',
        'review_status_changed','investigation_status_changed','analysis_started',
        'saved_view_created','annual_update_queued',
        'verification_task_created','verification_task_assigned',
        'verification_task_submitted','verification_task_reviewed'
    )
);

ALTER TABLE notifications DROP CONSTRAINT notifications_notification_type_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_notification_type_check CHECK (
    notification_type IN (
        'review_requested','field_check_assigned','dataset_failed','dataset_updated',
        'analysis_finished','conflict_found','assignment_assigned',
        'verification_task_assigned','verification_task_submitted',
        'verification_task_reviewed'
    )
);

COMMENT ON TABLE field_verification_tasks IS
    'Bounded tasks derived from declared analysis uncertainty; never generic field forms.';
COMMENT ON TABLE field_verification_reviews IS
    'Append-only human conclusions; official source and analysis records remain unchanged.';
COMMENT ON COLUMN findings.field_validation_status IS
    'Human field-evidence projection, separate from analysis validation_status.';

COMMIT;
