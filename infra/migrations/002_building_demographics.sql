BEGIN;

CREATE TABLE building_demographics (
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    building_gml_id text NOT NULL,
    mesh_code text NOT NULL,
    estimated_population double precision NOT NULL CHECK (estimated_population >= 0),
    estimated_elderly_population double precision NOT NULL
        CHECK (estimated_elderly_population >= 0),
    allocation_method text NOT NULL,
    allocation_weight_source text NOT NULL,
    allocation_weight double precision NOT NULL CHECK (allocation_weight > 0),
    allocation_fraction double precision NOT NULL
        CHECK (allocation_fraction > 0 AND allocation_fraction <= 1),
    population_resolution text NOT NULL CHECK (population_resolution = 'building_estimate'),
    source_population_year integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_version_id, building_gml_id, mesh_code),
    FOREIGN KEY (dataset_version_id, building_gml_id)
        REFERENCES plateau_city_objects(dataset_version_id, gml_id) ON DELETE CASCADE
);

CREATE INDEX building_demographics_mesh_idx
    ON building_demographics (dataset_version_id, mesh_code);
CREATE INDEX building_demographics_gml_idx ON building_demographics (building_gml_id);

CREATE TABLE building_accessibility (
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    building_gml_id text NOT NULL,
    facility_policy text NOT NULL,
    nearest_transport_type text,
    nearest_transport_name text,
    nearest_transport_distance_m double precision
        CHECK (nearest_transport_distance_m IS NULL OR nearest_transport_distance_m >= 0),
    nearest_medical_name text,
    nearest_medical_distance_m double precision
        CHECK (nearest_medical_distance_m IS NULL OR nearest_medical_distance_m >= 0),
    origin_method text NOT NULL CHECK (origin_method = 'building_origin_representative_point'),
    calculated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_version_id, building_gml_id, facility_policy),
    FOREIGN KEY (dataset_version_id, building_gml_id)
        REFERENCES plateau_city_objects(dataset_version_id, gml_id) ON DELETE CASCADE
);

CREATE INDEX building_accessibility_gml_idx ON building_accessibility (building_gml_id);

COMMIT;
