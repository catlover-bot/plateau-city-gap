# Cartographic interaction performance checkpoint

Goal: `cartographic-interaction-performance-v1`

Milestone: P4 — Automated Performance Checkpoint

Date: 2026-09-02 JST

This checkpoint compares the unchanged C5 Public cartographic experience at source commit `25a19ee9ebf444fb2244de6ace625238a74bbb89` with the optimized feature branch. It does not report a human test, municipal workflow review, main promotion, or Pages deployment.

Machine-readable evidence:

- [Five-sample P0 baseline](../analysis/outputs/real/cartographic-performance-profile-baseline.json)
- [Five-sample optimized profile](../analysis/outputs/real/cartographic-performance-profile-after.json)
- [Screenshot and semantic manifest](assets/cartographic-performance-checkpoint/manifest.json)
- [P0 root-cause profile](cartographic-performance-profile.md)

## Measurement contract

- Local production build and Vite preview, 1440 × 900, reduced motion, service worker blocked.
- Five fresh browser contexts for cold measurements; the second activation in the same context is warm.
- The external GSI basemap is intentionally blocked in the primary performance profile so local-vector readiness is reproducible. Basemap completion is not used as PLATEAU readiness.
- Story ready still requires the requested story, ready local MapLibre sources, and a rendered thematic feature.
- Exact target ready still requires the target step, exact source geometry in `public-target`, a ready source, and a rendered exact feature.
- Facility ready still requires its registered-position marker and essential local Area vectors.
- Compositor stability remains separately recorded two animation frames after semantic readiness.
- Screenshots add a second semantic gate: all story and mobile states must be `ready=true` with no pending source. Building and planning captures also require a rendered source feature.

No ready condition was shortened to produce a pass.

## Result

All primary median targets passed.

| Path | C5 checkpoint | P0 cold / warm | P4 cold median | P4 warm median | Acceptance |
|---|---:|---:|---:|---:|---|
| Public FMR | 1,125 ms | — | 1,685.3 ms | — | ≤ 2,000 ms: pass |
| 800 m Area | 288 ms | — | 174.4 ms | — | ≤ 1,000 ms: pass |
| Building-use story | 4,135 ms | 1,459.3 / 1,884.7 ms | 2,673.4 ms | 1,739.5 ms | cold ≤ 3,000; warm ≤ 2,000: pass |
| Exact building | 12,336 ms | 3,144.8 / 2,502.0 ms | 1,295.0 ms | 1,098.3 ms | cold ≤ 3,500; warm ≤ 2,500: pass |
| Facility reference | 5,057 ms | 4,450.2 / 3,602.8 ms | 1,227.9 ms | 938.0 ms | cold ≤ 2,500; warm ≤ 1,500: pass |
| Exact road | 2,453 ms | 1,773.8 / 2,289.8 ms | 1,045.3 ms | 1,052.5 ms | cold ≤ 2,500; warm ≤ 1,800: pass |

P4 samples, in run order:

| Path | Cold samples (ms) | Warm samples (ms) |
|---|---|---|
| Building-use | 5170.0 / 3534.6 / 2673.4 / 2407.1 / 2595.9 | 1739.5 / 1086.1 / 2089.2 / 2817.3 / 1589.2 |
| Exact building | 2239.4 / 1195.3 / 1317.1 / 1050.8 / 1295.0 | 1071.4 / 1098.3 / 1113.4 / 1005.1 / 1184.8 |
| Facility reference | 1632.4 / 1065.9 / 1227.9 / 1060.8 / 1486.3 | 935.7 / 1132.7 / 851.2 / 1224.7 / 938.0 |
| Exact road | 1714.8 / 1043.6 / 1045.3 / 1628.2 / 944.3 | 1052.5 / 1098.9 / 914.6 / 1092.9 / 966.7 |

FMR samples were `2076.4 / 2177.4 / 1331.9 / 1685.3 / 1323.2 ms`. The 800 m Area samples were `139.3 / 309.4 / 177.7 / 131.7 / 174.4 ms`. The cold building-use outlier of 5,170 ms is retained rather than discarded; median acceptance does not establish an outlier-free experience.

## Root cause and implemented boundary

### Building-use story

C5 loaded buildings, roads, and planning together, then resubmitted all 6,643 features on each switch. P2 now loads a selected story artifact independently, verifies its manifest hash, caches it by source/version/hash, cancels stale work, and reuses it. The 4,898 official source-attributed buildings and visible meaning are unchanged. Cold selection submits the building derivative once; warm reuse submits zero features.

### Exact building and road

C5 resolved a single object only after the complete Area bundle and resubmitted every derivative source. P1 adds a 2-feature target display derivative made from the exact existing building and road source features. It is 3,246 raw / 1,324 profiled gzip bytes. The object IDs and geometry JSON must equal the checked-in Area artifacts, so neither target is replaced by a point or simplified substitute.

### Facility reference

The facility is not a PLATEAU object. Its registered source position now renders without waiting for building, road, planning, or external basemap completion. It remains labelled `reference_position`; no exact geometry claim is introduced.

### MapLibre lifecycle

The MapLibre instance, sources, and layers remain stable. Same-reference GeoJSON and equal filters/paint/layout values are no-ops. Exact targets and facility transitions perform zero `setData`; median style/filter work is five calls for exact targets and four for the facility. Map recreation is zero in all cold and warm samples.

The generic parent viewport update was removed from target selection. Exact `fitBounds`/`easeTo` completes first, and `moveend` becomes the shared viewport. A failed GSI source is hidden after a bounded initial failure set, local vectors remain available, and the existing raster layer waits for `online` before one explicit resume.

## Payload and parse budget

Landing requests zero cartographic artifacts before and after this sprint.

| Phase | Assets | Features | Raw bytes | Profiled gzip bytes |
|---|---:|---:|---:|---:|
| C5 post-Area all-artifact bundle | 4 | 6,639 | 4,827,498 | 996,381 |
| P4 first exact-target path: manifest + target | 2 | 2 | 8,183 | 2,629 |
| P4 building story artifact only | 1 | 4,898 | 3,243,343 | 643,914 |
| P4 result-idle bounded path: manifest + target + building | 3 | 4,900 | 3,251,526 | 646,543 |

The result-idle path may prefetch the building story only after result intent and browser idle. `Save-Data`, `2g`, and `slow-2g` skip it. Planning is fetched only when selected. The 1.42 MiB Area road artifact is not fetched by the Public exact-road path. Every optimized sample recorded three cartographic requests, zero duplicate fetches, and no failed same-origin request.

Offline parse medians changed as follows:

| Artifact | P0 parse | P4 parse |
|---|---:|---:|
| Manifest | 0.025 ms | 0.023 ms |
| Buildings | 152.656 ms | 53.106 ms |
| Roads | 11.403 ms | 12.840 ms |
| Planning | 10.920 ms | 2.708 ms |
| Target fast derivative | not present | 0.043 ms |

Offline parse variance reflects the local Node process and is not substituted for browser semantic readiness.

## Cache, cancellation, and degraded behavior

- Completed artifacts are keyed by source version, source SHA-256, artifact kind, and artifact SHA-256.
- A mismatched artifact hash is rejected and never enters the completed cache.
- Leaving the result or changing story aborts a stale in-flight request; aborted responses are not cached.
- The screenshot run recorded two expected `net::ERR_ABORTED` building-prefetch cancellations while moving directly to an exact road target. They are preserved separately from errors in the manifest.
- The performance harness deliberately blocks the basemap. Four samples stopped after 16 aborted tile requests; the first SwiftShader sample observed 32 during initialization. Local readiness still passed. A separate online recovery check restored the same raster layer without recreating the map.
- Existing loading copy and degraded-basemap disclosure are retained. No fake progress or blocking overlay was added.

## Provenance

`plateau_targets.geojson` is a display derivative of the same existing Maizuru CityGML source/version. Its manifest retains artifact kind, source version/hash, generator/rule versions, scope, feature count, geometry types, object identities, and artifact hash. Generation fails if either target feature differs from the corresponding Area artifact. Public target resolution remains `exact`, `reference_position`, or honest `area_fallback`.

## Visual regression and self-review

Nineteen screenshots are stored in [the P4 asset directory](assets/cartographic-performance-checkpoint/). C5 files are not overwritten. The manifest records viewport, URL, commit, file hash, layout metrics, legends, story IDs, readiness, target resolution, and pixel comparisons.

- Area 800 m, population, building-use, establishments, planning, transport, Unknown, Area 500 m, Area 1 km, and mobile result had `0.0%` changed pixels in the deterministic comparison; degraded-basemap was `0.1%`.
- Target screenshots have larger background/camera pixel differences: road `50.9%`, building `43.0%`, facility `63.4%`, fallback `63.3%`, and mobile road `21.7%`. Changed pixels are not treated as semantic proof.
- Semantic checks separately confirm the same exact road/building resolution and source geometry, registered facility position, honest fallback, legends, Area mask, one active story, semantic colors, and zero 3D controls.
- Desktop remains 67.9/32.1 map/panel with 0.2% map occlusion. Mobile result remains 31.8% map share with 3.9% occlusion. Overlap and horizontal overflow are zero.
- A direct self-review of the generated story, target, fallback, and mobile images found the same information architecture and cartographic grammar. This is not a substitute for a participant review.

## Accessibility, privacy, and compatibility

- Automated critical/serious accessibility count: zero.
- Visible controls have names, a single visible `h1` is retained, duplicate IDs are absent, and keyboard focus is visible.
- Reduced-motion captures pass.
- Prohibited walking/ground copy, internal object IDs, field-evidence inputs, fake photos/GPS/answers/reviews, and restricted values are absent.
- The current Public route, legacy M3 route, and Advanced route pass the browser regression. Municipal compatibility is verified by its separate production build.

## Remaining performance risks

1. Cold building-use has a 5,170 ms retained outlier even though the median passes. The 3.24 MiB building artifact and MapLibre worker processing remain the largest unavoidable Public cost at this scope.
2. Two FMR samples exceeded 2,000 ms even though the 1,685.3 ms median passes. Initial JavaScript and headless SwiftShader variance remain observable.
3. The preview server transfers raw bodies; profiled gzip is a deterministic budget, not measured transfer compression.
4. Idle building prefetch saves the common story path but intentionally yields to Save-Data/slow connections and can be cancelled when the user chooses a target first.
5. External basemap availability remains outside CITY GAP control. The bounded degraded state is tested, but real device/network combinations still need human observation.
6. Screenshot pixel equality cannot prove comprehension. Exact geometry, semantics, and readiness are automated; usefulness and visual confidence remain human judgments.

## Local verification

- `ruff check analysis backend`: passed.
- `pytest analysis/tests backend/tests -q`: 414 passed; one upstream Starlette/httpx deprecation warning.
- Frontend ESLint, Markdown link check, TypeScript: passed.
- Vitest: 24 files / 102 tests passed.
- Public and `VITE_CITYGAP_SURFACE=municipal` production builds: passed.
- PLATEAU-native browser audit: all 18 checks passed, including mobile, keyboard, road claim boundary, and console/request cleanliness.
- Visual-identity audit: five viewports passed with no local HTTP failure, console error, horizontal overflow, gradient, or unnamed button.
- Legacy M3 guided regression: desktop and 390 px mobile passed; 4 uncertainties, 4 tasks, required checks `5 / 4 / 5 / 4`, and zero field-evidence inputs.
- Cartographic derivative regeneration: 4,898 buildings / 55 planning / 1,686 roads / 2 targets, with the expected exact building and road IDs.
- npm high audit and pip-audit after upgrading the disposable test-venv installer: no known vulnerabilities. Tracked secret scan and raw-data boundary: clean.
- `git diff --check` and all 82 local Markdown-link checks: passed.

Database-backed migration/PostGIS/API integration and container builds are delegated to the unchanged remote `Municipal Pilot CI`; no migration, backend, API, or database file changed in this sprint. Its feature-branch result is reported after the P4 commit is pushed. Main and Pages workflows are not triggered intentionally.

## Stop state

```text
AUTOMATED_CARTOGRAPHIC_PERFORMANCE_CHECKPOINT_COMPLETE
READY_FOR_SELF_VISUAL_REVIEW
READY_FOR_HUMAN_TEST
AWAITING_HUMAN_TEST
AWAITING_MUNICIPAL_WORKFLOW_REVIEW
HOLD_MAIN_PROMOTION
HOLD_P1_M4_M6
```

P4 stops here. Product P1, Borehole, walking isochrone, M4–M6, main merge, and Pages deployment are not started.
