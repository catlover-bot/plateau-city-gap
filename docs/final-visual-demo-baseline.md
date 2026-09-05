# Final visual polish and demo baseline

Goal: `final-visual-polish-and-demo-video-v1`

Captured: 2026-09-03 (Asia/Tokyo)

## Repository lock

| Check | Result |
|---|---|
| Branch | `feat/guided-spatial-storytelling-v1` |
| Starting HEAD | `dad536e87019f3e1b54dfca50fac9405adb23aac` |
| Remote feature HEAD | `dad536e87019f3e1b54dfca50fac9405adb23aac` |
| `origin/main` | `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff` |
| Worktree | clean |
| `git diff --check` | passed |
| Destructive history operations | none |

The visual work stays on the feature branch. It does not change the backend, database, migrations, datasets, analysis contracts, GitHub workflow, environment settings, or `main`.

## Product baseline

The production-preview build completed successfully from the starting HEAD in 82 seconds. The existing Guided browser suite passed its intro, three scenes, six-Area coverage, DPR 2, mobile, keyboard, deep-link, and single-map-instance checks. The first combined run encountered one aborted Area-context request while Guided unmounted for Advanced; an immediate dedicated Guided-to-Advanced regression run passed direct Advanced loading, cache reuse, back/forward, long URL reload, bounded failure, and retry with no page or console diagnostics. No product code was changed to obtain that result.

The current visual baseline is the immutable capture set in [`docs/assets/guided-spatial-checkpoint`](assets/guided-spatial-checkpoint/manifest.json). It records the intro, Area selection, six Scene 2 states, six Scene 3 states, road/building/facility targets, compact and DPR 2 Section views, and mobile map/Section/task views. Those captures render the same UI as the starting HEAD; the later commits only added checkpoint evidence and fixed the Guided-to-Advanced loader.

Observed baseline issues to address without adding features:

- The map is already the dominant surface, but the panel reads as a sequence of small technical labels and boxed notices rather than one clear civic story.
- Scene 1 gives equal visual weight to the shortlist, the 495-Area select, selected state, and CTA; the question and the chosen Area should dominate.
- Scene 2 has the right map/Section composition, but its compact labels, five-color Section legend, and note blocks are difficult to read on a presentation screen.
- Scene 3 presents the correct exact target and four checks, but the amber surface can be mistaken for warning severity and the boundary note competes with the checklist.
- Supporting text is frequently 9–11px. The final pass should use 12–16px wherever it carries product meaning.
- Mobile preserves the flow but needs a clearer map/Section mode relationship and more deliberate spacing around the fixed action.

## Performance baseline

The first five-sample run showed a transient local slowdown and failed four medians. A same-protocol repeat, without code changes, passed every required median:

| Measurement | Repeat median | Gate |
|---|---:|---:|
| Guided first meaningful render | 1,700.0ms | <= 2,000ms |
| Area context, cold | 2,426.4ms | report-only |
| Exact road target | 1,676.0ms | <= 1,800ms |
| Exact building target | 524.0ms | <= 2,500ms |
| Return to Scene 2 | 1,503.8ms | <= 2,000ms |

The prior tracked checkpoint remains a second reference: Guided FMR 851.3ms, Area cold 1,835.6ms, road 1,467.5ms, building 556.2ms, and return 794.0ms. The final checkpoint will report fresh five-sample medians rather than selecting the faster run.

## Browser benchmark

The benchmark evidence was opened in Chromium at 1440 x 900 before implementation. The retained [PLATEAU/cartographic reference manifest](assets/cartographic-benchmark/manifest.json) records the current comparison provenance. The larger superseded product-audit capture package remains recoverable from Git history. Third-party screenshots are research evidence only and are not reused in the product or demo video.

| Reference | Browser evidence | Useful principle | Explicit non-copy boundary |
|---|---|---|---|
| Felt | `TEXT_ONLY`; public product page rendered | Give the map a clear visual role and keep the primary action unmistakable | Do not copy its typeface, orange/green palette, toolbar, hero, or marketing language |
| Mapbox | `TEXT_ONLY`; public product page rendered | Use a short heading, one primary action, and generous negative space | Do not copy its black/blue brand treatment, navigation, buttons, or layout |
| ArcGIS Urban | `PARTIALLY_OBSERVED`; official UI documentation rendered | Separate overview, selection, and detail; show 3D only when it explains the selected object | Do not reproduce Esri navigation, panels, iconography, plan editor, or 3D styling |
| ArcGIS Field Maps | `PARTIALLY_OBSERVED`; official task/map documentation rendered | Keep the location and the immediate action together; use direct map interaction | Do not build or imitate a generic task list, collection form, or Field Maps status UI |
| ArcGIS StoryMaps | `PARTIALLY_OBSERVED`; official map-tour documentation rendered | Let one visual and one short narrative advance together | Do not copy StoryMaps templates, tour composition, typography, or authoring controls |
| Maptionnaire | `TEXT_ONLY`; public product page rendered | Explain the connection between spatial input and defensible evidence in one sentence | Do not copy its brand palette, survey patterns, page structure, or participation workflow |
| CARTO | `TEXT_ONLY`; public product page rendered | Place the map artifact beneath a concise value statement and avoid decorative dashboard chrome | Do not copy its dark theme, blue accents, widgets, navigation, or marketing composition |
| iwagaki viewer | `CAPTURED`; live 3D viewer rendered | A map and a section can explain the same location when their direction and focus stay synchronized | Do not copy its dark UI, hazard simulation, controls, color ramp, wording, or section design |
| Tide Viewer | `SHELL_CAPTURED_RENDER_UNCONFIRMED`; live shell rendered but the main visualization did not become evidentially ready | Keep source notes and controls subordinate to the spatial view | Do not infer the missing render or copy its dark shell, menu, controls, or tide semantics |
| PLATEAU Transit PoC | `ACCESS_UNAVAILABLE_FOR_VISUAL_CAPTURE`; HTTP 200 but no visual body was available | No visual conclusion | Do not infer, reproduce, or describe an unavailable interface |

## Adopted design principles

1. The map is the persistent primary surface; the right panel asks one question and offers one next action.
2. Space, type scale, and dividers establish hierarchy before borders, badges, or color.
3. Area, Section, and exact target remain the same source-linked spatial story; animation only confirms a user action.
4. Scene 2 is the presentation hero: map above, readable A–B Section below, explanation beside it.
5. Unknown is a neutral evidence boundary, not a danger state. Exact targets use a distinct cartographic mark without implying risk.
6. Internal identifiers, loader state names, and provenance detail remain available to tests and Advanced, not in the first reading path.
7. Mobile uses a deliberate map/Section switch and 44px actions rather than compressing the desktop composition.

## Tooling checkpoint

Playwright is available from the existing frontend toolchain. Neither WSL nor Windows currently exposes `ffmpeg` or `ffprobe`, and the existing Python environment does not contain an FFmpeg wrapper. This does not block V1–V4 or browser-native WebM recording. V5 must use a non-repository system FFmpeg toolchain before producing MP4; the project dependency graph will not be changed and an MP4 will not be fabricated if that toolchain remains unavailable.

## Claim boundary

This baseline authorizes automated visual and demo-readiness work only. It does not claim that a human understood the flow, that the design is aesthetically approved, or that the municipal workflow is validated.
