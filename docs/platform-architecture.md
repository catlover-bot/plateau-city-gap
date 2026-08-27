# CITY GAP Urban Digital Twin Platform architecture

## Scope and status

The competition demo remains a static React/Cesium application deployed to GitHub Pages. The
platform is an additive path; it does not make the public demo depend on PostGIS or the API.

The implemented boundary now includes full CityGML ingestion, building allocation, an explicitly
experimental road-surface graph with terrain observations, land-use/planning/hazard context,
versioned scenarios, and an explicit multi-city capability registry:

```text
Maizuru 2025 CityGML ZIP (Git-ignored)
  -> streaming inventory / event parser
  -> dataset version + ingestion run
  -> city object metadata + geometry parts
  -> typed building / road / terrain / land-use / planning / hazard tables
  -> canonical Python + GeoParquet computation
  -> versioned road/network and spatial-context runs
  -> versioned scenario runs + municipal review lifecycle
  -> bounded FastAPI queries

Existing pre-generated analysis -> existing React/Cesium -> GitHub Pages (unchanged)
```

The DB-backed schema, loaders, API and PostgreSQL worker are exercised against real PostGIS and
pgRouting in CI. The integration boundary uses a small spatial fixture plus canonical scenario
tables, so it does not claim a full Maizuru/Fujisawa database load. The worker durably claims jobs
with `SKIP LOCKED`, records attempts/heartbeats/errors, applies bounded retries and preserves an
idempotency key over city, exact datasets, algorithm and configuration.

The product boundary follows this flow:

```text
PLATEAU
  buildings | roads | terrain | land use | urban planning | flood | landslide | tsunami
          + census / transport / facilities
                          |
                Urban Data Platform
                          |
           building population | routes | hazard/planning context
                          |
                   CITY GAP Engine
                          |
                discover | verify | propose
                          |
                  compare alternatives
                          |
                   municipal review
```

The platform preserves those boundaries: source themes are versioned before analysis; an overlap
or score is evidence for review, not an automatic municipal decision.

## Design decisions

- PostgreSQL/PostGIS is the municipal system of record; Python + versioned Parquet remains the
  reproducible computation/interchange boundary. Real DB integration is separately verified.
- `gml:id` is unique within a dataset version, not globally across years.
- `city_dataset_versions` allows 2025 and later releases to coexist. Exactly one version per city
  may be marked current.
- The platform registry separately models city, dataset, dataset version and analysis run. New
  workflow APIs require explicit version IDs and do not infer "latest" from `is_current`.
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
- Large feature APIs require a bbox and enforce pagination. Citywide municipal layers use
  version-explicit authenticated MVT with ETag and a bounded LRU cache, not unbounded GeoJSON.
- Hazard overlap always means `additional_confirmation_required`; feasibility remains
  `not_determined` until municipal review.

## Repository boundaries

- `analysis/`: reproducible static screening and builders
- `frontend/`: existing competition UI and GitHub Pages bundle
- `backend/citygap_platform/ingestion/`: CityGML inventory, event reader, PostGIS loader
- `backend/citygap_platform/ingestion/adapters.py`: bounded CityGML, GTFS, CSV, GeoJSON and
  GeoPackage source contracts
- `backend/citygap_platform/api/`: query boundary and FastAPI
- `infra/migrations/`: durable schema
- `infra/docker/`: reproducible local containers

The backend package is deliberately not named top-level `platform`, avoiding collision with
Python's standard-library `platform` module.

## Scale and evolution

The CI scale benchmark inserts 100,000 synthetic buildings and 100,000 synthetic road edges and
reports API p50/p95 without calling it real municipal data or a production SLA. GiST indexes,
bulk COPY paths, bounded bbox queries, MVT and an asynchronous PostgreSQL worker establish the
current scaling boundary. Partitioning/connection pooling remain evidence-driven deployment choices.

## Open formats and official interoperability

The platform accepts CityGML directly and stores no proprietary interchange format. The road
adapter prefers node/link output from the official
[PLATEAU RoadNetwork Generator](https://github.com/Project-PLATEAU/PLATEAU-RoadNetwork-Generator).
The official tool is documented for Windows and was not executed in this environment, so its
output adapter and the experimental CityGML LOD1 surface-adjacency fallback remain separate.
Existing official 3D Tiles continue to be served by Cesium without conversion through the
database.

Municipal CSV, GeoJSON and GeoPackage inputs use the same explicit version boundary. Adapter
inspection records content hashes, sizes, row/feature counts, CRS and layers, but never equates
inspection with database ingestion. See [municipal data adapters](municipal-data-adapters.md).
