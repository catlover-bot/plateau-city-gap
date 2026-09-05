# Harbor Atlas visual identity baseline

Goal: `harbor-atlas-visual-identity-ux-v2`

Milestone: S0 baseline lock

This is an automated source, browser, and capture checkpoint. It records the starting visual system and the implementation contracts that the Harbor Atlas pass must preserve. It is not a human aesthetic, comprehension, accessibility, or municipal-workflow result.

## Source lock

| Item | Value |
|---|---|
| Branch | `feat/guided-spatial-storytelling-v1` |
| Starting HEAD / upstream | `7e75a132e7f135db2dcdcf2b26e4b1d833381586` |
| `origin/main` | `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff` |
| Initial worktree | clean |
| Capture environment | local production build and preview |
| Capture URL | `http://127.0.0.1:4174/plateau-city-gap/` |
| Browser protocol | Playwright Chromium, reduced motion, font and compositor readiness |

The starting branch, HEAD, upstream, main comparison, status, and 12-commit history were checked before any write. No main merge, reset, rebase, squash, clean, discard, or force push was performed.

## Baseline evidence

- [Core capture manifest](assets/harbor-atlas-v2/before/manifest.json): 17 state and viewport captures, zero diagnostics.
- [Supplemental capture manifest](assets/harbor-atlas-v2/before/supplement-manifest.json): Scene 1 hover, registered facility, Public 1920 x 1080, Advanced loading, and Advanced ready; five captures, zero diagnostics.
- [Performance profile](assets/harbor-atlas-v2/before/performance.json): five fresh browser contexts under one production-preview protocol.
- [Visual inventory](assets/harbor-atlas-v2/before/inventory.json): five responsive Advanced viewports plus source and build asset measurements.
- Palette study: three capture-only candidates were evaluated across Public, Guided, Section, mobile, grayscale, protanopia, and deuteranopia states. Harbor Atlas was selected; the superseded exploration rasters remain recoverable from Git history rather than the current checkout.
- [Evidence index](assets/harbor-atlas-v2/manifest.json): paths, counts, source hashes, and the selected palette.

The retained baseline contains the product screenshots required for direct before/after comparison. Desktop widths 1280, 1440, and 1920, mobile 390 x 844, and DPR 2 are represented across the Harbor checkpoint package. The existing demo video package is preserved unchanged; its source predates this visual pass and remains a reference rather than new Harbor Atlas evidence.

## Visual inventory

The source begins with 48 distinct `--cg-*` custom-property definitions. Across all frontend CSS, TS, and TSX sources there are 948 raw hexadecimal color occurrences and 629 distinct literals; this broad count includes Advanced visualization palettes and test/source constants, so it is a debt indicator rather than a target for global replacement. Public and Guided must converge on semantic tokens while Advanced-only analytical color remains available where meaning requires it.

The existing responsive visual audit reports:

| Viewport | Visible accents | Shadows | Floating surfaces | Horizontal overflow |
|---|---:|---:|---:|---:|
| 1440 x 900 | 3 | 2 | 3 | 0 |
| 1280 x 800 | 3 | 2 | 3 | 0 |
| 1024 x 768 | 3 | 2 | 3 | 0 |
| 768 x 1024 | 3 | 2 | 3 | 0 |
| 390 x 844 | 3 | 2 | 4 | 0 |

The visible audit accents are the legacy teal pair and amber. The production captures also expose a separate purple Section/A-B language, so Public and Guided do not yet read as one controlled two-family system.

## Starting visual findings

- The prior map-refinement pass already makes the selected Area and exact target functional and preserves geographic context, but the visual identity is still assembled from legacy teal, amber, purple, and neutral-blue families.
- Scene 1 gives selected and hovered rows similar pale-teal weight. Selection has a non-color rule, but hover needs a quieter, clearly temporary state.
- The 495 Area polygons remain visible as low-opacity context; the default three named candidates are useful, but Harbor hierarchy must make one selected Area unmistakable without strengthening every Area.
- Scene 2 correctly presents map and Section as two views of the same place. Its Section still uses purple for A/B endpoints and the focused line, which conflicts with the intended Harbor spatial language.
- Scene 3 exact road/building/facility states are geometrically honest and labeled, but the target emphasis inherits amber while headings and spatial selection inherit teal. Harbor Atlas will reserve Signal for the exact target and decisive action.
- The honest Area fallback is visually distinct through dashed geometry and must remain distinct after recoloring.
- The Inspector has a sound question/name/facts/action order, but its nested neutral panels and repeated divider treatments can be simplified without changing copy claims or workflow steps.
- The mobile Section is readable and has no horizontal overflow, yet labels and axis typography sit near the lower acceptable bound and need stronger type/line contrast.
- Public/Guided already avoid gradients and excessive rounding. The baseline Advanced audit reports zero gradients, two shadows, and no class-named cards at desktop widths.

## Palette decision

Candidate A, **Harbor Atlas**, is selected for implementation.

| Role | Harbor Atlas | Civic Graphite | Paper Map |
|---|---|---|---|
| Character | maritime civic, calm, spatial | restrained institutional neutral | warm editorial cartography |
| Area/navigation family | Harbor blue-green | desaturated blue-green | slate blue |
| Exact-target family | Signal coral | ochre | brick |
| Decision | selected | not selected | not selected |

Harbor Atlas gives the clearest relationship to Maizuru's maritime geography while keeping the UI neutral enough for dense map evidence. Civic Graphite is controlled but undersells spatial identity. Paper Map is attractive but its warmer base competes more with roads and Signal. The capture-only study adds no theme selector and changes no runtime product state.

The selected seed values are locked as:

```text
Ink #15242B                 Ink soft #526269
Paper #F5F5F1               Surface #FCFCF9
Surface muted #EEF1EF       Line #D7DDDA
Line strong #87959A

Harbor strong #164F63       Harbor #26758A
Harbor soft #77AEB6         Sea glass #C9E1DE
Harbor pale #E8F2EF

Signal strong #A94736       Signal target #D9664D
Signal soft #F1A085         Signal pale #F7E4DE

Building #9BA9AD            Building outline #596970
Road #E5DDD1                Road outline #667279
Terrain #5D7476             Focus #F0B84B
Error #B34E49
```

The grayscale simulation keeps the Section profile, buildings, roads, selected Area border, and labels distinguishable through value, line, and form. The protanopia and deuteranopia simulations show that the current target is still identifiable through its outline, halo, label, and Inspector structure; the implementation must retain those non-color cues while changing the target to Signal.

## Locked product contracts

The visual pass may change presentation and copy hierarchy, but it must preserve:

- one persistent MapLibre instance and one canonical selected Area;
- the 495-Area catalog, selected-Area lazy context, six-Area switching, and stale-request rejection;
- exact road and building geometry, registered facility position, honest Area fallback, and target-specific checks;
- exact A-B source/ownership equality, Section provenance, map focus, annotation collision layout, and responsive map/Section switching;
- Guided deep links, Back/Forward, legacy routes, and a first spatial action within one click;
- the Guided-to-Advanced single-flight, finite timeout, cached-ready, error, and retry behavior;
- Public, Advanced, and Municipal routes, claim boundaries, keyboard behavior, reduced motion, and existing accessibility/performance gates;
- the existing demo video files without recapture during implementation.

## Performance baseline

| Measurement | Median | V2 gate | Baseline result |
|---|---:|---:|---|
| First meaningful render | 314.9 ms | <= 2,000 ms | pass |
| Area context cold | 477.7 ms | <= 1,500 ms | pass |
| Exact road warm | 270.8 ms | <= 1,200 ms | pass |
| Exact building warm | 270.6 ms | <= 1,200 ms | pass |
| Return/building-story warm | 272.8 ms | <= 1,200 ms | pass |

The existing Section captures keep static annotation calculation below 16 ms in the baseline matrix, with zero measured overlap, outside-plot labels, endpoint conflicts, tick conflicts, or horizontal overflow. Final comparison must use the same protocol and may not regress any median by more than 20%.

## S0 decision

`BASELINE_LOCKED / PALETTE_A_SELECTED / READY_FOR_S1`

Human visual quality, unaided comprehension, accessibility acceptance, and municipal workflow value remain unclaimed.
