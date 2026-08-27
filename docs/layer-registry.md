# Layer Registry

The registry contains 26 renderer-neutral layers and seven task presets. Every layer declares `id`, human name, group, source kind/URL/fallback, year, PLATEAU theme, per-city availability, default visibility, zoom range, opacity, legend, attribution, render mode, exclusive group, and evidence link.

## Groups

| Group | Purpose |
|---|---|
| Analysis | CITY GAP, population, transport, medical |
| PLATEAU | buildings, roads, DEM, land use, planning, flood, landslide, tsunami |
| Infrastructure | stations, bus stops, medical facilities |
| Planning | planning context |
| Hazard | composite resilience context |
| Scenario | footprint, sites, routes |
| Validation | primary/reference routes, disagreement, temporal change |
| Reference | GSI basemap and OSM network |

Only one `primary-thematic` layer may be active. Context layers can coexist at restrained opacity. Unavailable layers are disabled, not hidden; this makes city coverage legible.

## Presets

The seven presets are 課題を探す, PLATEAU詳細, 交通を見る, 医療を見る, 災害を見る, Scenario比較, and Validation比較. Each preset chooses one primary layer and a small set of context layers. The advanced catalogue remains available for expert review but is not required for the primary tasks.

The former combined “PLATEAU 3D・道路” toggle is removed. Buildings, roads, terrain, land use, urban planning, flood, landslide, and tsunami are individually represented, with availability and evidence metadata.
