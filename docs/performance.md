# Performance and spatial delivery

No production SLA is claimed. Measurements are labelled either `REAL_MUNICIPAL_DATA` (offline pipeline timings from Maizuru/Fujisawa) or `SYNTHETIC_SCALE` (database/API scale fixture).

`python -m analysis.scripts.benchmark_pilot_api --output pilot-performance.json` creates 100,000 synthetic buildings and 100,000 synthetic road edges in migrated PostGIS, takes 30 samples (10 for cold MVT and municipal home views), reports p50/p95/max, then removes the fixture. It measures `/cities`, bounded buildings, mesh detail, scenario detail, A/B/C comparison, route detail, City Home, Data Hub, and cold/warm tiles. CI publishes the JSON as the `pilot-performance` artifact.

The 2026-08-29 GitHub Actions Linux run (`33185736512`, Python 3.12.14) produced the following database/API timings. These are synthetic-scale CI measurements, not Maizuru/Fujisawa API timings and not an SLA.

| Operation | p50 ms | p95 ms | Samples |
|---|---:|---:|---:|
| cities | 10.257 | 10.770 | 30 |
| bbox buildings (up to 1,000 records) | 61.436 | 63.439 | 30 |
| mesh detail | 12.219 | 15.987 | 30 |
| scenario detail | 22.711 | 24.548 | 30 |
| A/B/C comparison | 61.186 | 63.477 | 30 |
| route detail | 11.841 | 12.882 | 30 |
| City Home | 18.688 | 19.181 | 10 |
| Data Hub | 96.093 | 113.280 | 10 |
| warm building MVT | 3.145 | 4.038 | 30 |
| cold 50k-feature building MVT | 803.901 | 828.663 | 10 |

The immutable cache reduced median tile response from about 804 ms to 3.1 ms in this fixture. The exact machine metadata, maxima and real offline pipeline timings are tracked in `analysis/outputs/real/pilot_performance.json`.

The same run executed bounded bursts at concurrency 1, 10, 25 and 50. At concurrency 50,
bbox p95 was 1,974.314 ms at 31.458 requests/s; warm-tile p95 was 156.260 ms at
224.897 requests/s. These short synthetic bursts characterize this CI runner only and are explicitly
marked `concurrency_result_is_sla=false`.

The municipal API retains bounded GeoJSON endpoints for record inspection and adds version-explicit MVT for `buildings`, `road_edges`, `hazards`, and `scenario_impacts`. Tile requests require city, immutable dataset version and z/x/y; network/scenario layers additionally require their exact versions and algorithm. A bounded in-process LRU cache uses all of those values as its key and returns ETag/304 plus private immutable cache headers. Detailed tiles require authenticated `platform:read` and are not copied to GitHub Pages.

Cesium 3D Tiles remains the building-volume delivery path. The public competition demo continues to use privacy-reviewed aggregates. Production municipal map clients should request only visible tiles/zoom levels instead of downloading whole-city building, edge or impact GeoJSON.

Real pipeline timings and peak memory are stored in each `*_summary.json`. API timings are synthetic until a pilot database containing a municipally approved full load is benchmarked; they must not be relabelled as Maizuru/Fujisawa API results.

## Urban resilience algorithms

The real-data validation executes state identity diff, explicit hazard disruption, multi-source
service reachability, iterative Tarjan bridge criticality, selected-pair redundancy and planning
comparison. The latest tracked combined run completed in 27.672 seconds with peak RSS 978.3 MiB.
This combined peak covers both cities in one process and is not an API SLA.

| Real graph | nodes | edges | demand buildings | identity diff | criticality |
|---|---:|---:|---:|---:|---:|
| Maizuru | 15,684 | 23,437 | 28,448 | 1.152 s | 0.422 s |
| Fujisawa | 53,658 | 71,487 | 107,557 | 3.143 s | 1.116 s |

The identity diff is a correctness check against the same official version, not an annual-change
claim. Hazard runtimes and RSS are recorded per scenario in
`analysis/outputs/real/urban_futures_validation.json`.

The synthetic algorithm fixture is a ring with one demand record per node. It isolates scaling
behaviour and is never mixed with real-city results:

| synthetic nodes/edges/buildings | stress + criticality | peak RSS |
|---:|---:|---:|
| 100,000 | 2.145 s | 186.9 MiB |
| 250,000 | 7.839 s | 429.3 MiB |
| 500,000 | 13.783 s | 850.2 MiB |

Criticality uses `O(V+E)` bridge analysis rather than removing each edge and rerunning full-city
Dijkstra. Selected real candidates are independently verified by actual edge removal. Multi-source
Dijkstra is rerun once per service category and disruption state. Immutable graph indices and
result cache keys include city, urban state, network version, assumption hash and algorithm version.
