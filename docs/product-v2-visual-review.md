# Product 2.0 visual review

## Baseline

The pre-implementation record is in `product-v2-baseline-audit.md` with five viewport captures. It established that the former screen used a pitched 3D-first map, competing outlines/points, technical workspace navigation, independent Validation SVG, and a long path to first value.

## Iteration 1 — shell and hierarchy

Reviewed all ten target screens at 1440×900 plus 390×844. The task shell and Inspector hierarchy were clear, but three defects remained: the legacy `.map-toolbar` rule shifted the new renderer switch partly off-canvas; the analysis mesh did not render; and Cesium initialization raced React Strict Mode cleanup. The shell selector was scoped, Cesium async guards were added, and map source state was instrumented.

## Iteration 2 — renderer diagnosis

The toolbar and runtime exception were fixed, but MapLibre still showed only the basemap. Browser evidence showed the worker URL loaded while every GeoJSON source stayed unresolved (`isSourceLoaded=false`, zero source features). The Vite worker was changed to the official self-contained `?worker&url` path. The same audit then reported 1,680 mesh source features, 537 rendered cells, and 11 visible top-candidate features, with no console error and no Cesium overview request.

The map palette and hierarchy were then tuned: normal cells became subdued, top candidates received an amber fill and dark outline, labels began at overview scale, and selected/non-selected focus contrast increased.

## Iteration 3 — task maps and 3D

Reviewed Discovery, selected mesh, transport, hazard, scenario compare, Validation routes, temporal change, municipal flow, and mobile. Validation routes now render on the GSI basemap; scenario sites and before/after states are distinct; hazard uses a restrained fill plus dashed outline; and mobile preserves enough map above the bottom sheet.

Temporal samples were initially invisible because the verified real dataset is Kunitachi rather than Maizuru. The temporal action now moves to the Kunitachi viewport and shows a “VALIDATION REFERENCE · 国立市” badge. Cesium used a target bounding-sphere camera and the same GSI pale imagery so the 3D frame cannot point into empty sky. The final 3D capture intentionally uses the tracked PLATEAU-covered deep-dive mesh rather than implying complete city coverage.

## Final evidence

The ten final images and machine-readable `audit.json` are under `docs/assets/product-v2/`. The audit covers 1440×900, 1280×800, 1024×768, 768×1024, and 390×844; all report no horizontal overflow, visible Inspector, named primary legend, and basemap attribution.
