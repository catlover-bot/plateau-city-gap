BEGIN;

-- Data-manager work is a first-class, tenant-scoped record. Discovery is never
-- acceptance and a task never changes source bytes or a promoted dataset.
CREATE TABLE open_data_operator_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    city_source_id uuid,
    resource_id uuid,
    dataset_version_id uuid,
    job_run_id uuid,
    task_type text NOT NULL CHECK (
        task_type IN (
            'new_source','update_available','schema_changed','quality_failed',
            'license_review','ingestion_completed','field_verification',
            'reconciliation_review'
        )
    ),
    status text NOT NULL DEFAULT 'open' CHECK (
        status IN ('open','in_progress','resolved','dismissed')
    ),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
    detail jsonb NOT NULL DEFAULT '{}',
    created_by text NOT NULL,
    assigned_to text,
    resolution_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, city_source_id)
        REFERENCES city_open_data_sources(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, resource_id)
        REFERENCES open_data_resources(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, dataset_version_id)
        REFERENCES dataset_versions(organization_id, id),
    FOREIGN KEY (organization_id, job_run_id)
        REFERENCES job_runs(organization_id, id),
    CHECK (
        (status IN ('resolved','dismissed') AND resolved_at IS NOT NULL
            AND resolution_note IS NOT NULL AND length(resolution_note) > 0)
        OR (status IN ('open','in_progress') AND resolved_at IS NULL)
    )
);
CREATE INDEX open_data_operator_tasks_queue_idx
    ON open_data_operator_tasks (
        organization_id, city_id, status, task_type, created_at DESC, id
    );
CREATE UNIQUE INDEX open_data_operator_tasks_active_subject_idx
    ON open_data_operator_tasks (
        organization_id, city_id, task_type,
        COALESCE(city_source_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(resource_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(dataset_version_id, '00000000-0000-0000-0000-000000000000'::uuid)
    ) WHERE status IN ('open','in_progress');

-- Provider metadata checks are deliberately rate bounded. The policy schedules
-- metadata only; it does not download, accept or promote a changed resource.
CREATE TABLE open_data_source_refresh_policies (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_source_id uuid NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    minimum_interval_hours smallint NOT NULL DEFAULT 24 CHECK (
        minimum_interval_hours BETWEEN 6 AND 8760
    ),
    scheduled_interval_hours smallint NOT NULL DEFAULT 168 CHECK (
        scheduled_interval_hours BETWEEN 6 AND 8760
    ),
    next_check_after timestamptz NOT NULL DEFAULT now(),
    last_checked_at timestamptz,
    last_result text CHECK (
        last_result IS NULL OR last_result IN (
            'unchanged','update_available','failed','rate_limited'
        )
    ),
    consecutive_failures integer NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
    configured_by text NOT NULL,
    configured_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, city_source_id),
    FOREIGN KEY (organization_id, city_source_id)
        REFERENCES city_open_data_sources(organization_id, id) ON DELETE CASCADE,
    CHECK (scheduled_interval_hours >= minimum_interval_hours)
);
CREATE INDEX open_data_source_refresh_policies_due_idx
    ON open_data_source_refresh_policies (
        organization_id, next_check_after, city_source_id
    ) WHERE enabled;

ALTER TABLE open_data_transformation_runs ADD CONSTRAINT
    open_data_transformation_runs_org_id_resource_unique
    UNIQUE (organization_id, id, resource_id);

-- A quarantine is an explicit analysis-blocking decision. A later adapter may
-- reprocess the immutable resource, but the old run and old canonical records stay.
CREATE TABLE open_data_quarantine_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_id uuid NOT NULL,
    transformation_run_id uuid,
    category text NOT NULL CHECK (
        category IN (
            'schema_invalid','schema_changed','checksum_mismatch','crs_unknown',
            'license_unknown','archive_unsafe','xml_unsafe','formula_unsafe',
            'geometry_oversized','encoding_invalid','malformed_content','other'
        )
    ),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 4000),
    evidence jsonb NOT NULL DEFAULT '{}',
    blocks_analysis boolean NOT NULL DEFAULT true CHECK (blocks_analysis),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
    quarantined_by text NOT NULL,
    quarantined_at timestamptz NOT NULL DEFAULT now(),
    resolved_by text,
    resolved_at timestamptz,
    resolution_note text,
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, resource_id)
        REFERENCES open_data_resources(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, transformation_run_id, resource_id)
        REFERENCES open_data_transformation_runs(organization_id, id, resource_id),
    CHECK (
        (status = 'resolved' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL
            AND resolution_note IS NOT NULL AND length(resolution_note) > 0)
        OR (status = 'open' AND resolved_by IS NULL AND resolved_at IS NULL)
    )
);
CREATE INDEX open_data_quarantine_events_open_idx
    ON open_data_quarantine_events (organization_id, resource_id, quarantined_at DESC)
    WHERE status = 'open';

CREATE TABLE open_data_reprocessing_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_id uuid NOT NULL,
    previous_transformation_run_id uuid,
    target_adapter_id text NOT NULL REFERENCES open_data_adapters(adapter_id),
    target_adapter_version text NOT NULL,
    target_transformation_version text NOT NULL,
    target_canonical_version text NOT NULL,
    job_run_id uuid,
    status text NOT NULL DEFAULT 'queued' CHECK (
        status IN ('queued','running','succeeded','failed','quarantined')
    ),
    preserve_previous_canonical boolean NOT NULL DEFAULT true CHECK (
        preserve_previous_canonical
    ),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 4000),
    requested_by text NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, resource_id)
        REFERENCES open_data_resources(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, previous_transformation_run_id, resource_id)
        REFERENCES open_data_transformation_runs(organization_id, id, resource_id),
    FOREIGN KEY (organization_id, job_run_id)
        REFERENCES job_runs(organization_id, id),
    CHECK (
        (status IN ('queued','running') AND completed_at IS NULL)
        OR (status IN ('succeeded','failed','quarantined') AND completed_at IS NOT NULL)
    )
);
CREATE INDEX open_data_reprocessing_requests_resource_idx
    ON open_data_reprocessing_requests (
        organization_id, resource_id, requested_at DESC, id
    );

-- Snapshot the exact open-data chain selected by a versioned analysis. This is
-- supplemental to analysis_run_dataset_versions and never resolves a live URL.
CREATE TABLE analysis_run_open_data_inputs (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    analysis_run_id uuid NOT NULL,
    input_role text NOT NULL,
    resource_id uuid NOT NULL,
    transformation_run_id uuid NOT NULL,
    raw_blob_id uuid,
    raw_sha256 char(64) NOT NULL CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'),
    adapter_id text NOT NULL REFERENCES open_data_adapters(adapter_id),
    adapter_version text NOT NULL,
    transformation_version text NOT NULL,
    canonical_version text NOT NULL,
    algorithm_version text NOT NULL,
    parameters_sha256 char(64) NOT NULL CHECK (parameters_sha256 ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (
        organization_id, analysis_run_id, input_role, transformation_run_id
    ),
    FOREIGN KEY (organization_id, analysis_run_id)
        REFERENCES analysis_runs(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, resource_id)
        REFERENCES open_data_resources(organization_id, id),
    FOREIGN KEY (organization_id, transformation_run_id, resource_id)
        REFERENCES open_data_transformation_runs(organization_id, id, resource_id),
    FOREIGN KEY (raw_blob_id) REFERENCES open_data_raw_blobs(id)
);
CREATE INDEX analysis_run_open_data_inputs_resource_idx
    ON analysis_run_open_data_inputs (
        organization_id, resource_id, analysis_run_id
    );

-- Public-source feedback and municipal overrides remain separate layers. Feedback
-- cannot mutate raw or canonical official records.
CREATE TABLE open_data_source_feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    city_source_id uuid NOT NULL,
    canonical_record_id bigint,
    feedback_type text NOT NULL CHECK (
        feedback_type IN (
            'facility_closed','service_changed','timetable_mismatch',
            'geometry_issue','attribute_issue','other'
        )
    ),
    statement text NOT NULL CHECK (length(statement) BETWEEN 1 AND 4000),
    evidence jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'submitted' CHECK (
        status IN ('submitted','triaged','field_check_required','reconciled','closed')
    ),
    submitted_by text NOT NULL,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    reviewed_by text,
    reviewed_at timestamptz,
    resolution_note text,
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, city_source_id)
        REFERENCES city_open_data_sources(organization_id, id),
    FOREIGN KEY (organization_id, canonical_record_id)
        REFERENCES canonical_open_data_records(organization_id, id),
    CHECK (
        (status IN ('reconciled','closed') AND reviewed_by IS NOT NULL
            AND reviewed_at IS NOT NULL AND resolution_note IS NOT NULL)
        OR status IN ('submitted','triaged','field_check_required')
    )
);
CREATE INDEX open_data_source_feedback_city_idx
    ON open_data_source_feedback (
        organization_id, city_id, status, submitted_at DESC, id
    );

-- Overrides must always declare their review horizon. Existing rows, if any, are
-- assigned a one-year horizon without changing their effective data patch.
UPDATE local_data_overrides
SET expires_at = effective_date + 365
WHERE expires_at IS NULL;
ALTER TABLE local_data_overrides ALTER COLUMN expires_at SET NOT NULL;

-- Query-path indexes used by lineage, source updates and spatial investigations.
CREATE INDEX open_data_update_checks_source_latest_idx
    ON open_data_update_checks (
        organization_id, city_source_id, checked_at DESC, id DESC
    );
CREATE INDEX open_data_resources_source_created_idx
    ON open_data_resources (
        organization_id, city_source_id, created_at DESC, id
    );
CREATE INDEX open_data_transformation_runs_resource_started_idx
    ON open_data_transformation_runs (
        organization_id, resource_id, started_at DESC, id
    );
CREATE INDEX open_data_spatial_links_record_method_idx
    ON open_data_spatial_links (
        organization_id, canonical_record_id, match_method, link_type
    );

CREATE FUNCTION citygap_open_data_update_task() RETURNS trigger AS $$
DECLARE
    source_row city_open_data_sources%ROWTYPE;
BEGIN
    SELECT * INTO source_row
    FROM city_open_data_sources
    WHERE organization_id = NEW.organization_id AND id = NEW.city_source_id;

    INSERT INTO open_data_source_refresh_policies (
        organization_id, city_source_id, next_check_after, last_checked_at,
        last_result, consecutive_failures, configured_by
    ) VALUES (
        NEW.organization_id, NEW.city_source_id, NEW.next_check_after, NEW.checked_at,
        NEW.result, CASE WHEN NEW.result = 'failed' THEN 1 ELSE 0 END, 'system:metadata-check'
    )
    ON CONFLICT (organization_id, city_source_id) DO UPDATE SET
        next_check_after = EXCLUDED.next_check_after,
        last_checked_at = EXCLUDED.last_checked_at,
        last_result = EXCLUDED.last_result,
        consecutive_failures = CASE
            WHEN EXCLUDED.last_result = 'failed'
                THEN open_data_source_refresh_policies.consecutive_failures + 1
            ELSE 0
        END,
        updated_at = now();

    IF NEW.result = 'update_available' THEN
        INSERT INTO open_data_operator_tasks (
            organization_id, city_id, city_source_id, task_type, title,
            detail, created_by
        ) VALUES (
            NEW.organization_id, source_row.city_id, NEW.city_source_id,
            'update_available', source_row.title || ' に更新候補があります',
            jsonb_build_object(
                'update_check_id', NEW.id,
                'checked_at', NEW.checked_at,
                'observed_resource_url', NEW.observed_resource_url,
                'automatic_acceptance', false
            ), 'system:metadata-check'
        ) ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER open_data_update_check_task
    AFTER INSERT ON open_data_update_checks
    FOR EACH ROW EXECUTE FUNCTION citygap_open_data_update_task();

CREATE FUNCTION citygap_open_data_processing_task() RETURNS trigger AS $$
DECLARE
    source_row city_open_data_sources%ROWTYPE;
    version_id uuid;
BEGIN
    SELECT source.*
      INTO source_row
    FROM open_data_resources AS resource
    JOIN city_open_data_sources AS source
      ON source.organization_id = resource.organization_id
     AND source.id = resource.city_source_id
    WHERE resource.organization_id = NEW.organization_id
      AND resource.id = NEW.resource_id;

    SELECT resource.dataset_version_id
      INTO version_id
    FROM open_data_resources AS resource
    WHERE resource.organization_id = NEW.organization_id
      AND resource.id = NEW.resource_id;

    IF NEW.state = 'quarantined'
       AND (TG_OP = 'INSERT' OR OLD.state IS DISTINCT FROM NEW.state) THEN
        INSERT INTO open_data_operator_tasks (
            organization_id, city_id, city_source_id, resource_id,
            dataset_version_id, task_type, title, detail, created_by
        ) VALUES (
            NEW.organization_id, source_row.city_id, source_row.id, NEW.resource_id,
            version_id, 'quality_failed', source_row.title || ' は要確認です',
            jsonb_build_object('processing_state', NEW.state, 'reason', NEW.status_reason),
            'system:quality-gate'
        ) ON CONFLICT DO NOTHING;
    ELSIF NEW.state = 'analysis_ready'
       AND (TG_OP = 'INSERT' OR OLD.state IS DISTINCT FROM NEW.state) THEN
        INSERT INTO open_data_operator_tasks (
            organization_id, city_id, city_source_id, resource_id,
            dataset_version_id, task_type, title, detail, created_by
        ) VALUES (
            NEW.organization_id, source_row.city_id, source_row.id, NEW.resource_id,
            version_id, 'ingestion_completed', source_row.title || ' の取込が完了しました',
            jsonb_build_object('processing_state', NEW.state), 'system:ingestion'
        ) ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER open_data_processing_task
    AFTER INSERT OR UPDATE OF state ON open_data_resource_processing
    FOR EACH ROW EXECUTE FUNCTION citygap_open_data_processing_task();

CREATE FUNCTION citygap_open_data_quarantine_block() RETURNS trigger AS $$
DECLARE
    source_row city_open_data_sources%ROWTYPE;
    version_id uuid;
BEGIN
    INSERT INTO open_data_resource_processing (
        organization_id, resource_id, state, status_reason, updated_at
    ) VALUES (
        NEW.organization_id, NEW.resource_id, 'quarantined', NEW.reason, now()
    )
    ON CONFLICT (organization_id, resource_id) DO UPDATE SET
        state = 'quarantined', status_reason = EXCLUDED.status_reason, updated_at = now();

    SELECT source.*
      INTO source_row
    FROM open_data_resources AS resource
    JOIN city_open_data_sources AS source
      ON source.organization_id = resource.organization_id
     AND source.id = resource.city_source_id
    WHERE resource.organization_id = NEW.organization_id
      AND resource.id = NEW.resource_id;

    SELECT resource.dataset_version_id
      INTO version_id
    FROM open_data_resources AS resource
    WHERE resource.organization_id = NEW.organization_id
      AND resource.id = NEW.resource_id;

    INSERT INTO open_data_operator_tasks (
        organization_id, city_id, city_source_id, resource_id,
        dataset_version_id, task_type, title, detail, created_by
    ) VALUES (
        NEW.organization_id, source_row.city_id, source_row.id, NEW.resource_id,
        version_id,
        CASE WHEN NEW.category = 'license_unknown' THEN 'license_review'
             WHEN NEW.category = 'schema_changed' THEN 'schema_changed'
             ELSE 'quality_failed' END,
        source_row.title || ' を隔離しました',
        jsonb_build_object(
            'quarantine_id', NEW.id, 'category', NEW.category,
            'reason', NEW.reason, 'blocks_analysis', true
        ), NEW.quarantined_by
    ) ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER open_data_quarantine_block
    AFTER INSERT ON open_data_quarantine_events
    FOR EACH ROW EXECUTE FUNCTION citygap_open_data_quarantine_block();

COMMENT ON TABLE open_data_operator_tasks IS
    'Human data-manager queue. Task resolution is tenant-scoped and does not promote data.';
COMMENT ON TABLE open_data_source_refresh_policies IS
    'Rate-bounded metadata schedules. No live provider call occurs during analysis.';
COMMENT ON TABLE open_data_quarantine_events IS
    'Structured, analysis-blocking quality decisions for immutable source resources.';
COMMENT ON TABLE open_data_reprocessing_requests IS
    'A new adapter run over the same raw resource while prior canonical outputs remain immutable.';
COMMENT ON TABLE analysis_run_open_data_inputs IS
    'Exact raw checksum to adapter, canonical and algorithm chain captured at analysis creation.';
COMMENT ON TABLE open_data_source_feedback IS
    'Observed source disagreements; this table cannot mutate official raw or canonical records.';

COMMIT;
