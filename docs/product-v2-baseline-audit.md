# Product System & Spatial UX 2.0 — implementation baseline

Audit date: 2026-08-27. Baseline: `551570c83ab320517ecbca94aa421f5b3180e121`.
The five baseline screenshots were captured from the deployed GitHub Pages application, not from a mock.

## Evidence reviewed before implementation

- `docs/assets/product-v2/baseline/1440x900.png`
- `docs/assets/product-v2/baseline/1280x800.png`
- `docs/assets/product-v2/baseline/1024x768.png`
- `docs/assets/product-v2/baseline/768x1024.png`
- `docs/assets/product-v2/baseline/390x844.png`
- Existing discovery and validation captures in `docs/assets/final-v2/`

## Why the current map is difficult to read

1. The city overview is a pitched Cesium scene even though the primary task is reading and comparing 500 m meshes. In a fresh/headless session the geographic basemap is visually weak or blank while analysis points remain visible, so the points lose municipal context.
2. Meshes, station/medical symbols, candidate symbols, PLATEAU context, selection and story overlays share one renderer and compete for attention. At the discovery step every mesh outline is visible and large point sets are unclustered.
3. A single `PLATEAU 3D・道路` switch conflates buildings and roads; terrain, land use, planning and hazards are not represented as independently governed product layers.
4. Five technical workspaces plus two cities and methodology are exposed as a horizontal button wall. At 390 px the labels wrap and the first decision is about system architecture rather than the user's task.
5. Workspace transitions do not share a formal city/state/selection/map-mode URL contract. The same selected place cannot be reliably shared or carried through discovery, scenario and validation.
6. The validation primary map is a normalized SVG without a basemap. It proves route geometry is present but not where the disagreement is located in the city.
7. Internal status names such as `cross_validated` and `awaiting_field_validation` dominate validation content before plain-language meaning.
8. Legends exist, but their placement and style vary by workspace. Layer checkboxes, metric buttons, story controls and right-panel tabs do not form one coherent spatial interaction model.
9. Tablet is an incidental collapse of the desktop layout. Mobile uses a lower panel, but it inherits the desktop navigation and control density instead of a map-first bottom-sheet task flow.
10. `App.tsx` (729 lines), `CesiumMap.tsx` (1,027 lines) and `styles.css` (3,012 lines) combine application routing, state, map rendering, feature styling and responsive presentation.

## Product-system decisions

- MapLibre GL JS is the primary north-up 2D analytical renderer. It supports raster/vector tiles, GeoJSON clustering and an attribution control while preserving the existing PostGIS MVT contract.
- GSI pale raster tiles are the public basemap. The map visibly attributes the Geospatial Information Authority of Japan and links to the official tile catalogue.
- Cesium remains the PLATEAU detail renderer and is loaded only after an explicit `PLATEAU 3D` action.
- One shared spatial context owns city, urban state, task, typed selection, scenario, validation sample, map mode and viewport; the state is serialized to the URL.
- One layer registry and renderer-neutral adapter contract govern both map engines. Task presets replace checkbox-first operation.
- A shared Context Inspector and deterministic PLATEAU lineage replace workspace-specific map-side panel architectures.

