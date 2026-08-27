# CITY GAP final submission checklist

## Product and evidence

- [x] Existing ranking, detail, layers, methodology, responsive/error states retained
- [x] 495 display meshes / 286 percentile comparison meshes / 218 Primary ranking meshes
- [x] Rank 1 shown as `二尾バス停周辺` with 61.5%, transport 2,322m, medical 3,317m
- [x] `plateau_covered_candidates.csv` contains the required Top 5 and schema
- [x] Whole-city Rank 1 and PLATEAU-covered candidates are explicitly separated
- [x] 3D Deep Dive uses overall rank 23 `常団地前バス停周辺`
- [x] Deep Dive mesh contains 296 verified official building representatives
- [x] Click UI shows only actual usage, height, storeys, footprint area, floor area, and LOD
- [x] UI states that CITY GAP is 500m-mesh-level, not building-level
- [x] Top 10 zero coverage is framed as an urban-data coverage finding, not criticism

## PLATEAU context

- [x] Official CityGML themes inventoried: building, road, DEM, land use, urban planning, place names, flood
- [x] 135 official road LOD1 surfaces rendered in the Deep Dive
- [x] Official DEM TIN elevation and local triangle-slope summary generated
- [x] Euclidean distance and unavailable network-aware distance clearly distinguished
- [x] No road-network or walking-route result fabricated from surface polygons
- [x] “Why PLATEAU” separates current implementation from future work

## What-if and Story

- [x] Primary 0m mesh-centroid demo removed
- [x] Three road-surface candidates evaluated and shown
- [x] Candidate source, 150m exclusion, 1.5km separation, and objective disclosed
- [x] Improved meshes, recorded elderly population, mean distance change, total Score C change shown
- [x] “Affected elderly population” is not described as users or beneficiaries
- [x] Presentation Mode has eight steps: discovery, Rank 1, robustness, 3D, 1-site, 2-site, fairness, Fujisawa
- [x] Rank 1 centroid scenario remains only as a diagnostic option

## Delivery and fallback

- [x] Runtime needs no external map, analysis, or PLATEAU API
- [x] Cesium assets, Natural Earth II, analysis data, road subset, and 3D Tiles are static
- [x] `docs/assets/demo-fallback/Step1.png` through `Step4.png` generated
- [x] `docs/assets/demo-fallback/WhatIf.png` generated
- [x] Demo script contains the offline fallback order
- [x] MIT `LICENSE` added for software; data licenses remain separate

## Verification before push

- [x] Python `pytest`
- [x] Python `ruff check .`
- [x] Frontend `npm ci`
- [x] Frontend lint
- [x] Frontend typecheck
- [x] Frontend Vitest
- [x] Production build
- [x] Desktop Story 1–5
- [x] PLATEAU b3dm load and building click
- [x] Candidate What-if exact values
- [x] Mobile 390px no overflow
- [x] Optional PLATEAU and WebGL fallback
- [x] Browser console errors = 0
- [x] GitHub Pages deployed
- [x] Git worktree clean

## Cross-city and UX final phase

- [x] Shared city configuration loader
- [x] `maizuru.yaml` / `fujisawa.yaml`
- [x] Fujisawa official e-Stat / P11 / P04 / PLATEAU related data
- [x] Fujisawa 327 mesh output and Top 10
- [x] Fujisawa Top 1 numeric sanity check
- [x] Fujisawa threshold stability: 10/10 overlap in all four conditions
- [x] No cross-city percentile score comparison
- [x] Maizuru remains default Primary demo
- [x] Fujisawa explicitly labeled Cross-city validation
- [x] Fujisawa hides Maizuru-only 3D / What-if
- [x] Light civic map-first visual system
- [x] Rank 1 initial detail hierarchy
- [x] What-if distance Before / After emphasis
- [x] Desktop 1440×900 screenshot review
- [x] Cross-city 1280×800 screenshot review
- [x] Mobile 390×844; no horizontal overflow
- [x] Final screenshots in `docs/assets/final/`
- [x] Optional PLATEAU fallback and WebGL fallback
- [x] Browser console errors = 0
- [x] Final focus-regression rerun
- [x] GitHub Pages final deployment
- [x] Published city switch and data response verification
- [x] Final commit and clean worktree

## Decision Studio final phase

- [x] 9 predefined robustness conditions; frequency is not framed as probability
- [x] Robust candidate ordering is deterministic and documented
- [x] 11,460 PLATEAU LOD1 road-surface candidates retain coordinates and source identity
- [x] 1-site exact within candidate pool
- [x] 2/3-site deterministic greedy approximation disclosed
- [x] Overall, fairness, and robust alternatives compare different objectives
- [x] 0→1→2→3 diminishing returns shown without ROI wording
- [x] Before / After map uses the same Score C scale
- [x] Selected mesh shows a restrained straight-line calculation correspondence
- [x] Evidence Chain exposes source, CRS, equation, raw value, and plan coordinates
- [x] Independent verifier recomputes all 9 plans and Evidence Chain
- [x] Python robustness/optimizer/evidence tests
- [x] Frontend Decision Studio tests including prohibited wording
- [x] Mobile styles added for Decision controls and Evidence modal
- [x] Final-v2 screenshots 01–10 regenerated
- [x] Production browser console errors = 0
- [x] GitHub Pages final deployment and asset response verification

## Municipal Digital Twin Platform final phase

- [x] PLATEAU 8 themes / 97,140 features and all official context counts re-audited
- [x] 28,448 network-analysis buildings; 15,684 nodes / 23,437 edges; pedestrian claim prohibited
- [x] Terrain ascent/descent/grade remains a separate observed route component
- [x] 30 network scenarios independently verified across six objectives and 1–5 sites
- [x] Seven canonical scenario tables, review lifecycle and field-check contracts
- [x] Two-city/version/capability registry; unavailable capability is never substituted
- [x] CityGML, GTFS, CSV, GeoJSON and GeoPackage bounded adapters
- [x] DTD/entity rejection, archive traversal/size checks and vector input validation
- [x] GTFS-ready schema without a fabricated feed or P11 conversion
- [x] Bounded bbox API, job stages and JSON/CSV/HTML Evidence export
- [x] Municipal Workspace A/B/C, max-three comparison and manual review lifecycle
- [x] Privacy-safe 7,684 affected-building points with no per-building person values
- [x] Browser audit script: A points rendered, C selectable, privacy visible, console/errors zero
- [x] Machine audit: all 18 tracked real-artifact and contract checks pass
- [x] PostGIS execution remains explicitly false in all manifests
- [ ] Approved PostGIS environment, authentication/RBAC and durable worker deployed
- [ ] Real municipal GTFS, validated pedestrian network and field review acquired

## Urban Futures & Resilience final phase

- [x] Urban state model binds effective date and exact dataset/network/analysis versions
- [x] Lifecycle and quality gates prevent unverified current/future/stress/outcome states
- [x] PLATEAU diff classifies added/removed/geometry/attribute/unchanged conservatively
- [x] Dependency graph chooses bounded recompute scope and falls back to full rebuild
- [x] Incremental result is compared with full rebuild on independent small fixtures
- [x] IPSS and Fujisawa official future population series are hash-verified; no fake projection
- [x] Future accessibility is explicitly fixed-service scenario + CITY GAP allocation
- [x] Edge/group/area disruption and user-only service change contracts
- [x] Flood, landslide and tsunami stress tests use explicit counterfactual assumptions
- [x] Reachability, distance increase, elderly disconnect and fragmentation metrics
- [x] Iterative `O(V+E)` Tarjan criticality; no edges × citywide-Dijkstra brute force
- [x] Selected critical candidates independently edge-removal verified
- [x] Primary/second route review preserves experimental non-pedestrian boundary
- [x] Official Maizuru/Fujisawa shelters loaded without inferred capacity
- [x] Shelter result is network reachability, not evacuation/crowd simulation
- [x] Planning comparison uses review-candidate labels and never legal claims
- [x] Municipal target and external cost adapters never invent target/cost values
- [x] Multi-year portfolio, implementation records and non-causal outcome comparison
- [x] Selected-site PWA cache, IndexedDB queue, timezone/version/actor field records
- [x] HTTP 409 explicit resolution; silent last-write-wins prohibited
- [x] Temporal/resilience API, bbox/pagination, jobs, RBAC, audit and provenance
- [x] Evidence V3 deterministic JSON/CSV/print HTML and annual report model
- [x] Capability registry has 34 evidence-backed city-capability records
- [x] Maizuru and Fujisawa run through the same temporal/resilience core
- [x] Six real-data Maizuru golden cases and selected independent verification
- [x] 100k / 250k / 500k synthetic scale fixtures clearly separated from real data
- [x] Public workspace is aggregated and excludes building-level estimated demographics
- [x] Production build and browser audit: seven futures checks including aggregated map geometry, existing workspace, zero console errors
- [x] Final PostGIS integration workflow passed for migrations 011–013 — CI run `33066544364`
- [x] Final GitHub Actions suite passed and GitHub Pages deployment verified — Pages run `33066544350`
- [ ] Municipality-approved full DB load, OIDC, network/shelter snap and field/outcome review
