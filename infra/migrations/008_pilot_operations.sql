BEGIN;

ALTER TABLE job_runs DROP CONSTRAINT job_runs_job_type_check;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_job_type_check CHECK (
    job_type IN (
        'plateau_ingestion', 'building_demographics',
        'road_network', 'network_generation',
        'terrain', 'terrain_enrichment',
        'spatial_context', 'context_generation',
        'scenario_optimization', 'evidence_export'
    )
);
ALTER TABLE job_runs
    ADD COLUMN algorithm_version text NOT NULL DEFAULT 'platform-0.1.0',
    ADD COLUMN idempotency_key char(64),
    ADD COLUMN retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    ADD COLUMN max_retries integer NOT NULL DEFAULT 2 CHECK (max_retries BETWEEN 0 AND 10),
    ADD COLUMN finished_at timestamptz,
    ADD COLUMN last_heartbeat_at timestamptz,
    ADD COLUMN locked_by text;
UPDATE job_runs SET finished_at = completed_at WHERE completed_at IS NOT NULL;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_retry_bound CHECK (retry_count <= max_retries);
CREATE UNIQUE INDEX job_runs_idempotency_idx
    ON job_runs (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX job_runs_claim_idx ON job_runs (state, queued_at)
    WHERE state = 'queued';

CREATE TABLE job_attempts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_run_id uuid NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    worker_id text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    result text CHECK (result IN ('succeeded', 'failed', 'requeued')),
    error_message text,
    UNIQUE (job_run_id, attempt_number),
    CHECK ((finished_at IS NULL AND result IS NULL) OR
           (finished_at IS NOT NULL AND result IS NOT NULL))
);

CREATE TABLE platform_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issuer text NOT NULL,
    subject text NOT NULL,
    display_name text NOT NULL,
    email text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (issuer, subject)
);

CREATE TABLE platform_user_roles (
    user_id uuid NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    city_id uuid REFERENCES cities(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('viewer', 'analyst', 'planner', 'administrator')),
    granted_at timestamptz NOT NULL DEFAULT now(),
    granted_by uuid REFERENCES platform_users(id),
    PRIMARY KEY (user_id, city_id, role)
);

CREATE TABLE audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor text NOT NULL,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    city_id text,
    request_id text NOT NULL,
    before_state jsonb,
    after_state jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_resource_idx
    ON audit_log (resource_type, resource_id, occurred_at DESC);
CREATE INDEX audit_log_actor_idx ON audit_log (actor, occurred_at DESC);
CREATE INDEX audit_log_city_idx ON audit_log (city_id, occurred_at DESC);

ALTER TABLE scenario_field_checks
    ADD COLUMN photo_urls text[] NOT NULL DEFAULT '{}',
    ADD COLUMN location_context jsonb NOT NULL DEFAULT '{}',
    ADD CONSTRAINT scenario_field_checks_photo_url_limit
        CHECK (cardinality(photo_urls) <= 10),
    ADD CONSTRAINT scenario_field_checks_photo_url_protocol
        CHECK (array_to_string(photo_urls, ',') ~ '^((https://[^,]+)(,https://[^,]+)*)?$');

COMMENT ON TABLE audit_log IS
    'Append-only operational evidence. It records decisions; it never generates policy.';
COMMENT ON COLUMN job_runs.idempotency_key IS
    'SHA-256 of city, sorted dataset versions, job type, algorithm version and config hash.';
COMMENT ON COLUMN scenario_field_checks.photo_urls IS
    'HTTPS references only. CITY GAP does not upload or store photographs in pilot mode.';

COMMIT;
