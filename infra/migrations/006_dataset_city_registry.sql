BEGIN;

CREATE TABLE cities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_code text NOT NULL UNIQUE CHECK (city_code ~ '^[0-9]{5}$'),
    city_key text NOT NULL UNIQUE,
    name text NOT NULL,
    prefecture_code text NOT NULL CHECK (prefecture_code ~ '^[0-9]{2}$'),
    prefecture_name text NOT NULL,
    analysis_crs text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO cities (
    city_code, city_key, name, prefecture_code, prefecture_name, analysis_crs
)
SELECT DISTINCT
    version.city_id,
    version.city_id,
    version.city_name,
    substring(version.city_id FROM 1 FOR 2),
    'unregistered',
    'unregistered'
FROM city_dataset_versions AS version
ON CONFLICT (city_code) DO NOTHING;

ALTER TABLE city_dataset_versions
    ADD CONSTRAINT city_dataset_versions_city_registry_fk
    FOREIGN KEY (city_id) REFERENCES cities(city_code);

CREATE TABLE datasets (
    id uuid PRIMARY KEY,
    city_id uuid NOT NULL REFERENCES cities(id),
    dataset_key text NOT NULL,
    title text NOT NULL,
    provider text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (city_id, dataset_key)
);

CREATE TABLE dataset_versions (
    id uuid PRIMARY KEY,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version_key text NOT NULL,
    dataset_year integer NOT NULL CHECK (dataset_year BETWEEN 1900 AND 2200),
    data_format text NOT NULL,
    source_url text,
    license text,
    declared_source_crs text,
    archive_file_name text,
    archive_sha256 text CHECK (
        archive_sha256 IS NULL OR archive_sha256 ~ '^[0-9a-f]{64}$'
    ),
    verification_status text NOT NULL CHECK (
        verification_status IN ('metadata_registered', 'checksum_verified')
    ),
    registered_at timestamptz NOT NULL,
    UNIQUE (dataset_id, version_key)
);
CREATE INDEX dataset_versions_year_idx ON dataset_versions (dataset_year);
CREATE INDEX dataset_versions_hash_idx ON dataset_versions (archive_sha256);

ALTER TABLE city_dataset_versions
    ADD COLUMN registry_version_id uuid UNIQUE REFERENCES dataset_versions(id);

CREATE TABLE analysis_runs (
    id uuid PRIMARY KEY,
    city_id uuid NOT NULL REFERENCES cities(id),
    analysis_type text NOT NULL,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    config_hash text NOT NULL CHECK (config_hash ~ '^[0-9a-f]{64}$'),
    output_artifact text,
    output_sha256 text CHECK (output_sha256 IS NULL OR output_sha256 ~ '^[0-9a-f]{64}$'),
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}',
    CHECK (
        (status IN ('queued', 'running') AND completed_at IS NULL) OR
        (status IN ('succeeded', 'failed') AND completed_at IS NOT NULL)
    )
);
CREATE INDEX analysis_runs_city_type_idx ON analysis_runs (city_id, analysis_type, started_at);

CREATE TABLE analysis_run_dataset_versions (
    analysis_run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
    input_role text NOT NULL DEFAULT 'source',
    PRIMARY KEY (analysis_run_id, dataset_version_id, input_role)
);

CREATE TABLE city_capabilities (
    city_id uuid NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    capability text NOT NULL CHECK (
        capability IN (
            'screening', 'building_detail', 'road_network', 'terrain', 'land_use',
            'urban_planning', 'hazard', 'gtfs', 'scenario'
        )
    ),
    status text NOT NULL CHECK (status IN ('available', 'partial', 'unavailable')),
    note text NOT NULL,
    evidence jsonb NOT NULL DEFAULT '[]',
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (city_id, capability),
    CHECK (status = 'unavailable' OR jsonb_array_length(evidence) > 0)
);

CREATE VIEW dataset_registry_provenance AS
SELECT
    city.city_code,
    city.city_key,
    city.name AS city_name,
    dataset.dataset_key,
    dataset.title,
    dataset.provider,
    version.id AS dataset_version_id,
    version.version_key,
    version.dataset_year,
    version.data_format,
    version.source_url,
    version.license,
    version.archive_file_name,
    version.archive_sha256,
    version.verification_status,
    version.registered_at
FROM dataset_versions AS version
JOIN datasets AS dataset ON dataset.id = version.dataset_id
JOIN cities AS city ON city.id = dataset.city_id;

COMMENT ON TABLE city_capabilities IS
    'Evidence-backed availability. Missing city computations remain unavailable, never fabricated.';
COMMENT ON TABLE dataset_versions IS
    'Callers select an explicit UUID; no API or analysis job may silently substitute latest.';

COMMIT;
