# Cartographic validation checkpoint

Goal: `citygap-cartographic-visual-productization-v1`

Checkpoint: C5

Date: 2026-09-02 JST

## Outcome

The feature branch now makes the map explain the selected Investigation Area, one quantified evidence story, the selected Unknown, and its concrete verification target. The automated checkpoint passed without changing backend APIs, migrations, analytical facts, or the existing AreaSummary contract.

This is an automated product checkpoint, not a human or municipal validation result.

```text
AUTOMATED_CARTOGRAPHIC_CHECKPOINT_COMPLETE
READY_FOR_VISUAL_REVIEW
READY_FOR_HUMAN_TEST
AWAITING_HUMAN_TEST
AWAITING_MUNICIPAL_WORKFLOW_REVIEW
HOLD_MAIN_PROMOTION
HOLD_P1_M4_M6
BOREHOLE_INTEGRATE_RESEARCH_ONLY
```

## Repository boundary

- Branch: `feat/cartographic-visual-productization-v1`
- Source checkpoint: `946534c32a965654ee429af01e213cf980b8bac7`
- Baseline / `origin/main`: `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- C0–C4 commits: `88841c2`, `cefa068`, `54c517d`, `944afe3`, `047f314`
- C5 commit: the commit containing this checkpoint and its evidence
- Main merge / Pages deployment: not performed
- P1, Borehole, M4 Photo/GPS/Offline, M5 Review, and M6 Finding Feedback: not started

## What changed at C5

- Public Area data and the heavier cartographic derivative load independently.
- The cartographic load begins 500 ms after Area confirmation; no pre-confirmation prefetch occurs.
- Inline layer-array identity no longer recreates the MapLibre map when its semantic contents are unchanged.
- Public GeoJSON sources are updated before dependent visibility/paint changes.
- Exact road/building target geometry uses the source PLATEAU polygon.
- A facility that is not a PLATEAU object uses an explicitly labelled registered-position marker.
- Map and target readiness are exposed to the deterministic capture harness.
- The harness verifies story identity, rendered feature presence, target-color pixels, retry outcomes, diagnostics, accessibility, provenance hashes, routes, and fake/restricted evidence boundaries.

## Visual evidence

All screenshot dimensions, URLs, byte sizes, SHA-256 hashes, and source commit references are in [the manifest](assets/cartographic-checkpoint/manifest.json).

| State | Desktop evidence | Result |
|---|---|---|
| Before | [previous Known/Unknown](assets/cartographic-checkpoint/00-before-known-unknown-desktop.png) | Source checkpoint reference |
| 800m Area + population/age | [Area](assets/cartographic-checkpoint/02-area-800m-population-age.png) | Area and relative 500m-mesh context visible |
| Building use | [story](assets/cartographic-checkpoint/03-story-building-use.png) | PLATEAU use attributes; current use not claimed |
| Establishments | [story](assets/cartographic-checkpoint/04-story-establishments-aggregate.png) | Aggregate only; no fabricated locations |
| Urban planning | [story](assets/cartographic-checkpoint/05-story-urban-planning.png) | Available official objects only |
| Transport | [story](assets/cartographic-checkpoint/06-story-transport.png) | Registered points; operation/walkability not claimed |
| Unknown | [road Unknown](assets/cartographic-checkpoint/07-unknown-road-highlight.png) | Source limitation stays adjacent to the map |
| Exact road | [target](assets/cartographic-checkpoint/08-target-road-exact.png) | Source PLATEAU road surface |
| Exact building | [target](assets/cartographic-checkpoint/09-target-building-exact.png) | Source PLATEAU building footprint |
| Registered facility | [target](assets/cartographic-checkpoint/10-target-facility-reference.png) | Reference position, not a PLATEAU shape |
| Area fallback | [target](assets/cartographic-checkpoint/13-target-area-fallback.png) | Explicit honest fallback |
| Basemap unavailable | [degraded state](assets/cartographic-checkpoint/14-basemap-degraded-local-vectors.png) | Local vectors remain; limitation displayed |
| Mobile result | [390 x 844](assets/cartographic-checkpoint/15-mobile-result.png) | Map/panel remain connected |
| Mobile exact road | [390 x 844, DPR 2](assets/cartographic-checkpoint/16-mobile-target-road-exact.png) | Exact target remains visible |

The measured desktop/mobile changed-pixel proportions against the source checkpoint are 83.8% and 74.6%. They demonstrate a material rendering change, not human preference or quality.

## Performance

All values were collected from the same local production-preview protocol.

| Measure | Samples / result |
|---|---|
| First meaningful render | 3988, 1943, 1053, 1071, 1125 ms; median 1125 ms |
| Area ready | 500m 1278 ms; 800m 288 ms; 1km 1242 ms |
| Story switch | building use 4135 ms; establishments 1320 ms; planning 1077 ms; transport 1753 ms |
| Target ready | exact road 2453 ms; exact building 12336 ms; facility reference 5057 ms |

Target time is the recorded rendered-source arrival. The capture harness then waits for compositor stabilization; that stabilization delay is excluded from these figures.

## Cartographic correctness and provenance

- Source: `26202_maizuru-shi_city_2025_citygml_1_op.zip`
- Source SHA-256: `13f4020ade066dc7139b7653c47a55a09af0093dee743f6b9cca5d3177a71cff`
- The source hash is pinned in both generator code and the derivative manifest. CI, which intentionally excludes raw municipal/PLATEAU archives, verifies that identity plus every derivative artifact; a checkout that has the raw archive additionally verifies its bytes.
- Generator/rule: `citygap-public-cartography@1.0.0`
- Buildings: 4,898 Polygon features
- Roads: 1,686 Polygon features
- Planning: 55 Polygon/MultiPolygon features
- Artifact hashes match the derivative manifest.
- Exact target IDs resolve for one building and one road.
- No external data, population allocation, use inference, walking semantics, hazard/safety meaning, or score is added.

Target visual gates passed with exact-color signals of 278 road pixels, 318 building pixels, 164 facility-reference pixels, and 1,843 mobile-road pixels at DPR 2. The formal captures contain no page errors, failed same-origin requests, or error responses.

## Layout, interaction, and accessibility

- Desktop map/panel: 67.9% / 32.1%.
- Mobile result and target map share: 31.8%.
- Desktop map occlusion: 0.2%; mobile: 3.9%.
- Map/panel overlap and horizontal overflow: zero.
- Public first-run remains five clicks to the unverified task.
- Public top-level primary navigation: zero; header secondary action: one.
- Primary CTA count: one in intro/place/radius/result and zero at the terminal target state.
- Critical/serious accessibility violations: zero.
- Visible unnamed controls and duplicate IDs: zero.
- Keyboard-order failures: zero.
- Contextual 3D controls: zero by the existing UX-value gate; zero is an accepted result.
- Advanced, legacy M3, and the separately built Municipal surface remain available.

## Verification commands

Passed locally:

- `npm run lint`
- `npm run typecheck`
- `npm test` — 24 files, 96 tests
- `npm run build` — public production build
- `VITE_CITYGAP_SURFACE=municipal npm run build`
- `npm run audit:public-first-run` — five clicks, FMR median 1844 ms in its independent run
- `node scripts/audit-plateau-native.mjs --url ...` — all checks passed
- `node scripts/audit-visual-identity.mjs --url ...` — all five viewports, no console/local HTTP failure
- `node scripts/test-guided.mjs --url ...?journey=m3` — desktop/mobile passed
- `python analysis/scripts/build_public_cartographic_derivative.py --check`
- `pytest analysis/tests backend/tests -q` — 414 passed, one upstream deprecation warning
- `ruff check .`
- `npm run check:docs`
- `npm audit --audit-level=high` — zero vulnerabilities
- `git diff --check`

Remote CI is recorded after the feature branch is pushed. No workflow or `main` branch is changed to make CI run.

## Remaining risks and review questions

1. The cold building-use switch was 4135 ms; the exact-building target was 12336 ms and the facility reference was 5057 ms. Human reviewers should judge whether the loading/fallback communication prevents loss of confidence.
2. A basemap failure preserves local vectors, but its orientation quality is not yet human validated.
3. The facility reference capture can present a neutral background while the marker and boundary label remain available. This is honest but visually weaker than the exact PLATEAU targets.
4. The screenshot set supports review; it does not prove that a person recognizes the Area in three seconds or understands exact object versus registered position versus fallback.
5. The Unknown-to-field-task workflow is still awaiting direct municipal workflow review.

Proceed only through the separate review package. Do not promote to main or expand scope from this checkpoint.
