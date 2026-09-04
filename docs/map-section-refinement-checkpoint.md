# Map, UI, and Urban Section refinement checkpoint

Status: `M4_AUTOMATED_CHECKPOINT_RECORDED`

This checkpoint compares the same production-preview state matrix before and after the presentation-only refinement. It reports observable implementation and automated checks, not human visual quality.

## Source and protocol

- branch: `feat/guided-spatial-storytelling-v1`
- starting source: `8701df282da1b60049e9806e6b13f4ddceeecadc`
- refined implementation: `5172427a2dffcf2fff751a3db633592c6f239943`
- comparison package: `docs/assets/map-section-refinement-v1/manifest.json`
- evidence: 17 before and 17 after captures at matching URLs, viewports, DPR, reduced motion, font readiness, and production-build readiness gates
- browser diagnostics: zero in both capture sets
- persistent MapLibre initialization count: one in every captured state
- horizontal overflow: zero in every captured state

## Map and product UI result

The automated map-hierarchy audit records the active MapLibre layer state and styling in every capture.

- Scene 1 keeps candidate context while giving the selected Area its own fill, white halo, stronger outline, and `14 px` label. The basemap opacity is `0.61`.
- Scene 2 exposes the real PLATEAU buildings and roads in neutral context styling and the verified A–B line at `3.8 px`. The basemap opacity is `0.54`.
- Scene 3 reduces context, retains the selected Area, and exposes the exact target fill, white halo, `4.5 px` outline, point, and `13 px` map label. The basemap opacity is `0.46`.
- The fallback capture keeps an Area-range outline but does not expose the exact-target halo or label.
- The inspector now uses one heading hierarchy, semantic known-fact and target summaries, restrained status treatment, and a legend whose symbols match the active scene.

These assertions verify implemented hierarchy and state separation. Whether the result is aesthetically successful remains a user decision on the deployed product.

## Urban Section before and after

| Measurement | Before | After |
| --- | ---: | ---: |
| desktop static annotations including A/B | 6 | 6 |
| mobile static annotations including A/B | 6 | 4 |
| visible named roads, desktop | 0 | 4 |
| visible named roads, mobile | 0 | 2 |
| measured label overlaps | 5 | 0 |
| labels outside the plot | 6 | 0 |
| endpoint conflicts | 0 | 0 |
| axis-tick conflicts | not instrumented | 0 |
| Section height, `1440 × 900` | `323 px` | `361.47 px` |
| Section height, `1280 × 720` | `253 px` | `300 px` |
| Section height, `390 × 844` | `303.19 px` | `303.19 px` |

The Section now deduplicates named roads, distributes them over A–B, measures text with Canvas, and places labels on two bounded rails with a deterministic minimum gap. It renders four road names on desktop and two on mobile, hiding six and eight lower-priority labels respectively. The maximum measured calculation time in the versioned captures is `12.9 ms`, below the `16 ms` target and `50 ms` hard gate.

Axes use five desktop or four mobile distance ticks and three elevation ticks, with the unit in the axis title rather than every tick. Terrain is visually subordinate to buildings and roads. A/B remain explicit at the two endpoints. Hover or keyboard movement exposes one focused building or road through a crosshair, non-color accent, concise callout, accessible summary, and the matching map focus source; the SVG remains one tab stop.

## Performance

Five fresh browser contexts were measured under the unchanged Guided protocol.

| Measurement | Before median | After median | Gate | Result |
| --- | ---: | ---: | ---: | --- |
| first meaningful render | `331.5 ms` | `325.0 ms` | `≤ 2000 ms` | pass |
| Area context cold | `435.4 ms` | `455.0 ms` | diagnostic | recorded |
| exact road warm | `330.8 ms` | `266.2 ms` | `≤ 1800 ms` | pass |
| exact building warm | `257.4 ms` | `261.6 ms` | `≤ 2500 ms` | pass |
| return to Scene 2 | `252.2 ms` | `254.1 ms` | `≤ 2000 ms` | pass |

The profiler continues to record blocked Inspector/devtools resources when the GSI raster is intentionally blocked; those messages are not same-origin product request failures.

## Preserved product contracts

The full browser journey retains the canonical selected Area, 495-Area switching, lazy PLATEAU contexts, exact road and building geometry, registered-position facility behavior, honest Area fallback, verified A–B geometry, target-specific checks and provenance. Guided-to-Advanced still reaches finite full-data success and still exposes the existing retryable error path. Long and legacy URLs, back/forward navigation, mobile, DPR 2, reduced motion, keyboard operation, and stale-state rejection remain in the regression matrix.

No backend, database, migration, dataset, score, ranking, new analysis, inferred use, walking/isochrone claim, hazard/borehole feature, 3D feature, or main-branch merge is part of this checkpoint.

## Local validation

- `git diff --check`: pass
- frontend lint, documentation links, and typecheck: pass
- frontend unit tests: 28 files, 117 tests passed
- production build: pass, 1,420 modules transformed
- Guided browser audit: six Areas, exact road/building, registered-position facility, honest fallback, mobile, DPR 2, reduced motion, keyboard and route regressions passed; diagnostics zero
- Section browser audit: desktop/compact/mobile annotation, collision, height, tick, legend, single-tab-stop, focused-callout and map-focus checks passed
- Guided-to-Advanced audit: direct, Guided, cached, back/forward, long URL, legacy routes, finite success, retryable error and retry success passed; diagnostics zero
- Public first-run, PLATEAU-native, and visual-identity browser audits: pass; no critical product diagnostics or horizontal overflow
- Python: Ruff passed; 414 tests passed and 3 environment-dependent tests skipped
- dependency audit: npm and pip-audit found no known vulnerabilities in the installed dependency sets
- documentation links: all 98 Markdown files resolved

## Video status

The existing captioned, clean, and 15-second demo videos remain unchanged and continue to document deployed source `33466bd97a20d96fafa7cf2906a1e89676e7da07`. Because the UI has changed, their status is:

- `EXISTING_VIDEO_PACKAGE_PRESERVED`
- `VIDEO_RECAPTURE_REQUIRED_AFTER_USER_APPROVAL`
- `VIDEO_CAPTURE_HOLD_PENDING_VISUAL_APPROVAL`

No replacement video is captured before the deployed visual review.
