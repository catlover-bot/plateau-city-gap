# Map architecture

## Renderer roles

- MapLibre GL JS is the default renderer for reading, finding, and comparing. It is north-up, pitch 0, and uses the GSI pale basemap.
- Cesium is an explicit detail renderer for PLATEAU building, road, and terrain context. It is never the default overview and is lazy-loaded.
- `MapEngineAdapter` isolates domain components from renderer APIs with `setViewport`, `getViewport`, `fitBounds`, `setSelection`, `setLayers`, `highlight`, `clearHighlight`, and `exportView`.

MapLibre's module worker is bundled through Vite's `?worker&url` pipeline. This is necessary to produce a self-contained worker; a sibling-module worker silently left GeoJSON sources unresolved during visual QA.

## Map state model

The state machine uses `overview`, `focus`, `detail3d`, `compare`, `placement`, and `validation`. Selecting an entity enters focus; opening 3D enters detail; scenario compare uses synchronized maps; Validation uses the same basemap and engine.

## 2D pipeline

The current static deployment passes GeoJSON through the same layer contract that supports MVT URLs and public fallbacks. It renders the municipal boundary, 500m mesh, clustered stations/bus/medical points, PLATEAU roads, scenario sites and mesh results, resilience geometries, validation routes, and temporal samples.

The city overview shows the primary thematic layer and emphasizes only top candidates. Detailed mesh edges become visible at district zoom. Facility clusters have minimum zooms and collision-managed labels. Selection is a strong dark outline and dims non-selected analysis fill.

## 3D pipeline

`Plateau3DMap` is a renderer wrapper around the retained Cesium implementation. It carries the selected mesh into Cesium, loads buildings and roads independently, renders mesh as a thin contextual overlay, and returns building clicks through the unified selection contract. The camera uses a target bounding sphere, ensuring the chosen location stays in view. GSI pale imagery provides the same geographic context and credit as 2D.

## Comparison

Desktop scenario comparison uses two MapLibre instances sharing the same spatial viewport and selection. The left is current state and the right is scenario state. Tablet/mobile uses a single after view with a clearly labelled state because two sub-390px maps would be misleading.

Validation routes use solid blue for the PLATEAU experimental graph and dashed green for the reference graph. Temporal validation moves to the verified reference city (Kunitachi) and displays a map badge so the global product city is not mistaken for the validation dataset.
