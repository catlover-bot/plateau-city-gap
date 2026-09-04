# Harbor Atlas visual UX checkpoint

Status: `S5_AUTOMATED_CHECKPOINT_RECORDED`

This checkpoint records the completed Harbor Atlas visual-identity, map, Guided, and Urban Section refinement on `feat/guided-spatial-storytelling-v1`. It is automated and self-review evidence, not a human aesthetic, comprehension, accessibility-acceptance, or municipal-workflow result.

## Source and protocol

- locked baseline: `7e75a132e7f135db2dcdcf2b26e4b1d833381586`
- refined product and evidence tooling: `046cc261a870847955d3910a02668aa4960b227a`
- comparison package: [`docs/assets/harbor-atlas-v2/manifest.json`](assets/harbor-atlas-v2/manifest.json)
- final core capture manifest: [`after/manifest.json`](assets/harbor-atlas-v2/after/manifest.json)
- capture environment: local production preview, Playwright Chromium, reduced motion, font readiness, and compositor-frame readiness
- evidence set: 17 core states, five supplemental states, and three color-vision simulations; 25 final PNGs in total
- browser diagnostics: zero in all three capture manifests
- persistent MapLibre initialization count: one in every audited product state

The final evidence covers Public, Guided intro, all three Guided scenes, another Area, fallback, exact road, exact building, registered-position facility, desktop, 1280px, 1920px, 390px mobile, DPR 2, pointer hover, Advanced loading/ready, grayscale, protanopia, and deuteranopia. All evidence was captured after implementation and accessibility fixes; no baseline image was reused as an after image.

## Before and after

| State | Baseline | Harbor Atlas | Automated result |
| --- | --- | --- | --- |
| Public landing | [before](assets/harbor-atlas-v2/before/01-public-landing-desktop.png) | [after](assets/harbor-atlas-v2/after/01-public-landing-desktop.png) | quiet page/panel neutrals, one H1, one primary Signal action, map 73% |
| Guided Scene 1 | [before](assets/harbor-atlas-v2/before/03-scene1-find-desktop.png) | [after](assets/harbor-atlas-v2/after/03-scene1-find-desktop.png) | selected Harbor Area separates from quieter candidates; 15px selected label |
| Guided Scene 2 | [before](assets/harbor-atlas-v2/before/05-scene2-combined-desktop.png) | [after](assets/harbor-atlas-v2/after/05-scene2-combined-desktop.png) | map and Section share neutral materials and Harbor A-B identity |
| Guided Scene 3 | [before](assets/harbor-atlas-v2/before/07-scene3-exact-road.png) | [after](assets/harbor-atlas-v2/after/07-scene3-exact-road.png) | exact target uses Signal fill, white halo, strong outline, and 14px label |
| Mobile Section | [before](assets/harbor-atlas-v2/before/13-mobile-scene2-section.png) | [after](assets/harbor-atlas-v2/after/13-mobile-scene2-section.png) | A/B, two road names, axes, buildings, roads, and terrain remain readable at 390px |
| Grayscale Scene 2 | [simulation](assets/harbor-atlas-v2/after/21-grayscale-scene2.png) | same final state | selection and A-B remain distinguishable by outline, halo, endpoints, and geometry |
| Protanopia / deuteranopia Scene 3 | [protanopia](assets/harbor-atlas-v2/after/22-protanopia-scene3.png) | [deuteranopia](assets/harbor-atlas-v2/after/23-deuteranopia-scene3.png) | target remains distinct through halo, width, label, and geometry; simulated RGB distances pass |

## Harbor Atlas identity

The visual system now uses separately named semantic roles for UI neutrals, Harbor spatial selection/navigation, Signal exact targets/actions, map materials, Section materials, focus, error, and motion. Public and Guided decorative gradients and legacy purple accents are absent. No runtime theme selector, third-party font, new marketing surface, or new product mode was added.

The locked seed palette is:

- neutral ink `#15242B`, soft ink `#526269`, page `#F5F5F1`, panel `#FCFCF9`, muted `#EEF1EF`, line `#D7DDDA`, strong line `#87959A`
- Harbor `#164F63`, `#26758A`, `#77AEB6`, `#C9E1DE`, `#E8F2EF`
- Signal `#A94736`, `#D9664D`, `#F1A085`, `#F7E4DE`
- building `#9BA9AD` / `#596970`, road `#E5DDD1` / `#667279`, terrain `#5D7476`, focus `#F0B84B`, error `#B34E49`

Every Public and Guided core capture reports exactly two strong accent families: Harbor and Signal. Advanced retains its established specialist accent, which is outside the Public/Guided two-family rule.

The source inventory records 86 semantic-token definitions and 717 references after refinement, compared with 48 and 555 at baseline. Raw color literals outside the token source fell from 756 to 628. This is a source migration measurement, not a claim that all legacy product CSS has been converted.

## Map and Guided result

- Public and Guided keep the map as the primary surface, with a 73/27 desktop map/panel split and scene-aware basemap opacity.
- Scene 1 retains the canonical selected Area, the light 495-Area catalog, Area switching, stable row/map synchronization, and lazy detailed context.
- The selected Area uses Harbor fill, halo, outline, and label; candidates and other context are quieter.
- Scene 2 exposes neutral PLATEAU buildings and roads, the Harbor A-B line and endpoints, and the matching Section without introducing a second selection model.
- Scene 3 exact road/building and registered-position facility targets use Signal plus non-color cues. Honest fallback stays a dashed Harbor Area and does not imply exact geometry.
- The Guided story still has three deliberate forward actions. Deep links, Back/Forward behavior, legacy routes, Public, Advanced, Municipal, and reduced-motion behavior remain in the regression matrix.
- Guided to Advanced retains one bounded single-flight load, finite timeout, retry, cached success, and preserved selection/display state.

## Urban Section readability

| Measurement | Harbor Atlas result | Gate | Result |
| --- | ---: | ---: | --- |
| desktop annotations / named roads | `6` / `4` | retained | pass |
| mobile annotations / named roads | `4` / `2` | retained | pass |
| label overlap / outside / endpoint / tick conflicts | `0 / 0 / 0 / 0` | `0` | pass |
| named-road annotation size | `12px` | `>=12px` | pass |
| axis tick / title size | `11px` / `12px` | `>=11px` / `>=12px` | pass |
| A/B endpoint size | `16px` | `>=16px` | pass |
| Section calculation median | `9.9ms` | `<=16ms` | pass |
| Section calculation maximum | `11.1ms` | `<=50ms` | pass |

The placement algorithm remains deterministic and unchanged in capacity. Terrain, buildings, and roads use the same material roles as the map; Harbor identifies the transect and annotation rails; Signal is reserved for active object focus and its callout. Pointer and keyboard focus continue to drive the matching map focus with one SVG tab stop.

## Accessibility and color independence

The versioned [`accessibility.json`](assets/harbor-atlas-v2/after/accessibility.json) runs axe-core 4.10.3 against seven Public/Guided desktop and mobile states. It reports zero total violations, zero critical or serious violations, zero structural failures, one visible H1 per state, no duplicate IDs, no horizontal overflow, and one map initialization.

The keyboard focus treatment uses the prescribed gold focus color with a dark perimeter. Exact targets and selected Areas are not differentiated by hue alone: their fill, outline width/style, white halo, labels, and geometry differ. The automated simulations record passing target/Area RGB distances of `118.1` under protanopia and `138.8` under deuteranopia; grayscale retains the same structural separation. These simulations and axe results support automated conformance checks but do not constitute accessibility acceptance by people.

## Performance

Five fresh production-preview browser contexts produced the following medians. The external GSI basemap is deliberately blocked by the profiler so the timings isolate local product readiness; its blocked-resource messages are expected and are not same-origin product failures.

| Measurement | Baseline | Harbor Atlas | Change | Required gate | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| first meaningful render | `314.9ms` | `299.8ms` | `-4.8%` | `<=2000ms` | pass |
| Area context cold | `477.7ms` | `467.5ms` | `-2.1%` | `<=1500ms` | pass |
| exact road warm | `270.8ms` | `264.0ms` | `-2.5%` | `<=1200ms` | pass |
| exact building warm | `270.6ms` | `252.5ms` | `-6.7%` | `<=1200ms` | pass |
| return to Scene 2 | `272.8ms` | `257.8ms` | `-5.5%` | `<=1200ms` | pass |

Every absolute performance gate and the maximum 20% baseline-regression gate pass. The full sample distribution is versioned in [`performance.json`](assets/harbor-atlas-v2/after/performance.json).

## Preserved contracts

Automated unit and browser coverage retains one persistent MapLibre instance; canonical selection; 495 Areas; lazy context; Area switching and stale rejection; exact building/road geometry; registered-position facility and honest fallback behavior; A-B Section provenance, ownership, and map focus; target-specific checks; Guided deep links and navigation; the Guided-to-Advanced loading fix; legacy, Public, Advanced, and Municipal routes; keyboard and responsive behavior; claim boundaries; and performance limits.

No backend, database, migration, dataset, analysis, score, ranking, hazard, walking semantic, new target, Borehole, 3D, AI, dark-mode, or main-branch change is included.

## Local validation

- ESLint, TypeScript, and documentation links: pass; all 100 Markdown files resolve
- Vitest: 30 files and 130 tests pass, including the exact ten Harbor Atlas style/accessibility assertions
- default Public/Guided production build and `VITE_CITYGAP_SURFACE=municipal` build: pass; 1,421 modules transformed in each
- Ruff: pass
- Python non-database suite: 414 passed, three environment-dependent tests skipped, and two third-party deprecation warnings reported
- dependency review: npm reports zero vulnerabilities; pip-audit reports no known vulnerabilities and explicitly skips the editable local package
- Public first-run, visual identity, PLATEAU-native, full Guided six-Area/exact/facility/fallback/Section/mobile/keyboard/legacy, and Guided-to-Advanced direct/cached/Back-Forward/error/retry browser audits: pass
- final seven-state axe audit: pass with zero violations and zero structural failures
- final capture manifests: zero browser diagnostics; inventory reports zero console errors and zero local HTTP failures

## Video status and review boundary

The existing captioned, clean, 15-second, poster, captions, manifest, script, and runbook package in `docs/assets/demo-video/` remains byte-for-byte untouched by this refinement. It still documents the earlier deployed source and is therefore retained historical evidence, not a Harbor Atlas recording. Recapture remains on hold until the deployed Harbor Atlas visual review is accepted.

Current review states:

```text
S5_AUTOMATED_CHECKPOINT_RECORDED
READY_FOR_SELF_VISUAL_REVIEW
AWAITING_HUMAN_TEST
AWAITING_ACCESSIBILITY_ACCEPTANCE
AWAITING_MUNICIPAL_WORKFLOW_REVIEW
HOLD_MAIN_PROMOTION
VIDEO_RECAPTURE_HOLD_PENDING_VISUAL_APPROVAL
```
