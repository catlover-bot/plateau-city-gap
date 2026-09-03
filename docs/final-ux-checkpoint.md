# Final visual UX checkpoint

Goal: `final-visual-polish-and-demo-video-v1`

Checkpoint: V3 local production-preview audit

The visual and interaction changes are complete on `feat/guided-spatial-storytelling-v1`. This checkpoint is automated evidence, not a human aesthetic, comprehension, or municipal-workflow result.

## Source and evidence

| Item | Value |
|---|---|
| Starting HEAD | `dad536e87019f3e1b54dfca50fac9405adb23aac` |
| Visual source commit | `66eb7f74fc3554b6b19d2b28e040842beb91ee11` |
| `origin/main` at checkpoint | `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff` |
| Capture environment | local production preview |
| Viewports | 1440 x 900, 1280 x 720, 390 x 844, DPR 2 |
| Automated image set | [manifest and 13 captures](assets/final-visual-checkpoint/manifest.json) |
| Before reference | [retained Guided checkpoint](assets/guided-spatial-checkpoint/manifest.json) |
| Performance | [`final-visual-performance.json`](../analysis/outputs/real/final-visual-performance.json) |

The final capture waits for the app's public or Guided visual-readiness signal, font readiness, and compositor frames. Each record includes its URL, viewport, DPR, file hash, control count, map/panel ratio, map occlusion, map state, and spatial identity. All 13 local captures reported `map_render_state=ready`; browser diagnostics were empty. The same script will be run against GitHub Pages after V4 deployment, so these local files are not represented as the final production capture yet.

## Before and after

| State | Before | After | Automated result |
|---|---|---|---|
| Public landing | [before](assets/public-product-audit/production-landing-desktop.png) | [after](assets/final-visual-checkpoint/01-public-landing-desktop.png) | one heading, one CTA, map 73%, six visible controls |
| Guided intro | [before](assets/guided-spatial-checkpoint/desktop-intro.png) | [after](assets/final-visual-checkpoint/02-guided-intro-desktop.png) | map/panel 73/27, one CTA, map initialization retained |
| Scene 1 | [before](assets/guided-spatial-checkpoint/desktop-find-tsune.png) | [after](assets/final-visual-checkpoint/03-scene1-find-desktop.png) | compact rows, selected row and polygon, 10 controls |
| Scene 2 | [before](assets/guided-spatial-checkpoint/desktop-understand-533513314.png) | [after](assets/final-visual-checkpoint/04-scene2-hero-desktop.png) | exact PLATEAU context, A–B line and 323px plot |
| Section | [before](assets/guided-spatial-checkpoint/compact-understand-section.png) | [close-up](assets/final-visual-checkpoint/05-scene2-section-closeup.png) | terrain/building/road legend reduced to three items |
| Scene 3 | [before](assets/guided-spatial-checkpoint/desktop-verify-533513314.png) | [after](assets/final-visual-checkpoint/06-scene3-exact-road.png) | exact road, one `未確認`, four source-backed checks |
| Mobile Scene 2 | [before](assets/guided-spatial-checkpoint/mobile-understand-map.png) | [map](assets/final-visual-checkpoint/10-mobile-scene2-map.png) / [section](assets/final-visual-checkpoint/11-mobile-scene2-section.png) | map/section switch retained; section plot 303.2px |
| Mobile Scene 3 | [before](assets/guided-spatial-checkpoint/mobile-verify.png) | [after](assets/final-visual-checkpoint/12-mobile-scene3.png) | exact target remains visible; horizontal overflow 0 |

Additional evidence covers [another real Area](assets/final-visual-checkpoint/07-another-area.png), [an honest fallback Area](assets/final-visual-checkpoint/08-fallback-area.png), [mobile Scene 1](assets/final-visual-checkpoint/09-mobile-scene1.png), and [DPR 2 Scene 2](assets/final-visual-checkpoint/13-dpr2-scene2.png).

## Visual changes

- The system font stack, civic teal, neutral ink, dividers, focus treatment, and numeric alignment are defined as shared visual tokens. New fonts and third-party assets were not introduced.
- Public and Guided desktop layouts now use a 73/27 map/panel relationship. The map remains the largest first-three-second surface.
- Scene headings use a 24–30px scale and the landing uses a 32–36px scale. Supporting product text is 12–16px where it carries meaning.
- Scene 1 uses compact rows and one selected state instead of equal-weight cards. The visible select omits mesh codes while the accessible name and selected-Area contract remain stable.
- Scene 2 treats the verified Section as a second view of the same location. The map's exact A–B LineString remains `[[135.398125,35.44583333333334],[135.398125,35.45]]`; the plot exposes 94 terrain samples, 17 direct buildings, and 14 direct roads.
- Scene 3 uses a neutral exact-target treatment rather than a danger-like status. It shows the user-facing road name, four checks, and one `未確認`; source IDs stay in the machine contract rather than the initial reading path.
- Contextual legends contain at most three items. They are visible on desktop and removed where they duplicate the selected-state caption on 390px mobile.
- Decorative gradients, glass surfaces, glow, oversized rounded cards, and repeated English/system kickers are absent from the Public/Guided path. Spacing and type hierarchy do most grouping work.
- Map controls remain the zoom/display groups already available. No permanent 3D switch or layer catalog was added.

## Copy and state presentation

Public landing:

> 気になる場所を、地図とデータで確かめる。

Guided intro:

> 舞鶴の地域を、地図からたどる。

Scene questions:

1. `どの地域を詳しく見る？`
2. `{地域名}の地形と建物`
3. `ここで何を確かめる？`

Visible mesh codes, `GUIDED STORY`, `AWAITING_*`, validation codes, and loader internals were removed from the first reading path. Loading copy now says `詳細分析のデータを読み込んでいます` and explains that the selected region and display state remain intact. The existing finite timeout, retry, and return paths are unchanged.

No photo, GPS, answer, assignment, review, or simulated evidence appears in the Guided core. `回答や確認結果はまだありません。` is the terminal claim boundary.

## Layout and interaction measurements

| State | Map/panel | Controls | Primary CTA | Map occlusion | Horizontal overflow |
|---|---:|---:|---:|---:|---:|
| Desktop intro | 73/27 | 6 | 1 | 2.7% | 0px |
| Desktop Scene 1 | 73/27 | 10 | 1 | 3.8% | 0px |
| Desktop Scene 2 | 73/27 | 7 | 1 | 3.9% | 0px |
| Desktop Scene 3 | 73/27 | 8 | 0 terminal | 3.7% | 0px |
| Mobile Scene 1 | 43/57 vertical | 10 | 1 | 14.7% | 0px |
| Mobile Scene 2 | 55/45 vertical | 9 | 1 | 11.6% | 0px |
| Mobile Scene 3 | 42/58 vertical | 8 | 0 terminal | 14.2% | 0px |

The baseline Guided controls were 6/10/7/8 for intro/Scene 1/Scene 2/Scene 3, so the visual pass did not add actionable controls. Exact-task arrival is four clicks from Guided intro. There is one visible H1, at most one primary CTA, no document horizontal overflow, and no page-level Guided scroll in the audited states.

## Regression and performance

The Guided browser checkpoint passed:

- intro and all three scenes;
- six real Area switches in one MapLibre workspace;
- selected row/map synchronization;
- stale target and Section prevention;
- exact road and building geometry;
- point facility and Area fallback;
- A–B equality and Section ownership;
- 1440px, compact, mobile, and DPR 2 layouts;
- keyboard focus and reduced-motion behavior;
- legacy deep links;
- direct Advanced, Guided-to-Advanced, long URL reload, Back/Forward, bounded error, and retry.

Five fresh production-preview contexts produced these medians:

| Measurement | Median | Required gate | Result |
|---|---:|---:|---|
| Guided first meaningful render | 1,632.7ms | <=2,000ms | pass |
| Area context cold | 2,243.4ms | report-only | recorded |
| Exact road warm | 1,423.6ms | <=1,800ms | pass |
| Exact building warm | 719.7ms | <=2,500ms | pass |
| Return to Scene 2 | 1,252.9ms | <=2,000ms | pass |

The first sample was slower than the median (FMR 4,301.9ms), so the result is reported as a five-sample distribution rather than a best run. The profile deliberately blocks the external GSI basemap to isolate local application readiness; those expected blocked tile messages are not product request failures.

## Local gates

| Gate | Result |
|---|---|
| ESLint | pass |
| TypeScript | pass |
| Vitest | 27 files / 113 tests pass |
| Public production build | pass |
| Municipal production build | pass |
| Ruff | pass |
| Python unit/full non-DB suite | 417 pass; one third-party deprecation warning |
| Documentation links | 93 Markdown files pass before this file; rerun required before commit |
| `npm audit --audit-level=high` | 0 vulnerabilities |
| `pip-audit --skip-editable` | no known vulnerabilities; editable project intentionally skipped |
| Public first-run browser audit | pass; critical accessibility/diagnostics empty |
| Visual-identity browser audit | pass; console/local HTTP failures empty |
| PLATEAU-native browser audit | pass; all checks true |
| Guided spatial browser audit | pass; diagnostics empty |
| Guided-to-Advanced browser audit | pass; all flows and diagnostics clean |
| `git diff --check` | rerun required before commit |

Remote CI, feature Pages deployment, and production capture remain V4 work. The source branch has not been merged to `main`.

## Review boundary

Automated evidence supports that the defined visual, spatial, performance, and accessibility contracts remain intact. It does not establish whether people find the result aesthetically polished, understand it unaided, or can use the verification workflow in municipal work.

Current review states:

```text
READY_FOR_SELF_VISUAL_REVIEW
READY_FOR_DEMO_REVIEW
AWAITING_HUMAN_TEST
AWAITING_MUNICIPAL_WORKFLOW_REVIEW
HOLD_MAIN_PROMOTION
HOLD_P1_M4_M6
```
