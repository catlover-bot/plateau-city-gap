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
- [x] Story has five steps: mode comparison, Rank 1, 3D Deep Dive, realistic candidate, decision entry
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
- [ ] GitHub Pages deployed
- [ ] Git worktree clean
