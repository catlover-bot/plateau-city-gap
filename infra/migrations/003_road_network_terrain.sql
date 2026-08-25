BEGIN;

CREATE TABLE road_network_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    graph_version text NOT NULL,
    graph_method text NOT NULL,
    network_type text NOT NULL CHECK (network_type IN ('road', 'walk', 'surface_adjacency')),
    official_generator_repository text,
    official_generator_commit text,
    official_generator_executed boolean NOT NULL DEFAULT false,
    pedestrian_network boolean NOT NULL,
    route_semantics text NOT NULL,
    analysis_crs text NOT NULL,
    topology_tolerance_m double precision CHECK (topology_tolerance_m >= 0),
    config_hash text NOT NULL CHECK (config_hash ~ '^[0-9a-f]{64}$'),
    node_count integer NOT NULL CHECK (node_count >= 0),
    edge_count integer NOT NULL CHECK (edge_count >= 0),
    component_count integer NOT NULL CHECK (component_count >= 0),
    terrain_method text,
    terrain_node_coverage double precision CHECK (terrain_node_coverage BETWEEN 0 AND 1),
    generated_at timestamptz NOT NULL,
    software_commit text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}',
    UNIQUE (dataset_version_id, graph_version)
);

CREATE TABLE road_network_nodes (
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id) ON DELETE CASCADE,
    node_id text NOT NULL,
    road_gml_id text,
    surface_id text,
    component_id text,
    pedestrian_permission text NOT NULL,
    elevation_m double precision,
    terrain_source_member text,
    terrain_source_member_crc32 char(8),
    terrain_triangle_index bigint,
    geom geometry(Point, 6674) NOT NULL,
    PRIMARY KEY (network_version_id, node_id),
    CHECK (
        elevation_m IS NULL OR
        (terrain_source_member IS NOT NULL AND terrain_source_member_crc32 IS NOT NULL)
    )
);
CREATE INDEX road_network_nodes_component_idx
    ON road_network_nodes (network_version_id, component_id);
CREATE INDEX road_network_nodes_geom_idx ON road_network_nodes USING gist (geom);

CREATE TABLE road_network_edges (
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id) ON DELETE CASCADE,
    edge_id text NOT NULL,
    source_node_id text NOT NULL,
    target_node_id text NOT NULL,
    length_m double precision NOT NULL CHECK (length_m > 0),
    topology_relation text,
    surface_gap_m double precision CHECK (surface_gap_m >= 0),
    pedestrian_permission text NOT NULL,
    source_elevation_m double precision,
    target_elevation_m double precision,
    elevation_delta_source_to_target_m double precision,
    absolute_grade_percent double precision CHECK (absolute_grade_percent >= 0),
    geom geometry(LineString, 6674) NOT NULL,
    PRIMARY KEY (network_version_id, edge_id),
    FOREIGN KEY (network_version_id, source_node_id)
        REFERENCES road_network_nodes(network_version_id, node_id),
    FOREIGN KEY (network_version_id, target_node_id)
        REFERENCES road_network_nodes(network_version_id, node_id)
);
CREATE INDEX road_network_edges_source_idx
    ON road_network_edges (network_version_id, source_node_id);
CREATE INDEX road_network_edges_target_idx
    ON road_network_edges (network_version_id, target_node_id);
CREATE INDEX road_network_edges_geom_idx ON road_network_edges USING gist (geom);

CREATE TABLE facility_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    facility_key text NOT NULL,
    facility_type text NOT NULL,
    name text NOT NULL,
    source_dataset text NOT NULL,
    source_year integer,
    source_record_id text,
    inclusion_policy text NOT NULL,
    geom geometry(Point, 4326) NOT NULL,
    attributes jsonb NOT NULL DEFAULT '{}',
    UNIQUE (dataset_version_id, facility_key)
);
CREATE INDEX facility_registry_type_idx
    ON facility_registry (dataset_version_id, facility_type);
CREATE INDEX facility_registry_geom_idx ON facility_registry USING gist (geom);

CREATE TABLE building_network_accessibility (
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    network_version_id uuid NOT NULL REFERENCES road_network_versions(id),
    building_gml_id text NOT NULL,
    destination_class text NOT NULL CHECK (destination_class IN ('transport', 'medical')),
    destination_facility_key text,
    destination_name text,
    road_surface_id text,
    snapped_node_id text,
    building_to_surface_distance_m double precision CHECK (building_to_surface_distance_m >= 0),
    building_to_node_connector_m double precision CHECK (building_to_node_connector_m >= 0),
    network_distance_m double precision CHECK (network_distance_m >= 0),
    terrain_route_status text CHECK (
        terrain_route_status IN ('available', 'partial', 'unavailable', 'network_unreachable')
    ),
    terrain_route_coverage double precision CHECK (terrain_route_coverage BETWEEN 0 AND 1),
    route_ascent_m double precision CHECK (route_ascent_m >= 0),
    route_descent_m double precision CHECK (route_descent_m >= 0),
    maximum_absolute_grade_percent double precision CHECK (
        maximum_absolute_grade_percent >= 0
    ),
    route_semantics text NOT NULL,
    algorithm text NOT NULL,
    calculated_at timestamptz NOT NULL,
    provenance jsonb NOT NULL,
    PRIMARY KEY (
        dataset_version_id,
        network_version_id,
        building_gml_id,
        destination_class
    ),
    FOREIGN KEY (network_version_id, snapped_node_id)
        REFERENCES road_network_nodes(network_version_id, node_id)
);
CREATE INDEX building_network_accessibility_building_idx
    ON building_network_accessibility (dataset_version_id, building_gml_id);
CREATE INDEX building_network_accessibility_destination_idx
    ON building_network_accessibility (network_version_id, destination_class);

CREATE VIEW road_network_provenance AS
SELECT
    network.id AS network_version_id,
    network.graph_version,
    network.graph_method,
    network.network_type,
    network.official_generator_executed,
    network.pedestrian_network,
    network.route_semantics,
    network.config_hash,
    network.generated_at,
    dataset.city_id,
    dataset.city_name,
    dataset.dataset_year,
    dataset.archive_sha256
FROM road_network_versions AS network
JOIN city_dataset_versions AS dataset ON dataset.id = network.dataset_version_id;

COMMIT;
