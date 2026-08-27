# Multi-city validation

CITY GAP processed Maizuru and Fujisawa through the same five PLATEAU-native stages: inventory, building-demographic allocation, building-origin network accessibility, DEM enrichment, and planning/hazard context joins. This is a processing proof, not a claim that the two cities' scores are directly comparable.

| Actual 2025 PLATEAU input/result | Maizuru | Fujisawa |
|---|---:|---:|
| Archive SHA-256 | `13f4020…a71cff` | `7e85ff8…415ea` |
| Archive / expanded size | 914 MB / 12.26 GB | 736 MB / 6.66 GB |
| CityGML files | 369 | 416 |
| Unique top-level features | 97,140 | 399,271 |
| Buildings (LOD1 / LOD2) | 44,640 / 1,504 | 169,856 / 1,434 |
| Transportation features | 15,684 | 53,658 |
| DEM features | 23 | 8 |
| Land-use features | 31,067 | 110,898 |
| Urban-planning features | 394 | 1,537 |
| Hazard features | 5,332 | 63,309 |
| Strict residential buildings | 29,674 | 107,573 |
| Experimental graph nodes / edges | 15,684 / 23,437 | 53,658 / 71,487 |
| Road nodes with terrain | 15,504 / 15,684 | 53,467 / 53,658 |
| Analysis CRS | EPSG:6674 | EPSG:6677 |

The shared-stage processing rate is 5/5 (100%) for both cities. Differences are confined to city YAML, source archive, analysis CRS, package codelists and declared capabilities. The core source contains a regression test rejecting `if/elif/match/case` branches on `maizuru` or `26202`.

Actual Fujisawa runtime on this WSL host was 433.865 s inventory, 293.074 s building allocation, 77.479 s network, 522.011 s terrain, and 1,116.126 s context. Peak stage RSS was about 2.4 GiB during context processing. The tracked summaries and registry retain source checksums, algorithms and exact counts; detailed Parquet remains excluded from Git/public assets.

City-specific exceptions are explicit. Fujisawa scenario optimization is `unavailable`, because no Fujisawa scenario set was generated or reviewed. Fujisawa GTFS is `unavailable`, because no stable official public feed was verified. Both road graphs remain `partial` experimental LOD1 surface adjacency and are not pedestrian networks. These unavailable/partial capabilities are never filled with Maizuru results.

The proof is enforced by `backend/tests/test_multicity_platform.py`. It loads both real audit chains, validates their shared schemas and cross-stage version linkage, checks city configuration CRS, and validates the capability matrix.
