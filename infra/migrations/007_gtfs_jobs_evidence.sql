BEGIN;

CREATE TABLE gtfs_feeds (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL UNIQUE REFERENCES dataset_versions(id),
    feed_publisher_name text,
    feed_publisher_url text,
    feed_lang text,
    feed_start_date date,
    feed_end_date date,
    feed_version text,
    imported_at timestamptz NOT NULL DEFAULT now(),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE gtfs_stops (
    feed_id uuid NOT NULL REFERENCES gtfs_feeds(id) ON DELETE CASCADE,
    stop_id text NOT NULL,
    stop_code text,
    stop_name text NOT NULL,
    stop_desc text,
    zone_id text,
    location_type smallint,
    parent_station text,
    wheelchair_boarding smallint,
    geom geometry(Point, 4326) NOT NULL,
    PRIMARY KEY (feed_id, stop_id)
);
CREATE INDEX gtfs_stops_geom_idx ON gtfs_stops USING gist (geom);

CREATE TABLE gtfs_routes (
    feed_id uuid NOT NULL REFERENCES gtfs_feeds(id) ON DELETE CASCADE,
    route_id text NOT NULL,
    agency_id text,
    route_short_name text NOT NULL DEFAULT '',
    route_long_name text NOT NULL DEFAULT '',
    route_desc text,
    route_type integer NOT NULL,
    route_url text,
    route_color char(6),
    route_text_color char(6),
    PRIMARY KEY (feed_id, route_id),
    CHECK (route_short_name <> '' OR route_long_name <> '')
);

CREATE TABLE gtfs_calendar (
    feed_id uuid NOT NULL REFERENCES gtfs_feeds(id) ON DELETE CASCADE,
    service_id text NOT NULL,
    monday boolean NOT NULL,
    tuesday boolean NOT NULL,
    wednesday boolean NOT NULL,
    thursday boolean NOT NULL,
    friday boolean NOT NULL,
    saturday boolean NOT NULL,
    sunday boolean NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    PRIMARY KEY (feed_id, service_id),
    CHECK (start_date <= end_date)
);

CREATE TABLE gtfs_calendar_dates (
    feed_id uuid NOT NULL REFERENCES gtfs_feeds(id) ON DELETE CASCADE,
    service_id text NOT NULL,
    service_date date NOT NULL,
    exception_type smallint NOT NULL CHECK (exception_type IN (1, 2)),
    PRIMARY KEY (feed_id, service_id, service_date)
);

CREATE TABLE gtfs_trips (
    feed_id uuid NOT NULL REFERENCES gtfs_feeds(id) ON DELETE CASCADE,
    route_id text NOT NULL,
    service_id text NOT NULL,
    trip_id text NOT NULL,
    trip_headsign text,
    trip_short_name text,
    direction_id smallint CHECK (direction_id IN (0, 1)),
    block_id text,
    shape_id text,
    wheelchair_accessible smallint,
    bikes_allowed smallint,
    PRIMARY KEY (feed_id, trip_id),
    FOREIGN KEY (feed_id, route_id) REFERENCES gtfs_routes(feed_id, route_id)
);
CREATE INDEX gtfs_trips_service_idx ON gtfs_trips (feed_id, service_id);

CREATE TABLE gtfs_stop_times (
    feed_id uuid NOT NULL,
    trip_id text NOT NULL,
    stop_sequence integer NOT NULL CHECK (stop_sequence >= 0),
    stop_id text NOT NULL,
    arrival_time text NOT NULL CHECK (arrival_time ~ '^[0-9]+:[0-5][0-9]:[0-5][0-9]$'),
    departure_time text NOT NULL CHECK (departure_time ~ '^[0-9]+:[0-5][0-9]:[0-5][0-9]$'),
    arrival_seconds integer NOT NULL CHECK (arrival_seconds >= 0),
    departure_seconds integer NOT NULL CHECK (departure_seconds >= arrival_seconds),
    stop_headsign text,
    pickup_type smallint,
    drop_off_type smallint,
    timepoint smallint,
    PRIMARY KEY (feed_id, trip_id, stop_sequence),
    FOREIGN KEY (feed_id, trip_id) REFERENCES gtfs_trips(feed_id, trip_id),
    FOREIGN KEY (feed_id, stop_id) REFERENCES gtfs_stops(feed_id, stop_id)
);
CREATE INDEX gtfs_stop_times_stop_idx ON gtfs_stop_times (feed_id, stop_id);

CREATE TABLE job_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id uuid NOT NULL REFERENCES cities(id),
    job_type text NOT NULL CHECK (
        job_type IN (
            'plateau_ingestion', 'building_demographics', 'network_generation',
            'terrain_enrichment', 'context_generation', 'scenario_optimization'
        )
    ),
    state text NOT NULL DEFAULT 'queued' CHECK (
        state IN ('queued', 'running', 'succeeded', 'failed')
    ),
    current_stage text,
    config_hash text NOT NULL CHECK (config_hash ~ '^[0-9a-f]{64}$'),
    parameters jsonb NOT NULL DEFAULT '{}',
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    error_message text,
    CHECK (
        (state = 'queued' AND started_at IS NULL AND completed_at IS NULL) OR
        (state = 'running' AND started_at IS NOT NULL AND completed_at IS NULL) OR
        (state IN ('succeeded', 'failed') AND started_at IS NOT NULL AND completed_at IS NOT NULL)
    ),
    CHECK ((state = 'failed' AND error_message IS NOT NULL) OR state <> 'failed')
);
CREATE INDEX job_runs_city_state_idx ON job_runs (city_id, state, queued_at);

CREATE TABLE job_dataset_versions (
    job_run_id uuid NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    PRIMARY KEY (job_run_id, dataset_version_id)
);

CREATE TABLE job_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_run_id uuid NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    state text NOT NULL CHECK (state IN ('queued', 'running', 'succeeded', 'failed')),
    stage text,
    message text NOT NULL DEFAULT '',
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX job_events_run_idx ON job_events (job_run_id, recorded_at);

CREATE TABLE evidence_exports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id) ON DELETE CASCADE,
    export_format text NOT NULL CHECK (export_format IN ('json', 'csv', 'html')),
    artifact_path text NOT NULL,
    artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    generated_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}',
    UNIQUE (scenario_run_id, export_format, artifact_sha256)
);

COMMENT ON TABLE gtfs_feeds IS
    'A record exists only after a real GTFS feed is registered and validated. P11 points are not GTFS.';
COMMENT ON TABLE job_events IS
    'Progress is represented by completed real stages. Synthetic percentages are prohibited.';

COMMIT;
