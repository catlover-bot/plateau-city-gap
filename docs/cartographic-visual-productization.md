# Cartographic visual productization

Goal: `citygap-cartographic-visual-productization-v1`

This goal turns the Public map from a background into the answer to the selected Investigation Area. It preserves the completed first-run information architecture and changes only frontend cartography, presentation-only PLATEAU display geometry, and automated visual evidence.

## Active design rules

### Preserve geographic context

The Area must be recognizable within three seconds while roads, railway lines, place names, rivers, and the surrounding urban structure remain legible. Outside dimming is an adjustable starting treatment, not a fixed acceptance value. Browser evidence decides the final opacity. The Area is emphasized; the surroundings are not hidden.

### Summary is evidence, not navigation

Population/age, building use, establishments, urban planning, and transport remain Area Summary rows. Each row leads with its actual value and may include one small `地図で見る` action. The action can retain pressed state for accessibility, but the five rows may not form a tab bar, mode rail, or new top-level navigation.

### Wow comes from spatial meaning

The accepted moments are direct and causal:

```text
radius selection -> visible Investigation Area
Summary action -> one real thematic layer
Unknown selection -> only the related real object or honest fallback
target action -> camera and cartography move to the verified target
```

Decorative shadows, gradients, glow, animation, or excessive color do not count as product value. Motion only explains state changes and stops under `prefers-reduced-motion`.

## Data boundary

Existing public spatial packs are reused when their city, dataset version, and object identity match. Missing Public building footprints, road surfaces, or planning polygons may be deterministically extracted from the same checked-in Maizuru PLATEAU CityGML source/version. Each derivative records source SHA-256, source member lineage, object identity, generator/rule version, feature count, and artifact SHA-256.

Display derivatives contain geometry and explicit source attributes only. They do not add external data, inferred uses, population allocation, walking-network meaning, danger or hazard meaning, scores, field evidence, or policy conclusions. Exact object matching is required; unresolved targets remain a labelled reference-position or Area/mesh fallback.

## Visual grammar

- Area: evergreen soft fill and solid outline; outside treatment is tuned until orientation remains readable.
- Known/context: low-saturation blue-green, with a compact active-story legend.
- Unknown: amber plus a dashed outline and explicit `未確認` wording; never hazard red.
- Selected target: plum with a white halo or outline and a visible type label.
- Secondary context: slate at lower opacity.
- One thematic story at a time, alongside invariant Area/origin and selected target context.
- The default hero is two-dimensional. Current Public targets do not receive a 3D control because the existing UX-value gate rejects it.

## Stop state

C5 ends at an automated cartographic checkpoint. It prepares visual and human review but does not fabricate participant findings or promote the branch.

```text
AUTOMATED_CARTOGRAPHIC_CHECKPOINT_COMPLETE
READY_FOR_VISUAL_REVIEW
READY_FOR_HUMAN_TEST
AWAITING_HUMAN_TEST
AWAITING_MUNICIPAL_WORKFLOW_REVIEW
HOLD_MAIN_PROMOTION
HOLD_P1_M4_M6
```

## C5 checkpoint result

C0–C4 are implemented on `feat/cartographic-visual-productization-v1`. C5 captured the production build with the deterministic protocol in `frontend/scripts/capture-cartographic-checkpoint.mjs`; the machine-readable record is `assets/cartographic-checkpoint/manifest.json`.

Implemented cartographic sequence:

```text
Area confirmation
  -> deferred public cartography load
  -> 500m / 800m / 1km Area geometry
  -> one Summary story at a time
  -> Unknown-to-map emphasis
  -> exact PLATEAU object, registered reference position, or honest Area fallback
```

The initial Public route does not wait for the cartographic derivative. Loading begins 500 ms after Area confirmation. Until exact geometry is ready, the UI exposes a labelled reference-position or Area fallback and never invents an object shape.

Recorded automated results:

- Public FMR median: 1125 ms over five cold navigations.
- Area readiness: 500m 1278 ms; 800m 288 ms; 1km 1242 ms.
- Summary story switch: building use 4135 ms; establishments 1320 ms; urban planning 1077 ms; transport 1753 ms.
- Target readiness: road 2453 ms; building 12336 ms; facility reference 5057 ms.
- Exact target color signal: road 278 px; building 318 px; mobile road 1843 px at DPR 2.
- Registered facility reference signal: 164 px.
- Critical/serious accessibility violations and checkpoint gate failures: zero.

The exact target geometry is the existing PLATEAU source object, not a point substitute. A non-PLATEAU facility is explicitly a registered reference position. An unresolved case stays an Area/mesh fallback. The basemap-degraded capture demonstrates that checked-in local vectors remain visible and the missing background is disclosed.

The slower building story and building/facility target readiness are retained as review risks. Automated screenshots support review but do not establish three-second human recognition, comprehension, usefulness, or municipal workflow fit.

See `cartographic-validation-checkpoint.md` for the reproducible evidence and `cartographic-visual-review-package.md` for the intentionally empty human-review worksheet.
