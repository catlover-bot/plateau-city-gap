BEGIN;

-- Local projected CRS is a city/version property (Maizuru 6674, Fujisawa 6677).
-- Removing the fixed typmod retains the SRID on every geometry while allowing the same
-- platform tables and official-network adapter to accept another municipality.
ALTER TABLE road_network_nodes
    ALTER COLUMN geom TYPE geometry(Point) USING geom;
ALTER TABLE road_network_edges
    ALTER COLUMN geom TYPE geometry(LineString) USING geom;
ALTER TABLE scenario_candidate_spatial_context
    ALTER COLUMN candidate_geom TYPE geometry(Point) USING candidate_geom;
ALTER TABLE road_network_nodes ADD CONSTRAINT road_network_nodes_known_srid
    CHECK (ST_SRID(geom) > 0);
ALTER TABLE road_network_edges ADD CONSTRAINT road_network_edges_known_srid
    CHECK (ST_SRID(geom) > 0);
ALTER TABLE scenario_candidate_spatial_context ADD CONSTRAINT scenario_candidate_known_srid
    CHECK (ST_SRID(candidate_geom) > 0);

CREATE TABLE scenario_building_impacts (
    scenario_run_id uuid NOT NULL REFERENCES scenario_runs(id) ON DELETE CASCADE,
    dataset_version_id uuid NOT NULL REFERENCES city_dataset_versions(id),
    building_gml_id text NOT NULL,
    before_distance_m double precision NOT NULL CHECK (before_distance_m >= 0),
    after_distance_m double precision NOT NULL CHECK (after_distance_m >= 0),
    distance_reduction_m double precision GENERATED ALWAYS AS (
        before_distance_m - after_distance_m
    ) STORED,
    impact_band text NOT NULL,
    PRIMARY KEY (scenario_run_id, building_gml_id),
    FOREIGN KEY (dataset_version_id, building_gml_id)
        REFERENCES plateau_city_objects(dataset_version_id, gml_id) ON DELETE CASCADE
);
CREATE INDEX scenario_building_impacts_dataset_idx
    ON scenario_building_impacts (dataset_version_id, scenario_run_id);
CREATE INDEX scenario_building_impacts_reduction_idx
    ON scenario_building_impacts (scenario_run_id, distance_reduction_m DESC);

COMMENT ON TABLE scenario_building_impacts IS
    'Municipal-only detailed scenario results used by version-explicit vector tiles; never a public asset.';

COMMIT;
