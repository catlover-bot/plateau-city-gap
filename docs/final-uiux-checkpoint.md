# Final product UI/UX polish

Goal: `final-product-uiux-polish-v1`. Starting branch `feat/guided-spatial-storytelling-v1`, HEAD/upstream/remote `bb41d3c1aff385953b65d61c20f040d9c007d952`. Remote main remains `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`; this checkout has no local `origin/main` ref. GitHub authentication was verified. This is agent review, not human acceptance.

Status: **three authorized corrections implemented; publication withheld for a separate required overlap failure**. The user resumed this existing goal from branch/HEAD/upstream/remote `685f518b5d012a83c2acd56d535dfce148fd6487`, authorizing one additional correction pass and at most six affected review images. Source correction is `cfb66e9a13f79400c3f4d1e31e1859577ed1be9f`. No rollback, cleanup, main promotion, media regeneration, or expanded UI correction is authorized.

## Authorized correction pass — 2026-09-05

- Public keeps the complete heading and existing font size. Two locally non-breaking phrase spans prevent splitting 地図; an explicit unchanged accessible name preserves the original exact heading contract.
- Public/Guided non-interactive H1 focus movement and `tabIndex=-1` remain. The foundation focus rule now matches the existing token rule's H1 exclusion; buttons, links, inputs, map and Section controls retain the existing 3px gold / dark keyboard indicator. No global `outline:none` was added.
- Readable Section elevation-title x/rotation origin moves from 10 to 16. Its native rendered left margin changes from -3 to +3 CSS px. Font size, labels, axis/tick positions, A/B, analysis data and legacy non-readable geometry remain unchanged. All visible Section text is now explicitly tested for SVG containment.

Lint, TypeScript, 37 files / 219 unit tests, production build and diff check pass. The direct three-fix checks pass at 1440/1280/390/320 CSS px and actual Chrome 200% (1440×900 → 720×450, `getZoom=2`, DPR 1→2, visual scale 1). Existing Guided spatial, Guided→Advanced loading/retry, PLATEAU-native and five-viewport identity regressions remain supported by retained reports. The final validation record distinguishes the initial candidate from the final accessible-name build; it does not misattribute earlier tests.

The mandatory native-Chrome Guided 1440 Section overlap guard fails on **two transient focus-detail lines**, not the corrected elevation axis: “道路 · 47m · 標高96.4m” has y=687.703125..703.703125, while “直接交差” has y=702.703125..718.703125. Their baselines are 15px apart but native text boxes are 16px tall: 1 CSS px overlap. These unchanged `y=85/100` lines predate this pass. This is a bounding-box failure, not proof that glyph ink touches; the existing non-overlap criterion is nevertheless not waived. Changing that spacing is outside the three approved fixes. **Do not deploy this candidate while this required check fails.**

Two other audit failures are preserved with their diagnosis: inline-block phrases initially introduced accessibility-name whitespace (fixed in the H1, without weakening the exact Public selector; final nine-state Public audit passes); desktop software-rendered Cesium credits were inspected before the split layout settled (the test now additionally requires actual non-overlapping split geometry, existing strict 3D readiness and two frames, retaining every unobscured-focus assertion). The single affected final rerun still times out at the 5-second split-layout gate for Guided 1440; Guided 1280 settles and passes. This final 1440 failure remains unresolved, not waived as a known timing issue. Native credit focus passed. No assertion was skipped, relaxed or repeatedly rerun until green.

Old before/defective-after images, their manifest and validation record remain immutable. The new [correction-pass review](uiux-review/final-product-polish/correction-pass/manifest.json) contains exactly six images from one capture set, all visually inspected: Public 1440, Guided heading 1280, selected Guided Section 1440, selected Advanced Section 1920, mobile Section 390 and Public 320. It is separate UI evidence, not adopted presentation material or full acceptance. Captures have zero unexpected diagnostics; 57 optional GSI pale-tile cancellations are retained separately. The initial user-owned two image deletions/two untracked copies are excluded from staging. Fresh binary diffs, exclusive copy backups and SHA-256 inventories are retained at `/tmp/citygap-uiux-resume.JW6Icv90/preservation/`, including all 125 existing asset files, both older backup directories and the old review package. No new Pages run or production-performance comparison is claimed; the last verified publication remains `bb41d3c1aff385953b65d61c20f040d9c007d952`, Pages `33947973445`.

## Historical first-pass record

The sections below describe the preserved first pass (`061c940` / `685f518`), not acceptance of the resumed candidate. Its six inspected after-images exposed the Public word split, automatic H1 outline and -3px axis clipping that led to this explicitly authorized correction pass.

## Scope and observed problems

The first audit used six new real-browser images from the published starting UI: Public 1440×900, Guided selection 1280×720, selected Guided 3D and its Section 1440×900, Advanced 3D 1920×1080, and mobile Section 390×844. Field checks and smaller/zoom layouts were inspected without extra images. Existing product benchmarks were reused; no new design theme or external product survey was introduced.

| Screen → observed problem | Scoped change | Verification |
| --- | --- | --- |
| Public → long broken headline and a large automatic heading-focus box | Shorter place-specific heading and reduced heading-focus box; neutral 3D example link remains visible | Public→3D passes; remaining line break and gold outline are explicitly unresolved |
| Guided selection → kicker, heading and lead repeat the same instruction | One heading and one map/list instruction; statistical year and straight-line distance meaning remain beside rows | Same selected Area/495 choices; null remains missing, not zero |
| Guided building → large tinted attribute card and several competing explanation blocks | Neutral definition list with Signal selection edge; distinct regional population and intersection counts; remove redundant Section note | Real picked ID/usage/height/floors, region vs object semantics |
| Field checks → conversational heading and misleading “survey” action | “現地で確認すること” and “詳細分析を開く”; original checks and unconfirmed state unchanged | Same target/check IDs and actual Advanced destination |
| Advanced → map slogan, duplicate Section action and small specialist panel text | Compact place heading; selected object first, regional statistics separate below; neutral panels and 12px+ notes; one Section entry plus close | Actual pick/attributes/Section/target, standard analysis tools retained |
| Section → SVG scaling reduces text below 12 CSS px | Measure displayed width; retain collision-aware layout and larger axes/header/footer | Actual text ≥12px and no overlap; left axis-label clipping still needs correction |
| Section → picked building lacks persistent annotation; hover resembles selection | Pass existing selected object; exact-member persistent callout; distinct transient hover | Typed membership, selection/hover/leave, unchanged camera callbacks |
| Mobile/zoom → fixed map minimum pushes the panel below the viewport with no usable reading area | Page reflow with bounded map/Section surface and preserved primary/back actions | 320/390 CSS px, actual browser 200%, keyboard visibility and overlap |

No geometry, DEM, A–B coordinates, analysis values, source attributes, check meanings, loaders, backend, dependencies, workflows, or expert features are changed. Public/Guided 3D remains prominent; unsupported Areas retain their own honest fallback.

## Evidence and preservation

The [six-pair review manifest](uiux-review/final-product-polish/manifest.json) identifies URL, viewport, actual source commit, selected state, SHA-256 and diagnostics. Before source is `bb41d3c1aff385953b65d61c20f040d9c007d952`; refined application source is `061c940e22229f7bb37d0fa2adb0d77141bbd8ce`. These are UI-review evidence, not replacement slides or recordings. No local-after timing is compared with the production baseline.

Before editing, binary staged/unstaged diffs and both untracked image copies were preserved without overwriting anything at `/tmp/citygap-final-uiux-T9ufrF5y/preservation-v2/`. SHA-256 inventories cover all 125 existing files under `docs/assets/` and 27 files in the two existing backup directories. All eight adopted `docs/assets/judging-3d/` files also match reference commit `4d724f32e7c286ae8e8335d7c1b3d54ab5682ef2`. No browser profile, font, or secret was copied into this backup.

The initial browser audit had zero unexpected diagnostics; optional GSI tile cancellations during navigation/camera changes were retained separately, not blanket-ignored. One warm production sample on the same hardware measured 3D readiness 1160.258ms, real pick 689.412ms and Section 773.818ms. The final comparison must use the same production/warm protocol, not local-vs-production or 2D-vs-3D timings.

Local gates pass: lint, TypeScript, 37 test files / 212 tests, build, diff check, Public nine-state audit, Guided spatial and Advanced transition, PLATEAU-native 19/19, five-viewport identity, and strict legacy 3D readiness. [Local evidence](uiux-review/final-product-polish/local-validation.json) maps each report to its actual tested build. Required 320/390 layouts and actual Chrome browser 200% (1440×900 → 720×450, browser zoom factor 2, not pinch zoom) pass: rendered Section text ≥12px, horizontal page overflow 0, no serious/critical axe findings, visible keyboard focus, 44px primary controls, reduced motion and Section/3D return. Incomplete automated accessibility results remain; no full WCAG claim is made.

Earlier checks found and corrected hidden mobile Cesium focus, obscured Section keyboard focus, the explicit return-to-3D action, and first-visible mobile annotation density. One overlapping local rebuild caused a Public navigation failure and a legacy readiness check's required-data 404s; each passed one justified retry. One immediate mobile return visibility assertion failed; a bounded diagnostic found both immediate and settled visibility correct (12ms visible-state wait), without reproducing a persistent defect. The audit now additionally requires the post-interaction visible/non-inert/Section-closed state. All original failures and these boundaries are retained, not blanket-ignored.

The local docs checker reports only the two pre-existing missing presentation-image paths; their user-owned copies remain unstaged. Exact-commit CI checks the committed originals. This checkpoint is packaged before publication: the release handoff must identify the final HEAD, exact nine-job CI and Pages runs, matching live entry/chunk bytes, production interaction, same-condition warm performance comparison and end-of-task preservation result. It does not preclaim those commit-dependent gates.

## Remaining boundaries

Guided currently serializes the selected Area after a 3D building pick, so URL reload restores the Area rather than that in-memory building. Advanced restores exact object identity from its parent-mesh URL, but height/floors may need a fresh model pick. This task does not introduce a larger selection/attribute-loading redesign. Direct 3D road mouse picking is not claimed verified by an ID-mapping unit test.

The adopted 42-second Guided media and every previous media/provenance set are frozen historical captures. Their appearance may differ from the refined UI; their operations and data meanings remain supported. Current occupancy, entrances, walkability, effectiveness, human understanding, WCAG-wide acceptance and municipal adoption remain unverified.
