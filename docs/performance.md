# Performance and spatial delivery

No production SLA is claimed. Measurements are labelled either `REAL_MUNICIPAL_DATA` (offline pipeline timings from Maizuru/Fujisawa) or `SYNTHETIC_SCALE` (database/API scale fixture).

`python -m analysis.scripts.benchmark_pilot_api --output pilot-performance.json` creates 100,000 synthetic buildings and 100,000 synthetic road edges in migrated PostGIS, takes 30 samples (10 for uncached MVT), reports p50/p95/max, then removes the fixture. It measures `/cities`, bounded buildings, mesh detail, scenario detail, A/B/C comparison, route detail, cached tile and uncached tile. CI publishes the JSON as the `pilot-performance` artifact.

The municipal API retains bounded GeoJSON endpoints for record inspection and adds version-explicit MVT for `buildings`, `road_edges`, `hazards`, and `scenario_impacts`. Tile requests require city, immutable dataset version and z/x/y; network/scenario layers additionally require their exact versions and algorithm. A bounded in-process LRU cache uses all of those values as its key and returns ETag/304 plus private immutable cache headers. Detailed tiles require authenticated `platform:read` and are not copied to GitHub Pages.

Cesium 3D Tiles remains the building-volume delivery path. The public competition demo continues to use privacy-reviewed aggregates. Production municipal map clients should request only visible tiles/zoom levels instead of downloading whole-city building, edge or impact GeoJSON.

Real pipeline timings and peak memory are stored in each `*_summary.json`. API timings are synthetic until a pilot database containing a municipally approved full load is benchmarked; they must not be relabelled as Maizuru/Fujisawa API results.
