# CITY GAP Urban Digital Twin Platform architecture

## Scope and status

The competition demo remains a static React/Cesium application deployed to GitHub Pages. The
platform is an additive path; it does not make the public demo depend on PostGIS or the API.

Priority 1 implements the versioned PLATEAU ingestion boundary:

```text
Maizuru 2025 CityGML ZIP (Git-ignored)
  -> streaming inventory / event parser
  -> dataset version + ingestion run
  -> city object metadata + geometry parts
  -> typed building / road / terrain / land-use / planning / hazard tables
  -> bounded FastAPI queries

Existing pre-generated analysis -> existing React/Cesium -> GitHub Pages (unchanged)
```

Population allocation, generated road topology, network accessibility, detailed frontend mode,
and DB-backed scenarios are later priorities. Their tables or labels must not imply that those
calculations already exist.

## Design decisions

- PostgreSQL/PostGIS is the system of record; pgRouting is enabled for the later network phase.
- `gml:id` is unique within a dataset version, not globally across years.
- `city_dataset_versions` allows 2025 and later releases to coexist. Exactly one version per city
  may be marked current.
- Every record retains archive SHA-256, source member and CRC32, product specification version,
  ADE schema version, ingestion run and timestamp through direct columns and the provenance view.
- Typed analysis fields coexist with loss-minimizing JSONB attributes.
- Surface rings/TIN triangles are streamed into `plateau_geometry_parts`. A large terrain feature
  is never retained as a complete XML tree or one huge in-memory geometry.
- Source GML axis order is normalized to conventional longitude/latitude WKT for PostGIS 4326;
  the original CRS URI remains recorded. Metric analysis must explicitly transform to the
  appropriate local projected CRS (Maizuru: EPSG:6674).
- `representative_point` is a derived point-on-envelope for indexing and discovery. It is not
  called or treated as a building entrance.
- Large feature APIs require a bbox and enforce pagination. Future citywide thematic display
  should use MVT/PMTiles rather than unbounded GeoJSON.

## Repository boundaries

- `analysis/`: reproducible static screening and builders
- `frontend/`: existing competition UI and GitHub Pages bundle
- `backend/citygap_platform/ingestion/`: CityGML inventory, event reader, PostGIS loader
- `backend/citygap_platform/api/`: query boundary and FastAPI
- `infra/migrations/`: durable schema
- `infra/docker/`: reproducible local containers

The backend package is deliberately not named top-level `platform`, avoiding collision with
Python's standard-library `platform` module.

## Scale and evolution

The engineering target is 100,000+ buildings and road edges per city, with a multi-city feature
class reaching 1,000,000 records. These are design targets, not measured capacity claims. GiST
geometry indexes, per-member commits and bbox APIs establish the first scaling boundary. Bulk
COPY, partitioning, vector-tile generation, connection pooling and asynchronous scenario workers
should be introduced only when benchmark evidence requires them.

## Open formats and official interoperability

The platform accepts CityGML directly and stores no proprietary interchange format. Later road
topology work will prefer importing GeoJSON/Shapefile output from the official
[PLATEAU RoadNetwork Generator](https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator).
The official tool is documented for Windows, so its output adapter and any development-only
fallback extractor remain separate components. Existing official 3D Tiles continue to be served
by Cesium without conversion through the database.
