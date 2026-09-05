# Final product UI/UX polish

Goal: `final-product-uiux-polish-v1`. Starting branch `feat/guided-spatial-storytelling-v1`, HEAD/upstream/remote `bb41d3c1aff385953b65d61c20f040d9c007d952`. Remote main remains `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`; this checkout has no local `origin/main` ref. GitHub authentication was verified. This is agent review, not human acceptance.

Status: **visual correction required before publication**. All six after-images were inspected, not merely generated. They show a remaining Public headline split inside “地図”, a thin automatic Public/Guided heading outline inherited from `foundation.css`, and the Section elevation-axis label extending 3 CSS px beyond the left viewport (measured x=-3). The black outer heading box is removed, but the entire automatic outline is not. These are real residual defects, not passed aesthetic acceptance. The planned refinement/capture limit has been reached; a narrowly scoped correction and replacement after-captures were requested from the user. No final CI or Pages deployment has been dispatched.

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
