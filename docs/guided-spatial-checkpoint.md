# Guided spatial storytelling automated checkpoint

Goal: `guided-spatial-storytelling-v1`

This checkpoint evaluates implementation and comprehension support. It is not a human-comprehension or municipal-workflow result.

## Outcome

The Guided demo now uses one persistent MapLibre workspace for intro plus three spatial scenes:

```text
地域を見つける
  -> PLATEAUで街の形まで見る
  -> データだけでは分からない場所を現地確認する
```

The core is the selected Area's PLATEAU building, road, terrain and planning context. The Urban Section is an optional verified visualization owned only by Area `533513314`; it is not reused for Areas that do not own it.

## Repository boundary

- Source: `feat/public-product-language-section-v1` at `356dd90d49e7d736553de7596bb9cee619d1b692`
- Baseline: `origin/main` at `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- Execution: `feat/guided-spatial-storytelling-v1`
- Main merge: not performed
- Pages deployment: not performed
- Push / remote CI: not performed without separate authorization

## Before / after

| Dimension | Before | After |
|---|---|---|
| Core navigation | Six page-like guide states in production; four clamped steps in source | Intro + three internal scenes in one workspace |
| Map lifecycle | Guided PLATEAU step could replace the 2D map with a separate surface | One MapLibre instance persists; layers and camera change |
| Candidate link | Selected mesh could fall back to the first candidate | One Area identity drives row, polygon, label, camera and loaded context |
| PLATEAU scene | Small section; production plot about 162 px | 340 px plot at 1440 × 900; 260 px at 1280 × 720; 310 px mobile section surface |
| Map/section relation | Section appeared as a separate chart | Exact verified A–B LineString appears on the map and uses the same direction in the section |
| Verification | 28 generated checks in production Guide 4 | Target-specific 3–5 unknown urban states; no capture UI |
| Field/review | Large form and internal review states in Guide 5/6 | Moved out of the Guided core; legacy links map to Advanced |
| Cards / process chrome | Repeated bordered cards and numbered progress | Spatial stage 72%, restrained context panel 28%, no numbered progress |

The superseded production before-images remain recoverable from Git history. The retained after evidence and hashes are in `assets/guided-spatial-checkpoint/manifest.json`.

## Data and provenance gates

- Initial catalog: 495 Maizuru 500 m Areas; Area detail request count at intro is zero.
- CityGML: pinned Maizuru 2025 archive SHA-256 `13f4020ade066dc7139b7653c47a55a09af0093dee743f6b9cca5d3177a71cff`.
- Tsune Area: 303 intersecting building footprints, 135 road surfaces and eight planning shapes.
- Verified section: pack `maizuru-533513314-plateau-2025-v1`; A `[135.398125, 35.44583333333334]`; B `[135.398125, 35.45]`; 94 terrain samples; 17 direct buildings; 14 road intersections.
- The default exact road target is `tran_05dbefba-6a77-40ea-88ac-a568a63a2f05:0`; the public UI labels it 京月中央通線 and does not expose the ID initially.
- Switch sequence includes Tsune, Nio, Akano, `533502752`, `533512264`, and `533512362`. Geometry, label, counts, capabilities, target resolution and context signatures change without remounting the map.
- Non-owning Areas show no section. They use an explicit Area fallback rather than stale Tsune objects.
- A registered facility target is verified separately as a source point. No facility-only 3D control is shown.

## Automated layout and accessibility

| State | Viewport | Map/panel | Visible controls | Bordered surfaces | Horizontal overflow | Small controls |
|---|---:|---:|---:|---:|---:|---:|
| Intro | 1440 × 900 | 72 / 28 | 6 | 0 | 0 | 0 |
| Find | 1440 × 900 | 72 / 28 | 10 | 1 | 0 | 0 |
| Understand | 1440 × 900 | 72 / 28 | 7 | 3 | 0 | 0 |
| Understand | 1280 × 720 | 72 / 28 | 7 | 3 | 0 | 0 |
| Verify | 390 × 844 | stacked | 8 | 3 | 0 | 0 |

Automated checks found one visible `h1`, no unnamed actionable controls, no duplicate IDs, no horizontal overflow, and visible focus for the tested keyboard sequence. The mobile map/section switch preserves a full-width 310 px section plot. A real assistive-technology review remains outstanding.

## Spatial interaction evidence

- Intro -> Find reveals shortlist layers on the already mounted map.
- Row hover/focus and map feature hover share one highlighted Area state.
- Candidate selection changes the camera and strongest Area styling.
- Find -> Understand changes camera, Area detail layers, optional A–B line and section.
- Section pointer/keyboard position changes the focus point on the same A–B line.
- Understand -> Verify moves the camera to the exact target and emphasizes its geometry.
- Selecting road, building or facility changes both target geometry and 3–5 checks.

## Screenshots

- Desktop intro: `assets/guided-spatial-checkpoint/desktop-intro.png`
- Scene 1: `assets/guided-spatial-checkpoint/desktop-find-tsune.png`
- Hero Scene 2: `assets/guided-spatial-checkpoint/desktop-understand-533513314.png`
- DPR 2 Hero: `assets/guided-spatial-checkpoint/dpr2-understand-section.png`
- Exact road/building: `assets/guided-spatial-checkpoint/desktop-verify-533513314.png`, `desktop-verify-building.png`
- Facility point: `assets/guided-spatial-checkpoint/desktop-verify-facility.png`
- Mobile map/section/verify: `mobile-understand-map.png`, `mobile-understand-section.png`, `mobile-verify.png`

## Performance

The authoritative production-preview profile is `../analysis/outputs/real/guided-spatial-performance.json`. It records five fresh browser contexts at 1440 × 900, DPR 1 and reduced motion.

| Measurement | Samples (ms) | Median | Gate | Result |
|---|---|---:|---:|---|
| First meaningful render | 4662.4, 851.3, 820.0, 700.9, 1063.7 | 851.3 ms | ≤ 2000 ms | pass |
| Selected Area context, cold | 3416.3, 1835.6, 1395.6, 1570.6, 1877.4 | 1835.6 ms | reported | measured |
| Exact road target, warm | 1743.4, 1047.9, 1364.6, 1778.8, 1467.5 | 1467.5 ms | ≤ 1800 ms | pass |
| Exact building target, warm | 668.4, 524.4, 552.2, 556.2, 622.6 | 556.2 ms | ≤ 2500 ms | pass |
| Return to Scene 2, warm | 760.2, 794.0, 741.7, 1053.5, 994.9 | 794.0 ms | ≤ 2000 ms | pass |

The 4662.4 ms first sample and 3416.3 ms cold Area sample remain visible in the evidence; the median gates do not erase cold WebGL and machine variance. Screenshot-manifest `first_ready_ms` includes full map readiness and is diagnostic only, not the production FMR claim.

## Compatibility and route regression

- Legacy `?guide=1` and `?guide=2` resolve to Guided Find.
- Legacy `?guide=3` resolves to Guided Understand; `?guide=4` resolves to Guided Verify.
- Legacy `?guide=5` and `?guide=6` continue to Advanced field-sheet and municipal-review respectively.
- Public root continues to the existing Public Area experience.
- All route cases completed with no captured product error. Their canonical final URLs are recorded in the manifest.

## Local verification

- Production build: passed in `1m 33s`.
- ESLint: passed.
- TypeScript project typecheck: passed.
- Vitest: 26 files, 110 tests passed.
- Full Python suite: 417 tests passed; one existing Starlette deprecation warning.
- Ruff: passed.
- Guided context generator tests: three passed; deterministic `--check` also passed for all 495 Areas.
- Documentation links: all 92 Markdown files passed.
- Browser checkpoint: desktop, compact, DPR 2 and 390 × 844 paths passed; one primary action was visible in each actionable state.
- Dependency audits: npm reported zero vulnerabilities; pip-audit reported no known vulnerabilities and skipped the editable local package.
- `git diff --check`: passed.
- Remote CI: not run because push was not authorized for this goal.

## Claim boundary and remaining risk

- The section is display-only and does not prove walking access, building use, risk, or a relationship to the current target.
- Scene 3 asks about unknown urban states; photo, GPS and evidence capture remain in Advanced/HOLD scope.
- A 495-Area selector proves scope but may still be too broad for first-time users.
- The dense Tsune section legend and small-object detail need real-person and assistive-technology observation.
- Software WebGL and first cold load remain machine-dependent.
- The five-sample profile contains a 4662.4 ms FMR outlier and a 3416.3 ms cold Area-context outlier despite passing medians.
- Existing specialist viewers remain integration candidates, not products to reproduce.
- No human test or municipal workflow review has been conducted in this goal.
- Remote CI was not run because push was not authorized; this is a local automated checkpoint.

## Status

```text
AUTOMATED_GUIDED_CHECKPOINT_COMPLETE
READY_FOR_HUMAN_TEST
AWAITING_HUMAN_TEST
AWAITING_MUNICIPAL_WORKFLOW_REVIEW
HOLD_MAIN_PROMOTION
HOLD_PAGES_DEPLOY
HOLD_P1_M4_M6
```

This status does not assert `GUIDED_UX_PASS`, `HUMAN_COMPREHENSION_PASS`, or `VISUAL_QUALITY_PASS`.
