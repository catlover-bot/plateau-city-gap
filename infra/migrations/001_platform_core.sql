BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE city_dataset_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id text NOT NULL,
    city_name text NOT NULL,
    dataset_year integer NOT NULL CHECK (dataset_year BETWEEN 2000 AND 2200),
    dataset_name text NOT NULL,
    product_specification_version text NOT NULL,
    ade_schema_version text,
    archive_file_name text NOT NULL,
    archive_sha256 text NOT NULL CHECK (archive_sha256 ~ '^[0-9a-f]{64}$'),
    archive_size_bytes bigint NOT NULL CHECK (archive_size_bytes > 0),
    source_url text,
    published_at date,
    is_current boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (city_id, dataset_year, archive_sha256)
);

CREATE UNIQUE INDEX city_dataset_versions_one_current
    ON city_dataset_versions (city_id) WHERE is_current;

CREATE TABLE ingestion_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    parser_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    processed_members integer NOT NULL DEFAULT 0,
    processed_features bigint NOT NULL DEFAULT 0,
    processed_geometry_parts bigint NOT NULL DEFAULT 0,
    error_message text,
    CHECK ((status = 'running' AND completed_at IS NULL) OR status <> 'running')
);

CREATE TABLE plateau_city_objects (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    ingestion_run_id uuid NOT NULL REFERENCES ingestion_runs(id),
    gml_id text NOT NULL,
    theme text NOT NULL,
    feature_type text NOT NULL,
    lods smallint[] NOT NULL DEFAULT '{}',
    source_crs text[] NOT NULL DEFAULT '{}',
    source_member text NOT NULL,
    source_member_crc32 char(8) NOT NULL,
    attributes jsonb NOT NULL DEFAULT '{}',
    geometry_envelope geometry(Geometry, 4326),
    representative_point geometry(Point, 4326),
    ingested_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_version_id, gml_id)
);

CREATE INDEX plateau_city_objects_dataset_theme_idx
    ON plateau_city_objects (dataset_version_id, theme, feature_type);
CREATE INDEX plateau_city_objects_gml_id_idx ON plateau_city_objects (gml_id);
CREATE INDEX plateau_city_objects_attributes_idx ON plateau_city_objects USING gin (attributes);
CREATE INDEX plateau_city_objects_envelope_idx
    ON plateau_city_objects USING gist (geometry_envelope);
CREATE INDEX plateau_city_objects_point_idx
    ON plateau_city_objects USING gist (representative_point);

CREATE TABLE plateau_geometry_parts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city_object_id bigint NOT NULL REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    part_order integer NOT NULL,
    role text NOT NULL,
    geometry_type text NOT NULL,
    lod smallint,
    source_crs text,
    geom geometry(GeometryZ, 4326) NOT NULL,
    UNIQUE (city_object_id, part_order)
);
CREATE INDEX plateau_geometry_parts_object_idx ON plateau_geometry_parts (city_object_id);
CREATE INDEX plateau_geometry_parts_geom_idx ON plateau_geometry_parts USING gist (geom);

CREATE TABLE plateau_buildings (
    city_object_id bigint PRIMARY KEY REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    usage_code text,
    measured_height_m double precision,
    storeys_above_ground integer,
    storeys_below_ground integer,
    building_area_m2 double precision,
    floor_area_m2 double precision
);

CREATE TABLE plateau_roads (
    city_object_id bigint PRIMARY KEY REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    road_class text,
    function_code text,
    usage_code text,
    name text
);

CREATE TABLE plateau_terrain (
    city_object_id bigint PRIMARY KEY REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    relief_component_type text,
    minimum_elevation_m double precision,
    maximum_elevation_m double precision
);

CREATE TABLE plateau_landuse (
    city_object_id bigint PRIMARY KEY REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    class_code text,
    function_code text,
    usage_code text,
    area_m2 double precision
);

CREATE TABLE plateau_urban_planning (
    city_object_id bigint PRIMARY KEY REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    planning_type text,
    function_code text,
    usage_code text,
    name text
);

CREATE TABLE plateau_hazards (
    city_object_id bigint PRIMARY KEY REFERENCES plateau_city_objects(id) ON DELETE CASCADE,
    hazard_type text NOT NULL,
    rank_code text,
    rank_description text,
    depth_m double precision
);

CREATE VIEW plateau_feature_provenance AS
SELECT
    object.id AS city_object_id,
    object.gml_id,
    object.theme,
    object.feature_type,
    object.source_member,
    object.source_member_crc32,
    object.ingested_at,
    version.city_id,
    version.city_name,
    version.dataset_year,
    version.dataset_name,
    version.product_specification_version,
    version.ade_schema_version,
    version.archive_file_name,
    version.archive_sha256,
    version.source_url
FROM plateau_city_objects AS object
JOIN city_dataset_versions AS version ON version.id = object.dataset_version_id;

COMMIT;
