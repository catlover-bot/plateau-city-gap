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
- [ ] GitHub Pages deployed
- [ ] Git worktree clean

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
- [ ] GitHub Pages final deployment
- [ ] Published city switch and data response verification
- [ ] Final commit and clean worktree

## Decision Studio final phase

- [x] 9 predefined robustness conditions; frequency is not framed as probability
- [x] Robust candidate ordering is deterministic and documented
- [x] 12,062 PLATEAU road-surface candidates retain coordinates and source identity
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
- [ ] GitHub Pages final deployment and asset response verification
