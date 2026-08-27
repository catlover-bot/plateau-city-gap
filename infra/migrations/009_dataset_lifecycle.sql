BEGIN;

ALTER TABLE dataset_versions
    ADD COLUMN lifecycle_status text NOT NULL DEFAULT 'registered' CHECK (
        lifecycle_status IN ('registered', 'staging', 'validated', 'ingesting', 'available', 'failed')
    ),
    ADD COLUMN quality_status text NOT NULL DEFAULT 'pending' CHECK (
        quality_status IN ('pending', 'passed', 'failed')
    ),
    ADD COLUMN quality_report jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN analysis_ready boolean NOT NULL DEFAULT false,
    ADD CONSTRAINT dataset_versions_analysis_ready_gate CHECK (
        NOT analysis_ready OR (quality_status = 'passed' AND lifecycle_status = 'available')
    );

ALTER TABLE road_network_versions
    ADD COLUMN source_type text NOT NULL DEFAULT 'experimental_surface_adjacency' CHECK (
        source_type IN ('official_walk', 'official_drive', 'experimental_surface_adjacency')
    );
CREATE INDEX road_network_versions_source_idx
    ON road_network_versions (dataset_version_id, source_type, generated_at DESC);

CREATE TABLE dataset_feature_fingerprints (
    dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    gml_id text NOT NULL,
    feature_type text NOT NULL,
    geometry_sha256 char(64) NOT NULL,
    attributes_sha256 char(64) NOT NULL,
    feature_sha256 char(64) NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_version_id, gml_id)
);
CREATE INDEX dataset_feature_fingerprints_hash_idx
    ON dataset_feature_fingerprints (dataset_version_id, feature_sha256);

CREATE TABLE dataset_version_diffs (
    from_dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    to_dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    gml_id text NOT NULL,
    change_type text NOT NULL CHECK (change_type IN ('added', 'removed', 'changed', 'unchanged')),
    from_feature_sha256 char(64),
    to_feature_sha256 char(64),
    compared_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (from_dataset_version_id, to_dataset_version_id, gml_id),
    CHECK (from_dataset_version_id <> to_dataset_version_id),
    CHECK ((change_type = 'added' AND from_feature_sha256 IS NULL AND to_feature_sha256 IS NOT NULL) OR
           (change_type = 'removed' AND from_feature_sha256 IS NOT NULL AND to_feature_sha256 IS NULL) OR
           (change_type IN ('changed', 'unchanged') AND from_feature_sha256 IS NOT NULL AND to_feature_sha256 IS NOT NULL))
);
CREATE INDEX dataset_version_diffs_change_idx
    ON dataset_version_diffs (to_dataset_version_id, change_type);

CREATE TABLE analysis_dependencies (
    dependent_type text NOT NULL CHECK (dependent_type IN ('analysis', 'network', 'scenario')),
    dependent_id text NOT NULL,
    dependency_type text NOT NULL CHECK (
        dependency_type IN ('dataset_version', 'network_version', 'context_run', 'feature_type')
    ),
    dependency_id text NOT NULL,
    feature_types text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dependent_type, dependent_id, dependency_type, dependency_id)
);
CREATE INDEX analysis_dependencies_lookup_idx
    ON analysis_dependencies (dependency_type, dependency_id);

CREATE VIEW impacted_analysis AS
SELECT DISTINCT
    diff.to_dataset_version_id,
    dependency.dependent_type,
    dependency.dependent_id,
    diff.change_type,
    COALESCE(current_fingerprint.feature_type, previous_fingerprint.feature_type) AS feature_type
FROM dataset_version_diffs AS diff
JOIN analysis_dependencies AS dependency
  ON dependency.dependency_type = 'dataset_version'
 AND dependency.dependency_id = diff.from_dataset_version_id::text
LEFT JOIN dataset_feature_fingerprints AS current_fingerprint
  ON current_fingerprint.dataset_version_id = diff.to_dataset_version_id
 AND current_fingerprint.gml_id = diff.gml_id
LEFT JOIN dataset_feature_fingerprints AS previous_fingerprint
  ON previous_fingerprint.dataset_version_id = diff.from_dataset_version_id
 AND previous_fingerprint.gml_id = diff.gml_id
WHERE diff.change_type <> 'unchanged'
  AND (cardinality(dependency.feature_types) = 0 OR
       COALESCE(current_fingerprint.feature_type, previous_fingerprint.feature_type) = ANY(dependency.feature_types));

CREATE TABLE accessibility_metric_versions (
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    building_gml_id text NOT NULL,
    destination_class text NOT NULL,
    metric_source text NOT NULL CHECK (
        metric_source IN (
            'euclidean', 'experimental_surface_adjacency', 'official_drive', 'official_walk'
        )
    ),
    network_version_id uuid REFERENCES road_network_versions(id),
    algorithm_version text NOT NULL,
    config_hash char(64) NOT NULL,
    distance_m double precision CHECK (distance_m >= 0),
    duration_seconds double precision CHECK (duration_seconds >= 0),
    provenance jsonb NOT NULL,
    calculated_at timestamptz NOT NULL,
    PRIMARY KEY (
        dataset_version_id, building_gml_id, destination_class,
        metric_source, algorithm_version, config_hash
    ),
    CHECK ((metric_source = 'euclidean' AND network_version_id IS NULL) OR
           (metric_source <> 'euclidean' AND network_version_id IS NOT NULL))
);
CREATE INDEX accessibility_metric_versions_compare_idx
    ON accessibility_metric_versions (dataset_version_id, building_gml_id, destination_class);

CREATE TABLE upload_inspections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor text NOT NULL,
    source_format text NOT NULL,
    source_sha256 char(64) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    accepted boolean NOT NULL,
    inspection jsonb NOT NULL,
    inspected_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE dataset_version_diffs IS
    'Feature update classification uses gml:id plus geometry and important-attribute hashes.';
COMMENT ON TABLE impacted_analysis IS
    'A conservative dependency view; operators decide re-execution, never an automatic policy result.';
COMMENT ON TABLE accessibility_metric_versions IS
    'Metrics from different network semantics are side-by-side and never overwritten.';

COMMIT;
