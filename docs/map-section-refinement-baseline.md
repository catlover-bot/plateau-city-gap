# Map and Urban Section refinement baseline

Status: `M0_BASELINE_LOCKED`

This checkpoint fixes the comparison protocol for the map-readability, spatial-product UI, and Urban Section annotation refinement. It is evidence for automated comparison; it is not a human visual-quality result.

## Execution lock

- branch: `feat/guided-spatial-storytelling-v1`
- source and starting HEAD: `8701df282da1b60049e9806e6b13f4ddceeecadc`
- remote feature HEAD at start: `8701df282da1b60049e9806e6b13f4ddceeecadc`
- `origin/main` at start: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- starting worktree: clean
- comparison environment: production build and production preview
- capture runtime: Playwright Chromium 149, reduced motion, fonts ready, four compositor frames
- prohibited operations retained: no reset, clean, rebase, squash, force push, main merge, or discarded work

## Evidence set

The versioned `before` package is in `docs/assets/map-section-refinement-v1/before/`.

- 17 PNG captures cover Public landing, Guided intro, Scene 1, Scene 2 map and Section, exact road, exact building, another Area, fallback Area, mobile scenes, `1280 × 720`, `1920 × 1080`, and DPR 2.
- `manifest.json` records URL, viewport, DPR, SHA-256, map/panel shares, Section height, visible annotations, collisions, overflow, map initialization count, render readiness, and target resolution.
- `performance.json` records five fresh browser contexts under the existing Guided performance protocol.
- capture diagnostics: zero product-error records
- persistent MapLibre initialization: one in every measured state
- desktop map/panel ratio: `73 / 27` at `1440 × 900` and `1920 × 1080`; `71.9 / 28.1` at `1280 × 720`
- horizontal overflow: zero in every measured state

## Baseline visual inventory

### Map

- GSI raster opacity is fixed at `0.78`; saturation and contrast are fixed rather than scene-tuned.
- Scene 1 shortlist fill is visually stronger than the selected-Area treatment, while place names and contour context compete with the small Area labels.
- Scene 2 uses several saturated building categories and active road/planning colors at once. The verified A–B line is present, but endpoint and direction hierarchy is limited.
- Scene 3 uses an exact target fill/line, but its surrounding context remains comparatively strong and the exact target name is not labeled on the map.
- Map labels are mostly `9–12 px`, below the intended `12–14 px` product hierarchy.
- Exact road, exact building, and honest Area fallback behavior are all present and are preservation gates.

### Urban Section

- source facts in the default verified Section: 63 building services, 14 direct road intersections, 94 terrain samples, A–B distance `462.257 m`, and elevation range `65.47–98.27 m`.
- named road inventory contains duplicates for 椿川通線 and 京月西通線; road names appear only in SVG titles, not as readable plot annotations.
- six service annotations are rendered at the right edge. In the baseline audit, five overlap and all six extend outside the Section plot bounds.
- Section height is `323 px` at desktop, `253 px` at `1280 × 720`, and `303.1875 px` in the mobile Section state.
- A/B labels are readable, but axis labels and ticks are `8–9 px`, the distance unit is repeated on every tick, and the mobile service stack clips at the right edge.
- annotation calculation time, hidden-low-priority count, and selected-annotation visibility are not instrumented in the baseline implementation.
- the compact pointer calculation uses the desktop view width and is a known interaction defect to correct without changing source geometry.

## Performance baseline

Five-context medians:

| Measurement | Median | Gate | Result |
| --- | ---: | ---: | --- |
| first meaningful render | `331.5 ms` | `≤ 2000 ms` | pass |
| Area context cold | `435.4 ms` | diagnostic | recorded |
| exact road warm | `330.8 ms` | `≤ 1800 ms` | pass |
| exact building warm | `257.4 ms` | `≤ 2500 ms` | pass |
| building story warm | `252.2 ms` | `≤ 2000 ms` | pass |

The browser reports blocked Inspector resources during profiling. These are extension/devtools requests and are retained in the raw console log; the measured product states reached their readiness gates.

## Refinement acceptance boundary

The `after` evidence must use the same capture script and state matrix. It must preserve one persistent map, canonical selected Area, 495-Area switching, lazy contexts, exact PLATEAU building/road geometry, registered-position facility target, honest fallback, verified A–B geometry and provenance, target-specific checks, Guided-to-Advanced full-data upgrade behavior, timeouts/errors/retry, legacy URLs, access modes, accessibility, and current claim boundaries.

The intended changes are presentation and interaction only: scene-aware visual hierarchy, quieter context, stronger selection and target emphasis, inspector polish, collision-aware Section annotations, accessible Section focus, and responsive plot sizing. No new dataset, metric, score, ranking, analysis, inferred use, walking/isochrone meaning, hazard/borehole feature, 3D capability, backend, database, or migration is authorized.

## Demo-video status

The existing captioned, clean, and 15-second demo videos are preserved unchanged. They document the earlier deployed source commit `33466bd97a20d96fafa7cf2906a1e89676e7da07` and become visually stale after this refinement. Recapture is deferred until production visual approval.
