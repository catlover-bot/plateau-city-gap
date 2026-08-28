# Platform benchmark

## Priority 1 measurements

The source-archive inventory is measured on the Maizuru 2025 package by
`python -m analysis.scripts.build_plateau_inventory`. The JSON output is the machine-readable
source of truth. Hardware/virtualization affect elapsed time and RSS, so every comparison should
record environment and commit.

| Measurement | Result | Status |
|---|---:|---|
| Source ZIP | 914,222,089 bytes | measured |
| Uncompressed ZIP members | 12,257,307,956 bytes | measured |
| ZIP members | 691 | measured |
| CityGML members / themes | 369 / 8 | measured |
| Top-level features / unique `gml:id` | 97,140 / 97,140 | measured |
| Duplicate top-level `gml:id` | 0 | measured |
| CityGML inventory time | 586.968 s | measured full run |
| Peak inventory RSS | 281,372 KiB (274.8 MiB) | measured full run |
| PostGIS DB size | not measured | Docker/PostGIS run required |
| Building point query latency | not measured | populated DB required |
| bbox query latency | not measured | populated DB required |
| Network routing latency | not applicable | Priority 3–4 |
| Scenario execution time | existing static-engine evidence only | DB engine not implemented |

The full run was executed in WSL2 with Python 3.12. Elapsed time is dominated by the 10.46 GB
uncompressed DEM theme (501.774 s). The exact per-member and per-theme timings remain in
`maizuru_plateau_inventory.json`.

## Method

- Do not extract the ZIP; inventory every `udx/*/*.gml` member once.
- Use process peak RSS from Linux `getrusage`; distinguish it from current RSS.
- Measure database size with `pg_database_size` after `VACUUM (ANALYZE)` and record PostGIS/image
  versions.
- Warm and cold query latency must be reported separately, with bbox, result count, repetitions,
  median and p95.
- Routing measurements require graph size, connected-component coverage and origin/destination
  sampling rules.
- A benchmark is evidence, not an SLA. The design targets in architecture documentation must not
  be relabelled as measured capacity.

## Spatial delivery and concurrency protocol

`python -m analysis.scripts.benchmark_pilot_api` reports cold and warm vector-tile
measurements separately. The in-process cache key includes the exact dataset version and,
when supplied, the Urban State ID in addition to network/scenario/algorithm versions and
tile coordinates. Responses are private and immutable and expose the pinned version in
headers.

The same report executes bounded request bursts at concurrency 1, 10, 25 and 50 for a
bbox query and a warm vector tile. It reports request count, p50, p95, maximum latency and
observed throughput. Those database/API rows are explicitly `SYNTHETIC_SCALE`; the report
sets `concurrency_result_is_sla` and `production_sla_claimed` to false. Maizuru and
Fujisawa ingestion/runtime/RSS entries are loaded separately from checked-in real-pipeline
artifacts and must never be merged with the synthetic workload classification.
