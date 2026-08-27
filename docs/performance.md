# Performance and spatial delivery

No production SLA is claimed. Measurements are labelled either `REAL_MUNICIPAL_DATA` (offline pipeline timings from Maizuru/Fujisawa) or `SYNTHETIC_SCALE` (database/API scale fixture).

`python -m analysis.scripts.benchmark_pilot_api --output pilot-performance.json` creates 100,000 synthetic buildings and 100,000 synthetic road edges in migrated PostGIS, takes 30 samples (10 for uncached MVT), reports p50/p95/max, then removes the fixture. It measures `/cities`, bounded buildings, mesh detail, scenario detail, A/B/C comparison, route detail, cached tile and uncached tile. CI publishes the JSON as the `pilot-performance` artifact.

The 2026-08-27 GitHub Actions Linux run (`33055835395`, Python 3.12.14) produced the following database/API timings. These are synthetic-scale CI measurements, not Maizuru/Fujisawa API timings and not an SLA.

| Operation | p50 ms | p95 ms | Samples |
|---|---:|---:|---:|
| cities | 10.647 | 11.113 | 30 |
| bbox buildings (up to 1,000 records) | 61.694 | 63.532 | 30 |
| mesh detail | 12.587 | 12.919 | 30 |
| scenario detail | 24.902 | 25.683 | 30 |
| A/B/C comparison | 68.387 | 70.594 | 30 |
| route detail | 12.329 | 12.772 | 30 |
| cached building MVT | 2.559 | 3.357 | 30 |
| uncached 50k-feature building MVT | 803.776 | 842.642 | 10 |

The immutable cache reduced median tile response from about 804 ms to 2.6 ms in this fixture. The exact machine metadata, maxima and real offline pipeline timings are tracked in `analysis/outputs/real/pilot_performance.json`.

The municipal API retains bounded GeoJSON endpoints for record inspection and adds version-explicit MVT for `buildings`, `road_edges`, `hazards`, and `scenario_impacts`. Tile requests require city, immutable dataset version and z/x/y; network/scenario layers additionally require their exact versions and algorithm. A bounded in-process LRU cache uses all of those values as its key and returns ETag/304 plus private immutable cache headers. Detailed tiles require authenticated `platform:read` and are not copied to GitHub Pages.

Cesium 3D Tiles remains the building-volume delivery path. The public competition demo continues to use privacy-reviewed aggregates. Production municipal map clients should request only visible tiles/zoom levels instead of downloading whole-city building, edge or impact GeoJSON.

Real pipeline timings and peak memory are stored in each `*_summary.json`. API timings are synthetic until a pilot database containing a municipally approved full load is benchmarked; they must not be relabelled as Maizuru/Fujisawa API results.
