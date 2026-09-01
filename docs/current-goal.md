# Current goal

Active goal: `cartographic-interaction-performance-v1`

Current milestone: P1 Target Fast Path complete; P2 Story Loading next

Gate: `HOLD_MAIN_PROMOTION / HOLD_P1_M4_M6`

Checkpoint state:

- source branch: `feat/cartographic-visual-productization-v1`
- source HEAD: `25a19ee9ebf444fb2244de6ace625238a74bbb89`
- execution branch: `feat/cartographic-interaction-performance-v1`
- baseline / origin/main: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- preservation: existing M3/028, A0–A5, and U0–U4 work retained; no reset, clean, rebase, squash, or force push
- performance goal: preserve the complete C5 cartographic product while reducing only story/target interaction latency
- scope: root-cause profiling, provenance-preserving display-derivative partitioning, bounded loading, MapLibre lifecycle stabilization, and automated performance evidence
- excluded: UI redesign, copy changes, backend, API, migration, external datasets, new analytical facts, product P1, M4–M6, main merge, and Pages deployment
- reference capture: 9 URLs recorded with screenshot or explicit unavailable status; third-party captures remain benchmark-only
- merge / deployment: not performed
- C0–C4 implementation commits: `88841c2`, `cefa068`, `54c517d`, `944afe3`, `047f314`
- C5 baseline: `docs/cartographic-validation-checkpoint.md` and `docs/assets/cartographic-checkpoint/manifest.json`
- P0 evidence: `docs/cartographic-performance-profile.md` and `analysis/outputs/real/cartographic-performance-profile-baseline.json`
- P1 target path: exact building/road geometry is available from a two-feature, provenance-complete derivative; facility remains a registered local position

Core value hypothesis:

> 自治体職員が経験的に感じている地域の状態を公開データとPLATEAUで定量化・可視化し、データだけでは判断できない部分を明示して次の確認へつなげる。

Internal contract:

```text
LOCAL INTUITION
  -> QUANTIFIED EVIDENCE
  -> KNOWN / UNKNOWN
  -> source limitation
  -> Finding
  -> versioned PLATEAU target / honest fallback
  -> 3–5 verification checks
  -> status = unverified
```

Validation status:

- AOI need: `DIRECT_MUNICIPAL_NEED_CONFIRMED`
- Area Summary content: `DIRECT_MUNICIPAL_NEED_PARTIALLY_CONFIRMED`
- Known/Unknown value: `DIRECT_MUNICIPAL_VALUE_SIGNAL_CONFIRMED`
- Unknown-to-field-task workflow: `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`
- Automated Public UX: `AUTOMATED_UX_CHECKPOINT_COMPLETE`
- Automated cartographic checkpoint: `AUTOMATED_CARTOGRAPHIC_CHECKPOINT_COMPLETE`
- Visual-review readiness: `READY_FOR_VISUAL_REVIEW`
- Human-test readiness: `READY_FOR_HUMAN_TEST`
- Public copy comprehension: `AWAITING_HUMAN_TEST`

Product boundary:

- `Investigation Area` is the center; station is one convenient `point_radius` origin.
- P0 supports station/map point, 500/800/1000m and bounded custom radius.
- 800m is a policy-analysis radius, not an actual walking-time isochrone.
- The feature branch makes the new Area first-run journey its Public root. `main` and GitHub Pages keep the current entry until a separate promotion decision after human and municipal review.
- Public Area displays no photo, GPS, answer, assignee, or municipal review.
- Area selection and aggregation are not the novelty. The provisional differentiation is the traceable Area → Known/Unknown → Finding → PLATEAU target → verification chain.
- M4 Photo/GPS/Offline, M5 Municipal Review, M6 Finding Feedback, pedestrian isochrone, polygon drawing, and Borehole UI are not authorized by this goal.

Active Public execution rules:

- Unknown cards in the Public first view contain only what is still unknown and why it should be checked. Dataset, version, source limitation, coverage, rule, model code, and object provenance are consolidated in one collapsed `出典・データの注意点` disclosure. Only a short, material misunderstanding warning may appear inline.
- The PLATEAU object, source/version, coverage, and WebGL checks are necessary but not sufficient for 3D. `3Dで周辺を見る` is rendered only when 3D adds understandable spatial context beyond the 2D map. A technically eligible single road point or single-building current-use check remains 2D when 3D adds no decision information.
- A zero-button 3D result is an acceptable UX outcome. U4 records both the technical gate and the UX reason for every displayed or withheld case.
- The Area spotlight must preserve roads, railway lines, place names, rivers, and other geographic orientation. Outside dimming is tuned from browser evidence rather than fixed at 16%; it may not hide surrounding context. The goal is to make the Area primary, not to conceal its surroundings.
- The five Summary groups remain evidence summaries. A small contextual `地図で見る` action may change the active story and use `aria-pressed`, but the rows must not look or behave like top-level tabs or navigation.
- Visual wow must come from spatial meaning: radius changes reveal the Area, Summary actions reveal real thematic geometry, Unknown selection isolates related real objects, and the target action moves the camera to the verified target. Decorative gradients, glow, excessive shadow, looping animation, and extra color are not substitutes for spatial meaning.
- At most one thematic story layer is active. Invariant Area/origin context and the selected target may remain visible.
- PLATEAU display geometry may be generated only from the same existing CityGML source/version, after checking existing public spatial packs first. It is a deterministic display derivative with source hash, generator version, provenance, and artifact hash; it may not add population allocation, inferred use, walking semantics, hazards, scores, or policy meaning.

Maizuru borehole evidence:

- Evidence status: `DIRECT_MUNICIPAL_USE_CASE_OVERLAP_CONFIRMED`.
- Maizuru's current-year use case is considering borehole columns on a PLATEAU 3D city model together with liquefaction maps and landslide or other hazard data.
- `PLATEAU 3D + borehole columns + hazard layers` is therefore not CITY GAP novelty.
- Borehole strategy is `INTEGRATE / RESEARCH ONLY`, not an automatic P1 implementation.
- CITY GAP will not build its own borehole viewer, 3D column viewer, or hazard-and-borehole viewer. A later, separately approved goal may only assess whether Maizuru outputs can be connected as an official Investigation Area source with provenance and source limitations intact.

Current stop state:

- `AUTOMATED_CARTOGRAPHIC_CHECKPOINT_COMPLETE`
- `AUTOMATED_UX_CHECKPOINT_COMPLETE`
- `READY_FOR_VISUAL_REVIEW`
- `READY_FOR_HUMAN_TEST`
- `AWAITING_HUMAN_TEST`
- `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`
- `HOLD_MAIN_PROMOTION`
- `HOLD_P1_M4_M6`
- `BOREHOLE_INTEGRATE_RESEARCH_ONLY`

Automated checkpoint facts:

- 19 versioned before/after and state screenshots were captured with hashes.
- Public FMR samples were `3988 / 1943 / 1053 / 1071 / 1125 ms`; median `1125 ms`.
- 500m / 800m / 1km Area render readiness was `1278 / 288 / 1242 ms`.
- Exact PLATEAU road and building targets, a registered-position facility target, and an honest Area fallback were verified separately.
- Desktop map/panel remained `67.9 / 32.1`; mobile result map share remained `31.8%`; overlap and horizontal overflow were zero.
- Critical/serious accessibility violations, unnamed visible controls, capture diagnostics, prohibited copy, internal IDs, and field-evidence inputs were zero.
- Visual recognition and usefulness remain human judgments. No participant result has been generated or inferred.

Remaining measured risks:

- The controlled five-sample P0 profile records building target medians of `3144.8 ms` cold / `2502.0 ms` warm and facility medians of `4450.2 ms` cold / `3602.8 ms` warm, with much larger retained outliers.
- Every story/target action currently resubmits seven GeoJSON sources and at least 6,643 features; some cold target transitions submit the full set twice.
- All three heavy artifacts load together after Area confirmation. Exact target lookup and the registered facility presentation remain unnecessarily coupled to Area context.
- A basemap-unavailable state preserves local vectors, but the controlled degraded run observes hundreds of aborted external tile requests per page. Retry/readiness stabilization remains P3 work.

P1 acceptance facts:

- `plateau_targets.geojson` contains exactly the existing building and road target features: `3,246` raw bytes / `1,324` profiled gzip bytes.
- Generator verification requires exact feature equality with the Area building/road artifacts, matching object IDs, source version/hash, rule/generator version, scope, count, geometry types, and artifact hash.
- With all three Area-wide artifacts deliberately blocked, the browser still rendered the exact road polygon, exact building polygon, and facility registered-position marker. The Area loader honestly reported degraded while the target fast path reported ready.
- A P1 smoke profile reduced target-step GeoJSON submission from `6,643` features to `4` essential Area/target features. Final latency is not claimed yet because redundant source/style work remains P3 scope.

Next action is P2 Story Loading, followed only by P3 Lifecycle/Readiness and P4 Automated Performance Checkpoint. Stop at P4. Do not begin product P1 or M4–M6 and do not promote to `main` automatically.
