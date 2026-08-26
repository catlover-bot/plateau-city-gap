# PLATEAU CityGML ingestion

## Source profile

The Git-ignored source is
`data/raw/plateau_citygml/26202_maizuru-shi_city_2025_citygml_1_op.zip`. Its embedded README says
that the Maizuru 2025 product was created on 2026-03-20 and conforms to PLATEAU Standard Product
Specification 5.0. The archive contains ADE 3.2 schemas. The parser stores those values per
dataset version instead of assuming the current PLATEAU specification is the source version.

The current national specification is published separately by MLIT in the
[PLATEAU handbooks](https://www.mlit.go.jp/plateau/libraries/handbooks/). A later 5.1 archive can
therefore coexist with the 5.0 Maizuru archive and be handled by a version-aware dataset profile.

## Inventory

Run:

```bash
python -m analysis.scripts.build_plateau_inventory
```

The command never expands the archive. It streams each `udx/<theme>/*.gml` member with
`xml.etree.ElementTree.iterparse`, clears completed elements, and writes
`analysis/outputs/real/maizuru_plateau_inventory.json`.

Only an element directly below `core:cityObjectMember` is counted as a city feature. Nested ADE
records or polygon IDs are not inflated into feature totals. For every theme the inventory
records file count, compressed/uncompressed size, top-level feature types, per-feature LOD,
attribute availability, geometry type, CRS, duplicate `gml:id`, member CRC and parse time. The
archive SHA-256 and process peak RSS are also recorded.

The completed Maizuru run scanned 369 CityGML members across eight themes and found 97,140
top-level features with 97,140 unique `gml:id` values and no duplicate. It took 586.968 seconds
with 281,372 KiB peak RSS in the measured WSL2 run. The CityGML itself contains 44,640 top-level
Building features; this is kept distinct from the package README's stated 44,647 LOD1 buildings.

## Database ingestion

Start the database and run the loader:

```bash
docker compose up -d postgres api
python -m pip install -e '.[platform]'
python -m analysis.scripts.ingest_plateau_postgis
```

The loader emits three event types:

1. `FeatureStart`: creates/upserts the version-scoped city object and provenance.
2. `GeometryPart`: writes a completed ring/line immediately to PostGIS.
3. `FeatureEnd`: writes LOD, CRS, attributes, derived envelope/representative point and a typed
   domain row.

This event boundary is essential for DEM TIN: memory is tied to a coordinate ring rather than a
whole relief feature. A transaction is committed after each source member, and the ingestion run
retains progress and failure text.

## Normalization and semantics

- Buildings: usage, measured height, above/below-ground storeys, building/floor area where the
  attributes really exist.
- Roads: class, function, usage and name. Road surfaces are not called a pedestrian network.
- Terrain: relief city object plus streamed geometry parts. A terrain triangle is not a road
  slope measurement.
- Land use, urban planning and flood/tsunami/landslide themes: normalized only when present.
- All remaining simple leaf values are retained in JSONB. Missing values stay null; they are not
  inferred.

The source CRS URI remains in both object and geometry-part provenance. Maizuru GML coordinates
using EPSG:6697 are read in GML CRS axis order and written as longitude/latitude EPSG:4326 for GIS
queries. Metric calculations must use an explicit projected CRS.

The context builder adds package-local official codelist labels and exact EPSG:6674 relations.
Flood/tsunami rank uses the actual `rankOrg`; landslide uses `areaType`. The base loader does not
place a description code into a rank-label field and does not derive depth from geometry Z. See
[PLATEAU context](plateau-context.md).

After CityGML and the matching road graph are loaded, verified Parquet relations can be loaded with:

```bash
python -m analysis.scripts.load_plateau_context_postgis \
  --database-url "$CITYGAP_DATABASE_URL"
```

## Idempotence and incremental updates

The dataset key is `(city_id, dataset_year, archive_sha256)`. Re-running the same archive upserts
objects by `(dataset_version_id, gml_id)` and replaces their geometry parts. Another archive or
year receives another dataset version. Future added/removed/changed reports should compare
version-scoped `gml:id` plus normalized attribute/geometry hashes; no cross-year identity is
assumed when IDs change.

## Known database limitations

- The Python event parser and SQL migration are validated in this repository, but a full PostGIS
  load requires Docker/PostGIS and substantial storage. Do not claim DB size or query latency
  until that run is recorded.
- Geometry rings are stored as independent parts. Topological reconstruction/repair and compact
  bulk loading remain benchmark-driven improvements.
- Source-member CRC detects member changes inside the ZIP; archive SHA-256 is the authoritative
  package checksum.
