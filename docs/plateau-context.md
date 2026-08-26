# PLATEAU land-use, planning and hazard context

## What is implemented

The Maizuru 2025 CityGML package is streamed into one common LOD1 polygon model. Interior rings,
`gml:id`, source member, member CRC32, XML attribute paths, `codeSpace` and units are retained.
Labels come only from GML dictionaries in the same PLATEAU archive; no inferred land-use or risk
category is substituted.

| Theme | Top-level features | LOD1 source surface parts |
|---|---:|---:|
| LandUse | 31,067 | 31,067 |
| Urban planning | 394 | 394 |
| Sediment disaster prone area | 4,643 | 4,643 |
| River flood | 666 | 2,678,026 |
| Tsunami | 23 | 63,436 |

The urban-planning records comprise 13 actual feature types, including 163 `UseDistrict`, 87
`TrafficFacility`, 30 `OpenSpaceForPublicUse`, 19 `AreaClassification` and three
`UrbanPlanningArea` features. Missing planning attributes remain null.

Flood and tsunami geometry Z is not interpreted as inundation depth. The published context uses
the actual `uro:rankOrg` value and its official `RiverFloodingRiskAttribute_rankOrg.xml` or
`TsunamiRiskAttribute_rankOrg.xml` label. Landslide context uses the actual `urf:areaType` and
`LandSlideRiskAttribute_areaType.xml` label, with `disasterType` retained separately.

## Spatial relations

All exact relations are computed in JGD2011 / Japan Plane Rectangular CS VI (EPSG:6674):

- 28,448 unique strict-residential analysis buildings: point intersection with land use,
  planning and hazards;
- 495 census meshes: exact feature intersection area;
- 11,460 screened PLATEAU road-surface scenario anchors: point intersection;
- 23,437 experimental road-surface graph edges: exact hazard intersection length.

Every residential building receives a land-use and planning context. A hazard overlap was found
for 22,379 of those buildings, 489 meshes, 8,517 candidates and 19,227 road edges. These counts
mean overlap with one or more supplied source layers, not verified exposure of a resident and not
a policy decision.

The invariant is:

```text
hazard overlap -> additional_confirmation_required
hazard overlap != siting impossible
siting feasibility -> not_determined
```

Overlapping official hazard features are retained as separate relations. Therefore aggregate
relation areas or lengths are named feature-intersection sums and may double-count physical space.

## Reproduction and independent verification

```bash
python -m analysis.scripts.build_plateau_context --refresh
python -m analysis.scripts.verify_plateau_context
```

`--refresh` reparses the 914 MB source archive. The measured flood pass processed 2,678,026 faces
in 6m27s with about 205 MiB peak RSS. A complete first run also performs all spatial joins. Later
runs reuse versioned GeoParquet caches; the measured cached join run took 4m38s and about 770 MiB
peak RSS. These are WSL2 observations, not service-level guarantees.

The independent verifier reloads artifacts rather than invoking the production join helpers. It
checks inventory counts, ID uniqueness, geometry validity, official-label resolution, review
semantics and direct Shapely recomputation of 300 building relations, 300 road relations and all
21 planning/hazard relations in deep-dive mesh `533513314`. The recorded maximum length and area
residuals are both zero.

Compact, tracked evidence:

- `maizuru_plateau_context_summary.json`
- `maizuru_plateau_context_verification.json`
- `maizuru_mesh_plateau_context.csv`
- `maizuru_scenario_candidate_context.csv`
- `maizuru_road_hazard_summary.csv`

Detailed GeoParquet/Parquet feature and relation tables stay Git-ignored. They are canonical Python
outputs, not hidden synthetic data.

## PostGIS and API

Migration `004_spatial_context.sql` adds versioned context runs and building, mesh, candidate and
road relations. The loader requires matching current CityGML and road-graph versions, uses bulk
COPY, checks every inserted row count and only then marks the run `succeeded`:

```bash
python -m analysis.scripts.load_plateau_context_postgis \
  --database-url "$CITYGAP_DATABASE_URL"
```

This repository environment did not run PostGIS, so no database load time or DB query latency is
claimed. Available bounded contracts are:

- `GET /cities/{city_id}/context/{landuse|planning|hazards}?bbox=...`
- `GET /cities/{city_id}/meshes/{mesh_code}/context`
- `GET /cities/{city_id}/scenario-candidates/{candidate_id}/context`
- `GET /cities/{city_id}/road-edges/{edge_id}/hazards`
