# Current goal

Active goal: `harbor-atlas-visual-identity-ux-v2`

Current milestone: S4 Urban Section visual language complete; S5 automated visual checkpoint next

Execution lock:

- branch: `feat/guided-spatial-storytelling-v1`
- starting HEAD / upstream: `7e75a132e7f135db2dcdcf2b26e4b1d833381586`
- origin/main at start: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- initial worktree: clean
- scope: Harbor Atlas semantic tokens, cartographic hierarchy, map-first Guided refinement, unified Urban Section language, responsive polish, automated comparison, feature-branch CI, feature-branch Pages deploy, and production audit
- preserve: one persistent MapLibre instance, canonical selection, 495 Areas, lazy context, Area switching and stale rejection, exact road/building and facility/fallback targets, A-B Section provenance/focus, Guided deep links and navigation, Guided-to-Advanced single-flight loading/retry, legacy/Public/Advanced/Municipal routes, accessibility, claims, and performance
- exclude: backend, database, migrations, new datasets or analysis, scores/ranking, hazards, walking semantics, Borehole, M4-M6, new 3D, AI features, external fonts, runtime themes, dark mode, fake evidence, main merge/push, and Pages workflow/environment changes
- baseline: production build passed; 22 product captures and 21 palette-study captures complete; diagnostics zero
- palette decision: candidate A, Harbor Atlas; capture-only study with no runtime selector
- baseline medians: FMR `314.9 ms`, Area cold `477.7 ms`, road `270.8 ms`, building `270.6 ms`, return/story warm `272.8 ms`; all V2 limits pass
- baseline Section: desktop/mobile annotations `6`/`4`, named roads `4`/`2`, zero overlap/outside/endpoint/tick conflicts, zero horizontal overflow, and calculations below `16 ms` in the capture matrix
- evidence: `docs/harbor-atlas-visual-baseline.md` and `docs/assets/harbor-atlas-v2/`
- S1 identity: UI neutrals, Harbor Area/navigation roles, Signal exact-target/action roles, map material roles, Urban Section roles, focus/error roles, and five motion timings are defined separately with retained compatibility aliases
- S1 composition: Public and Guided headings, selected rows, target summaries, primary/secondary actions, overlays, loading shell, and responsive surface switch now consume semantic roles; decorative Guided loading gradients and legacy purple Public/Guided accents are removed
- S1 style gates: ten Harbor Atlas source assertions pass, including locked seed values, UI/cartography separation, primary-action hierarchy, timing bands, reduced motion, no Public/Guided gradient, no runtime theme selector, and no legacy purple Section accent
- S1 regression: lint, typecheck, production build, `29` test files / `127` tests, Public/Guided/Advanced five-state browser capture with zero diagnostics, and the complete Guided-to-Advanced direct/cached/Back-Forward/error/retry suite pass
- S2 cartography: typed MapLibre colors now mirror the CSS semantic source; Signal exact targets, Harbor selected Area/A-B, neutral buildings/roads, quiet Harbor shortlist/context, and subdued basemap/other-Area layers implement the required visual priority
- S2 target states: exact road/building polygons and registered facility point use Signal with white halo plus labels; fallback remains a dashed Harbor Area with no exact-target fill, point, or label
- S2 map readability: selected Area labels increase to `15 px`, target labels to `14 px`, A/B endpoints to `15 px`; 495 Areas and non-selected context are quieter while buildings and roads remain distinguishable by material fill, outline, and geometry
- S2 motion: Public camera transitions move to `380 ms`; Guided remains `320 ms`; reduced motion continues to resolve at `0 ms`
- S2 regression: cartography/style tests, lint, typecheck, production build, 17-state core and five-state supplemental raster checks with zero diagnostics, and the full six-Area/exact/facility/fallback/Section/mobile/keyboard/legacy Guided contract all pass with one map initialization
- S3 flow: the single intro CTA now says `地域を選ぶ`; Scene 1 presents the selected 495-Area switch before three compact reference rows, then one `街の形を見る` action; the three-scene journey remains three deliberate forward actions
- S3 row/map sync: representative rows expose `aria-pressed`, `aria-current`, stable Area identity, focus/blur hover synchronization, and quieter transient hover than persistent selection
- S3 target hierarchy: exact-target captions and task summaries use Signal; fallback captions, legend, summary, numbering, and dashed geometry stay Harbor and never imply an exact object
- S3 responsive result: the Inspector uses `clamp(360px, 27vw, 440px)` on desktop; at 390 x 844 the selected Area name/switch and fixed 44px+ action are immediately visible, horizontal overflow is zero, and the remaining rows scroll below
- S3 copy: the stale `purple A-B line` phrase is removed; map and Section are described as the same A-B place without color-dependent language
- S3 regression: lint, typecheck, production build, 17-state raster capture with zero diagnostics, full six-Area/exact/facility/fallback/Section/mobile/keyboard/legacy browser journey, and complete Guided-to-Advanced transition/retry suite pass
- S4 material language: the SVG Section now shares the map's neutral terrain, building, and road roles; Harbor identifies A/B and annotation rails, while Signal is reserved for the active building/road focus and callout
- S4 readability: named-road annotations are `12 px`, axis ticks `11 px`, axis titles `12 px`, A/B endpoints `16 px`, and focused callout text `13 px` / `12 px`; matching text measurement prevents the larger labels from clipping
- S4 structure: background, grid, header, footer, legend, terrain, buildings, roads, focus, planning, hazard, and scenario states consume semantic Harbor Atlas tokens; the legacy Section-specific accent and raw local color literals are removed
- S4 collision result: the existing placement algorithm is unchanged; desktop/mobile retain `6`/`4` total annotations and `4`/`2` road labels with zero overlap, outside-plot, endpoint, tick, or legend conflicts and zero horizontal overflow
- S4 interaction: desktop and mobile pointer/keyboard Section focus continues to produce the matching map focus with one SVG tab stop and one persistent MapLibre initialization; the selected callout remains visible
- S4 regression: lint, typecheck, production build, `30` test files / `130` tests, 17-state desktop/compact/presentation/mobile/DPR2 raster capture with zero diagnostics, full six-Area/exact/facility/fallback/Section/mobile/keyboard/legacy browser journey, and complete Guided-to-Advanced direct/cached/Back-Forward/error/retry suite pass
- next gate: capture the final 20-state evidence set, record inventory/contrast/color-vision/performance/a11y results, run the complete local matrix, and document the automated before/after checkpoint
- no human visual, comprehension, accessibility-acceptance, or municipal-workflow pass is claimed

Prior deployed map/Section refinement checkpoint retained below.

---

Active goal: `deployed-map-ux-section-refinement-v1`

Current milestone: M4 automated checkpoint verified; M5 feature-branch push and remote CI next

Execution lock:

- branch: `feat/guided-spatial-storytelling-v1`
- starting HEAD: `8701df282da1b60049e9806e6b13f4ddceeecadc`
- remote feature HEAD at start: `8701df282da1b60049e9806e6b13f4ddceeecadc`
- origin/main at start: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- scope: Guided map readability, spatial-product UI polish, Urban Section annotation clarity, automated comparison, feature-branch CI, feature-branch Pages deployment, and production browser audit
- preserve: selected Area, 495-Area switching, exact PLATEAU targets, A–B Section, target-specific checks, upgrade controller, provenance, accessibility, performance, and deep links
- exclude: backend, database, migrations, new datasets, scores, ranking, analysis, Borehole, isochrone, GTFS, hazard additions, new M4–M6 product features, new 3D capability, main merge, and force push
- baseline evidence: `docs/map-section-refinement-baseline.md` and `docs/assets/map-section-refinement-v1/before/`
- local final UX evidence: `docs/final-ux-checkpoint.md`
- V4 feature push: commit `33466bd97a20d96fafa7cf2906a1e89676e7da07`
- V4 Municipal Pilot CI: run `33756406111`, all nine required jobs passed
- V4 Pages deployment: run `33756795063`, build and deploy passed
- production capture: 13 required states, diagnostics zero, source commit and Pages run recorded in `docs/assets/final-visual-checkpoint/manifest.json`
- production browser audit: Guided scenes, six Area switches, exact/fallback targets, mobile, keyboard, PLATEAU-native checks, and production Guided-to-Advanced flows passed
- production demo package: captioned 1080p, clean 1080p, 15-second backup, poster, VTT captions, manifest, script, and runbook in `docs/assets/demo-video/` and `docs/`
- V5 video source: the already deployed UI commit `33466bd97a20d96fafa7cf2906a1e89676e7da07`; recording diagnostics zero
- M0 facts: clean start, exact branch/upstream/head verified, production build passed, 17-view capture complete, capture diagnostics zero, one MapLibre initialization preserved, and five-context performance gates passed
- map baseline: basemap and multi-theme context compete with selection; exact targets lack a map label; Scene 1 Area labels are small
- Section baseline: no visible road-name annotations, `5` measured overlaps, `6` annotations outside the plot, tiny axis typography, and clipped mobile services
- existing demo videos: preserved unchanged; mark as visually stale after this refinement and recapture only after production visual approval
- M0 evidence commit: `a8f342391441fa3d9e039d5173cdb7a3c16840b3`
- M1 implementation: scene-aware basemap tuning, restrained candidate hierarchy, selected-Area halo/label, neutral PLATEAU context, stronger verified A–B line/endpoints, exact-target emphasis/label, and distinct honest fallback styling
- M1 evidence commit: `cc52b06`; 113 unit tests, full Guided browser journey, exact/fallback targets, six-Area switching, legacy routes, and Guided-to-Advanced upgrade/retry checks passed
- M2 implementation: clarify inspector hierarchy, map-caption state, back-navigation separation, semantic evidence/target summaries, status treatment, type scale, and legend fidelity without adding workflow steps
- M2 evidence commit: `90c4271`; 17-state production-preview visual pass and zero capture diagnostics, with the dedicated Guided-to-Advanced transition suite passing in isolation
- M3 implementation: deduplicated and distributed road labels, measured two-rail collision placement, four-road desktop/two-road mobile limits plus A/B, responsive plot height, clear axes/units/endpoints, subtle terrain hierarchy, focused-object accent/callout, accessible summary, one SVG tab stop, and corrected compact pointer projection
- M3 current measurements: total static annotations `6` desktop / `4` mobile; overlaps `0`; outside-plot labels `0`; endpoint/tick conflicts `0`; plot height `361.47 px` at `1440 × 900`, `300 px` at `1280 × 720`, `373 px` at `1920 × 1080`, and `303.19 px` mobile
- M3 performance/interaction: annotation calculation remained below the `16 ms` target in the versioned checkpoint; focused road/building callout, elevation/relation text, matching map focus source, one SVG tab stop, and one persistent map all verified
- M3 regression: production build, lint, typecheck, `117` unit tests, full Guided six-Area journey, exact/fallback/facility targets, legacy routes, and Guided-to-Advanced load/cache/error/retry suite passed
- M3 evidence commit: `5172427a2dffcf2fff751a3db633592c6f239943`
- M4 evidence: 17 matching after captures, zero browser diagnostics, explicit map-hierarchy gates, one map initialization, zero horizontal overflow, and fixed before/after manifest in `docs/assets/map-section-refinement-v1/`
- M4 Section result: desktop/mobile annotations `6`/`4`, visible named roads `4`/`2`, hidden lower-priority labels `6`/`8`, overlaps/outside/endpoint/tick conflicts all `0`, and maximum capture calculation `12.9 ms`
- M4 performance medians: FMR `325.0 ms`, Area context `455.0 ms`, exact road `266.2 ms`, exact building `261.6 ms`, and return to Scene 2 `254.1 ms`; all required gates passed
- M4 local gates: lint, docs, typecheck, production build, `117` frontend tests, Ruff, `414` Python tests with `3` skips, npm audit, pip-audit, Public/PLATEAU/visual audits, full Guided and Guided-to-Advanced browser suites passed
- M4 checkpoint: `docs/map-section-refinement-checkpoint.md`; existing videos remain preserved and are explicitly held for recapture until production visual approval
- next gate: commit M4, push only the feature branch, dispatch remote CI, and require all nine jobs green before Pages deployment
- human and municipal validation remain pending

Prior Guided checkpoint retained below.

---

Active goal at retained checkpoint: `guided-spatial-storytelling-v1`

Current milestone: G6 automated Guided spatial storytelling checkpoint complete

Gate: `READY_FOR_HUMAN_TEST / AWAITING_HUMAN_TEST / AWAITING_MUNICIPAL_WORKFLOW_REVIEW / HOLD_MAIN_PROMOTION / HOLD_PAGES_DEPLOY / HOLD_P1_M4_M6`

Checkpoint state:

- source branch: `feat/public-product-language-section-v1`
- source HEAD: `356dd90d49e7d736553de7596bb9cee619d1b692`
- execution branch: `feat/guided-spatial-storytelling-v1`
- baseline CI: Municipal Pilot CI run `33606249675`, completed successfully with all nine required jobs green
- worktree at G0: clean; no reset, clean, rebase, squash, or force push used
- goal: replace the current Guided card/wizard flow with one persistent MapLibre workspace whose camera, layers, selection, inspector, and optional section dock change across three internal scenes
- core story: `地域を見つける -> 街の形を空間的に理解する -> 現地で確かめる場所を特定する`
- default demo: 常団地前周辺; this is a default selection, not a product-wide fixed case
- Area contract: one canonical selected Area drives its polygon, label, metrics, capability state, lazy PLATEAU context, optional section, target, checks, and provenance
- payload boundary: a light 495-Area citywide catalog is initial; building, road, planning, target, section, and detailed source context load only for the selected Area
- PLATEAU source priority: use the pinned Maizuru 2025 citywide CityGML source for deterministic display membership where available; do not patch unrelated local artifacts together
- section boundary: optional and verified only for the Area/source pair that owns it; a missing section never blocks the Area context scene
- Scene 3 boundary: the 3–5 primary checks describe urban conditions that data cannot decide; photo/GPS/evidence-capture steps remain outside the Guided core
- implementation stops after G6; no main merge, Pages deploy, Human Test, P1, or M4–M6
- evidence product HEAD: `92bcad25a5b13e9cc81d488f9b023a1482381898`
- production build: passed (`1m 33s` on the final local run)
- Guided browser checkpoint: passed with one persistent MapLibre instance, six-area switch proof, legacy-route regression, desktop/mobile captures, keyboard checks, and no product errors
- production-preview medians: FMR `851.3 ms`; Area context cold `1835.6 ms`; exact road `1467.5 ms`; exact building `556.2 ms`; return to Scene 2 `794.0 ms`
- remote CI: not run because this goal has no push authorization
- next action: stop for real human comprehension testing and separate municipal workflow review

Prior completed checkpoint retained:

- source branch: `feat/cartographic-interaction-performance-v1`
- source HEAD: `a365dc04ccbcfad020d8f6ff2cd63db6e7865d60`
- execution branch: `feat/public-product-language-section-v1`
- baseline / origin/main: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- preservation: existing M3/028, A0–A5, U0–U4, C0–C5, and P0–P4 work retained; no reset, clean, rebase, squash, or force push
- goal: replace overexplained Public language and nested dashboard surfaces with concise Japanese, typographic hierarchy, and a disciplined section decision
- scope: Public copy, visual hierarchy, the Public boundary for Urban Section, and end-to-end presentation polish only
- excluded: backend, API, DB, migration, external data, new metric/score/ranking/recommendation, Borehole, hazards, walking isochrone, GTFS, M4–M6, new 3D capability, main merge, and Pages deployment
- H0 benchmark: nine official public URLs captured at 1440 × 900 with explicit access status; third-party captures remain research evidence only
- production baseline: GitHub Pages captured separately and remains unchanged
- feature baseline: source-HEAD production preview captured at desktop and 390 × 844 mobile across intro/place/radius/result/target
- Urban Section decision: Option C (`advanced_only`); do not add it to the Area Public first-run, preserve legacy M3 and Advanced
- merge / deployment: not performed
- inherited performance baseline: `docs/cartographic-performance-checkpoint.md` and `analysis/outputs/real/cartographic-performance-profile-after.json`
- H0 evidence: `docs/public-product-benchmark.md`, `docs/public-product-language-audit.md`, `docs/public-copy-deck.md`, `docs/urban-section-audit.md`, and `docs/assets/public-product-audit/manifest.json`
- H1 copy: concrete Japanese stage labels, one source disclosure, no system terminology in the initial reading path, and unchanged claim boundaries
- H2 hierarchy: one-line stage status, reduced cards/badges/rounding, neutral Unknown rows, and an un-nested target checklist
- H3 section boundary: `advanced_only`; no section in Public, no deletion from M3 or Advanced
- H4 presentation: consistent Area/result/target captions, 12–13px supporting text, 44px story actions, and unchanged 67.9/32.1 desktop map/panel ratio
- H5 evidence: same-protocol before/after inventory, 29 comparison screenshots, 19 cartographic screenshots, four required viewport classes including DPR 2, and a blank human-review sheet

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
- Automated cartographic performance: `AUTOMATED_CARTOGRAPHIC_PERFORMANCE_CHECKPOINT_COMPLETE`
- Visual-review readiness: `READY_FOR_SELF_VISUAL_REVIEW`
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

- `AUTOMATED_GUIDED_CHECKPOINT_COMPLETE`
- `READY_FOR_HUMAN_TEST`
- `AWAITING_HUMAN_TEST`
- `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`
- `HOLD_MAIN_PROMOTION`
- `HOLD_PAGES_DEPLOY`
- `HOLD_P1_M4_M6`

`GUIDED_UX_PASS`, `HUMAN_COMPREHENSION_PASS`, and `VISUAL_QUALITY_PASS` are not claimed. The automated checkpoint supports testing readiness only.

Automated checkpoint facts:

- Five controlled cold/warm samples were captured without weakening the C5 story, exact-target, facility, or compositor-ready meanings.
- Public FMR median is `1685.3 ms`; 800m Area-ready median is `174.4 ms`.
- Building-use is `2673.4 ms` cold / `1739.5 ms` warm; exact building is `1295.0 / 1098.3 ms`; facility is `1227.9 / 938.0 ms`; exact road is `1045.3 / 1052.5 ms`. Every primary median target passes.
- 19 versioned screenshots were captured with hashes, C5 pixel comparisons, and semantic readiness assertions. All required desktop story and mobile states are ready with no pending local source.
- Exact PLATEAU road and building targets, a registered-position facility target, and an honest Area fallback were verified separately.
- Desktop map/panel remained `67.9 / 32.1`; mobile result map share remained `31.8%`; overlap and horizontal overflow were zero.
- Critical/serious accessibility violations, unnamed visible controls, critical capture diagnostics, prohibited copy, internal IDs, and field-evidence inputs were zero.
- Visual recognition and usefulness remain human judgments. No participant result has been generated or inferred.

Remaining measured risks:

- Cold building-use retains a `5170.0 ms` outlier even though its median passes. The 3.24 MiB / 4,898-feature building derivative remains the heaviest allowed display path.
- Two FMR samples exceeded 2 seconds even though the median passes. Initial JavaScript and headless SwiftShader variance remain observable.
- The preview server transfers raw response bodies; profiled gzip is a deterministic comparison budget, not measured preview compression.
- Idle building prefetch is intentionally cancelled when target intent wins and is skipped for Save-Data/slow connections, so cold performance remains device/network dependent.
- External basemap availability remains outside CITY GAP control. The bounded degraded path and online recovery are automated, but actual device confidence remains a human-review question.

P1 acceptance facts:

- `plateau_targets.geojson` contains exactly the existing building and road target features: `3,246` raw bytes / `1,324` profiled gzip bytes.
- Generator verification requires exact feature equality with the Area building/road artifacts, matching object IDs, source version/hash, rule/generator version, scope, count, geometry types, and artifact hash.
- With all three Area-wide artifacts deliberately blocked, the browser still rendered the exact road polygon, exact building polygon, and facility registered-position marker. The Area loader honestly reported degraded while the target fast path reported ready.
- A P1 smoke profile reduced target-step GeoJSON submission from `6,643` features to `4` essential Area/target features. Final latency is not claimed yet because redundant source/style work remains P3 scope.

P2 acceptance facts:

- Landing requested zero cartography artifacts. Result-idle requested one manifest, the two-feature target artifact, and the 800 m Area building story artifact; it did not request Area roads or planning.
- Selecting the planning story requested only the planning artifact. Returning to building use reused the completed source/version/hash-keyed artifact; every artifact request count remained one.
- Building use retains all 4,898 source-attributed buildings intersecting the versioned 800 m Area. No usage is inferred and no visible information is removed.
- Save-Data, `slow-2g`, and `2g` connections skip idle prefetch. Leaving result or choosing a different story cancels a stale in-flight story request; a user-selected story takes priority.
- Story and target artifact bytes are verified against the manifest SHA-256 before entering the completed cache. A mismatched artifact is rejected rather than reused.
- A single P2 smoke run observed building-use `1809.1 ms` cold / `2156.5 ms` warm. This is diagnostic only; five-sample P4 values determine acceptance after P3.

P3 acceptance facts:

- Exact road/building and facility target transitions submit zero GeoJSON features after the target fast artifact is ready; they retain the existing source/layer instances and change only the necessary visibility/paint/camera values.
- A single P3 smoke run recorded map recreation zero, target `setData` zero, and only five style calls for exact targets / four for the facility marker. Final acceptance still uses P4 five-sample medians.
- Building story cold submits its 4,898-feature Area derivative once; warm reuse submits zero. Data fetched during result-idle is not sent to the MapLibre worker until that story is selected.
- The target selection effect no longer re-dispatches a generic viewport on every parent render. The exact MapLibre camera completes first and its `moveend` becomes the shared viewport.
- A failed external basemap hides after 16 bounded tile attempts, preserves local vectors and the degraded notice, and waits for an `online` event. A browser recovery test restored the same raster layer to visible/ready with no map recreation.
- Clicking the current Summary story repeats its existing request intent, allowing a failed hash/network load to retry without adding a new control or changing copy.

P4 is complete locally. Stop after the evidence commit and feature-branch remote CI report. Do not begin product P1 or M4–M6 and do not promote to `main` automatically.
