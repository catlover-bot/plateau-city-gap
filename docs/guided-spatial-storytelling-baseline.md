# Guided spatial storytelling baseline

Goal: `guided-spatial-storytelling-v1`

## Repository lock

- Source branch: `feat/public-product-language-section-v1`
- Source HEAD: `356dd90d49e7d736553de7596bb9cee619d1b692`
- Execution branch: `feat/guided-spatial-storytelling-v1`
- Baseline: `origin/main` at `2f28cd1089eda576c3002ebb2fb3e0f2b62123ff`
- Required baseline CI: run `33606249675`, success
- Worktree before branch creation: clean

No reset, clean, rebase, squash, force push, main merge, or Pages deployment is authorized.

## Verified starting problems

- Production Guided uses six page-like steps; the feature source uses four steps but still replaces the MapLibre map with a separate 3D surface in the PLATEAU step.
- Production Guide 3 allocates 248 px to the complete section and 162 px to the SVG. Its automated screenshot can contain a blank 3D stage.
- Production Guide 4 exposes 28 checks; Guide 5 exposes 183 controls and a 9,737 px scrolling form; Guide 6 exposes internal review codes.
- The active Guided selection falls back to the first of three candidates when a different mesh is selected.
- `guidedCase.ts`, `verificationModel.ts`, `UrbanSection.tsx`, and `CesiumMap.tsx` contain constants tied to mesh `533513314` or its spatial pack.
- The URL parser accepts `guide=1...6`; the feature source clamps 5 and 6 to 4.

## Source and capability facts

- `mesh_metrics.geojson` contains 495 real Maizuru 500 m Areas with population, 65+ population, and straight-line transport/medical context.
- The pinned Maizuru 2025 CityGML archive is locally available and its recorded SHA-256 is `13f4020ade066dc7139b7653c47a55a09af0093dee743f6b9cca5d3177a71cff`.
- It contains citywide official buildings and road surfaces and is the preferred source for deterministic Area display membership.
- The verified section belongs only to spatial pack `maizuru-533513314-plateau-2025-v1`.
- Its A/B LineString is `[135.398125, 35.44583333333334] -> [135.398125, 35.45]`, with 94 terrain samples, 17 directly intersecting buildings, and 14 road intersections.
- Current default verification road/building targets do not occur in that section artifact. No target-to-section relationship may be implied.

## Implementation overrides

1. Scene changes occur inside one mounted spatial workspace and must not recreate the MapLibre instance.
2. Area context is core; Urban Section is optional.
3. Citywide verified CityGML is preferred over patching local display artifacts.
4. Core checks describe unknown urban conditions; photo and GPS capture remain in Advanced/HOLD scope.
5. The initial catalog remains light; PLATEAU objects and detailed provenance load lazily per selected Area.

Every primary Guided interaction must document and test the spatial change it causes.
